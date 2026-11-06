"""Líneas base del experimento (Fase 3).

Línea base A: el LLM escribe la prueba en Lean de una sola vez y el kernel la verifica (sin RAG,
              sin Crítico, sin reintentos). Respuesta del sistema = veredicto del kernel.
Línea base B: el LLM razona en lenguaje natural (Chain-of-Thought) y luego traduce a Lean de una
              vez, SIN verificación dentro del sistema: la salida se da por buena (claimed_correct
              = True). La verificación posterior (`verified`) es solo MEDICIÓN: permite contar los
              falsos positivos que un sistema sin verificador entregaría.

Ambas usan el mismo enunciado fijo del dataset: el modelo solo escribe el bloque de tácticas que
va después de `:= by`; el enunciado se ensambla aquí (así no puede cambiarlo) y además se pasa como
`expected_statement` al verificador.

Los fallos de infraestructura (servidor caído, cupo del LLM, etc.) se propagan como excepciones:
nunca se convierten en un veredicto sobre la prueba.
"""
import json
import re
import time
from pathlib import Path

SYSTEM = ("You are an expert in Lean 4 and Mathlib. The environment has `import Mathlib` and "
          "`open scoped Nat Real` already loaded.")

PROMPT_A = """{system}

Prove the following theorem in Lean 4 with Mathlib.

Natural-language statement:
{nl}

Lean statement (fixed, do not change it):
```lean
{statement} := by
```

Reply with ONLY the tactic proof that goes after `:= by`, inside one ```lean code block.
Do not repeat the theorem statement. Do not use `sorry`, `admit` or new axioms."""

PROMPT_B_COT = """Solve the following math problem. Reason step by step in natural language and
give a complete, rigorous proof of the formal claim at the end. Do not write Lean code yet.

Natural-language statement:
{nl}

Formal claim to prove (Lean 4):
{statement}"""

PROMPT_B_LEAN = """{system}

Here is a natural-language proof of a theorem:

{reasoning}

Translate it into a Lean 4 (Mathlib) proof of the fixed statement below.

```lean
{statement} := by
```

Reply with ONLY the tactic proof that goes after `:= by`, inside one ```lean code block.
Do not repeat the theorem statement. Do not use `sorry`, `admit` or new axioms."""

_FENCE = re.compile(r"```(?:lean4?|Lean)?[ \t]*\n(.*?)```", re.S)


def extract_tactics(text: str) -> str:
    """Devuelve solo las tácticas (lo que va después de `:= by`). Tolera que el modelo repita el teorema."""
    blocks = _FENCE.findall(text)
    code = blocks[-1] if blocks else text
    code = "\n".join(l for l in code.splitlines() if not l.strip().startswith("import "))
    m = re.search(r":=\s*by\b[ \t]*\n?", code)
    if m and re.search(r"\b(theorem|lemma)\b", code[:m.start()]):
        code = code[m.end():]
    code = code.strip("\n")
    return code.rstrip()


def assemble(statement_lean: str, tactics: str) -> str:
    lines = tactics.splitlines()
    nonblank = [l for l in lines if l.strip()]
    if not nonblank:
        return ""
    base = min(len(l) - len(l.lstrip()) for l in nonblank)
    body = "\n".join(("  " + l[base:]) if l.strip() else "" for l in lines)
    return f"{statement_lean} := by\n{body}"


def load_problems(path="data/problems.jsonl", ids=None):
    P = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            p = json.loads(line)
            P[p["id"]] = p
    if ids is None:
        return list(P.values())
    missing = [i for i in ids if i not in P]
    if missing:
        raise KeyError(f"ids que no están en el dataset: {missing}")
    return [P[i] for i in ids]


def _verify(verifier, p, code):
    t = time.perf_counter()
    ok, trace = verifier(code, p["statement_lean"])
    return bool(ok), trace, time.perf_counter() - t


def _call(llm, logger, config, p, agent, prompt):
    t = time.perf_counter()
    r = llm.call(agent, prompt)
    dt = time.perf_counter() - t
    logger.log(kind="llm_call", config=config, problem_id=p["id"], agent=agent, attempt=1,
               tokens_in=r.tokens_in, tokens_out=r.tokens_out, latency_s=round(dt, 3))
    return r, dt


def run_a(p, llm, verifier, logger) -> dict:
    r, dt_llm = _call(llm, logger, "baseline_a", p, "generator",
                      PROMPT_A.format(system=SYSTEM, nl=p["statement_nl"], statement=p["statement_lean"]))
    code = assemble(p["statement_lean"], extract_tactics(r.text))
    if not code:
        ok, trace, dt_v = False, "formalization_failure: respuesta sin tácticas", 0.0
    else:
        ok, trace, dt_v = _verify(verifier, p, code)
    logger.log(kind="verify", config="baseline_a", problem_id=p["id"], agent="verifier", attempt=1,
               verdict=ok, trace=trace[:500], latency_s=round(dt_v, 3))
    return {"config": "baseline_a", "problem_id": p["id"], "difficulty": p["difficulty"], "area": p["area"],
            "verified": ok, "claimed_correct": ok, "trace": trace[:1000], "lean_code": code,
            "llm_calls": 1, "tokens_in": r.tokens_in, "tokens_out": r.tokens_out,
            "latency_s": round(dt_llm + dt_v, 3)}


def run_b(p, llm, verifier, logger) -> dict:
    r1, dt1 = _call(llm, logger, "baseline_b", p, "planner",
                    PROMPT_B_COT.format(nl=p["statement_nl"], statement=p["statement_lean"]))
    r2, dt2 = _call(llm, logger, "baseline_b", p, "autoformalizer",
                    PROMPT_B_LEAN.format(system=SYSTEM, reasoning=r1.text, statement=p["statement_lean"]))
    code = assemble(p["statement_lean"], extract_tactics(r2.text))
    if not code:
        ok, trace, dt_v = False, "formalization_failure: respuesta sin tácticas", 0.0
    else:
        ok, trace, dt_v = _verify(verifier, p, code)
    logger.log(kind="verify_posthoc", config="baseline_b", problem_id=p["id"], agent="verifier", attempt=1,
               verdict=ok, trace=trace[:500], latency_s=round(dt_v, 3))
    return {"config": "baseline_b", "problem_id": p["id"], "difficulty": p["difficulty"], "area": p["area"],
            "verified": ok, "claimed_correct": True, "trace": trace[:1000], "lean_code": code,
            "llm_calls": 2, "tokens_in": r1.tokens_in + r2.tokens_in, "tokens_out": r1.tokens_out + r2.tokens_out,
            "latency_s": round(dt1 + dt2, 3), "verification_is_posthoc": True}


RUNNERS = {"A": run_a, "B": run_b}
