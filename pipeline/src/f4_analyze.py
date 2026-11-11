"""F4 - analise local das saidas do piloto (baixadas do Kaggle com `kaggle kernels output`). Sem LLM.

Gera results/f4_piloto.md com: (1) custo, tokens, falhas, recusas e exemplos de veredito do pipeline; (2) teste de determinismo;
(3) validacao do julgamento automatico de correcao (A3b + criterios) contra os rotulos 'Was issue fixed' dos autores (GPT-4.1);
(4) validacao da regra da F6 (linha +-3 + CWE compativel) sobre as respostas do artigo extraidas em forma estruturada.

Uso:  pipeline\\.venv\\Scripts\\python.exe -I pipeline\\src\\f4_analyze.py --out <pasta com runs/, cache/, f4/, run_report.json>
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import metrics as mt  # noqa: E402
from canonical import MODELS  # noqa: E402
from cwe import CWEHierarchy, load_families  # noqa: E402
from stats import cohen_kappa  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
DATA, RESULTS = HERE / "data", HERE / "results"


def agree(y_true: list[bool], y_pred: list[bool]) -> dict:
    tp = sum(t and p for t, p in zip(y_true, y_pred)); tn = sum((not t) and (not p) for t, p in zip(y_true, y_pred))
    fp = sum((not t) and p for t, p in zip(y_true, y_pred)); fn = sum(t and (not p) for t, p in zip(y_true, y_pred))
    n = len(y_true)
    return {"n": n, "acordo": round((tp + tn) / n, 3) if n else None, "kappa": round(cohen_kappa(y_true, y_pred), 3) if n else None,
            "TP": tp, "FP": fp, "FN": fn, "TN": tn}


def load_cache_calls(cache_dir: Path) -> list[dict]:
    out = []
    for p in Path(cache_dir).glob("*/*.json"):
        r = json.loads(p.read_text(encoding="utf-8"))
        if "step" in r and "prompt_tokens" in r:           # entradas de ferramentas (compile/scan) nao tem esses campos
            out.append(r)
    return out


def subset_gt(gt: mt.GT, files: set[str]) -> mt.GT:
    return mt.GT([i for i in gt.issues if i["file"] in files], [i for i in gt.fps if i["file"] in files],
                 {k: v for k, v in gt.file_class.items() if k in files})


# --------------------------------------------------------------------------- 1. piloto
def pilot_section(out: Path, gt: mt.GT, hier, fams) -> list[str]:
    L = ["## 1. Piloto: custo, falhas e exemplos", ""]
    runs = out / "runs"
    configs = [c for c in ("B0", "B1", "C1", "C2", "C3", "C3mf") if (runs / c / "main").is_dir()]
    res = {c: mt.load_runs(runs, c, "main") for c in configs}
    files = set().union(*[set(r) for r in res.values()]) if res else set()
    L.append(f"Arquivos: {len(files)} ({sum(1 for f in files if gt.file_class.get(f) == 'positive')} positivos, "
             f"{sum(1 for f in files if gt.file_class.get(f) == 'negative')} negativos). Configuracoes: {', '.join(configs)}.\n")
    rows = []
    for c in configs:
        u = defaultdict(float)
        for r in res[c].values():
            for k in ("calls", "prompt_tokens", "completion_tokens", "seconds", "failures", "refusals"):
                u[k] += r["usage"][k]
        n = len(res[c])
        rows.append({"config": c, "arquivos": n, "chamadas/arq": round(u["calls"] / n, 1), "tokens entrada/arq": round(u["prompt_tokens"] / n),
                     "tokens saida/arq": round(u["completion_tokens"] / n), "s de chamada/arq": round(u["seconds"] / n, 1),
                     "falhas": int(u["failures"]), "recusas": int(u["refusals"])})
    L += [pd.DataFrame(rows).to_markdown(index=False), "",
          "As chamadas compartilhadas (A1, A3a, A2) contam em todas as configuracoes que as usam; o custo real total e o das etapas unicas (tabela abaixo).", ""]
    calls = load_cache_calls(out / "cache")
    by = defaultdict(lambda: defaultdict(float))
    for r in calls:
        s = by[r["step"]]
        s["n"] += 1; s["prompt"] += r["prompt_tokens"]; s["comp"] += r["completion_tokens"]; s["sec"] += r["seconds"]
        s["schema_fail"] += r["schema_failures"]; s["errors"] += int(not r["ok"]); s["refusal"] += int(r["refusal"]); s["retried"] += int(r["attempts"] > 1)
    rows = [{"etapa": k, "chamadas unicas": int(v["n"]), "tokens saida/chamada": round(v["comp"] / v["n"]), "tok/s por requisicao": round(v["comp"] / v["sec"], 1) if v["sec"] else None,
             "s/chamada": round(v["sec"] / v["n"], 1), "falhas de schema": int(v["schema_fail"]), "chamadas sem sucesso": int(v["errors"]), "recusas": int(v["refusal"]),
             "com repeticao": int(v["retried"])} for k, v in sorted(by.items())]
    tot = sum(v["n"] for v in by.values())
    L += ["### Chamadas unicas por etapa (cache)", "", pd.DataFrame(rows).to_markdown(index=False), "",
          f"Total: {int(tot)} chamadas unicas; sem sucesso: {int(sum(v['errors'] for v in by.values()))} ({100 * sum(v['errors'] for v in by.values()) / max(tot, 1):.1f}%); "
          f"falhas de schema: {int(sum(v['schema_fail'] for v in by.values()))}; recusas: {int(sum(v['refusal'] for v in by.values()))}.", ""]
    # achados por arquivo do A1
    if "B1" in res:
        pos = [len(r["findings"]) for f, r in res["B1"].items() if gt.file_class.get(f) == "positive"]
        neg = [len(r["findings"]) for f, r in res["B1"].items() if gt.file_class.get(f) == "negative"]
        nov = sum(1 for r in res["B1"].values() if r.get("no_vulnerability"))
        L += [f"A1 (B1): media de achados por arquivo = {sum(pos + neg) / max(len(pos + neg), 1):.2f} (positivos {sum(pos) / max(len(pos), 1):.2f}, "
              f"negativos {sum(neg) / max(len(neg), 1):.2f}); respondeu 'nenhuma vulnerabilidade' em {nov} de {len(res['B1'])} arquivos.", ""]
    # descritivo no subconjunto do piloto (denominadores do piloto, nao os globais)
    sub = subset_gt(gt, files)
    rows = []
    for c in configs:
        ev = mt.evaluate_run(res[c], sub, c, "main", hierarchy=hier, families=fams)
        m = ev.metrics()
        rows.append({"config": c, "issues reais acusados": f"{len(ev.accused_real)}/{ev.n_real}", "falsos alarmes conhecidos acusados": f"{len(ev.accused_fp)}/{ev.n_fp}",
                     "achados fora do gabarito": m["n_out"], "arquivos negativos sinalizados": f"{m['files_flagged_neg']}/{m['n_neg_files']}"})
    L += ["### Descritivo no subconjunto do piloto (so ilustra: amostra pequena)", "", pd.DataFrame(rows).to_markdown(index=False), ""]
    # exemplos de veredito
    ex = defaultdict(list)
    for f, r in (res.get("C1") or {}).items():
        for row in r["findings"]:
            v = row.get("verdict")
            if v and len(ex[v]) < 2:
                ex[v].append((f, row["finding"], (row["a3a"].get("parsed") or {})))
    L.append("### Exemplos de veredito do A3a (2 de cada tipo)\n")
    for v in ("confirmed", "refuted", "uncertain"):
        L.append(f"**{v}** ({len(ex[v])} exemplos)")
        for f, fi, p in ex[v]:
            L.append(f"- `{f}` {fi['cwe']} linhas {fi['lines']} - {fi['title']}. Refutacao tentada: {str(p.get('refutation_attempt', ''))[:300]}")
        L.append("")
    return L


# --------------------------------------------------------------------------- 2. determinismo
def determinism_section(out: Path) -> list[str]:
    rep = json.loads((out / "run_report.json").read_text(encoding="utf-8")) if (out / "run_report.json").exists() else {}
    st = rep.get("stages", {}).get("determinism")
    L = ["## 2. Determinismo (temperature=0, seed=0, repetido com cache novo)", ""]
    if not st or not st.get("ok"):
        return L + ["Etapa nao executada ou com erro: " + (st or {}).get("error", "sem dados")[-300:], ""]
    r = st["result"]
    c = r["calls"]
    L += [f"Chamadas comparaveis (mesma entrada nas duas execucoes): {c['common_calls']}; respostas identicas: {c['identical_calls']} "
          f"({100 * (c['fraction_identical'] or 0):.1f}%). So na 1a execucao: {c['only_in_a']}; so na 2a: {c['only_in_b']} (entradas que dependiam de saidas que mudaram).", "",
          pd.DataFrame([{"etapa": k, "comparaveis": v["common"], "identicas": v["identical"], "fracao": round(v["fraction_identical"], 3) if v["fraction_identical"] is not None else None}
                        for k, v in c["per_step"].items()]).to_markdown(index=False), "",
          "Conjunto de achados aceitos por arquivo, igual nas duas execucoes:", "",
          pd.DataFrame([{"config": k, "arquivos": v["files"], "iguais": v["same_accepted_set"], "fracao": v["fraction"]} for k, v in r["accepted_sets"].items()]).to_markdown(index=False), ""]
    return L


# --------------------------------------------------------------------------- 3. validacao do julgamento de correcao
def fix_validation_section(out: Path, gt: mt.GT, labels: pd.DataFrame) -> list[str]:
    L = ["## 3. Validacao do julgamento automatico de correcao (patches do GPT-4.1 do artigo, 56 issues)", ""]
    d = out / "f4" / "fix_validation"
    if not d.is_dir():
        return L + ["Sem dados.", ""]
    by_id = {i["id"]: i for i in gt.issues}
    lab = labels[(labels.model == "gpt-4.1") & (labels.status == "real")].set_index("issue_id")
    rows = []
    for p in sorted(d.glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        if "issue_id" not in r:
            continue
        iss = by_id[r["issue_id"]]
        crit = mt.fix_criteria({"fix_verdict": r["fix_verdict"], "tools": r["tools"]}, iss)
        rows.append({"issue_id": r["issue_id"], "lang": r["lang"], "verdict": r["fix_verdict"], **crit, "label": bool(lab.loc[r["issue_id"], "fixed"]),
                     "label_sheet": lab.loc[r["issue_id"], "fixed_sheet"], "judged": r["a3b"]["ok"]})
    df = pd.DataFrame(rows)
    if df.empty:
        return L + ["Sem casos.", ""]
    df.to_csv(RESULTS / "f4_fix_validation_cases.csv", index=False, lineterminator="\n")
    ok = df[df.judged]
    y = ok.label.tolist()
    nf = lambda s: s.map(lambda v: v is not False)  # noqa: E731
    variants = {
        "A3b = valid": ok.verdict.eq("valid"),
        "A3b valid ou partial": ok.verdict.isin(["valid", "partial"]),
        "A3b valid e criterios 2-4 sem falha (plano)": ok.verdict.eq("valid") & nf(ok.rule_gone) & nf(ok.compiles) & nf(ok.no_new_warning),
        "so ferramentas (regra sumiu, compila, sem novo warning)": ok.rule_gone.eq(True) & nf(ok.compiles) & nf(ok.no_new_warning),
        "todos os patches = corrigido (linha de base)": pd.Series(True, index=ok.index),
    }
    tab = [{"variante": k, **agree(y, [bool(x) for x in v])} for k, v in variants.items()]
    L += [f"Casos julgados: {len(ok)} de {len(df)}. Rotulo dos autores ('Was issue fixed', GPT-4.1, Tabelas 13/14): {sum(y)} corrigidos, {len(y) - sum(y)} nao.", "",
          pd.DataFrame(tab).to_markdown(index=False), "",
          "Cobertura dos criterios automaticos (True / False / nao verificavel):", "",
          pd.DataFrame([{"criterio": k, "True": int((df[k] == True).sum()), "False": int((df[k] == False).sum()), "nao verificavel": int(df[k].isna().sum())}  # noqa: E712
                        for k in ("verdict_valid", "rule_gone", "compiles", "no_new_warning")]).to_markdown(index=False), "",
          "Veredito do A3b x rotulo dos autores:", "", pd.crosstab(ok.verdict, ok.label.map({True: "corrigido", False: "nao corrigido"})).to_markdown(), ""]
    if "label_sheet" in ok:
        alt = ok.label_sheet.map(lambda v: v if isinstance(v, bool) else None)
        m = alt.notna()
        if m.any():
            L += [f"Sensibilidade com o rotulo da planilha (onde ha; {int(m.sum())} casos): kappa de 'A3b = valid' = "
                  f"{agree([bool(x) for x in alt[m]], [bool(x) for x in variants['A3b = valid'][m]])['kappa']}.", ""]
    return L


# --------------------------------------------------------------------------- 4. extracao estruturada x regra da F6
def extraction_section(out: Path, gt: mt.GT, labels: pd.DataFrame, hier, fams) -> list[str]:
    L = ["## 5. Regra da F6 (linha +-3 + CWE compativel) sobre as respostas do artigo, extraidas em forma estruturada", ""]
    base = out / "f4" / "paper_extract"
    if not base.is_dir():
        return L + ["Sem dados.", ""]
    lab = labels[labels.status == "real"].set_index(["issue_id", "model"])["detected"].astype(bool)
    rows, per_model = [], []
    for m in MODELS:
        res = {}
        for p in sorted((base / m).glob("*.json")) if (base / m).is_dir() else []:
            r = json.loads(p.read_text(encoding="utf-8"))
            if "file" not in r:
                continue
            res[r["file"]] = {"file": r["file"], "findings": [{"finding": {"id": f"E{i}", "cwe": f["cwe"], "lines": f["lines"], "title": f["description"], "confidence": None},
                                                               "accepted": True, "accepted_sens": True} for i, f in enumerate(r["findings"], 1)],
                              "ok": r["ok"]}
        if not res:
            continue
        files = set(res)
        sub = subset_gt(gt, files)
        for tag, kw in (("linha +-3 e CWE compativel (regra da F6)", {}), ("so linha +-3 (sensibilidade)", {"require_cwe": False})):
            ev = mt.evaluate_run(res, sub, m, "paper", hierarchy=hier, families=fams, **kw)
            issues = [i for i in sub.issues]
            y = [bool(lab[(i["id"], m)]) for i in issues]
            pred = [i["id"] in ev.accused_real for i in issues]
            a = agree(y, pred)
            mm = ev.metrics()
            rows.append({"modelo": m, "regra": tag, **a})
            if not kw:
                per_model.append({"modelo": m, "arquivos": len(files), "extracoes sem sucesso": sum(1 for r in res.values() if not r["ok"]),
                                  "achados/arquivo": round(mm["findings_per_file"], 2), "achados/arq. negativo": round(sum(len(res[f]["findings"]) for f in files if gt.file_class.get(f) == "negative") / max(1, sum(1 for f in files if gt.file_class.get(f) == "negative")), 2),
                                  "issues reais acusados": f"{len(ev.accused_real)}/{ev.n_real} (autores: {int(sum(y))})",
                                  "falsos alarmes conhecidos acusados": f"{len(ev.accused_fp)}/{ev.n_fp}", "arquivos negativos sinalizados": f"{mm['files_flagged_neg']}/{mm['n_neg_files']}"})
    if not rows:
        return L + ["Sem extracoes.", ""]
    L += ["Concordancia com os rotulos 'detected' dos autores (referencia: kappa >= 0,7):", "", pd.DataFrame(rows).to_markdown(index=False), "",
          "Indicadores da configuracao original do artigo no regime estruturado (base de comparacao para a E1):", "", pd.DataFrame(per_model).to_markdown(index=False), ""]
    return L


# --------------------------------------------------------------------------- 5b. calibracao do A3a
def calibration_section(out: Path, gt: mt.GT) -> list[str]:
    """A3a sobre achados do scanner: confirma o que os autores consideram real e refuta o que consideram seguro?"""
    from scipy.stats import fisher_exact
    base = out / "f4" / "verifier_calibration"
    if not base.is_dir():
        return []
    real_ids = {i["id"]: i for i in gt.issues}
    fp_ids = {i["id"] for i in gt.fps}
    rows = []
    for p in sorted(base.glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        if "case_id" not in r:
            continue
        cid = r["case_id"]
        rows.append({"case_id": cid, "classe": "real" if cid in real_ids else ("falso alarme" if cid in fp_ids else "?"), "verdict": r.get("verdict") or "falha",
                     "quality_only": bool(real_ids[cid]["quality_only"]) if cid in real_ids else None, "lang": r.get("finding", {}).get("lang")})
    df = pd.DataFrame(rows)
    L = ["## 4. Calibracao do verificador (A3a sobre achados do scanner: 56 issues reais x 85 falsos alarmes conhecidos)", ""]
    if df.empty:
        return L + ["Sem dados.", ""]
    tab = pd.crosstab(df["classe"], df["verdict"])
    L += [tab.to_markdown(), ""]
    n_r, n_f = int((df.classe == "real").sum()), int((df.classe == "falso alarme").sum())
    c_r, c_f = int(((df.classe == "real") & (df.verdict == "confirmed")).sum()), int(((df.classe == "falso alarme") & (df.verdict == "confirmed")).sum())
    u_r, u_f = int(((df.classe == "real") & (df.verdict.isin(["confirmed", "uncertain"]))).sum()), int(((df.classe == "falso alarme") & (df.verdict.isin(["confirmed", "uncertain"]))).sum())
    _, pval = fisher_exact([[c_r, n_r - c_r], [c_f, n_f - c_f]])
    L += [f"- Sensibilidade (issue real confirmada): {c_r}/{n_r} = {c_r / max(1, n_r):.2f}; com 'uncertain' como aceito: {u_r}/{n_r} = {u_r / max(1, n_r):.2f}.",
          f"- Falso alarme conhecido confirmado: {c_f}/{n_f} = {c_f / max(1, n_f):.2f} (especificidade {1 - c_f / max(1, n_f):.2f}); com 'uncertain': {u_f}/{n_f}.",
          f"- Fisher exato (confirmado: real x falso alarme): p = {pval:.3g}.", ""]
    q = df[(df.classe == "real")]
    if q["quality_only"].notna().any():
        qt = pd.crosstab(q["quality_only"].map({True: "so qualidade (nao seguranca)", False: "seguranca"}), q["verdict"])
        L += ["Issues reais por tipo (rotulo dos autores):", "", qt.to_markdown(), ""]
    return L


# --------------------------------------------------------------------------- 6. projecao de horas de GPU
def projection_section(out: Path, n_files_total: int = 114, weekly_quota: float = 30.0) -> list[str]:
    """Projeta as horas de GPU da execucao completa a partir dos tempos reais do piloto (PARADA 2).

    Execucao principal: tempo de parede da etapa 'pipeline' do piloto / n. de arquivos x 114.
    Cada repeticao do estudo de variancia (so B1 e C3): o tempo da principal x (carga do servidor mais ocupado em B1+C3) /
    (carga do servidor mais ocupado em todas as configuracoes), com a carga = segundos de chamada / requisicoes simultaneas."""
    L = ["## 6. Projecao de horas de GPU (execucao completa)", ""]
    rep_path = out / "run_report.json"
    if not rep_path.exists():
        return L + ["Sem run_report.json.", ""]
    rep = json.loads(rep_path.read_text(encoding="utf-8"))
    st = rep.get("stages", {}).get("pipeline")
    if not st or not st.get("ok"):
        return L + ["Etapa 'pipeline' sem sucesso.", ""]
    done = st["result"]["reps"]["main"]["done"]
    wall_main = st["seconds"] / max(done, 1) * n_files_total
    calls = load_cache_calls(out / "cache")
    sec = defaultdict(float)
    for r in calls:
        sec[r["step"]] += r["seconds"]
    par_det = (rep.get("detector_final") or {}).get("num_parallel", 1)
    par_ver = 4
    # fracao dos patches (A2) que o C3 usa: so os confirmados; aproximada pela razao a3b / a3joint (mesmos achados, mesma ordem de grandeza)
    n_by = Counter(r["step"] for r in calls)
    frac_conf = min(1.0, n_by["a3b"] / n_by["a2"]) if n_by["a2"] else 1.0
    det_main = sec["a1"] + sec["a2"] + sec["b0_response"] + sec["b0_extract"]
    ver_main = sec["a3a"] + sec["a3joint"] + sec["a3b"]
    det_var = sec["a1"] + sec["a2"] * frac_conf
    ver_var = sec["a3a"] + sec["a3b"]
    load_main = max(det_main / par_det, ver_main / par_ver)
    load_var = max(det_var / par_det, ver_var / par_ver)
    wall_var = wall_main * (load_var / load_main) if load_main else float("nan")
    extra = rep["stages"].get("determinism", {}).get("seconds", 0) / 3600
    tot = wall_main / 3600 + 3 * wall_var / 3600
    L += [f"Piloto: {done} arquivos em {st['seconds']:.0f} s de parede (todas as configuracoes) -> {st['seconds'] / max(done, 1):.0f} s/arquivo.", "",
          pd.DataFrame([
              {"item": "execucao principal (114 arquivos, B0+B1+C1+C2+C3)", "horas": round(wall_main / 3600, 1)},
              {"item": "1 repeticao do estudo de variancia (B1+C3)", "horas": round(wall_var / 3600, 1)},
              {"item": "estudo de variancia (3 repeticoes)", "horas": round(3 * wall_var / 3600, 1)},
              {"item": "principal + variancia", "horas": round(tot, 1)},
              {"item": "extracao das respostas dos 66 arquivos negativos (E1), estimada", "horas": "ver etapa paper_extraction"},
              {"item": "cota semanal do Kaggle", "horas": weekly_quota},
          ]).to_markdown(index=False), "",
          f"Carga dos servidores no piloto (s de chamada / paralelismo): detector {det_main / par_det:.0f} s (paralelismo {par_det}), verificador {ver_main / par_ver:.0f} s (paralelismo {par_ver}).",
          f"Fracao dos patches do A2 que o C3 usa (confirmados): {frac_conf:.2f}.", "",
          "Estimativa linear: assume que os 114 arquivos se parecem com os 10 do piloto e que a vazao dos servidores nao muda.", ""]
    return L


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    RESULTS.mkdir(exist_ok=True)
    gt = mt.load_gt(DATA)
    labels = pd.read_csv(DATA / "paper_labels.csv")
    hier = CWEHierarchy.from_xml(DATA / "cwe" / "1000.xml")
    fams = load_families(HERE / "matching_families.yaml")
    L = ["# F4 - piloto", ""]
    for name, fn in (("pilot", lambda: pilot_section(out, gt, hier, fams)), ("determinism", lambda: determinism_section(out)),
                     ("fix", lambda: fix_validation_section(out, gt, labels)), ("calib", lambda: calibration_section(out, gt)),
                     ("extract", lambda: extraction_section(out, gt, labels, hier, fams)),
                     ("projection", lambda: projection_section(out))):
        try:
            L += fn()
        except Exception as e:  # noqa: BLE001 - uma secao com problema nao impede as outras
            import traceback
            L += [f"## ({name}) ERRO na analise", "", "```", traceback.format_exc()[-800:], "```", ""]
    rep = out / "run_report.json"
    if rep.exists():
        r = json.loads(rep.read_text(encoding="utf-8"))
        L += ["## 7. Tempo de sessao", "", f"Sessao total: {r.get('session_hours')} h. Etapas: " + ", ".join(f"{k}={v['seconds']}s ({'ok' if v['ok'] else 'ERRO'})" for k, v in r.get("stages", {}).items()), ""]
        if r.get("detector_final"):
            L += [f"Detector final: {r['detector_final']}.", ""]
    (RESULTS / "f4_piloto.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
