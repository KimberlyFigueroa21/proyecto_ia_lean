---
language: [en]
pretty_name: Lean 4 multi-agent evaluation set and results (30 miniF2F problems)
size_categories: [n<1K]
task_categories: [text-generation]
tags: [lean4, mathlib, formal-verification, minif2f, theorem-proving]
---

# Dataset card

## Contents

| File | Description |
|---|---|
| `data/eval_set.jsonl` | 30 miniF2F problems selected for evaluation, with split and labels |
| `results/*.jsonl` | one record per problem and configuration (5 configurations × dev/test) |
| `rag_data/idx2/` | embedding index of 123,201 Mathlib theorems (BAAI/bge-small-en-v1.5, d = 384) [subir si el tamaño lo permite] |

## Evaluation set

30 formal statements taken from miniF2F (Lean 4 version, statements only: no reference proofs are included).
Families: amc12 (11), mathd (10), aime (5), imo (4).

| | Basic | Intermediate | Advanced | Total |
|---|---|---|---|---|
| Development | 6 | 2 | 2 | 10 |
| Test | 4 | 9 | 7 | 20 |

Areas (manual labels): algebra 11, counting 10, number theory 9. Development: algebra 5 / counting 2 / number theory 3;
test: 6 / 7 / 7. The split is fixed: development problems were used to build and tune the system, test problems were
evaluated once after the code was frozen.

### Fields of `eval_set.jsonl`

`id`, `source_family`, `difficulty` (basico | intermedio | avanzado), `area`, `area_source` (`nombre` = from the
problem name, `heuristica` = keywords; the latter are less reliable), `statement_nl` (natural language),
`statement_lean`, `lean_with_sorry`, `has_reference_proof`, `maintainer_note`, `prelude`
(`open scoped Nat Real`), `split` (dev | test).

## Results files

File names: `baseline_a_<split>.jsonl`, `baseline_b_<split>.jsonl`, `pipeline_<config>_<split>_v1[_lean].jsonl`
(`_lean` = RAG query built from the Lean statement). Main fields: `problem_id`, `verified` (accepted by Lean),
`claimed_correct` (delivered as correct), `lean_code`, `trace` (last Lean message), `llm_calls`, `tokens_in`,
`tokens_out`, `latency_s`; pipeline runs add `subgoals`, `retrieved`, `r` (replans), `k`, `status`, `failure_reason`.
Baseline B's verification is post-hoc (it never uses Lean to decide what to deliver).

## Known issues and limitations

- Labels for area and difficulty are manual; some counting labels are debatable (see `data/auditoria.md`).
- Formal statements are used as in miniF2F; Lean checks the proof against the formal statement, not against the
  natural-language problem. Mis-formalizations are possible.
- miniF2F is public and its proofs circulate online: training-data contamination of the LLM cannot be ruled out.
- 30 problems and one run per configuration give very wide confidence intervals.
- Results depend on Lean 4.36.0-rc2, Mathlib commit `9d581dfff2e41de989072ea63abf3daf69311520` and
  `gemini-3.5-flash-lite` (temperature 0). Error categories are heuristic.

## Licenses and attribution

miniF2F (Zheng, Han, Polu, 2022) and Mathlib have their own licenses [verificar y citar]. Generated proofs and
analysis: [licencia por definir].

## Citation

Figueroa Zapata, K. N. and Páez Alarcón, A. *Multi-agent generative AI with formal verification in Lean 4*.
UPTC Sogamoso, 2026. [completar con la referencia final del informe]
