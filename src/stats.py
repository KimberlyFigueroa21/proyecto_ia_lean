"""Análisis estadístico de los resultados de las 5 configuraciones (Fase 5).

Todo es Python estándar (sin scipy) para correr igual dentro del contenedor.
- Wilson: intervalo de confianza de una proporción (pass@1) con n pequeño.
- McNemar exacto: compara dos configuraciones sobre los MISMOS problemas (pares); solo cuentan los
  discordantes (b: A acierta y B falla; c: al revés). Bonferroni: p * nº de comparaciones.
- Bootstrap pareado: IC de la diferencia de pass@1 remuestreando problemas.
"""
import json
import math
import random
import re
from collections import Counter
from pathlib import Path

Z95 = 1.959963984540054
CONFIGS = ["baseline_a", "baseline_b", "sin_rag", "sin_critico", "completo"]
RAG_CONFIGS = {"sin_critico", "completo"}
MIN_CALLS = 3
LABELS = {"baseline_a": "Baseline A", "baseline_b": "Baseline B", "sin_rag": "Sin RAG",
          "sin_critico": "Sin Crítico", "completo": "Completo"}
# Comparaciones pareadas planeadas de antemano (familia sobre la que se corrige con Bonferroni).
COMPARISONS = [("completo", "sin_rag"), ("completo", "sin_critico"), ("completo", "baseline_a"),
               ("completo", "baseline_b"), ("sin_critico", "baseline_a")]


def wilson(k: int, n: int, z: float = Z95):
    if n == 0:
        return 0.0, 1.0
    p, d = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def bootstrap_diff(x, y, reps: int = 10000, seed: int = 0):
    """x, y: listas 0/1 emparejadas. Devuelve (diferencia media x-y, IC95 inferior, superior)."""
    n = len(x)
    if n == 0:
        return 0.0, 0.0, 0.0
    d = [a - b for a, b in zip(x, y)]
    rng = random.Random(seed)
    means = sorted(sum(d[i] for i in rng.choices(range(n), k=n)) / n for _ in range(reps))
    return sum(d) / n, means[int(0.025 * reps)], means[int(0.975 * reps) - 1]


# ---------- taxonomía de errores (heurística sobre el mensaje de Lean del último intento) ----------
ERROR_RULES = [
    ("alucinación de identificador", r"unknown (identifier|constant|namespace|declaration)"),
    ("sintaxis / formalización", r"unexpected token|unterminated|parse error|formalization_failure|expected '|expected term"),
    ("uso de sorry/admit", r"sorry|admit"),
    ("enunciado alterado", r"statement_mismatch|enunciado|statement .*(differ|mismatch|changed)"),
    ("tiempo agotado", r"timeout|heartbeat|deterministic"),
    ("tipos / instancias", r"type mismatch|failed to synthesize|typeclass|invalid field|function expected"),
    ("táctica no cierra la meta", r"linarith failed|nlinarith|omega|unsolved goals|simp made no progress|failed|ring_nf|no goals"),
]
NO_INFO = {"retries_exhausted", "critic_disabled", "budget_exhausted", ""}


def classify_error(rec: dict) -> str:
    if not rec.get("lean_code"):
        return "sin tácticas (formalización fallida)"
    reason = rec.get("failure_reason") or ""
    text = (rec.get("trace") or "") + " " + ("" if reason in NO_INFO else reason)
    if not text.strip():
        return "sin traza"
    for label, pat in ERROR_RULES:
        if re.search(pat, text, re.I):
            return label
    return "otro"


def used_lemmas(rec: dict):
    """Lemas recuperados que aparecen en la prueba final (nombre completo o corto, como palabra)."""
    code = rec.get("lean_code") or ""
    out = []
    for name in rec.get("retrieved") or []:
        for cand in {name, name.split(".")[-1]}:
            if cand and re.search(r"(?<![\w.'])" + re.escape(cand) + r"(?![\w'])", code):
                out.append(name)
                break
    return out


# ---------- carga ----------
def result_path(config: str, split: str, variant: str = "v1", rag_query: str = "lean", results_dir="results") -> Path:
    d = Path(results_dir)
    if config.startswith("baseline_"):
        return d / f"{config}_{split}.jsonl"
    return d / (f"pipeline_{config}_{split}_{variant}" + (f"_{rag_query}" if config in RAG_CONFIGS else "") + ".jsonl")


def load(path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return {r["problem_id"]: r for r in (json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip())}


# ---------- informe ----------
def _md(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _pct(k, n):
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {k / n:.2f} [{lo:.2f}, {hi:.2f}]" if n else "—"


def analyze(split="dev", results_dir="results", variant="v1", rag_query="lean", expected_ids=None):
    runs = {c: load(result_path(c, split, variant, rag_query, results_dir)) for c in CONFIGS}
    runs = {c: r for c, r in runs.items() if r}
    missing = [LABELS[c] for c in CONFIGS if c not in runs]
    ids = sorted(expected_ids) if expected_ids else sorted({i for r in runs.values() for i in r})
    out = [f"# Resultados — conjunto `{split}` (n = {len(ids)})", ""]
    if missing:
        out += [f"**Configuraciones sin resultados todavía:** {', '.join(missing)}", ""]
    if not runs:
        return "\n".join(out + ["(sin datos)"]), []
    meta = {i: r for run in runs.values() for i, r in run.items()}
    # 1. resumen
    rows = []
    for c, r in runs.items():
        v = [r[i] for i in ids if i in r]
        n, ok = len(v), sum(x["verified"] for x in v)
        claimed = sum(bool(x.get("claimed_correct", x["verified"])) for x in v)
        fp = sum(bool(x.get("claimed_correct", x["verified"])) and not x["verified"] for x in v)
        mean = lambda key: sum(x.get(key, 0) or 0 for x in v) / n if n else 0
        rows.append([LABELS[c], _pct(ok, n), claimed, fp, f"{mean('llm_calls'):.1f}",
                     f"{mean('tokens_in'):.0f} / {mean('tokens_out'):.0f}", f"{mean('latency_s'):.0f}"])
    out += ["## 1. pass@1 y costo", "",
            _md(["Configuración", "pass@1 [Wilson 95 %]", "Entregadas como correctas", "Falsos positivos",
                 "Llamadas/problema", "Tokens in / out por problema", "Latencia (s)"], rows), "",
            "Falso positivo = prueba entregada como correcta que Lean rechaza. La línea base B no verifica "
            "dentro del sistema (la verificación es solo medición), por eso allí aparecen; en las demás "
            "configuraciones el veredicto de Lean decide, así que son 0.", ""]
    # 2. por área y dificultad
    for key, title in (("area", "área"), ("difficulty", "dificultad")):
        vals = sorted({meta[i][key] for i in ids if i in meta})
        rows = []
        for val in vals:
            row = [val]
            for c, r in runs.items():
                v = [r[i] for i in ids if i in r and r[i][key] == val]
                row.append(f"{sum(x['verified'] for x in v)}/{len(v)}")
            rows.append(row)
        out += [f"## 2. pass@1 por {title}", "", _md([title] + [LABELS[c] for c in runs], rows), ""]
    # 3. comparaciones pareadas
    m = sum(1 for a, b in COMPARISONS if a in runs and b in runs)
    rows = []
    for a, b in COMPARISONS:
        if a not in runs or b not in runs:
            continue
        common = [i for i in ids if i in runs[a] and i in runs[b]]
        x = [int(runs[a][i]["verified"]) for i in common]
        y = [int(runs[b][i]["verified"]) for i in common]
        bb, cc = sum(1 for p, q in zip(x, y) if p and not q), sum(1 for p, q in zip(x, y) if q and not p)
        p = mcnemar_exact(bb, cc)
        d, lo, hi = bootstrap_diff(x, y)
        rows.append([f"{LABELS[a]} vs {LABELS[b]}", len(common), bb, cc, f"{d:+.2f} [{lo:+.2f}, {hi:+.2f}]",
                     f"{p:.3f}", f"{min(1.0, p * m):.3f}"])
    out += ["## 3. Comparaciones pareadas", "",
            _md(["Comparación", "n", "solo 1.º acierta", "solo 2.º acierta", "Δ pass@1 [bootstrap 95 %]",
                 "p (McNemar exacto)", f"p Bonferroni (×{m})"], rows), "",
            "Con n pequeño solo diferencias grandes pueden ser significativas; se reporta igualmente el tamaño "
            "de la diferencia con su intervalo.", ""]
    # 4. reintento y RAG
    rows = []
    for c in ("sin_rag", "sin_critico", "completo"):
        if c not in runs:
            continue
        v = [runs[c][i] for i in ids if i in runs[c]]
        ok = [x for x in v if x["verified"]]
        # `k` vuelve a 0 al aceptar una prueba, así que no sirve; un acierto al primer intento cuesta justo
        # MIN_CALLS llamadas (Planner, Generator, AutoFormalizer). Más llamadas = hubo reintentos o replan.
        first = sum(1 for x in ok if x.get("llm_calls", MIN_CALLS) <= MIN_CALLS)
        rescued = len(ok) - first
        replans = sum(1 for x in v if (x.get("r") or 0) >= 1)
        if c in RAG_CONFIGS:
            using = [x["problem_id"] for x in ok if used_lemmas(x)]
            rag = f"{len(using)}/{len(ok)}" + (f" ({', '.join(using)})" if using else "")
        else:
            rag = "—"
        rows.append([LABELS[c], first, rescued, replans, rag])
    out += ["## 4. Contribución del Crítico y del RAG", "",
            _md(["Configuración", "Resueltos al primer intento (3 llamadas)", "Resueltos tras reintento o replan (>3 llamadas)",
                 "Problemas con replanificación", "Pruebas verificadas que usan un lema recuperado"], rows), "",
            "El pass@1 no distingue si el RAG intervino: esta última columna cuenta las pruebas correctas cuyo "
            "texto contiene algún lema recuperado.", ""]
    # 5. taxonomía de errores
    cats = []
    errs = {}
    for c, r in runs.items():
        errs[c] = Counter(classify_error(r[i]) for i in ids if i in r and not r[i]["verified"])
        cats += [k for k in errs[c] if k not in cats]
    rows = [[k] + [errs[c].get(k, 0) for c in runs] for k in cats]
    out += ["## 5. Taxonomía de errores (intentos fallidos)", "",
            _md(["Categoría"] + [LABELS[c] for c in runs], rows) if rows else "(sin fallos)", "",
            "Clasificación heurística por el mensaje de Lean del último intento; conviene revisar a mano los casos "
            "`otro` y los ambiguos antes de citar cifras.", ""]
    # 6. matriz por problema
    matrix = [[i, meta[i]["area"], meta[i]["difficulty"]] + [
        ("1" if runs[c][i]["verified"] else "0") if i in runs[c] else "" for c in runs] for i in ids if i in meta]
    out += ["## 6. Por problema", "",
            _md(["problema", "área", "dificultad"] + [LABELS[c] for c in runs],
                [[a, b, c2] + [("✓" if x == "1" else "✗" if x == "0" else "-") for x in rest]
                 for a, b, c2, *rest in matrix]), ""]
    csv = [["problem_id", "area", "difficulty"] + list(runs)] + matrix
    return "\n".join(out), csv
