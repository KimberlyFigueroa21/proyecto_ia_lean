"""Results explorer for the multi-agent Lean 4 proof system (UPTC Sogamoso).

The Space only READS the saved experiment results (results/*.jsonl). It does not call an LLM
and does not run Lean, so it needs no API key and starts in seconds.
"""
import json
from pathlib import Path

import gradio as gr

import stats

ROOT = Path(__file__).parent
RESULTS = ROOT / "results"
FIG = ROOT / "figures"

CONFIGS = stats.CONFIGS
LABEL = {
    "baseline_a": "Baseline A (single call, verified)",
    "baseline_b": "Baseline B (single call, not verified)",
    "sin_rag": "w/o RAG",
    "sin_critico": "w/o Critic",
    "completo": "Full system",
}
SHORT = {"baseline_a": "Baseline A", "baseline_b": "Baseline B", "sin_rag": "w/o RAG",
         "sin_critico": "w/o Critic", "completo": "Full"}
ERR_EN = {
    "táctica no cierra la meta": "Tactic does not close the goal",
    "uso de sorry/admit": "Uses sorry/admit",
    "alucinación de identificador": "Unknown identifier",
    "sintaxis / formalización": "Syntax / formalization error",
    "tiempo o recursión agotados": "Timeout / recursion limit",
    "tipos / instancias": "Type / instance error",
    "enunciado alterado": "Statement altered",
    "sin tácticas (formalización fallida)": "No tactics (formalization failed)",
    "sin traza": "No trace",
    "otro": "Other",
}

PROBLEMS = {}
for line in (ROOT / "data" / "eval_set.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        p = json.loads(line)
        PROBLEMS[p["id"]] = p

RUNS = {s: {c: stats.load(stats.result_path(c, s, "v1", "lean", RESULTS)) for c in CONFIGS}
        for s in ("dev", "test")}


def ids_of(split):
    return sorted(i for i, p in PROBLEMS.items() if p["split"] == split)


def delivered(rec):
    return bool(rec.get("claimed_correct", rec.get("verified")))


# ---------------------------------------------------------------- summary tab
def summary(split):
    ids = ids_of(split)
    rows = []
    for c in CONFIGS:
        run = RUNS[split][c]
        recs = [run[i] for i in ids if i in run]
        n = len(recs)
        if not n:
            continue
        ok = sum(bool(r["verified"]) for r in recs)
        dl = sum(delivered(r) for r in recs)
        lo, hi = stats.wilson(ok, n)
        rows.append([
            SHORT[c], f"{ok}/{n}", f"{ok / n:.2f}", f"[{lo:.2f}, {hi:.2f}]", dl, dl - ok,
            round(sum(r.get("llm_calls", 0) for r in recs) / n, 1),
            round(sum(r.get("tokens_in", 0) for r in recs) / n / 1000, 1),
        ])
    note = (f"**{split.upper()}** — {len(ids)} problems, one run per configuration. "
            "pass@1 = fraction of problems whose delivered proof Lean accepts. "
            "FP = false positives (delivered as correct but rejected by Lean)."
            + (" The test set was evaluated once, after the code was frozen." if split == "test" else
               " These problems were used to build and tune the system, so they are not comparable with test."))
    return note, rows


SUMMARY_HEADERS = ["Configuration", "Solved", "pass@1", "95% Wilson CI", "Delivered", "FP",
                   "Mean LLM calls", "Mean input tokens (k)"]


# ---------------------------------------------------------------- problem tab
def problem_choices(split):
    ids = ids_of(split)
    solved = {i for i in ids if any(RUNS[split][c].get(i, {}).get("verified") for c in CONFIGS)}
    return [(f"{'✓ ' if i in solved else '· '}{i}", i) for i in ids]


def on_split_change(split):
    ch = problem_choices(split)
    return gr.update(choices=ch, value=ch[0][1])


def problem_view(split, pid):
    p = PROBLEMS[pid]
    diff = {"basico": "basic", "intermedio": "intermediate", "avanzado": "advanced"}.get(p["difficulty"], p["difficulty"])
    head = (f"**{pid}** — difficulty: {diff}, area: {p['area']}, split: {p['split']}\n\n"
            f"{p['statement_nl']}")
    rows = []
    for c in CONFIGS:
        r = RUNS[split][c].get(pid)
        if not r:
            rows.append([SHORT[c], "—", "—", "—", "—"])
            continue
        verdict = "✓ verified" if r["verified"] else ("✗ rejected by Lean" if delivered(r) else "✗ not delivered")
        rows.append([SHORT[c], verdict, "yes" if delivered(r) else "no", r.get("llm_calls", "—"),
                     "—" if r["verified"] else ERR_EN.get(stats.classify_error(r), stats.classify_error(r))])
    return head, p["statement_lean"], rows


def run_view(split, pid, config):
    r = RUNS[split][config].get(pid)
    if not r:
        return "No result for this configuration.", "", "", ""
    used = set(stats.used_lemmas(r))
    info = [f"**{LABEL[config]}** — {'verified by Lean ✓' if r['verified'] else 'not verified ✗'}",
            f"LLM calls: {r.get('llm_calls', '—')} · input tokens: {r.get('tokens_in', '—')} · "
            f"latency: {r.get('latency_s', '—')} s"]
    if "r" in r:
        info.append(f"Replans: {r['r']} · retries on last subgoal: {r['k']} · final status: {r.get('status')}"
                    + (f" ({r['failure_reason']})" if r.get("failure_reason") else ""))
    plan = ""
    if r.get("subgoals"):
        plan = "\n".join(f"{n}. {s}" for n, s in enumerate(r["subgoals"], 1))
    lemmas = ""
    if r.get("retrieved"):
        lemmas = "\n".join(f"{'★ used  ' if n in used else '         '}{n}" for n in r["retrieved"])
    return "\n\n".join(info), r.get("lean_code") or "(no code produced)", r.get("trace") or "(empty)", \
        (("Subgoals:\n" + plan + "\n\n") if plan else "") + (("Retrieved lemmas (★ = appears in final proof):\n" + lemmas) if lemmas else "")


# ---------------------------------------------------------------- UI
ABOUT = """
### What this is
A research prototype for a course project (Inteligencia Computacional, UPTC Sogamoso): six agents
(Planner, Retriever/RAG, Generator, AutoFormalizer, LeanVerifier, Critic) orchestrated with LangGraph that try to
prove 30 miniF2F problems in **Lean 4 / Mathlib**. A proof counts only if the Lean kernel accepts it.

### Main findings (test set, n = 20)
* Very few problems are solved by any configuration (1–3 of 20); differences are at most one problem and **none is
  statistically significant** (exact McNemar with Bonferroni correction).
* Baseline B, which never checks its own proof, delivered 20 proofs and Lean rejected 18 of them (90 %).
  Configurations with the verifier delivered no false proof.
* No correct proof used a lemma retrieved by RAG, so RAG gets no credit in this experiment.
* The Critic/replanning loop costs about 10 LLM calls per problem against 1–3 for the simpler configurations.

### Limitations
Small evaluation set (30 problems), a single model (`gemini-3.5-flash-lite`, free tier) and a single run per
configuration; development-set tuning; possible training-data contamination (miniF2F is public); the error
taxonomy is heuristic. Lean 4.36.0-rc2 with a fixed Mathlib commit. Results describe trends, not general capability.

### Not reproduced here
This Space does not run Lean or call any LLM. To re-run the experiments see the code repository:
https://github.com/KimberlyFigueroa21/proyecto_ia_lean (tag `congelado`).

Authors: Kimberly Natalia Figueroa Zapata, Alisson Páez Alarcón — UPTC Sogamoso.
"""

with gr.Blocks(title="Multi-agent Lean 4 prover — results explorer") as demo:
    gr.Markdown("# Multi-agent generative AI with formal verification in Lean 4\n"
                "Results explorer for the 5 experimental configurations on 30 miniF2F problems.")
    with gr.Tab("Summary"):
        split_s = gr.Radio(["test", "dev"], value="test", label="Problem set")
        note = gr.Markdown()
        table = gr.Dataframe(headers=SUMMARY_HEADERS, interactive=False, wrap=True)
        gr.Markdown("### Figures (test set)")
        with gr.Row():
            gr.Image(str(FIG / "fig_pass_at_1.png"), label="pass@1, delivered vs. verified", show_download_button=False)
            gr.Image(str(FIG / "fig_per_problem.png"), label="Problems solved per configuration", show_download_button=False)
        with gr.Row():
            gr.Image(str(FIG / "fig_cost.png"), label="Cost vs. pass@1", show_download_button=False)
            gr.Image(str(FIG / "fig_errors.png"), label="Failure categories (heuristic)", show_download_button=False)

        def _upd(s):
            n, rows = summary(s)
            return n, rows
        split_s.change(_upd, split_s, [note, table])
        demo.load(_upd, split_s, [note, table])

    with gr.Tab("Problem explorer"):
        gr.Markdown("✓ = solved by at least one configuration.")
        with gr.Row():
            split_p = gr.Radio(["test", "dev"], value="test", label="Problem set")
            init = problem_choices("test")
            prob = gr.Dropdown(init, value=init[0][1], label="Problem")
        head = gr.Markdown()
        lean_stmt = gr.Code(label="Formal statement (Lean 4)", language=None, interactive=False)
        verdicts = gr.Dataframe(headers=["Configuration", "Verdict", "Delivered", "LLM calls", "Failure category"],
                                interactive=False, wrap=True)
        cfg = gr.Dropdown([(LABEL[c], c) for c in CONFIGS], value="completo", label="Inspect configuration")
        info = gr.Markdown()
        code = gr.Code(label="Final Lean proof", language=None, interactive=False)
        with gr.Accordion("Last Lean message", open=False):
            trace = gr.Textbox(show_label=False, lines=8, interactive=False)
        with gr.Accordion("Plan and retrieved lemmas", open=False):
            extra = gr.Textbox(show_label=False, lines=10, interactive=False)

        def _prob(s, p):
            h, st, rows = problem_view(s, p)
            return h, st, rows

        split_p.change(on_split_change, split_p, prob)
        prob.change(_prob, [split_p, prob], [head, lean_stmt, verdicts])
        prob.change(run_view, [split_p, prob, cfg], [info, code, trace, extra])
        cfg.change(run_view, [split_p, prob, cfg], [info, code, trace, extra])
        demo.load(_prob, [split_p, prob], [head, lean_stmt, verdicts])
        demo.load(run_view, [split_p, prob, cfg], [info, code, trace, extra])

    with gr.Tab("System"):
        gr.Markdown("Agents and control flow: PLAN → RETRIEVE → GENERATE → FORMALIZE → VERIFY → "
                    "(CRITIQUE | DONE | FAIL). The Critic can retry a subgoal (k ≤ 3) or replan (r ≤ 1).")
        gr.Image(str(FIG / "arch_graph.png"), show_label=False, show_download_button=False)
        gr.Image(str(FIG / "arch_flow.png"), show_label=False, show_download_button=False)
    with gr.Tab("About"):
        gr.Markdown(ABOUT)

if __name__ == "__main__":
    demo.launch()
