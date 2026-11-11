"""Corre el grafo multiagente sobre problemas del dataset (reanudable).

Dentro del contenedor, con el servidor de verificación en estado `ready`:
    python3 run_pipeline.py                                  # 5 pilotos, config sin_rag_ni_critico
    python3 run_pipeline.py --ids mathd_algebra_141          # un solo problema (depurar)
    python3 run_pipeline.py --config completo                # (cuando existan RAG y Crítico)
Salidas: results/pipeline_<config>.jsonl (un registro por problema) y
         results/pipeline_<config>_agentes.jsonl (una fila por llamada de agente: tokens, latencia, decisión).
"""
import argparse
import json
import sys
from pathlib import Path

from src.api_llm import DailyQuotaExceeded, LLMError, make_llm
from src.baselines import load_problems
from src.logger import JsonlLogger
from src.pipeline import PRESETS, run_pipeline_problem
from src.verify_client import RemoteVerifier, VerifierUnavailable


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", choices=sorted(PRESETS), default="sin_rag_ni_critico")
    ap.add_argument("--ids", nargs="*", default=None, help="por defecto data/pilot_ids.json")
    ap.add_argument("--thinking", default="low", help="razonamiento del modelo: low|medium|high|none")
    ap.add_argument("--max-tokens", type=int, default=8192)
    ap.add_argument("--out-dir", default="results")
    a = ap.parse_args()

    cfg = PRESETS[a.config]
    ids = a.ids or json.loads(Path("data/pilot_ids.json").read_text())
    problems = load_problems(ids=ids)
    out = Path(a.out_dir) / f"pipeline_{cfg.name}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)["problem_id"] for l in out.read_text(encoding="utf-8").splitlines() if l.strip()} \
        if out.exists() else set()
    logger = JsonlLogger(Path(a.out_dir) / f"pipeline_{cfg.name}_agentes.jsonl")

    verifier = RemoteVerifier()
    try:
        verifier.wait_ready()
        llm = make_llm(max_output_tokens=a.max_tokens, thinking_level=None if a.thinking == "none" else a.thinking)
        model = llm.stats["signature"]["model"]
        print(f"Config: {cfg.name}  |  modelo: {model}  |  rag={cfg.use_rag} critico={cfg.use_critic}")
        for p in problems:
            if p["id"] in done:
                print(f"- {p['id']}: ya hecho, se salta")
                continue
            rec = run_pipeline_problem(p, llm, verifier, cfg, logger, model=model)
            with out.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            mark = "OK   " if rec["verified"] else "FALLA"
            print(f"{mark} {p['id']:28s} llamadas {rec['llm_calls']}  tokens {rec['tokens_in']}→{rec['tokens_out']}  "
                  f"{rec['latency_s']}s  pasos {len(rec['subgoals'])}  "
                  f"{'' if rec['verified'] else rec['trace'][:80].replace(chr(10), ' ')}")
    except DailyQuotaExceeded as e:
        print(f"\nTope diario alcanzado; vuelve a ejecutar mañana (se reanuda solo): {e}")
        return 3
    except (VerifierUnavailable, LLMError) as e:
        print(f"\nFallo de infraestructura (no es un veredicto): {type(e).__name__}: {e}")
        return 2
    rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [r for r in rows if r["problem_id"] in set(ids)]
    ok = sum(r["verified"] for r in rows)
    print(f"\n{cfg.name}: {ok}/{len(rows)} verificados  |  llamadas reales de hoy: "
          f"{llm.stats['calls_today']}/{llm.daily_cap}  |  tokens {sum(r['tokens_in'] for r in rows)}→"
          f"{sum(r['tokens_out'] for r in rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
