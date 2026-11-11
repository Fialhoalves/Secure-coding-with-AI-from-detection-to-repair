#!/usr/bin/env python3
"""Kernel de execucao do pipeline no Kaggle. Usado no ensaio em CPU (mode='rehearsal') e no piloto da F4 / execucao da F5 (2x T4).

Etapas (cada uma isolada: um erro nao perde as saidas das outras): ajuste do detector -> pipeline (B0,B1,C1,C2,C3) -> repeticao
para o teste de determinismo -> A3b nos patches do GPT-4.1 do artigo -> extracao estruturada das respostas do artigo.

Parametros do trabalho em JOB (edite e rode `kaggle kernels push -p kaggle/run [--accelerator NvidiaTeslaT4]`).
Saidas em /kaggle/working: runs/, cache/, runs_det/, cache_det/, f4/, run_report.json, run_error.txt.
"""
import copy
import glob
import json
import os
import sys
import time
import traceback
from pathlib import Path

JOB = {
    "mode": "pilot",
    "select": "part:0/2",
    "reps": [
        "main"
    ],
    "configs": None,
    "session_hours": 10.0,
    "tune_detector": False,
    "pipeline": True,
    "determinism": False,
    "fix_validation": False,
    "verifier_calibration": False,
    "paper_extraction": False,
    "extraction_scope": "all",
    "archive": True,
    "limit_cases": None,
    "limit_extraction_files": None,
    "workers": None,
    "rehearsal_model": "qwen2.5-coder:0.5b"
}
OUT = "/kaggle/working"


def main() -> int:
    t0 = time.time()
    os.system("find /kaggle/input -maxdepth 4 | head -40")
    # o Kaggle monta em /kaggle/input/datasets/<dono>/<slug>/ e ACHATA o zip (o conteudo de pipeline/ fica na raiz)
    ds = next((d for d in glob.glob("/kaggle/input/**/taes-pipeline", recursive=True) if os.path.isdir(f"{d}/src")), None)
    if ds is None:
        raise RuntimeError("Dataset taes-pipeline nao encontrado em /kaggle/input (veja a arvore acima)")
    root = "/tmp/proj"                                    # symlink: root/pipeline -> Dataset (caminhos do config.yaml valem)
    os.makedirs(root, exist_ok=True)
    if not os.path.exists(f"{root}/pipeline"):
        os.symlink(ds, f"{root}/pipeline")
    sys.path.insert(0, f"{root}/pipeline/src")
    import f4_jobs
    import kaggle_boot as kb
    from canonical import MODELS
    from config import build_ctx, load_config
    from runner import QuotaGuard, load_items, run

    rehearsal = JOB["mode"] == "rehearsal"
    report = {"job": JOB, "stages": {}}

    def stage(name, fn):
        ts = time.time()
        kb.log(f"===== {name} =====")
        try:
            res = fn()
            report["stages"][name] = {"ok": True, "seconds": round(time.time() - ts, 1), "result": res}
            return res
        except Exception:  # noqa: BLE001
            tb = traceback.format_exc()
            kb.log(f"ERRO em {name}:\n{tb[-1500:]}")
            report["stages"][name] = {"ok": False, "seconds": round(time.time() - ts, 1), "error": tb[-3000:]}
            return None
        finally:
            with open(f"{OUT}/run_report.json", "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    kb.install_tools()
    report["ollama_version"] = kb.install_ollama()
    cfg = load_config(f"{root}/pipeline/config.yaml", root=root, work_dir=OUT)
    m = cfg["models"]
    if rehearsal:                                         # modelo minusculo em CPU; sem digest de referencia nem raciocinio
        for key in ("detector", "verifier"):
            m[key].update({"tag": JOB["rehearsal_model"], "digest": None, "parallel": 1, "reasoning_effort": None,
                           "infer": {"context_length": 8192, "kv_cache_type": "f16", "flash_attention": 1}})
    srv = {"detector": kb.Server(11434, None if rehearsal else 0), "verifier": kb.Server(11435, None if rehearsal else 1)}
    for key, s in srv.items():
        s.start(int(m[key]["parallel"]), m[key]["infer"]["kv_cache_type"], int(m[key]["infer"]["context_length"]))
    report["models"] = {key: kb.pull_and_check(srv[key], m[key]) for key in srv}
    items = load_items(cfg["paths"]["raw_root"], cfg["paths"]["data_dir"] / "files.jsonl", JOB["select"])
    kb.log(f"{len(items)} arquivos selecionados:", [i.id for i in items])

    # ---- 1. ajuste do detector: cache KV quantizado + paralelismo
    if JOB["tune_detector"]:
        cands = [("q8_0", 2)] if rehearsal else [("q8_0", 2), ("q8_0", 3)]
        tune = stage("tune_detector", lambda: kb.tune_detector(cfg, srv["detector"], items[: (2 if rehearsal else 10)], cands, cpu=rehearsal))
        if tune:
            m["detector"]["parallel"] = tune["chosen"]["num_parallel"]
            m["detector"]["infer"]["kv_cache_type"] = tune["chosen"]["kv_cache_type"]
            report["detector_final"] = tune["chosen"]
    # sobe (de novo) os dois servidores com a configuracao final e carrega os modelos
    for key, s in srv.items():
        s.start(int(m[key]["parallel"]), m[key]["infer"]["kv_cache_type"], int(m[key]["infer"]["context_length"]))
        report.setdefault("warm_seconds", {})[key] = kb.warm(s.port, m[key]["tag"], m[key].get("reasoning_effort"))
        report.setdefault("fits_on_gpu", {})[key] = (True, {}) if rehearsal else kb.fits(s.port, m[key]["tag"])
    kb.log("modelos carregados; iniciando o pipeline")
    guard = QuotaGuard(JOB["session_hours"])
    ctx = build_ctx(cfg, dry_run=False)
    configs = JOB["configs"] if JOB["configs"] else (["B0", "B1", "C1", "C2", "C3", "C3mf"] if rehearsal else ["B0", "B1", "C1", "C2", "C3"])

    # ---- 2. pipeline
    pipe = stage("pipeline", lambda: run(cfg, ctx, items, JOB["reps"], configs=configs, workers=JOB["workers"], guard=guard, log=kb.log)) if JOB["pipeline"] else None

    # ---- 3. determinismo: repete o mesmo trabalho com cache novo e compara
    if JOB["determinism"] and pipe:
        def det():
            cfg2 = copy.deepcopy(cfg)
            cfg2["paths"]["cache_dir"], cfg2["paths"]["runs_dir"] = Path(f"{OUT}/cache_det"), Path(f"{OUT}/runs_det")
            ctx2 = build_ctx(cfg2, dry_run=False)
            s2 = run(cfg2, ctx2, items, JOB["reps"], configs=configs, workers=JOB["workers"], guard=guard, log=kb.log)
            return {"second_run": s2["llm"], "calls": f4_jobs.compare_caches(cfg["paths"]["cache_dir"], cfg2["paths"]["cache_dir"]),
                    "accepted_sets": f4_jobs.compare_runs(cfg["paths"]["runs_dir"], cfg2["paths"]["runs_dir"], configs, JOB["reps"][0])}
        stage("determinism", det)

    f4_dir, raw = Path(f"{OUT}/f4"), cfg["paths"]["raw_root"]
    # ---- 4. A3b nos patches do GPT-4.1 do artigo (56 issues)
    if JOB["fix_validation"]:
        def fixval():
            cases = f4_jobs.load_fix_cases(cfg["paths"]["data_dir"] / "f4_fix_cases.jsonl")
            if JOB["limit_cases"]:
                cases = cases[: JOB["limit_cases"]]
            return f4_jobs.run_fix_validation(ctx, cases, raw, f4_dir, workers=int(m["verifier"]["parallel"]), log=kb.log)
        stage("fix_validation", fixval)

    # ---- 4b. calibracao do A3a (sensibilidade/especificidade do verificador, sem o detector)
    if JOB["verifier_calibration"]:
        def calib():
            cases = f4_jobs.load_fix_cases(cfg["paths"]["data_dir"] / "f4_verifier_cases.jsonl")
            if JOB["limit_cases"]:
                cases = cases[: JOB["limit_cases"]]
            return f4_jobs.run_verifier_calibration(ctx, cases, raw, f4_dir, workers=int(m["verifier"]["parallel"]), log=kb.log)
        stage("verifier_calibration", calib)

    # ---- 5. extracao estruturada das respostas do artigo (114 arquivos x 3 modelos)
    if JOB["paper_extraction"]:
        def extract():
            files = [json.loads(line) for line in open(cfg["paths"]["data_dir"] / "files.jsonl", encoding="utf-8")]
            keep = {"all": ("positive", "negative"), "positive": ("positive",), "negative": ("negative",)}[JOB["extraction_scope"]]
            files = [r for r in files if r["class"] in keep]
            if JOB["limit_extraction_files"]:
                files = files[: JOB["limit_extraction_files"]]
            return f4_jobs.run_paper_extraction(ctx, files, raw, f4_dir, workers=max(1, int(m["detector"]["parallel"])), log=kb.log,
                                                models=(["gpt-4.1"] if rehearsal else list(MODELS)))
        stage("paper_extraction", extract)

    report["session_hours"] = round(guard.elapsed_hours(), 3)
    report["t_total_s"] = round(time.time() - t0, 1)
    with open(f"{OUT}/run_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    kb.log("pronto:", json.dumps({k: v["ok"] for k, v in report["stages"].items()}))
    for s in srv.values():
        s.stop()
    if JOB["archive"]:
        import shutil
        import tarfile
        arc, n_files = f"{OUT}/taes_outputs.tar.gz", 0
        with tarfile.open(arc, "w:gz") as tf:
            for d in ("runs", "cache", "f4"):
                if os.path.isdir(f"{OUT}/{d}"):
                    n_files += sum(len(fs) for _, _, fs in os.walk(f"{OUT}/{d}"))
                    tf.add(f"{OUT}/{d}", arcname=d)
        with tarfile.open(arc) as tf:
            n_members = sum(1 for m in tf.getmembers() if m.isfile())
        kb.log(f"arquivo {arc}: {n_members} arquivos (esperado {n_files}), {os.path.getsize(arc) / 1e6:.1f} MB")
        if n_members == n_files:                     # so apaga os originais se o pacote confere
            for d in ("runs", "cache", "f4"):
                shutil.rmtree(f"{OUT}/{d}", ignore_errors=True)
    return 0


if __name__ == "__main__":
    try:
        main()
    except BaseException:  # noqa: BLE001 - grava o erro no output para o agente ler (kernels output)
        tb = traceback.format_exc()
        print(tb)
        open(f"{OUT}/run_error.txt", "w").write(tb)
    sys.exit(0)
