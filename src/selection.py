"""Selección de los 30 problemas de evaluación (determinista y reproducible) + partición dev/test.

    python3 -m src.selection            # escribe data/eval_set.jsonl, data/eval_set.md y data/auditoria.md

Reglas (documentar en el informe: Experimental Setup y Limitations)
- Fuente: miniF2F Test.lean; dificultad por origen (mathd=básico, amc12=intermedio, aime/imo=avanzado);
  los 34 problemas de origen "otro" (sin dificultad por origen) se excluyen.
- Se excluyen los 2 con prueba de referencia y los 2 con nota de los mantenedores.
- Los 5 pilotos (data/pilot_ids.json) ya se usaron para depurar: van a DEV, nunca a test.
- Dentro de cada casilla (área, dificultad) el orden de elección es sha256(semilla:id): sin azar oculto,
  mismo resultado en cualquier máquina.
- Conteo: un problema es de conteo si su META es la cardinalidad de un conjunto (`S.card = k`); criterio objetivo,
  distinto de la técnica que se use para resolverlo (varios son de teoría de números o de trigonometría).
  miniF2F Test solo tiene 9 así (2 básicos y 7 intermedios, ninguno avanzado); se usan todos. Por eso las áreas
  quedan 11/10/9 y no 10/10/10. El profesor lo aceptó si se justifica el límite.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

SEED = 2026
# (split, área, dificultad) -> cuántos. Los pilotos cubren los básicos de dev.
QUOTAS = {
    ("dev", "algebra", "basico"): 3, ("dev", "algebra", "intermedio"): 1, ("dev", "algebra", "avanzado"): 1,
    ("dev", "teoria_de_numeros", "basico"): 2, ("dev", "teoria_de_numeros", "avanzado"): 1,
    ("dev", "conteo", "basico"): 1, ("dev", "conteo", "intermedio"): 1,
    ("test", "algebra", "basico"): 1, ("test", "algebra", "intermedio"): 1, ("test", "algebra", "avanzado"): 4,
    ("test", "teoria_de_numeros", "basico"): 2, ("test", "teoria_de_numeros", "intermedio"): 2,
    ("test", "teoria_de_numeros", "avanzado"): 3,
    ("test", "conteo", "basico"): 1, ("test", "conteo", "intermedio"): 6,
}
N_FIDELITY_AUDIT = 5
# Auditoría de fidelidad hecha por la autora el 11-nov-2026 (enunciado en Lean = enunciado en lenguaje natural):
# sin hallazgos. Se conserva al re-seleccionar para no repetir trabajo; deben seguir estando en el conjunto.
AUDITED_FIDELITY = ["aime_1983_p3", "amc12b_2021_p1", "mathd_algebra_398", "imo_1984_p6", "amc12a_2020_p4"]
# Etiquetas de área corregidas tras esa auditoría (el criterio de conteo pasó a ser la meta del enunciado).
AREA_FIXES = {"imo_1974_p3": "conteo → teoría de números", "amc12a_2021_p25": "conteo → teoría de números"}


def _key(seed: int, pid: str) -> str:
    return hashlib.sha256(f"{seed}:{pid}".encode()).hexdigest()


def select(problems: list[dict], pilot_ids: list[str], seed: int = SEED) -> list[dict]:
    by_id = {p["id"]: p for p in problems}
    pilots = [by_id[i] for i in pilot_ids]
    taken = set(pilot_ids)
    pool = [p for p in problems if p["id"] not in taken and not p["has_reference_proof"]
            and not p["maintainer_note"] and p["difficulty"] in ("basico", "intermedio", "avanzado")]
    chosen = [{**p, "split": "dev"} for p in pilots]
    need = Counter(QUOTAS)
    for p in pilots:                                  # los pilotos descuentan su casilla de dev
        cell = ("dev", p["area"], p["difficulty"])
        if need[cell] <= 0:
            raise ValueError(f"piloto {p['id']} no cabe en la cuota {cell}")
        need[cell] -= 1
    for (split, area, diff), n in sorted(need.items(), key=lambda kv: (kv[0][0] != "dev", kv[0])):
        cands = sorted((p for p in pool if p["area"] == area and p["difficulty"] == diff and p["id"] not in taken),
                       key=lambda p: _key(seed, p["id"]))
        if len(cands) < n:
            raise ValueError(f"faltan problemas en {(split, area, diff)}: hay {len(cands)}, se piden {n}")
        for p in cands[:n]:
            chosen.append({**p, "split": split})
            taken.add(p["id"])
    return chosen


def fidelity_sample(chosen: list[dict], n: int = N_FIDELITY_AUDIT, seed: int = SEED) -> list[str]:
    """Los problemas cuya fidelidad (enunciado en Lean = enunciado en lenguaje natural) se audita a fondo."""
    return [p["id"] for p in sorted(chosen, key=lambda p: _key(seed + 1, p["id"]))[:n]]


def summary_table(chosen: list[dict]) -> str:
    areas, diffs = ["algebra", "teoria_de_numeros", "conteo"], ["basico", "intermedio", "avanzado"]
    lines = ["| Área \\ Dificultad | " + " | ".join(diffs) + " | Total |", "|---|---|---|---|---|"]
    for a in areas:
        row = []
        for d in diffs:
            c = [p for p in chosen if p["area"] == a and p["difficulty"] == d]
            row.append(f"{len(c)} ({sum(p['split'] == 'dev' for p in c)} dev)" if c else "0")
        lines.append(f"| {a} | " + " | ".join(row) + f" | {sum(p['area'] == a for p in chosen)} |")
    lines.append(f"| **Total** | " + " | ".join(str(sum(p['difficulty'] == d for p in chosen)) for d in diffs)
                 + f" | {len(chosen)} |")
    return "\n".join(lines)


def audit_markdown(chosen: list[dict], fid: list[str]) -> str:
    out = ["# Auditoría del conjunto de evaluación", "",
           "Marca cada casilla con `x`. Dos preguntas por problema:", "",
           "- **Área**: ¿la etiqueta (álgebra, teoría de números, conteo) es razonable? "
           "Las de `heurística` se asignaron por palabras clave y son las más dudosas.",
           "- **Fidelidad** (solo los marcados con ★): ¿el enunciado en Lean significa lo mismo que el enunciado "
           "en lenguaje natural? Si no, es una mala formalización: anótala en Observaciones.", ""]
    for p in sorted(chosen, key=lambda p: (p["split"], p["area"], p["difficulty"], p["id"])):
        star = " ★ FIDELIDAD" if p["id"] in fid else ""
        out += [f"## {p['id']}{star}", "",
                f"- Split: **{p['split']}** · Dificultad: {p['difficulty']} · Área: {p['area']} "
                f"(`{p['area_source']}`)",
                f"- [ ] Área correcta" + ("   - [ ] Fidelidad correcta" if star else ""),
                "- Observaciones: ", "",
                "Lenguaje natural:", "", "> " + p["statement_nl"].replace("\n", " ")[:600], "",
                "Lean:", "", "```lean", p["statement_lean"], "```", ""]
    return "\n".join(out)


def main():
    problems = [json.loads(l) for l in Path("data/problems.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    pilots = json.loads(Path("data/pilot_ids.json").read_text())
    chosen = select(problems, pilots)
    fid = [i for i in AUDITED_FIDELITY if i in {p["id"] for p in chosen}]
    if len(fid) < N_FIDELITY_AUDIT:                    # completa con una muestra determinista si hiciera falta
        fid += [i for i in fidelity_sample(chosen, N_FIDELITY_AUDIT) if i not in fid][:N_FIDELITY_AUDIT - len(fid)]
    Path("data/eval_set.jsonl").write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in chosen) + "\n",
                                           encoding="utf-8")
    md = ["# Conjunto de evaluación", "", f"Semilla {SEED}. {len(chosen)} problemas: "
          f"{sum(p['split'] == 'dev' for p in chosen)} dev, {sum(p['split'] == 'test' for p in chosen)} test.", "",
          summary_table(chosen), "",
          "Criterio de conteo: la meta del enunciado es la cardinalidad de un conjunto (`S.card = k`).", "",
          "Auditoría de fidelidad (autora, 11-nov-2026, sin hallazgos): " + ", ".join(AUDITED_FIDELITY) + ".", "",
          "Etiquetas corregidas tras la auditoría: " + "; ".join(f"{k} ({v})" for k, v in AREA_FIXES.items())
          + ". Discutibles, sin cambio: amc12a_2003_p23 y amc12b_2020_p21 (conteo por la meta, técnica de teoría de "
          "números); aime_1994_p3 (álgebra o teoría de números).", "",
          "| id | split | dificultad | área | origen del área |", "|---|---|---|---|---|"]
    md += [f"| {p['id']} | {p['split']} | {p['difficulty']} | {p['area']} | {p['area_source']} |"
           for p in sorted(chosen, key=lambda p: (p["split"], p["area"], p["difficulty"], p["id"]))]
    Path("data/eval_set.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    Path("data/auditoria.md").write_text(audit_markdown(chosen, fid), encoding="utf-8")
    print(summary_table(chosen))
    print(f"\n{len(chosen)} problemas → data/eval_set.jsonl, data/eval_set.md, data/auditoria.md")
    print("Auditoría de fidelidad (★):", ", ".join(fid))


if __name__ == "__main__":
    main()
