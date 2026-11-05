"""Verificador Lean 4 (opción A: robusto y simple, `lake env lean`).  NFR-1: el veredicto SOLO
sale del kernel. Interfaz del grafo:  verifier(lean_code) -> (bool, trace).

Qué cuenta como ACEPTADO:
  1. Lean termina sin líneas `error`.
  2. No hay `sorry` (ni warning "declaration uses 'sorry'", ni sorryAx en los axiomas).
  3. `#print axioms <teorema>` solo muestra propext, Classical.choice, Quot.sound
     (esto atrapa `axiom` inventados y `native_decide`).
  4. (opcional) el enunciado coincide con el del dataset -> evita mal-formalización en el teorema final.
"""
import re, subprocess, tempfile
from pathlib import Path

OK_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}
HEADER = ("import Mathlib\nimport Aesop\nset_option maxHeartbeats 400000\n"
          "open BigOperators Real Nat Topology Rat\n\n")
NAME = re.compile(r"^\s*(?:@\[[^\]]*\]\s*)?(?:protected\s+|private\s+)*(?:theorem|lemma)\s+([^\s:({\[]+)", re.M)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


class LeanVerifier:
    def __init__(self, project_dir: str, timeout: int = 180, header: str = HEADER, runner=None):
        self.project_dir, self.timeout, self.header = Path(project_dir), timeout, header
        self.runner = runner or self._run_lake

    def _run_lake(self, src: str):
        with tempfile.NamedTemporaryFile("w", suffix=".lean", dir=self.project_dir, delete=False,
                                         encoding="utf-8") as f:
            f.write(src); path = f.name
        try:
            p = subprocess.run(["lake", "env", "lean", path], cwd=self.project_dir, capture_output=True,
                               text=True, timeout=self.timeout, encoding="utf-8")
            return p.stdout + p.stderr, False
        except subprocess.TimeoutExpired:
            return "", True
        finally:
            Path(path).unlink(missing_ok=True)

    def __call__(self, lean_code: str, expected_statement: str | None = None):
        code = "\n".join(l for l in lean_code.splitlines() if not l.strip().startswith("import "))
        names = NAME.findall(code)
        if not names:
            return False, "formalization_failure: no theorem/lemma found"
        if expected_statement and _norm(expected_statement) not in _norm(code):
            return False, "misformalization: statement differs from the dataset's"
        src = self.header + code + "\n" + "".join(f"\n#print axioms {n}" for n in names)
        out, timed_out = self.runner(src)
        if timed_out:
            return False, "timeout"
        if re.search(r"\berror\b", out, re.I) and re.search(r":\s*error", out):
            return False, out[:4000]
        if "sorry" in out:
            return False, "uses sorry:\n" + out[:2000]
        for m in re.finditer(r"depends on axioms: \[([^\]]*)\]", out):
            bad = {a.strip() for a in m.group(1).split(",") if a.strip()} - OK_AXIOMS
            if bad:
                return False, f"non-standard axioms: {sorted(bad)}"
        return True, ""
