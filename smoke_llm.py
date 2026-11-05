"""Prueba de humo del cliente LLM (Fase 1). Gasta 1 llamada real; la segunda sale de la caché.

Dentro del contenedor, desde /workspace/proyecto_ia_lean:
    export GEMINI_API_KEY="..."        # solo para esta terminal (no lo pegues en el chat ni en Git)
    python3 smoke_llm.py
"""
import sys

from src.api_llm import LLMError, make_llm


def main() -> int:
    try:
        llm = make_llm(max_output_tokens=2048)
        sig = llm.stats["signature"]
        print(f"Modelo: {sig['model']}  temperatura={sig['temperature']}  tope diario={llm.daily_cap}  rpm={llm.rpm}")
        prompt = "Responde únicamente con la palabra OK."
        r1 = llm.call("smoke", prompt)
        print(f"1.ª llamada (real):  {r1.text.strip()!r}  tokens_in={r1.tokens_in} tokens_out={r1.tokens_out}")
        r2 = llm.call("smoke", prompt)
        print(f"2.ª llamada (caché): {r2.text.strip()!r}  tokens_in={r2.tokens_in} tokens_out={r2.tokens_out}")
        s = llm.stats
        print(f"\nllamadas reales={s['real_calls']}  aciertos de caché={s['cache_hits']}  "
              f"gastadas hoy={s['calls_today']}/{s['daily_cap']}")
        ok = r1 == r2 and s["real_calls"] <= 1 and s["cache_hits"] >= 1
        print("OK" if ok else "REVISAR: la segunda llamada no salió de la caché")
        return 0 if ok else 1
    except LLMError as e:
        print(f"{type(e).__name__}: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
