"""Verificador Lean 4 con REPL persistente (Plan B).

Problema que resuelve: `lake env lean archivo.lean` vuelve a cargar todo Mathlib en CADA llamada
(minutos en tu equipo). Aquí el REPL de Lean carga `import Mathlib` UNA sola vez, guarda ese
entorno en memoria (env base) y cada verificación se ejecuta sobre ese entorno.

Misma interfaz que LeanVerifier:  verifier(lean_code, expected_statement=None) -> (bool, trace)
Mismo criterio de aceptación (NFR-1): sin errores, sin sorry, solo axiomas estándar.

Notas de uso
- La primera llamada (o `start()`) paga el import completo; las demás reutilizan el entorno.
- Un REPL = un proceso con Mathlib cargado (varios GB de RAM). Usa UNA instancia a la vez.
- Si una verificación excede `call_timeout`, el REPL no se puede interrumpir: se mata y se
  reinicia en la siguiente llamada (pagando de nuevo el import). `maxHeartbeats` en el
  encabezado reduce esos casos porque corta tácticas costosas de forma determinista.
- `restart_every` reinicia el REPL cada N verificaciones para acotar el crecimiento de memoria.
"""
import collections
import json
import queue
import re
import subprocess
import threading
import time

from .verifier_lean import HEADER, NAME, OK_AXIOMS, _norm

AXIOMS = re.compile(r"depends on axioms: \[([^\]]*)\]")


class ReplError(RuntimeError):
    pass


class LeanReplVerifier:
    def __init__(self, project_dir: str, repl_bin: str = "/opt/lean/repl/.lake/build/bin/repl",
                 header: str = HEADER, startup_timeout: float = 1800, call_timeout: float = 300,
                 restart_every: int | None = 500, repl_cmd: list[str] | None = None):
        self.project_dir, self.repl_bin, self.header = project_dir, repl_bin, header
        self.startup_timeout, self.call_timeout = startup_timeout, call_timeout
        self.restart_every, self.repl_cmd = restart_every, repl_cmd
        self._proc = None
        self._q: queue.Queue | None = None
        self._err: collections.deque = collections.deque(maxlen=40)
        self._env: int | None = None
        self._calls = 0
        self.starts = 0                       # cuántas veces se (re)inició el REPL
        self.startup_seconds: float | None = None

    # ---------- proceso ----------
    @staticmethod
    def _pump_out(proc, q):
        for line in proc.stdout:
            q.put(line.rstrip("\n"))
        q.put(None)                           # EOF

    @staticmethod
    def _pump_err(proc, buf):
        for line in proc.stderr:
            buf.append(line.rstrip("\n"))

    def _spawn(self):
        cmd = self.repl_cmd or ["lake", "env", self.repl_bin]
        self._proc = subprocess.Popen(cmd, cwd=self.project_dir, stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True, encoding="utf-8", bufsize=1)
        self._q = queue.Queue()
        self._err.clear()
        threading.Thread(target=self._pump_out, args=(self._proc, self._q), daemon=True).start()
        threading.Thread(target=self._pump_err, args=(self._proc, self._err), daemon=True).start()

    def close(self):
        p, self._proc, self._env, self._calls = self._proc, None, None, 0
        if p is not None:
            try:
                p.kill()
                p.wait(timeout=10)
            except Exception:
                pass

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.close()

    # ---------- protocolo JSON (comandos separados por línea en blanco) ----------
    def _request(self, payload: dict, timeout: float) -> dict:
        try:
            self._proc.stdin.write(json.dumps(payload) + "\n\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise ReplError(f"no se pudo escribir al REPL: {e}; stderr: {self._tail()}")
        lines, deadline = [], time.monotonic() + timeout
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError()
            try:
                line = self._q.get(timeout=left)
            except queue.Empty:
                raise TimeoutError()
            if line is None:
                raise ReplError(f"el REPL terminó inesperadamente; stderr: {self._tail()}")
            if line == "":
                if lines:
                    break
                continue
            lines.append(line)
        try:
            return json.loads("\n".join(lines))
        except json.JSONDecodeError as e:
            raise ReplError(f"respuesta no es JSON ({e}): {' '.join(lines)[:300]}")

    def _tail(self) -> str:
        return " | ".join(list(self._err)[-5:])[:500]

    def start(self):
        """Arranca el REPL y carga el encabezado (import Mathlib) una vez."""
        if self._proc is not None and self._proc.poll() is None and self._env is not None:
            return
        self.close()
        t0 = time.perf_counter()
        self._spawn()
        self.starts += 1
        try:
            resp = self._request({"cmd": self.header}, self.startup_timeout)
        except Exception:
            self.close()
            raise
        errs = [m for m in resp.get("messages", []) if m.get("severity") == "error"]
        if errs or "env" not in resp:
            self.close()
            raise ReplError(f"falló el encabezado: {self._fmt(errs) or resp}")
        self._env = resp["env"]
        self.startup_seconds = time.perf_counter() - t0

    # ---------- verificación ----------
    def __call__(self, lean_code: str, expected_statement: str | None = None):
        code = "\n".join(l for l in lean_code.splitlines() if not l.strip().startswith("import "))
        names = NAME.findall(code)
        if not names:
            return False, "formalization_failure: no theorem/lemma found"
        if expected_statement and _norm(expected_statement) not in _norm(code):
            return False, "misformalization: statement differs from the dataset's"
        src = code + "".join(f"\n#print axioms {n}" for n in names)
        if self.restart_every and self._calls >= self.restart_every:
            self.close()
        self.start()      # fuera del try: si el REPL no arranca es un error de infraestructura
        try:              # (se propaga), NO un veredicto sobre la prueba
            resp = self._request({"cmd": src, "env": self._env}, self.call_timeout)
            self._calls += 1
        except TimeoutError:
            self.close()
            return False, "timeout"
        except ReplError as e:
            self.close()
            return False, f"repl_error: {e}"
        if "env" not in resp and "message" in resp:      # error de protocolo del REPL
            self.close()
            return False, f"repl_error: {resp['message']}"
        return self._judge(resp)

    @staticmethod
    def _fmt(msgs) -> str:
        out = []
        for m in msgs:
            pos = m.get("pos") or {}
            out.append(f"{pos.get('line', '?')}:{pos.get('column', '?')}: "
                       f"{m.get('severity', '?')}: {m.get('data', '')}")
        return "\n".join(out)[:4000]

    def _judge(self, resp: dict):
        msgs = resp.get("messages", [])
        errors = [m for m in msgs if m.get("severity") == "error"]
        if errors:
            return False, self._fmt(errors)
        if resp.get("sorries") or any("sorry" in m.get("data", "")
                                      for m in msgs if m.get("severity") == "warning"):
            return False, "uses sorry:\n" + self._fmt(msgs)
        for m in msgs:
            found = AXIOMS.search(m.get("data", ""))
            if found:
                bad = {a.strip() for a in found.group(1).split(",") if a.strip()} - OK_AXIOMS
                if bad:
                    return False, f"non-standard axioms: {sorted(bad)}"
        return True, ""
