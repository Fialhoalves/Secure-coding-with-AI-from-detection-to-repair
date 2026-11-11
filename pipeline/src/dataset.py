"""Leitura do repositorio dos autores: pastas File_XX, Info.txt, codigo enviado aos LLMs.

Os dados sao nao confiaveis: este modulo so LE texto. Nada e executado ou compilado aqui.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from pathlib import Path

from canonical import MODELS

SNAPSHOT_DIRS = {"v8": "DevGPT_v8_snapshot_20231012", "v10": "DevGPT_v10_snapshot_20240514"}
DATA_SUBDIR = Path("DetectAndFix_Data") / "2025_09_24"
EXT_LANG = {".c": "C", ".cpp": "C++", ".cs": "C#"}
LONG_PREFIX = chr(92) * 2 + "?" + chr(92)  # prefixo de caminho longo do Windows (barra dupla, ?, barra)


def long_path(p: str | Path) -> str:
    """No Windows, caminhos > 260 caracteres (pastas 'Sharing_<titulo>' em cirilico/chines) exigem o prefixo."""
    p = os.path.abspath(str(p))
    if os.name != "nt" or p.startswith(LONG_PREFIX):
        return p
    return LONG_PREFIX + p


def read_text(p: str | Path) -> str:
    with open(long_path(p), encoding="utf-8", errors="replace") as f:
        return f.read()


def sha256_of(p: str | Path) -> str:
    with open(long_path(p), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def posix_rel(p: str | Path, root: str | Path) -> str:
    return Path(os.path.relpath(str(p), str(root))).as_posix()


# --------------------------------------------------------------------------- Info.txt
def parse_info(text: str) -> dict:
    """Info.txt: 'File name:', 'Scanners:' e o JSON 'Detect info from scanners:'."""
    name = re.search(r"^File name:\s*(.+?)\s*$", text, re.M)
    scanners = re.search(r"^Scanners:\s*(\[.*\])\s*$", text, re.M)
    dets = re.search(r"Detect info from scanners:\s*(\[.*\])", text, re.S)
    return {
        "scanned_file": name.group(1) if name else None,
        "scanners": ast.literal_eval(scanners.group(1)) if scanners else [],
        "detections": json.loads(dets.group(1)) if dets else [],
    }


def parse_source_info(text: str) -> dict:
    url = re.search(r"^Url:\s*(.+?)\s*$", text, re.M)
    return {"source_url": url.group(1) if url else None}


def detections_for(info_dets: list[dict], line: int, scanners: list[str] | None = None) -> tuple[list[dict], str]:
    """Deteccoes do Info.txt para uma linha da planilha.

    Devolve (deteccoes, modo): 'strict' = mesma linha e scanner listado; 'line_only' = mesma linha mas o
    scanner difere (a planilha troca nomes de scanner em alguns casos); 'none' = nada naquela linha.
    """
    on_line = [d for d in info_dets if int(d.get("line", -1)) == int(line)]
    want = {s.lower() for s in (scanners or [])}
    strict = [d for d in on_line if str(d.get("scanner", "")).lower() in want]
    if strict:
        return strict, "strict"
    return on_line, ("line_only" if on_line else "none")


def single_detection_of(info_dets: list[dict], scanners: list[str]) -> dict | None:
    """A unica deteccao do Info.txt feita por um dos scanners listados (None se zero ou varias)."""
    want = {s.lower() for s in scanners}
    cands = [d for d in info_dets if str(d.get("scanner", "")).lower() in want]
    return cands[0] if len(cands) == 1 else None


# --------------------------------------------------------------------------- pastas
def file_dirs(raw_root: Path, snapshot: str) -> list[Path]:
    base = raw_root / DATA_SUBDIR / SNAPSHOT_DIRS[snapshot]
    names = [d for d in os.listdir(long_path(base)) if re.fullmatch(r"File_\d+", d)]
    return [base / d for d in sorted(names, key=lambda s: int(s.split("_")[1]))]


def build_file_record(raw_root: Path, snapshot: str, fdir: Path) -> dict:
    """Registro de uma pasta File_XX. O codigo enviado aos LLMs e o Code_* dentro de LLMs/<modelo>/."""
    info = parse_info(read_text(fdir / "Info.txt"))
    src = parse_source_info(read_text(fdir / "source_data_info.txt")) if (fdir / "source_data_info.txt").exists() \
        else {"source_url": None}
    rec = {"snapshot": snapshot, "folder": fdir.name, "file_number": int(fdir.name.split("_")[1]),
           "rel_dir": posix_rel(fdir, raw_root), **info, **src, "models": {}}
    codes = {}
    for key, mdir in MODELS.items():
        d = fdir / "LLMs" / mdir
        names = sorted(os.listdir(long_path(d)))
        code_files = [n for n in names if n.startswith("Code_")]
        if len(code_files) != 1:
            raise ValueError(f"{d}: esperado 1 arquivo Code_*, achei {code_files}")
        codes[key] = (d / code_files[0], sha256_of(d / code_files[0]))
        rec["models"][key] = {
            "dir": posix_rel(d, raw_root),
            "code": posix_rel(d / code_files[0], raw_root),
            "prompt": posix_rel(d / "OurPrompt.txt", raw_root),
            "response": posix_rel(d / "LLM_Response.md", raw_root),
            "new_code": [posix_rel(d / n, raw_root) for n in names if n.startswith("New_generated_code_")],
        }
        for must in ("OurPrompt.txt", "LLM_Response.md"):
            if must not in names:
                raise ValueError(f"{d}: falta {must}")
    hashes = {h for _, h in codes.values()}
    ref_path, ref_hash = codes["gpt-4.1"]
    text = read_text(ref_path)
    ext = ref_path.suffix.lower()
    rec["code"] = {"path": rec["models"]["gpt-4.1"]["code"], "name": ref_path.name, "ext": ext,
                   "sha256": ref_hash, "n_lines": len(text.splitlines()), "n_chars": len(text),
                   "identical_across_models": len(hashes) == 1}
    rec["language"] = EXT_LANG.get(ext)
    return rec
