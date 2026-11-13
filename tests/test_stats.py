import json

import pytest

from src.stats import (analyze, bootstrap_diff, classify_error, load, mcnemar_exact, result_path,
                       used_lemmas, wilson)


def test_wilson_valores_conocidos():
    lo, hi = wilson(6, 10)
    assert lo == pytest.approx(0.3127, abs=1e-3) and hi == pytest.approx(0.8318, abs=1e-3)
    assert wilson(0, 10)[0] == 0.0 and wilson(10, 10)[1] == pytest.approx(1.0) and wilson(0, 0) == (0.0, 1.0)


def test_mcnemar_exacto():
    assert mcnemar_exact(5, 0) == pytest.approx(0.0625)
    assert mcnemar_exact(3, 3) == 1.0 and mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(1, 0) == 1.0


def test_bootstrap_diff_reproducible_y_signo():
    x, y = [1] * 8 + [0] * 2, [0] * 8 + [0] * 2
    d, lo, hi = bootstrap_diff(x, y, reps=2000)
    assert d == pytest.approx(0.8) and 0.5 <= lo <= d <= hi <= 1.0
    assert bootstrap_diff(x, y, reps=2000) == (d, lo, hi)
    assert bootstrap_diff([], []) == (0.0, 0.0, 0.0)


@pytest.mark.parametrize("rec,esperado", [
    ({"lean_code": "x", "trace": "error: Unknown constant `ZMod.foo`"}, "alucinación de identificador"),
    ({"lean_code": "x", "trace": "7:23: error: unexpected token '*'; expected ')'"}, "sintaxis / formalización"),
    ({"lean_code": "x", "trace": "declaration uses 'sorry'"}, "uso de sorry/admit"),
    ({"lean_code": "x", "trace": "error: linarith failed to find a contradiction"}, "táctica no cierra la meta"),
    ({"lean_code": "x", "trace": "type mismatch\n  h"}, "tipos / instancias"),
    ({"lean_code": "", "trace": ""}, "sin tácticas (formalización fallida)"),
    ({"lean_code": "x", "trace": "", "failure_reason": "retries_exhausted"}, "sin traza"),
    ({"lean_code": "x", "trace": "algo raro"}, "otro"),
])
def test_classify_error(rec, esperado):
    assert classify_error(rec) == esperado


def test_used_lemmas_palabras_completas():
    rec = {"retrieved": ["Nat.mul_mod", "add_comm", "Int.even_add"],
           "lean_code": "by\n  rw [mul_mod]\n  exact Nat.add_comm_foo\n  have := h.add_comm"}
    assert used_lemmas(rec) == ["Nat.mul_mod"]                 # mul_mod (corto) sí; add_comm_foo y h.add_comm no
    assert used_lemmas({"lean_code": "x"}) == []


def test_result_path():
    assert result_path("baseline_a", "dev").as_posix() == "results/baseline_a_dev.jsonl"
    assert result_path("sin_rag", "dev").as_posix() == "results/pipeline_sin_rag_dev_v1.jsonl"
    assert result_path("completo", "test", rag_query="lean").as_posix() == "results/pipeline_completo_test_v1_lean.jsonl"


def rec(pid, ok, area="algebra", dif="basico", **kw):
    return {"problem_id": pid, "area": area, "difficulty": dif, "verified": ok, "claimed_correct": ok,
            "llm_calls": 3, "tokens_in": 100, "tokens_out": 50, "latency_s": 10.0, "lean_code": "by omega",
            "trace": "" if ok else "linarith failed", **kw}


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_analyze_extremo_a_extremo(tmp_path):
    ids = [f"p{i}" for i in range(6)]
    comp = [dict(rec(i, j < 5, r=0, retrieved=["Nat.mul_mod"] if j == 4 else [],
                lean_code="by rw [mul_mod]" if j == 4 else "by omega"), llm_calls=6 if j == 4 else 3) for j, i in enumerate(ids)]
    sinrag = [rec(i, j < 3, k=0, r=0) for j, i in enumerate(ids)]
    b = [dict(rec(i, j < 2), claimed_correct=True) for j, i in enumerate(ids)]
    write(result_path("completo", "dev", results_dir=tmp_path), comp)
    write(result_path("sin_rag", "dev", results_dir=tmp_path), sinrag)
    write(result_path("baseline_b", "dev", results_dir=tmp_path), b)
    md, csv = analyze("dev", tmp_path, expected_ids=ids)
    assert "Sin Crítico" in md and "Baseline A" in md          # avisa de lo que falta
    assert "5/6 = 0.83" in md and "3/6 = 0.50" in md and "2/6 = 0.33" in md
    assert "Completo vs Sin RAG" in md and "Completo vs Baseline B" in md
    assert "Completo vs Baseline A" not in md                  # sin datos de A, no se compara
    row4 = [l for l in md.splitlines() if l.startswith("| Completo | 4 | 1 |")]
    assert row4, "4 al primer intento y 1 rescatado por reintento"
    assert "1/5 (p4)" in md                                    # un acierto usa un lema recuperado
    assert csv[0] == ["problem_id", "area", "difficulty", "baseline_b", "sin_rag", "completo"]
    fp_row = [l for l in md.splitlines() if l.startswith("| Baseline B")][0]
    assert "| 6 | 4 |" in fp_row                               # B entrega 6 como correctas, 4 son falsos positivos


def test_analyze_sin_datos(tmp_path):
    md, csv = analyze("dev", tmp_path)
    assert "sin datos" in md and csv == []


def test_espera_hasta_reinicio_del_pacifico():
    from datetime import datetime, timezone

    from run_experiment import seconds_until_pacific_reset
    # 2026-11-13 12:00 UTC = 04:00 PST (UTC-8): faltan 20 h y 5 min hasta 00:05 del día siguiente
    now = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
    assert seconds_until_pacific_reset(now) == 20 * 3600 + 5 * 60
    # justo después de medianoche del Pacífico: casi 24 h
    now2 = datetime(2026, 11, 13, 8, 10, tzinfo=timezone.utc)
    assert seconds_until_pacific_reset(now2) == 24 * 3600 - 5 * 60


def test_auto_resume_espera_y_continua(monkeypatch, tmp_path):
    import run_experiment as R
    from src.api_llm import DailyQuotaExceeded, TransientError

    llamadas, esperas = [], []

    class V:
        def wait_ready(self): pass

    def run_all(*a, **k):
        llamadas.append(1)
        if len(llamadas) == 1:
            raise DailyQuotaExceeded("tope")
        if len(llamadas) == 2:
            raise TransientError("503")
    monkeypatch.setattr(R, "RemoteVerifier", V)
    monkeypatch.setattr(R, "run_all", run_all)
    monkeypatch.setattr(R, "sleep_log", lambda s, why: esperas.append(why))
    monkeypatch.setattr("sys.argv", ["x", "--split", "dev", "--configs", "baseline_a", "--auto-resume",
                                      "--out-dir", str(tmp_path)])
    assert R.main() == 0 and len(llamadas) == 3 and len(esperas) == 2   # tope -> espera; 503 -> espera; luego termina


def test_sin_auto_resume_termina_con_codigo(monkeypatch, tmp_path):
    import run_experiment as R
    from src.api_llm import DailyQuotaExceeded

    class V:
        def wait_ready(self): pass
    monkeypatch.setattr(R, "RemoteVerifier", V)
    monkeypatch.setattr(R, "run_all", lambda *a, **k: (_ for _ in ()).throw(DailyQuotaExceeded("tope")))
    monkeypatch.setattr("sys.argv", ["x", "--split", "dev", "--configs", "baseline_a", "--out-dir", str(tmp_path)])
    assert R.main() == 3


def test_test_exige_allow_test(monkeypatch, tmp_path):
    import run_experiment as R
    monkeypatch.setattr("sys.argv", ["x", "--split", "test", "--out-dir", str(tmp_path)])
    assert R.main() == 4
