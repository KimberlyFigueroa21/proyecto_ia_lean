# Multi-agent generative AI with formal verification in Lean 4

Course project, *Inteligencia Computacional*, Universidad Pedagógica y Tecnológica de Colombia (UPTC), Sogamoso.
Authors: Kimberly Natalia Figueroa Zapata, Alisson Páez Alarcón.

A multi-agent system attempts to prove competition-level theorems from **miniF2F** in **Lean 4 / Mathlib**.
A proof counts only if the Lean kernel accepts it. Six agents are orchestrated with LangGraph:

| Agent | Role |
|---|---|
| Planner | splits the problem into 2–5 subgoals |
| Retriever (RAG) | retrieves Mathlib lemmas by cosine similarity (BAAI/bge-small-en-v1.5, 123,201 theorems) |
| Generator | writes a detailed proof strategy |
| AutoFormalizer | turns the strategy into a Lean 4 tactic proof |
| LeanVerifier | compiles the proof with Lean/Mathlib |
| Critic | decides: retry (k ≤ 3), replan (r ≤ 1), finish or fail |

Control flow: PLAN → RETRIEVE → GENERATE → FORMALIZE → VERIFY → (CRITIQUE | DONE | FAIL).

## Experiment

Five configurations on 30 miniF2F problems (10 development, 20 test; the test set was evaluated once, after the code was
frozen, tag `congelado`): Baseline A (one call + verification), Baseline B (one call, never verified: it "delivers" every
proof), w/o RAG, w/o Critic, Full. LLM: `gemini-3.5-flash-lite` (temperature 0, one run per configuration).

**Test results (n = 20)**

| Configuration | pass@1 | 95 % Wilson CI | Delivered | False positives | Mean LLM calls |
|---|---|---|---|---|---|
| Baseline A | 1/20 | [0.01, 0.24] | 1 | 0 | 1.0 |
| Baseline B | 2/20 | [0.03, 0.30] | 20 | 18 | 2.0 |
| w/o RAG | 3/20 | [0.05, 0.36] | 3 | 0 | 9.6 |
| w/o Critic | 2/20 | [0.03, 0.30] | 2 | 0 | 3.0 |
| Full | 2/20 | [0.03, 0.30] | 2 | 0 | 10.2 |

Honest reading: very few problems are solved; differences are at most one problem and none is statistically significant
(exact McNemar, Bonferroni ×5). The clear effect is verification: Baseline B delivered 20 proofs and Lean rejected 18.
No correct proof used a lemma retrieved by RAG, so RAG gets no credit here. See `docs/TECHNICAL.md` for details and limitations.

## Links

- Space (results explorer): https://huggingface.co/spaces/KimberlyFigueroa01/lean-multiagent-explorer-static 
- Dataset / results: https://huggingface.co/datasets/KimberlyFigueroa01/lean-multiagent-minif2f-eval
- Technical documentation: `docs/TECHNICAL.md`; dataset card: `DATASET_CARD.md`

## Reproducing

Requirements: Docker with Lean 4.36.0-rc2 + Mathlib (commit `9d581dfff2e41de989072ea63abf3daf69311520`), Python 3.12,
a Gemini API key (`GEMINI_API_KEY`), the RAG index (`rag_data/idx2`, not in Git because of its size; see Hugging Face).

```bash
export GEMINI_MODEL=gemini-3.5-flash-lite
export GEMINI_API_KEY=...            # never commit it
python3 -m src.verify_server &       # Lean verification server (startup takes several minutes)
python3 run_experiment.py --split dev  --rag-query lean --auto-resume
python3 run_experiment.py --split test --rag-query lean --auto-resume --allow-test
python3 analyze_results.py --split test
python3 -m pytest tests              # 114 tests, no API key needed (mock LLM)
```

Free-tier limits (10 requests/minute, 500/day) make a full run take about a day; responses are cached on disk.

## Limitations

Small evaluation set, single model and single run, tuning on 10 development problems, possible training-data
contamination (miniF2F is public), heuristic error taxonomy, results tied to one Lean/Mathlib version.

## Licenses

Code: [LICENSE por definir]. Lean 4, Mathlib and miniF2F keep their own licenses [verificar antes de publicar].
