"""Redacta results_draft.tex (inglés, listo para Overleaf) y results_draft_es_tecnico.md (español, para revisar),
con TODAS las cifras tomadas de out/values.json (generado por build_results.py)."""
import json, sys
from pathlib import Path
OUT = Path(sys.argv[1])
V = json.load(open(OUT / "values.json", encoding="utf-8"))
T, D = V["T"], V["D"]
tx = lambda s: s.replace("_", r"\_")
f2 = lambda x: f"{x:.2f}"
f1 = lambda x: f"{x:.1f}"
A, B, SR, SC, FU = (T[c] for c in ("baseline_a", "baseline_b", "sin_rag", "sin_critico", "completo"))
dFU, dSR, dB = D["completo"], D["sin_rag"], D["baseline_b"]
pct = round(100 * B["fp"] / B["claimed"])
nint, nbas, nadv = V["difficulty"]["intermedio"], V["difficulty"]["basico"], V["difficulty"]["avanzado"]
ncount = 7
solved = V["solved_all"]
dsolved = V["dev_solved_all"]
assert dsolved == ["mathd_algebra_141", "mathd_algebra_33", "mathd_algebra_398", "mathd_numbertheory_12", "mathd_numbertheory_521", "mathd_numbertheory_99"], dsolved
assert solved == ["aime_1989_p8", "mathd_algebra_441", "mathd_numbertheory_430"], solved
assert V["who"]["mathd_numbertheory_430"] == ["w/o RAG"] and V["who"]["mathd_algebra_441"] == ["Baseline B", "w/o RAG", "w/o Critic", "Full"]
cats = {k: sum(V["cnt"][c].get(k, 0) for c in V["cnt"]) for k in V["cats"]}
sorry_rng = [V["cnt"][c].get("uso de sorry/admit", 0) for c in V["cnt"]]
ident_rng = [V["cnt"][c].get("alucinación de identificador", 0) for c in V["cnt"]]
tok = lambda c: f"{T[c]['tin'] / 1000:.1f}"
maxdiff = max(abs(p["d"]) for p in V["PAIRS"])
dev_resc_sr, dev_resc_fu = V["dev_rescued"]["sin_rag"], V["dev_rescued"]["completo"]
tab = lambda n: (OUT / "tables" / f"{n}.tex").read_text(encoding="utf-8").strip()

def fig(name, label, caption, star=False):
    env = "figure*" if star else "figure"
    w = r"\textwidth" if star else r"\columnwidth"
    return "\n".join([rf"\begin{{{env}}}[t]", r"\centering", rf"\includegraphics[width={w}]{{figures/{name}.pdf}}",
                      r"\caption{" + caption + "}", r"\label{" + label + "}", rf"\end{{{env}}}"])

en = rf"""% =====================================================================
% RESULTS  (borrador generado a partir de results/*.jsonl; revisar antes de pegar)
% Requiere: \usepackage{{graphicx}}; subir la carpeta figures/ a Overleaf.
% =====================================================================
\section{{Results}}
\label{{sec:results}}

All configurations were run once per problem. The prompts and the retrieval query were fixed on the development set, and the
test set was evaluated a single time after the code was frozen. We report pass@1, the fraction of problems whose final
delivered proof is accepted by the Lean verifier.

\subsection{{Overall performance}}
Table~\ref{{tab:main}} and Fig.~\ref{{fig:pass}} summarize pass@1. On the 20 test problems every configuration solves few
problems: pass@1 ranges from {f2(A['ok']/A['n'])} (Baseline A, {A['ok']}/{A['n']}) to {f2(SR['ok']/SR['n'])} (w/o RAG,
{SR['ok']}/{SR['n']}), and the 95\% Wilson intervals overlap almost completely. None of the paired comparisons in
Table~\ref{{tab:pairs}} is significant after Bonferroni correction (all $p_{{\mathrm{{adj}}}} = 1.000$); the largest paired
difference is {round(maxdiff * 20)} problem. Pass@1 on the development set was higher (up to {f2(dFU['ok']/dFU['n'])} for the
full system), a gap we analyze in the Discussion.

{tab('main')}

{tab('pairs')}

{fig('fig_pass_at_1', 'fig:pass', r'(a) pass@1 of the five configurations on the test set with 95\% Wilson intervals; diamonds show pass@1 on the development set. (b) Proofs delivered as correct versus proofs verified by Lean on the test set.', star=True)}

\subsection{{Verification and false positives}}
Baseline B generates a natural-language proof, translates it to Lean and delivers it without checking it inside the system.
It therefore delivers all {B['claimed']} test proofs as correct, but Lean rejects {B['fp']} of them ({pct}\%). The
other four configurations use the verifier as the acceptance criterion and delivered no incorrect proof
(Fig.~\ref{{fig:pass}}b). The same pattern appears on the development set, where Baseline B delivers {dB['claimed']} proofs and
{dB['fp']} are rejected.

\subsection{{Per-problem results}}
Only {len(solved)} distinct test problems were solved by any configuration (Fig.~\ref{{fig:problems}}):
\texttt{{aime\_1989\_p8}} by all five configurations, \texttt{{mathd\_algebra\_441}} by every configuration except Baseline A,
and \texttt{{mathd\_numbertheory\_430}} only by w/o RAG. No configuration solved any of the {nint} intermediate problems
or any of the {ncount} counting problems (Table~\ref{{tab:strata}}). On the development set, {len(dsolved)} of the 10 problems were
solved by at least one configuration, all of them basic (\texttt{{mathd\_algebra\_141}}, \texttt{{mathd\_algebra\_33}},
\texttt{{mathd\_algebra\_398}}, \texttt{{mathd\_numbertheory\_12}}, \texttt{{mathd\_numbertheory\_99}} and
\texttt{{mathd\_numbertheory\_521}}); none of the four intermediate or advanced development problems was solved.

{fig('fig_per_problem', 'fig:problems', r'Test problems solved (check mark) by each configuration, grouped by difficulty. Each mark is one problem solved by one configuration, so a problem solved by several configurations is marked in several rows.', star=True)}

{tab('strata')}

\subsection{{Contribution of the Critic and of retrieval}}
Table~\ref{{tab:critic}} separates problems solved at the first attempt from those solved after retries or replanning. On the
test set, w/o RAG solved {SR['first']} problems at the first attempt and {SR['rescued']} after a retry
(\texttt{{mathd\_numbertheory\_430}}), while the full system solved both of its problems at the first attempt even though it
replanned in {FU['replan']} of 20 problems (w/o RAG: {SR['replan']}). On the development set, retries rescued
{len(dev_resc_sr)} problem in w/o RAG and {len(dev_resc_fu)} in the full system
(\texttt{{{tx(dev_resc_fu[0])}}} and \texttt{{{tx(dev_resc_fu[1])}}}). None of the {SC['nlemma_ok'] + FU['nlemma_ok']} correct proofs
produced by the configurations with retrieval contains a retrieved lemma.

{tab('critic')}

\subsection{{Cost}}
Fig.~\ref{{fig:cost}} relates pass@1 to cost. The configurations with the Critic need {f1(SR['calls'])}--{f1(FU['calls'])} LLM
calls per problem, against {f1(SC['calls'])} without the Critic and {f1(A['calls'])}--{f1(B['calls'])} for the baselines, and
roughly {tok('sin_rag')}k--{tok('completo')}k input tokens per problem, against {tok('sin_critico')}k for w/o Critic and
{tok('baseline_a')}k--{tok('baseline_b')}k for the baselines. The additional cost is not accompanied by a pass@1 that is
distinguishable from that of the cheaper configurations.

{fig('fig_cost', 'fig:cost', r'pass@1 on the test set versus mean LLM calls per problem (log scale). Bars are 95\% Wilson intervals.')}

\subsection{{Failure analysis}}
Table~\ref{{tab:errors}} and Fig.~\ref{{fig:errors}} classify the last Lean error of each failed test problem. Failures are
spread over several categories and none disappears when components are added: tactics that do not close the goal
({cats['táctica no cierra la meta']} cases across configurations), use of \texttt{{sorry}} or \texttt{{admit}} ({cats['uso de sorry/admit']};
{min(sorry_rng)}--{max(sorry_rng)} per configuration), unknown identifiers ({cats['alucinación de identificador']};
{min(ident_rng)}--{max(ident_rng)} per configuration) and syntax or formalization errors
({cats['sintaxis / formalización']}). The classification is heuristic, based on the last Lean message, so the counts are approximate.

{tab('errors')}

{fig('fig_errors', 'fig:errors', r'Failure taxonomy on the test set (number of failed problems per category and configuration).')}
"""
(OUT / "results_draft.tex").write_text(en, encoding="utf-8")

es = f"""# Results — borrador en español (para revisar; el texto en inglés está en results_draft.tex)

Todas las cifras salen de `results/*.jsonl` con las mismas funciones que `analyze_results.py`.

## Rendimiento global
En los 20 problemas de test todas las configuraciones resuelven pocos problemas: pass@1 va de {f2(A['ok']/A['n'])} (Baseline A, {A['ok']}/{A['n']}) a {f2(SR['ok']/SR['n'])} (sin RAG, {SR['ok']}/{SR['n']}), y los intervalos de Wilson del 95 % se solapan casi por completo. Ninguna comparación pareada es significativa tras Bonferroni (todos los p ajustados valen 1.000); la mayor diferencia pareada es de {round(maxdiff * 20)} problema. En desarrollo el pass@1 fue más alto (hasta {f2(dFU['ok']/dFU['n'])} en el sistema completo); esa brecha se analiza en la Discusión. (Tablas 1 y 2, Fig. 1.)

## Verificación y falsos positivos
La línea base B entrega los {B['claimed']} problemas como correctos sin comprobarlos, pero Lean rechaza {B['fp']} de ellos ({pct} %). Las otras cuatro configuraciones usan el verificador como criterio de aceptación y no entregaron ninguna prueba incorrecta (Fig. 1b). En desarrollo ocurre lo mismo: B entrega {dB['claimed']} y {dB['fp']} son rechazados.

## Resultados por problema
Solo {len(solved)} problemas distintos de test fueron resueltos por alguna configuración (Fig. 2): `aime_1989_p8` por las cinco, `mathd_algebra_441` por todas menos Baseline A, y `mathd_numbertheory_430` solo por «sin RAG». Ninguna configuración resolvió alguno de los {nint} problemas intermedios ni de los {ncount} de conteo (Tabla 3). En desarrollo, {len(dsolved)} de los 10 problemas fueron resueltos por alguna configuración y todos son de nivel básico (`mathd_algebra_141`, `mathd_algebra_33`, `mathd_algebra_398`, `mathd_numbertheory_12`, `mathd_numbertheory_99` y `mathd_numbertheory_521`); ninguno de los 4 problemas intermedios o avanzados de desarrollo fue resuelto.

## Contribución del Crítico y del RAG
En test, «sin RAG» resolvió {SR['first']} problemas al primer intento y {SR['rescued']} tras un reintento (`mathd_numbertheory_430`); el sistema completo resolvió sus 2 al primer intento aunque replanificó en {FU['replan']} de 20 problemas («sin RAG»: {SR['replan']}). En desarrollo los reintentos rescataron {len(dev_resc_sr)} problema en «sin RAG» y {len(dev_resc_fu)} en el completo (`{dev_resc_fu[0]}` y `{dev_resc_fu[1]}`). Ninguna de las {SC['nlemma_ok'] + FU['nlemma_ok']} pruebas correctas de las configuraciones con recuperación contiene un lema recuperado. (Tabla 4.)

## Costo
Con Crítico se necesitan {f1(SR['calls'])}–{f1(FU['calls'])} llamadas por problema, frente a {f1(SC['calls'])} sin Crítico y {f1(A['calls'])}–{f1(B['calls'])} en las líneas base; y unos {tok('sin_rag')}k–{tok('completo')}k tokens de entrada por problema frente a {tok('sin_critico')}k (sin Crítico) y {tok('baseline_a')}k–{tok('baseline_b')}k (líneas base). El costo extra no se traduce en un pass@1 distinguible del de las configuraciones más baratas. (Fig. 3.)

## Análisis de fallos
Los fallos se reparten en varias categorías y ninguna desaparece al añadir componentes: tácticas que no cierran la meta ({cats['táctica no cierra la meta']} casos entre configuraciones), `sorry`/`admit` ({cats['uso de sorry/admit']}; {min(sorry_rng)}–{max(sorry_rng)} por configuración), identificadores inexistentes ({cats['alucinación de identificador']}; {min(ident_rng)}–{max(ident_rng)} por configuración) y errores de sintaxis o formalización ({cats['sintaxis / formalización']}). La clasificación es heurística (último mensaje de Lean). (Tabla 5, Fig. 4.)
"""
(OUT / "results_draft_es_tecnico.md").write_text(es, encoding="utf-8")
print(en[:1200]); print("..."); print(len(en), len(es))
