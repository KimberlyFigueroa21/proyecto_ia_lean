"""Ejecuta el grafo multiagente sobre un problema del dataset y devuelve un registro comparable
con el de las líneas base (mismos campos: verified, tokens, llm_calls, latency_s...)."""
import time

from .contracts import RunConfig
from .graph import build_graph, run_problem
from .llm import LLMResult
from .prompts import PROMPTS

# Configuraciones de ablación (el grafo no cambia de forma; solo se apagan piezas).
PRESETS = {
    "sin_rag_ni_critico": RunConfig(name="sin_rag_ni_critico", use_rag=False, use_critic=False),  # hito sem. 2
    "sin_rag": RunConfig(name="sin_rag", use_rag=False),
    "sin_critico": RunConfig(name="sin_critico", use_critic=False),
    "completo": RunConfig(name="completo"),
}


class UsageMeter:
    """Envuelve un LLM y suma llamadas, tokens y tiempo de un problema."""
    def __init__(self, llm):
        self.llm, self.calls, self.tokens_in, self.tokens_out, self.seconds = llm, 0, 0, 0, 0.0

    def call(self, agent: str, prompt: str) -> LLMResult:
        t = time.perf_counter()
        r = self.llm.call(agent, prompt)
        self.seconds += time.perf_counter() - t
        self.calls += 1
        self.tokens_in += r.tokens_in
        self.tokens_out += r.tokens_out
        return r


def problem_text(p: dict) -> str:
    return (f"Problem (natural language):\n{p['statement_nl']}\n\n"
            f"Lean statement:\n{p['statement_lean']}")


def run_pipeline_problem(p: dict, llm, verifier, cfg: RunConfig, logger, retriever=None,
                         prompts=None, model: str = "") -> dict:
    meter = UsageMeter(llm)
    graph = build_graph(meter, retriever or (lambda sg, k: []), verifier, cfg, logger, prompts or PROMPTS)
    t = time.perf_counter()
    s = run_problem(graph, p["id"], problem_text(p), statement_lean=p["statement_lean"])
    wall = time.perf_counter() - t
    ok = s.get("status") == "DONE"
    hist = s.get("history", [])
    return {"config": cfg.name, "model": model, "problem_id": p["id"], "difficulty": p["difficulty"],
            "area": p["area"], "verified": ok, "claimed_correct": ok, "status": s.get("status"),
            "failure_reason": s.get("failure_reason", ""), "trace": (hist[-1]["trace"] if hist else "")[:1000],
            "lean_code": s.get("lean_code", ""), "subgoals": s.get("subgoals", []),
            "llm_calls": meter.calls, "tokens_in": meter.tokens_in, "tokens_out": meter.tokens_out,
            "latency_s": round(wall, 3), "r": s.get("r", 0), "k": s.get("k", 0)}
