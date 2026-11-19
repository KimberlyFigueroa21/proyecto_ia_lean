# Technical documentation

## 1. Architecture

LangGraph state machine over a shared `GraphState`. Nodes: `plan`, `retrieve`, `generate`, `formalize`, `verify`,
`critique`, `advance`, `done`, `fail` (`src/graph.py`). Contracts between agents are Pydantic v2 models (`src/contracts.py`);
each configuration is a `RunConfig` and the graph keeps the same shape for all of them.

```
PLAN → RETRIEVE → GENERATE → FORMALIZE → VERIFY ─ accepted ─→ DONE
                                           └ rejected → CRITIQUE ─ retry (k < k_max) ─→ GENERATE
                                                                  ├ replan (r < r_max) ─→ PLAN
                                                                  └ otherwise ─→ FAIL
```

Counters `k` (retries) and `r` (replans) are separate, so replanning is reachable. Defaults: `k_max = 3`,
`r_max = 1`, `top_k = 5`, `max_llm_calls = 30` (hard safety cap; the average is reported), temperature 0.
The Critic only sees the Lean error text, not the reference proof.

Every agent call is logged as JSON Lines with tokens and latency (`*_agentes.jsonl` in the repository).

## 2. Verification

Lean 4.36.0-rc2 and Mathlib commit `9d581dfff2e41de989072ea63abf3daf69311520` run in a Docker container
(`lean-dev`). A local server (`src.verify_server`, 127.0.0.1:8765) keeps Mathlib loaded and compiles
`theorem … := by <tactics>`. A proof is **verified** when Lean reports no error and the declaration does not use
`sorry`. The formal statement is fixed by the system; the model only writes the tactic block.
A proof counts as **delivered** when the system presents it as correct (for Baseline B: always).

## 3. RAG

- Corpus: 123,201 theorems dumped from Lean itself for the same Mathlib commit (exact names and signatures).
- Embeddings: `BAAI/bge-small-en-v1.5` (d = 384, max sequence 256), cosine similarity via NumPy `V @ q`.
- Query variants evaluated on 10 development problems with hand-picked expected lemmas (exact name match):
  recall@10 = 0.30 (Lean statement), 0.20 (plan + Lean), 0.10 (plan), 0.00 (problem text).
  The best variant (`lean`) is used in all experiments. These numbers are a guide for choosing a variant, not an estimate
  of retrieval quality.

## 4. Configurations

| Name | Planner | RAG | Critic | Verified before delivering |
|---|---|---|---|---|
| Baseline A | – | – | – | yes (one attempt) |
| Baseline B | – | – | – | no (delivers every proof; Lean is applied afterwards) |
| w/o RAG | yes | no | yes | yes |
| w/o Critic | yes | yes | no | yes |
| Full | yes | yes | yes | yes |

LLM: `gemini-3.5-flash-lite` (Google AI Studio, free tier: 10 requests/minute, 500/day), thinking level low,
max 8192 output tokens, on-disk response cache. Prompt variant `v1`.

## 5. Evaluation protocol

30 miniF2F problems, 3 difficulty levels × 3 areas; 10 development / 20 test. Development was used to tune prompts and
the RAG query; the code was frozen (git tag `congelado`) and the test set was run once.

- **pass@1**: share of problems whose delivered proof Lean accepts (no extra attempts are counted; Critic retries
  happen before delivery).
- Intervals: Wilson 95 %. Paired comparisons: exact McNemar with Bonferroni (5 planned comparisons: Full vs. w/o RAG,
  w/o Critic, Baseline A, Baseline B; w/o Critic vs. Baseline A) and paired bootstrap of the difference (10,000
  resamples, seed 0). Implementation: `src/stats.py` (standard library only).
- Rescued by retry: verified with more than 3 LLM calls (the minimum is Planner + Generator + AutoFormalizer).
- Lemma use: a retrieved lemma name appears in the final proof.
- Failure taxonomy: rules over the last Lean message of each failed problem (heuristic, one category per problem).

## 6. Results summary

See `README.md` for the test table. Development (n = 10): A 4, B 4 (6 false positives of 10 delivered), w/o RAG 5,
w/o Critic 4, Full 6. Test: no difference between configurations is significant; the only large effect is the
false-positive rate of the unverified Baseline B (18 of 20 delivered proofs rejected). All proofs solved by the
pipeline close with automation tactics (`omega`, `nlinarith`, …); none used a retrieved lemma.

## 7. Limitations

Small evaluation set; one model, one run per configuration (variance not measured); tuning on 10 development
problems; possible contamination; manual area labels; heuristic error taxonomy; results tied to one Lean/Mathlib
version; Gemini 503 errors affect timing but are retried and never counted as results.

## 8. Repository layout

| Path | Content |
|---|---|
| `src/` | contracts, graph, agents, prompts, retriever, verifier client/server, statistics |
| `run_experiment.py`, `run_pipeline.py`, `run_baselines.py` | experiment runners (`--auto-resume` handles quota and 503) |
| `analyze_results.py` | statistics and tables from `results/` |
| `rag/` | Mathlib dump (`dump_decls.lean`), index build, retrieval evaluation |
| `data/` | evaluation set, development RAG queries, audit notes |
| `results/` | `.jsonl` results per configuration and split, analysis files |
| `paper_results/` | figures, tables and scripts used by the report |
| `tests/` | 114 tests (mock LLM, no API key) |

## 9. Security and ethics

The API key is only read from the environment and is not stored in the repository, logs or results. Only public
mathematical statements and generated Lean code are sent to the LLM service. The system is a research prototype:
"verified" certifies the proof against the formal statement, not the faithfulness of the statement.
