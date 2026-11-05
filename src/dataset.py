"""Conjunto de evaluación: convierte miniF2F (google-deepmind) a problems.jsonl y comprueba que los
enunciados compilan en NUESTRO Lean/Mathlib.

Fuente: data/raw/Test.lean (google-deepmind/miniF2F, formalizado para Lean 4.27; el nuestro es 4.36).
Se usa solo Test.lean: Valid.lean emplea `answer(...)`, que exige otra dependencia (formal_conjectures).

Uso (desde /workspace/proyecto_ia_lean):
    python3 -m src.dataset build                 # data/raw/Test.lean -> data/problems.jsonl + resumen
    python3 -m src.dataset check                 # compila cada enunciado con `sorry` -> data/compile_report.jsonl
    python3 -m src.dataset check --ids mathd_algebra_478,mathd_numbertheory_3   # solo algunos
"""
import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

PRELUDE = "open scoped Nat Real"      # apertura de espacios de nombres que usa el archivo de miniF2F

BLOCK = re.compile(
    r"^(?:/--(?P<doc>(?:(?!-/).)*)-/[ \t]*\n)?theorem[ \t]+(?P<name>\S+)(?P<rest>.*?)"
    r"(?=^/--|^theorem[ \t]|\Z)", re.M | re.S)
SORRY = re.compile(r":=\s*by\s+sorry\b")
COMMENT = re.compile(r"/-(?!-).*?-/|--[^\n]*", re.S)      # comentarios (no docstrings)

NT_HINT = re.compile(r"Nat\.Prime|\bPrime\b|\.gcd|Nat\.gcd|Nat\.lcm|\bgcd\b|\blcm\b|∣|Nat\.digits|ZMod|"
                     r"Int\.emod|\bEven\b|\bOdd\b|\bdigits\b| % ")
COUNT_HINT = re.compile(r"Finset\.card|Nat\.choose|Fintype\.card|Nat\.card|\.card\b|\bchoose\b")


def family(name: str) -> str:
    for prefix, fam in (("mathd_", "mathd"), ("amc12", "amc12"), ("aime", "aime"), ("imo", "imo")):
        if name.startswith(prefix):
            return fam
    return "otro"


DIFFICULTY = {"mathd": "basico", "amc12": "intermedio", "aime": "avanzado", "imo": "avanzado",
              "otro": "sin_clasificar"}


def classify_area(name: str, statement: str | None) -> tuple[str, str]:
    """(area, fuente). 'nombre' = viene del nombre del problema; 'heuristica' = revisar a mano."""
    if "numbertheory" in name:
        return "teoria_de_numeros", "nombre"
    if "algebra" in name:
        return "algebra", "nombre"
    s = statement or ""
    if COUNT_HINT.search(s):
        return "conteo", "heuristica"
    if NT_HINT.search(s):
        return "teoria_de_numeros", "heuristica"
    return "algebra", "heuristica"


def _clean_comment(c: str) -> str:
    c = re.sub(r"^/-+|-+/$|^--", "", c.strip())
    return re.sub(r"\s+", " ", c).strip()


def split_tail(rest: str):
    """Separa el enunciado de lo que sigue a su `:= by sorry`. Lo que sigue solo puede ser comentarios
    (notas de los mantenedores sobre el teorema SIGUIENTE). Si hay otra cosa, el teorema trae prueba."""
    ms = list(SORRY.finditer(rest))
    if ms:
        tail = rest[ms[-1].end():]
        if not COMMENT.sub("", tail).strip():
            return rest[:ms[-1].start()], [_clean_comment(c) for c in COMMENT.findall(tail)]
    return None, []


def parse_minif2f(text: str) -> list[dict]:
    problems, pending = [], []
    for m in BLOCK.finditer(text):
        name, rest = m.group("name"), m.group("rest").rstrip()
        doc = re.sub(r"\s+", " ", (m.group("doc") or "")).strip()
        head, notes_after = split_tail(rest)
        statement = f"theorem {name}{head}".strip() if head is not None else None
        notes_here, pending = pending, [n for n in notes_after if n]
        fam = family(name)
        area, area_src = classify_area(name, statement)
        problems.append({
            "id": name,
            "source_family": fam,
            "difficulty": DIFFICULTY[fam],
            "area": area,
            "area_source": area_src,
            "statement_nl": doc,
            "statement_lean": statement,
            "lean_with_sorry": f"{statement} := by\n  sorry" if statement else None,
            "has_reference_proof": statement is None,
            "maintainer_note": " | ".join(notes_here),
            "prelude": PRELUDE,
        })
    return problems


def summarize(problems: list[dict]) -> str:
    elig = [p for p in problems if not p["has_reference_proof"]]
    lines = [f"{len(problems)} problemas parseados, {len(elig)} elegibles "
             f"({len(problems) - len(elig)} ya traen prueba: {[p['id'] for p in problems if p['has_reference_proof']]})",
             "", "Elegibles por dificultad x área (área 'heurística' = revisar a mano):"]
    cross = Counter((p["difficulty"], p["area"]) for p in elig)
    diffs, areas = ["basico", "intermedio", "avanzado", "sin_clasificar"], ["algebra", "teoria_de_numeros", "conteo"]
    lines.append(f"{'':<16}" + "".join(f"{a:>20}" for a in areas))
    for d in diffs:
        lines.append(f"{d:<16}" + "".join(f"{cross[(d, a)]:>20}" for a in areas))
    heur = sum(1 for p in elig if p["area_source"] == "heuristica")
    lines.append(f"\nÁrea asignada por heurística (no por nombre): {heur} de {len(elig)}")
    noted = [p["id"] for p in elig if p["maintainer_note"]]
    lines.append(f"Con nota de los mantenedores (enunciado con advertencia conocida): {len(noted)}")
    return "\n".join(lines)


def check_statements(problems: list[dict], verifier, prelude: str = PRELUDE, log=print) -> list[dict]:
    """Envía cada enunciado con `sorry`. Compila <=> el verificador contesta 'uses sorry' (sin errores)."""
    records = []
    for i, p in enumerate(problems, 1):
        if p["has_reference_proof"]:
            continue
        t0 = time.perf_counter()
        ok, trace = verifier(f"{prelude}\n{p['lean_with_sorry']}")
        sec = time.perf_counter() - t0
        if trace.startswith(("timeout", "repl_error")):
            status = "infra"
        elif (not ok) and trace.startswith("uses sorry"):
            status = "compila"
        else:
            status = "error"
        records.append({"id": p["id"], "status": status, "seconds": round(sec, 2),
                        "detail": "" if status == "compila" else trace[:700]})
        if i % 25 == 0:
            log(f"  {i}/{len(problems)} revisados")
    return records


def error_kinds(records: list[dict]) -> Counter:
    kinds = Counter()
    for r in records:
        if r["status"] == "error":
            m = re.search(r"error: (.{0,70})", r["detail"])
            kinds[re.sub(r"[`'][^`']*[`']", "·", m.group(1)) if m else r["detail"][:70]] += 1
    return kinds


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--src", default="data/raw/Test.lean")
    b.add_argument("--out", default="data/problems.jsonl")
    c = sub.add_parser("check")
    c.add_argument("--problems", default="data/problems.jsonl")
    c.add_argument("--out", default="data/compile_report.jsonl")
    c.add_argument("--ids", default=None, help="lista separada por comas")
    c.add_argument("--url", default="http://127.0.0.1:8765")
    a = ap.parse_args()

    if a.cmd == "build":
        problems = parse_minif2f(Path(a.src).read_text(encoding="utf-8"))
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            for p in problems:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        print(summarize(problems))
        print(f"\nEscrito: {a.out}")
        return

    from .verify_client import RemoteVerifier, VerifierUnavailable
    problems = [json.loads(l) for l in open(a.problems, encoding="utf-8")]
    if a.ids:
        wanted = set(a.ids.split(","))
        problems = [p for p in problems if p["id"] in wanted]
    v = RemoteVerifier(a.url)
    try:
        print("Esperando al servidor de verificación...", flush=True)
        v.wait_ready()
        t0 = time.perf_counter()
        records = check_statements(problems, v)
    except VerifierUnavailable as e:
        raise SystemExit(f"Servidor no disponible: {e}")
    with open(a.out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    cnt = Counter(r["status"] for r in records)
    print(f"\nCompilan: {cnt['compila']}/{len(records)}  |  con error: {cnt['error']}  |  fallo de infraestructura: {cnt['infra']}"
          f"  ({time.perf_counter() - t0:.0f} s)")
    if cnt["error"]:
        print("\nTipos de error más frecuentes:")
        for kind, n in error_kinds(records).most_common(8):
            print(f"  {n:>4}  {kind}")
    print(f"\nInforme: {a.out}")


if __name__ == "__main__":
    main()
