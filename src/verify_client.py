"""Cliente del servidor de verificación. Misma interfaz que LeanVerifier / LeanReplVerifier:

    verifier = RemoteVerifier()                       # http://127.0.0.1:8765
    ok, trace = verifier(lean_code, expected_statement=None)

Sirve directamente como `verifier` de build_graph(...). Si el servidor aún está arrancando el REPL,
la primera llamada espera (con sondeos a /health) en vez de fallar.
Estado rápido:  python3 -m src.verify_client
"""
import json
import sys
import time
import urllib.error
import urllib.request

START_HINT = ("setsid nohup python3 -m src.verify_server > logs/verify_server.log 2>&1 &   "
              "(desde /workspace/proyecto_ia_lean)")


class VerifierUnavailable(RuntimeError):
    """El servidor no responde o el REPL está en error. NO es un veredicto sobre la prueba."""


class RemoteVerifier:
    def __init__(self, url: str = "http://127.0.0.1:8765", request_timeout: float = 2400,
                 ready_timeout: float = 2400, poll: float = 5.0):
        self.url = url.rstrip("/")
        self.request_timeout, self.ready_timeout, self.poll = request_timeout, ready_timeout, poll
        self._ready = False

    def _call(self, method: str, path: str, payload: dict | None = None, timeout: float = 30):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.url + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            try:
                msg = json.loads(body).get("error", body)
            except ValueError:
                msg = body
            if e.code == 503:
                raise VerifierUnavailable(msg)
            raise RuntimeError(f"HTTP {e.code}: {msg}")
        except TimeoutError:
            raise VerifierUnavailable(f"tiempo de espera agotado hablando con {self.url}")
        except urllib.error.URLError as e:
            raise VerifierUnavailable(f"no hay servidor de verificación en {self.url} ({e.reason}). "
                                      f"Inícialo con: {START_HINT}")

    def health(self) -> dict:
        return self._call("GET", "/health")

    def restart(self):
        self._ready = False
        return self._call("POST", "/restart", {})

    def wait_ready(self, timeout: float | None = None) -> dict:
        deadline = time.monotonic() + (timeout or self.ready_timeout)
        while True:
            h = self.health()
            if h["status"] == "ready":
                self._ready = True
                return h
            if h["status"] == "error":
                raise VerifierUnavailable(h.get("error") or "el servidor reporta error")
            if time.monotonic() > deadline:
                raise VerifierUnavailable("el REPL no estuvo listo a tiempo")
            time.sleep(self.poll)

    def __call__(self, lean_code: str, expected_statement: str | None = None):
        if not self._ready:
            self.wait_ready()
        r = self._call("POST", "/verify",
                       {"lean_code": lean_code, "expected_statement": expected_statement},
                       timeout=self.request_timeout)
        return r["verdict"], r["trace"]


if __name__ == "__main__":
    try:
        print(json.dumps(RemoteVerifier().health(), indent=2, ensure_ascii=False))
    except VerifierUnavailable as e:
        print(e)
        sys.exit(1)
