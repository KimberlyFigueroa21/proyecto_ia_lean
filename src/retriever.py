"""Recuperador RAG sobre el índice de Mathlib: s = V·q  (ec. 16) y R_k = Top-k(s)  (ec. 17-18).

    r = Retriever("rag_data/idx2")
    r("a quotient equals a fraction iff cross multiplication", k=5)   # -> [{name, signature, score}, ...]

El índice (vectors.npy, meta.jsonl, index_info.json) lo construye rag/build_index.py con el MISMO commit
de Mathlib que usa el verificador. `embed` se puede inyectar (pruebas sin descargar el modelo).
"""
import json
from pathlib import Path

import numpy as np


def _normalize(v: np.ndarray) -> np.ndarray:
    return (v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)).astype(np.float32)


class Retriever:
    def __init__(self, index_dir: str, embed=None, model: str | None = None, max_seq_length: int = 256):
        d = Path(index_dir)
        self.V = np.load(d / "vectors.npy")
        self.meta = [json.loads(l) for l in open(d / "meta.jsonl", encoding="utf-8")]
        self.info = json.load(open(d / "index_info.json"))
        if len(self.meta) != len(self.V):
            raise ValueError(f"índice inconsistente: {len(self.V)} vectores y {len(self.meta)} lemas")
        if embed is None:
            from sentence_transformers import SentenceTransformer        # pip install sentence-transformers
            m = SentenceTransformer(model or self.info["model"])
            m.max_seq_length = max_seq_length                            # igual que al construir el índice
            embed = lambda texts: m.encode(texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True)
        self._embed = embed

    def __call__(self, query: str, k: int = 5) -> list[dict]:
        q = _normalize(np.asarray(self._embed([query]), dtype=np.float32))[0]
        s = self.V @ q
        k = min(k, len(s))
        top = np.argpartition(-s, k - 1)[:k]
        top = top[np.argsort(-s[top])]
        return [{**self.meta[i], "score": float(s[i])} for i in top]


def retrieve_many(retriever, queries: list[str], k: int) -> list[dict]:
    """Une los resultados de varias consultas (p. ej. los pasos del plan) por turnos: primero el mejor de
    cada consulta, luego el segundo..., sin repetir lemas. Así cada paso aporta y ninguno monopoliza los k."""
    queries = [q for q in queries if q and q.strip()]
    per_query = [retriever(q, k) for q in queries]
    out, seen = [], set()
    for rank in range(k):
        for res in per_query:
            if rank < len(res) and res[rank]["name"] not in seen:
                seen.add(res[rank]["name"])
                out.append(res[rank])
                if len(out) == k:
                    return out
    return out
