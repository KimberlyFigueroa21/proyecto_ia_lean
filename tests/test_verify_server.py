import json
import sys
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from src.verifier_repl import LeanReplVerifier
from src.verify_client import RemoteVerifier, VerifierUnavailable
from src.verify_server import VerifyService, make_server

FAKE = str(Path(__file__).parent / "fake_repl.py")
OK = "theorem t1 (a b : ℕ) : a + b = b + a := by omega"


@pytest.fixture
def stack(tmp_path):
    verifier = LeanReplVerifier(str(tmp_path), header="import Mathlib\n",
                                repl_cmd=[sys.executable, FAKE])
    service = VerifyService(verifier)
    server = make_server(service, "127.0.0.1", 0)           # puerto libre
    threading.Thread(target=server.serve_forever, daemon=True).start()
    service.start_async()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    client = RemoteVerifier(url, poll=0.05, request_timeout=30, ready_timeout=30)
    yield client, service, url
    server.shutdown()
    verifier.close()


def post(url, path, body: bytes):
    req = urllib.request.Request(url + path, data=body, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_health_pasa_a_ready(stack):
    client, _, _ = stack
    h = client.wait_ready()
    assert h["status"] == "ready" and h["starts"] == 1


def test_los_cinco_casos_por_http(stack):
    client, _, _ = stack
    assert client(OK) == (True, "")
    ok, tr = client("theorem t3 (a b : ℕ) : a + b = b + a := by sorry")
    assert not ok and "sorry" in tr
    ok, tr = client("theorem t4 (a b : ℕ) : a + b = b + a := by exact zzz")
    assert not ok and "unknown identifier" in tr
    ok, tr = client("axiom ax : False\ntheorem t5 : 1 = 2 := ax.elim")
    assert not ok and "non-standard axioms" in tr
    ok, tr = client(OK, expected_statement="theorem t1 (a b : ℕ) : a * b = b * a")
    assert not ok and "misformalization" in tr


def test_un_solo_arranque_para_muchas_llamadas(stack):
    client, _, _ = stack
    for _ in range(5):
        assert client(OK)[0]
    h = client.health()
    assert h["starts"] == 1 and h["calls"] == 5


def test_peticiones_concurrentes_se_serializan(stack):
    client, _, _ = stack
    with ThreadPoolExecutor(6) as pool:
        results = list(pool.map(lambda _: client(OK), range(12)))
    assert all(r == (True, "") for r in results)
    assert client.health()["calls"] == 12


def test_servidor_no_disponible():
    with pytest.raises(VerifierUnavailable, match="no hay servidor"):
        RemoteVerifier("http://127.0.0.1:1", ready_timeout=2).health()


def test_json_invalido_y_campos_faltantes(stack):
    _, _, url = stack
    assert post(url, "/verify", b"esto no es json")[0] == 400
    assert post(url, "/verify", b"{}")[0] == 400
    assert post(url, "/nada", b"{}")[0] == 404


def test_restart(stack):
    client, _, _ = stack
    client.wait_ready()
    client.restart()
    h = client.wait_ready()
    assert h["starts"] == 2 and client(OK)[0]


def test_fallo_de_arranque_no_es_un_veredicto(tmp_path):
    verifier = LeanReplVerifier(str(tmp_path), header="import Mathlib\n",
                                repl_cmd=[sys.executable, "-c", "import sys; sys.exit(1)"])
    service = VerifyService(verifier)
    server = make_server(service, "127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    service.start_async()
    client = RemoteVerifier(f"http://127.0.0.1:{server.server_address[1]}", poll=0.05, ready_timeout=10)
    try:
        with pytest.raises(VerifierUnavailable):
            client(OK)                            # debe lanzar excepción, NO devolver (False, ...)
    finally:
        server.shutdown()
        verifier.close()
