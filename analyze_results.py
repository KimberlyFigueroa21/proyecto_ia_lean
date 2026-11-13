"""Tablas y estadística de las 5 configuraciones (sin llamadas al LLM ni al verificador).

    python3 analyze_results.py --split dev
Escribe results/analysis_<split>.md (tablas) y results/analysis_<split>.csv (problema × configuración).
"""
import argparse
import csv
import json
from pathlib import Path

from src.stats import analyze


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["pilot", "dev", "test"], default="dev")
    ap.add_argument("--variant", default="v1")
    ap.add_argument("--rag-query", default="lean")
    ap.add_argument("--results-dir", default="results")
    a = ap.parse_args()
    ids = None
    if a.split in ("dev", "test"):
        from src.baselines import load_split
        ids = [p["id"] for p in load_split(a.split)]
    md, rows = analyze(a.split, a.results_dir, a.variant, a.rag_query, ids)
    print(md)
    out = Path(a.results_dir)
    (out / f"analysis_{a.split}.md").write_text(md, encoding="utf-8")
    with (out / f"analysis_{a.split}.csv").open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)
    print(f"\nGuardado: {out}/analysis_{a.split}.md y .csv")


if __name__ == "__main__":
    main()
