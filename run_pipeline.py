"""Corre el grafo multiagente sobre problemas del dataset (reanudable).

Dentro del contenedor, con el servidor de verificación en estado `ready`:
    python3 run_pipeline.py --split dev --prompt-variant v1        # los 10 problemas de desarrollo
    python3 run_pipeline.py --split dev --prompt-variant v2
    python3 run_pipeline.py --ids mathd_algebra_141                # un solo problema (depurar)
    python3 run_pipeline.py                                        # 5 pilotos
El conjunto de PRUEBA (--split test) solo se corre tras congelar el código y exige --allow-test.
Salidas: results/pipeline_<config>_<split>_<variante>.jsonl (un registro por problema) y
         results/pipeline_<config>_<split>_<variante>_agentes.jsonl (una fila por paso de agente).
"""
import argparse
import json
import sys
from pathlib import Path

from src.api_llm import DailyQuotaExceeded, LLMError, make_llm
from src.baselines import load_problems, load_split
from src.logger import JsonlLogger
from src.pipeline import PRESETS, run_pipeline_problem
from src.prompts import PROMPTS_BY_VARIANT
from src.verify_client import RemoteVerifier, VerifierUnavailable


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", choices=sorted(PRESETS), default="sin_rag_ni_critico")
    ap.add_argument("--split", choices=["pilot", "dev", "test"], default="pilot")
    ap.add_argument("--allow-test", action="store_true", help="necesario para --split test (código congelado)")
    ap.add_argument("--prompt-variant", choices=sorted(PROMPTS_BY_VARIANT), default="v1")
    ap.add_argument("--ids", nargs="*", default=None, help="ids concretos del dataset completo (anula --split)")
    ap.add_argument("--thinking", default="low", help="razonamiento del modelo: low|medium|high|none")
    ap.add_argument("--max-tokens", type=int, default=8192)
    ap.add_argument("--out-dir", default="results")
    ap.add_argument("--rag-index", default="rag_data/idx2", help="carpeta del índice de Mathlib (configs con RAG)")
    ap.add_argument("--rag-query", choices=["plan", "lean", "plan+lean", "problem"], default=None,
                    help="qué se busca en el índice (por defecto el de la configuración: plan)")
    a = ap.parse_args()

    if a.split == "test" and not a.ids and not a.allow_test:
        print("El conjunto de prueba solo se corre con el código congelado. Usa --allow-test si es el momento.")
        return 4
    cfg = PRESETS[a.config]
    if a.rag_query:
        cfg = cfg.model_copy(update={"rag_query": a.rag_query})
    if a.ids:
        problems, split = load_problems(ids=a.ids), "ids"
    elif a.split == "pilot":
        problems, split = load_problems(ids=json.loads(Path("data/pilot_ids.json").read_text())), "pilot"
    else:
        problems, split = load_split(a.split), a.split
    ids = [p["id"] for p in problems]
    stem = f"pipeline_{cfg.name}_{split}_{a.prompt_variant}" + (f"_{cfg.rag_query}" if cfg.use_rag else "")
    out = Path(a.out_dir) / f"{stem}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)["problem_id"] for l in out.read_text(encoding="utf-8").splitlines() if l.strip()} \
        if out.exists() else set()
    logger = JsonlLogger(Path(a.out_dir) / f"{stem}_agentes.jsonl")

    retriever = None
    if cfg.use_rag:
        from src.retriever import Retriever
        retriever = Retriever(a.rag_index)
        print(f"RAG: {retriever.info['count']} lemas, {retriever.info['model']}, consulta={cfg.rag_query}")
    verifier = RemoteVerifier()
    try:
        verifier.wait_ready()
        llm = make_llm(max_output_tokens=a.max_tokens, thinking_level=None if a.thinking == "none" else a.thinking)
        model = llm.stats["signature"]["model"]
        print(f"Config: {cfg.name}  |  conjunto: {split} ({len(problems)})  |  prompts: {a.prompt_variant}  |  "
              f"modelo: {model}  |  rag={cfg.use_rag} critico={cfg.use_critic}")
        for p in problems:
            if p["id"] in done:
                print(f"- {p['id']}: ya hecho, se salta")
                continue
            rec = run_pipeline_problem(p, llm, verifier, cfg, logger, model=model, retriever=retriever,
                                       prompts=PROMPTS_BY_VARIANT[a.prompt_variant], variant=a.prompt_variant)
            with out.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            mark = "OK   " if rec["verified"] else "FALLA"
            print(f"{mark} {p['id']:28s} llamadas {rec['llm_calls']}  tokens {rec['tokens_in']}→{rec['tokens_out']}  "
                  f"{rec['latency_s']}s  "
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
    print(f"\n{stem}: {ok}/{len(rows)} verificados  |  llamadas reales de hoy: "
          f"{llm.stats['calls_today']}/{llm.daily_cap}  |  tokens {sum(r['tokens_in'] for r in rows)}→"
          f"{sum(r['tokens_out'] for r in rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
