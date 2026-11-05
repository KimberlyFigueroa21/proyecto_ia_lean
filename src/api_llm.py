"""Cliente LLM real (Gemini) + envoltorio con caché, limitador de ritmo, reintentos y tope diario.

    llm = make_llm()                         # lee GEMINI_API_KEY (y opcionalmente GEMINI_MODEL, LLM_RPM, LLM_DAILY_CAP)
    r = llm.call("planner", "Divide este problema ...")   # -> LLMResult(text, tokens_in, tokens_out)

Sirve directamente como `llm` de build_graph(...): cumple el protocolo LLM de src/llm.py.

Qué hace cada capa
- GeminiLLM: una llamada al SDK oficial `google-genai`. Traduce los errores a tres clases:
  RateLimited (429), TransientError (5xx / red) -> se reintentan; LLMError (clave, modelo, petición) -> no.
- LimitedCachedLLM: (1) caché en disco: repetir una corrida o depurar NO gasta cupo ni cambia los
  resultados (NFR-2); (2) espaciado entre llamadas (rpm); (3) reintentos con espera creciente;
  (4) tope diario persistente (DailyQuotaExceeded) para no quemar el cupo gratuito.

Notas
- Los tokens de una respuesta en caché son los de la llamada ORIGINAL (así las métricas de eficiencia
  no dependen de si la corrida se repitió). El cupo solo se gasta en llamadas reales.
- `tokens_out` incluye los tokens de razonamiento interno del modelo (también cuentan y se cobran).
- Cada intento real cuenta contra el cupo diario, incluso si falla (el proveedor también lo cuenta).
- El día del cupo se reinicia a medianoche de la hora del Pacífico (según la documentación de terceros
  consultada); aquí se aproxima con zoneinfo, o con UTC-8 fijo si el contenedor no trae tzdata.
- Las respuestas vacías y los errores NO se guardan en caché.
"""
import hashlib
import inspect
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .llm import LLMResult

DEFAULT_MODEL = "gemini-3.8-flash"     # estable según la documentación consultada (nov 2026); los IDs rotan rápido


class LLMError(RuntimeError):
    """Error no reintentable (clave inválida, modelo inexistente, petición rechazada...)."""


class RateLimited(LLMError):
    """HTTP 429: demasiadas peticiones o cupo agotado."""


class TransientError(LLMError):
    """Fallo temporal: 5xx o de red."""


class EmptyResponse(LLMError):
    """El modelo no devolvió texto (bloqueo de seguridad o se agotó max_output_tokens)."""


class DailyQuotaExceeded(LLMError):
    """Se alcanzó el tope diario configurado."""


def classify_error(e: Exception) -> LLMError:
    code = getattr(e, "code", None)
    msg = f"{type(e).__name__}: {e}"[:500]
    if code == 429:
        return RateLimited(msg)
    if isinstance(code, int) and code >= 500:
        return TransientError(msg)
    if isinstance(code, int):
        return LLMError(f"HTTP {code} (no se reintenta): {msg}")
    module = type(e).__module__ or ""
    if isinstance(e, (TimeoutError, ConnectionError)) or module.startswith(("httpx", "httpcore", "requests", "urllib3")):
        return TransientError(msg)
    return LLMError(msg)


class GeminiLLM:
    def __init__(self, model: str = DEFAULT_MODEL, temperature: float = 0.0, max_output_tokens: int = 8192,
                 thinking_level: str | None = None, seed: int | None = None,
                 api_key: str | None = None, client=None):
        if client is None:
            from google import genai                         # pip install google-genai
            key = api_key or os.environ.get("GEMINI_API_KEY")
            if not key:
                raise LLMError("Falta la clave de API: define la variable de entorno GEMINI_API_KEY")
            client = genai.Client(api_key=key)
        self.client, self.model = client, model
        self.temperature, self.max_output_tokens = temperature, max_output_tokens
        self.thinking_level, self.seed = thinking_level, seed

    def signature(self) -> dict:
        """Todo lo que cambia la respuesta: forma parte de la clave de la caché."""
        return {"model": self.model, "temperature": self.temperature, "max_output_tokens": self.max_output_tokens,
                "thinking_level": self.thinking_level, "seed": self.seed}

    def _config(self, sample: int) -> dict:
        cfg = {"temperature": self.temperature, "max_output_tokens": self.max_output_tokens}
        if self.seed is not None:
            cfg["seed"] = self.seed + sample
        if self.thinking_level:
            cfg["thinking_config"] = {"thinking_level": self.thinking_level}
        return cfg

    def call(self, agent: str, prompt: str, sample: int = 0) -> LLMResult:
        try:
            resp = self.client.models.generate_content(model=self.model, contents=prompt,
                                                       config=self._config(sample))
        except LLMError:
            raise
        except Exception as e:                               # noqa: BLE001
            raise classify_error(e) from e
        try:
            text = resp.text or ""
        except Exception:                                    # noqa: BLE001
            text = ""
        if not text.strip():
            cands = getattr(resp, "candidates", None) or []
            finish = getattr(cands[0], "finish_reason", None) if cands else None
            block = getattr(getattr(resp, "prompt_feedback", None), "block_reason", None)
            raise EmptyResponse(f"respuesta vacía (finish_reason={finish}, block_reason={block}). Si fue "
                                f"MAX_TOKENS, sube max_output_tokens: el razonamiento interno también consume tokens")
        u = getattr(resp, "usage_metadata", None)
        tin = getattr(u, "prompt_token_count", 0) or 0
        tout = (getattr(u, "candidates_token_count", 0) or 0) + (getattr(u, "thoughts_token_count", 0) or 0)
        return LLMResult(text, tin, tout)


def _pacific_now(now: datetime) -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return now.astimezone(ZoneInfo("America/Los_Angeles"))
    except Exception:                                        # sin tzdata en el contenedor
        return now.astimezone(timezone(timedelta(hours=-8)))


class LimitedCachedLLM:
    def __init__(self, inner, cache_dir: str = "cache", *, rpm: float = 10, daily_cap: int = 500,
                 backoff: tuple = (10, 30, 60, 120), clock=time.monotonic, sleep=time.sleep, now=None):
        self.inner, self.rpm, self.daily_cap, self.backoff = inner, rpm, daily_cap, tuple(backoff)
        self._clock, self._sleep = clock, sleep
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._cache_path, self._quota_path = self._dir / "llm_cache.jsonl", self._dir / "quota.json"
        self._lock, self._call_lock = threading.Lock(), threading.Lock()
        self._last_call = float("-inf")
        self._accepts_sample = "sample" in inspect.signature(inner.call).parameters
        self.cache_hits = self.real_calls = self.retries = 0
        self._cache: dict[str, dict] = {}
        if self._cache_path.exists():
            for line in self._cache_path.read_text(encoding="utf-8").splitlines():
                try:
                    rec = json.loads(line)
                    self._cache[rec["key"]] = rec
                except (ValueError, KeyError):
                    continue                                 # línea truncada por una caída: se ignora

    # ---------- utilidades ----------
    def _signature(self) -> dict:
        return self.inner.signature() if hasattr(self.inner, "signature") else {}

    def _key(self, agent: str, prompt: str, sample: int) -> str:
        blob = json.dumps([self._signature(), agent, prompt, sample], sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _today(self) -> str:
        return _pacific_now(self._now()).date().isoformat()

    def calls_today(self) -> int:
        try:
            q = json.loads(self._quota_path.read_text(encoding="utf-8"))
            return q["n"] if q.get("day") == self._today() else 0
        except (OSError, ValueError, KeyError):
            return 0

    def _reserve_quota(self):
        n = self.calls_today()
        if n >= self.daily_cap:
            raise DailyQuotaExceeded(
                f"Tope diario alcanzado: {n}/{self.daily_cap} llamadas reales hoy (día del Pacífico "
                f"{self._today()}). Se reinicia a medianoche del Pacífico. Si el límite real de tu proyecto "
                f"es mayor, sube LLM_DAILY_CAP.")
        tmp = self._quota_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"day": self._today(), "n": n + 1}), encoding="utf-8")
        os.replace(tmp, self._quota_path)

    def _pace(self):
        wait = self._last_call + 60.0 / self.rpm - self._clock()
        if wait > 0:
            self._sleep(wait)
        self._last_call = self._clock()

    def _store(self, key: str, agent: str, res: LLMResult):
        rec = {"key": key, "agent": agent, "signature": self._signature(), "text": res.text,
               "tokens_in": res.tokens_in, "tokens_out": res.tokens_out, "day": self._today()}
        with self._cache_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
        self._cache[key] = rec

    @property
    def stats(self) -> dict:
        return {"cache_hits": self.cache_hits, "real_calls": self.real_calls, "retries": self.retries,
                "calls_today": self.calls_today(), "daily_cap": self.daily_cap, "cached_entries": len(self._cache),
                "signature": self._signature()}

    # ---------- llamada ----------
    def _hit(self, key: str) -> LLMResult | None:
        rec = self._cache.get(key)
        if rec is None:
            return None
        self.cache_hits += 1
        return LLMResult(rec["text"], rec["tokens_in"], rec["tokens_out"])

    def call(self, agent: str, prompt: str, sample: int = 0) -> LLMResult:
        key = self._key(agent, prompt, sample)
        with self._lock:
            hit = self._hit(key)
        if hit:
            return hit
        with self._call_lock:                                # las llamadas reales van de una en una
            with self._lock:
                hit = self._hit(key)                         # otro hilo pudo resolverla mientras esperábamos
            if hit:
                return hit
            last_error: LLMError | None = None
            for attempt in range(1 + len(self.backoff)):
                if attempt:
                    self._sleep(self.backoff[attempt - 1])
                self._reserve_quota()
                self._pace()
                try:
                    res = (self.inner.call(agent, prompt, sample=sample) if self._accepts_sample
                           else self.inner.call(agent, prompt))
                except (RateLimited, TransientError) as e:
                    last_error = e
                    self.retries += 1
                    continue
                self.real_calls += 1
                with self._lock:
                    self._store(key, agent, res)
                return res
            raise last_error


def make_llm(model: str | None = None, *, temperature: float = 0.0, max_output_tokens: int = 8192,
             thinking_level: str | None = None, seed: int | None = None, cache_dir: str = "cache",
             rpm: float | None = None, daily_cap: int | None = None, client=None) -> LimitedCachedLLM:
    inner = GeminiLLM(model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL), temperature, max_output_tokens,
                      thinking_level, seed, client=client)
    return LimitedCachedLLM(inner, cache_dir,
                            rpm=float(rpm or os.environ.get("LLM_RPM", 10)),
                            daily_cap=int(daily_cap or os.environ.get("LLM_DAILY_CAP", 500)))
