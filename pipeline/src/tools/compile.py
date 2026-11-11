"""Verificacao de sintaxe com gcc/g++ (-fsyntax-only). NUNCA executa o codigo: so checa a sintaxe.
C#: sem compilador no ambiente; marcado como 'not_verifiable' (sao poucos casos)."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

ERR_LINE = "error"


def tool_version(exe: str, run=subprocess.run) -> str | None:
    if shutil.which(exe) is None:
        return None
    try:
        out = run([exe, "--version"], capture_output=True, text=True, timeout=10).stdout
        return (out.splitlines() or [""])[0].strip() or None
    except Exception:  # noqa: BLE001
        return None


def syntax_check(code: str, lang: str, *, run=subprocess.run, timeout: int = 30) -> dict:
    """{'status': 'ok'|'error'|'not_verifiable'|'unavailable'|'timeout', 'n_errors', 'errors': [...], 'cmd': ...}."""
    if lang == "C#":
        return {"status": "not_verifiable", "reason": "C# nao tem compilador neste ambiente", "n_errors": None, "errors": []}
    exe, std, x, ext = ("gcc", "-std=c11", "c", ".c") if lang == "C" else ("g++", "-std=c++17", "c++", ".cpp")
    if shutil.which(exe) is None and run is subprocess.run:
        return {"status": "unavailable", "reason": f"{exe} nao encontrado", "n_errors": None, "errors": []}
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / f"snippet{ext}"
        src.write_text(code, encoding="utf-8")
        cmd = [exe, std, "-fsyntax-only", "-x", x, src.name]
        try:
            p = run(cmd, cwd=d, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "n_errors": None, "errors": [], "cmd": " ".join(cmd)}
    errors = [ln.strip() for ln in (p.stderr or "").splitlines() if f": {ERR_LINE}:" in ln or ": fatal error:" in ln]
    return {"status": "ok" if p.returncode == 0 else "error", "rc": p.returncode, "n_errors": len(errors),
            "errors": errors[:10], "cmd": " ".join(cmd)}
