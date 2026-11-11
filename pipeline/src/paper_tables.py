"""Tabelas 13 e 14 do artigo (deteccao Dt e correcao Fx por issue e por modelo), extraidas do PDF.

Servem para (1) validar a normalizacao dos rotulos da planilha e (2) apontar onde a planilha dos
autores e o artigo publicado discordam. Nenhum agente do pipeline recebe estes valores.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROW = re.compile(r"^(?P<id>\d+/\d+[ab]?)\s+(?P<mid>.+?)\s+(?P<marks>(?:Yes|No)(?:\s+(?:Yes|No)){5})\s*$")
MODEL_ORDER = ("gpt-4.1", "gpt-5", "opus-4.1")  # colunas do artigo: (Dt Fx) para cada modelo


def parse_table_text(text: str, snapshot: str) -> list[dict]:
    """Linhas de dados de uma tabela ('N/L CWE Lang. Source Scanner Severity  Dt Fx Dt Fx Dt Fx')."""
    rows = []
    for line in text.splitlines():
        m = ROW.match(line.strip())
        if not m:
            continue
        marks = [x == "Yes" for x in m.group("marks").split()]
        mid = m.group("mid").split()
        rec = {"snapshot": snapshot, "issue_id": f"{snapshot}:{m.group('id')}", "paper_cwe": mid[0],
               "paper_lang": mid[1], "paper_source": mid[2], "paper_scanner_severity": " ".join(mid[3:])}
        for i, model in enumerate(MODEL_ORDER):
            rec[f"{model}__detected"], rec[f"{model}__fixed"] = marks[2 * i], marks[2 * i + 1]
        rows.append(rec)
    return rows


def extract_paper_tables(pdf_path: str | Path) -> pd.DataFrame:
    """Le o PDF e devolve uma linha por issue (56 no total)."""
    import pypdf

    reader = pypdf.PdfReader(str(pdf_path))
    pages = [p.extract_text() or "" for p in reader.pages]
    full = "\n".join(pages)
    i13 = full.index("Table 13 Security issues detection")
    i14 = full.index("Table 14 Security issues detection")
    end14 = i14 + full[i14:].index("Table 15")  # as Tabelas 17/18 (outro recorte) vem depois e nao entram aqui
    rows = parse_table_text(full[i13:i14], "v8") + parse_table_text(full[i14:end14], "v10")
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- Tabela 11 (experimento de 2024, GPT-4o)
_T11_START = re.compile(r"^(?P<id>\d+/\d+[ab]?)\s+(?P<rest>.*)$")
_T11_END = re.compile(r"^(?P<mid>.*?)\s+(?P<det>Yes|No)\s+(?P<fix>Yes|No)\s*$")


def parse_table11_text(text: str) -> list[dict]:
    """Linhas da Tabela 11. Algumas linhas quebram ('semgrep,\nflawfinder\nerror,\nwarning\nNo No'):
    junta as linhas ate encontrar o par final 'Yes|No Yes|No'."""
    rows, cur_id, buf = [], None, []
    for raw in text.splitlines():
        line = raw.strip()
        m = _T11_START.match(line)
        if m and not (cur_id and not _T11_END.match(" ".join(buf))):
            cur_id, buf = m.group("id"), [m.group("rest")]
        elif cur_id:
            buf.append(line)
        else:
            continue
        end = _T11_END.match(" ".join(buf))
        if end:
            mid = end.group("mid").split()
            rows.append({"issue_id": f"v8:{cur_id}", "cwe": mid[0], "lang": mid[1], "source": mid[2],
                         "detected": end.group("det") == "Yes", "fixed": end.group("fix") == "Yes"})
            cur_id, buf = None, []
    return rows


def extract_table11(pdf_path: str | Path) -> pd.DataFrame:
    import pypdf

    reader = pypdf.PdfReader(str(pdf_path))
    full = "\n".join(p.extract_text() or "" for p in reader.pages)
    i = full.index("Table 11 Security issues detection")
    j = full.index("Page 19 of 38", i)
    body = full[i:j]
    body = body[body.index("GPT-4o \nFixed") + 1:] if "GPT-4o \nFixed" in body else body
    return pd.DataFrame(parse_table11_text(body))
