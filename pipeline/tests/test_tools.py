"""Parsers e logica de diff das ferramentas do A3b. Nenhuma ferramenta externa e necessaria (runner injetado)."""
import subprocess
from types import SimpleNamespace

from tools import FakeTools
from tools.compile import syntax_check
from tools.scan import (diff_scans, format_tool_report, parse_cppcheck, parse_flawfinder_csv, parse_semgrep_json,
                        run_scanners)

FF_CSV = ("File,Line,Column,Level,Category,Name,Warning,Suggestion,Note,CWEs,Context,Fingerprint,ToolVersion,RuleId,HelpUri\r\n"
          "snippet.c,5,5,4,buffer,strcpy,Does not check for buffer overflows,use strncpy,,\"CWE-120\",\"strcpy(buf,name);\",fp1,2.0.20,FF1049,http://x\r\n"
          "snippet.c,4,5,2,buffer,char,Statically-sized arrays can be improperly restricted,check,,\"CWE-119!/CWE-120\",char buf[16];,fp2,2.0.20,FF1013,http://x\r\n"
          "snippet.c,9,1,5,shell,system,Calls system,avoid,,\"CWE-78\",system(x);,fp3,2.0.20,FF1044,http://x\r\n")
CPP = "5|warning|bufferAccessOutOfBounds|788|Buffer is accessed out of bounds\n12|style|unusedVariable|563|Unused variable: x\nlixo sem formato\n"


def _semgrep_json():
    import json
    return json.dumps({"results": [{"check_id": "c.lang.strcpy", "start": {"line": 5}, "extra": {
        "severity": "ERROR", "message": "strcpy is unsafe", "metadata": {"cwe": ["CWE-120: Buffer Copy"]}}}]})


def test_parse_flawfinder_levels_and_cwes():
    f = parse_flawfinder_csv(FF_CSV)
    assert [(x["line"], x["severity"], x["rule"]) for x in f] == [(5, "error", "FF1049"), (4, "note", "FF1013"), (9, "error", "FF1044")]
    assert f[1]["cwe"] == [119] or f[1]["cwe"] == [119, 120]    # 'CWE-119!/CWE-120'
    assert parse_flawfinder_csv("") == []


def test_parse_cppcheck_template():
    f = parse_cppcheck(CPP)
    assert [(x["line"], x["severity"], x["rule"], x["cwe"]) for x in f] == [(5, "warning", "bufferAccessOutOfBounds", [788]),
                                                                           (12, "note", "unusedVariable", [563])]


def test_parse_semgrep_json_and_garbage():
    f = parse_semgrep_json(_semgrep_json())
    assert f == [{"scanner": "semgrep", "line": 5, "severity": "error", "rule": "c.lang.strcpy", "cwe": [120], "message": "strcpy is unsafe"}]
    assert parse_semgrep_json("nao e json") == []


def _f(scanner, rule, line, sev="warning", msg="m"):
    return {"scanner": scanner, "line": line, "severity": sev, "rule": rule, "cwe": [], "message": msg}


def test_diff_scans_rule_gone_by_count_not_by_line():
    before = {"status": "ok", "findings": [_f("flawfinder", "FF1049", 5, "error"), _f("flawfinder", "FF1013", 4, "note")]}
    after = {"status": "ok", "findings": [_f("flawfinder", "FF1013", 9, "note")]}          # as linhas mudaram com o patch
    d = diff_scans(before, after, target_line=5)
    assert d["target_rules"] == ["flawfinder:FF1013", "flawfinder:FF1049"]               # +-3 linhas pega as duas
    assert d["per_rule_gone"] == {"flawfinder:FF1013": False, "flawfinder:FF1049": True}
    assert d["target_gone"] is False and d["any_target_gone"] is True and d["new_warning_or_worse"] == 0
    d2 = diff_scans(before, after, target_rules=[("flawfinder", "FF1049")])
    assert d2["target_gone"] is True


def test_diff_scans_new_findings_only_warning_or_worse_count():
    before = {"status": "ok", "findings": [_f("cppcheck", "a", 1)]}
    after = {"status": "ok", "findings": [_f("cppcheck", "a", 1), _f("cppcheck", "b", 3, "warning"), _f("cppcheck", "c", 4, "note")]}
    d = diff_scans(before, after, target_line=1)
    assert {x["rule"] for x in d["new_findings"]} == {"b", "c"} and d["new_warning_or_worse"] == 1


def test_diff_scans_no_target_and_not_verifiable():
    assert diff_scans({"status": "ok", "findings": []}, {"status": "ok", "findings": []}, target_line=5)["target_gone"] is None
    assert diff_scans({"status": "not_verifiable"}, {"status": "ok"}) == {"status": "not_verifiable"}


def _proc(rc=0, out="", err=""):
    return SimpleNamespace(returncode=rc, stdout=out, stderr=err)


def test_syntax_check_with_stub_runner():
    ok = syntax_check("int main(){}", "C", run=lambda *a, **k: _proc(0))
    assert ok["status"] == "ok" and ok["n_errors"] == 0 and "gcc" in ok["cmd"] and "-fsyntax-only" in ok["cmd"] and "-std=c11" in ok["cmd"]
    bad = syntax_check("int main(", "C++", run=lambda *a, **k: _proc(1, err="snippet.cpp:1:10: error: expected ')'\nnote: x\n"))
    assert bad["status"] == "error" and bad["n_errors"] == 1 and "g++" in bad["cmd"] and "-std=c++17" in bad["cmd"]
    assert syntax_check("class A{}", "C#")["status"] == "not_verifiable"

    def boom(*a, **k):
        raise subprocess.TimeoutExpired("gcc", 1)
    assert syntax_check("x", "C", run=boom)["status"] == "timeout"


def test_run_scanners_with_stub_runner_parses_each_tool():
    def fake_run(cmd, **kw):
        if cmd[0] == "flawfinder":
            return _proc(0, out=FF_CSV)
        if cmd[0] == "cppcheck":
            return _proc(0, err=CPP)
        return _proc(0, out=_semgrep_json())
    r = run_scanners("int main(){}", "C", run=fake_run, force=True)
    assert r["available"] == {"flawfinder": True, "cppcheck": True, "semgrep": True}
    assert {f["scanner"] for f in r["findings"]} == {"flawfinder", "cppcheck", "semgrep"}
    assert run_scanners("class A{}", "C#")["status"] == "not_verifiable"


def test_run_scanners_survives_a_failing_tool():
    def fake_run(cmd, **kw):
        if cmd[0] == "cppcheck":
            raise subprocess.TimeoutExpired("cppcheck", 1)
        return _proc(0, out=FF_CSV if cmd[0] == "flawfinder" else "{}")
    r = run_scanners("x", "C", run=fake_run, force=True)
    assert r["errors"] == {"cppcheck": "timeout"} and any(f["scanner"] == "flawfinder" for f in r["findings"])


def test_tool_report_has_only_tool_output_and_handles_unavailable():
    ft = FakeTools()
    orig, patch = "strcpy(a,b);\n", "strncpy(a,b,3);\n"
    so, sp = ft.scan(orig, "C"), ft.scan(patch, "C")
    d = diff_scans(so, sp, target_line=1)
    rep = format_tool_report(ft.compile(orig, "C"), ft.compile(patch, "C"), so, sp, d)
    assert "ORIGINAL: ok" in rep and "PATCH: ok" in rep and "flawfinder:FF1001" in rep and "yes" in rep
    cs = format_tool_report(ft.compile("x", "C#"), ft.compile("y", "C#"), ft.scan("x", "C#"), ft.scan("y", "C#"), {"status": "not_verifiable"})
    assert "not available" in cs and "not available for this language" in cs
    for forbidden in ("known_fp", "positive", "negative"):
        assert forbidden not in rep


def test_fake_tools_compile_flags_unbalanced_braces():
    assert FakeTools().compile("void f() {", "C")["status"] == "error"
    assert FakeTools().compile("void f() {}", "C++")["status"] == "ok"
