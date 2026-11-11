import json

from src.agents import assemble_code, build_formalizer_text, build_generator_text, format_plan, parse_subgoals
from src.contracts import RunConfig
from src.llm import MockLLM
from src.logger import JsonlLogger
from src.pipeline import PRESETS, problem_text, run_pipeline_problem
from src.prompts import PROMPTS

P = {"id": "t1", "difficulty": "basico", "area": "algebra", "statement_nl": "Show a+b=b+a.",
     "statement_lean": "theorem t1 (a b : ℕ) : a + b = b + a"}
PLAN = "1. Reduce to commutativity.\n2. Close with omega."
GOOD = "```lean\nomega\n```"


def run(tmp_path, script, verifier, cfg=None, **kw):
    llm = MockLLM(script)
    log = JsonlLogger(tmp_path / "log.jsonl")
    rec = run_pipeline_problem(P, llm, verifier, cfg or PRESETS["sin_rag_ni_critico"], log, **kw)
    return rec, llm, [json.loads(l) for l in (tmp_path / "log.jsonl").read_text().splitlines()]


# ---------- parseo ----------
def test_parse_subgoals_variantes():
    assert parse_subgoals("sub1\nsub2") == ["sub1", "sub2"]
    assert parse_subgoals("Here is the plan:\n1. **Isolate x**\n- Substitute\n2) Simplify\n") == \
        ["Isolate x", "Substitute", "Simplify"]
    assert parse_subgoals("```\ncode\n```\nStep 1: do it") == ["do it"]
    assert parse_subgoals("\n\n") == []
    assert len(parse_subgoals("\n".join(f"paso {i}" for i in range(20)))) == 6
    assert format_plan(["a", "b"]) == "1. a\n2. b"


def test_assemble_code():
    assert assemble_code(P["statement_lean"], GOOD) == P["statement_lean"] + " := by\n  omega"
    assert assemble_code(P["statement_lean"], "```lean\n\n```") == ""


def test_prompts_solo_usan_x():
    for name, tpl in PROMPTS.items():
        assert tpl.format(x="Z").count("Z") == 1, name


# ---------- grafo en modo teorema completo ----------
def test_e2e_sin_rag_ni_critico_acierta(tmp_path):
    seen = {}
    def ver(code, expected=None):
        seen.update(code=code, expected=expected)
        return True, ""
    rec, llm, rows = run(tmp_path, {"planner": [PLAN], "generator": ["use omega"], "formalizer": [GOOD]}, ver,
                         model="m-test")
    assert rec["verified"] and rec["status"] == "DONE" and rec["llm_calls"] == 3 and rec["model"] == "m-test"
    assert seen["expected"] == P["statement_lean"] and seen["code"].endswith(":= by\n  omega")
    assert rec["subgoals"] == ["Reduce to commutativity.", "Close with omega."]
    assert [a for a, _ in llm.calls] == ["planner", "generator", "formalizer"]      # sin Crítico ni Retriever
    assert [r["agent"] for r in rows if r["agent"] != "orchestrator"] == \
        ["planner", "retriever", "generator", "formalizer", "verifier"]
    assert all({"tokens_in", "tokens_out", "latency_ms", "problem_id"} <= r.keys() for r in rows)


def test_los_textos_de_entrada_llevan_enunciado_plan_y_lemas(tmp_path):
    rec, llm, _ = run(tmp_path, {"planner": [PLAN], "generator": ["use omega"], "formalizer": [GOOD]},
                      lambda c, e=None: (True, ""))
    planner_in, generator_in, formalizer_in = (p for _, p in llm.calls)
    assert P["statement_lean"] in planner_in and "Show a+b=b+a." in planner_in
    assert "Proof plan:\n1. Reduce to commutativity." in generator_in
    assert "use omega" in formalizer_in and P["statement_lean"] + " := by" in formalizer_in
    st = {"problem": problem_text(P), "subgoals": ["s"], "statement_lean": P["statement_lean"], "sketch": "x",
          "retrieved": [{"name": "Nat.add_comm", "signature": "a + b = b + a"}], "hint": "try simp"}
    assert "Nat.add_comm : a + b = b + a" in build_generator_text(st)
    assert "Feedback on the previous failed attempt:\ntry simp" in build_generator_text(st)
    assert "Nat.add_comm" in build_formalizer_text(st)


def test_rechazo_del_kernel_es_fallo_sin_critico(tmp_path):
    rec, _, _ = run(tmp_path, {"planner": [PLAN], "generator": ["g"], "formalizer": [GOOD]},
                    lambda c, e=None: (False, "error: unsolved goals"))
    assert not rec["verified"] and rec["status"] == "FAIL" and rec["failure_reason"] == "critic_disabled"
    assert "unsolved goals" in rec["trace"] and rec["llm_calls"] == 3


def test_sin_tacticas_no_llama_al_verificador(tmp_path):
    def ver(*_):
        raise AssertionError("no debía llamarse")
    rec, _, _ = run(tmp_path, {"planner": [PLAN], "generator": ["g"], "formalizer": ["no code here ```lean\n\n```"]}, ver)
    assert not rec["verified"] and "formalization_failure" in rec["trace"]


def test_planner_inservible_cae_a_un_solo_paso(tmp_path):
    rec, _, rows = run(tmp_path, {"planner": ["```\n\n```"], "generator": ["g"], "formalizer": [GOOD]},
                       lambda c, e=None: (True, ""))
    assert rec["verified"] and len(rec["subgoals"]) == 1
    assert any(r["agent"] == "planner" and r["decision"] == "fallback" for r in rows)


def test_sin_planner_usa_el_problema_como_unico_paso(tmp_path):
    cfg = RunConfig(name="x", use_planner=False, use_rag=False, use_critic=False)
    rec, llm, _ = run(tmp_path, {"generator": ["g"], "formalizer": [GOOD]}, lambda c, e=None: (True, ""), cfg=cfg)
    assert rec["verified"] and rec["llm_calls"] == 2 and "planner" not in [a for a, _ in llm.calls]


def test_con_rag_los_lemas_llegan_al_generator(tmp_path):
    from src.pipeline import run_pipeline_problem as rp
    llm = MockLLM({"planner": [PLAN], "generator": ["g"], "formalizer": [GOOD]})
    lemmas = lambda q, k: [{"name": "Nat.add_comm", "signature": "a + b = b + a", "score": 0.9}][:k]
    rec = rp(P, llm, lambda c, e=None: (True, ""), RunConfig(name="r", use_critic=False),
             JsonlLogger(tmp_path / "l.jsonl"), retriever=lemmas)
    assert rec["verified"] and "Nat.add_comm : a + b = b + a" in llm.calls[1][1]


def test_excepcion_de_infraestructura_se_propaga(tmp_path):
    def ver(*_):
        raise RuntimeError("servidor caído")
    try:
        run(tmp_path, {"planner": [PLAN], "generator": ["g"], "formalizer": [GOOD]}, ver)
    except RuntimeError:
        return
    raise AssertionError("debía propagarse")
