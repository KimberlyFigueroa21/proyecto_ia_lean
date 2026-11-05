import sys
from pathlib import Path

import pytest

from src.verifier_repl import LeanReplVerifier

FAKE = str(Path(__file__).parent / "fake_repl.py")
OK = "theorem t1 (a b : ℕ) : a + b = b + a := by omega"


def make(tmp_path, **kw):
    return LeanReplVerifier(str(tmp_path), header="import Mathlib\n",
                            repl_cmd=[sys.executable, FAKE], **kw)


@pytest.fixture
def v(tmp_path):
    with make(tmp_path) as verifier:
        yield verifier


def test_acepta_prueba_valida(v):
    assert v(OK) == (True, "")


def test_rechaza_sorry(v):
    ok, trace = v("theorem t3 (a b : ℕ) : a + b = b + a := by sorry")
    assert not ok and "sorry" in trace


def test_rechaza_error_de_lean(v):
    ok, trace = v("theorem t4 (a b : ℕ) : a + b = b + a := by exact zzz")
    assert not ok and "unknown identifier" in trace


def test_rechaza_axioma_no_estandar(v):
    ok, trace = v("axiom ax : False\ntheorem t5 : 1 = 2 := ax.elim")
    assert not ok and "non-standard axioms" in trace


def test_sin_teorema(v):
    ok, trace = v("-- nada")
    assert not ok and "no theorem" in trace


def test_enunciado_distinto_al_del_dataset(v):
    ok, trace = v(OK, expected_statement="theorem t1 (a b : ℕ) : a * b = b * a")
    assert not ok and "misformalization" in trace
    assert v(OK, expected_statement="theorem t1 (a b : ℕ) : a + b = b + a") == (True, "")


def test_reutiliza_el_proceso(v):
    for _ in range(3):
        assert v(OK)[0]
    assert v.starts == 1                      # el import se pagó una sola vez


def test_timeout_y_recuperacion(tmp_path):
    with make(tmp_path, call_timeout=1) as verifier:
        assert verifier(OK)[0]
        assert verifier("theorem t (a : ℕ) : a = a := by rfl -- SLEEP") == (False, "timeout")
        assert verifier(OK)[0]                # se reinició solo
        assert verifier.starts == 2


def test_caida_del_repl_y_recuperacion(v):
    ok, trace = v("theorem t (a : ℕ) : a = a := by rfl -- CRASH")
    assert not ok and "repl_error" in trace
    assert v(OK)[0]
    assert v.starts == 2


def test_reinicio_periodico(tmp_path):
    with make(tmp_path, restart_every=2) as verifier:
        for _ in range(5):
            assert verifier(OK)[0]
        assert verifier.starts == 3           # reinicios tras 2 y 4 llamadas


def test_fallo_de_arranque_se_propaga_como_error(tmp_path):
    from src.verifier_repl import ReplError
    v = LeanReplVerifier(str(tmp_path), header="import Mathlib\n",
                         repl_cmd=[sys.executable, "-c", "import sys; sys.exit(1)"])
    with pytest.raises(ReplError):
        v(OK)                                 # no debe devolver (False, "timeout"/"repl_error")
