"""F6/F7: as contagens por arquivo reproduzem exatamente as metricas do evaluate_run (base do bootstrap por cluster)."""
import math

import pytest

import f7_analyze as f7
import metrics as mt
from test_metrics import FAMS, GT, finding, row, run_of, scenario  # gabarito sintetico ja validado a mao


def _close(a, b):
    return (math.isnan(a) and math.isnan(b)) or a == pytest.approx(b)


@pytest.mark.parametrize("only_security", [False, True])
def test_sums_of_file_counts_reproduce_run_metrics(only_security):
    ev = mt.evaluate_run(scenario(), GT, "X", "main", families=FAMS, only_security=only_security)
    cnt = f7.file_counts(ev, GT, only_security)
    s = cnt.to_numpy(float).sum(axis=0)
    m = ev.metrics()
    for name in f7.MAIN_METRICS + f7.DESC_METRICS:
        assert _close(f7.metric_value(name, s), m[name]), name


def test_file_counts_one_row_per_file_with_accused_issues_per_file():
    ev = mt.evaluate_run(scenario(), GT, "X", "main", families=FAMS)
    cnt = f7.file_counts(ev, GT)
    assert list(cnt.index) == ["f1", "f2"]
    assert cnt.loc["f1", "acc_real"] == 3 and cnt.loc["f1", "n_real"] == 3 and cnt.loc["f1", "acc_fp"] == 1
    assert cnt.loc["f2", "acc_fp"] == 1 and cnt.loc["f2", "n_fp"] == 2 and cnt.loc["f2", "flag_neg"] == 1


def test_cluster_bootstrap_point_matches_and_interval_contains_it():
    ev = mt.evaluate_run(scenario(), GT, "X", "main", families=FAMS)
    cnt = f7.file_counts(ev, GT)
    ci = f7.ci_table(cnt, ["recall", "false_alarm_rate"], n_boot=200)
    assert ci["recall"]["point"] == ev.metrics()["recall"]
    assert ci["recall"]["lo"] <= ci["recall"]["point"] <= ci["recall"]["hi"]


def test_file_cwe_view_makes_findings_without_line_match_by_file_and_cwe():
    res = run_of([row(finding("a", "CWE-120", []))], [])
    strict = mt.evaluate_run(res, GT, "B0", "main", families=FAMS)
    assert strict.accused_real == set()                                   # sem linha, a regra estrita nao casa
    loose = mt.evaluate_run(f7.file_cwe_view(res), GT, "B0", "main", families=FAMS, tolerance=10 ** 6)
    assert loose.accused_real == {"R1"}                                   # arquivo + CWE compativel (120 ~ 120)


def test_b0_failed_files_and_subset():
    res = {"f1": {"steps": {"b0_extract": {"ok": False}}}, "f2": {"steps": {"b0_extract": {"ok": True}}}, "f3": {"steps": {}}}
    assert f7.b0_failed_files(res) == ["f1"]
    sub = f7.subset_gt(GT, {"f2"})
    assert [i["id"] for i in sub.fps] == ["P2", "P3"] and sub.issues == [] and sub.file_class == {"f2": "negative"}


# --------------------------------------------------------------------------- E1 e variancia (com gabarito sintetico)
import json  # noqa: E402


def _write_runs(root, config, rep, results):
    d = root / config / rep
    d.mkdir(parents=True)
    for fid, r in results.items():
        (d / f"{fid}.json").write_text(json.dumps(r), encoding="utf-8")


def _only_first_accepted(results):
    out = {}
    for fid, r in results.items():
        rows = [{**x, "accepted": i == 0, "accepted_sens": i == 0} for i, x in enumerate(r["findings"])]
        out[fid] = {**r, "findings": rows}
    return out


def test_variance_section_reports_each_repetition_and_h1(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    for rep in ("var1", "var2"):
        _write_runs(runs, "B1", rep, scenario())
        _write_runs(runs, "C3", rep, _only_first_accepted(scenario()))
    monkeypatch.setattr(f7, "RUNS", runs)
    main_var = f7.run_variant({"B1": scenario(), "C3": _only_first_accepted(scenario())}, GT, "main", None, FAMS, configs=["B1", "C3"])
    L, flat = f7.variance_section(GT, None, FAMS, 50, main_var)
    text = "\n".join(L)
    assert "var1" in text and "var2" in text and "var3" not in text
    assert "H1 refeita em cada repeticao" in text and "de 2 repeticoes" in text
    assert {r["variant"] for r in flat} == {"variancia var1", "variancia var2"}


def test_variance_section_without_runs_says_not_executed(tmp_path, monkeypatch):
    monkeypatch.setattr(f7, "RUNS", tmp_path / "vazio")
    L, flat = f7.variance_section(GT, None, FAMS, 50, {})
    assert "Ainda nao executado" in "\n".join(L) and flat == []


def test_e1_compares_pipeline_with_paper_responses_on_common_files(tmp_path, monkeypatch):
    pe = tmp_path / "paper_extract"
    for m, lines in (("gpt-4.1", [11]), ("gpt-5", [11]), ("opus-4.1", [11])):
        d = pe / m
        d.mkdir(parents=True)
        for fid in ("f1", "f2"):
            (d / f"{fid}.json").write_text(json.dumps({"file": fid, "paper_model": m, "ok": True, "findings": [{"cwe": "CWE-120", "lines": lines, "description": "x"}]}), encoding="utf-8")
    monkeypatch.setattr(f7, "PAPER_DIR", pe)
    base = {"B0": scenario(), "B1": scenario(), "C3": _only_first_accepted(scenario())}
    L, flat = f7.e1_section(base, GT, None, FAMS, 50)
    text = "\n".join(L)
    assert "GPT-5 (artigo)" in text and "Diferenca pareada por arquivo" in text and "2 positivos" not in text
    assert any(r["config"] == "GPT-4.1 (artigo)" for r in flat)


def test_e1_without_extractions_reports_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(f7, "PAPER_DIR", tmp_path / "nada")
    L, flat = f7.e1_section({}, GT, None, FAMS, 50)
    assert "Sem extracoes" in "\n".join(L) and flat == []


# --------------------------------------------------------------------------- H5 (C3 x C3-mf)
def _with_usage(results, verdict_of=lambda i: "confirmed" if i == 0 else "refuted"):
    out = {}
    for fid, r in results.items():
        rows = [{**x, "verdict": verdict_of(i)} for i, x in enumerate(r["findings"])]
        out[fid] = {**r, "findings": rows, "usage": {"calls": 3, "prompt_tokens": 100, "completion_tokens": 20, "seconds": 2.0}}
    return out


def test_h5_without_runs_says_not_executed(tmp_path, monkeypatch):
    monkeypatch.setattr(f7, "RUNS", tmp_path / "vazio")
    L, flat = f7.h5_section({}, GT, None, FAMS, 50)
    assert "Ainda nao executado" in "\n".join(L) and flat == []


def test_h5_compares_c3_with_c3mf_on_the_same_findings(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    c3 = _with_usage(_only_first_accepted(scenario()))
    mf = _with_usage(scenario(), verdict_of=lambda i: "confirmed")           # o verificador da mesma familia confirma tudo
    _write_runs(runs, "C3mf", "main", mf)
    monkeypatch.setattr(f7, "RUNS", runs)
    L, flat = f7.h5_section({"B1": _with_usage(scenario(), verdict_of=lambda i: None), "C3": c3}, GT, None, FAMS, 50)
    text = "\n".join(L)
    assert "Achados do A1 identicos aos do C3 em 2 de 2 arquivos" in text
    assert "McNemar exato por local, C3 x C3-mf" in text and "Sintese mecanica" in text and "H5" in text
    assert "Cobertura parcial" in text                                        # o gabarito sintetico nao tem 48 + 66 arquivos
    assert {r["variant"] for r in flat} == {"H5 regra estrita (linha ±3 e CWE compativel)", "H5 so linha ±3 (sensibilidade)",
                                            "H5 'uncertain' aceito (sensibilidade S2)"}
    assert {r["config"] for r in flat} == {"B1", "C3", "C3mf"}


def test_h5_flags_findings_that_differ_between_c3_and_c3mf(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    c3 = _with_usage(_only_first_accepted(scenario()))
    mf = _with_usage(scenario())
    mf["f2"]["findings"][0]["finding"] = {**mf["f2"]["findings"][0]["finding"], "lines": [6]}   # o A1 teria sido refeito e diferiu
    _write_runs(runs, "C3mf", "main", mf)
    monkeypatch.setattr(f7, "RUNS", runs)
    L, _ = f7.h5_section({"B1": _with_usage(scenario()), "C3": c3}, GT, None, FAMS, 50)
    assert "nao e sobre exatamente os mesmos achados" in "\n".join(L) and "em 1 de 2 arquivos" in "\n".join(L)


# --------------------------------------------------------------------------- A3b nos patches do B0
def test_b0_fix_section_without_runs_says_not_executed(tmp_path, monkeypatch):
    monkeypatch.setattr(f7, "B0FIX_DIR", tmp_path / "nada")
    assert "ainda nao executado" in "\n".join(f7.b0_fix_section(scenario(), GT, None, FAMS))


def test_b0_fix_merge_and_summary_use_the_a3b_verdict_plus_tool_criteria():
    from test_metrics import tools
    fix = {"f1": {"file": "f1", "tools": tools(before=[("FF1049", 10)], after=[]),
                  "rows": [{"finding_id": "a", "fix_verdict": "valid"}, {"finding_id": "e", "fix_verdict": "invalid"}]},
           "f2": {"file": "f2", "tools": None, "rows": []}}
    merged = f7.merge_b0_fix(scenario(), fix)
    rows = {r["finding"]["id"]: r for r in merged["f1"]["findings"]}
    assert rows["a"]["fix_verdict"] == "valid" and rows["a"]["tools"] is not None
    assert rows["c"]["fix_verdict"] is None and rows["c"]["tools"] is None          # achado sem julgamento do A3b
    text = "\n".join(f7.b0_fix_section(scenario(), GT, None, FAMS, fix))
    assert "B0 + A3b" in text and "valid: 1" in text and "invalid: 1" in text and "arquivos sem julgamento (sem patch ou sem achados extraidos): 1" in text
    # acusados: R1 (a), R2 (e) e o item so de qualidade Q1 (f); so a (valid + regra sumiu + compila + sem aviso novo) conta como corrigida => 1 de 3
    ev = mt.evaluate_run(merged, GT, "B0", "main", families=FAMS)
    cs = mt.correction_summary(merged, GT, ev)
    assert cs["accused"] == 3 and cs["fixed_combined"] == 1 and cs["fix_rate_conditional"] == pytest.approx(1 / 3)
