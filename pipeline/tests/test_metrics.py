"""Metricas da Secao 6 com um gabarito sintetico pequeno (calculavel a mao)."""
import math

import pytest

import metrics as mt
from cwe import load_families

FAMS = [frozenset({119, 120, 121, 787}), frozenset({20, 129})]


def issue(i, file, line, cwes, quality=False, scanners=("flawfinder",), types=("FF1049",)):
    return {"id": i, "file": file, "line": line, "cwe_ids": cwes, "quality_only": quality, "scanners": list(scanners),
            "scanner_types": list(types), "source_code": None}


GT = mt.GT(
    issues=[issue("R1", "f1", 10, [120]), issue("R2", "f1", 30, [20]), issue("Q1", "f1", 50, [561], quality=True)],
    fps=[issue("P1", "f1", 20, [134]), issue("P2", "f2", 5, []), issue("P3", "f2", 40, [120])],
    file_class={"f1": "positive", "f2": "negative"})


def finding(fid, cwe, lines, conf=0.9):
    return {"id": fid, "cwe": cwe, "lines": lines, "confidence": conf}


def row(f, accepted=True, **extra):
    return {"finding": f, "accepted": accepted, "accepted_sens": accepted, **extra}


def run_of(f1_rows, f2_rows):
    return {"f1": {"file": "f1", "findings": f1_rows}, "f2": {"file": "f2", "findings": f2_rows}}


def scenario():
    return run_of(
        [row(finding("a", "CWE-120", [11])),            # casa R1                          -> tp_new
         row(finding("b", "CWE-121", [12])),            # casa R1 de novo (mesma familia)   -> dup
         row(finding("c", "CWE-134", [21])),            # casa o falso alarme P1            -> fp_new
         row(finding("d", "CWE-78", [100])),            # nao casa com nada                 -> out
         row(finding("e", "CWE-20", [29])),             # casa R2                           -> tp_new
         row(finding("f", "CWE-561", [50]))],           # casa o item so de qualidade Q1
        [row(finding("g", "CWE-999", [5]))])            # P2 nao tem CWE: casa so por linha -> fp_new


def test_labeled_metrics_by_hand():
    m = mt.labeled_metrics(tp=4, fp=2, n_real=8, n_fp=10)
    assert m["recall"] == 0.5 and m["false_alarm_rate"] == 0.2 and m["precision"] == pytest.approx(4 / 6)
    assert (m["fn"], m["tn"]) == (4, 8)
    assert m["f1"] == pytest.approx(2 * 4 / (2 * 4 + 4 + 2))
    assert m["f05"] == pytest.approx(1.25 * 4 / (1.25 * 4 + 0.25 * 4 + 2))
    assert m["mcc"] == pytest.approx((4 * 8 - 2 * 4) / math.sqrt(6 * 8 * 10 * 12))
    z = mt.labeled_metrics(0, 0, 5, 5)
    assert math.isnan(z["precision"]) and z["recall"] == 0 and math.isnan(z["mcc"])


def test_evaluate_run_classifies_each_finding():
    ev = mt.evaluate_run(scenario(), GT, "X", "main", families=FAMS)
    kinds = {r["finding_id"]: r["kind"] for r in ev.finding_rows}
    assert kinds == {"a": "tp_new", "b": "dup", "c": "fp_new", "d": "out", "e": "tp_new", "f": "tp_new", "g": "fp_new"}
    assert ev.accused_real == {"R1", "R2", "Q1"} and ev.accused_fp == {"P1", "P2"}
    m = ev.metrics()
    assert m["recall"] == 1.0 and m["false_alarm_rate"] == pytest.approx(2 / 3) and m["precision"] == pytest.approx(3 / 5)
    # intervalo da precisao geral: tp_new=3, fp_new=2, fora do gabarito=1 (o duplicado fica fora do numerador e do denominador)
    assert m["precision_overall_low"] == pytest.approx(3 / 6) and m["precision_overall_high"] == pytest.approx(4 / 6)
    assert m["n_out"] == 1 and m["out_per_file_pos"] == 1 and m["out_per_file_neg"] == 0
    assert m["files_flagged_pos"] == 1 and m["files_flagged_neg"] == 1 and m["neg_files_flagged_frac"] == 1.0


def test_without_families_cwe_121_does_not_match_cwe_120():
    run = run_of([row(finding("b", "CWE-121", [11]))], [])
    assert mt.evaluate_run(run, GT, "X", "m").accused_real == set()
    assert mt.evaluate_run(run, GT, "X", "m", families=FAMS).accused_real == {"R1"}


def test_line_only_sensitivity():
    run = run_of([row(finding("i", "CWE-999", [31]))], [])
    assert mt.evaluate_run(run, GT, "X", "m", families=FAMS).accused_real == set()
    assert mt.evaluate_run(run, GT, "X", "m", families=FAMS, require_cwe=False).accused_real == {"R2"}


def test_only_security_drops_quality_items_from_both_sides():
    ev = mt.evaluate_run(scenario(), GT, "X", "m", families=FAMS, only_security=True)
    assert ev.n_real == 2 and ev.accused_real == {"R1", "R2"}
    kinds = {r["finding_id"]: r["kind"] for r in ev.finding_rows}
    assert kinds["f"] == "ignored"                                  # nao conta como achado fora do gabarito nem como acerto
    assert ev.metrics()["recall"] == 1.0 and ev.metrics()["n_out"] == 1 and ev.per_file["n_findings"].sum() == 6


def test_only_accepted_findings_are_counted_and_sensitivity_flag():
    run = run_of([row(finding("a", "CWE-120", [11]), accepted=False), row(finding("e", "CWE-20", [29]))], [])
    assert mt.evaluate_run(run, GT, "X", "m").accused_real == {"R2"}
    run["f1"]["findings"][0]["accepted_sens"] = True
    assert mt.evaluate_run(run, GT, "X", "m", flag="accepted_sens").accused_real == {"R1", "R2"}


def test_files_missing_from_the_run_are_skipped():
    ev = mt.evaluate_run({"f1": scenario()["f1"]}, GT, "X", "m", families=FAMS)
    assert list(ev.per_file["file"]) == ["f1"] and ev.metrics()["n_neg_files"] == 0


def test_verifier_effect_removed_fp_and_lost_tp():
    b1 = mt.evaluate_run(scenario(), GT, "B1", "m", families=FAMS)
    kept = scenario()
    kept["f1"]["findings"][2]["accepted"] = False          # o verificador rejeita o falso alarme P1 (achado c)
    kept["f1"]["findings"][4]["accepted"] = False          # ... e perde o verdadeiro positivo R2 (achado e)
    kept["f1"]["findings"][3]["accepted"] = False          # ... e remove o achado fora do gabarito (d)
    c = mt.evaluate_run(kept, GT, "C3", "m", families=FAMS)
    e = mt.verifier_effect(b1, c)
    assert e["fp_removal_rate"] == 0.5 and (e["fp_removed"], e["fp_ref"]) == (1, 2)
    assert e["tp_loss_rate"] == pytest.approx(1 / 3) and (e["tp_lost"], e["tp_ref"]) == (1, 3)
    assert e["out_reduction"] == 1.0


def test_confidence_curve_is_monotone_and_starts_empty():
    run = run_of([row(finding("a", "CWE-120", [11], 0.9)), row(finding("c", "CWE-134", [21], 0.6)),
                  row(finding("e", "CWE-20", [29], 0.3))], [row(finding("g", "CWE-1", [5], 0.8))])
    cur = mt.confidence_curve(run, GT, families=FAMS)
    assert cur.iloc[0]["recall"] == 0 and cur.iloc[0]["false_alarm_rate"] == 0
    assert list(cur["recall"]) == sorted(cur["recall"]) and list(cur["false_alarm_rate"]) == sorted(cur["false_alarm_rate"])
    assert cur.iloc[-1]["recall"] == pytest.approx(3 / 3 - 1 / 3)      # R1 e R2 acusados (Q1 nao); 2 de 3 locais reais


# --------------------------------------------------------------------------- correcao
def tools(ok_orig=True, ok_patch=True, before=(), after=(), avail=True):
    f = lambda rule, line, sev="error", scanner="flawfinder": {"scanner": scanner, "line": line, "severity": sev, "rule": rule, "cwe": [], "message": rule}  # noqa: E731
    return {"compile_orig": {"status": "ok" if ok_orig else "error"}, "compile_patch": {"status": "ok" if ok_patch else "error"},
            "scan_orig": [f(*b) for b in before], "scan_patch": [f(*a) for a in after], "scan_status": "ok",
            "available": {"flawfinder": avail}}


ISS = issue("R1", "f1", 10, [120])


def test_fix_criteria_all_good():
    r = {"fix_verdict": "valid", "tools": tools(before=[("FF1049", 10)], after=[])}
    assert mt.fix_criteria(r, ISS) == {"verdict_valid": True, "rule_gone": True, "compiles": True, "no_new_warning": True}


def test_fix_criteria_each_failure_is_separate():
    base = {"fix_verdict": "partial", "tools": tools(before=[("FF1049", 10)], after=[("FF1049", 12), ("FF9", 3, "warning")])}
    c = mt.fix_criteria(base, ISS)
    assert c == {"verdict_valid": False, "rule_gone": False, "compiles": True, "no_new_warning": False}
    assert mt.fix_criteria({"fix_verdict": "valid", "tools": tools(ok_patch=False, before=[("FF1049", 10)])}, ISS)["compiles"] is False


def test_fix_criteria_not_applicable_cases():
    # original que nao compila: nao penaliza o patch
    assert mt.fix_criteria({"fix_verdict": "valid", "tools": tools(ok_orig=False, ok_patch=False)}, ISS)["compiles"] is None
    # sem ferramenta (C#): so o veredito vale
    assert mt.fix_criteria({"fix_verdict": "valid", "tools": {"scan_status": "not_verifiable"}}, ISS) == \
        {"verdict_valid": True, "rule_gone": None, "compiles": None, "no_new_warning": None}
    # issue so do snyk: a regra nao e re-executavel; usa as regras que dispararam perto da linha
    snyk = issue("R9", "f1", 10, [20], scanners=("snyk",), types=("cpp/X",))
    assert mt.fix_criteria({"fix_verdict": "valid", "tools": tools(before=[("FF1", 11)], after=[])}, snyk)["rule_gone"] is True
    assert mt.fix_criteria({"fix_verdict": "valid", "tools": tools(before=[("FF1", 90)], after=[])}, snyk)["rule_gone"] is None
    assert mt.fix_criteria({"tools": None}, ISS)["verdict_valid"] is None


def test_correction_summary_and_unnecessary_patches():
    run = run_of(
        [row(finding("a", "CWE-120", [11]), fix_verdict="valid", tools=tools(before=[("FF1049", 10)]), a2={"ok": True}),
         row(finding("c", "CWE-134", [21]), accepted=False, a2={"ok": True}),                  # patch para um falso alarme (rejeitado depois)
         row(finding("e", "CWE-20", [29]), fix_verdict="invalid", tools=tools(before=[("FF1049", 30)], after=[("FF1049", 30)]))],
        [row(finding("g", "CWE-1", [5]), accepted=False)])
    ev = mt.evaluate_run(run, GT, "C3", "m", families=FAMS)
    s = mt.correction_summary(run, GT, ev)
    assert (s["accused"], s["with_patch"], s["fixed_combined"]) == (2, 2, 1)
    assert s["fix_rate_conditional"] == 0.5 and s["fix_rate_global"] == pytest.approx(1 / 3)
    assert s["verdict_valid_true"] == 1 and s["verdict_valid_false"] == 1 and s["rule_gone_true"] == 1
    assert mt.unnecessary_patches(run, GT, families=FAMS) == 1
