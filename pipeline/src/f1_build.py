"""F1 - Dados e gabarito. Gera files.jsonl, gt_issues.csv, gt_scanner_fp.csv, paper_labels.csv e o
relatorio de validacao (results/f1_validacao.md). Nao chama LLM.

Uso (da raiz do projeto):  pipeline\\.venv\\Scripts\\python.exe -I pipeline\\src\\f1_build.py
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from canonical import (CANONICAL_IDS, EXPECTED_COUNTS, EXPECTED_FILES, EXPECTED_KNOWN_FP,  # noqa: E402
                       EXPECTED_SHEET_ROWS, KNOWN_DIVERGENT, MODELS, NEVER_DETECTED)
from dataset import (SNAPSHOT_DIRS, build_file_record, detections_for, file_dirs,  # noqa: E402
                     single_detection_of)
from gt import (MODEL_COLS, apply_labels, assign_ids, classify_status, load_overrides,  # noqa: E402
                parse_cwes, read_sheet)
from paper_tables import extract_paper_tables  # noqa: E402

QUALITY_ONLY_CWES = {561, 1164}  # codigo morto / irrelevante: qualidade, nao seguranca (recorte "so seguranca")


def _join(xs) -> str:
    return "|".join(str(x) for x in xs)


def build(raw_root: Path, ods: Path, pdf: Path, overrides_csv: Path) -> dict:
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))

    # ---------------------------------------------------------------- pastas
    recs = []
    for snap in SNAPSHOT_DIRS:
        for fdir in file_dirs(raw_root, snap):
            recs.append(build_file_record(raw_root, snap, fdir))
    per_snap = pd.Series([r["snapshot"] for r in recs]).value_counts().to_dict()
    check("pastas File_XX", per_snap == {"v8": 64, "v10": 51}, f"obtido {per_snap} (Apendice A: 64 e 51)")
    check("codigo identico nos 3 modelos", all(r["code"]["identical_across_models"] for r in recs), "")
    by_file = {(r["snapshot"], r["file_number"]): r for r in recs}

    # ---------------------------------------------------------------- planilha -> rotulos
    sheets = pd.concat([read_sheet(ods, s) for s in ("v8", "v10")], ignore_index=True)
    rows_per = sheets.groupby("snapshot").size().to_dict()
    check("linhas da planilha por aba", rows_per == EXPECTED_SHEET_ROWS, f"obtido {rows_per}, esperado {EXPECTED_SHEET_ROWS}")
    sheets["line_sheet"] = sheets["line"]
    sheets["line_note"] = ""
    for i, r in sheets.iterrows():
        rec = by_file.get((r["snapshot"], r["file_number"]))
        dets, mode = detections_for(rec["detections"] if rec else [], r["line"], r["scanners"])
        if mode == "none":
            one = single_detection_of(rec["detections"], r["scanners"]) if rec else None
            if one is not None:  # linha da planilha nao existe no Info.txt, mas ha uma so deteccao do scanner
                sheets.at[i, "line"] = int(one["line"])
                sheets.at[i, "line_note"] = f"linha da planilha ({r['line']}) ausente no Info.txt; usada a unica deteccao de {one['scanner']} (linha {one['line']})"
        elif mode == "line_only":
            sheets.at[i, "line_note"] = "mesma linha no Info.txt, mas o scanner la e diferente do da planilha"
    df, review = apply_labels(sheets, load_overrides(overrides_csv))
    df = assign_ids(df)
    check("issue_id unico", df["issue_id"].is_unique, "")
    df = classify_status(df)  # levanta erro se faltar algum dos 56 canonicos
    canon_keys = {(r.snapshot, r.issue_number) for r in df.itertuples() if r.issue_id in set(CANONICAL_IDS)}
    unresolved = [r for r in review if not (r["field"] != "is_real" and (r["snapshot"], r["issue_number"]) in canon_keys)]
    check("nenhum veredito/rotulo ficou sem resolver (celulas ambiguas dos 56 issues vem das Tabelas 13/14)",
          not unresolved, f"{len(review) - len(unresolved)} celulas ambiguas resolvidas pelo artigo; pendentes: {unresolved[:3]}")

    # junta linhas da planilha com as deteccoes do Info.txt (codigo da linha, tipos de regra, textos)
    by_file = {(r["snapshot"], r["file_number"]): r for r in recs}
    det_json, src_code, scanner_types, cwe_ids, cwe_src, matched = [], [], [], [], [], []
    for _, r in df.iterrows():
        rec = by_file.get((r["snapshot"], r["file_number"]))
        use, mode = detections_for(rec["detections"] if rec else [], r["line"], r["scanners"])
        matched.append(len(use))
        det_json.append(json.dumps(use, ensure_ascii=False))
        src_code.append(next((d.get("source_code") for d in use if d.get("source_code")), None))
        scanner_types.append(_join(d.get("type") for d in use))
        ids = parse_cwes(r["cwe_type"])
        src = "planilha:CWE type"
        if not ids:
            ids, src = parse_cwes(*[d.get("text") for d in use]), "Info.txt:texto do scanner"
        if not ids:
            ids, src = parse_cwes(r["verdict_raw"]), "planilha:veredito dos autores"
        cwe_ids.append(ids)
        cwe_src.append(src if ids else "nenhuma")
    df["detections_json"], df["source_code"], df["scanner_types"] = det_json, src_code, scanner_types
    df["cwe_ids"], df["cwe_source"], df["n_info_matches"] = cwe_ids, cwe_src, matched
    df["scanners_txt"] = df["scanners"].map(_join)
    unmatched = df[df["n_info_matches"] == 0]
    unmatched_ok = unmatched["issue_id"].tolist() == list(KNOWN_DIVERGENT)  # v8:2/14: o Info.txt dessa pasta nao tem deteccoes
    notes = [(r.issue_id, r.line_note) for r in df.itertuples() if r.line_note]
    check("toda linha da planilha tem deteccao no Info.txt (exceto a divergente v8:2/14)", unmatched_ok,
          f"sem correspondencia: {unmatched['issue_id'].tolist()}; ajustes/avisos: {notes}")

    # ---------------------------------------------------------------- tabelas do artigo
    paper = extract_paper_tables(pdf).set_index("issue_id")
    check("tabelas 13/14 do artigo: 56 issues = lista canonica", set(paper.index) == set(CANONICAL_IDS), "")
    counts_ok, count_detail = True, []
    for m in MODELS:
        for s in ("v8", "v10"):
            p = paper[paper["snapshot"] == s]
            got = (int(p[f"{m}__detected"].sum()), int(p[f"{m}__fixed"].sum()))
            counts_ok &= got == EXPECTED_COUNTS[m][s]
            count_detail.append(f"{m}/{s}={got}")
    check("contadores detectadas/corrigidas do artigo = Apendice A", counts_ok, "; ".join(count_detail))

    # ---------------------------------------------------------------- combina planilha e artigo (CWE e origem)
    # CWE: uniao (planilha primeiro) das CWEs que os autores deram ao mesmo issue na planilha e na Tabela 13/14.
    # Origem: a coluna "Source" do artigo (user / gpt3.5 / gpt4 / llm) cobre todos os 56; a planilha tem lacunas.
    df["cwe_sheet"] = df["cwe_ids"]
    cwe_paper, cwe_union, origin_paper, origin_final = [], [], [], []
    for r in df.itertuples():
        if r.issue_id in paper.index:
            pc = [int(x) for x in re.findall(r"[0-9]+", str(paper.loc[r.issue_id, "paper_cwe"]))]
            po = "user" if paper.loc[r.issue_id, "paper_source"] == "user" else "gpt"
        else:
            pc, po = [], None
        cwe_paper.append(pc)
        cwe_union.append(list(dict.fromkeys(list(r.cwe_sheet) + pc)))
        origin_paper.append(po)
        origin_final.append(po or r.origin)
    df["cwe_paper"], df["cwe_ids"] = cwe_paper, cwe_union
    df["origin_sheet"], df["origin_paper"], df["origin"] = df["origin"], origin_paper, origin_final
    both = df[df["issue_id"].isin(paper.index)]
    cwe_diff = [i for i, a, b in zip(both["issue_id"], both["cwe_sheet"], both["cwe_paper"]) if set(a) != set(b)]
    org_diff = [i for i, a, b in zip(both["issue_id"], both["origin_sheet"], both["origin_paper"])
                if a != "unknown" and a != b]
    org_gap = [i for i, a in zip(both["issue_id"], both["origin_sheet"]) if a == "unknown"]
    check("(informativo) CWE planilha x artigo: diferencas (a uniao e usada no matcher)", True,
          f"{len(cwe_diff)}: {cwe_diff}")
    check("(informativo) origem planilha x artigo: conflitos e lacunas (o artigo prevalece)", True,
          f"conflitos {org_diff}; planilha sem origem {org_gap}")

    # ---------------------------------------------------------------- classes de arquivo
    real = df[df["status"] == "real"]
    kfp = df[df["status"] == "known_fp"]
    div = df[df["status"] == "divergent"]
    check("56 issues reais = lista canonica", set(real["issue_id"]) == set(CANONICAL_IDS) and len(real) == 56, f"{len(real)}")
    check("divergente planilha x artigo = [v8:2/14]", tuple(div["issue_id"]) == KNOWN_DIVERGENT, str(list(div["issue_id"])))
    check("falsos alarmes conhecidos = 85", len(kfp) == EXPECTED_KNOWN_FP, f"{len(kfp)}")
    check("deteccoes da planilha - divergente = 141 (Tabela 12)", len(df) - len(div) == 141, f"{len(df)} - {len(div)}")
    for rec in recs:
        sub = df[(df["snapshot"] == rec["snapshot"]) & (df["file_number"] == rec["file_number"])]
        n_real, n_kfp, n_div = (sub["status"] == s for s in ("real", "known_fp", "divergent"))
        rec["n_sheet_rows"] = len(sub)
        rec["real_issue_ids"] = list(sub.loc[n_real, "issue_id"])
        rec["known_fp_ids"] = list(sub.loc[n_kfp, "issue_id"])
        rec["divergent_ids"] = list(sub.loc[n_div, "issue_id"])
        if n_real.any():
            rec["class"] = "positive"
        elif n_div.any() and not n_kfp.any():
            rec["class"] = "excluded"
        elif len(sub):
            rec["class"] = "negative"
        else:
            rec["class"] = "unlabeled"
        po = [o for o in sub["origin_paper"] if isinstance(o, str) and o]  # NaN (sem dado do artigo) e "verdadeiro"
        so = sub["origin_sheet"].iloc[0] if len(sub) else "unknown"
        rec["origin"] = po[0] if po else so
        rec["origin_source"] = "artigo" if po else ("planilha" if so != "unknown" else "desconhecida")
        rec["language_sheet"] = sub["language"].iloc[0] if len(sub) else None
        rec["origin_llm_name"] = sub["llm_name"].iloc[0] if len(sub) else None
    cls = pd.Series([r["class"] for r in recs]).value_counts().to_dict()
    check("classes de arquivo = 48 positivos / 66 negativos / 1 excluido", cls == EXPECTED_FILES, f"{cls}")
    pos_per = pd.Series([r["snapshot"] for r in recs if r["class"] == "positive"]).value_counts().to_dict()
    check("positivos por aba = 24 e 24", pos_per == {"v8": 24, "v10": 24}, f"{pos_per}")
    lang_bad = [(r["snapshot"], r["file_number"], r["language"], r["language_sheet"]) for r in recs
                if r["language_sheet"] and r["language"] != r["language_sheet"]]
    # informativo: a extensao do arquivo enviado aos LLMs define a linguagem usada no A3b (gcc x g++)
    check("(informativo) extensao do codigo vs linguagem da planilha: diferencas listadas", True,
          f"{len(lang_bad)} diferem (planilha chama de C++ arquivos .c): {lang_bad}")

    # ---------------------------------------------------------------- rotulos finais (paper_labels)
    label_rows, conflicts = [], []
    for _, r in df.iterrows():
        for m in MODELS:
            row = {"issue_id": r["issue_id"], "snapshot": r["snapshot"], "file_number": r["file_number"],
                   "issue_number": r["issue_number"], "status": r["status"], "model": m,
                   "cwe_identified_raw": r[f"{m}__cwe_identified_raw"],
                   "cwe_identified": _join(parse_cwes(r[f"{m}__cwe_identified_raw"]))}
            for f in ("detected", "fixed"):
                sheet_v = r[f"{m}__{f}"]
                paper_v = bool(paper.loc[r["issue_id"], f"{m}__{f}"]) if r["issue_id"] in paper.index else None
                sheet_v = None if (sheet_v is None or (isinstance(sheet_v, float) and pd.isna(sheet_v))) else bool(sheet_v)
                final = paper_v if paper_v is not None else sheet_v
                conflict = ("planilha_sem_rotulo_claro" if (paper_v is not None and sheet_v is None and r[f"{m}__{f}_raw"])
                            else ("difere" if (paper_v is not None and sheet_v is not None and paper_v != sheet_v) else ""))
                row.update({f: final, f"{f}_sheet": sheet_v, f"{f}_paper": paper_v,
                            f"{f}_source": "artigo" if paper_v is not None else ("planilha" if sheet_v is not None else ""),
                            f"{f}_conflict": conflict, f"{f}_raw": r[f"{m}__{f}_raw"]})
                if conflict:
                    conflicts.append({"issue_id": r["issue_id"], "model": m, "field": f, "planilha": sheet_v,
                                      "artigo": paper_v, "conflito": conflict, "texto_planilha": r[f"{m}__{f}_raw"]})
            label_rows.append(row)
    labels = pd.DataFrame(label_rows)
    lr = labels[labels["status"] == "real"]
    nd = [i for i in CANONICAL_IDS if not lr[(lr["issue_id"] == i)]["detected"].any()]
    check("issues nao detectadas por nenhum modelo = Apendice A", sorted(nd) == sorted(NEVER_DETECTED), f"{sorted(nd)}")

    # ---------------------------------------------------------------- saidas
    real = df[df["status"] == "real"].copy()
    real["quality_only"] = real["cwe_ids"].map(lambda ids: bool(ids) and set(ids) <= QUALITY_ONLY_CWES)
    real["paper_source"] = real["issue_id"].map(paper["paper_source"])
    code_of = {k: v["code"]["path"] for k, v in by_file.items()}
    for frame in (real, df[df["status"] == "known_fp"].copy(), div.copy()):
        frame["code_path"] = [code_of[(s, f)] for s, f in zip(frame["snapshot"], frame["file_number"])]

    def fmt(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        for c in ("cwe_ids", "cwe_sheet", "cwe_paper"):
            out[c] = out[c].map(_join)
        cols = ["issue_id", "snapshot", "file_number", "line", "line_sheet", "line_note", "issue_number", "severity",
                "cwe_type", "cwe_ids", "cwe_sheet", "cwe_paper", "cwe_source", "scanners_txt", "scanner_types",
                "origin", "origin_sheet", "origin_paper", "llm_name", "language", "source_code",
                "verdict_raw", "comment", "code_path", "detections_json"] + \
               [c for c in ("quality_only", "paper_source") if c in out.columns]
        return out[cols].rename(columns={"scanners_txt": "scanners", "language": "language_sheet"})

    kfp = df[df["status"] == "known_fp"].copy()
    kfp["code_path"] = [code_of[(s, f)] for s, f in zip(kfp["snapshot"], kfp["file_number"])]
    div = div.copy()
    div["code_path"] = [code_of[(s, f)] for s, f in zip(div["snapshot"], div["file_number"])]
    return {"files": recs, "gt_issues": fmt(real), "gt_scanner_fp": fmt(kfp), "gt_excluded": fmt(div),
            "paper_labels": labels, "conflicts": pd.DataFrame(conflicts), "checks": checks, "df": df,
            "paper": paper.reset_index()}


def nan_to_none(obj):
    """JSON valido: NaN/Infinity (celulas vazias do pandas) viram null."""
    if isinstance(obj, float) and (obj != obj or obj in (float("inf"), float("-inf"))):
        return None
    if isinstance(obj, dict):
        return {k: nan_to_none(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [nan_to_none(v) for v in obj]
    return obj


def write_all(res: dict, data_dir: Path, results_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    with open(data_dir / "files.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in res["files"]:
            f.write(json.dumps(nan_to_none(r), ensure_ascii=False, allow_nan=False) + "\n")
    for name in ("gt_issues", "gt_scanner_fp", "gt_excluded", "paper_labels"):
        res[name].to_csv(data_dir / f"{name}.csv", index=False, encoding="utf-8", lineterminator="\n")
    res["conflicts"].to_csv(data_dir / "label_conflicts.csv", index=False, encoding="utf-8", lineterminator="\n")

    lines = ["# F1 - validacao do gabarito", "", "| # | Verificacao | Resultado | Detalhe |", "|---|---|---|---|"]
    for i, (name, ok, detail) in enumerate(res["checks"], 1):
        lines.append(f"| {i} | {name} | {'OK' if ok else '**FALHOU**'} | {detail} |")
    fl = pd.Series([r["class"] for r in res["files"]]).value_counts()
    lines += ["", "## Arquivos por classe", "", *(f"- {k}: {v}" for k, v in fl.items()), "",
              f"## Conflitos planilha x artigo ({len(res['conflicts'])} celulas)", ""]
    if len(res["conflicts"]):
        lines += ["| issue | modelo | campo | planilha | artigo | tipo | texto da planilha |", "|---|---|---|---|---|---|---|"]
        for c in res["conflicts"].itertuples():
            lines.append(f"| {c.issue_id} | {c.model} | {c.field} | {c.planilha} | {c.artigo} | {c.conflito} | {str(c.texto_planilha)[:90]} |")
    (results_dir / "f1_validacao.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    here = Path(__file__).resolve().parent.parent  # .../pipeline
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(here / "data" / "raw" / "MSc_DataEngineering_Results"))
    ap.add_argument("--pdf", default=str(here.parent / "artigo.pdf"))
    ap.add_argument("--overrides", default=str(here / "data" / "label_overrides.csv"))
    a = ap.parse_args()
    raw = Path(a.raw)
    ods = raw / "DetectAndFix_Data" / "2025_09_24" / "SecurityIssuesAnalysis.ods"
    res = build(raw, ods, Path(a.pdf), Path(a.overrides))
    write_all(res, here / "data", here / "results")
    bad = [c for c in res["checks"] if not c[1]]
    for name, ok, detail in res["checks"]:
        print(("OK     " if ok else "FALHOU ") + name + ("" if ok else f"  -> {detail}"))
    print(f"\n{len(res['files'])} pastas | {len(res['gt_issues'])} issues reais | {len(res['gt_scanner_fp'])} falsos alarmes "
          f"conhecidos | {len(res['gt_excluded'])} excluido | {len(res['conflicts'])} celulas em conflito")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
