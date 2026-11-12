#!/usr/bin/env python3
"""Construye la matriz V (M×d) normalizada: w_j = e(firma ‖ docstring)  (ec. 13-14 del documento).

Uso: python build_index.py decls.jsonl indice/ --model BAAI/bge-small-en-v1.5 [--mathlib-rev <commit>]
     python build_index.py decls.jsonl indice/ --fake      # para pruebas sin descargar modelos
Guarda: vectors.npy, meta.jsonl, index_info.json (versiones, para reproducibilidad: RNF-2).
"""
import argparse, hashlib, json, time
from pathlib import Path
import numpy as np


def fake_embed(texts, d=64):
    out = np.zeros((len(texts), d), dtype=np.float32)
    for i, t in enumerate(texts):
        for tok in t.lower().split():
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            out[i, h % d] += 1.0
    return out


def get_embedder(model_name: str | None, fake: bool):
    if fake:
        return fake_embed
    from sentence_transformers import SentenceTransformer   # pip install sentence-transformers
    m = SentenceTransformer(model_name)
    return lambda texts: m.encode(texts, batch_size=64, show_progress_bar=True, convert_to_numpy=True)


def normalize(v):
    return (v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)).astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("decls"); ap.add_argument("outdir")
    ap.add_argument("--model", default="BAAI/bge-small-en-v1.5")
    ap.add_argument("--fake", action="store_true")
    ap.add_argument("--mathlib-rev", default="unknown")
    a = ap.parse_args()
    recs = [json.loads(l) for l in open(a.decls, encoding="utf-8")]
    texts = [f"{r['signature']} ‖ {r['docstring']}" for r in recs]
    V = normalize(np.asarray(get_embedder(a.model, a.fake)(texts), dtype=np.float32))
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    np.save(out / "vectors.npy", V)
    with open(out / "meta.jsonl", "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps({"name": r["name"], "signature": r["signature"]}, ensure_ascii=False) + "\n")
    json.dump({"model": "fake-hash" if a.fake else a.model, "count": len(recs), "dim": int(V.shape[1]),
               "mathlib_rev": a.mathlib_rev, "built": time.strftime("%Y-%m-%d")},
              open(out / "index_info.json", "w"), indent=2)
    print(f"V = {V.shape} guardada en {out}")


if __name__ == "__main__":
    main()
