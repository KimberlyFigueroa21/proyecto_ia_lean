"""Evalúa el recuperador sobre los problemas de DESARROLLO: ¿aparece algún lema útil entre los k primeros?

Para cada problema hay una lista de lemas aceptables (data/rag_queries_dev.jsonl; elegidos a mano mirando
qué usaría una prueba humana y comprobados contra el índice). Un acierto = alguno de ellos en los k
recuperados. Se comparan las formas de construir la consulta con las MISMAS condiciones que usa el
pipeline (los pasos del plan salen de results/pipeline_sin_rag_dev_v1.jsonl, campo `subgoals`):

    problem    texto completo del problema (lo que se hacía antes)
    plan       un paso del plan = una consulta corta, unidas por turnos
    lean       solo el enunciado en Lean
    plan+lean  enunciado Lean + pasos del plan

    python3 rag/eval_rag.py rag_data/idx2

Limitación para el informe: los lemas esperados son un juicio del autor (no se extraen de pruebas de
referencia), y son solo 10 problemas; sirve para elegir entre variantes, no para estimar un rendimiento.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.agents import build_rag_queries                    # noqa: E402
from src.baselines import load_split                        # noqa: E402
from src.pipeline import problem_text                       # noqa: E402
from src.retriever import Retriever, retrieve_many          # noqa: E402

MODES = ("problem", "plan", "lean", "plan+lean")


def main(idx, qpath="data/rag_queries_dev.jsonl", plans="results/pipeline_sin_rag_dev_v1.jsonl", ks=(5, 10)):
    R = Retriever(idx)
    exist = {m["name"] for m in R.meta}
    probs = {p["id"]: p for p in load_split("dev")}
    steps = {}
    for l in open(plans, encoding="utf-8"):
        r = json.loads(l)
        steps[r["problem_id"]] = r["subgoals"]
    items = [json.loads(l) for l in open(qpath, encoding="utf-8")]
    missing = sorted({e for it in items for e in it["expected"] if e not in exist})
    print(f"índice: {R.info['count']} lemas, {R.info['model']}  |  esperados que no existen en el índice: {missing or 'ninguno'}\n")
    table = {m: {k: [] for k in ks} for m in MODES}
    print(f"{'problema':26s}" + "".join(f"{m:>12s}" for m in MODES) + "   (rango del primer acierto, k=10)")
    for it in items:
        pid, exp = it["problem_id"], set(it["expected"]) & exist
        p = probs[pid]
        state = {"problem": problem_text(p), "statement_lean": p["statement_lean"], "subgoals": steps.get(pid, [])}
        row = f"{pid:26s}"
        for m in MODES:
            names = [r["name"] for r in retrieve_many(R, build_rag_queries(state, m), max(ks))]
            ranks = [names.index(e) + 1 for e in exp if e in names]
            for k in ks:
                table[m][k].append(bool(ranks and min(ranks) <= k))
            row += f"{(str(min(ranks)) if ranks else '—'):>12s}"
        print(row)
    n = len(items)
    print()
    for k in ks:
        print(f"recall@{k:<3d}" + "".join(f"{m}={sum(table[m][k]) / n:.2f}  " for m in MODES))


if __name__ == "__main__":
    main(*sys.argv[1:2])
