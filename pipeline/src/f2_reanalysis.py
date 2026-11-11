"""F2 - Reanalise dos dados do proprio artigo (sem LLM, sem custo).

1. extrai as CWEs citadas em cada LLM_Response.md (3 modelos x 115 pastas) e valida a extracao contra a
   coluna "CWE identified in file" da planilha (v8);
2. indicadores de falso positivo da configuracao do artigo (prompt "You must find security issues...");
3. valida o matcher (o mesmo da F6) contra os rotulos "detected" dos autores: concordancia e kappa de Cohen.

Uso:  pipeline\\.venv\\Scripts\\python.exe -I pipeline\\src\\f2_reanalysis.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from canonical import MODELS  # noqa: E402
from cwe import CWEHierarchy, load_families  # noqa: E402
from dataset import read_text  # noqa: E402
from matching import cwe_mentions, mentions_issue  # noqa: E402

HERE = Path(__file__).resolve().parent.parent          # .../pipeline
DATA, RESULTS = HERE / "data", HERE / "results"
RAW = DATA / "raw" / "MSc_DataEngineering_Results"

# Regra congelada do matcher (ver DIARIO, F2). Edite SO aqui se a validacao pedir ajuste.
CHOSEN = "cwe+ident/prosa (ou)"


def cohen_kappa(y_true: list[bool], y_pred: list[bool]) -> float:
    n = len(y_true)
    tp = sum(t and p for t, p in zip(y_true, y_pred))
    tn = sum((not t) and (not p) for t, p in zip(y_true, y_pred))
    fp = sum((not t) and p for t, p in zip(y_true, y_pred))
    fn = sum(t and (not p) for t, p in zip(y_true, y_pred))
    po = (tp + tn) / n
    pe = ((tp + fn) * (tp + fp) + (fn + tn) * (fp + tn)) / (n * n)
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)


def _ints(s) -> list[int]:
    return [int(x) for x in str(s).split("|") if x not in ("", "nan")] if pd.notna(s) else []


def variants(hier, fams) -> dict[str, dict]:
    return {
        "cwe/igual": dict(mode="cwe"),
        "cwe/+familias": dict(mode="cwe", families=fams),
        "cwe/+hierarquia": dict(mode="cwe", hierarchy=hier, families=fams),
        "cwe/+hierarquia c/ pilares": dict(mode="cwe", hierarchy=hier, families=fams, allow_pillars=True),
        "ident/prosa": dict(mode="ident", ident_scope="prose"),
        "ident/completo": dict(mode="ident", ident_scope="full"),
        "cwe+ident/prosa (ou)": dict(mode="cwe_or_ident", ident_scope="prose", hierarchy=hier, families=fams),
        "cwe+ident/completo (ou)": dict(mode="cwe_or_ident", ident_scope="full", hierarchy=hier, families=fams),
        "cwe+ident/prosa (e)": dict(mode="cwe_and_ident", ident_scope="prose", hierarchy=hier, families=fams),
        "ident+nomes/prosa": dict(mode="ident", ident_scope="prose", ident_names=True),
        "cwe+ident+nomes/prosa (e)": dict(mode="cwe_and_ident", ident_scope="prose", ident_names=True,
                                          hierarchy=hier, families=fams),
        "secao: cwe+ident/prosa (e)": dict(mode="cwe_and_ident", ident_scope="prose", section=True,
                                            hierarchy=hier, families=fams),
        "secao: cwe+ident+nomes/prosa (e)": dict(mode="cwe_and_ident", ident_scope="prose", ident_names=True,
                                                  section=True, hierarchy=hier, families=fams),
        "secao: cwe+ident+nomes/prosa (ou)": dict(mode="cwe_or_ident", ident_scope="prose", ident_names=True,
                                                   section=True, hierarchy=hier, families=fams),
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    RESULTS.mkdir(parents=True, exist_ok=True)
    files = [json.loads(line) for line in open(DATA / "files.jsonl", encoding="utf-8")]
    gt = pd.read_csv(DATA / "gt_issues.csv")
    fp = pd.read_csv(DATA / "gt_scanner_fp.csv")
    labels = pd.read_csv(DATA / "paper_labels.csv")
    hier = CWEHierarchy.from_xml(DATA / "cwe" / "1000.xml")
    fams = load_families(HERE / "matching_families.yaml")
    print(f"hierarquia CWE (view 1000): {len(hier.parents)} fraquezas, "
          f"{sum(1 for a in hier.abstraction.values() if a == 'Pillar')} pilares; {len(fams)} familias")

    # ------------------------------------------------------------ 1. extracao
    resp: dict[tuple, str] = {}
    rows = []
    for rec in files:
        for m in MODELS:
            text = read_text(RAW / rec["models"][m]["response"])
            resp[(rec["snapshot"], rec["file_number"], m)] = text
            cw = cwe_mentions(text)
            rows.append({"snapshot": rec["snapshot"], "file_number": rec["file_number"], "class": rec["class"],
                         "model": m, "n_cwes": len(cw), "cwes": "|".join(map(str, cw)), "chars": len(text)})
    per_file = pd.DataFrame(rows)
    per_file.to_csv(RESULTS / "f2_cwes_por_arquivo.csv", index=False, lineterminator="\n")

    # valida contra a planilha (v8): CWE identified in file, uniao das linhas do arquivo
    sheet = labels[(labels["cwe_identified"].notna()) & (labels["snapshot"] == "v8")]
    sheet_sets = sheet.groupby(["snapshot", "file_number", "model"])["cwe_identified"].apply(
        lambda s: set(int(x) for v in s for x in str(v).split("|") if x))
    cmp_rows = []
    for (snap, fn, m), want in sheet_sets.items():
        got = set(per_file[(per_file.snapshot == snap) & (per_file.file_number == fn) & (per_file.model == m)]["cwes"]
                  .iloc[0].split("|")) - {""}
        got = {int(x) for x in got}
        cmp_rows.append({"snapshot": snap, "file": fn, "model": m, "exact": got == want, "extracted_superset": got >= want,
                         "sheet_superset": want > got, "n_sheet": len(want), "n_extracted": len(got)})
    cmp_df = pd.DataFrame(cmp_rows)
    ext_summary = {"pares (arquivo,modelo) v8 com CWEs na planilha": len(cmp_df),
                   "conjunto igual": int(cmp_df["exact"].sum()),
                   "extraido contem o da planilha": int(cmp_df["extracted_superset"].sum()),
                   "planilha tem CWE que a regex nao achou": int(cmp_df["sheet_superset"].sum())}
    print("\n[1] extracao x planilha:", ext_summary)

    # ------------------------------------------------------------ 3. matcher (antes, p/ usar na 2)
    gt = gt.assign(cwes=gt["cwe_ids"].map(_ints))
    fp = fp.assign(cwes=fp["cwe_ids"].map(_ints))
    lab = labels[labels["status"] == "real"].set_index(["issue_id", "model"])["detected"].astype(bool)
    grid, preds = [], []
    for name, kw in variants(hier, fams).items():
        y_true, y_pred = [], []
        for g in gt.itertuples():
            for m in MODELS:
                r = mentions_issue(resp[(g.snapshot, g.file_number, m)], g.cwes, g.source_code, **kw)
                y_true.append(bool(lab[(g.issue_id, m)]))
                y_pred.append(r["mention"])
                if name == CHOSEN:
                    preds.append({"issue_id": g.issue_id, "model": m, "authors_detected": y_true[-1],
                                  "matcher": r["mention"], "cwe_hit": str(r["cwe_hit"]), "ident_hit": r["ident_hit"]})
        tp = sum(t and p for t, p in zip(y_true, y_pred)); tn = sum((not t) and (not p) for t, p in zip(y_true, y_pred))
        fpn = sum((not t) and p for t, p in zip(y_true, y_pred)); fnn = sum(t and (not p) for t, p in zip(y_true, y_pred))
        grid.append({"variante": name, "n": len(y_true), "acordo": round((tp + tn) / len(y_true), 3),
                     "kappa": round(cohen_kappa(y_true, y_pred), 3), "TP": tp, "FP": fpn, "FN": fnn, "TN": tn})
    grid_df = pd.DataFrame(grid)
    grid_df.to_csv(RESULTS / "f2_matcher_validacao.csv", index=False, lineterminator="\n")
    pd.DataFrame(preds).to_csv(RESULTS / "f2_matcher_predicoes.csv", index=False, lineterminator="\n")
    print("\n[3] matcher x rotulos 'detected' dos autores (56 issues x 3 modelos = 168 pares):")
    print(grid_df.to_string(index=False))

    # ------------------------------------------------------------ 2. indicadores de falso positivo
    # O casamento por texto livre NAO atingiu kappa >= 0,7 (ver grade acima). Por isso os indicadores que dependem
    # dele saem como INTERVALO: limite superior = regra leniente (CWE ou identificador), limite inferior = regra
    # estrita (CWE e identificador, ambos na prosa). Os indicadores por arquivo nao dependem do matcher.
    LENIENT, STRICT = "cwe+ident/prosa (ou)", "cwe+ident/prosa (e)"
    kw_len, kw_str = variants(hier, fams)[LENIENT], variants(hier, fams)[STRICT]
    cls = {(r["snapshot"], r["file_number"]): r["class"] for r in files}
    n_real_total = len(gt)

    def rate(hits):
        return f"{sum(hits)}/{len(hits)} ({100 * sum(hits) / len(hits):.1f}%)"

    out = []
    for m in MODELS:
        pf = per_file[(per_file.model == m) & (per_file["class"].isin(["positive", "negative"]))]
        pos, neg = pf[pf["class"] == "positive"], pf[pf["class"] == "negative"]
        row = {"modelo": m, "arquivos": len(pf),
               "CWEs/arquivo (todos)": round(pf.n_cwes.mean(), 2),
               "CWEs/arquivo (positivos, n=%d)" % len(pos): round(pos.n_cwes.mean(), 2),
               "CWEs/arquivo (negativos, n=%d)" % len(neg): round(neg.n_cwes.mean(), 2),
               "% negativos com >=1 CWE": round(100 * (neg.n_cwes >= 1).mean(), 1),
               "% positivos com >=1 CWE": round(100 * (pos.n_cwes >= 1).mean(), 1),
               "razao de alarmes (CWEs citadas / 56 issues)": round(pf.n_cwes.sum() / n_real_total, 2)}
        for label, kw in (("estrita", kw_str), ("leniente", kw_len)):
            kfp_hit = [mentions_issue(resp[(f.snapshot, f.file_number, m)], f.cwes, f.source_code, **kw)["mention"]
                       for f in fp.itertuples()]
            kfp_neg = [h for h, f in zip(kfp_hit, fp.itertuples()) if cls[(f.snapshot, f.file_number)] == "negative"]
            real_hit = [mentions_issue(resp[(g.snapshot, g.file_number, m)], g.cwes, g.source_code, **kw)["mention"]
                        for g in gt.itertuples()]
            row[f"falsos alarmes conhecidos citados / 85 [{label}]"] = rate(kfp_hit)
            row[f"... so em arquivos negativos [{label}]"] = rate(kfp_neg)
            row[f"issues reais citadas / 56 [{label}]"] = rate(real_hit)
        row["issues reais detectadas segundo os autores / 56"] = int(labels[(labels.status == "real") & (labels.model == m)]["detected"].sum())
        out.append(row)
    fp_df = pd.DataFrame(out)
    fp_df.to_csv(RESULTS / "f2_fp_artigo.csv", index=False, lineterminator="\n")
    print("\n[2] indicadores de falso positivo da configuracao do artigo (intervalo estrita..leniente):")
    print(fp_df.set_index("modelo").T.to_string(header=True))

    # ------------------------------------------------------------ vizinhanca de linhas no gabarito (regra +-3)
    allrows = pd.concat([gt.assign(kind="real"), fp.assign(kind="known_fp")], ignore_index=True)
    near = 0
    for (_, _), g in allrows.groupby(["snapshot", "file_number"]):
        lines = g["line"].tolist()
        near += sum(1 for i in range(len(lines)) for j in range(i + 1, len(lines)) if abs(lines[i] - lines[j]) <= 3)
    print(f"\npares de linhas do gabarito a <= 3 linhas no mesmo arquivo: {near} (ambiguidade possivel na regra +-3)")

    best = grid_df.sort_values("kappa", ascending=False).iloc[0]
    md = ["# F2 - reanalise dos dados do artigo", "",
          f"**Validacao do matcher de texto livre: NAO atingiu a meta (kappa >= 0,7).** Melhor variante: "
          f"`{best.variante}` com kappa = {best.kappa} (acordo {best.acordo}). A regra do plano "
          f"(`{CHOSEN}`) deu kappa = {grid_df[grid_df.variante == CHOSEN].iloc[0].kappa}.", "",
          "## Extracao de CWEs x planilha (v8)", "", *(f"- {k}: {v}" for k, v in ext_summary.items()), "",
          "## Validacao do matcher (variantes, 56 issues x 3 modelos = 168 pares)", "", grid_df.to_markdown(index=False), "",
          "## Indicadores de falso positivo (configuracao original do artigo)", "",
          "Indicadores por arquivo nao dependem do matcher; os demais saem como intervalo estrita..leniente.", "",
          fp_df.set_index("modelo").T.to_markdown(), "",
          f"Pares de linhas do gabarito a <= 3 linhas no mesmo arquivo: {near}."]
    (RESULTS / "f2_resumo.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    ok = best.kappa >= 0.7
    print("\nMETA kappa >= 0.7:", "atingida" if ok else f"NAO atingida (melhor = {best.kappa} em '{best.variante}')")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
