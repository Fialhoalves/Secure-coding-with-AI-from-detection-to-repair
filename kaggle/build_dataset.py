"""Monta kaggle/dataset_build/ = o Dataset privado '<KAGGLE_USERNAME>/taes-pipeline' (codigo do pipeline + dados minimos).

Entra: pipeline/src, prompts, config.yaml, matching_families.yaml, files.jsonl e, do repositorio
dos autores SO o codigo enviado aos LLMs (Code_*), os patches do GPT-4.1 (New_generated_code_*) e as 3 respostas (LLM_Response.md), usados na F4.
NAO entra: o clone inteiro (71 MB), o XML do CWE (16 MB; as metricas rodam na maquina local), testes, venv, certificados.

Uso (da raiz do projeto):  pipeline\\.venv\\Scripts\\python.exe -I kaggle\\build_dataset.py
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPE = ROOT / "pipeline"
OUT = ROOT / "kaggle" / "dataset_build"
RAW = PIPE / "data" / "raw" / "MSc_DataEngineering_Results"
LONG = chr(92) * 2 + "?" + chr(92)


def lp(p: Path) -> str:
    s = str(p.resolve())
    return s if not s.startswith("C:") and not s[1:3] == ":" else LONG + s


def copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(lp(src), lp(dst))


def seed_main_cache() -> int:
    """Entradas de cache da execucao principal que o C3-mf reaproveita (H5): o A1 de cada arquivo (runs/B1/main) e os patches do A2
    (runs/C3/main). Com a mesma chave, o C3-mf julga exatamente os mesmos achados do C3. Vai em pipeline/cache_seed/ (~0,5 MB)."""
    runs, cache, n = PIPE / "runs", PIPE / "cache", 0
    keys: set[str] = set()
    for p in (runs / "B1" / "main").glob("*.json"):
        keys.add(json.loads(p.read_text(encoding="utf-8"))["steps"]["a1"]["cache_key"])
    for p in (runs / "C3" / "main").glob("*.json"):
        for row in json.loads(p.read_text(encoding="utf-8"))["findings"]:
            if row.get("a2") and row["a2"].get("cache_key"):
                keys.add(row["a2"]["cache_key"])
    for k in sorted(keys):
        src = cache / k[:2] / f"{k}.json"
        if not src.exists():
            raise SystemExit(f"entrada de cache ausente: {k}")
        copy(src, OUT / "pipeline" / "cache_seed" / k[:2] / f"{k}.json"); n += 1
    return n


def main() -> int:
    owner = os.environ.get("KAGGLE_USERNAME", "").strip()
    if not owner:
        raise SystemExit("Defina KAGGLE_USERNAME com o seu usuario do Kaggle (ex.: set KAGGLE_USERNAME=meu_usuario).")
    for attempt in range(6):          # o antivirus pode segurar arquivos recem-gravados por alguns segundos
        if not OUT.exists():
            break
        try:
            shutil.rmtree(OUT)
        except PermissionError:
            time.sleep(2 + attempt)
    if OUT.exists():
        print("AVISO: nao consegui apagar dataset_build/; sobrescrevendo os arquivos por cima")
    n = 0
    for p in (PIPE / "src").rglob("*.py"):
        if "__pycache__" not in p.parts:
            copy(p, OUT / "pipeline" / "src" / p.relative_to(PIPE / "src")); n += 1
    for p in (PIPE / "prompts").glob("*.md"):
        copy(p, OUT / "pipeline" / "prompts" / p.name); n += 1
    for name in ("config.yaml", "matching_families.yaml"):
        copy(PIPE / name, OUT / "pipeline" / name); n += 1
    # o gabarito (gt_*.csv, paper_labels.csv) fica de fora: o runner nao precisa dele; as metricas rodam na maquina local
    copy(PIPE / "data" / "files.jsonl", OUT / "pipeline" / "data" / "files.jsonl"); n += 1
    copy(PIPE / "data" / "f4_fix_cases.jsonl", OUT / "pipeline" / "data" / "f4_fix_cases.jsonl"); n += 1   # 56 achados + patches (sem rotulos de correcao)
    copy(PIPE / "data" / "f4_verifier_cases.jsonl", OUT / "pipeline" / "data" / "f4_verifier_cases.jsonl"); n += 1   # 141 achados do scanner (sem rotulo real/falso alarme)
    with open(PIPE / "data" / "files.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            # codigo enviado, patches do GPT-4.1 e as 3 respostas do artigo (extracao estruturada da F4)
            rels = [r["code"]["path"], *r["models"]["gpt-4.1"]["new_code"], *(r["models"][m]["response"] for m in r["models"])]
            for rel in rels:
                copy(RAW / rel, OUT / "pipeline" / "data" / "raw" / "MSc_DataEngineering_Results" / rel); n += 1
    n += seed_main_cache()
    for p in (PIPE / "runs" / "B0" / "main").glob("*.json"):          # B0 da execucao principal: patch e achados, para o A3b nos patches do B0
        copy(p, OUT / "pipeline" / "b0_seed" / p.name); n += 1
    meta = {"title": "taes-pipeline", "id": f"{owner}/taes-pipeline", "licenses": [{"name": "CC0-1.0"}]}
    (OUT / "dataset-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"{n} arquivos, {size / 1e6:.2f} MB em {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
