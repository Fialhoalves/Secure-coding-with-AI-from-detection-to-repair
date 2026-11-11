"""Gabarito a partir de SecurityIssuesAnalysis.ods (planilha dos autores, rotulos de 2025).

Nada aqui chama LLM. As funcoes sao puras, para poder testar com fixtures pequenas.
"""
from __future__ import annotations

import csv
import re
import string
import warnings
from pathlib import Path

import pandas as pd

from canonical import CANONICAL_IDS, MODELS

SHEETS = {"v8": "DevGPT v8", "v10": "DevGPT v10"}

BASE_COLS = {0: "file_number", 1: "link", 2: "language", 3: "origin_raw", 4: "llm_name", 5: "issue_number",
             6: "severity", 7: "line", 8: "cwe_type", 9: "scanners", 10: "verdict_raw"}
# (detected, fixed, cwe_identified) de cada modelo; a planilha tem o mesmo layout em v8 e v10.
MODEL_COLS = {"gpt-4.1": (11, 12, 13), "gpt-5": (14, 15, 16), "opus-4.1": (17, 18, 19)}
COMMENT_COL = 20


# --------------------------------------------------------------------------- texto
def clean(v) -> str | None:
    """Texto de uma celula: None se vazia; espacos colapsados."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = " ".join(str(v).split())
    return s or None


def norm_for_match(text: str | None) -> str:
    """Minusculas, aspas tipograficas e caractere de substituicao viram apostrofo, espacos colapsados."""
    text = clean(text)
    if not text:
        return ""
    t = text.lower()
    for ch in (chr(0xFFFD), chr(0x2019), chr(0x2018)):  # caractere de substituicao e aspas tipograficas
        t = t.replace(ch, "'")
    return " ".join(t.split())


def parse_cwes(*texts: str | None) -> list[int]:
    """Numeros de CWE citados nos textos (ordem de aparicao, sem repeticao)."""
    seen: list[int] = []
    for t in texts:
        for m in re.finditer(r"CWE[-\s]?(\d+)", clean(t) or "", flags=re.I):
            n = int(m.group(1))
            if n not in seen:
                seen.append(n)
    return seen


def classify_verdict(text: str | None) -> str:
    """'real' | 'not_real' | 'review' para a coluna 'Is this detect actual security problem?'.

    Regra do plano (F1 item 3): comeca com 'Yes' -> real; comeca com 'No'/'Not', ou contem
    'not security issue' / 'not an issue' -> not_real; qualquer outro caso -> revisao manual.
    """
    t = norm_for_match(text)
    if not t:
        return "review"
    if re.match(r"yes\b", t):
        return "real"
    if re.match(r"(no|not)\b", t):
        return "not_real"
    if "not security issue" in t or "not an issue" in t:
        return "not_real"
    return "review"


def classify_yesno(text: str | None) -> bool | None | str:
    """True/False para textos que comecam com Yes / No|Not; None se vazio; 'review' nos demais."""
    t = norm_for_match(text)
    if not t:
        return None
    if re.match(r"yes\b", t):
        return True
    if re.match(r"(no|not)\b", t):
        return False
    return "review"


# --------------------------------------------------------------------------- overrides
def load_overrides(path: Path | None) -> dict[tuple, tuple[str, str]]:
    """label_overrides.csv -> {(snapshot, issue_number, model, field): (value, reason)}.

    field: is_real | detected | fixed. value: real|not_real (is_real) ou yes|no (detected, fixed).
    Cada linha traz a justificativa, para a decisao ficar rastreavel.
    """
    out: dict[tuple, tuple[str, str]] = {}
    if path is None or not Path(path).exists():
        return out
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = (r["snapshot"], int(r["issue_number"]), (r.get("model") or "").strip(), r["field"].strip())
            if key in out:
                raise ValueError(f"override duplicado: {key}")
            out[key] = (r["value"].strip(), r["reason"].strip())
    return out


# --------------------------------------------------------------------------- planilha
def _check_layout(raw: pd.DataFrame, h1: int, snapshot: str) -> None:
    group, sub = raw.iloc[h1], raw.iloc[h1 + 1]
    g = lambda c: norm_for_match(clean(group.iat[c]))  # noqa: E731
    s = lambda c: norm_for_match(clean(sub.iat[c]))    # noqa: E731
    ok = (g(11) in ("chatgpt-4.1", "chatgpt-4o") and g(14) == "chatgpt-5" and g(17).startswith("claude")
          and "4.1" in g(17) and s(10).startswith("is this detect actual") and s(8) == "cwe type"
          and all(s(c).startswith("was issue detected") for c in (11, 14, 17))
          and all(s(c) == "was issue fixed?" for c in (12, 15, 18))
          and all(s(c) == "cwe identified in file" for c in (13, 16, 19)))
    if not ok:
        raise ValueError(f"layout inesperado na aba {snapshot}: {[g(c) for c in (11, 14, 17)]}")


def read_sheet(path: str | Path, snapshot: str) -> pd.DataFrame:
    """Le uma aba (2 linhas de cabecalho; 'File number' vazio = continuacao do arquivo anterior).

    Devolve um DataFrame com uma linha por deteccao de scanner julgada pelos autores.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        raw = pd.read_excel(path, sheet_name=SHEETS[snapshot], header=None, engine="odf", dtype=object)
    h1 = next(i for i in range(len(raw)) if clean(raw.iat[i, 0]) == "File number")
    _check_layout(raw, h1, snapshot)

    rows, current_file, current_lang, current_origin = [], None, None, None
    for r in range(h1 + 2, len(raw)):
        row = raw.iloc[r]
        issue_number = clean(row.iat[5])
        if issue_number is None or not re.fullmatch(r"\d+", issue_number):
            continue  # linhas em branco ou perdidas no fim da aba
        if clean(row.iat[0]) is not None:  # nova pasta (celula mesclada: so a 1a linha traz o numero)
            current_file = int(float(clean(row.iat[0])))
            lang = clean(row.iat[2])
            current_lang = lang.replace(chr(0x0421), "C") if lang else lang  # 'C' cirilico digitado na planilha
            current_origin = clean(row.iat[3])
        rec = {"snapshot": snapshot, "sheet_row": r + 1, "file_number": current_file,
               "language": current_lang, "origin_raw": current_origin,
               "llm_name": clean(row.iat[4]), "issue_number": int(issue_number),
               "severity": clean(row.iat[6]), "line": int(float(clean(row.iat[7]))),
               "cwe_type": clean(row.iat[8]),
               "scanners": [s.strip().lower() for s in (clean(row.iat[9]) or "").split(",") if s.strip()],
               "verdict_raw": clean(row.iat[10]), "comment": clean(row.iat[COMMENT_COL])}
        for m, (cd, cf, cc) in MODEL_COLS.items():
            rec[f"{m}__detected_raw"] = clean(row.iat[cd])
            rec[f"{m}__fixed_raw"] = clean(row.iat[cf])
            rec[f"{m}__cwe_identified_raw"] = clean(row.iat[cc])
        rows.append(rec)
    return pd.DataFrame(rows)


def origin_of(origin_raw: str | None) -> str:
    """'gpt' (codigo gerado pelo ChatGPT), 'user' ou 'unknown', conforme a planilha."""
    t = norm_for_match(origin_raw)
    return {"yes": "gpt", "no": "user"}.get(t, "unknown")


def apply_labels(df: pd.DataFrame, overrides: dict | None = None) -> tuple[pd.DataFrame, list[dict]]:
    """Normaliza veredito, detected e fixed. Devolve (df, pendencias de revisao manual)."""
    overrides = overrides or {}
    df = df.copy()
    review: list[dict] = []
    used = set()

    def resolve(key, auto, kind):
        if key in overrides:
            used.add(key)
            return overrides[key][0], "override"
        return auto, kind

    verdicts, sources = [], []
    for _, r in df.iterrows():
        auto = classify_verdict(r["verdict_raw"])
        val, src = resolve((r["snapshot"], r["issue_number"], "", "is_real"), auto, "rule")
        if val == "review":
            review.append({"snapshot": r["snapshot"], "issue_number": r["issue_number"], "file": r["file_number"],
                           "line": r["line"], "field": "is_real", "text": r["verdict_raw"]})
        verdicts.append(val)
        sources.append(src)
    df["is_real_label"], df["is_real_source"] = verdicts, sources

    for m in MODEL_COLS:
        for field in ("detected", "fixed"):
            vals = []
            for _, r in df.iterrows():
                auto = classify_yesno(r[f"{m}__{field}_raw"])
                key = (r["snapshot"], r["issue_number"], m, field)
                if key in overrides:
                    used.add(key)
                    v = {"yes": True, "no": False}[overrides[key][0]]
                else:
                    v = auto
                if v == "review":
                    review.append({"snapshot": r["snapshot"], "issue_number": r["issue_number"],
                                   "file": r["file_number"], "line": r["line"], "field": f"{m}.{field}",
                                   "text": r[f"{m}__{field}_raw"]})
                    v = None
                vals.append(v)
            df[f"{m}__{field}"] = vals
    unused = set(overrides) - used
    if unused:
        raise ValueError(f"overrides sem uso (chave errada?): {sorted(unused)}")
    df["origin"] = df["origin_raw"].map(origin_of)
    return df, review


def assign_ids(df: pd.DataFrame) -> pd.DataFrame:
    """issue_id = '<snap>:<arquivo>/<linha>' (+ 'a','b',... se houver varias na mesma linha e classe)."""
    df = df.copy()
    ids = []
    grp = df.groupby(["snapshot", "file_number", "line", "is_real_label"], sort=False)
    sizes = grp["issue_number"].transform("size")
    rank = grp.cumcount()
    for (_, r), n, k in zip(df.iterrows(), sizes, rank):
        suffix = string.ascii_lowercase[k] if n > 1 else ""
        ids.append(f"{r['snapshot']}:{r['file_number']}/{r['line']}{suffix}")
    df["issue_id"] = ids
    return df


def classify_status(df: pd.DataFrame, canonical=CANONICAL_IDS) -> pd.DataFrame:
    """status: 'real' (esta na lista canonica), 'known_fp' (autores: nao e problema),
    'divergent' (planilha diz real, mas o artigo nao conta). Falha se faltar algum canonico."""
    df = df.copy()
    canon = set(canonical)
    status = []
    for _, r in df.iterrows():
        if r["is_real_label"] == "real":
            status.append("real" if r["issue_id"] in canon else "divergent")
        elif r["is_real_label"] == "not_real":
            status.append("known_fp")
        else:
            status.append("review")
    df["status"] = status
    missing = canon - set(df.loc[df["status"] == "real", "issue_id"])
    if missing:
        raise ValueError(f"issues canonicas ausentes na planilha: {sorted(missing)}")
    return df
