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

FORMALIZER = SYSTEM + """

Turn the proof strategy below into a Lean 4 proof of the fixed statement. Reply with ONLY the tactic proof
that goes after `:= by`, inside one ```lean code block. Do not repeat the theorem statement. Do not use
`sorry`, `admit` or new axioms. Prefer robust automation (`nlinarith`, `linarith`, `norm_num`, `omega`,
`field_simp`, `simp`) over fragile rewriting.

{x}"""

PROMPTS = {"planner": PLANNER, "generator": GENERATOR, "formalizer": FORMALIZER}
