"""Orquestador LangGraph: PLAN→RETRIEVE→GENERATE→FORMALIZE→VERIFY→(ADVANCE|CRITIQUE)→DONE|FAIL.

Regla del Crítico (corrige el solapamiento k=kmax / k>=kmax de la ec. 7):
  k  = intentos fallidos del subobjetivo actual     (tope k_max)
  r  = replanificaciones usadas en el problema      (tope r_max)
  REPLAN solo si r < r_max; RETRY solo si k < k_max; si no, FAIL.
"""
import time
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

from .contracts import (Action, RunConfig, PlannerIn, PlannerOut, Lemma,
                        GeneratorIn, FormalizerIn, VerifierOut, CriticIn, CriticOut)
from .llm import LLM
from .logger import JsonlLogger


class GraphState(TypedDict, total=False):
    problem_id: str
    problem: str
    subgoals: list[str]
    i: int                 # índice del subobjetivo actual
    k: int                 # intentos fallidos en el subobjetivo actual
    r: int                 # replanificaciones usadas
    retrieved: list[dict]
    sketch: str
    lean_code: str
    verdict: bool
    trace: str
    hint: str
    action: str
    history: list[dict]
    proofs: list[str]      # pruebas Lean aceptadas por subobjetivo
    llm_calls: int
    status: str            # RUNNING | DONE | FAIL
    failure_reason: str


def build_graph(llm: LLM, retriever, verifier, cfg: RunConfig, logger: JsonlLogger,
                prompts: dict[str, str] | None = None):
    """retriever(subgoal, k) -> list[Lemma-like dict];  verifier(lean_code) -> (bool, trace)."""
    P = prompts or {}

    def _llm(agent: str, text: str):
        t0 = time.perf_counter()
        res = llm.call(agent, P.get(agent, "{x}").format(x=text))
        return res, int((time.perf_counter() - t0) * 1000)

    def _log(state, agent, decision, res=None, ms=0):
        logger.log(problem_id=state["problem_id"], config=cfg.name, agent=agent,
                   subgoal=state.get("i", 0), attempt=state.get("k", 0), decision=decision,
                   tokens_in=getattr(res, "tokens_in", 0), tokens_out=getattr(res, "tokens_out", 0),
                   latency_ms=ms)

    def plan(state: GraphState):
        if not cfg.use_planner:
            _log(state, "planner", "skipped")
            return {"subgoals": [state["problem"]], "i": 0, "k": 0, "proofs": []}
        inp = PlannerIn(problem=state["problem"])
        hint = f"\nHINT: {state['hint']}" if state.get("hint") else ""
        res, ms = _llm("planner", inp.problem + hint)
        out = PlannerOut(subgoals=[s.strip() for s in res.text.splitlines() if s.strip()])
        _log(state, "planner", f"{len(out.subgoals)} subgoals", res, ms)
        return {"subgoals": out.subgoals, "i": 0, "k": 0, "proofs": [],
                "llm_calls": state.get("llm_calls", 0) + 1}

    def retrieve(state: GraphState):
        sg = state["subgoals"][state["i"]]
        if not cfg.use_rag:
            _log(state, "retriever", "skipped")
            return {"retrieved": []}
        t0 = time.perf_counter()
        lemmas = [Lemma(**l).model_dump() for l in retriever(sg, cfg.top_k)]
        _log(state, "retriever", f"{len(lemmas)} lemmas", ms=int((time.perf_counter() - t0) * 1000))
        return {"retrieved": lemmas}

    def generate(state: GraphState):
        inp = GeneratorIn(subgoal=state["subgoals"][state["i"]],
                          lemmas=state.get("retrieved", []), hint=state.get("hint"))
        res, ms = _llm("generator", inp.model_dump_json())
        _log(state, "generator", "sketch", res, ms)
        return {"sketch": res.text, "llm_calls": state.get("llm_calls", 0) + 1}

    def formalize(state: GraphState):
        inp = FormalizerIn(sketch=state["sketch"], lemmas=state.get("retrieved", []))
        res, ms = _llm("formalizer", inp.model_dump_json())
        _log(state, "formalizer", "lean_code", res, ms)
        return {"lean_code": res.text, "llm_calls": state.get("llm_calls", 0) + 1}

    def verify(state: GraphState):
        t0 = time.perf_counter()
        ok, trace = verifier(state["lean_code"])
        out = VerifierOut(verdict=ok, trace=trace)
        _log(state, "verifier", "accepted" if ok else "rejected", ms=int((time.perf_counter() - t0) * 1000))
        hist = state.get("history", []) + [{"i": state["i"], "k": state.get("k", 0),
                                            "verdict": ok, "trace": trace[:2000]}]
        return {"verdict": out.verdict, "trace": out.trace, "history": hist}

    def advance(state: GraphState):
        return {"proofs": state.get("proofs", []) + [state["lean_code"]],
                "i": state["i"] + 1, "k": 0, "hint": ""}

    def critique(state: GraphState):
        k = state.get("k", 0) + 1
        r = state.get("r", 0)
        calls = state.get("llm_calls", 0)
        if not cfg.use_critic:                       # ablación: un intento, sin análisis
            _log(state, "critic", "FAIL (critic off)")
            return {"action": Action.FAIL.value, "k": k, "failure_reason": "critic_disabled"}
        if calls >= cfg.max_llm_calls:
            _log(state, "critic", "FAIL (budget)")
            return {"action": Action.FAIL.value, "k": k, "failure_reason": "llm_budget"}
        res, ms = _llm("critic", CriticIn(trace=state["trace"], history=state["history"]).model_dump_json())
        proposed = CriticOut.model_validate_json(res.text)
        if proposed.action == Action.REPLAN and r < cfg.r_max:
            action, upd = Action.REPLAN, {"r": r + 1, "k": 0}
        elif proposed.action in (Action.RETRY, Action.REPLAN) and k < cfg.k_max:
            action, upd = Action.RETRY, {"k": k}
        else:
            action, upd = Action.FAIL, {"k": k, "failure_reason": "retries_exhausted"}
        _log(state, "critic", action.value, res, ms)
        return {**upd, "action": action.value, "hint": proposed.hint, "llm_calls": calls + 1}

    def done(state: GraphState):
        _log(state, "orchestrator", "DONE")
        return {"status": "DONE"}

    def fail(state: GraphState):
        _log(state, "orchestrator", f"FAIL:{state.get('failure_reason', '')}")
        return {"status": "FAIL"}

    after_verify = lambda s: "advance" if s["verdict"] else "critique"
    after_advance = lambda s: "retrieve" if s["i"] < len(s["subgoals"]) else "done"
    after_critic = lambda s: {"RETRY": "generate", "REPLAN": "plan", "FAIL": "fail"}[s["action"]]

    g = StateGraph(GraphState)
    for name, fn in [("plan", plan), ("retrieve", retrieve), ("generate", generate),
                     ("formalize", formalize), ("verify", verify), ("advance", advance),
                     ("critique", critique), ("done", done), ("fail", fail)]:
        g.add_node(name, fn)
    g.add_edge(START, "plan")
    g.add_edge("plan", "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", "formalize")
    g.add_edge("formalize", "verify")
    g.add_conditional_edges("verify", after_verify, {"advance": "advance", "critique": "critique"})
    g.add_conditional_edges("advance", after_advance, {"retrieve": "retrieve", "done": "done"})
    g.add_conditional_edges("critique", after_critic, {"generate": "generate", "plan": "plan", "fail": "fail"})
    g.add_edge("done", END)
    g.add_edge("fail", END)
    return g.compile()


def run_problem(graph, problem_id: str, problem: str) -> GraphState:
    return graph.invoke({"problem_id": problem_id, "problem": problem, "history": [],
                         "llm_calls": 0, "status": "RUNNING", "r": 0, "k": 0, "i": 0},
                        config={"recursion_limit": 200})
