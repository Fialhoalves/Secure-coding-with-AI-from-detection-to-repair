"""Gera kaggle/<nome>/run.py (+ kernel-metadata.json) a partir de kaggle/run/run.py com um JOB diferente.

Uso:  pipeline\.venv\Scripts\python.exe -I kaggle\make_job.py <job>      (jobs: chaves de JOBS abaixo)
O dono dos kernels e do Dataset vem da variavel de ambiente KAGGLE_USERNAME (o seu usuario do Kaggle).
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
JOBS = {
    # ensaio em CPU: modelo minusculo, 2 arquivos; valida cliente real, schemas, ferramentas, cache, ajuste, determinismo, validacao e extracao
    "rehearsal": {"slug": "taes-rehearsal", "gpu": False,
                  "job": {"mode": "rehearsal", "select": "first:2", "session_hours": 2.0, "limit_cases": 3, "limit_extraction_files": 2, "workers": 2}},
    # piloto da F4: 10 arquivos, 2x T4, todas as etapas
    "pilot": {"slug": "taes-pilot", "gpu": True, "job": {"mode": "pilot", "select": "pilot", "session_hours": 10.0, "extraction_scope": "positive"}},
    # ajuste de prompt (F4, ciclo de 10-20 min): so o pipeline do A1 em diante, nos 10 arquivos do piloto; sem B0, determinismo, validacao e extracao
    "tune1": {"slug": "taes-tune1", "gpu": True,
              "job": {"mode": "pilot", "select": "pilot", "session_hours": 3.0, "configs": ["B1", "C1", "C3"], "tune_detector": False,
                      "determinism": False, "fix_validation": False, "paper_extraction": False}},
    # calibracao do verificador: A3a sobre 56 issues reais + 85 falsos alarmes (achados do scanner); so o servidor do verificador trabalha
    "verif": {"slug": "taes-verif", "gpu": True,
              "job": {"mode": "pilot", "select": "first:1", "session_hours": 2.0, "tune_detector": False, "pipeline": False, "determinism": False,
                      "fix_validation": False, "paper_extraction": False, "verifier_calibration": True}},
    # F5 - execucao completa. Principal em 2 metades (cada uma < 12 h de sessao); B0,B1,C1,C2,C3; temperatura 0, seed 0
    "f5a": {"slug": "taes-f5a", "gpu": True,
            "job": {"mode": "pilot", "select": "part:0/2", "session_hours": 10.0, "tune_detector": False, "determinism": False,
                    "fix_validation": False, "paper_extraction": False, "archive": True}},
    "f5b": {"slug": "taes-f5b", "gpu": True,
            "job": {"mode": "pilot", "select": "part:1/2", "session_hours": 10.0, "tune_detector": False, "determinism": False,
                    "fix_validation": False, "paper_extraction": False, "archive": True}},
    # F5 - estudo de variancia: B1 e C3, 3 repeticoes com amostragem (seeds 1-3, temperatura do cartao), 114 arquivos
    "f5var": {"slug": "taes-f5var", "gpu": True,
              "job": {"mode": "pilot", "select": "all", "reps": ["var1", "var2", "var3"], "configs": ["B1", "C3"], "session_hours": 10.0, "tune_detector": False,
                      "determinism": False, "fix_validation": False, "paper_extraction": False, "archive": True}},
    # F5 - ablacao H5 (C3-mf): verificador e A3b do MESMO modelo do detector (qwen), em 2 metades como o f5a/f5b. O cache semeado traz o A1 e os
    # patches do A2 da execucao principal, de modo que o C3-mf julga exatamente os mesmos achados do C3. So o servidor do qwen trabalha.
    "f5mfa": {"slug": "taes-f5mfa", "gpu": True,
              "job": {"mode": "pilot", "select": "part:0/2", "reps": ["main"], "configs": ["C3mf"], "session_hours": 10.0, "tune_detector": False,
                      "determinism": False, "fix_validation": False, "paper_extraction": False, "seed_cache": True, "archive": True}},
    "f5mfb": {"slug": "taes-f5mfb", "gpu": True,
              "job": {"mode": "pilot", "select": "part:1/2", "reps": ["main"], "configs": ["C3mf"], "session_hours": 10.0, "tune_detector": False,
                      "determinism": False, "fix_validation": False, "paper_extraction": False, "seed_cache": True, "archive": True}},
    # F5 - A3b (o mesmo do C3) nos patches do B0 da execucao principal: 373 achados do B0 com patch; so o servidor do verificador trabalha
    "f5b0fix": {"slug": "taes-f5b0fix", "gpu": True,
                "job": {"mode": "pilot", "select": "all", "session_hours": 4.0, "tune_detector": False, "pipeline": False, "determinism": False,
                        "fix_validation": False, "paper_extraction": False, "b0_fix_validation": True, "archive": True}},
    # F5 - extracao das respostas do artigo nos 66 negativos (base da E1)
    "f5neg": {"slug": "taes-f5neg", "gpu": True,
              "job": {"mode": "pilot", "select": "first:1", "session_hours": 4.0, "tune_detector": False, "pipeline": False, "determinism": False,
                      "fix_validation": False, "paper_extraction": True, "extraction_scope": "negative", "archive": True}},
}


def kaggle_owner() -> str:
    owner = os.environ.get("KAGGLE_USERNAME", "").strip()
    if not owner:
        raise SystemExit("Defina KAGGLE_USERNAME com o seu usuario do Kaggle (ex.: set KAGGLE_USERNAME=meu_usuario).")
    return owner


def main(name: str) -> None:
    spec = JOBS[name]
    owner = kaggle_owner()          # antes de gravar qualquer arquivo
    src = (ROOT / "run" / "run.py").read_text(encoding="utf-8")
    m = re.search(r"JOB = \{.*?\n\}\n", src, flags=re.S)
    base = eval(m.group(0).split("=", 1)[1].strip())          # o dict literal do template
    base.update(spec["job"])
    new = src[:m.start()] + "JOB = " + json.dumps(base, indent=4).replace("true", "True").replace("false", "False").replace("null", "None") + "\n" + src[m.end():]
    out = ROOT / name
    out.mkdir(exist_ok=True)
    (out / "run.py").write_text(new, encoding="utf-8")
    meta = json.loads((ROOT / "run" / "kernel-metadata.json").read_text(encoding="utf-8"))
    meta.update({"id": f"{owner}/{spec['slug']}", "title": spec["slug"], "enable_gpu": spec["gpu"],
                 "dataset_sources": [f"{owner}/taes-pipeline"]})
    (out / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"kaggle/{name}/ gerado: JOB = {base}")


if __name__ == "__main__":
    main(sys.argv[1])
