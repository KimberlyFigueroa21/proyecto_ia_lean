"""Piezas de los agentes que NO dependen del grafo: parseo tolerante de la salida del LLM y
construcción de los textos de entrada en 'modo teorema completo'.

Modo teorema completo: el Planner propone pasos de estrategia; el Generator los convierte en una
estrategia detallada; el AutoFormalizer escribe las tácticas; el Verifier comprueba el teorema
COMPLETO con el enunciado del dataset fijo (así no puede alterarse). Los pasos del Planner guían,
no se verifican por separado."""
import json
import re

from .baselines import assemble, extract_tactics

MAX_STEPS = 6
_MARK = re.compile(r"^\s*(?:[-*•]+\s+|\d+\s*[.)]\s*|step\s*\d+\s*[:.)]?\s*)", re.I)


def parse_subgoals(text: str, max_steps: int = MAX_STEPS) -> list[str]:
    """Una línea = un paso. Quita viñetas, numeración, negritas y líneas de encabezado/código."""
    steps, in_code = [], False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not line:
            continue
        line = _MARK.sub("", line).strip().strip("*_ ").strip()
        if not line or line.endswith(":"):
            continue
        steps.append(line)
    return steps[:max_steps]


def format_plan(subgoals: list[str]) -> str:
    return "\n".join(f"{i}. {s}" for i, s in enumerate(subgoals, 1))


def format_lemmas(lemmas: list[dict]) -> str:
    if not lemmas:
        return ""
    return "Useful Mathlib lemmas:\n" + "\n".join(f"- {l['name']} : {l.get('signature', '')}" for l in lemmas)


def _blocks(*parts: str) -> str:
    return "\n\n".join(p for p in parts if p)


def build_generator_text(state: dict) -> str:
    hint = state.get("hint") or ""
    return _blocks(state["problem"],
                   "Proof plan:\n" + format_plan(state["subgoals"]),
                   format_lemmas(state.get("retrieved", [])),
                   ("Feedback on the previous failed attempt:\n" + hint) if hint else "")


def build_formalizer_text(state: dict) -> str:
    prev = ""
    if state.get("k", 0) > 0 and state.get("lean_code"):          # reintento: ver lo que falló y por qué
        prev = ("Previous attempt (it FAILED, do not repeat it):\n" + state["lean_code"] +
                "\nLean error:\n" + (state.get("trace") or "")[:1500])
    return _blocks(state["problem"],
                   "Proof strategy:\n" + state["sketch"],
                   format_lemmas(state.get("retrieved", [])),
                   prev,
                   "Lean statement (fixed):\n" + state["statement_lean"] + " := by")


def assemble_code(statement_lean: str, llm_text: str) -> str:
    """Enunciado fijo del dataset + las tácticas que escribió el modelo. '' si no hay tácticas."""
    return assemble(statement_lean, extract_tactics(llm_text))


# ---------- Crítico ----------
_ACTION = re.compile(r"\b(RETRY|REPLAN|FAIL)\b", re.I)
_HINT = re.compile(r"hint\s*[:=]\s*(.+)", re.I | re.S)
MAX_HINT = 1200


def parse_critic(text: str) -> tuple[str, str]:
    """Salida tolerante del Crítico -> (acción, pista). Acepta JSON {"action","hint"} o texto
    `ACTION: RETRY` + `HINT: ...`. Si no entiende la acción, RETRY (la opción menos destructiva)."""
    t = text.strip()
    m = re.search(r"\{.*\}", t, re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            a = str(d.get("action", "")).upper()
            if a in ("RETRY", "REPLAN", "FAIL"):
                return a, str(d.get("hint", ""))[:MAX_HINT].strip()
        except ValueError:
            pass
    head = t.split("HINT", 1)[0] if re.search(r"hint", t, re.I) else t
    am = re.search(r"action\s*[:=]\s*\W*(RETRY|REPLAN|FAIL)", head, re.I) or _ACTION.search(head)
    action = am.group(1).upper() if am else "RETRY"
    hm = _HINT.search(t)
    return action, (hm.group(1).strip() if hm else "")[:MAX_HINT]


def build_critic_text(state: dict) -> str:
    """Entrada del Crítico en modo teorema completo: enunciado, código que falló y error de Lean."""
    return _blocks(state["problem"],
                   "Failed Lean proof (attempt %d):\n%s" % (state.get("k", 0) + 1, state.get("lean_code") or "(empty)"),
                   "Lean error:\n" + (state.get("trace") or "")[:1500],
                   "Plan used:\n" + format_plan(state.get("subgoals", [])))
