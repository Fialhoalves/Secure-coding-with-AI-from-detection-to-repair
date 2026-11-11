"""Metricas. Funcoes puras sobre os resultados em runs/ e o gabarito.

Conjunto rotulado pelos autores: 56 issues reais + 85 falsos alarmes conhecidos. Uma configuracao ACUSA um local quando
algum achado aceito casa com ele (arquivo, linha a +-3, CWE compativel; ver matching.finding_matches_issue).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from matching import finding_matches_issue
from tools.scan import diff_scans

QUALITY_ONLY_REASON = "cwe 561/1164"


@dataclass
class GT:
    issues: list[dict]           # {'id','file','line','cwe_ids':[int],'quality_only':bool,'scanners','scanner_types'}
    fps: list[dict]
    file_class: dict[str, str]   # 'v8:File_01' -> positive | negative

    def by_file(self) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
        ri: dict[str, list[dict]] = {}
        rf: dict[str, list[dict]] = {}
        for i in self.issues:
            ri.setdefault(i["file"], []).append(i)
        for i in self.fps:
            rf.setdefault(i["file"], []).append(i)
        return ri, rf


def _ints(s) -> list[int]:
    return [int(x) for x in str(s).split("|") if x not in ("", "nan")] if pd.notna(s) else []


def _file_id(snapshot: str, number: int) -> str:
    return f"{snapshot}:File_{int(number):02d}"


def load_gt(data_dir: str | Path) -> GT:
    d = Path(data_dir)
    gi, gf = pd.read_csv(d / "gt_issues.csv"), pd.read_csv(d / "gt_scanner_fp.csv")

    def rows(df: pd.DataFrame) -> list[dict]:
        return [{"id": r.issue_id, "file": _file_id(r.snapshot, r.file_number), "line": int(r.line), "cwe_ids": _ints(r.cwe_ids),
                 "quality_only": bool(getattr(r, "quality_only", False)), "scanners": str(r.scanners).split("|"),
                 "scanner_types": [x for x in str(r.scanner_types).split("|") if x and x != "nan"],
                 "source_code": r.source_code if pd.notna(r.source_code) else None} for r in df.itertuples()]

    cls = {}
    for line in open(d / "files.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r["class"] in ("positive", "negative"):
            cls[_file_id(r["snapshot"], r["file_number"])] = r["class"]
    return GT(rows(gi), rows(gf), cls)


def load_runs(runs_dir: str | Path, config: str, rep: str) -> dict[str, dict]:
    """{file_id: resultado} de runs/<config>/<rep>/*.json."""
    out = {}
    for p in sorted((Path(runs_dir) / config / rep).glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        out[r["file"]] = r
    return out


# --------------------------------------------------------------------------- casamento com o gabarito
def labeled_metrics(tp: int, fp: int, n_real: int, n_fp: int) -> dict:
    """Metricas no conjunto rotulado. TP/FP = locais acusados (reais / falsos alarmes conhecidos)."""
    fn, tn = n_real - tp, n_fp - fp
    prec = tp / (tp + fp) if (tp + fp) else float("nan")
    rec = tp / n_real if n_real else float("nan")
    far = fp / n_fp if n_fp else float("nan")

    def fbeta(b: float) -> float:
        d = (1 + b * b) * tp + b * b * fn + fp
        return (1 + b * b) * tp / d if d else float("nan")

    den = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    mcc = (tp * tn - fp * fn) / den if den else float("nan")
    return {"recall": rec, "false_alarm_rate": far, "precision": prec, "f1": fbeta(1.0), "f05": fbeta(0.5), "mcc": mcc,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn}


@dataclass
class RunEval:
    config: str
    rep: str
    accused_real: set = field(default_factory=set)
    accused_fp: set = field(default_factory=set)
    per_file: pd.DataFrame = field(default_factory=pd.DataFrame)   # uma linha por arquivo analisado
    finding_rows: list = field(default_factory=list)               # classificacao de cada achado aceito
    n_real: int = 0
    n_fp: int = 0

    def metrics(self) -> dict:
        m = labeled_metrics(len(self.accused_real), len(self.accused_fp), self.n_real, self.n_fp)
        pf = self.per_file
        pos, neg = pf[pf["cls"] == "positive"], pf[pf["cls"] == "negative"]
        n_new_tp, n_new_fp, n_out = int(pf["tp_new"].sum()), int(pf["fp_new"].sum()), int(pf["out"].sum())
        m.update({
            "files_flagged_pos": int((pos["n_findings"] > 0).sum()), "n_pos_files": len(pos),
            "files_flagged_neg": int((neg["n_findings"] > 0).sum()), "n_neg_files": len(neg),
            "file_sensitivity": float((pos["n_findings"] > 0).mean()) if len(pos) else float("nan"),
            "neg_files_flagged_frac": float((neg["n_findings"] > 0).mean()) if len(neg) else float("nan"),
            "out_per_file_pos": float(pos["out"].mean()) if len(pos) else float("nan"),
            "out_per_file_neg": float(neg["out"].mean()) if len(neg) else float("nan"),
            "findings_per_file": float(pf["n_findings"].mean()) if len(pf) else float("nan"),
            "n_out": n_out,
            # intervalo da precisao geral: fora do gabarito tratado como falso (inferior) ou verdadeiro (superior)
            "precision_overall_low": n_new_tp / (n_new_tp + n_new_fp + n_out) if (n_new_tp + n_new_fp + n_out) else float("nan"),
            "precision_overall_high": (n_new_tp + n_out) / (n_new_tp + n_new_fp + n_out) if (n_new_tp + n_new_fp + n_out) else float("nan"),
        })
        return m


def evaluate_run(results: dict[str, dict], gt: GT, config: str, rep: str, *, hierarchy=None, families=(),
                 flag: str = "accepted", require_cwe: bool = True, only_security: bool = False,
                 tolerance: int = 3) -> RunEval:
    """Classifica os achados aceitos de cada arquivo: tp_new (issue real ainda nao acusado), fp_new (falso alarme conhecido ainda nao
    acusado), dup (casa so com algo ja acusado: fora do numerador e do denominador), out (nao casa com nada)."""
    by_real, by_fp = gt.by_file()
    kw = dict(hierarchy=hierarchy, families=families)
    ev = RunEval(config=config, rep=rep)
    issues_all = [i for i in gt.issues if not (only_security and i["quality_only"])]
    ev.n_real, ev.n_fp = len(issues_all), len(gt.fps)
    rows = []
    for fid, cls in gt.file_class.items():
        r = results.get(fid)
        if r is None:
            continue
        issues = [i for i in by_real.get(fid, []) if not (only_security and i["quality_only"])]
        quality = [i for i in by_real.get(fid, []) if only_security and i["quality_only"]]
        fps = by_fp.get(fid, [])
        n_f = tp_new = fp_new = dup = out = ignored = 0
        for row in r["findings"]:
            if not row.get(flag):
                continue
            f = row["finding"]
            n_f += 1
            hit_r = [i for i in issues if finding_matches_issue(f, i, tolerance=tolerance, require_cwe=require_cwe, **kw)["match"]]
            hit_q = [i for i in quality if finding_matches_issue(f, i, tolerance=tolerance, require_cwe=require_cwe, **kw)["match"]]
            hit_f = [i for i in fps if finding_matches_issue(f, i, tolerance=tolerance, require_cwe=require_cwe, **kw)["match"]]
            kind = "out"
            if hit_r:
                new = [i["id"] for i in hit_r if i["id"] not in ev.accused_real]
                kind = "tp_new" if new else "dup"
                ev.accused_real.update(i["id"] for i in hit_r)
                tp_new += int(bool(new))
                dup += int(not new)
            elif hit_q:
                kind, ignored = "ignored", ignored + 1
            elif hit_f:
                new = [i["id"] for i in hit_f if i["id"] not in ev.accused_fp]
                kind = "fp_new" if new else "dup"
                ev.accused_fp.update(i["id"] for i in hit_f)
                fp_new += int(bool(new))
                dup += int(not new)
            else:
                out += 1
            ev.finding_rows.append({"file": fid, "finding_id": f["id"], "kind": kind, "real": [i["id"] for i in hit_r], "fp": [i["id"] for i in hit_f]})
        rows.append({"file": fid, "cls": cls, "n_findings": n_f - ignored, "tp_new": tp_new, "fp_new": fp_new, "dup": dup, "out": out})
    ev.per_file = pd.DataFrame(rows)
    return ev


def verifier_effect(ref: RunEval, cfg: RunEval) -> dict:
    """Efeito do verificador sobre os achados do A1 (ref = B1 da mesma repeticao): quantos falsos alarmes conhecidos foram
    removidos e quantos verdadeiros positivos foram perdidos (o custo)."""
    fp_ref, tp_ref = ref.accused_fp, ref.accused_real
    removed_fp = fp_ref - cfg.accused_fp
    lost_tp = tp_ref - cfg.accused_real
    out_ref, out_cfg = int(ref.per_file["out"].sum()), int(cfg.per_file["out"].sum())
    return {"fp_removal_rate": len(removed_fp) / len(fp_ref) if fp_ref else float("nan"),
            "tp_loss_rate": len(lost_tp) / len(tp_ref) if tp_ref else float("nan"),
            "out_reduction": (out_ref - out_cfg) / out_ref if out_ref else float("nan"),
            "fp_removed": len(removed_fp), "fp_ref": len(fp_ref), "tp_lost": len(lost_tp), "tp_ref": len(tp_ref)}


# --------------------------------------------------------------------------- curva do limiar de confianca (H4)
def confidence_curve(results: dict[str, dict], gt: GT, **kw) -> pd.DataFrame:
    """Recall x taxa de falsos alarmes conhecidos do B1 quando so se aceitam achados com confianca >= limiar."""
    confs = sorted({row["finding"].get("confidence") for r in results.values() for row in r["findings"]
                    if row["finding"].get("confidence") is not None}, reverse=True)
    out = []
    for t in [1.01] + confs:
        sub = {fid: {**r, "findings": [{**row, "thr": bool((row["finding"].get("confidence") or 0) >= t)} for row in r["findings"]]}
               for fid, r in results.items()}
        m = evaluate_run(sub, gt, "B1", "curve", flag="thr", **kw).metrics()
        out.append({"threshold": t, "recall": m["recall"], "false_alarm_rate": m["false_alarm_rate"], "precision": m["precision"],
                    "findings_per_file": m["findings_per_file"]})
    return pd.DataFrame(out)


# --------------------------------------------------------------------------- correcao
def fix_criteria(row: dict, issue: dict) -> dict:
    """Criterios automaticos de correcao para UM achado aceito que casou com UM issue real.

    1. veredito do A3b (C3) ou do A3 conjunto (C2) e 'valid'
    2. a regra do scanner original deixou de disparar (comparacao de contagens; so scanners re-executaveis)
    3. o patch compila, se o original compilava
    4. nao surgiram achados novos de severidade warning ou maior
    Cada criterio vale True/False, ou None quando nao e verificavel (C#, snyk, original que nao compila...).
    """
    tools = row.get("tools")
    fix_verdict = row.get("fix_verdict")
    c1 = (fix_verdict == "valid") if fix_verdict is not None else None
    if not tools or tools.get("scan_status") == "not_verifiable":
        return {"verdict_valid": c1, "rule_gone": None, "compiles": None, "no_new_warning": None}
    co, cp = tools["compile_orig"], tools["compile_patch"]
    c3 = (cp["status"] == "ok") if co.get("status") == "ok" else None
    before, after = {"findings": tools["scan_orig"], "status": "ok"}, {"findings": tools["scan_patch"], "status": "ok"}
    present = {(f["scanner"], f["rule"]) for f in tools["scan_orig"]}
    wanted = [(s, t) for s in issue.get("scanners", []) for t in issue.get("scanner_types", []) if (s, t) in present]
    d = diff_scans(before, after, target_line=issue["line"], target_rules=wanted or None)
    rule_gone = d["target_gone"]
    c4 = (d["new_warning_or_worse"] == 0) if any(tools.get("available", {}).values()) else None
    return {"verdict_valid": c1, "rule_gone": rule_gone, "compiles": c3, "no_new_warning": c4}


def correction_summary(results: dict[str, dict], gt: GT, ev: RunEval) -> dict:
    """Taxas de correcao de uma configuracao (C2 ou C3): condicional (corrigidas/acusadas) e global (corrigidas/56)."""
    by_id = {i["id"]: i for i in gt.issues}
    best: dict[str, dict] = {}
    for fr in ev.finding_rows:
        if not fr["real"]:
            continue
        r = results[fr["file"]]
        row = next(x for x in r["findings"] if x["finding"]["id"] == fr["finding_id"])
        if row.get("tools") is None and row.get("fix_verdict") is None:
            continue
        for iid in fr["real"]:
            crit = fix_criteria(row, by_id[iid])
            score = sum(v is True for v in crit.values())
            if iid not in best or score > best[iid][1]:
                best[iid] = (crit, score)
    crits = {k: [c[k] for c, _ in best.values()] for k in ("verdict_valid", "rule_gone", "compiles", "no_new_warning")}
    combined = [all(v is not False for v in c.values()) and c["verdict_valid"] is True for c, _ in best.values()]
    n_acc = len(ev.accused_real)
    out = {"accused": n_acc, "with_patch": len(best), "fixed_combined": int(sum(combined)),
           "fix_rate_conditional": sum(combined) / n_acc if n_acc else float("nan"),
           "fix_rate_global": sum(combined) / ev.n_real if ev.n_real else float("nan")}
    for k, v in crits.items():
        out[f"{k}_true"], out[f"{k}_false"], out[f"{k}_na"] = sum(x is True for x in v), sum(x is False for x in v), sum(x is None for x in v)
    return out


def unnecessary_patches(results: dict[str, dict], gt: GT, **kw) -> int:
    """Patches gerados para falsos alarmes conhecidos (correcao desnecessaria): achados do A1 que casam com um falso alarme
    conhecido (e com nenhum issue real) e para os quais houve A2 - aceitos ou nao. Em C3 so os confirmados recebem patch;
    em C2 todos os achados do A1 recebem."""
    sub = {fid: {**r, "findings": [{**row, "_all": True} for row in r["findings"]]} for fid, r in results.items()}
    ev = evaluate_run(sub, gt, "x", "x", flag="_all", **kw)
    n = 0
    for fr in ev.finding_rows:
        if fr["fp"] and not fr["real"]:
            row = next(x for x in sub[fr["file"]]["findings"] if x["finding"]["id"] == fr["finding_id"])
            n += int(row.get("a2") is not None)
    return n
