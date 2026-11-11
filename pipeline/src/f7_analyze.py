"""F6 + F7 - correspondencia dos achados com o gabarito e metricas/estatistica da execucao principal. Sem LLM, sem GPU.

Entrada: pipeline/runs/<config>/<rep>/<arquivo>.json (saida da F5, uma metade de cada kernel ja mesclada).
Saidas (pipeline/results/): f6_findings.csv (cada achado aceito e sua classe), metrics.csv, tests.csv, f7_resultados.md.

Uso:  pipeline\\.venv\\Scripts\\python.exe -I pipeline\\src\\f7_analyze.py [--rep main] [--n-boot 2000]

Regra principal = linha +-3 e CWE compativel; "uncertain" do verificador = rejeitado.
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import metrics as mt  # noqa: E402
from cwe import CWEHierarchy, load_families  # noqa: E402
from stats import (cluster_bootstrap, cochran_q, holm, mcnemar_exact, mean_sd, paired_bootstrap_diff)  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
DATA, RESULTS, RUNS = HERE / "data", HERE / "results", HERE / "runs"
CONFIGS = ["B0", "B1", "C1", "C2", "C3"]

# contagens por arquivo; todas as metricas sao funcoes da SOMA destas colunas (bootstrap por cluster = reamostrar arquivos)
COLS = ["acc_real", "n_real", "acc_fp", "n_fp", "flag_pos", "n_pos", "flag_neg", "n_neg", "out_pos", "out_neg",
        "new_tp", "new_fp", "out", "n_find"]
IDX = {c: i for i, c in enumerate(COLS)}


def _div(a: float, b: float) -> float:
    return a / b if b else float("nan")


def metric_value(name: str, s) -> float:
    """Valor de uma metrica a partir do vetor de somas (na ordem de COLS)."""
    g = lambda c: float(s[IDX[c]])  # noqa: E731
    if name in ("recall", "false_alarm_rate", "precision", "f1", "f05", "mcc"):
        return mt.labeled_metrics(int(g("acc_real")), int(g("acc_fp")), int(g("n_real")), int(g("n_fp")))[name]
    return {
        "file_sensitivity": lambda: _div(g("flag_pos"), g("n_pos")),
        "neg_files_flagged_frac": lambda: _div(g("flag_neg"), g("n_neg")),
        "out_per_file_pos": lambda: _div(g("out_pos"), g("n_pos")),
        "out_per_file_neg": lambda: _div(g("out_neg"), g("n_neg")),
        "findings_per_file": lambda: _div(g("n_find"), g("n_pos") + g("n_neg")),
        "precision_overall_low": lambda: _div(g("new_tp"), g("new_tp") + g("new_fp") + g("out")),
        "precision_overall_high": lambda: _div(g("new_tp") + g("out"), g("new_tp") + g("new_fp") + g("out")),
    }[name]()


MAIN_METRICS = ["recall", "false_alarm_rate", "precision", "f1", "f05", "mcc"]
DESC_METRICS = ["file_sensitivity", "neg_files_flagged_frac", "out_per_file_pos", "out_per_file_neg", "findings_per_file",
                "precision_overall_low", "precision_overall_high"]


def subset_gt(gt: mt.GT, files: set[str]) -> mt.GT:
    return mt.GT([i for i in gt.issues if i["file"] in files], [i for i in gt.fps if i["file"] in files],
                 {k: v for k, v in gt.file_class.items() if k in files})


def file_counts(ev: mt.RunEval, gt: mt.GT, only_security: bool = False) -> pd.DataFrame:
    """Uma linha por arquivo analisado, com as colunas COLS (indice = id do arquivo, ordenado)."""
    file_of = {i["id"]: i["file"] for i in gt.issues} | {i["id"]: i["file"] for i in gt.fps}
    ar, af = Counter(file_of[i] for i in ev.accused_real), Counter(file_of[i] for i in ev.accused_fp)
    n_real = Counter(i["file"] for i in gt.issues if not (only_security and i["quality_only"]))
    n_fp = Counter(i["file"] for i in gt.fps)
    rows = []
    for r in ev.per_file.itertuples():
        pos, flag = r.cls == "positive", r.n_findings > 0
        rows.append({"file": r.file, "acc_real": ar[r.file], "n_real": n_real[r.file], "acc_fp": af[r.file], "n_fp": n_fp[r.file],
                     "flag_pos": int(flag and pos), "n_pos": int(pos), "flag_neg": int(flag and not pos), "n_neg": int(not pos),
                     "out_pos": r.out if pos else 0, "out_neg": 0 if pos else r.out,
                     "new_tp": r.tp_new, "new_fp": r.fp_new, "out": r.out, "n_find": r.n_findings})
    return pd.DataFrame(rows).set_index("file").sort_index()[COLS]


def ci_table(counts: pd.DataFrame, names: list[str], n_boot: int, seed: int = 0) -> dict[str, dict]:
    arr = counts.to_numpy(float)
    return {m: cluster_bootstrap(arr, lambda s, m=m: metric_value(m, s), n_boot=n_boot, seed=seed) for m in names}


def fmt(d: dict, pct: bool = True, nd: int = 1) -> str:
    if d["point"] != d["point"]:                       # NaN: metrica indefinida (p.ex. precisao sem nenhum achado aceito)
        return "n/d"
    k = 100 if pct else 1
    return f"{k * d['point']:.{nd}f} [{k * d['lo']:.{nd}f}; {k * d['hi']:.{nd}f}]"


# --------------------------------------------------------------------------- carga e variantes
def load_all(rep: str) -> dict[str, dict[str, dict]]:
    return {c: mt.load_runs(RUNS, c, rep) for c in CONFIGS}


def b0_failed_files(res_b0: dict[str, dict]) -> list[str]:
    """Arquivos do B0 em que a extracao estruturada falhou (resposta sem achados por falha, nao por decisao do modelo)."""
    return sorted(f for f, r in res_b0.items() if not (r.get("steps", {}).get("b0_extract", {}).get("ok", True)))


def pilot_files() -> set[str]:
    from agents import CodeItem
    from runner import select_pilot
    items = []
    for line in open(DATA / "files.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r["class"] in ("positive", "negative"):
            items.append(CodeItem(f"{r['snapshot']}:{r['folder']}", r["snapshot"], r["file_number"], r["language"], r["code"]["ext"], "", r["class"]))
    return {i.id for i in select_pilot(items)}


def file_cwe_view(res: dict[str, dict]) -> dict[str, dict]:
    """Sensibilidade exploratoria S6: ignora a linha (achados sem linha passam a valer para o arquivo todo)."""
    return {f: {**r, "findings": [{**row, "finding": {**row["finding"], "lines": [0]}} for row in r["findings"]]} for f, r in res.items()}


def evaluate(res: dict[str, dict], gt: mt.GT, config: str, rep: str, hier, fams, **kw) -> mt.RunEval:
    return mt.evaluate_run(res, gt, config, rep, hierarchy=hier, families=fams, **kw)


def run_variant(all_res: dict, gt: mt.GT, rep: str, hier, fams, *, files: set[str] | None = None, require_cwe=True,
                flag="accepted", only_security=False, file_cwe=False, configs: list[str] | None = None
                ) -> dict[str, tuple[mt.RunEval, pd.DataFrame, mt.GT]]:
    g = subset_gt(gt, files) if files is not None else gt
    out = {}
    for c in (configs or CONFIGS):
        res = {f: r for f, r in all_res[c].items() if f in g.file_class}
        if file_cwe:
            res = file_cwe_view(res)
        kw = dict(require_cwe=require_cwe, flag=flag, only_security=only_security)
        if file_cwe:
            kw["tolerance"] = 10 ** 6
        ev = evaluate(res, g, c, rep, hier, fams, **kw)
        out[c] = (ev, file_counts(ev, g, only_security), g)
    return out


# --------------------------------------------------------------------------- F6: classes dos achados
def f6_table(all_res: dict, gt: mt.GT, rep: str, hier, fams) -> tuple[pd.DataFrame, list[str]]:
    """Cada achado ACEITO de cada configuracao em exatamente uma classe: tp_new / fp_new / dup / out (e 'ignored' no recorte de seguranca)."""
    rows, problems = [], []
    for c in CONFIGS:
        ev = evaluate(all_res[c], gt, c, rep, hier, fams)
        accepted = sum(1 for r in all_res[c].values() for x in r["findings"] if x.get("accepted"))
        if len(ev.finding_rows) != accepted:
            problems.append(f"{c}: {accepted} achados aceitos, mas {len(ev.finding_rows)} classificados")
        for fr in ev.finding_rows:
            rows.append({"config": c, "file": fr["file"], "finding_id": fr["finding_id"], "classe": fr["kind"],
                         "issues_reais": "|".join(fr["real"]), "falsos_alarmes_conhecidos": "|".join(fr["fp"])})
    return pd.DataFrame(rows), problems


# --------------------------------------------------------------------------- relatorio
def md(df: pd.DataFrame, index: bool = False) -> str:
    return df.to_markdown(index=index)


def main_table(var: dict, n_boot: int, names=MAIN_METRICS) -> tuple[pd.DataFrame, list[dict]]:
    rows, flat = [], []
    for c in var:
        ev, cnt, g = var[c]
        ci = ci_table(cnt, names, n_boot)
        row = {"config": c, "acusados reais": f"{len(ev.accused_real)}/{ev.n_real}", "falsos alarmes acusados": f"{len(ev.accused_fp)}/{ev.n_fp}"}
        for m in names:
            pct = m not in ("mcc",) and not m.startswith("out_per") and m != "findings_per_file"
            row[m] = fmt(ci[m], pct=pct, nd=1 if pct else 2)
            flat.append({"config": c, "metric": m, **ci[m]})
        rows.append(row)
    return pd.DataFrame(rows), flat


def compare_pairs(var: dict, gt_issues: list[dict], gt_fps: list[dict], n_boot: int) -> tuple[list[str], list[dict]]:
    """McNemar exato por issue e por falso alarme; Q de Cochran; Holm; diferencas pareadas por arquivo (bootstrap)."""
    L, tests = [], []
    ids_r, ids_f = [i["id"] for i in gt_issues], [i["id"] for i in gt_fps]
    cols_r = {c: [i in var[c][0].accused_real for i in ids_r] for c in CONFIGS}
    cols_f = {c: [i in var[c][0].accused_fp for i in ids_f] for c in CONFIGS}
    for tag, cols, ids in (("detecao de issues reais (56)", cols_r, ids_r), ("acusacao de falsos alarmes conhecidos (85)", cols_f, ids_f)):
        q = cochran_q(np.array([cols[c] for c in CONFIGS]).T)
        raw, rows = {}, []
        for a, b in itertools.combinations(CONFIGS, 2):
            r = mcnemar_exact(cols[a], cols[b])
            raw[f"{a} x {b}"] = r["p"]
            rows.append({"par": f"{a} x {b}", "so_a": r["only_a"], "so_b": r["only_b"], "p": r["p"]})
        adj = holm(raw)
        for r in rows:
            r["p_Holm"] = adj[r["par"]]
            r["p"], r["p_Holm"] = round(r["p"], 4), round(r["p_Holm"], 4)
            tests.append({"familia": tag, "teste": "McNemar exato", **r})
        tests.append({"familia": tag, "teste": "Q de Cochran (5 configuracoes)", "par": "todas", "p": q["p"], "Q": q["Q"], "gl": q["df"]})
        L += [f"**{tag}** - Q de Cochran = {q['Q']:.2f} (gl {q['df']}), p = {q['p']:.4g}. McNemar exato par a par, com Holm:", "", md(pd.DataFrame(rows)), ""]
    return L, tests


def hypothesis_section(var: dict, n_boot: int, gt: mt.GT) -> tuple[list[str], list[dict]]:
    L, tests = ["### Comparacoes confirmatorias (H1 a H3), diferenca A - B por arquivo-bootstrap pareado", ""], []
    pairs = [("H1", "C3", "B1"), ("H2", "B1", "B0"), ("H3", "C3", "C2")]
    rows = []
    for h, a, b in pairs:
        ca, cb = var[a][1].to_numpy(float), var[b][1].to_numpy(float)
        row = {"hipotese": h, "A": a, "B": b}
        for m in ("recall", "false_alarm_rate", "precision", "f1"):
            d = paired_bootstrap_diff(ca, cb, lambda s, m=m: metric_value(m, s), n_boot=n_boot)
            pct = 100
            row[m + " (A-B, p.p.)"] = f"{pct * d['diff']:+.1f} [{pct * d['lo']:+.1f}; {pct * d['hi']:+.1f}]"
            tests.append({"familia": "pareado por arquivo", "teste": f"{h} {a}-{b}", "par": m, "diff": d["diff"], "lo": d["lo"], "hi": d["hi"], "p": d["p_two_sided"]})
        rows.append(row)
    L += [md(pd.DataFrame(rows)), ""]
    # veredito mecanico de H1, so como sintese (os numeros acima mandam)
    d_far = next(t for t in tests if t["teste"] == "H1 C3-B1" and t["par"] == "false_alarm_rate")
    d_rec = next(t for t in tests if t["teste"] == "H1 C3-B1" and t["par"] == "recall")
    L += [f"H1 (C3 x B1): taxa de falsos alarmes conhecidos {100 * d_far['diff']:+.1f} p.p. (IC {100 * d_far['lo']:+.1f} a {100 * d_far['hi']:+.1f}); "
          f"recall {100 * d_rec['diff']:+.1f} p.p. (IC {100 * d_rec['lo']:+.1f} a {100 * d_rec['hi']:+.1f}). Criterio da H1: reducao dos falsos alarmes com perda de recall de no maximo 5 p.p.: "
          f"{'reducao com IC abaixo de zero' if d_far['hi'] < 0 else 'IC da reducao inclui zero'}; "
          f"{'perda pontual dentro de 5 p.p.' if d_rec['diff'] >= -0.05 else 'perda pontual MAIOR que 5 p.p.'} "
          f"(limite inferior do IC do recall: {100 * d_rec['lo']:+.1f} p.p.).", ""]
    return L, tests


def curve_section(all_res: dict, gt: mt.GT, var: dict, hier, fams) -> tuple[list[str], pd.DataFrame]:
    cur = mt.confidence_curve(all_res["B1"], gt, hierarchy=hier, families=fams)
    cur.to_csv(RESULTS / "f7_curva_confianca_B1.csv", index=False, lineterminator="\n")
    L = ["### H4: o verificador contra um corte por confianca do detector (curva do B1)", ""]
    rows = []
    for c in ("B0", "B1", "C1", "C2", "C3"):
        m = var[c][0].metrics()
        ok = cur[cur["false_alarm_rate"] <= m["false_alarm_rate"] + 1e-12]
        best = float(ok["recall"].max()) if len(ok) else float("nan")
        rows.append({"config": c, "taxa de falsos alarmes": round(m["false_alarm_rate"], 3), "recall": round(m["recall"], 3),
                     "melhor recall do B1 com taxa <= essa": round(best, 3), "recall - curva (p.p.)": round(100 * (m["recall"] - best), 1)})
    L += [md(pd.DataFrame(rows)), "",
          "Se 'recall - curva' for positivo, a configuracao acusa mais issues reais do que qualquer corte de confianca do B1 com a mesma taxa de falsos alarmes (valor agregador do verificador, H4).", ""]
    return L, cur


def verifier_section(var: dict, cfgs: tuple[str, ...] = ("C1", "C2", "C3"), title: str = "Efeito do verificador sobre os achados do A1 (referencia: B1)"
                     ) -> list[str]:
    from scipy.stats import fisher_exact
    ref = var["B1"][0]
    rows = []
    for c in cfgs:
        e = mt.verifier_effect(ref, var[c][0])
        kept_tp, kept_fp = e["tp_ref"] - e["tp_lost"], e["fp_ref"] - e["fp_removed"]
        _, p = fisher_exact([[kept_tp, e["tp_lost"]], [kept_fp, e["fp_removed"]]])
        rows.append({"config": c, "falsos alarmes removidos": f"{e['fp_removed']}/{e['fp_ref']}", "taxa de remocao": round(e["fp_removal_rate"], 3) if e["fp_ref"] else None,
                     "verdadeiros positivos perdidos": f"{e['tp_lost']}/{e['tp_ref']}", "taxa de perda": round(e["tp_loss_rate"], 3) if e["tp_ref"] else None,
                     "reducao de achados fora do gabarito": round(e["out_reduction"], 3),
                     "mantidos: reais x falsos alarmes": f"{kept_tp}/{e['tp_ref']} x {kept_fp}/{e['fp_ref']}", "Fisher exato (mantem real x falso alarme)": round(float(p), 3)})
    return [f"### {title}", "", md(pd.DataFrame(rows)), "",
            "Taxas sobre locais (issues reais e falsos alarmes conhecidos) acusados pelo B1. O teste de Fisher compara a fracao mantida de reais com a de falsos alarmes: mede se o verificador discrimina, alem de apenas rejeitar muito.", ""]


def classes_section(f6: pd.DataFrame) -> list[str]:
    tab = pd.crosstab(f6["config"], f6["classe"]).reindex(CONFIGS).fillna(0).astype(int)
    tab["total aceitos"] = tab.sum(axis=1)
    return ["### Classes dos achados aceitos (F6)", "", md(tab, index=True), "",
            "tp_new = primeiro achado sobre um issue real; fp_new = primeiro sobre um falso alarme conhecido; dup = repetido sobre algo ja acusado (fora do numerador e do denominador); out = fora do gabarito (nao julgado, D5).", ""]


B0FIX_DIR = RESULTS / "b0_fix_validation"


def load_b0_fix() -> dict[str, dict]:
    """Julgamentos do A3b sobre o patch do B0 (kernel f5b0fix): results/b0_fix_validation/<arquivo>.json."""
    d = B0FIX_DIR
    return {r["file"]: r for r in (json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json")))} if d.is_dir() else {}


def merge_b0_fix(res_b0: dict[str, dict], fix: dict[str, dict]) -> dict[str, dict]:
    """Poe em cada achado do B0 o veredito do A3b e as ferramentas do patch do arquivo (mesmos campos que o C3 usa em correction_summary)."""
    out = {}
    for f, r in res_b0.items():
        fx = fix.get(f)
        verd = {x["finding_id"]: x["fix_verdict"] for x in (fx["rows"] if fx else [])}
        rows = [{**row, "fix_verdict": verd.get(row["finding"]["id"]),
                 "tools": fx["tools"] if fx and row["finding"]["id"] in verd else None} for row in r["findings"]]
        out[f] = {**r, "findings": rows}
    return out


def b0_fix_section(res_b0: dict[str, dict], gt: mt.GT, hier, fams, fix: dict[str, dict] | None = None) -> list[str]:
    """Correcao do B0 com o A3b (o mesmo do C3) + ferramentas, nos achados do B0 que casam com um issue real (regra estrita e so linha)."""
    fix = load_b0_fix() if fix is None else fix
    if not fix:
        return ["B0 com o A3b: ainda nao executado (falta `results/b0_fix_validation/`).", ""]
    merged = merge_b0_fix(res_b0, fix)
    judged = Counter(x["fix_verdict"] for r in fix.values() for x in r["rows"])
    no_patch = sorted(f for f, r in fix.items() if r["tools"] is None)
    rows = []
    for tag, kw in (("regra estrita", {}), ("so linha ±3 (sensibilidade)", {"require_cwe": False})):
        ev = evaluate(merged, gt, "B0", "main", hier, fams, **kw)
        cs = mt.correction_summary(merged, gt, ev)
        by_id = {fr["finding_id"] + "@" + fr["file"]: fr for fr in ev.finding_rows if fr["real"]}
        verd = Counter(next(x for x in merged[fr["file"]]["findings"] if x["finding"]["id"] == fr["finding_id"]).get("fix_verdict")
                       for fr in by_id.values())
        rows.append({"B0 + A3b": tag, **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in cs.items()},
                     "vereditos do A3b nos achados que casam com issue real": ", ".join(f"{k}: {v}" for k, v in sorted(verd.items(), key=str))})
    return ["### B0 com o A3b nos patches do B0 (o patch e o ultimo bloco de codigo da resposta; um por arquivo, usado para todos os achados do arquivo)", "",
            md(pd.DataFrame(rows)), "",
            f"Julgamentos do A3b: {sum(judged.values())} achados do B0 ({', '.join(f'{k}: {v}' for k, v in sorted(judged.items(), key=str))}); "
            f"arquivos sem julgamento (sem patch ou sem achados extraidos): {len(no_patch)}. A taxa condicional usa as issues reais acusadas pelo B0; `valid` do A3b so e valido com os criterios das ferramentas "
            f"(a regra do scanner sumiu, compila, sem aviso novo). O A3b tem kappa baixo contra 'Was issue fixed' (0,28): leitura secundaria.", ""]


def correction_section(all_res: dict, gt: mt.GT, var: dict, hier, fams) -> list[str]:
    rows = []
    for c in ("C2", "C3"):
        ev = var[c][0]
        cs = mt.correction_summary(all_res[c], gt, ev)
        un = mt.unnecessary_patches(all_res[c], gt, hierarchy=hier, families=fams)
        rows.append({"config": c, **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in cs.items()}, "patches desnecessarios": un})
    # B0: so os criterios de ferramentas (nao ha veredito do A3b), sobre os issues acusados
    by_id = {i["id"]: i for i in gt.issues}
    ev0 = var["B0"][0]
    crit = []
    for iid in sorted(ev0.accused_real):
        r = all_res["B0"][by_id[iid]["file"]]
        crit.append(mt.fix_criteria({"tools": r.get("tools"), "fix_verdict": None}, by_id[iid]))
    b0 = {k: [c[k] for c in crit] for k in ("rule_gone", "compiles", "no_new_warning")}
    b0row = {"config": "B0 (so ferramentas)", "accused": len(crit)}
    for k, v in b0.items():
        b0row[f"{k}_true"], b0row[f"{k}_false"], b0row[f"{k}_na"] = sum(x is True for x in v), sum(x is False for x in v), sum(x is None for x in v)
    return ["## Correcao (secundaria; limitacao: kappa do A3b contra 'Was issue fixed' = 0,28)", "",
            md(pd.DataFrame(rows)), "", md(pd.DataFrame([b0row])), "",
            "B0 (linha acima): so os criterios 2-4 das ferramentas, sobre o patch do arquivo inteiro.", "",
            *b0_fix_section(all_res["B0"], gt, hier, fams)]


def cost_section(all_res: dict, var: dict) -> tuple[list[str], pd.DataFrame]:
    rows = []
    for c in CONFIGS:
        u = Counter()
        for r in all_res[c].values():
            for k in ("calls", "prompt_tokens", "completion_tokens", "seconds"):
                u[k] += r["usage"][k]
        n = len(all_res[c])
        tp = len(var[c][0].accused_real)
        rows.append({"config": c, "chamadas/arq": round(u["calls"] / n, 1), "tokens entrada/arq": round(u["prompt_tokens"] / n), "tokens saida/arq": round(u["completion_tokens"] / n),
                     "s de chamada/arq": round(u["seconds"] / n, 1), "tokens totais por issue real acusado": round((u["prompt_tokens"] + u["completion_tokens"]) / tp) if tp else None})
    df = pd.DataFrame(rows)
    return ["## Custo computacional (cada configuracao contada sozinha; o A1 e o A3a compartilhados contam em todas que os usam)", "", md(df), ""], df


PAPER_DIR = RESULTS / "paper_extract"
PAPER_LABEL = {"gpt-4.1": "GPT-4.1 (artigo)", "gpt-5": "GPT-5 (artigo)", "opus-4.1": "Opus 4.1 (artigo)"}


def load_paper(model: str) -> dict[str, dict]:
    """Respostas do artigo, extraidas em forma estruturada pelo mesmo extrator do B0 (f4_jobs.run_paper_extraction)."""
    res, d = {}, PAPER_DIR / model
    for p in sorted(d.glob("*.json")) if d.is_dir() else []:
        r = json.loads(p.read_text(encoding="utf-8"))
        if "file" not in r:
            continue
        res[r["file"]] = {"file": r["file"], "ok": r["ok"], "findings": [
            {"finding": {"id": f"E{i}", "cwe": f["cwe"], "lines": f["lines"], "title": f["description"], "confidence": None},
             "accepted": True, "accepted_sens": True} for i, f in enumerate(r["findings"], 1)]}
    return res


def e1_section(all_res: dict, gt: mt.GT, hier, fams, n_boot: int) -> tuple[list[str], list[dict]]:
    """E1 (exploratoria): pipeline com modelos abertos x respostas originais do artigo (GPT-4.1, GPT-5, Opus 4.1), no MESMO regime:
    resposta -> extracao estruturada pelo mesmo modelo -> mesma regra da F6. Mesmos arquivos em todas as linhas."""
    L = ["## E1 (exploratoria): pipeline com modelos abertos x respostas originais do artigo, no mesmo regime estruturado", ""]
    paper = {PAPER_LABEL[m]: load_paper(m) for m in PAPER_LABEL}
    paper = {k: v for k, v in paper.items() if v}
    if not paper:
        return L + ["Sem extracoes das respostas do artigo em `results/paper_extract/`.", ""], []
    files = set.intersection(*[set(v) for v in paper.values()]) & set(gt.file_class)
    n_pos = sum(gt.file_class[f] == "positive" for f in files)
    n_neg = len(files) - n_pos
    sets = {"B0 (abertos)": all_res["B0"], "B1 (abertos)": all_res["B1"], "C3 (abertos)": all_res["C3"], **paper}
    fail = {k: sorted(f for f, r in v.items() if not r["ok"]) for k, v in paper.items()}
    L += [f"Arquivos em comum: {len(files)} ({n_pos} positivos, {n_neg} negativos)." + ("" if n_neg == 66 and n_pos == 48 else
          " **Cobertura parcial**: faltam extracoes; as taxas abaixo usam so os locais desses arquivos, nao os 85 e 56 completos."),
          "Respostas do artigo com extracao sem sucesso: " + "; ".join(f"{k}: {len(v)}" for k, v in fail.items()) + ".",
          "Diferencas importantes: os modelos do artigo sao outros (comerciais, maiores); as respostas do artigo foram escritas para o prompt original, "
          "sem linhas obrigatorias, e a extracao feita por um modelo de 14B pode errar; a regra da F6 teve kappa baixo contra os rotulos dos autores. "
          "Por isso a comparacao e exploratoria e so vale no mesmo regime.", ""]
    flat = []
    for tag, kw in (("regra estrita (linha ±3 e CWE compativel)", {}), ("so linha ±3 (sensibilidade)", {"require_cwe": False})):
        var = run_variant(sets, gt, "e1", hier, fams, files=files, configs=list(sets), **kw)
        t, fl = main_table(var, n_boot)
        flat += [{"variant": f"E1 {tag}", **r} for r in fl]
        L += [f"### {tag}", "", md(t), ""]
        if not kw:
            rows = []
            for k in paper:
                row = {"comparacao": f"C3 (abertos) - {k}"}
                for m in ("recall", "false_alarm_rate", "precision"):
                    d = paired_bootstrap_diff(var["C3 (abertos)"][1].to_numpy(float), var[k][1].to_numpy(float), lambda s, m=m: metric_value(m, s), n_boot=n_boot)
                    row[m + " (p.p.)"] = f"{100 * d['diff']:+.1f} [{100 * d['lo']:+.1f}; {100 * d['hi']:+.1f}]"
                rows.append(row)
            L += ["Diferenca pareada por arquivo (regra estrita), C3 menos cada modelo do artigo:", "", md(pd.DataFrame(rows)), ""]
    return L, flat


def variance_section(gt: mt.GT, hier, fams, n_boot: int, main_var: dict) -> tuple[list[str], list[dict]]:
    """Estudo de variancia: B1 e C3 nas repeticoes var1-3 (amostragem: seeds 1-3, temperatura do cartao do modelo). Media e desvio-padrao
    das metricas e a H1 refeita em cada repeticao. As repeticoes usam temperatura > 0; a execucao principal (T=0) entra como referencia."""
    L = ["## Estudo de variancia (B1 e C3, repeticoes com amostragem)", ""]
    reps = [r for r in ("var1", "var2", "var3") if (RUNS / "B1" / r).is_dir() and (RUNS / "C3" / r).is_dir()]
    if not reps:
        return L + ["Ainda nao executado: nao ha `runs/B1/var*` nem `runs/C3/var*`.", ""], []
    per, flat = {}, []
    for rep in reps:
        res = {c: mt.load_runs(RUNS, c, rep) for c in ("B1", "C3")}
        files = set(res["B1"]) & set(res["C3"]) & set(gt.file_class)
        per[rep] = (run_variant(res, gt, rep, hier, fams, files=None if files == set(gt.file_class) else files, configs=["B1", "C3"]),
                    len(files), sum(len(r["findings"]) for r in res["C3"].values()))
    rows = []
    for rep in reps:
        var, nf, _ = per[rep]
        for c in ("B1", "C3"):
            ev = var[c][0]
            m = ev.metrics()
            rows.append({"repeticao": rep, "config": c, "arquivos": nf,
                         "recall": f"{100 * m['recall']:.1f}% ({len(ev.accused_real)}/{ev.n_real})",
                         "falsos alarmes conhecidos": f"{100 * m['false_alarm_rate']:.1f}% ({len(ev.accused_fp)}/{ev.n_fp})",
                         "precisao": f"{100 * m['precision']:.1f}%" if m["precision"] == m["precision"] else "n/d",
                         "F1": f"{100 * m['f1']:.1f}%" if m["f1"] == m["f1"] else "n/d", "MCC": round(m["mcc"], 2) if m["mcc"] == m["mcc"] else None,
                         "achados aceitos": int(var[c][1]["n_find"].sum()), "arquivos negativos sinalizados": f"{100 * m['neg_files_flagged_frac']:.1f}%"})
            flat += [{"variant": f"variancia {rep}", "config": c, "metric": k, "point": m[k], "lo": float("nan"), "hi": float("nan"), "n_boot": 0}
                     for k in MAIN_METRICS]
    L += [f"Repeticoes disponiveis: {', '.join(reps)} (seeds 1 a 3, temperatura do cartao: detector 0,7; verificador 1,0).", "", md(pd.DataFrame(rows)), ""]
    # media e desvio-padrao
    summ = []
    for c in ("B1", "C3"):
        row = {"config": c, "repeticoes": len(reps)}
        for k in MAIN_METRICS:
            v = [per[rep][0][c][0].metrics()[k] for rep in reps]
            ms = mean_sd(v)
            pct = k != "mcc"
            row[k] = (f"{100 * ms['mean']:.1f} ± {100 * ms['sd']:.1f} p.p." if pct else f"{ms['mean']:.2f} ± {ms['sd']:.2f}") if ms["n"] > 1 else "n/d"
        mm = main_var[c][0].metrics()
        row["referencia (T=0, principal): recall; falsos alarmes"] = f"{100 * mm['recall']:.1f}%; {100 * mm['false_alarm_rate']:.1f}%"
        summ.append(row)
    L += ["### Media ± desvio-padrao nas repeticoes (n pequeno: o desvio e uma estimativa grosseira)", "", md(pd.DataFrame(summ)), ""]
    # H1 em cada repeticao
    hrows, ok_n = [], 0
    for rep in reps:
        var, _, _ = per[rep]
        ca, cb = var["C3"][1].to_numpy(float), var["B1"][1].to_numpy(float)
        d = {m: paired_bootstrap_diff(ca, cb, lambda s, m=m: metric_value(m, s), n_boot=n_boot) for m in ("recall", "false_alarm_rate", "precision")}
        far_down = d["false_alarm_rate"]["hi"] < 0
        loss_ok = d["recall"]["diff"] >= -0.05
        ok_n += int(far_down and loss_ok)
        hrows.append({"repeticao": rep, "recall (C3-B1, p.p.)": f"{100 * d['recall']['diff']:+.1f} [{100 * d['recall']['lo']:+.1f}; {100 * d['recall']['hi']:+.1f}]",
                      "falsos alarmes (C3-B1, p.p.)": f"{100 * d['false_alarm_rate']['diff']:+.1f} [{100 * d['false_alarm_rate']['lo']:+.1f}; {100 * d['false_alarm_rate']['hi']:+.1f}]",
                      "precisao (C3-B1, p.p.)": f"{100 * d['precision']['diff']:+.1f} [{100 * d['precision']['lo']:+.1f}; {100 * d['precision']['hi']:+.1f}]",
                      "queda de falsos alarmes com IC < 0": "sim" if far_down else "nao", "perda de recall <= 5 p.p. (pontual)": "sim" if loss_ok else "nao"})
    L += ["### H1 refeita em cada repeticao (C3 - B1, bootstrap pareado por arquivo)", "", md(pd.DataFrame(hrows)), "",
          f"Criterio da H1 (queda dos falsos alarmes e perda de recall de no maximo 5 p.p.) cumprido em {ok_n} de {len(reps)} repeticoes.", ""]
    return L, flat


def h5_section(all_res: dict, gt: mt.GT, hier, fams, n_boot: int, rep: str = "main") -> tuple[list[str], list[dict]]:
    """H5 (opcional, exploratoria; fora da familia confirmatoria com Holm): verificador de OUTRA familia (C3, gpt-oss) x da MESMA familia do
    detector (C3-mf: A3a e A3b com o qwen). Mesmos arquivos e, gracas ao cache semeado, os mesmos achados do A1 (confere-se abaixo).
    Criterio fixado no DIARIO antes do resultado: H5 apoiada se a taxa de falsos alarmes conhecidos do C3 for menor que a do C3-mf com IC
    pareado da diferenca abaixo de 0; o recall e reportado junto."""
    L = ["## H5 (exploratoria): verificador de outra familia (C3, gpt-oss) x da mesma familia do detector (C3-mf, qwen)", ""]
    res_mf = mt.load_runs(RUNS, "C3mf", rep)
    files = set(res_mf) & set(gt.file_class)
    if not files:
        return L + ["Ainda nao executado: nao ha `runs/C3mf/main`.", ""], []
    sets = {"B1": all_res["B1"], "C3": all_res["C3"], "C3mf": res_mf}
    names = list(sets)
    n_pos = sum(gt.file_class[f] == "positive" for f in files)
    n_neg = len(files) - n_pos
    same = sum([r["finding"] for r in all_res["C3"][f]["findings"]] == [r["finding"] for r in res_mf[f]["findings"]] for f in files)
    L += [f"Arquivos: {len(files)} ({n_pos} positivos, {n_neg} negativos)." + ("" if (n_pos, n_neg) == (48, 66) else
          " **Cobertura parcial**: faltam arquivos; as taxas usam so os locais desses arquivos, nao os 85 e 56 completos."),
          f"Achados do A1 identicos aos do C3 em {same} de {len(files)} arquivos"
          + ("." if same == len(files) else " (**a comparacao nao e sobre exatamente os mesmos achados nos demais arquivos**)."),
          "No C3 o verificador (A3a) e o juiz da correcao (A3b) sao o `gpt-oss:20b`; no C3-mf sao o `qwen2.5-coder:14b`, o mesmo modelo do detector. "
          "O corretor (A2) e o `qwen` nos dois. Aceito = veredito `confirmed`.", ""]
    flat, strict = [], None
    for tag, kw in (("regra estrita (linha ±3 e CWE compativel)", {}), ("so linha ±3 (sensibilidade)", {"require_cwe": False}),
                    ("'uncertain' aceito (sensibilidade S2)", {"flag": "accepted_sens"})):
        var = run_variant(sets, gt, rep, hier, fams, files=files, configs=names, **kw)
        t, fl = main_table(var, n_boot)
        flat += [{"variant": f"H5 {tag}", **r} for r in fl]
        L += [f"### {tag}", "", md(t), ""]
        if not kw:
            strict = var
    # diferencas pareadas por arquivo (regra estrita)
    rows, tests = [], {}
    for a, b in (("C3", "C3mf"), ("C3mf", "B1"), ("C3", "B1")):
        row = {"comparacao": f"{a} - {b}"}
        for m in ("recall", "false_alarm_rate", "precision"):
            d = paired_bootstrap_diff(strict[a][1].to_numpy(float), strict[b][1].to_numpy(float), lambda s, m=m: metric_value(m, s), n_boot=n_boot)
            row[m + " (p.p.)"] = "n/d" if d["diff"] != d["diff"] else f"{100 * d['diff']:+.1f} [{100 * d['lo']:+.1f}; {100 * d['hi']:+.1f}]"
            tests[(a, b, m)] = d
        rows.append(row)
    L += ["### Diferenca pareada por arquivo (regra estrita; bootstrap por arquivo, IC de 95%)", "", md(pd.DataFrame(rows)), ""]
    # McNemar exato por local, C3 x C3mf
    g = subset_gt(gt, files)
    ids_r, ids_f = [i["id"] for i in g.issues], [i["id"] for i in g.fps]
    mrows = []
    for tag, ids, attr in (("issues reais", ids_r, "accused_real"), ("falsos alarmes conhecidos", ids_f, "accused_fp")):
        ca = [i in getattr(strict["C3"][0], attr) for i in ids]
        cb = [i in getattr(strict["C3mf"][0], attr) for i in ids]
        r = mcnemar_exact(ca, cb)
        mrows.append({"locais": f"{tag} ({len(ids)})", "so no C3": r["only_a"], "so no C3-mf": r["only_b"], "p (McNemar exato)": round(r["p"], 4)})
    L += ["### McNemar exato por local, C3 x C3-mf (regra estrita; exploratorio, sem correcao de Holm)", "", md(pd.DataFrame(mrows)), ""]
    # veredito de cada verificador sobre os achados do A1 e efeito em relacao ao B1
    vrows = []
    for c in ("C3", "C3mf"):
        cnt = Counter(str(row.get("verdict")) for f in files for row in sets[c][f]["findings"])
        n = sum(cnt.values())
        vrows.append({"config": c, "achados do A1": n, **{k: f"{cnt.get(k, 0)} ({100 * cnt.get(k, 0) / n:.0f}%)" if n else "0"
                                                              for k in ("confirmed", "refuted", "uncertain", "None")}})
    L += ["### Vereditos do A3a sobre os achados do A1 ('None' = veredito ausente por falha)", "", md(pd.DataFrame(vrows)), ""]
    L += verifier_section(strict, ("C3", "C3mf"), "Efeito de cada verificador sobre os achados do A1 (referencia: B1; regra estrita)")
    # correcao e custo (secundarios)
    crow, urow = [], []
    for c in ("C3", "C3mf"):
        cs = mt.correction_summary(sets[c], g, strict[c][0])
        crow.append({"config": c, **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in cs.items()},
                     "patches desnecessarios": mt.unnecessary_patches({f: r for f, r in sets[c].items() if f in files}, g, hierarchy=hier, families=fams)})
        u = Counter()
        for f in files:
            for k in ("calls", "prompt_tokens", "completion_tokens", "seconds"):
                u[k] += sets[c][f]["usage"][k]
        urow.append({"config": c, "chamadas/arq": round(u["calls"] / len(files), 1), "tokens entrada/arq": round(u["prompt_tokens"] / len(files)),
                     "tokens saida/arq": round(u["completion_tokens"] / len(files)), "s de chamada/arq": round(u["seconds"] / len(files), 1)})
    L += ["### Correcao (secundaria; kappa do A3b contra 'Was issue fixed' = 0,28)", "", md(pd.DataFrame(crow)), "",
          "### Custo (A1 e A2 vindos do cache semeado contam com o tempo e os tokens da execucao original)", "", md(pd.DataFrame(urow)), ""]
    far, rec, pre = (tests[("C3", "C3mf", m)] for m in ("false_alarm_rate", "recall", "precision"))
    if far["hi"] < 0:
        v = "**H5 apoiada**: o C3 acusa menos falsos alarmes conhecidos que o C3-mf, com IC pareado abaixo de 0"
    elif far["lo"] > 0:
        v = "**H5 contrariada**: o C3-mf (mesma familia) acusa MENOS falsos alarmes conhecidos que o C3, com IC pareado acima de 0"
    else:
        v = "**H5 nao apoiada**: o IC pareado da diferenca de falsos alarmes (C3 - C3-mf) inclui 0"
    L += [f"Sintese mecanica (criterio fixado antes do resultado): {v}. Falsos alarmes conhecidos C3 - C3-mf = {100 * far['diff']:+.1f} p.p. "
          f"(IC {100 * far['lo']:+.1f} a {100 * far['hi']:+.1f}); recall {100 * rec['diff']:+.1f} p.p. (IC {100 * rec['lo']:+.1f} a {100 * rec['hi']:+.1f}); "
          f"precisao {'n/d (o C3-mf nao aceita nenhum achado: precisao indefinida)' if pre['diff'] != pre['diff'] else f'{100 * pre['diff']:+.1f} p.p. (IC {100 * pre['lo']:+.1f} a {100 * pre['hi']:+.1f})'}. Exploratoria: nao entra na familia com Holm.", ""]
    return L, flat


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--rep", default="main")
    ap.add_argument("--n-boot", type=int, default=2000)
    a = ap.parse_args()
    RESULTS.mkdir(exist_ok=True)
    gt = mt.load_gt(DATA)
    hier = CWEHierarchy.from_xml(DATA / "cwe" / "1000.xml")
    fams = load_families(HERE / "matching_families.yaml")
    all_res = load_all(a.rep)
    for c in CONFIGS:
        assert set(all_res[c]) == set(gt.file_class), f"{c}: arquivos faltando ou sobrando"
    failed = b0_failed_files(all_res["B0"])
    pilot = pilot_files()
    all_files = set(gt.file_class)

    L = ["# F6 + F7 - correspondencia, metricas e estatistica da execucao principal", "",
         f"Repeticao `{a.rep}` (temperatura 0, seed 0), {len(all_files)} arquivos ({sum(v == 'positive' for v in gt.file_class.values())} positivos, "
         f"{sum(v == 'negative' for v in gt.file_class.values())} negativos), gabarito: {len(gt.issues)} issues reais e {len(gt.fps)} falsos alarmes conhecidos. "
         f"Regra principal: linha +-3 e CWE compativel; 'uncertain' do verificador = rejeitado. IC de 95% por bootstrap por arquivo ({a.n_boot} replicas).", ""]

    # ---- F6
    f6, problems = f6_table(all_res, gt, a.rep, hier, fams)
    f6.to_csv(RESULTS / "f6_findings.csv", index=False, lineterminator="\n")
    L += ["## F6 - Correspondencia", "", *classes_section(f6),
          "Aceite da F6: todo achado aceito pertence a uma das classes: " + ("**sim**" if not problems else "**NAO**: " + "; ".join(problems)), ""]
    nolines = sum(1 for r in all_res["B0"].values() for x in r["findings"] if not x["finding"]["lines"])
    totb0 = sum(len(r["findings"]) for r in all_res["B0"].values())
    L += [f"B0: {nolines} de {totb0} achados extraidos ({100 * nolines / totb0:.0f}%) nao tem linha (a resposta de texto livre nao cita) e nao podem casar pela regra estrita; ver a sensibilidade S6.",
          f"Falha de extracao do B0 (resposta sem achados por falha do extrator): {failed}.", ""]

    # ---- F7 principal
    base = run_variant(all_res, gt, a.rep, hier, fams)
    tab, flat = main_table(base, a.n_boot)
    dtab, dflat = main_table(base, a.n_boot, DESC_METRICS)
    L += ["## F7 - Resultado principal (114 arquivos, regra estrita)", "", "Percentuais com IC de 95% [inferior; superior]. Recall = issues reais acusadas / 56; taxa de falsos alarmes conhecidos = locais acusados / 85.", "",
          md(tab), "", "### Descritivas (sem julgamento dos achados fora do gabarito)", "", md(dtab.drop(columns=["acusados reais", "falsos alarmes acusados"])), ""]
    L += verifier_section(base)
    cl, cur = curve_section(all_res, gt, base, hier, fams)
    L += cl
    L += ["## Comparacoes pareadas", ""]
    hl, tests = hypothesis_section(base, a.n_boot, gt)
    L += hl
    pl, tests2 = compare_pairs(base, gt.issues, gt.fps, a.n_boot)
    L += ["### Todas as comparacoes (confirmatorias: H1 = C3 x B1, H2 = B1 x B0, H3 = C3 x C2; as demais sao exploratorias)", "", *pl]
    L += correction_section(all_res, gt, base, hier, fams)
    cl2, cost = cost_section(all_res, base)
    L += cl2

    # ---- sensibilidades
    L += ["## Analises de sensibilidade (mesmas metricas, IC por arquivo)", ""]
    variants = {
        "S1 so linha +-3 (sem checar CWE)": dict(require_cwe=False),
        "S2 'uncertain' do verificador aceito": dict(flag="accepted_sens"),
        "S3 recorte so seguranca (sem CWE-561/1164)": dict(only_security=True),
        "S4 104 arquivos fora do piloto": dict(files=all_files - pilot),
        f"S5 sem os {len(failed)} arquivos do B0 com extracao falha": dict(files=all_files - set(failed)),
        "S6 (exploratoria) arquivo + CWE, sem exigir linha": dict(file_cwe=True),
    }
    allflat = [{"variant": "principal", **r} for r in flat + dflat]
    for name, kw in variants.items():
        v = run_variant(all_res, gt, a.rep, hier, fams, **kw)
        t, fl = main_table(v, a.n_boot)
        allflat += [{"variant": name, **r} for r in fl]
        n_files = len(next(iter(v.values()))[1])
        L += [f"### {name} ({n_files} arquivos)", "", md(t), ""]
    el, eflat = e1_section(all_res, gt, hier, fams, a.n_boot)
    vl, vflat = variance_section(gt, hier, fams, a.n_boot, base)
    hl5, h5flat = h5_section(all_res, gt, hier, fams, a.n_boot, a.rep)
    L += el + vl + hl5
    allflat += eflat + vflat + h5flat
    pd.DataFrame(allflat).to_csv(RESULTS / "metrics.csv", index=False, lineterminator="\n")
    pd.DataFrame(tests + tests2).to_csv(RESULTS / "tests.csv", index=False, lineterminator="\n")
    cost.to_csv(RESULTS / "f7_custo.csv", index=False, lineterminator="\n")
    (RESULTS / "f7_resultados.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
