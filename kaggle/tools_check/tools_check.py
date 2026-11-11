#!/usr/bin/env python3
"""Validacao (CPU, sem GPU e sem LLM) dos wrappers de ferramentas do pipeline contra as ferramentas REAIS no Kaggle.

Roda gcc/g++ -fsyntax-only, flawfinder, cppcheck e semgrep sobre os 114 arquivos e sobre o 1o patch do GPT-4.1 de cada arquivo
positivo, e mede: (a) quanto do codigo (fragmentos) compila, (b) se os parsers leem a saida real, (c) quantas deteccoes originais
(Info.txt dos autores) o re-scan local reproduz com a MESMA regra a +-3 linhas - isso define quanto o criterio 2 de correcao
("a regra do scanner original deixou de disparar") e verificavel. Escreve /kaggle/working/tools_check_report.json.
"""
import concurrent.futures as cf
import collections
import glob
import json
import os
import subprocess
import sys
import time

OUT = "/kaggle/working"
T0 = time.time()
TOOLS_VENV = "/tmp/tools_venv"


def log(*a):
    print(f"[{time.time() - T0:7.1f}s]", *a, flush=True)


def sh(cmd, timeout=900):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main():
    report = {"steps": {}}
    # ---- instalacao (igual ao infer.py)
    sh("apt-get update -qq", 300)
    sh("DEBIAN_FRONTEND=noninteractive apt-get install -y -qq cppcheck", 600)
    sh(f"{sys.executable} -m pip install -q virtualenv", 300)
    sh(f"{sys.executable} -m virtualenv -q {TOOLS_VENV}", 300)
    rc, out = sh(f"{TOOLS_VENV}/bin/pip install -q flawfinder semgrep", 900)
    os.environ["PATH"] = f"{TOOLS_VENV}/bin:" + os.environ["PATH"]
    log("ferramentas instaladas; rc pip =", rc)
    # ---- semgrep: descobre qual pacote de regras reproduz as regras que os autores usaram (ex.: c.lang.security.insecure-use-scanf-fn)
    sample = "#include <stdio.h>\nint main(void) {\n    int n;\n    char name[16];\n    scanf(\"%d\", &n);\n    scanf(\"%s\", name);\n    return 0;\n}\n"
    os.makedirs("/tmp/sg", exist_ok=True)
    open("/tmp/sg/sample.c", "w").write(sample)
    diag = {}
    for cfgname in ("p/default", "p/c", "p/security-audit", "p/cpp", "p/ci"):
        rc, out = sh(f"cd /tmp/sg && semgrep --config {cfgname} --json --metrics=off --quiet --disable-version-check sample.c", 300)
        try:
            ids = sorted({r["check_id"] for r in json.loads(out[out.index("{"):]).get("results", [])})
        except Exception:  # noqa: BLE001
            ids = []
        diag[cfgname] = {"rc": rc, "rules": ids, "out_head": "" if ids else out[:300]}
    report["semgrep_diag"] = diag
    chosen = next((c for c, d in diag.items() if any("insecure-use-scanf-fn" in i for i in d["rules"])), "p/c")
    os.environ["TAES_SEMGREP_CONFIG"] = chosen
    report["semgrep_config_chosen"] = chosen
    log("semgrep diag:", {c: len(d["rules"]) for c, d in diag.items()}, "-> escolhido", chosen)

    # ---- codigo do pipeline (Dataset anexado)
    os.system("find /kaggle/input -maxdepth 4 | head -40")          # diagnostico: onde o Dataset foi montado
    # o Kaggle monta em /kaggle/input/datasets/<dono>/<slug>/ e ACHATA o zip (o conteudo de pipeline/ fica na raiz)
    ds = next((d for d in glob.glob("/kaggle/input/**/taes-pipeline", recursive=True) if os.path.isdir(f"{d}/src")), None)
    if ds is None:
        raise RuntimeError("Dataset taes-pipeline nao encontrado em /kaggle/input (veja a arvore acima)")
    root = "/tmp/proj"                                              # symlink: root/pipeline -> Dataset (caminhos do config.yaml valem)
    os.makedirs(root, exist_ok=True)
    if not os.path.exists(f"{root}/pipeline"):
        os.symlink(ds, f"{root}/pipeline")
    sys.path.insert(0, f"{root}/pipeline/src")
    from tools import ToolRunner  # noqa: E402
    import tools.scan as scan  # noqa: E402
    tr = ToolRunner(cache=None)
    report["versions"] = tr.versions
    log("versoes:", tr.versions)

    files = [json.loads(line) for line in open(f"{root}/pipeline/data/files.jsonl", encoding="utf-8")]
    files = [r for r in files if r["class"] in ("positive", "negative")]
    raw = f"{root}/pipeline/data/raw/MSc_DataEngineering_Results"

    def read(rel):
        return open(f"{raw}/{rel}", encoding="utf-8", errors="replace").read()

    def work(rec):
        code, lang = read(rec["code"]["path"]), rec["language"]
        t0 = time.time(); c = tr.compile(code, lang); t1 = time.time(); s = tr.scan(code, lang); t2 = time.time()
        row = {"file": f"{rec['snapshot']}:{rec['folder']}", "class": rec["class"], "lang": lang, "compile": c, "scan": s,
               "t_compile": round(t1 - t0, 2), "t_scan": round(t2 - t1, 2), "detections": rec["detections"]}
        if rec["class"] == "positive" and rec["models"]["gpt-4.1"]["new_code"]:
            pc = read(rec["models"]["gpt-4.1"]["new_code"][0])
            row["patch"] = {"compile": tr.compile(pc, lang), "scan": tr.scan(pc, lang), "chars": len(pc)}
        return row

    rows = []
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for i, r in enumerate(ex.map(work, files), 1):
            rows.append(r)
            if i % 20 == 0:
                log(f"{i}/{len(files)} arquivos")

    # ---- agregados
    comp = collections.Counter((r["lang"], r["compile"]["status"]) for r in rows)
    report["compile_original"] = {f"{k[0]}:{k[1]}": v for k, v in sorted(comp.items())}
    report["compile_error_examples"] = [{"file": r["file"], "errors": r["compile"].get("errors", [])[:2]} for r in rows if r["compile"]["status"] == "error"][:6]
    per = {}
    for name in ("flawfinder", "cppcheck", "semgrep"):
        ok = [r for r in rows if r["scan"].get("available", {}).get(name)]
        per[name] = {"files_run": len(ok), "files_with_findings": sum(1 for r in ok if any(f["scanner"] == name for f in r["scan"]["findings"])),
                     "findings": sum(1 for r in ok for f in r["scan"]["findings"] if f["scanner"] == name),
                     "errors": sum(1 for r in rows if name in r["scan"].get("errors", {})),
                     "avg_seconds_all_scanners": round(sum(r["t_scan"] for r in ok) / max(1, len(ok)), 2)}
    report["scan_per_tool"] = per
    # reproducao das deteccoes originais (Info.txt dos autores)
    repro = {}
    mismatch = collections.defaultdict(list)
    for name in ("flawfinder", "cppcheck", "semgrep"):
        n = same_rule = same_line_any = 0
        for r in rows:
            for d in r["detections"]:
                if d.get("scanner") != name:
                    continue
                n += 1
                near = [f for f in r["scan"]["findings"] if f["scanner"] == name and abs(f["line"] - int(d["line"])) <= 3]
                if any(f["rule"] == d["type"] for f in near):
                    same_rule += 1
                elif near:
                    same_line_any += 1
                    if len(mismatch[name]) < 6:
                        mismatch[name].append({"autor": d["type"], "local": sorted({f["rule"] for f in near})[:3]})
        repro[name] = {"deteccoes_dos_autores": n, "reproduzidas_mesma_regra": same_rule, "so_mesma_linha_outra_regra": same_line_any}
    report["reproducao_das_deteccoes_originais"] = repro
    report["exemplos_de_regras_diferentes"] = mismatch
    snyk = sum(1 for r in rows for d in r["detections"] if d.get("scanner") == "snyk")
    report["deteccoes_snyk_nao_reexecutaveis"] = snyk
    # patches do GPT-4.1 (previa da F4)
    pr = [r for r in rows if "patch" in r]
    report["patches_gpt41"] = {"n": len(pr),
                               "original_compila": sum(1 for r in pr if r["compile"]["status"] == "ok"),
                               "patch_compila": sum(1 for r in pr if r["patch"]["compile"]["status"] == "ok"),
                               "original_ok_e_patch_quebra": sum(1 for r in pr if r["compile"]["status"] == "ok" and r["patch"]["compile"]["status"] == "error"),
                               "csharp_nao_verificavel": sum(1 for r in pr if r["lang"] == "C#")}
    report["tempo_total_s"] = round(time.time() - T0, 1)
    slim = [{"file": r["file"], "class": r["class"], "lang": r["lang"], "compile": r["compile"]["status"], "findings": r["scan"]["findings"],
             "patch": ({"compile": r["patch"]["compile"]["status"], "findings": r["patch"]["scan"]["findings"]} if "patch" in r else None)} for r in rows]
    with open(f"{OUT}/scan_all.json", "w", encoding="utf-8") as f:
        json.dump(slim, f, ensure_ascii=False)
    with open(f"{OUT}/tools_check_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    # amostra bruta (pequena) para inspecionar os parsers
    sample = {r["file"]: {"compile": r["compile"], "findings": r["scan"]["findings"][:8], "errors": r["scan"].get("errors")} for r in rows[:6]}
    with open(f"{OUT}/tools_check_sample.json", "w", encoding="utf-8") as f:
        json.dump(sample, f, indent=1, ensure_ascii=False)
    log("pronto")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        with open(f"{OUT}/tools_check_error.txt", "w") as f:
            f.write(traceback.format_exc())
    sys.exit(0)
