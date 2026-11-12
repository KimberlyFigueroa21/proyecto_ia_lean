"""Compara corridas por problema: python3 compare_runs.py results/a.jsonl results/b.jsonl ...
Muestra ✓/✗ por problema y por archivo, más totales, llamadas y tokens."""
import json
import sys
from pathlib import Path


def load(path):
    return {r["problem_id"]: r for r in (json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines()
                                         if l.strip())}


def table(paths):
    runs = [load(p) for p in paths]
    names = [Path(p).stem.replace("pipeline_", "") for p in paths]
    ids = list(dict.fromkeys(i for r in runs for i in r))
    w = max([len(i) for i in ids] + [8])
    lines = [f"{'problema':{w}}  " + "  ".join(f"{n[:22]:22}" for n in names)]
    for i in ids:
        cells = []
        for r in runs:
            cells.append(f"{('✓' if r[i]['verified'] else '✗') if i in r else '-':22}")
        lines.append(f"{i:{w}}  " + "  ".join(cells))
    tot = [f"{sum(x['verified'] for x in r.values())}/{len(r)}" for r in runs]
    lines.append(f"{'TOTAL':{w}}  " + "  ".join(f"{t:22}" for t in tot))
    lines.append(f"{'tokens (in→out)':{w}}  " + "  ".join(
        f"{sum(x['tokens_in'] for x in r.values())}→{sum(x['tokens_out'] for x in r.values()):<14}" for r in runs))
    lines.append(f"{'llamadas':{w}}  " + "  ".join(f"{sum(x['llm_calls'] for x in r.values()):<22}" for r in runs))
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    print(table(sys.argv[1:]))
