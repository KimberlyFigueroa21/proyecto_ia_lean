#!/usr/bin/env python3
"""Estadística del protocolo de ablación (guía §8.4).

Entrada: CSV con columnas  problem_id,config,solved,llm_calls,tokens,wall_s
         (una fila por problema y configuración; solved = 0/1 según el kernel de Lean).
Salida : tabla pass@1 con IC de Wilson, McNemar pareado exacto con Bonferroni,
         y costo (mediana, IQR, IC bootstrap de la media) sobre problemas resueltos.

Uso: python stats.py resultados.csv [--baseline baseline_A] [--alpha 0.05] [--seed 0]
"""
import argparse, csv, itertools, math
from collections import defaultdict
import numpy as np
from scipy.stats import binomtest


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (float("nan"),) * 2
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def mcnemar_exact(a: list[int], b: list[int]):
    """a,b: resultados 0/1 pareados. Devuelve (b01, b10, p) con prueba binomial exacta."""
    b01 = sum(1 for x, y in zip(a, b) if x == 0 and y == 1)   # solo B resuelve
    b10 = sum(1 for x, y in zip(a, b) if x == 1 and y == 0)   # solo A resuelve
    n = b01 + b10
    p = 1.0 if n == 0 else binomtest(min(b01, b10), n, 0.5).pvalue
    return b01, b10, p


def boot_ci_mean(x, reps=1000, seed=0, alpha=0.05):
    x = np.asarray(x, float)
    if len(x) == 0:
        return (float("nan"),) * 2
    rng = np.random.default_rng(seed)
    means = rng.choice(x, size=(reps, len(x)), replace=True).mean(axis=1)
    return tuple(np.quantile(means, [alpha / 2, 1 - alpha / 2]))


def load(path):
    data = defaultdict(dict)          # config -> problem_id -> row
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            data[r["config"]][r["problem_id"]] = {
                "solved": int(r["solved"]), "llm_calls": float(r.get("llm_calls") or 0),
                "tokens": float(r.get("tokens") or 0), "wall_s": float(r.get("wall_s") or 0)}
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    data = load(a.csv)
    configs = list(data)

    print("== pass@1 (Wilson 95%) ==")
    for c in configs:
        ids = data[c]; k = sum(v["solved"] for v in ids.values()); n = len(ids)
        lo, hi = wilson(k, n)
        print(f"{c:<20} {k}/{n} = {k/n:.3f}  [{lo:.3f}, {hi:.3f}]")

    pairs = list(itertools.combinations(configs, 2))
    alpha_adj = a.alpha / max(1, len(pairs))
    print(f"\n== McNemar exacto pareado (Bonferroni: alpha={a.alpha} / {len(pairs)} = {alpha_adj:.4f}) ==")
    for c1, c2 in pairs:
        common = sorted(set(data[c1]) & set(data[c2]))
        x = [data[c1][i]["solved"] for i in common]; y = [data[c2][i]["solved"] for i in common]
        only2, only1, p = mcnemar_exact(x, y)
        sig = "*" if p < alpha_adj else ""
        print(f"{c1} vs {c2}: solo {c1}={only1}, solo {c2}={only2}, n={len(common)}, p={p:.4f} {sig}")

    print("\n== Costo por problema RESUELTO (mediana [IQR]; media IC bootstrap 1000) ==")
    for c in configs:
        solved = [v for v in data[c].values() if v["solved"]]
        for m in ("llm_calls", "tokens", "wall_s"):
            x = np.array([v[m] for v in solved])
            if len(x) == 0:
                print(f"{c:<20} {m:<10} sin problemas resueltos"); continue
            q1, med, q3 = np.quantile(x, [.25, .5, .75])
            lo, hi = boot_ci_mean(x, 1000, a.seed)
            print(f"{c:<20} {m:<10} {med:.1f} [{q1:.1f}, {q3:.1f}]  media IC [{lo:.1f}, {hi:.1f}]")


if __name__ == "__main__":
    main()
