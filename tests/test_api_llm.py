import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from src.api_llm import (DailyQuotaExceeded, EmptyResponse, GeminiLLM, LimitedCachedLLM, LLMError, RateLimited,
                         TransientError, classify_error, make_llm)
from src.llm import LLMResult, MockLLM


# ---------- dobles de prueba ----------
def fake_response(text="hola", pin=10, cand=5, thoughts=0, finish="STOP"):
    usage = SimpleNamespace(prompt_token_count=pin, candidates_token_count=cand, thoughts_token_count=thoughts)
    return SimpleNamespace(text=text, usage_metadata=usage,
                           candidates=[SimpleNamespace(finish_reason=finish)], prompt_feedback=None)


class FakeClient:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []
        self.models = SimpleNamespace(generate_content=self._gen)

    def _gen(self, *, model, contents, config=None):
        self.calls.append({"model": model, "contents": contents, "config": config})
        r = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(r, Exception):
            raise r
        return r


class Err(Exception):
    def __init__(self, code):
        super().__init__(f"http {code}")
        self.code = code


class Scripted:
    """LLM interno guionado: lista de resultados o excepciones."""
    def __init__(self, *items, **sig):
        self.items, self.n, self._sig = list(items), 0, sig

    def signature(self):
        return self._sig

    def call(self, agent, prompt, sample=0):
        self.n += 1
        it = self.items.pop(0) if len(self.items) > 1 else self.items[0]
        if isinstance(it, Exception):
            raise it
        return it


class Clock:
    def __init__(self):
        self.t, self.sleeps = 0.0, []

    def clock(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


def make(tmp_path, inner, **kw):
    c = Clock()
    kw.setdefault("rpm", 6000)
    llm = LimitedCachedLLM(inner, str(tmp_path / "cache"), clock=c.clock, sleep=c.sleep, **kw)
    return llm, c


OKR = LLMResult("ok", 7, 3)


# ---------- GeminiLLM ----------
def test_gemini_mapea_texto_tokens_y_config():
    client = FakeClient(fake_response("respuesta", pin=12, cand=5, thoughts=40))
    llm = GeminiLLM("gemini-x", temperature=0.2, max_output_tokens=999, thinking_level="low", seed=10, client=client)
    r = llm.call("planner", "pregunta", sample=2)
    assert (r.text, r.tokens_in, r.tokens_out) == ("respuesta", 12, 45)       # incluye tokens de razonamiento
    c = client.calls[0]
    assert c["model"] == "gemini-x" and c["contents"] == "pregunta"
    assert c["config"] == {"temperature": 0.2, "max_output_tokens": 999, "seed": 12,
                           "thinking_config": {"thinking_level": "low"}}


def test_gemini_config_minima_no_incluye_opcionales():
    client = FakeClient(fake_response())
    GeminiLLM("m", client=client).call("a", "p")
    assert client.calls[0]["config"] == {"temperature": 0.0, "max_output_tokens": 8192}


def test_gemini_respuesta_vacia_y_sin_metadatos_de_uso():
    with pytest.raises(EmptyResponse, match="MAX_TOKENS"):
        GeminiLLM("m", client=FakeClient(fake_response(text=None, finish="MAX_TOKENS"))).call("a", "p")
    sin_uso = SimpleNamespace(text="x", usage_metadata=None, candidates=[], prompt_feedback=None)
    r = GeminiLLM("m", client=FakeClient(sin_uso)).call("a", "p")
    assert (r.tokens_in, r.tokens_out) == (0, 0)


def test_gemini_traduce_errores_del_sdk():
    for code, kind in [(429, RateLimited), (503, TransientError), (500, TransientError)]:
        with pytest.raises(kind):
            GeminiLLM("m", client=FakeClient(Err(code))).call("a", "p")
    with pytest.raises(LLMError) as e:
        GeminiLLM("m", client=FakeClient(Err(401))).call("a", "p")
    assert not isinstance(e.value, (RateLimited, TransientError))


def test_classify_error():
    ConnectError = type("ConnectError", (Exception,), {"__module__": "httpx"})
    assert isinstance(classify_error(ConnectError("x")), TransientError)
    assert isinstance(classify_error(TimeoutError()), TransientError)
    c = classify_error(ValueError("raro"))
    assert type(c) is LLMError


def test_gemini_sin_clave(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    pytest.importorskip("google.genai")
    with pytest.raises(LLMError, match="GEMINI_API_KEY"):
        GeminiLLM("m")


def test_la_config_es_valida_para_el_sdk_real():
    types = pytest.importorskip("google.genai.types")
    cfg = GeminiLLM("m", thinking_level="low", seed=1, client=FakeClient(fake_response()))._config(0)
    parsed = types.GenerateContentConfig.model_validate(cfg)
    assert parsed.temperature == 0.0 and parsed.seed == 1 and parsed.thinking_config is not None


# ---------- caché ----------
def test_cache_evita_la_segunda_llamada_y_conserva_tokens(tmp_path):
    inner = Scripted(OKR, model="m")
    llm, _ = make(tmp_path, inner)
    a, b = llm.call("planner", "p"), llm.call("planner", "p")
    assert a == b == OKR and inner.n == 1
    assert llm.stats["cache_hits"] == 1 and llm.stats["real_calls"] == 1 and llm.calls_today() == 1


def test_la_clave_distingue_agente_prompt_sample_y_configuracion(tmp_path):
    inner = Scripted(OKR, model="m", temperature=0)
    llm, _ = make(tmp_path, inner)
    llm.call("planner", "p"); llm.call("critic", "p"); llm.call("planner", "q"); llm.call("planner", "p", sample=1)
    assert inner.n == 4
    otro = Scripted(OKR, model="m", temperature=0.7)
    llm2 = LimitedCachedLLM(otro, str(tmp_path / "cache"))
    llm2.call("planner", "p")
    assert otro.n == 1                                       # otra temperatura => no reutiliza la caché


def test_la_cache_persiste_entre_instancias_y_tolera_lineas_corruptas(tmp_path):
    llm, _ = make(tmp_path, Scripted(OKR, model="m"))
    llm.call("a", "p")
    with (tmp_path / "cache" / "llm_cache.jsonl").open("a", encoding="utf-8") as f:
        f.write('{"key": "trunc')                             # simula una caída a mitad de escritura
    inner2 = Scripted(OKR, model="m")
    llm2, _ = make(tmp_path, inner2)
    assert llm2.call("a", "p") == OKR and inner2.n == 0


def test_errores_y_respuestas_vacias_no_se_guardan(tmp_path):
    inner = Scripted(EmptyResponse("vacía"), OKR, model="m")
    llm, _ = make(tmp_path, inner)
    with pytest.raises(EmptyResponse):
        llm.call("a", "p")
    assert llm.call("a", "p") == OKR and inner.n == 2         # el fallo no quedó en caché


def test_solicitudes_identicas_concurrentes_llaman_una_vez(tmp_path):
    inner = Scripted(OKR, model="m")
    llm, _ = make(tmp_path, inner)
    with_threads = [threading.Thread(target=llm.call, args=("a", "p")) for _ in range(8)]
    [t.start() for t in with_threads]
    [t.join() for t in with_threads]
    assert inner.n == 1


def test_inner_sin_parametro_sample_funciona(tmp_path):
    mock = MockLLM({"planner": ["hola"]})
    llm, _ = make(tmp_path, mock)
    assert llm.call("planner", "x", sample=3).text == "hola"


# ---------- ritmo, reintentos y tope diario ----------
def test_espaciado_entre_llamadas_reales(tmp_path):
    llm, c = make(tmp_path, Scripted(OKR, model="m"), rpm=30)            # 1 llamada cada 2 s
    for i in range(3):
        llm.call("a", f"p{i}")
    assert [round(s, 3) for s in c.sleeps] == [2.0, 2.0]                 # la primera no espera


def test_reintenta_ante_429_con_espera_creciente(tmp_path):
    inner = Scripted(RateLimited("429"), TransientError("503"), OKR, model="m")
    llm, c = make(tmp_path, inner, backoff=(10, 30, 60))
    assert llm.call("a", "p") == OKR
    assert inner.n == 3 and [s for s in c.sleeps if s >= 10] == [10, 30]
    assert llm.calls_today() == 3 and llm.stats["retries"] == 2          # cada intento cuenta contra el cupo


def test_se_rinde_tras_agotar_los_reintentos(tmp_path):
    inner = Scripted(RateLimited("429"), model="m")
    llm, _ = make(tmp_path, inner, backoff=(1, 1))
    with pytest.raises(RateLimited):
        llm.call("a", "p")
    assert inner.n == 3


def test_error_fatal_no_se_reintenta(tmp_path):
    inner = Scripted(LLMError("clave inválida"), model="m")
    llm, _ = make(tmp_path, inner)
    with pytest.raises(LLMError, match="clave"):
        llm.call("a", "p")
    assert inner.n == 1


def test_tope_diario_persiste_y_no_bloquea_la_cache(tmp_path):
    t0 = datetime(2026, 11, 5, 20, 0, tzinfo=timezone.utc)
    clock_now = {"t": t0}
    inner = Scripted(OKR, model="m")
    llm, _ = make(tmp_path, inner, daily_cap=2, now=lambda: clock_now["t"])
    llm.call("a", "p1"); llm.call("a", "p2")
    with pytest.raises(DailyQuotaExceeded, match="LLM_DAILY_CAP"):
        llm.call("a", "p3")
    assert llm.call("a", "p1") == OKR                                    # lo que ya está en caché sigue disponible
    llm2, _ = make(tmp_path, Scripted(OKR, model="m"), daily_cap=2, now=lambda: clock_now["t"])
    with pytest.raises(DailyQuotaExceeded):
        llm2.call("a", "p4")                                             # el contador sobrevive al reinicio
    clock_now["t"] = t0 + timedelta(days=1)                              # al día siguiente se reinicia
    assert llm2.call("a", "p4") == OKR


def test_make_llm_usa_variables_de_entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "modelo-env")
    monkeypatch.setenv("LLM_RPM", "7")
    monkeypatch.setenv("LLM_DAILY_CAP", "123")
    llm = make_llm(cache_dir=str(tmp_path / "c"), client=FakeClient(fake_response()))
    assert llm.inner.model == "modelo-env" and llm.rpm == 7 and llm.daily_cap == 123
