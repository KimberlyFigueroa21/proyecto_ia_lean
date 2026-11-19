"""Builds data.json for the static Space from the saved results (stdlib only)."""
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import stats
src = Path(sys.argv[1]); out = Path(sys.argv[2])
ERR = {"táctica no cierra la meta": "Tactic does not close the goal", "uso de sorry/admit": "Uses sorry/admit",
       "alucinación de identificador": "Unknown identifier", "sintaxis / formalización": "Syntax / formalization error",
       "tiempo o recursión agotados": "Timeout / recursion limit", "tipos / instancias": "Type / instance error",
       "enunciado alterado": "Statement altered", "sin tácticas (formalización fallida)": "No tactics (formalization failed)",
       "sin traza": "No trace", "otro": "Other"}
DIFF = {"basico": "basic", "intermedio": "intermediate", "avanzado": "advanced"}
probs = [json.loads(l) for l in (src / "data/eval_set.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
data = {"problems": [], "runs": {}, "summary": {}}
for p in probs:
    data["problems"].append({"id": p["id"], "split": p["split"], "difficulty": DIFF[p["difficulty"]], "area": p["area"],
                             "nl": p["statement_nl"], "lean": p["statement_lean"]})
for s in ("dev", "test"):
    ids = sorted(p["id"] for p in probs if p["split"] == s)
    data["runs"][s] = {}; data["summary"][s] = []
    for c in stats.CONFIGS:
        run = stats.load(stats.result_path(c, s, "v1", "lean", src / "results"))
        recs = [run[i] for i in ids if i in run]
        n = len(recs); ok = sum(bool(r["verified"]) for r in recs)
        dl = sum(bool(r.get("claimed_correct", r.get("verified"))) for r in recs)
        lo, hi = stats.wilson(ok, n)
        data["summary"][s].append({"config": c, "solved": ok, "n": n, "lo": round(lo, 2), "hi": round(hi, 2), "delivered": dl,
            "fp": dl - ok, "calls": round(sum(r.get("llm_calls", 0) for r in recs) / n, 1),
            "tok": round(sum(r.get("tokens_in", 0) for r in recs) / n / 1000, 1)})
        data["runs"][s][c] = {}
        for i, r in run.items():
            used = set(stats.used_lemmas(r))
            data["runs"][s][c][i] = {
                "verified": bool(r["verified"]), "delivered": bool(r.get("claimed_correct", r.get("verified"))),
                "calls": r.get("llm_calls"), "tok": r.get("tokens_in"), "lat": r.get("latency_s"),
                "err": None if r["verified"] else ERR.get(stats.classify_error(r), stats.classify_error(r)),
                "code": r.get("lean_code") or "", "trace": (r.get("trace") or "")[:4000],
                "subgoals": r.get("subgoals") or [], "lemmas": [[n, n in used] for n in (r.get("retrieved") or [])],
                "r": r.get("r"), "k": r.get("k"), "status": r.get("status"), "reason": r.get("failure_reason")}
out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(out.stat().st_size, "bytes")
