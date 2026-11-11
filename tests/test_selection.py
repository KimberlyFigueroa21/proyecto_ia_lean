import json
from collections import Counter
from pathlib import Path

import pytest

from src.selection import QUOTAS, audit_markdown, fidelity_sample, select, summary_table

PROBLEMS = [json.loads(l) for l in Path("data/problems.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
PILOTS = json.loads(Path("data/pilot_ids.json").read_text())


def test_cuotas_suman_30_y_20_test():
    assert sum(QUOTAS.values()) == 30
    assert sum(n for (s, _, _), n in QUOTAS.items() if s == "test") == 20


def test_seleccion_cumple_cuotas_y_no_repite():
    ch = select(PROBLEMS, PILOTS)
    assert len(ch) == 30 and len({p["id"] for p in ch}) == 30
    assert Counter((p["split"], p["area"], p["difficulty"]) for p in ch) == Counter(QUOTAS)


def test_pilotos_en_dev_y_nada_prohibido():
    ch = select(PROBLEMS, PILOTS)
    assert all(p["split"] == "dev" for p in ch if p["id"] in PILOTS)
    assert all(not p["has_reference_proof"] and not p["maintainer_note"] for p in ch)
    assert all(p["difficulty"] in ("basico", "intermedio", "avanzado") for p in ch)
    assert not any(p["split"] == "test" and p["id"] in PILOTS for p in ch)


def test_es_determinista_y_depende_de_la_semilla():
    a = [p["id"] for p in select(PROBLEMS, PILOTS)]
    assert a == [p["id"] for p in select(PROBLEMS, PILOTS)]
    assert a != [p["id"] for p in select(PROBLEMS, PILOTS, seed=1)]


def test_conteo_usa_los_9_disponibles():
    ch = select(PROBLEMS, PILOTS)
    assert {p["id"] for p in ch if p["area"] == "conteo"} == {p["id"] for p in PROBLEMS if p["area"] == "conteo"}


def test_error_si_falta_material():
    with pytest.raises(ValueError, match="faltan problemas"):
        select([p for p in PROBLEMS if p["area"] != "conteo"], PILOTS)


def test_auditoria_y_tabla():
    ch = select(PROBLEMS, PILOTS)
    fid = fidelity_sample(ch)
    assert len(fid) == 5 and set(fid) <= {p["id"] for p in ch}
    md = audit_markdown(ch, fid)
    assert md.count("★ FIDELIDAD") == 5 and md.count("\n## ") == 30
    assert "| **Total** |" in summary_table(ch)
