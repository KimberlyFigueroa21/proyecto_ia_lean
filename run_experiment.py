"""Corre las 5 configuraciones sobre un conjunto (reanudable) y muestra el análisis al final.

Dentro del contenedor, con el servidor de verificación en `ready` y GEMINI_API_KEY / GEMINI_MODEL exportadas:
    python3 run_experiment.py --split dev
    python3 run_experiment.py --split dev --configs baseline_a baseline_b      # solo algunas
    python3 run_experiment.py --split test --allow-test --auto-resume          # solo con el código congelado
Cada archivo de salida ya existente se reutiliza: se saltan los problemas ya hechos.

--auto-resume deja la corrida desatendida: si se acaba el tope diario espera al siguiente día del Pacífico
(+5 min) y sigue; si Google responde 503/red, espera 5 min y reintenta (máx. 12 veces seguidas sin avance).
Un fallo del VERIFICADOR sí detiene la corrida (hay que revisar el servidor). Sin la bandera, el runner termina
limpio (código 3 por tope, 2 por fallo de infraestructura) y se vuelve a lanzar a mano.
Orden: de lo más barato a lo más caro, para que el tope diario corte lo menos importante.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from src.api_llm import DailyQuotaExceeded, LLMError, make_llm
from src.baselines import RUNNERS, load_split
from src.logger import JsonlLogger
from src.pipeline import PRESETS, run_pipeline_problem
from src.prompts import PROMPTS_BY_VARIANT
from src.stats import CONFIGS, RAG_CONFIGS, analyze, result_path
from src.verify_client import RemoteVerifier, VerifierUnavailable

ORDER = ["baseline_a", "baseline_b", "sin_critico", "sin_rag", "completo"]
RETRY_SLEEP_S, MAX_STALLS = 300, 12


def done_ids(path: Path) -> set:
    return {json.loads(l)["problem_id"] for l in path.read_text(encoding="utf-8").splitlines() if l.strip()} \
        if path.exists() else set()


def seconds_until_pacific_reset(now_utc: datetime | None = None, margin_min: int = 5) -> int:
    """Segundos hasta 00:05 del siguiente día del Pacífico (cuando el cliente reinicia el contador diario)."""
    from zoneinfo import ZoneInfo
    pac = ZoneInfo("America/Los_Angeles")
    now = (now_utc or datetime.now(ZoneInfo("UTC"))).astimezone(pac)
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=margin_min, second=0, microsecond=0)
    return max(60, int((nxt - now).total_seconds()))


def sleep_log(seconds: int, why: str):
    print(f"\n[{datetime.now():%a %H:%M}] {why}. Espero {seconds // 60} min...", flush=True)
    end = time.time() + seconds
    while time.time() < end:
        time.sleep(min(1800, max(1, end - time.time())))


def run_all(a, wanted, problems, retriever, verifier):
    """Una pasada sobre todas las configuraciones pedidas; lanza las excepciones de infraestructura."""
    llm = make_llm(max_output_tokens=a.max_tokens, thinking_level=None if a.thinking == "none" else a.thinking)
    model = llm.stats["signature"]["model"]
    print(f"Conjunto: {a.split} ({len(problems)})  |  modelo: {model}  |  configuraciones: {', '.join(wanted)}")
    try:
        for c in wanted:
            out = result_path(c, a.split, a.prompt_variant, a.rag_query, a.out_dir)
            out.parent.mkdir(parents=True, exist_ok=True)
            done = done_ids(out)
            todo = [p for p in problems if p["id"] not in done]
            print(f"\n== {c}: {len(done)} ya hechos, {len(todo)} por hacer -> {out.name}", flush=True)
            if c.startswith("baseline_"):
                logger = JsonlLogger(Path(a.out_dir) / "calls.jsonl")
            else:
                logger = JsonlLogger(out.with_name(out.stem + "_agentes.jsonl"))
                cfg = PRESETS[c]
                if cfg.use_rag:
                    cfg = cfg.model_copy(update={"rag_query": a.rag_query})
            for p in todo:
                if c.startswith("baseline_"):
                    rec = RUNNERS[c[-1].upper()](p, llm, verifier, logger)
                    rec["model"] = model
                else:
                    rec = run_pipeline_problem(p, llm, verifier, cfg, logger, model=model,
                                               retriever=retriever if cfg.use_rag else None,
                                               prompts=PROMPTS_BY_VARIANT[a.prompt_variant], variant=a.prompt_variant)
                with out.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                print(f"{'OK   ' if rec['verified'] else 'FALLA'} {p['id']:28s} llamadas {rec['llm_calls']}  "
                      f"{rec['latency_s']}s  {'' if rec['verified'] else rec['trace'][:70].replace(chr(10), ' ')}",
                      flush=True)
    finally:
        print(f"Llamadas reales de hoy: {llm.stats['calls_today']}/{llm.daily_cap}")


def pending(a, wanted, problems) -> int:
    return sum(len([p for p in problems if p["id"] not in done_ids(
        result_path(c, a.split, a.prompt_variant, a.rag_query, a.out_dir))]) for c in wanted)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], required=True)
    ap.add_argument("--configs", nargs="*", choices=CONFIGS, default=None)
    ap.add_argument("--allow-test", action="store_true")
    ap.add_argument("--auto-resume", action="store_true", help="espera al día siguiente / reintenta 503 sola")
    ap.add_argument("--prompt-variant", choices=sorted(PROMPTS_BY_VARIANT), default="v1")
    ap.add_argument("--rag-query", choices=["plan", "lean", "plan+lean", "problem"], default="lean")
    ap.add_argument("--rag-index", default="rag_data/idx2")
    ap.add_argument("--thinking", default="low")
    ap.add_argument("--max-tokens", type=int, default=8192)
    ap.add_argument("--out-dir", default="results")
    a = ap.parse_args()
    if a.split == "test" and not a.allow_test:
        print("El conjunto de prueba solo se corre con el código congelado. Usa --allow-test si es el momento.")
        return 4
    wanted = [c for c in ORDER if c in (a.configs or CONFIGS)]
    problems = load_split(a.split)
    ids = [p["id"] for p in problems]
    retriever = None
    if RAG_CONFIGS & set(wanted):
        from src.retriever import Retriever
        retriever = Retriever(a.rag_index)
        print(f"RAG: {retriever.info['count']} lemas, {retriever.info['model']}, consulta={a.rag_query}")
    verifier = RemoteVerifier()
    code, stalls = 0, 0
    while True:
        before = pending(a, wanted, problems)
        try:
            verifier.wait_ready()
            run_all(a, wanted, problems, retriever, verifier)
            code = 0
            break
        except DailyQuotaExceeded as e:
            print(f"\nTope diario alcanzado: {e}")
            code = 3
            if not a.auto_resume:
                print("Vuelve a ejecutar mañana (se reanuda solo).")
                break
            stalls = 0
            sleep_log(seconds_until_pacific_reset(), "Esperando el reinicio del tope diario")
        except VerifierUnavailable as e:
            print(f"\nFallo del verificador (no es un veredicto): {type(e).__name__}: {e}")
            code = 2
            break
        except LLMError as e:
            print(f"\nFallo de infraestructura (no es un veredicto): {type(e).__name__}: {e}")
            code = 2
            stalls = stalls + 1 if pending(a, wanted, problems) >= before else 0
            if not a.auto_resume or stalls >= MAX_STALLS:
                break
            sleep_log(RETRY_SLEEP_S, f"Reintento {stalls}/{MAX_STALLS} tras el fallo del servicio")
    md, _ = analyze(a.split, a.out_dir, a.prompt_variant, a.rag_query, ids)
    print("\n" + md)
    return code


if __name__ == "__main__":
    sys.exit(main())
