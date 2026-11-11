"""F4 - jobs do piloto alem do runner: (1) validacao do A3b nos patches do GPT-4.1 do artigo, (2) extracao estruturada das
respostas do artigo (valida a regra da F6 no regime estruturado), (3) comparacao de duas execucoes (teste de determinismo)."""
from __future__ import annotations

import concurrent.futures as cf
import json
import re
import threading
from pathlib import Path

from agents import CodeItem, Ctx
from agents.detector import run_b0_extract
from agents.verifier import run_a3b
from canonical import MODELS
from dataset import read_text
from llm import sum_usage
from runner import FileTools, compact


def safe_name(s: str) -> str:
    """Nome de arquivo seguro: ids como 'v8:1/1a' tem ':' e '/'."""
    return re.sub(r"[^A-Za-z0-9_.-]", "_", s)


def _write(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def load_fix_cases(path: str | Path) -> list[dict]:
    return [json.loads(line) for line in open(path, encoding="utf-8")]


def _pool(fn, items, workers: int, log=print, label: str = "") -> list:
    results, lock = [], threading.Lock()

    def wrap(x):
        try:
            r = fn(x)
        except Exception as e:  # noqa: BLE001 - um caso com erro nao derruba o job
            r = {"error": repr(e), "item": str(x)[:80]}
        with lock:
            results.append(r)
            if len(results) % 10 == 0:
                log(f"[{label}] {len(results)}/{len(items)}")
        return r

    with cf.ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        list(ex.map(wrap, items))
    return results


# --------------------------------------------------------------------------- 1. A3b nos patches do artigo
def run_fix_validation(ctx: Ctx, cases: list[dict], raw_root: Path, out_dir: Path, workers: int = 4, log=print) -> dict:
    """Aplica o A3b (com as ferramentas) ao patch do GPT-4.1 de cada um dos 56 issues. Grava f4/fix_validation/<issue>.json.
    Os criterios automaticos e a comparacao com 'Was issue fixed' sao calculados depois, localmente (f4_analyze.py)."""
    def one(case: dict) -> dict:
        dst = out_dir / "fix_validation" / f"{safe_name(case['issue_id'])}.json"
        if dst.exists():
            return json.loads(dst.read_text(encoding="utf-8"))
        code, patch = read_text(raw_root / case["code_path"]), read_text(raw_root / case["patch_path"])
        item = CodeItem(case["file"], case["snapshot"], case["file_number"], case["lang"], case["ext"], code, "")
        ft = FileTools(ctx.tools, item)
        report = ft.report_for(case["finding"], patch)
        rec = run_a3b(ctx, item, case["finding"], patch, report)
        out = {"issue_id": case["issue_id"], "file": case["file"], "lang": case["lang"], "finding": case["finding"],
               "patch_chars": len(patch), "tools": ft.stored(patch), "report": report, "a3b": compact(rec),
               "fix_verdict": rec["parsed"]["fix_verdict"] if rec["ok"] else None, "usage": sum_usage([rec])}
        _write(dst, out)
        return out

    res = _pool(one, cases, workers, log, "fix_validation")
    ok = [r for r in res if r.get("a3b", {}) and r["a3b"].get("ok")]
    return {"cases": len(cases), "judged": len(ok), "errors": [r for r in res if "error" in r][:5],
            "usage": sum_usage([r["a3b"] for r in res if r.get("a3b")])}


# --------------------------------------------------------------------------- 1a. A3b nos patches do B0
def run_b0_fix_validation(ctx: Ctx, items: list[CodeItem], b0_dir: Path, out_dir: Path, workers: int = 4, log=print) -> dict:
    """Aplica o A3b (o MESMO do C3: gpt-oss, mesmo prompt, mesmo relatorio de ferramentas) ao patch do B0 de cada arquivo, uma vez por achado
    extraido do B0 (o patch do B0 e o ultimo bloco de codigo da resposta, um so por arquivo, para todos os achados). `b0_dir` = runs/B0/main
    (o patch e os achados vem de la; nada do gabarito). Grava f4/b0_fix_validation/<arquivo>.json; que achados contam fica para a analise."""
    from runner import safe_name as run_safe

    def one(item: CodeItem) -> dict:
        dst = out_dir / "b0_fix_validation" / f"{safe_name(item.id)}.json"
        if dst.exists():
            return json.loads(dst.read_text(encoding="utf-8"))
        b0 = json.loads((Path(b0_dir) / f"{run_safe(item.id)}.json").read_text(encoding="utf-8"))
        patch, findings = b0.get("patch"), [row["finding"] for row in b0["findings"]]
        rows, recs, tools = [], [], None
        if patch and findings:
            ft = FileTools(ctx.tools, item)
            for f in findings:
                rec = run_a3b(ctx, item, f, patch, ft.report_for(f, patch))
                recs.append(rec)
                rows.append({"finding_id": f["id"], "a3b": compact(rec), "fix_verdict": rec["parsed"]["fix_verdict"] if rec["ok"] else None})
            tools = ft.stored(patch)
        out = {"file": item.id, "patch_chars": len(patch or ""), "n_findings": len(findings), "tools": tools, "rows": rows, "usage": sum_usage(recs)}
        _write(dst, out)
        return out

    res = _pool(one, items, workers, log, "b0_fix_validation")
    done = [r for r in res if "error" not in r]
    return {"files": len(items), "files_with_patch": sum(1 for r in done if r["tools"] is not None),
            "judged": sum(1 for r in done for x in r["rows"] if x["fix_verdict"]), "judgements": sum(len(r["rows"]) for r in done),
            "errors": [r for r in res if "error" in r][:5],
            "usage": sum_usage([x["a3b"] for r in done for x in r["rows"]])}


# --------------------------------------------------------------------------- 1b. calibracao do A3a (sensibilidade e especificidade)
def run_verifier_calibration(ctx: Ctx, cases: list[dict], raw_root: Path, out_dir: Path, workers: int = 4, log=print) -> dict:
    """A3a sobre achados reconstruidos so do relatorio do scanner: 56 issues reais + 85 falsos alarmes conhecidos (sem rotulo no
    arquivo de casos). Mede quanto o verificador confirma do que os autores consideram real e refuta do que consideram seguro,
    sem o ruido do detector. Grava f4/verifier_calibration/<caso>.json."""
    from agents.verifier import run_a3a

    def one(case: dict) -> dict:
        dst = out_dir / "verifier_calibration" / f"{safe_name(case['case_id'])}.json"
        if dst.exists():
            return json.loads(dst.read_text(encoding="utf-8"))
        item = CodeItem(case["file"], case["snapshot"], case["file_number"], case["lang"], case["ext"], read_text(raw_root / case["code_path"]), "")
        rec = run_a3a(ctx, item, case["finding"])
        out = {"case_id": case["case_id"], "file": case["file"], "finding": case["finding"], "a3a": compact(rec),
               "verdict": rec["parsed"]["verdict"] if rec["ok"] else None, "usage": sum_usage([rec])}
        _write(dst, out)
        return out

    res = _pool(one, cases, workers, log, "verifier_calibration")
    return {"cases": len(cases), "judged": sum(1 for r in res if r.get("verdict")), "errors": [r for r in res if "error" in r][:5],
            "usage": sum_usage([r["a3a"] for r in res if r.get("a3a")])}


# --------------------------------------------------------------------------- 2. extracao das respostas do artigo
def run_paper_extraction(ctx: Ctx, files: list[dict], raw_root: Path, out_dir: Path, workers: int = 2, log=print,
                         models: list[str] | None = None) -> dict:
    """Extrai achados estruturados (CWE, linhas, descricao) das LLM_Response.md do artigo, com o mesmo extrator do B0.
    Serve para medir o kappa da regra 'linha +-3 + CWE compativel' contra os rotulos 'detected' dos autores."""
    jobs = [(rec, m) for rec in files for m in (models or list(MODELS))]

    def one(job: tuple) -> dict:
        rec, m = job
        dst = out_dir / "paper_extract" / m / f"{safe_name(rec['snapshot'] + '_' + rec['folder'])}.json"
        if dst.exists():
            return json.loads(dst.read_text(encoding="utf-8"))
        code = read_text(raw_root / rec["code"]["path"])
        item = CodeItem(f"{rec['snapshot']}:{rec['folder']}", rec["snapshot"], rec["file_number"], rec["language"], rec["code"]["ext"], code, "")
        text = read_text(raw_root / rec["models"][m]["response"])
        r = run_b0_extract(ctx, item, text)
        out = {"file": item.id, "paper_model": m, "ok": r["ok"], "findings": (r["parsed"]["findings"] if r["ok"] else []),
               "response_chars": len(text), "usage": sum_usage([r]), "step": compact(r)}
        _write(dst, out)
        return out

    res = _pool(one, jobs, workers, log, "paper_extract")
    return {"jobs": len(jobs), "ok": sum(1 for r in res if r.get("ok")), "errors": [r for r in res if "error" in r][:5],
            "usage": sum_usage([{"prompt_tokens": r["usage"]["prompt_tokens"], "completion_tokens": r["usage"]["completion_tokens"],
                                 "seconds": r["usage"]["seconds"], "ok": r["ok"], "refusal": False} for r in res if "usage" in r])}


# --------------------------------------------------------------------------- 3. determinismo
def compare_caches(dir_a: Path, dir_b: Path) -> dict:
    """Compara as respostas brutas de duas execucoes pela chave de cache (mesma entrada -> mesma chave).
    So as chamadas cuja entrada foi identica nas duas execucoes sao comparaveis; as demais dependem de saidas anteriores que mudaram."""
    def load(root: Path) -> dict:
        out = {}
        for p in Path(root).glob("*/*.json"):
            r = json.loads(p.read_text(encoding="utf-8"))
            if "cache_key" in r:
                out[r["cache_key"]] = r
        return out

    a, b = load(dir_a), load(dir_b)
    per: dict[str, dict] = {}
    for k, ra in a.items():
        s = per.setdefault(ra["step"], {"in_a": 0, "common": 0, "identical": 0, "parsed_identical": 0})
        s["in_a"] += 1
        rb = b.get(k)
        if rb is not None:
            s["common"] += 1
            s["identical"] += int(ra["content"] == rb["content"])
            s["parsed_identical"] += int(ra["parsed"] == rb["parsed"])
    for s in per.values():
        s["fraction_identical"] = s["identical"] / s["common"] if s["common"] else None
    tot_c = sum(s["common"] for s in per.values())
    tot_i = sum(s["identical"] for s in per.values())
    return {"per_step": per, "common_calls": tot_c, "identical_calls": tot_i,
            "fraction_identical": tot_i / tot_c if tot_c else None, "only_in_a": len(set(a) - set(b)), "only_in_b": len(set(b) - set(a))}


def _finding_key(f: dict) -> tuple:
    return (str(f.get("cwe")), tuple(f.get("lines") or []))


def compare_runs(runs_a: Path, runs_b: Path, configs: list[str], rep: str = "main") -> dict:
    """Por (configuracao, arquivo): o conjunto de achados aceitos e igual nas duas execucoes?"""
    out = {}
    for c in configs:
        n = same = 0
        for pa in sorted((Path(runs_a) / c / rep).glob("*.json")):
            pb = Path(runs_b) / c / rep / pa.name
            if not pb.exists():
                continue
            ra, rb = json.loads(pa.read_text(encoding="utf-8")), json.loads(pb.read_text(encoding="utf-8"))
            ka = sorted(_finding_key(x["finding"]) for x in ra["findings"] if x.get("accepted"))
            kb = sorted(_finding_key(x["finding"]) for x in rb["findings"] if x.get("accepted"))
            n += 1
            same += int(ka == kb)
        out[c] = {"files": n, "same_accepted_set": same, "fraction": same / n if n else None}
    return out
