"""Prueba de humo del verificador con REPL persistente (Plan B).

Ejecutar DENTRO del contenedor, desde /workspace/proyecto_ia_lean:
    python3 smoke_repl.py --minimal   # 1.º: comprueba el cableado con un import pequeño (segundos)
    python3 smoke_repl.py             # 2.º: con `import Mathlib` completo (el arranque puede tardar minutos)

Lo importante es la columna de tiempos: tras el arranque, cada caso debe tardar segundos,
no minutos. Resultado esperado: 5/5 casos correctos.
"""
import sys
import time

from src.verifier_repl import LeanReplVerifier

PROYECTO_LEAN = "/opt/lean/LeanMathlibProject"
REPL_BIN = "/opt/lean/repl/.lake/build/bin/repl"
HEADER = ("import Mathlib.Data.Nat.Basic\n" if "--minimal" in sys.argv else
          "import Mathlib\nimport Aesop\nset_option maxHeartbeats 400000\n"
          "open BigOperators Real Nat Topology Rat\n")

CASOS = {
    "ok_omega": ("theorem t1 (a b : ℕ) : a + b = b + a := by omega", True),
    "ok_exact": ("theorem t2 (a b : ℕ) : a + b = b + a := by exact Nat.add_comm a b", True),
    "sorry":    ("theorem t3 (a b : ℕ) : a + b = b + a := by sorry", False),
    "error":    ("theorem t4 (a b : ℕ) : a + b = b + a := by exact zzz", False),
    "axioma":   ("axiom ax : False\ntheorem t5 : 1 = 2 := ax.elim", False),
}


def main() -> int:
    print(f"Encabezado: {HEADER.splitlines()[0]}")
    print("Arrancando el REPL (carga Mathlib una sola vez, puede tardar)...", flush=True)
    fallos = 0
    with LeanReplVerifier(PROYECTO_LEAN, repl_bin=REPL_BIN, header=HEADER) as v:
        print(f"REPL listo en {v.startup_seconds:.1f} s\n")
        for nombre, (codigo, esperado) in CASOS.items():
            t0 = time.perf_counter()
            ok, traza = v(codigo)
            seg = time.perf_counter() - t0
            bien = ok == esperado
            fallos += not bien
            print(f"{'OK ' if bien else 'MAL'} {nombre:<9} veredicto={ok!s:<5} {seg:6.1f}s  {traza[:70]!r}")
    print(f"\n{len(CASOS) - fallos}/{len(CASOS)} casos correctos")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
