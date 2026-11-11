"""Ferramentas do A3b e da avaliacao: compilacao (sintaxe) e re-scan. `ToolRunner` (real, com cache em disco)
e `FakeTools` (dry-run/testes; nenhum processo externo)."""
from __future__ import annotations

import hashlib

from cache import DiskCache, make_key
from tools import compile as comp
from tools import scan


class ToolRunner:
    def __init__(self, cache: DiskCache | None = None, **scan_kw):
        self.cache, self.scan_kw = cache, scan_kw
        self.versions = {"gcc": comp.tool_version("gcc"), "g++": comp.tool_version("g++"),
                         "cppcheck": comp.tool_version("cppcheck"), "flawfinder": comp.tool_version(scan.FLAWFINDER_BIN),
                         "semgrep": comp.tool_version("semgrep"), "semgrep_config": scan.SEMGREP_CONFIG}

    def _cached(self, kind: str, code: str, lang: str, fn):
        if self.cache is None:
            return fn()
        key = make_key(tool=kind, versions=self.versions, lang=lang, code=hashlib.sha256(code.encode()).hexdigest())
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        res = fn()
        self.cache.put(key, res)
        return res

    def compile(self, code: str, lang: str) -> dict:
        return self._cached("compile", code, lang, lambda: comp.syntax_check(code, lang))

    def scan(self, code: str, lang: str) -> dict:
        return self._cached("scan", code, lang, lambda: scan.run_scanners(code, lang, **self.scan_kw))


class FakeTools:
    """Deterministico: 'compila' se o codigo tem '{' e '}' balanceados; um achado de flawfinder por strcpy/gets."""

    versions = {"fake": "1"}

    def compile(self, code: str, lang: str) -> dict:
        if lang == "C#":
            return {"status": "not_verifiable", "reason": "C#", "n_errors": None, "errors": []}
        ok = code.count("{") == code.count("}")
        return {"status": "ok" if ok else "error", "rc": 0 if ok else 1, "n_errors": 0 if ok else 1,
                "errors": [] if ok else ["snippet:1: error: unbalanced braces"], "cmd": "fake"}

    def scan(self, code: str, lang: str) -> dict:
        if lang == "C#":
            return {"status": "not_verifiable", "available": {}, "findings": [], "errors": {}}
        f = []
        for i, ln in enumerate(code.splitlines(), 1):
            for tok, rule in (("strcpy(", "FF1001"), ("gets(", "FF1002"), ("scanf(", "FF1003")):
                if tok in ln and "n" + tok not in ln:   # 'strncpy(' nao conta como 'strcpy('
                    f.append({"scanner": "flawfinder", "line": i, "severity": "error", "rule": rule, "cwe": [120], "message": tok})
        return {"status": "ok", "available": {"flawfinder": True, "cppcheck": False, "semgrep": False}, "findings": f, "errors": {}}
