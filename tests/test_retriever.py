import hashlib
import json

import numpy as np

from src.agents import build_rag_queries, format_lemmas
from src.contracts import RunConfig
from src.graph import build_graph, run_problem
from src.llm import MockLLM
from src.logger import JsonlLogger
from src.retriever import Retriever, retrieve_many


def fake_embed(texts, d=64):
    out = np.zeros((len(texts), d), dtype=np.float32)
    for i, t in enumerate(texts):
        for tok in t.lower().split():
            out[i, int(hashlib.md5(tok.encode()).hexdigest(), 16) % d] += 1.0
    return out


LEMMAS = [("Nat.add_comm", "theorem Nat.add_comm : a + b = b + a"),
          ("Nat.mul_mod", "theorem Nat.mul_mod : a * b % n = (a % n) * (b % n) % n"),
          ("Real.sq_sqrt", "theorem Real.sq_sqrt : sqrt a ^ 2 = a"),
          ("div_eq_iff", "theorem div_eq_iff : a / b = c <-> a = c * b")]


def make_index(tmp_path):
    texts = [f"{s} ‖ " for _, s in LEMMAS]
    V = fake_embed(texts)
    V = V / np.linalg.norm(V, axis=1, keepdims=True)
    d = tmp_path / "idx"
    d.mkdir()
    np.save(d / "vectors.npy", V.astype(np.float32))
    (d / "meta.jsonl").write_text("\n".join(json.dumps({"name": n, "signature": s}) for n, s in LEMMAS), encoding="utf-8")
    (d / "index_info.json").write_text(json.dumps({"model": "fake", "count": len(LEMMAS), "dim": 64}), encoding="utf-8")
    return str(d)


def test_retriever_devuelve_lo_mas_parecido(tmp_path):
    r = Retriever(make_index(tmp_path), embed=fake_embed)
    top = r("a * b % n remainder", k=2)
    assert top[0]["name"] == "Nat.mul_mod" and len(top) == 2
    assert top[0]["score"] >= top[1]["score"] and {"name", "signature", "score"} <= set(top[0])


def test_retriever_rechaza_indice_inconsistente(tmp_path):
    d = make_index(tmp_path)
    (tmp_path / "idx" / "meta.jsonl").write_text(json.dumps({"name": "x", "signature": "y"}), encoding="utf-8")
    try:
        Retriever(d, embed=fake_embed)
        assert False
    except ValueError as e:
        assert "inconsistente" in str(e)


def test_retrieve_many_intercala_y_no_repite():
    fake = {"a": [{"name": "A1", "score": .9}, {"name": "A2", "score": .5}],
            "b": [{"name": "B1", "score": .8}, {"name": "A1", "score": .7}, {"name": "B3", "score": .1}]}
    out = retrieve_many(lambda q, k: fake[q][:k], ["a", "b", " "], 3)
    assert [r["name"] for r in out] == ["A1", "B1", "A2"]            # turnos, sin duplicados, ignora consultas vacías
    assert retrieve_many(lambda q, k: [], ["a"], 3) == []


def test_build_rag_queries_modos():
    st = {"problem": "P", "statement_lean": "theorem t : True", "subgoals": ["s1", "s2"]}
    assert build_rag_queries(st, "plan") == ["s1", "s2"]
    assert build_rag_queries(st, "lean") == ["theorem t : True"]
    assert build_rag_queries(st, "plan+lean") == ["theorem t : True", "s1", "s2"]
    assert build_rag_queries(st, "problem") == ["P"]
    assert build_rag_queries({**st, "subgoals": []}, "plan") == ["P"]


def test_format_lemmas_recorta_firmas_largas():
    txt = format_lemmas([{"name": "L", "signature": "x" * 1000}])
    assert len(txt) < 400 and txt.endswith("…")


def test_grafo_en_modo_completo_consulta_con_los_pasos_del_plan(tmp_path):
    seen = []

    def retriever(q, k):
        seen.append(q)
        return [{"name": f"L{len(seen)}", "signature": "sig", "score": 0.5}]

    llm = MockLLM({"planner": ["paso uno\npaso dos"], "generator": ["sketch"],
                   "formalizer": ["```lean\nomega\n```"]})
    cfg = RunConfig(name="t", use_critic=False, top_k=2, rag_query="plan")
    g = build_graph(llm, retriever, lambda c, e=None: (True, ""), cfg, JsonlLogger(str(tmp_path / "l.jsonl")),
                    {"planner": "{x}", "generator": "{x}", "formalizer": "{x}"})
    s = run_problem(g, "t1", "problema", statement_lean="theorem t1 : True")
    assert s["status"] == "DONE" and seen == ["paso uno", "paso dos"]
    assert [l["name"] for l in s["retrieved"]] == ["L1", "L2"]
    prompts = [p for a, p in llm.calls if a == "formalizer"]
    assert "Useful Mathlib lemmas" in prompts[0] and "L1" in prompts[0]
