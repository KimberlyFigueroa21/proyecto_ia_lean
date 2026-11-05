"""Servidor de verificación: UN REPL de Lean con Mathlib cargado, atendido por HTTP local.

Por qué: arrancar el REPL con `import Mathlib` tarda ~6 minutos. Con este servidor lo pagas una
vez por sesión de trabajo; tus scripts (líneas base, runner de ablación) lo consultan al instante.

Uso (DENTRO del contenedor, desde /workspace/proyecto_ia_lean):
    mkdir -p logs
    setsid nohup python3 -m src.verify_server > logs/verify_server.log 2>&1 &
    python3 -m src.verify_client            # estado: starting -> ready
    kill $(cat logs/verify_server.pid)      # detener (cierra también el REPL)

Endpoints (solo 127.0.0.1, dentro del contenedor; no se expone a Windows ni a la red):
    GET  /health   -> {"status": "starting|ready|error", "calls", "starts", "startup_seconds", ...}
    POST /verify   {"lean_code": str, "expected_statement": str|null} -> {"verdict", "trace", "seconds"}
    POST /restart  -> reinicia el REPL (útil si quedó en estado "error")

Las verificaciones se atienden de una en una (un REPL = un proceso con Mathlib en memoria).
No ejecutes smoke_repl.py mientras el servidor corre: serían dos REPL con Mathlib en RAM.
"""
import argparse
import json
import os
import signal
import sys
import threading
import time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .verifier_lean import HEADER
from .verifier_repl import LeanReplVerifier

MAX_BODY = 1_000_000


class ServiceUnavailable(RuntimeError):
    pass


def _log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


class VerifyService:
    def __init__(self, verifier: LeanReplVerifier):
        self.v = verifier
        self.lock = threading.Lock()          # una verificación a la vez
        self.status = "starting"              # starting | ready | error
        self.error: str | None = None
        self.calls = 0
        self.t0 = time.time()

    def _boot(self):
        with self.lock:
            try:
                self.v.start()
                self.status, self.error = "ready", None
                _log(f"REPL listo en {self.v.startup_seconds:.1f} s")
            except Exception as e:                      # noqa: BLE001
                self.status, self.error = "error", f"{type(e).__name__}: {e}"
                _log(f"ERROR al arrancar el REPL: {self.error}")

    def start_async(self):
        threading.Thread(target=self._boot, daemon=True).start()

    def restart(self):
        self.status, self.error = "starting", None

        def run():
            with self.lock:
                self.v.close()
            self._boot()

        threading.Thread(target=run, daemon=True).start()

    def health(self) -> dict:
        return {"status": self.status, "error": self.error, "calls": self.calls,
                "starts": self.v.starts, "startup_seconds": self.v.startup_seconds,
                "uptime_s": round(time.time() - self.t0)}

    def verify(self, code: str, expected: str | None):
        if self.status == "error":
            raise ServiceUnavailable(self.error or "el REPL está en estado de error; usa POST /restart")
        with self.lock:
            t = time.perf_counter()
            try:
                ok, trace = self.v(code, expected)
            except Exception as e:                      # noqa: BLE001  (fallo de infraestructura)
                self.status, self.error = "error", f"{type(e).__name__}: {e}"
                _log(f"ERROR de infraestructura: {self.error}")
                raise ServiceUnavailable(self.error)
            dt = time.perf_counter() - t
            self.calls += 1
            self.status = "ready"
        _log(f"verify #{self.calls}: verdict={ok} {dt:.2f}s")
        return ok, trace, dt


class _Handler(BaseHTTPRequestHandler):
    svc: VerifyService = None                 # lo fija make_server

    def log_message(self, fmt, *args):        # silencia el log por defecto de http.server
        pass

    def _json(self, code: int, obj: dict):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ValueError("cuerpo demasiado grande")
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if self.path == "/health":
            return self._json(200, self.svc.health())
        self._json(404, {"error": "ruta desconocida"})

    def do_POST(self):
        try:
            data = self._body()
        except ValueError as e:                # incluye JSONDecodeError
            return self._json(400, {"error": f"JSON inválido: {e}"})
        if self.path == "/verify":
            code, expected = data.get("lean_code"), data.get("expected_statement")
            if not isinstance(code, str) or not (expected is None or isinstance(expected, str)):
                return self._json(400, {"error": "se requiere 'lean_code' (str)"})
            try:
                ok, trace, dt = self.svc.verify(code, expected)
            except ServiceUnavailable as e:
                return self._json(503, {"error": str(e)})
            return self._json(200, {"verdict": ok, "trace": trace, "seconds": round(dt, 3)})
        if self.path == "/restart":
            self.svc.restart()
            return self._json(202, {"status": "starting"})
        self._json(404, {"error": "ruta desconocida"})


def make_server(service: VerifyService, host: str = "127.0.0.1", port: int = 8765):
    handler = type("Handler", (_Handler,), {"svc": service})
    return ThreadingHTTPServer((host, port), handler)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default="/opt/lean/LeanMathlibProject")
    ap.add_argument("--repl-bin", default="/opt/lean/repl/.lake/build/bin/repl")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--call-timeout", type=float, default=300)
    ap.add_argument("--pidfile", default="logs/verify_server.pid")
    ap.add_argument("--repl-cmd", default=None, help=argparse.SUPPRESS)   # solo para pruebas (lista JSON)
    ap.add_argument("--minimal", action="store_true",
                    help="encabezado con import pequeño (pruebas de cableado, arranca en segundos)")
    a = ap.parse_args()

    header = "import Mathlib.Data.Nat.Basic\n" if a.minimal else HEADER
    verifier = LeanReplVerifier(a.project, repl_bin=a.repl_bin, header=header,
                                call_timeout=a.call_timeout, restart_every=None,
                                repl_cmd=json.loads(a.repl_cmd) if a.repl_cmd else None)
    service = VerifyService(verifier)
    server = make_server(service, a.host, a.port)       # primero el puerto: si ya hay un servidor, falla aquí
    pidfile = Path(a.pidfile)
    pidfile.parent.mkdir(parents=True, exist_ok=True)
    pidfile.write_text(str(os.getpid()))                 # para detenerlo con: kill $(cat logs/verify_server.pid)
    _log(f"escuchando en http://{a.host}:{a.port}  (encabezado: {header.splitlines()[0]})")
    service.start_async()
    _log("arrancando el REPL; con `import Mathlib` completo tarda varios minutos")

    def stop(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.serve_forever()
    finally:
        verifier.close()                                # evita dejar un REPL huérfano ocupando RAM
        pidfile.unlink(missing_ok=True)
        _log("servidor detenido")


if __name__ == "__main__":
    main()
