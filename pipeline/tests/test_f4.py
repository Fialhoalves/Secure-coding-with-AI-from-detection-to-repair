"""Jobs da F4 em dry-run: validacao do A3b nos patches do artigo, extracao das respostas do artigo, comparacao de execucoes."""
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

import f4_jobs
import f4_prepare
import runner
from config import build_ctx
from conftest import CODE_C

RESPONSE = ("## Security analysis\n### 1. Unsafe copy with strcpy (line 5) (CWE-120)\nThe call overflows.\n"
            "### 2. Printf format (line 6) (CWE-134)\nNot controlled.\n```c\nint x;\n```\n")


@pytest.fixture
def raw(tmp_path):
    r = tmp_path / "raw"
    (r / "f").mkdir(parents=True)
    (r / "f" / "code.c").write_text(CODE_C, encoding="utf-8")
    (r / "f" / "patch.c").write_text(CODE_C.replace("strcpy(", "strncpy(") + "// fix\n", encoding="utf-8")
    (r / "f" / "resp.md").write_text(RESPONSE, encoding="utf-8")
    return r


def case(i):
    return {"issue_id": f"v8:1/{i}", "file": "v8:File_01", "snapshot": "v8", "folder": "File_01", "file_number": 1, "lang": "C", "ext": ".c",
            "code_path": "f/code.c", "patch_path": "f/patch.c",
            "finding": {"id": "G1", "cwe": "CWE-120", "lines": [5], "title": "strcpy overflow", "untrusted_source": "x", "sink": "strcpy(buf, name);",
                        "trigger": "long name", "assumptions": "none"}}


def test_fix_validation_stores_tools_verdict_and_resumes(cfg, raw, tmp_path):
    ctx = build_ctx(cfg, dry_run=True)
    out = tmp_path / "f4"
    s = f4_jobs.run_fix_validation(ctx, [case(1), case(2)], raw, out, workers=2, log=lambda *a: None)
    assert s["cases"] == 2 and s["judged"] == 2 and s["errors"] == []
    r = json.loads((out / "fix_validation" / "v8_1_1.json").read_text(encoding="utf-8"))
    assert r["fix_verdict"] in ("valid", "partial", "invalid") and r["a3b"]["step"] == "a3b"
    assert r["tools"]["compile_orig"]["status"] == "ok" and r["tools"]["scan_orig"] and "Syntax check" in r["report"]
    calls = ctx.ver.calls
    f4_jobs.run_fix_validation(ctx, [case(1), case(2)], raw, out, workers=2, log=lambda *a: None)
    assert ctx.ver.calls == calls                                           # retomada: nada refeito


def test_fix_validation_reports_a_broken_case_without_stopping(cfg, raw, tmp_path):
    ctx = build_ctx(cfg, dry_run=True)
    bad = {**case(9), "patch_path": "nao/existe.c"}
    s = f4_jobs.run_fix_validation(ctx, [case(1), bad], raw, tmp_path / "f4", workers=1, log=lambda *a: None)
    assert s["judged"] == 1 and len(s["errors"]) == 1


def test_paper_extraction_parses_claimed_findings(cfg, raw, tmp_path):
    ctx = build_ctx(cfg, dry_run=True)
    rec = {"snapshot": "v8", "folder": "File_01", "file_number": 1, "language": "C", "code": {"path": "f/code.c", "ext": ".c"},
           "models": {m: {"response": "f/resp.md"} for m in ("gpt-4.1", "gpt-5", "opus-4.1")}}
    s = f4_jobs.run_paper_extraction(ctx, [rec], raw, tmp_path / "f4", workers=2, log=lambda *a: None)
    assert s["jobs"] == 3 and s["ok"] == 3
    r = json.loads((tmp_path / "f4" / "paper_extract" / "gpt-4.1" / "v8_File_01.json").read_text(encoding="utf-8"))
    assert [(f["cwe"], f["lines"]) for f in r["findings"]] == [("CWE-120", [5]), ("CWE-134", [6])]


def test_dry_run_is_fully_deterministic_across_two_caches(cfg, items, tmp_path):
    import copy
    ctx1 = build_ctx(cfg, dry_run=True)
    runner.run(cfg, ctx1, items, ["main"], configs=["B1", "C1", "C3"], workers=2, log=lambda *a: None)
    cfg2 = copy.deepcopy(cfg)
    cfg2["paths"]["cache_dir"], cfg2["paths"]["runs_dir"] = tmp_path / "cache2", tmp_path / "runs2"
    ctx2 = build_ctx(cfg2, dry_run=True)
    runner.run(cfg2, ctx2, items, ["main"], configs=["B1", "C1", "C3"], workers=2, log=lambda *a: None)
    c = f4_jobs.compare_caches(cfg["paths"]["cache_dir"], cfg2["paths"]["cache_dir"])
    assert c["fraction_identical"] == 1.0 and c["common_calls"] > 0 and c["only_in_a"] == 0 and c["only_in_b"] == 0
    assert set(c["per_step"]) >= {"a1", "a3a"}
    runs = f4_jobs.compare_runs(cfg["paths"]["runs_dir"], cfg2["paths"]["runs_dir"], ["B1", "C1", "C3"])
    assert all(v["fraction"] == 1.0 and v["files"] == 3 for v in runs.values())


def test_compare_detects_differences(cfg, items, tmp_path):
    import copy
    ctx1 = build_ctx(cfg, dry_run=True)
    runner.run(cfg, ctx1, items, ["main"], configs=["B1"], workers=1, log=lambda *a: None)
    cfg2 = copy.deepcopy(cfg)
    cfg2["paths"]["cache_dir"], cfg2["paths"]["runs_dir"] = tmp_path / "cache2", tmp_path / "runs2"
    ctx2 = build_ctx(cfg2, dry_run=True)
    runner.run(cfg2, ctx2, items, ["main"], configs=["B1"], workers=1, log=lambda *a: None)
    # adultera uma resposta da 2a execucao e o conjunto aceito de um arquivo
    p = next(Path(cfg2["paths"]["cache_dir"]).glob("*/*.json"))
    rec = json.loads(p.read_text(encoding="utf-8")); rec["content"] += " "; p.write_text(json.dumps(rec), encoding="utf-8")
    f = next((Path(cfg2["paths"]["runs_dir"]) / "B1" / "main").glob("*.json"))
    r = json.loads(f.read_text(encoding="utf-8"))
    r["findings"].append({"finding": {"id": "X", "cwe": "CWE-1", "lines": [99]}, "accepted": True}); f.write_text(json.dumps(r), encoding="utf-8")
    c = f4_jobs.compare_caches(cfg["paths"]["cache_dir"], cfg2["paths"]["cache_dir"])
    assert c["fraction_identical"] < 1.0
    assert f4_jobs.compare_runs(cfg["paths"]["runs_dir"], cfg2["paths"]["runs_dir"], ["B1"])["B1"]["fraction"] < 1.0


def test_finding_from_issue_has_no_labels_and_strips_yes():
    row = pd.Series({"verdict_raw": "Yes, curl_easy_setopt() argument unsanitized", "cwe_ids": "20|78", "line": 29})
    f = f4_prepare.finding_from_issue(row, "curl_easy_setopt(curl, CURLOPT_URL, url);", "Unsanitized argument")
    assert f["title"] == "curl_easy_setopt() argument unsanitized" and f["cwe"] == "CWE-20" and f["lines"] == [29]
    assert f["trigger"] == "Unsanitized argument" and "fixed" not in json.dumps(f).lower()
    none = f4_prepare.finding_from_issue(pd.Series({"verdict_raw": "Yes", "cwe_ids": "nan", "line": 3}), None, None)
    assert none["cwe"] == "none" and none["title"] == "see scanner message"


def test_fix_cases_file_is_consistent_with_the_ground_truth():
    p = Path(__file__).resolve().parent.parent / "data" / "f4_fix_cases.jsonl"
    if not p.exists():
        pytest.skip("rode f4_prepare.py")
    cases = f4_jobs.load_fix_cases(p)
    assert len(cases) == 56 and len({c["issue_id"] for c in cases}) == 56
    assert all(c["patch_path"].startswith("DetectAndFix_Data") and "New_generated_code" in c["patch_path"] for c in cases)
    txt = p.read_text(encoding="utf-8").lower()
    assert "was issue fixed" not in txt and '"fixed"' not in txt          # nenhum rotulo de correcao dos autores


def test_verifier_calibration_runs_a3a_without_labels_and_resumes(cfg, raw, tmp_path):
    ctx = build_ctx(cfg, dry_run=True)
    cases = [{"case_id": f"v8:1/{i}", "file": "v8:File_01", "snapshot": "v8", "folder": "File_01", "file_number": 1, "lang": "C", "ext": ".c",
              "code_path": "f/code.c", "finding": case(i)["finding"]} for i in (1, 2)]
    s = f4_jobs.run_verifier_calibration(ctx, cases, raw, tmp_path / "f4", workers=2, log=lambda *a: None)
    assert s["cases"] == 2 and s["judged"] == 2 and s["errors"] == []
    r = json.loads((tmp_path / "f4" / "verifier_calibration" / "v8_1_1.json").read_text(encoding="utf-8"))
    assert r["verdict"] in ("confirmed", "refuted", "uncertain") and r["a3a"]["step"] == "a3a"
    calls = ctx.ver.calls
    f4_jobs.run_verifier_calibration(ctx, cases, raw, tmp_path / "f4", workers=2, log=lambda *a: None)
    assert ctx.ver.calls == calls


def test_verifier_cases_file_has_no_labels_and_scanner_only_text():
    p = Path(__file__).resolve().parent.parent / "data" / "f4_verifier_cases.jsonl"
    rows = [json.loads(line) for line in open(p, encoding="utf-8")]
    assert len(rows) == 141 and len({r["case_id"] for r in rows}) == 141
    assert all(set(r) == {"case_id", "file", "snapshot", "folder", "file_number", "lang", "ext", "code_path", "finding"} for r in rows)
    assert all(r["finding"]["trigger"].startswith("not specified") for r in rows)


def test_b0_fix_validation_judges_each_b0_finding_against_the_files_patch_and_resumes(cfg, items, tmp_path):
    ctx = build_ctx(cfg, dry_run=True)
    runner.run(cfg, ctx, items, ["main"], configs=["B0"], workers=1, log=lambda *a: None)
    b0_dir = Path(cfg["paths"]["runs_dir"]) / "B0" / "main"
    b0 = {r["file"]: r for r in (json.loads(p.read_text(encoding="utf-8")) for p in b0_dir.glob("*.json"))}
    n_find = {f: len(r["findings"]) for f, r in b0.items() if r["patch"]}
    assert sum(n_find.values()) > 0
    out = tmp_path / "f4"
    s = f4_jobs.run_b0_fix_validation(ctx, items, b0_dir, out, workers=2, log=lambda *a: None)
    assert s["files"] == len(items) and s["errors"] == [] and s["judgements"] == sum(n_find.values()) and s["judged"] == s["judgements"]
    assert s["files_with_patch"] == len(n_find)
    for it in items:
        r = json.loads((out / "b0_fix_validation" / f"{f4_jobs.safe_name(it.id)}.json").read_text(encoding="utf-8"))
        assert [x["finding_id"] for x in r["rows"]] == [row["finding"]["id"] for row in b0[it.id]["findings"]] if it.id in n_find else r["rows"] == []
        assert all(x["a3b"]["step"] == "a3b" and x["fix_verdict"] in ("valid", "partial", "invalid") for x in r["rows"])
        assert (r["tools"] is not None) == (it.id in n_find)
    calls = ctx.ver.calls
    f4_jobs.run_b0_fix_validation(ctx, items, b0_dir, out, workers=2, log=lambda *a: None)
    assert ctx.ver.calls == calls                                           # retomada: nada refeito
