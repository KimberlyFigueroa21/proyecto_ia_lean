from src.dataset import check_statements, error_kinds, parse_minif2f

SAMPLE = '''/-
Copyright (c) 2021 OpenAI.
-/
import MiniF2F.ProblemImports

open scoped Nat
open scoped Real

/--
The volume of a cone is $V = \\frac{1}{3}Bh$. What is $V$? -/
theorem mathd_algebra_478 (b h v : ℝ) (h₀ : 0 < b ∧ 0 < h ∧ 0 < v) (h₁ : v = 1 / 3 * (b * h))
    (h₂ : b = 30) (h₃ : h = 13 / 2) : v = 65 := by
  sorry

theorem numbertheory_4x3m7y3neq2003 (x y : ℤ) : 4 * x ^ 3 - 7 * y ^ 3 ≠ 2003 := by
  sorry

/-- Determine the remainder of 194 (mod 11). -/
theorem mathd_numbertheory_66 : 194 % 11 = 7 :=
  rfl

/-- Evaluate. -/
theorem mathd_algebra_302 : (Complex.I / 2) ^ 2 = -(1 / 4) := by
  norm_num [div_pow]

/-- Count the multiples of 20. -/
theorem amc12_2001_p1 : Finset.card (Finset.filter (fun x => 20 ∣ x) (Finset.Icc 15 85)) = 4 := by
  sorry

/-- Un enunciado con := dentro. -/
theorem aime_1983_p9 (x : ℝ) (h : let y := x + 1; y = 2) : x = 1 := by
  sorry

-- Nota: este enunciado es una versión simplificada del original
/-- Con comentario previo. -/
theorem mathd_algebra_999 (x : ℝ) (h : x = 1) : x = 1 := by
  sorry

/-
Un comentario de bloque tras el sorry, sobre el siguiente.
-/
/-- Primos. -/
theorem imo_1959_p1 (n : ℕ) : Nat.gcd (21 * n + 4) (14 * n + 3) = 1 := by
  sorry
'''


def by_id():
    return {p["id"]: p for p in parse_minif2f(SAMPLE)}


def test_cuenta_y_ids():
    assert list(by_id()) == ["mathd_algebra_478", "numbertheory_4x3m7y3neq2003", "mathd_numbertheory_66",
                             "mathd_algebra_302", "amc12_2001_p1", "aime_1983_p9", "mathd_algebra_999",
                             "imo_1959_p1"]


def test_enunciado_sin_el_sorry_y_multilinea():
    p = by_id()["mathd_algebra_478"]
    assert p["statement_lean"].startswith("theorem mathd_algebra_478 (b h v : ℝ)")
    assert p["statement_lean"].endswith("v = 65")
    assert "sorry" not in p["statement_lean"] and ":= by" not in p["statement_lean"]
    assert p["lean_with_sorry"].endswith(":= by\n  sorry")
    assert p["statement_nl"].startswith("The volume of a cone")


def test_docstring_no_se_pega_al_teorema_anterior():
    assert by_id()["numbertheory_4x3m7y3neq2003"]["statement_nl"] == ""


def test_detecta_teoremas_que_ya_traen_prueba():
    P = by_id()
    assert P["mathd_numbertheory_66"]["has_reference_proof"] and P["mathd_numbertheory_66"]["statement_lean"] is None
    assert P["mathd_algebra_302"]["has_reference_proof"]


def test_let_con_dos_puntos_igual_no_corta_el_enunciado():
    assert "let y := x + 1; y = 2" in by_id()["aime_1983_p9"]["statement_lean"]


def test_dificultad_y_area():
    P = by_id()
    assert (P["mathd_algebra_478"]["difficulty"], P["mathd_algebra_478"]["area"]) == ("basico", "algebra")
    assert P["amc12_2001_p1"]["difficulty"] == "intermedio" and P["amc12_2001_p1"]["area"] == "conteo"
    assert P["aime_1983_p9"]["difficulty"] == "avanzado" and P["aime_1983_p9"]["area_source"] == "heuristica"
    assert P["imo_1959_p1"]["area"] == "teoria_de_numeros"
    assert P["numbertheory_4x3m7y3neq2003"]["difficulty"] == "sin_clasificar"


def test_check_statements_clasifica_resultados():
    problems = list(by_id().values())

    def fake(code):
        if "mathd_algebra_478" in code:
            return False, "uses sorry:\n1:8: warning: declaration uses `sorry`"
        if "numbertheory_4x3m7y3neq2003" in code:
            return False, "1:49: error: Unknown identifier `zzz`"
        if "amc12_2001_p1" in code:
            return False, "timeout"
        return False, "uses sorry:\n..."

    recs = {r["id"]: r for r in check_statements(problems, fake, log=lambda *_: None)}
    assert "mathd_numbertheory_66" not in recs              # los que ya traen prueba se omiten
    assert recs["mathd_algebra_478"]["status"] == "compila"
    assert recs["numbertheory_4x3m7y3neq2003"]["status"] == "error"
    assert recs["amc12_2001_p1"]["status"] == "infra"
    assert list(error_kinds(list(recs.values()))) == ["Unknown identifier ·"]


def test_comentarios_tras_el_sorry_no_hacen_que_parezca_que_trae_prueba():
    P = by_id()
    assert not P["aime_1983_p9"]["has_reference_proof"]
    assert not P["mathd_algebra_999"]["has_reference_proof"]          # le sigue un comentario de bloque
    assert P["mathd_algebra_999"]["statement_lean"].endswith("x = 1")


def test_la_nota_se_asigna_al_teorema_siguiente():
    P = by_id()
    assert "simplificada" in P["mathd_algebra_999"]["maintainer_note"]
    assert "comentario de bloque" in P["imo_1959_p1"]["maintainer_note"]
    assert P["mathd_algebra_478"]["maintainer_note"] == ""
