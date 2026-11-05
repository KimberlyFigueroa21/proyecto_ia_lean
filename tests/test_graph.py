import json
from src.contracts import RunConfig
from src.graph import build_graph, run_problem
from src.llm import MockLLM
from src.logger import JsonlLogger

RETRY = json.dumps({"action": "RETRY", "hint": "usa nlinarith"})
REPLAN = json.dumps({"action": "REPLAN", "hint": "otra descomposición"})
LEMMAS = lambda sg, k: [{"name": "Nat.add_comm", "signature": "a + b = b + a", "score": 0.9}][:k]


def make(tmp_path, script, verdicts, **cfg):
    it = iter(verdicts)
    llm = MockLLM(script)
    log = JsonlLogger(tmp_path / "run.jsonl")
    g = build_graph(llm, LEMMAS, lambda code: next(it), RunConfig(**cfg), log)
    return g, llm, tmp_path / "run.jsonl"


BASE = {"planner": ["sub1\nsub2"], "generator": ["sketch"],
        "formalizer": ["theorem x : True := trivial"], "critic": [RETRY]}


def test_all_pass(tmp_path):
    g, llm, _ = make(tmp_path, BASE, [(True, ""), (True, "")])
    s = run_problem(g, "p1", "prob")
    assert s["status"] == "DONE" and len(s["proofs"]) == 2


def test_retry_then_pass(tmp_path):
    g, llm, log = make(tmp_path, BASE, [(False, "err"), (True, ""), (True, "")])
    s = run_problem(g, "p1", "prob")
    assert s["status"] == "DONE"
    rows = [json.loads(l) for l in log.read_text().splitlines()]
    assert any(r["agent"] == "critic" and r["decision"] == "RETRY" for r in rows)
    assert all({"problem_id", "agent", "attempt", "tokens_in", "latency_ms"} <= r.keys() for r in rows)


def test_fail_when_retries_exhausted(tmp_path):
    g, *_ = make(tmp_path, BASE, [(False, "err")] * 10, k_max=2)
    s = run_problem(g, "p1", "prob")
    assert s["status"] == "FAIL" and s["failure_reason"] == "retries_exhausted"


def test_replan_is_reachable_and_bounded(tmp_path):
    g, *_ = make(tmp_path, {**BASE, "critic": [REPLAN]}, [(False, "e")] * 10, k_max=3, r_max=1)
    s = run_problem(g, "p1", "prob")
    assert s["r"] == 1 and s["status"] == "FAIL"


def test_no_critic_means_single_attempt(tmp_path):
    g, llm, _ = make(tmp_path, BASE, [(False, "e")] * 5, use_critic=False, k_max=1)
    s = run_problem(g, "p1", "prob")
    assert s["status"] == "FAIL" and s["failure_reason"] == "critic_disabled"
    assert not any(a == "critic" for a, _ in llm.calls)


def test_no_rag_skips_retrieval(tmp_path):
    g, llm, log = make(tmp_path, BASE, [(True, ""), (True, "")], use_rag=False)
    run_problem(g, "p1", "prob")
    rows = [json.loads(l) for l in log.read_text().splitlines()]
    assert all(r["decision"] == "skipped" for r in rows if r["agent"] == "retriever")


def test_llm_budget_cap(tmp_path):
    g, *_ = make(tmp_path, BASE, [(False, "e")] * 50, k_max=50, max_llm_calls=8)
    s = run_problem(g, "p1", "prob")
    assert s["status"] == "FAIL" and s["failure_reason"] == "llm_budget"
