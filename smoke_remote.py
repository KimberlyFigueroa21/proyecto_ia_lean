"""Prueba de humo del servidor de verificación (cliente HTTP).

Con el servidor ya corriendo y en estado "ready":
    python3 smoke_remote.py
Cada caso debe tardar décimas de segundo. Resultado esperado: 5/5 casos correctos.
"""
import sys
import time

from src.verify_client import RemoteVerifier, VerifierUnavailable

CASOS = {
    "ok_omega": ("theorem t1 (a b : ℕ) : a + b = b + a := by omega", True),
    "ok_exact": ("theorem t2 (a b : ℕ) : a + b = b + a := by exact Nat.add_comm a b", True),
    "sorry":    ("theorem t3 (a b : ℕ) : a + b = b + a := by sorry", False),
    "error":    ("theorem t4 (a b : ℕ) : a + b = b + a := by exact zzz", False),
    "axioma":   ("axiom ax : False\ntheorem t5 : 1 = 2 := ax.elim", False),
}


def main() -> int:
    v = RemoteVerifier()
    try:
        print("Esperando al servidor...", flush=True)
        h = v.wait_ready()
    except VerifierUnavailable as e:
        print(e)
        return 2
    print(f"Servidor listo: REPL arrancó en {h['startup_seconds']} s, {h['calls']} verificaciones previas\n")
    fallos = 0
    for nombre, (codigo, esperado) in CASOS.items():
        t0 = time.perf_counter()
        ok, traza = v(codigo)
        seg = time.perf_counter() - t0
        bien = ok == esperado
        fallos += not bien
        print(f"{'OK ' if bien else 'MAL'} {nombre:<9} veredicto={ok!s:<5} {seg:6.2f}s  {traza[:70]!r}")
    print(f"\n{len(CASOS) - fallos}/{len(CASOS)} casos correctos")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
