#!/usr/bin/env python3
"""Recuperador Top-k:  s = V·q  (ec. 16) y  R_k = Top-k(s)  (ec. 17-18).
Compatible con el nodo RETRIEVE del grafo: Retriever(...)(subgoal, k) -> list[dict].

Evaluación del RAG antes de integrarlo (guía §11):
  python retrieve.py indice/ consultas.jsonl --k 5 [--fake]
  consultas.jsonl: {"query": "...", "expected": ["Nat.add_comm", ...]} por línea.
"""
import argparse, json
from pathlib import Path
import numpy as np
from build_index import get_embedder, normalize


class Retriever:
    def __init__(self, index_dir, model=None, fake=False):
        d = Path(index_dir)
        self.V = np.load(d / "vectors.npy")
        self.meta = [json.loads(l) for l in open(d / "meta.jsonl", encoding="utf-8")]
        info = json.load(open(d / "index_info.json"))
        self.embed = get_embedder(model or info["model"], fake or info["model"] == "fake-hash")

    def __call__(self, subgoal: str, k: int = 5):
        q = normalize(np.asarray(self.embed([subgoal]), dtype=np.float32))[0]
        s = self.V @ q
        k = min(k, len(s))
        top = np.argpartition(-s, k - 1)[:k]
        top = top[np.argsort(-s[top])]
        return [{**self.meta[i], "score": float(s[i])} for i in top]


def evaluate(retriever, queries, k=5):
    hits, rr = 0, 0.0
    for q in queries:
        names = [r["name"] for r in retriever(q["query"], k)]
        pos = [names.index(e) for e in q["expected"] if e in names]
        hits += bool(pos)
        rr += 1 / (1 + min(pos)) if pos else 0.0
    n = len(queries)
    return {f"recall@{k}": hits / n, "MRR": rr / n, "n": n}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("index_dir"); ap.add_argument("queries")
    ap.add_argument("--k", type=int, default=5); ap.add_argument("--fake", action="store_true")
    a = ap.parse_args()
    qs = [json.loads(l) for l in open(a.queries, encoding="utf-8")]
    print(evaluate(Retriever(a.index_dir, fake=a.fake), qs, a.k))
