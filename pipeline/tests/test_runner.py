"""Runner em dry-run (clientes e ferramentas simulados): nenhum modelo e chamado. Verifica a estrutura das configuracoes,
as regras de desenho da Secao 3 (reaproveitamento do A1, mesma postura no A3, sem vazamento do gabarito), a retomada e a
guarda de cota."""
import json
import re
import sys
from pathlib import Path

import pytest

import runner
from agents import Ctx
from config import build_ctx
from llm import FakeClient, RawResponse

CFGS = ["B0", "B1", "C1", "C2", "C3"]
PIPELINE = Path(__file__).resolve().parent.parent


def read(cfg, config, item, rep="main"):
    return json.loads((Path(cfg["paths"]["runs_dir"]) / config / rep / f"{runner.safe_name(item.id)}.json").read_text(encoding="utf-8"))


def test_dry_run_completes_all_configs_without_real_calls(cfg, items, monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)      # qualquer tentativa de usar o cliente real falharia
    ctx = build_ctx(cfg, dry_run=True)
    assert ctx.det.is_fake and ctx.ver.is_fake
    s = runner.run(cfg, ctx, items, ["main"], configs=CFGS, workers=2)
    assert s["reps"]["main"]["done"] == 3 and s["reps"]["main"]["errors"] == []
    for it in items:
        for c in CFGS:
            r = read(cfg, c, it)
            assert r["file"] == it.id and r["config"] == c and r["rep"] == "main" and "usage" in r
    assert ctx.det.calls + ctx.ver.calls == s["llm"]["calls"] - s["llm"]["cache_hits"] > 0


def test_structure_and_invariants_between_configs(cfg, items):
    ctx = build_ctx(cfg, dry_run=True)
    runner.run(cfg, ctx, items, ["main"], configs=CFGS, workers=1)
    for it in items:
        b1, c1, c2, c3 = (read(cfg, c, it) for c in ("B1", "C1", "C2", "C3"))
        ids = [x["finding"]["id"] for x in b1["findings"]]
        assert b1["accepted"] == ids                                        # B1 aceita tudo o que o A1 achou
        assert set(c1["accepted"]) <= set(b1["accepted"])                   # o verificador so remove
        assert c3["accepted"] == c1["accepted"]                             # regra 1: mesmo A1, mesmo A3a (cache compartilhado)
        assert set(c2["accepted"]) <= set(ids)
        n, n_conf = len(ids), len(c3["accepted"])
        assert b1["usage"]["calls"] == 1
        assert c1["usage"]["calls"] == 1 + n
        assert c2["usage"]["calls"] == 1 + 2 * n                            # A2 em todos + A3 conjunto em todos
        assert c3["usage"]["calls"] == 1 + n + 2 * n_conf                   # A3a em todos; A2 e A3b so nos confirmados
        assert all(("a2" in r) for r in c2["findings"])                    # C2 corrige todos os achados
        assert all(("a3b" in r) == (r["verdict"] == "confirmed") for r in c3["findings"])
        assert all(r.get("status") == "fixed_judged" for r in c3["findings"] if r["verdict"] == "confirmed")
    assert len(ctx.caller.cache) < sum(read(cfg, c, it)["usage"]["calls"] for it in items for c in CFGS)   # houve compartilhamento


def test_uncertain_counts_as_rejected_in_main_and_accepted_in_sensitivity(cfg, items):
    ctx = build_ctx(cfg, dry_run=True)
    runner.run(cfg, ctx, items, ["main"], configs=["C1"], workers=1)
    seen = set()
    for it in items:
        for r in read(cfg, "C1", it)["findings"]:
            seen.add(r["verdict"])
            assert r["accepted"] == (r["verdict"] == "confirmed")
            assert r["accepted_sens"] == (r["verdict"] in ("confirmed", "uncertain"))
    assert "uncertain" in seen or len(seen) >= 1


def test_resume_skips_finished_files_and_cache_makes_reruns_free(cfg, items):
    ctx = build_ctx(cfg, dry_run=True)
    s1 = runner.run(cfg, ctx, items, ["main"], configs=CFGS, workers=2)
    calls = s1["llm"]["calls"]
    s2 = runner.run(cfg, ctx, items, ["main"], configs=CFGS, workers=2)
    assert s2["reps"]["main"]["done"] == 0 and s2["llm"]["calls"] == calls          # nada pendente: nada refeito
    import shutil
    shutil.rmtree(cfg["paths"]["runs_dir"])
    ctx2 = build_ctx(cfg, dry_run=True)                                              # novo processo, mesmo cache em disco
    s3 = runner.run(cfg, ctx2, items, ["main"], configs=CFGS, workers=2)
    assert s3["reps"]["main"]["done"] == 3 and s3["llm"]["calls"] == s3["llm"]["cache_hits"] > 0
    assert ctx2.det.calls == 0 and ctx2.ver.calls == 0


def test_quota_guard_stops_before_starting_files(cfg, items):
    ctx = build_ctx(cfg, dry_run=True)
    s = runner.run(cfg, ctx, items, ["main"], configs=["B1"], workers=1, guard=runner.QuotaGuard(0.0))
    assert s["reps"]["main"]["done"] == 0 and s["reps"]["main"]["stopped_by_quota_guard"] and s["reps"]["main"]["pending_left"] == 3
    log = [json.loads(x) for x in (Path(cfg["paths"]["runs_dir"]) / "gpu_sessions.jsonl").read_text().splitlines()]
    assert log[-1]["done"] == {"main": 0} and "hours" in log[-1]
    # uma guarda generosa processa tudo e registra as horas da sessao
    s2 = runner.run(cfg, ctx, items, ["main"], configs=["B1"], workers=1, guard=runner.QuotaGuard(11.0))
    assert s2["reps"]["main"]["done"] == 3 and not s2["reps"]["main"]["stopped_by_quota_guard"]


def test_variance_repetitions_only_run_b1_and_c3_with_other_seeds(cfg, items):
    ctx = build_ctx(cfg, dry_run=True)
    runner.run(cfg, ctx, items[:1], ["main", "var1"], workers=1)
    runs = Path(cfg["paths"]["runs_dir"])
    assert {p.name for p in runs.iterdir() if p.is_dir()} == {"B0", "B1", "C1", "C2", "C3"}
    assert (runs / "C3" / "var1").is_dir() and (runs / "B1" / "var1").is_dir()
    assert not (runs / "C1" / "var1").exists() and not (runs / "C2" / "var1").exists() and not (runs / "B0" / "var1").exists()
    b1_main, b1_var = read(cfg, "B1", items[0], "main"), read(cfg, "B1", items[0], "var1")
    assert b1_main["steps"]["a1"]["base_seed"] == 0 and b1_var["steps"]["a1"]["base_seed"] == 1
    assert b1_var["steps"]["a1"]["temperature"] == 0.7                                # temperatura do cartao do detector


def test_c3mf_uses_the_detector_model_as_verifier(cfg, items):
    ctx = build_ctx(cfg, dry_run=True)
    runner.run(cfg, ctx, items[:1], ["main"], configs=["C3", "C3mf"], workers=1)
    c3, mf = read(cfg, "C3", items[0]), read(cfg, "C3mf", items[0])
    for r in c3["findings"]:
        assert r["a3a"]["model"] == "gpt-oss:20b"
    for r in mf["findings"]:
        assert r["a3a"]["model"] == "qwen2.5-coder:14b" and r["a3a"]["step"] == "a3a_mf"


# --------------------------------------------------------------------------- regras de desenho
class Recorder(FakeClient):
    def __init__(self, spec):
        super().__init__(spec)
        self.log = []

    def chat(self, step, messages, schema, temperature, seed, max_tokens):
        self.log.append((step, messages))
        return super().chat(step, messages, schema, temperature, seed, max_tokens)


@pytest.fixture
def recorded(cfg, items):
    base = build_ctx(cfg, dry_run=True)
    det, ver = Recorder(base.det.spec), Recorder(base.ver.spec)
    ctx = Ctx(caller=base.caller, prompts=base.prompts, det=det, ver=ver, tools=base.tools)
    runner.run(cfg, ctx, items, ["main"], configs=CFGS, workers=1)
    return det.log + ver.log


def test_no_gold_standard_or_scanner_output_reaches_detector_verifier_or_fixer(recorded, items):
    forbidden = ["flawfinder", "cppcheck", "semgrep", "snyk", "known_fp", "gt_issues", "scanner_types", "positive", "negative", "Static scanners"]
    seen_steps = set()
    for step, msgs in recorded:
        if step in ("a1", "a3a", "a3joint", "a2", "b0_response", "b0_extract"):
            seen_steps.add(step)
            text = " ".join(m["content"] for m in msgs).lower()
            for w in forbidden:
                assert w.lower() not in text, f"{step} recebeu '{w}'"
    assert seen_steps == {"a1", "a3a", "a3joint", "a2", "b0_response", "b0_extract"}


def test_tool_output_appears_only_in_a3b(recorded):
    a3b = [msgs for step, msgs in recorded if step == "a3b"]
    assert a3b and all("Syntax check" in m[-1]["content"] and "Static scanners" in m[-1]["content"] for m in a3b)
    assert all("Syntax check" not in " ".join(m["content"] for m in msgs) for step, msgs in recorded if step != "a3b")


def test_a3a_and_joint_share_the_same_adversarial_prompt(recorded):
    a3a = next(m for s, m in recorded if s == "a3a")
    joint = [m for s, m in recorded if s == "a3joint"]
    assert joint and all(j[0] == a3a[0] for j in joint)                                  # mesma mensagem de sistema
    u = a3a[1]["content"]
    assert "Proposed patch" not in u and all("Proposed patch" in j[1]["content"] for j in joint)   # A3a nao ve o patch
    assert all("REFUTE" in j[0]["content"] for j in joint)


def test_confidence_is_hidden_from_verifier_and_fixer(recorded):
    for step, msgs in recorded:
        if step in ("a3a", "a3joint", "a2", "a3b"):
            assert not re.search(r'"confidence":\s*[0-9]', msgs[-1]["content"]), step


def test_a3a_judges_one_finding_per_call(recorded):
    for step, msgs in recorded:
        if step == "a3a":
            assert msgs[-1]["content"].count("Reported finding:") == 1 and msgs[-1]["content"].count('"id":') == 1


def test_untrusted_code_is_delimited_and_injection_is_ignored_by_instruction(recorded):
    for step, msgs in recorded:
        if step in ("a1", "a3a", "a3joint", "a2", "a3b"):
            assert "<code>" in msgs[-1]["content"] and "</code>" in msgs[-1]["content"]
            assert "untrusted" in msgs[0]["content"].lower() and "ignore" in msgs[0]["content"].lower()


# --------------------------------------------------------------------------- B0 e dados
def test_b0_prompt_is_the_papers_prompt_literally(cfg, items):
    from agents import fence_lang
    p = build_ctx(cfg, dry_run=True).prompts["b0"]
    (m,) = p.messages(fence_lang=fence_lang(items[0]), code=items[0].code)
    assert m["role"] == "user" and p.system is None
    assert m["content"].startswith("I would like to ask you to behave like senior software developer with expertise in software security")
    assert "You must find security issues in the code snippet below in this message." in m["content"]
    assert m["content"].endswith("\n```)") and "(```c\n#include <stdio.h>" in m["content"]


def test_last_code_block_is_the_b0_patch():
    assert runner.last_code_block("a\n```c\nx=1;\n```\ntexto\n```cpp\ny=2;\nz=3;\n```\nfim") == "y=2;\nz=3;"
    assert runner.last_code_block("sem codigo") is None


def test_pilot_selection_is_stratified_and_deterministic():
    from agents import CodeItem
    its = []
    for i in range(1, 25):
        lang, ext = [("C", ".c"), ("C++", ".cpp"), ("C#", ".cs")][i % 3]
        its.append(CodeItem(f"v8:File_{i:02d}", "v8", i, lang, ext, "x", "positive" if i % 2 else "negative"))
    a, b = runner.select_pilot(its), runner.select_pilot(its)
    assert [x.id for x in a] == [x.id for x in b] and len(a) == 10
    assert sum(x.cls == "positive" for x in a) == 5 and sum(x.cls == "negative" for x in a) == 5
    assert {x.lang for x in a} == {"C", "C++", "C#"}
    mixed = [CodeItem(f"{s}:File_{i:02d}", s, i, "C", ".c", "x", "positive") for i in range(1, 9) for s in ("v8", "v10")]
    assert {x.snapshot for x in runner.select_pilot(mixed, n_pos=4, n_neg=0)} == {"v8", "v10"}      # nao esgota um snapshot


@pytest.mark.skipif(not (PIPELINE / "data" / "files.jsonl").exists() or not (PIPELINE / "data" / "raw").exists(),
                    reason="dados dos autores nao baixados")
def test_load_items_from_real_data():
    items = runner.load_items(PIPELINE / "data" / "raw" / "MSc_DataEngineering_Results", PIPELINE / "data" / "files.jsonl", "all")
    assert len(items) == 114 and sum(i.cls == "positive" for i in items) == 48 and sum(i.cls == "negative" for i in items) == 66
    assert "v8:File_02" not in {i.id for i in items}                                  # o arquivo excluido fica de fora
    pilot = runner.select_items(items, "pilot")
    assert len(pilot) == 10 and sum(i.cls == "positive" for i in pilot) == 5
    assert len(runner.select_items(items, "first:3")) == 3


def test_a1_findings_are_capped_in_model_order(cfg, items):
    ctx = build_ctx(cfg, dry_run=True)
    ctx.max_findings = 0
    runner.run(cfg, ctx, items[:1], ["main"], configs=["B1", "C1"], workers=1)
    assert read(cfg, "B1", items[0])["findings"] == [] and read(cfg, "C1", items[0])["findings"] == []


def _f(fid, cwe, lines):
    return {"id": fid, "cwe": cwe, "lines": lines}


def test_dedupe_same_cwe_overlapping_lines_keeps_first():
    fs = [_f("F1", "CWE-78", [2, 3]), _f("F2", "CWE-78", [3]), _f("F3", "CWE-120", [3]), _f("F4", "CWE-78", [3]), _f("F5", "CWE-78", [9])]
    kept, n = runner.dedupe_findings(fs)
    assert [f["id"] for f in kept] == ["F1", "F3", "F5"] and n == 2           # outra CWE na mesma linha e outra linha ficam


def test_dedupe_never_drops_findings_without_lines_and_normalizes_cwe_text():
    fs = [_f("F1", "none", []), _f("F2", "none", []), _f("F3", "CWE-120", [5]), _f("F4", " cwe-120 ", [5, 6])]
    kept, n = runner.dedupe_findings(fs)
    assert [f["id"] for f in kept] == ["F1", "F2", "F3"] and n == 1


def test_dedupe_can_be_switched_off(cfg, items):
    ctx = build_ctx(cfg, dry_run=True)
    ctx.dedupe = False
    runner.run(cfg, ctx, items[:1], ["main"], configs=["B1"], workers=1)
    assert read(cfg, "B1", items[0])["duplicates_removed"] == 0


def test_select_part_splits_items_without_overlap(cfg, items):
    a, b = runner.select_items(items, "part:0/2"), runner.select_items(items, "part:1/2")
    assert [i.id for i in a] == ["v8:File_01", "v10:File_03"] and [i.id for i in b] == ["v8:File_02"]
    assert {i.id for i in a} | {i.id for i in b} == {i.id for i in items} and not ({i.id for i in a} & {i.id for i in b})
