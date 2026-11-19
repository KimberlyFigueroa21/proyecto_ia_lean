---
title: Multi-agent Lean 4 prover - results explorer
emoji: 🧮
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 5.9.1
app_file: app.py
pinned: false
short_description: Explore results of a multi-agent Lean 4 proof system
---

# Multi-agent generative AI with formal verification in Lean 4

Results explorer for a course project (Inteligencia Computacional, UPTC Sogamoso).
A multi-agent system (Planner, Retriever/RAG, Generator, AutoFormalizer, LeanVerifier, Critic; LangGraph)
tries to prove 30 miniF2F problems in Lean 4 / Mathlib, and five configurations are compared
(Baseline A, Baseline B, w/o RAG, w/o Critic, Full).

This Space only **reads saved results**: it does not call an LLM or run Lean, and needs no API key.

- Code, prompts and reproduction instructions: https://github.com/KimberlyFigueroa21/proyecto_ia_lean (tag `congelado`)
- Authors: Kimberly Natalia Figueroa Zapata, Alisson Páez Alarcón (UPTC Sogamoso)

Results are small-sample (20 test problems, one run per configuration, one model) and describe trends, not general capability.
