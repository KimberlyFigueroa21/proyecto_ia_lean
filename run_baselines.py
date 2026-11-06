"""Corre las líneas base A y/o B (reanudable: salta los problemas que ya están en el archivo de salida).

Dentro del contenedor, con el servidor de verificación en estado `ready`:
    python3 run_baselines.py --baseline A            # 5 problemas piloto
    python3 run_baselines.py --baseline B
    python3 run_baselines.py --baseline A --ids mathd_algebra_141
"""
import argparse
import json
import sys
from pathlib import Path

from src.api_llm import DailyQuotaExceeded, LLMError, make_llm
from src.baselines import RUNNERS, load_problems
from src.logger import JsonlLogger
from src.verify_client import RemoteVerifier, VerifierUnavailable


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", choices=["A", "B"], required=True)
    ap.add_argument("--ids", nargs="*", default=None, help="por defecto data/pilot_ids.json")
    ap.add_argument("--thinking", default="low", help="nivel de razonamiento del modelo: low|medium|high|none")
    ap.add_argument("--max-tokens", type=int, default=8192)
    ap.add_argument("--out-dir", default="results")
    a = ap.parse_args()

    ids = a.ids or json.loads(Path("data/pilot_ids.json").read_text())
    problems = load_problems(ids=ids)
    out = Path(a.out_dir) / f"baseline_{a.baseline.lower()}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)["problem_id"] for l in out.read_text(encoding="utf-8").splitlines() if l.strip()} \
        if out.exists() else set()
    logger = JsonlLogger(Path(a.out_dir) / "calls.jsonl")

    verifier = RemoteVerifier()
    try:
        verifier.wait_ready()
        llm = make_llm(max_output_tokens=a.max_tokens,
                       thinking_level=None if a.thinking == "none" else a.thinking)
        for p in problems:
            if p["id"] in done:
                print(f"- {p['id']}: ya hecho, se salta")
                continue
            rec = RUNNERS[a.baseline](p, llm, verifier, logger)
            with out.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            mark = "OK " if rec["verified"] else "FALLA"
            print(f"{mark} {p['id']:28s} tokens {rec['tokens_in']}→{rec['tokens_out']}  {rec['latency_s']}s  "
                  f"{'' if rec['verified'] else rec['trace'][:90].replace(chr(10), ' ')}")
    except DailyQuotaExceeded as e:
        print(f"\nTope diario alcanzado; vuelve a ejecutar mañana (se reanuda solo): {e}")
        return 3
    except (VerifierUnavailable, LLMError) as e:
        print(f"\nFallo de infraestructura (no es un veredicto): {type(e).__name__}: {e}")
        return 2
    rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [r for r in rows if r["problem_id"] in set(ids)]
    n, ok = len(rows), sum(r["verified"] for r in rows)
    print(f"\nBaseline {a.baseline}: {ok}/{n} verificados  |  llamadas reales de hoy: {llm.stats['calls_today']}/{llm.daily_cap}"
          f"  |  tokens totales {sum(r['tokens_in'] for r in rows)}→{sum(r['tokens_out'] for r in rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
