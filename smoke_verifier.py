"""Prueba de humo del verificador Lean (semana 1, pista Lean).

Ejecutar DENTRO del contenedor, desde la carpeta del repositorio:
    cd /workspace/proyecto_ia_lean
    python3 smoke_verifier.py          # importación mínima (rápida)
    python3 smoke_verifier.py --full   # con `import Mathlib` completo (mide también la velocidad)

Resultado esperado: las 5 líneas con "OK". Cualquier "MAL" indica que el verificador
acepta algo que debería rechazar (o al revés).
"""
import sys
import time

from src.verifier_lean import LeanVerifier

# Ruta del proyecto Lean dentro del contenedor (volumen de Docker del Camino 2).
# Si todavía no lo moviste, usa "/workspace/LeanMathlibProject".
PROYECTO_LEAN = "/opt/lean/LeanMathlibProject"

HEADER = "import Mathlib\n" if "--full" in sys.argv else "import Mathlib.Data.Nat.Basic\n"

CASOS = {
    "ok_omega": ("theorem t1 (a b : ℕ) : a + b = b + a := by omega", True),
    "ok_exact": ("theorem t2 (a b : ℕ) : a + b = b + a := by exact Nat.add_comm a b", True),
    "sorry":    ("theorem t3 (a b : ℕ) : a + b = b + a := by sorry", False),
    "error":    ("theorem t4 (a b : ℕ) : a + b = b + a := by exact zzz", False),
    "axioma":   ("axiom ax : False\ntheorem t5 : 1 = 2 := ax.elim", False),
}


def main() -> int:
    verificador = LeanVerifier(PROYECTO_LEAN, header=HEADER, timeout=600)
    print(f"Proyecto Lean: {PROYECTO_LEAN}")
    print(f"Encabezado:    {HEADER.strip()}\n")
    fallos = 0
    for nombre, (codigo, esperado) in CASOS.items():
        t0 = time.perf_counter()
        ok, traza = verificador(codigo)
        seg = time.perf_counter() - t0
        bien = ok == esperado
        fallos += not bien
        print(f"{'OK ' if bien else 'MAL'} {nombre:<9} veredicto={ok!s:<5} {seg:5.1f}s  {traza[:70]!r}")
    print(f"\n{len(CASOS) - fallos}/{len(CASOS)} casos correctos")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
