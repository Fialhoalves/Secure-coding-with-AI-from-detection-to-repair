"""Re-scan com flawfinder, cppcheck e semgrep (o Snyk fica fora: exige conta). Roda no original e no patch;
`diff_scans` diz se o achado da linha-alvo sumiu e se apareceram achados novos de severidade warning ou maior."""
from __future__ import annotations

import csv
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

SEV_ORDER = {"note": 0, "warning": 1, "error": 2}
FLAWFINDER_BIN = "flawfinder"
# p/default reproduz as regras de semgrep que os autores usaram (ex.: c.lang.security.insecure-use-scanf-fn); p/c nao (F3, tools_check). O pacote e baixado do registro a cada chamada (nao fica fixado): registrar a data e a versao ao reportar resultados.
SEMGREP_CONFIG = os.environ.get("TAES_SEMGREP_CONFIG", "p/default")


def _cwes(text: str | None) -> list[int]:
    return [int(x) for x in dict.fromkeys(re.findall(r"CWE[-\s]?([0-9]+)", text or "", flags=re.I))]


def parse_flawfinder_csv(text: str) -> list[dict]:
    """Nivel do flawfinder: 1-2 note, 3 warning, 4-5 error."""
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            level, line = int(row.get("Level", 0)), int(row.get("Line", 0))
        except ValueError:
            continue
        out.append({"scanner": "flawfinder", "line": line, "severity": "note" if level <= 2 else ("warning" if level == 3 else "error"),
                    "rule": row.get("RuleId") or row.get("Name") or "", "cwe": _cwes(row.get("CWEs")),
                    "message": (row.get("Warning") or "").strip()[:200]})
    return out


def parse_cppcheck(text: str) -> list[dict]:
    """Template: {line}|{severity}|{id}|{cwe}|{message}. error->error, warning->warning, o resto->note."""
    out = []
    for ln in text.splitlines():
        parts = ln.split("|", 4)
        if len(parts) != 5 or not parts[0].strip().isdigit():
            continue
        sev = {"error": "error", "warning": "warning"}.get(parts[1].strip(), "note")
        out.append({"scanner": "cppcheck", "line": int(parts[0]), "severity": sev, "rule": parts[2].strip(),
                    "cwe": [int(parts[3])] if parts[3].strip().isdigit() else [], "message": parts[4].strip()[:200]})
    return out


def parse_semgrep_json(text: str) -> list[dict]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    out = []
    for r in data.get("results", []):
        extra = r.get("extra", {})
        meta_cwe = extra.get("metadata", {}).get("cwe", [])
        meta_cwe = meta_cwe if isinstance(meta_cwe, list) else [meta_cwe]
        sev = {"ERROR": "error", "WARNING": "warning"}.get(str(extra.get("severity", "")).upper(), "note")
        out.append({"scanner": "semgrep", "line": int(r.get("start", {}).get("line", 0)), "severity": sev,
                    "rule": r.get("check_id", ""), "cwe": _cwes(" ".join(map(str, meta_cwe))),
                    "message": str(extra.get("message", "")).strip()[:200]})
    return out


def run_scanners(code: str, lang: str, *, run=subprocess.run, timeout: int = 120, semgrep_bin: str | None = None,
                 semgrep_config: str = SEMGREP_CONFIG, force: bool = False) -> dict:
    """{'available': {scanner: bool}, 'findings': [...], 'errors': {scanner: msg}}. C#: nao verificavel."""
    if lang == "C#":
        return {"status": "not_verifiable", "available": {}, "findings": [], "errors": {}}
    ext, cpp_lang = (".c", "c") if lang == "C" else (".cpp", "c++")
    semgrep_bin = semgrep_bin or shutil.which("semgrep") or "semgrep"
    findings, available, errors = [], {}, {}
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / f"snippet{ext}"
        src.write_text(code, encoding="utf-8")
        jobs = {
            "flawfinder": ([FLAWFINDER_BIN, "--csv", "--minlevel=1", src.name], lambda p: p.stdout, parse_flawfinder_csv),
            "cppcheck": (["cppcheck", f"--language={cpp_lang}", "--enable=warning,style,performance,portability", "--inconclusive",
                          "--quiet", "--template={line}|{severity}|{id}|{cwe}|{message}", src.name], lambda p: p.stderr, parse_cppcheck),
            "semgrep": ([semgrep_bin, "--config", semgrep_config, "--json", "--metrics=off", "--quiet", "--disable-version-check", src.name],
                        lambda p: p.stdout, parse_semgrep_json),
        }
        for name, (cmd, pick, parse) in jobs.items():
            if not force and run is subprocess.run and shutil.which(cmd[0]) is None:
                available[name] = False
                continue
            available[name] = True
            try:
                p = run(cmd, cwd=d, capture_output=True, text=True, timeout=timeout)
                findings += parse(pick(p))
            except subprocess.TimeoutExpired:
                errors[name] = "timeout"
            except Exception as e:  # noqa: BLE001
                errors[name] = repr(e)[:200]
    return {"status": "ok", "available": available, "findings": findings, "errors": errors}


def _key(f: dict) -> tuple:
    return (f["scanner"], f["rule"], f["message"])


def diff_scans(before: dict, after: dict, target_line: int | list[int] | None = None, tol: int = 3,
               target_rules: list[tuple[str, str]] | None = None) -> dict:
    """Compara o re-scan do original com o do patch.

    * target_rules: regras (scanner, regra) do achado original; se nao vier, sao as que dispararam a +-tol da linha-alvo.
    * 'gone' por regra: a contagem da regra no patch e menor que no original (as linhas mudam com o patch, por isso
      comparamos contagens e nao posicoes).
    * novos achados: multiconjunto (scanner, regra, mensagem) do patch menos o do original; so warning+ contam.
    """
    fb, fa = before.get("findings", []), after.get("findings", [])
    if before.get("status") == "not_verifiable" or after.get("status") == "not_verifiable":
        return {"status": "not_verifiable"}
    if target_rules is None:
        tl = [] if target_line is None else ([target_line] if isinstance(target_line, int) else list(target_line))
        target_rules = sorted({(f["scanner"], f["rule"]) for f in fb if any(abs(f["line"] - x) <= tol for x in tl)})
    cb = Counter((f["scanner"], f["rule"]) for f in fb)
    ca = Counter((f["scanner"], f["rule"]) for f in fa)
    per_rule = {f"{s}:{r}": ca[(s, r)] < cb[(s, r)] for s, r in target_rules}
    new = Counter(_key(f) for f in fa) - Counter(_key(f) for f in fb)
    sev_of = {_key(f): f["severity"] for f in fa}
    new_list = [{"scanner": k[0], "rule": k[1], "message": k[2], "severity": sev_of[k], "n": n} for k, n in new.items()]
    return {"status": "ok", "target_rules": [f"{s}:{r}" for s, r in target_rules], "per_rule_gone": per_rule,
            "target_gone": (all(per_rule.values()) if per_rule else None),
            "any_target_gone": (any(per_rule.values()) if per_rule else None),
            "new_findings": new_list,
            "new_warning_or_worse": sum(x["n"] for x in new_list if SEV_ORDER[x["severity"]] >= SEV_ORDER["warning"])}


def format_tool_report(compile_orig: dict, compile_patch: dict, scan_orig: dict, scan_patch: dict, diff: dict) -> str:
    """Texto compacto que o A3b recebe. Nao contem nada do gabarito: so a saida das ferramentas."""
    def comp(c: dict) -> str:
        if c["status"] in ("not_verifiable", "unavailable"):
            return f"not available ({c.get('reason', c['status'])})"
        return "ok" if c["status"] == "ok" else f"{c['status']} ({c.get('n_errors')} errors: {'; '.join(c.get('errors', [])[:3])})"
    lines = [f"- Syntax check (gcc/g++ -fsyntax-only) of the ORIGINAL: {comp(compile_orig)}",
             f"- Syntax check of the PATCH: {comp(compile_patch)}"]
    if diff.get("status") == "not_verifiable" or not scan_orig.get("available"):
        lines.append("- Static scanners: not available for this language.")
    else:
        av = [k for k, v in scan_orig["available"].items() if v]
        lines.append(f"- Static scanners run: {', '.join(av) or 'none'}. Findings: original {len(scan_orig['findings'])}, patch {len(scan_patch['findings'])}.")
        if diff.get("target_rules"):
            lines.append("- Rules that fired near the reported line in the original: " + ", ".join(diff["target_rules"])
                         + ". Fewer occurrences in the patch: " + ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in diff["per_rule_gone"].items()))
        else:
            lines.append("- No scanner rule fired near the reported line in the original.")
        nw = [x for x in diff.get("new_findings", []) if SEV_ORDER[x["severity"]] >= 1][:6]
        lines.append("- New warning-or-worse findings in the patch: " + ("; ".join(f"{x['scanner']}:{x['rule']} ({x['severity']})" for x in nw) if nw else "none"))
    return "\n".join(lines)
