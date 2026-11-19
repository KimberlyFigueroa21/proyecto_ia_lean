"""Genera tablas LaTeX, figuras (PDF+PNG) y el borrador de Results a partir de results/*.jsonl.
Todas las cifras salen de src/stats.py (las mismas funciones que analyze_results.py)."""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(sys.argv[1])
OUT = Path(sys.argv[2])
sys.path.insert(0, str(ROOT))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from src.stats import (COMPARISONS, CONFIGS, bootstrap_diff, classify_error, load, mcnemar_exact, result_path,
                       used_lemmas, wilson)

(OUT / "figures").mkdir(parents=True, exist_ok=True)
(OUT / "tables").mkdir(parents=True, exist_ok=True)

EN = {"baseline_a": "Baseline A", "baseline_b": "Baseline B", "sin_rag": "w/o RAG", "sin_critico": "w/o Critic",
      "completo": "Full"}
ERR_EN = {"táctica no cierra la meta": "Tactic does not close goal", "alucinación de identificador": "Unknown identifier",
          "uso de sorry/admit": "Use of sorry/admit", "sintaxis / formalización": "Syntax / formalization",
          "tipos / instancias": "Type / instance error", "tiempo o recursión agotados": "Timeout / recursion limit",
          "otro": "Other", "sin traza": "No trace", "sin tácticas (formalización fallida)": "Empty answer"}
SH = {"baseline_a": "Base A", "baseline_b": "Base B", "sin_rag": "w/o RAG", "sin_critico": "w/o Crit.", "completo": "Full"}
ERR_SH = {"táctica no cierra la meta": "Tactic fails", "alucinación de identificador": "Unknown ident.", "uso de sorry/admit": "sorry/admit", "sintaxis / formalización": "Syntax/formal.", "tipos / instancias": "Type/instance", "tiempo o recursión agotados": "Timeout/recursion", "otro": "Other"}
DIFF_ORDER = ["basico", "intermedio", "avanzado"]
DIFF_EN = {"basico": "Basic", "intermedio": "Intermediate", "avanzado": "Advanced"}
AREA_EN = {"algebra": "Algebra", "conteo": "Counting", "teoria_de_numeros": "Number theory"}

rows = [json.loads(l) for l in open(ROOT / "data/eval_set.jsonl", encoding="utf-8") if l.strip()]
IDS = {s: [r["id"] for r in rows if r["split"] == s] for s in ("dev", "test")}
META = {r["id"]: r for r in rows}
R = {s: {c: load(result_path(c, s, "v1", "lean", ROOT / "results")) for c in CONFIGS} for s in ("dev", "test")}
for s in R:
    for c in CONFIGS:
        assert set(R[s][c]) == set(IDS[s]), (s, c)

# ---------------- cifras ----------------
def stats(s, c):
    v = [R[s][c][i] for i in IDS[s]]
    n, ok = len(v), sum(x["verified"] for x in v)
    claimed = sum(bool(x.get("claimed_correct", x["verified"])) for x in v)
    fp = sum(bool(x.get("claimed_correct", x["verified"])) and not x["verified"] for x in v)
    okr = [x for x in v if x["verified"]]
    first = sum(1 for x in okr if x["llm_calls"] <= 3)
    return dict(n=n, ok=ok, ci=wilson(ok, n), claimed=claimed, fp=fp,
                calls=sum(x["llm_calls"] for x in v) / n, tin=sum(x["tokens_in"] for x in v) / n,
                tout=sum(x["tokens_out"] for x in v) / n, first=first, rescued=len(okr) - first,
                replan=sum(1 for x in v if (x.get("r") or 0) >= 1),
                lemma=[x["problem_id"] for x in okr if used_lemmas(x)], nlemma_ok=len(okr),
                solved=[x["problem_id"] for x in okr], fails=[x for x in v if not x["verified"]])


S = {s: {c: stats(s, c) for c in CONFIGS} for s in ("dev", "test")}
T, D = S["test"], S["dev"]
f2 = lambda x: f"{x:.2f}"
tex = lambda s: s.replace("_", r"\_").replace("%", r"\%")

# paired comparisons (test)
PAIRS = []
m = sum(1 for a, b in COMPARISONS)
for a, b in COMPARISONS:
    x = [int(R["test"][a][i]["verified"]) for i in IDS["test"]]
    y = [int(R["test"][b][i]["verified"]) for i in IDS["test"]]
    bb = sum(1 for p, q in zip(x, y) if p and not q)
    cc = sum(1 for p, q in zip(x, y) if q and not p)
    p = mcnemar_exact(bb, cc)
    d, lo, hi = bootstrap_diff(x, y)
    PAIRS.append(dict(a=a, b=b, only_a=bb, only_b=cc, d=d, lo=lo, hi=hi, p=p, padj=min(1.0, p * m)))

# ---------------- tablas LaTeX ----------------
def wtable(name, caption, label, header, body, colspec, star=False):
    env = "table*" if star else "table"
    lines = [rf"\begin{{{env}}}[t]", r"\centering", r"\caption{" + caption + "}", r"\label{" + label + "}", r"\footnotesize", r"\setlength{\tabcolsep}{3pt}",
             r"\begin{tabular}{" + colspec + "}", r"\hline", " & ".join(header) + r" \\", r"\hline"]
    lines += [" & ".join(str(c) for c in r) + r" \\" for r in body]
    lines += [r"\hline", r"\end{tabular}", rf"\end{{{env}}}"]
    (OUT / "tables" / f"{name}.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return "\n".join(lines)


body = []
for c in CONFIGS:
    t, d = T[c], D[c]
    body.append([EN[c], f"{d['ok']}/{d['n']}", f"{t['ok']}/{t['n']}", f"[{f2(t['ci'][0])}, {f2(t['ci'][1])}]",
                 t["claimed"], t["fp"], f"{t['calls']:.1f}"])
TAB_MAIN = wtable("main", r"pass@1 on the development (10) and test (20) problems. The 95\% Wilson interval refers to test. "
                  r"``Delivered'' is the number of proofs the system presents as correct; false positives (FP) are delivered "
                  r"proofs that Lean rejects. Calls = mean LLM calls per test problem.", "tab:main",
                  ["Config.", "Dev", "Test", "95\\% CI", "Deliv.", "FP", "Calls"], body, "lccccrr")

body = [[f"{EN[p['a']]} vs.\\ {EN[p['b']]}", p["only_a"], p["only_b"], f"{p['d']:+.2f} [{p['lo']:+.2f}, {p['hi']:+.2f}]",
         f"{p['padj']:.3f}"] for p in PAIRS]
TAB_PAIRS = wtable("pairs", r"Paired comparisons on the test set. ``Only 1st / 2nd'' counts problems solved by only one "
                   r"configuration; $\Delta$ is the difference in pass@1 with a 95\% bootstrap interval; $p$ is the exact McNemar "
                   rf"test with Bonferroni correction ($\times${m}).", "tab:pairs",
                   ["Comparison", "Only 1st", "Only 2nd", "$\\Delta$ pass@1 [95\\% CI]", "$p_{\\mathrm{adj}}$"], body, "lcccc", star=True)

body = []
for split, title in (("dev", "Development"), ("test", "Test")):
    body.append([(r"\hline" + "\n" if split == "test" else "") + r"\multicolumn{7}{l}{\textit{" + title + "}}"])
    for key, order, names in (("difficulty", DIFF_ORDER, DIFF_EN), ("area", sorted(AREA_EN), AREA_EN)):
        for v in order:
            ids = [i for i in IDS[split] if META[i][key] == v]
            body.append([names[v], len(ids)] + [sum(R[split][c][i]["verified"] for i in ids) for c in CONFIGS])
TAB_STRATA = wtable("strata", r"Problems solved by difficulty and by area, on the development and test sets ($n$ = problems in each "
                    r"stratum). The difficulty rows and the area rows count the same problems from two angles, so they are not added together.",
                    "tab:strata", ["Stratum", "$n$"] + [SH[c] for c in CONFIGS], body, "lcccccc")

body = [[EN[c], T[c]["first"], T[c]["rescued"], T[c]["replan"],
         (f"{len(T[c]['lemma'])}/{T[c]['nlemma_ok']}" if c in ("sin_critico", "completo") else "--")]
        for c in ("sin_rag", "sin_critico", "completo")]
TAB_CRIT = wtable("critic", r"Contribution of the Critic and of RAG on the test set. A problem is solved at the first attempt if it "
                  r"needed the minimum of three LLM calls (Planner, Generator, AutoFormalizer); more calls imply retries or "
                  r"replanning. The last column counts correct proofs that contain a retrieved lemma.", "tab:critic",
                  ["Config.", "1st att.", "Retry", "Replan", "Lemma used"], body, "lcccc")

cats = []
cnt = {}
for c in CONFIGS:
    cnt[c] = Counter(classify_error(x) for x in T[c]["fails"])
    cats += [k for k in cnt[c] if k not in cats]
cats.sort(key=lambda k: -sum(cnt[c][k] for c in CONFIGS))
body = [[ERR_SH.get(k, ERR_EN.get(k, k))] + [cnt[c][k] for c in CONFIGS] for k in cats]
body.append([r"\textbf{Failed problems}"] + [len(T[c]["fails"]) for c in CONFIGS])
TAB_ERR = wtable("errors", r"Failure taxonomy on the test set (heuristic classification of the last Lean message of each failed "
                 r"problem).", "tab:errors", ["Category"] + [SH[c] for c in CONFIGS], body, "lccccc")

# ---------------- figuras ----------------
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#d9d8d4"
COL = {"baseline_a": "#2a78d6", "baseline_b": "#eb6834", "sin_rag": "#1baf7a", "sin_critico": "#eda100", "completo": "#e87ba4"}
HATCH = {"baseline_a": "", "baseline_b": "///", "sin_rag": "\\\\\\", "sin_critico": "...", "completo": "xxx"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": INK, "ytick.color": INK, "axes.spines.top": False, "axes.spines.right": False,
                     "pdf.fonttype": 42, "savefig.dpi": 300})
LAB = {c: EN[c].replace("w/o ", "w/o\n").replace("Baseline ", "Baseline\n") for c in CONFIGS}
LAB["completo"] = "Full\n"


def save(fig, name):
    fig.savefig(OUT / "figures" / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(OUT / "figures" / f"{name}.png", bbox_inches="tight", dpi=300)
    plt.close(fig)


# Fig 1: pass@1 con IC + entregadas vs verificadas
fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.16, 2.5), gridspec_kw={"wspace": 0.28})
x = np.arange(len(CONFIGS))
for i, c in enumerate(CONFIGS):
    t, d = T[c], D[c]
    p = t["ok"] / t["n"]
    a1.bar(i, p, 0.62, color=COL[c], hatch=HATCH[c], edgecolor=INK, linewidth=0.5, zorder=2)
    a1.errorbar(i, p, yerr=[[p - t["ci"][0]], [t["ci"][1] - p]], color=INK, capsize=2.5, lw=0.9, zorder=3)
    a1.text(i, t["ci"][1] + 0.015, f"{t['ok']}/{t['n']}", ha="center", va="bottom", fontsize=7, color=INK)
    a1.plot(i, d["ok"] / d["n"], marker="D", ms=4.5, mfc="white", mec=INK, mew=0.9, ls="none", zorder=4)
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
h1 = [Line2D([], [], marker="D", ms=4.5, mfc="white", mec=INK, mew=0.9, ls="none", label="Dev (10 problems)"),
      Patch(facecolor="#cccccc", edgecolor=INK, linewidth=0.5, label="Test (20 problems), 95% Wilson CI")]
a1.set_xticks(x, [LAB[c] for c in CONFIGS]); a1.set_ylim(0, 0.95); a1.set_ylabel("pass@1")
a1.yaxis.grid(True, color=GRID, lw=0.5, zorder=0); a1.set_axisbelow(True)
a1.legend(handles=h1, frameon=False, loc="upper left", fontsize=6.5, handlelength=1.2)
a1.set_title("(a) pass@1", loc="left", fontsize=7.5)
w = 0.36
for i, c in enumerate(CONFIGS):
    t = T[c]
    a2.bar(i - w / 2, t["claimed"], w, color="white", edgecolor=INK, linewidth=0.8, hatch="////", zorder=2)
    a2.bar(i + w / 2, t["ok"], w, color=COL[c], edgecolor=INK, linewidth=0.5, zorder=2)
    a2.text(i - w / 2, t["claimed"] + 0.4, str(t["claimed"]), ha="center", va="bottom", fontsize=7)
    a2.text(i + w / 2, t["ok"] + 0.4, str(t["ok"]), ha="center", va="bottom", fontsize=7)
h2 = [Patch(facecolor="white", edgecolor=INK, hatch="////", label="Delivered as correct"),
      Patch(facecolor="#bbbbbb", edgecolor=INK, linewidth=0.5, label="Verified by Lean")]
a2.set_xticks(x, [LAB[c] for c in CONFIGS]); a2.set_ylim(0, 24); a2.set_ylabel("Test problems (of 20)")
a2.yaxis.grid(True, color=GRID, lw=0.5, zorder=0); a2.set_axisbelow(True)
a2.legend(handles=h2, frameon=False, loc="upper right", fontsize=6.5, handlelength=1.2)
a2.set_title("(b) Delivered vs. verified", loc="left", fontsize=7.5)
a2.annotate(f"{T['baseline_b']['fp']} false\npositives", xy=(1 - w / 2, 20), xytext=(1.75, 12.5), fontsize=6.5, color=INK,
            arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6), va="center")
save(fig, "fig_pass_at_1")

# Fig 2: matriz por problema (test)
order = sorted(IDS["test"], key=lambda i: (DIFF_ORDER.index(META[i]["difficulty"]), META[i]["area"], i))
M = np.array([[1 if R["test"][c][i]["verified"] else 0 for i in order] for c in CONFIGS])
fig, ax = plt.subplots(figsize=(7.16, 2.5))
ax.imshow(M, aspect="auto", cmap=LinearSegmentedColormap.from_list("b", ["#ecebe7", "#2a78d6"]), vmin=0, vmax=1)
ax.set_xticks(range(len(order)), [i.replace("_", " ") for i in order], rotation=60, ha="right", fontsize=6)
ax.set_yticks(range(len(CONFIGS)), [EN[c] for c in CONFIGS])
for r in range(len(CONFIGS)):
    for k in range(len(order)):
        ax.text(k, r, "✓" if M[r, k] else "", ha="center", va="center", color="white", fontsize=8, fontweight="bold")
ax.set_xticks(np.arange(-.5, len(order), 1), minor=True); ax.set_yticks(np.arange(-.5, len(CONFIGS), 1), minor=True)
ax.grid(which="minor", color="white", lw=1.5); ax.tick_params(which="both", length=0)
for s in ax.spines.values():
    s.set_visible(False)
edges, start = [], 0
for d in DIFF_ORDER:
    k = sum(1 for i in order if META[i]["difficulty"] == d)
    edges.append((d, start, start + k)); start += k
for d, a, b in edges:
    ax.text((a + b - 1) / 2, -0.85, DIFF_EN[d], ha="center", va="bottom", fontsize=7, color=INK, fontweight="bold")
    if a > 0:
        ax.axvline(a - 0.5, color=INK, lw=0.9)
save(fig, "fig_per_problem")

# Fig 3: costo vs pass@1
fig, ax = plt.subplots(figsize=(3.5, 2.5))
off = {"baseline_a": (6, -9), "baseline_b": (6, 5), "sin_rag": (-6, 7), "sin_critico": (6, -9), "completo": (6, -9)}
ha = {"baseline_a": "left", "baseline_b": "left", "sin_rag": "right", "sin_critico": "left", "completo": "left"}
for c in CONFIGS:
    t = T[c]
    p = t["ok"] / t["n"]
    ax.errorbar(t["calls"], p, yerr=[[p - t["ci"][0]], [t["ci"][1] - p]], fmt="o", ms=6, color=COL[c], mec=INK, mew=0.7,
                ecolor=MUTED, elinewidth=0.8, capsize=2, zorder=3)
    ax.annotate(EN[c], (t["calls"], p), xytext=off[c], textcoords="offset points", fontsize=7, ha=ha[c], color=INK)
ax.set_xscale("log"); ax.set_xticks([1, 2, 3, 5, 10]); ax.set_xticklabels(["1", "2", "3", "5", "10"])
ax.set_xlabel("Mean LLM calls per problem (log scale)"); ax.set_ylabel("pass@1 (test), 95% Wilson CI")
ax.set_ylim(-0.02, 0.42); ax.yaxis.grid(True, color=GRID, lw=0.5, zorder=0); ax.set_axisbelow(True)
save(fig, "fig_cost")

# Fig 4: taxonomía (mapa de calor secuencial)
Mx = np.array([[cnt[c][k] for c in CONFIGS] for k in cats])
fig, ax = plt.subplots(figsize=(3.5, 2.5))
ax.imshow(Mx, aspect="auto", cmap=LinearSegmentedColormap.from_list("s", ["#f1f6fd", "#9cc3f0", "#1f5aa6"]), vmin=0, vmax=max(6, Mx.max()))
ax.set_xticks(range(len(CONFIGS)), [LAB[c] for c in CONFIGS]); ax.xaxis.tick_top()
ax.set_yticks(range(len(cats)), [ERR_EN.get(k, k) for k in cats])
for r in range(len(cats)):
    for k in range(len(CONFIGS)):
        ax.text(k, r, str(Mx[r, k]), ha="center", va="center", fontsize=7.5,
                color="white" if Mx[r, k] >= 0.6 * max(6, Mx.max()) else INK)
ax.set_xticks(np.arange(-.5, len(CONFIGS), 1), minor=True); ax.set_yticks(np.arange(-.5, len(cats), 1), minor=True)
ax.grid(which="minor", color="white", lw=1.5); ax.tick_params(which="both", length=0)
for s in ax.spines.values():
    s.set_visible(False)
save(fig, "fig_errors")

# ---------------- valores para el texto ----------------
solved_all = sorted({i for c in CONFIGS for i in T[c]["solved"]})
dev_solved_all = sorted({i for c in CONFIGS for i in D[c]["solved"]})
who = {i: [EN[c] for c in CONFIGS if i in T[c]["solved"]] for i in solved_all}
dev_rescued = {c: [x["problem_id"] for x in R["dev"][c].values() if x["verified"] and x["llm_calls"] > 3] for c in CONFIGS}
test_rescued = {c: [x["problem_id"] for x in R["test"][c].values() if x["verified"] and x["llm_calls"] > 3] for c in CONFIGS}
V = dict(T=T, D=D, PAIRS=PAIRS, solved_all=solved_all, dev_solved_all=dev_solved_all, who=who, dev_rescued=dev_rescued, test_rescued=test_rescued, m=m,
         cats=cats, cnt={c: dict(cnt[c]) for c in CONFIGS},
         difficulty={d: len([i for i in IDS["test"] if META[i]["difficulty"] == d]) for d in DIFF_ORDER},
         difficulty_dev={d: len([i for i in IDS["dev"] if META[i]["difficulty"] == d]) for d in DIFF_ORDER})
json.dump(V, open(OUT / "values.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=lambda o: list(o))
print(json.dumps({k: V[k] for k in ("solved_all", "who", "dev_rescued", "test_rescued", "difficulty", "difficulty_dev")},
                 ensure_ascii=False, indent=1))
for c in CONFIGS:
    t = T[c]
    print(c, t["ok"], t["n"], [round(z, 2) for z in t["ci"]], "claimed", t["claimed"], "fp", t["fp"], "calls", round(t["calls"], 2),
          "tin", round(t["tin"]), "tout", round(t["tout"]), "first", t["first"], "resc", t["rescued"], "replan", t["replan"],
          "lemma", t["lemma"])
for p in PAIRS:
    print(p["a"], p["b"], p["only_a"], p["only_b"], round(p["d"], 2), round(p["lo"], 2), round(p["hi"], 2), round(p["p"], 3))
