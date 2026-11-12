"""Prompts de los agentes. Cada plantilla usa SOLO el marcador {x} (el grafo hace .format(x=...)).
No escribas llaves { } sueltas aquí: si hicieran falta, se escriben dobles {{ }}.
Se afinan únicamente con el conjunto de desarrollo (el código se congela el 18 nov)."""

SYSTEM = ("You are an expert in Lean 4 and Mathlib. The environment already has `import Mathlib` and "
          "`open scoped Nat Real` loaded.")

PLANNER = SYSTEM + """

Break the problem below into a short proof plan: between 2 and 5 steps, one step per line, each step one
short sentence of mathematical strategy (for example: "Rewrite the hypotheses to isolate x", "Substitute
into the goal and simplify"). Do not write Lean code. Do not add headings, numbering or any extra text.

{x}"""

GENERATOR = SYSTEM + """

Below you have a theorem, a proof plan, optionally some Mathlib lemmas and optionally feedback on a previous
failed attempt. Write the proof strategy in detail: which tactics to use and why (for example `nlinarith`,
`field_simp`, `norm_num`, `omega`, `simp`, `positivity`), which Mathlib lemmas to apply, and the order of the
steps. Be concrete about Lean tactics. Do not write the final theorem statement.

{x}"""

FORMALIZER_V1 = SYSTEM + """

Turn the proof strategy below into a Lean 4 proof of the fixed statement. Reply with ONLY the tactic proof
that goes after `:= by`, inside one ```lean code block. Do not repeat the theorem statement. Do not use
`sorry`, `admit` or new axioms. Prefer robust automation (`nlinarith`, `linarith`, `norm_num`, `omega`,
`field_simp`, `simp`) over fragile rewriting.

{x}"""

FORMALIZER_V2 = SYSTEM + """

Turn the proof strategy below into a Lean 4 proof of the fixed statement. Reply with ONLY the tactic proof
that goes after `:= by`, inside one ```lean code block. Do not repeat the theorem statement.

Hard rules:
- No `sorry`, `admit`, `native_decide` or new axioms.
- Prefer robust automation over fragile rewriting: `omega` (linear arithmetic over naturals and integers,
  including `%` and `/` by numerals), `norm_num`, `nlinarith [...]` and `linarith` (real arithmetic, give hint
  terms such as `sq_nonneg (a - b)`), `positivity`, `field_simp`, `simp`, `decide` (small finite cases).
- Use `rw` only when you are sure the pattern appears exactly in the goal.
- Unpack hypotheses first (`obtain ⟨h1, h2⟩ := h`, `subst`, `rcases`) and name what you use.
- Hedge with fallbacks: `first | omega | nlinarith [sq_nonneg (a - b)] | norm_num | simp`, so that one failing
  tactic does not sink the whole proof.
- Keep the proof short: a few lines are better than a long chain that can break.

{x}"""

FORMALIZER_V3 = SYSTEM + """

Turn the proof strategy below into a Lean 4 proof of the fixed statement. Reply with ONLY the tactic proof
that goes after `:= by`, inside one ```lean code block. Do not repeat the theorem statement.

Rules:
- No `sorry`, `admit`, `native_decide` or new axioms.
- Follow the strategy. If it recommends a single automation tactic (for example `omega`, `norm_num`, `decide`,
  `simp`, `nlinarith [...]`), your proof must try exactly that tactic first. Do NOT add intermediate `have`
  statements or `rw` steps that the strategy does not need: every extra step is another chance to fail, and
  one failing step sinks the whole proof.
- To keep fallbacks, put the alternatives on ONE line: `first | omega | nlinarith [sq_nonneg (a - b)] | simp`.
  Each alternative must be a complete tactic that closes the goal.
- If an intermediate fact is really needed, prove it with automation (`have h : <statement> := by omega`) and
  close the goal with automation too. Use `rw` only when the pattern appears exactly in the goal.
- Natural-number subtraction, `%` and `/` by numerals: `omega`. Real arithmetic: `nlinarith` with hint terms,
  `field_simp`, `norm_num`.
- A short proof (1 to 6 lines) is better than a long one.

{x}"""

CRITIC = SYSTEM + """

A Lean 4 proof attempt failed. Read the Lean error and decide what to do next.

- RETRY: the strategy is fine but the Lean code has a local problem (a rewrite whose pattern is not in the
  goal, a wrong lemma name, a tactic that needs another hint). Often the best fix is to DELETE the failing
  step and let one automation tactic (omega, nlinarith [...], norm_num, simp) close the goal.
- REPLAN: the whole approach cannot work (the tactic is too weak for this kind of goal). Suggest a different
  approach.
- FAIL: hopeless.

Reply in exactly this format and nothing else:
ACTION: RETRY or REPLAN or FAIL
HINT: one to three sentences telling the next attempt precisely what to change.

{x}"""

PROMPTS_BY_VARIANT = {
    "v1": {"planner": PLANNER, "generator": GENERATOR, "formalizer": FORMALIZER_V1},
    "v2": {"planner": PLANNER, "generator": GENERATOR, "formalizer": FORMALIZER_V2},
    "v3": {"planner": PLANNER, "generator": GENERATOR, "formalizer": FORMALIZER_V3},
}
for _v in PROMPTS_BY_VARIANT.values():
    _v["critic"] = CRITIC
DEFAULT_VARIANT = "v1"          # cambia a la ganadora SOLO tras compararlas sobre el conjunto de desarrollo
FORMALIZER = PROMPTS_BY_VARIANT[DEFAULT_VARIANT]["formalizer"]
PROMPTS = PROMPTS_BY_VARIANT[DEFAULT_VARIANT]
