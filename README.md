# Proyecto IA: multiagente + Lean 4
Base de la semana 1. Probado: `pip install -r requirements.txt && pytest` (7 pruebas del grafo con MockLLM).
Sin probar: `src/verifier_lean.py` contra Lean real (hacerlo con el teorema trivial de la semana 1).
- `src/`        contratos, grafo, LLM (mock), logger, verificador Lean
- `retrieval/`  extracción de Mathlib, índice y recuperador (semana 2-3)
- `experiments/stats.py`  estadística de la ablación (semana 4)
- `prompts/`, `schemas/`, `data/`, `logs/`  vacíos por ahora
