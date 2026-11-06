import json
from pathlib import Path

from src.baselines import assemble, extract_tactics, load_problems, run_a, run_b
from src.llm import LLMResult

P = {"id": "t1", "difficulty": "basico", "area": "algebra", "statement_nl": "x", "statement_lean":
     "theorem t1 (a b : ℕ) : a + b = b + a"}


class L:
    def __init__(self, *texts): self.t = list(texts); self.prompts = []
    def call(self, agent, prompt):
        self.prompts.append(prompt)
        return LLMResult(self.t.pop(0), 10, 5)


class Log:
    def __init__(self): self.rows = []
    def log(self, **f): self.rows.append(f)


def test_extract_solo_tacticas_y_teorema_repetido():
    assert extract_tactics("Aquí:\n```lean\nomega\n```") == "omega"
    full = "```lean4\ntheorem t1 (a b : ℕ) : a + b = b + a := by\n  omega\n```"
    assert extract_tactics(full) == "  omega"
    assert extract_tactics("simp") == "simp"
    assert extract_tactics("```lean\nimport Mathlib\nomega\n```") == "omega"
    assert extract_tactics("```lean\nfoo\n```\ntexto\n```lean\nbar\n```") == "bar"


def test_assemble_normaliza_sangria():
    code = assemble(P["statement_lean"], "    nlinarith [sq_nonneg a]\n      <;> linarith")
    assert code == P["statement_lean"] + " := by\n  nlinarith [sq_nonneg a]\n    <;> linarith"
    assert assemble("theorem x : True", "  \n") == ""


def test_run_a_veredicto_del_verificador():
    seen = {}
    def ver(code, exp): seen.update(code=code, exp=exp); return True, ""
    r = run_a(P, L("```lean\nomega\n```"), ver, Log())
    assert r["verified"] and r["claimed_correct"] and r["llm_calls"] == 1
    assert seen["exp"] == P["statement_lean"] and seen["code"].endswith(":= by\n  omega")


def test_run_a_respuesta_sin_tacticas_no_llama_al_verificador():
    def ver(*_): raise AssertionError("no debía llamarse")
    r = run_a(P, L("```lean\n\n```"), ver, Log())
    assert not r["verified"] and "formalization_failure" in r["trace"]


def test_run_b_da_por_buena_la_salida_y_mide_despues():
    lg = Log()
    llm = L("razonamiento largo", "```lean\nsimp\n```")
    r = run_b(P, llm, lambda c, e: (False, "error: unsolved goals"), lg)
    assert r["claimed_correct"] is True and r["verified"] is False and r["verification_is_posthoc"]
    assert r["llm_calls"] == 2 and r["tokens_in"] == 20 and r["tokens_out"] == 10
    assert "razonamiento largo" in llm.prompts[1]
    assert [x["kind"] for x in lg.rows] == ["llm_call", "llm_call", "verify_posthoc"]


def test_la_excepcion_de_infraestructura_se_propaga():
    def ver(*_): raise RuntimeError("servidor caído")
    try:
        run_a(P, L("omega"), ver, Log())
    except RuntimeError:
        return
    raise AssertionError("debía propagarse")


def test_pilotos_existen_en_el_dataset():
    ids = json.loads(Path("data/pilot_ids.json").read_text())
    ps = load_problems(ids=ids)
    assert [p["id"] for p in ps] == ids and len(ids) == 5
