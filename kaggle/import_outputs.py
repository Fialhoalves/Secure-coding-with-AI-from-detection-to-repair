"""Traz para o projeto as saidas de um kernel do Kaggle (o taes_outputs.tar.gz baixado com `kaggle kernels output`).

Mapeamento (nada e sobrescrito; arquivo igual ja existente conta como "igual", diferente conta como "conflito"):
  runs/<config>/<rep>/<arquivo>.json  -> pipeline/runs/<config>/<rep>/
  cache/<ab>/<chave>.json             -> pipeline/cache/<ab>/
  f4/paper_extract/<modelo>/...       -> pipeline/results/paper_extract/<modelo>/   (E1)
  f4/b0_fix_validation/...            -> pipeline/results/b0_fix_validation/        (A3b nos patches do B0)
  runs/gpu_sessions.jsonl             -> linhas novas acrescentadas a pipeline/runs/gpu_sessions.jsonl
Outros caminhos (por exemplo, as saidas do piloto em f4/) sao listados e ignorados: o piloto e analisado direto da pasta baixada
com `pipeline/src/f4_analyze.py --out <pasta>`.
Com --job, o tar.gz e o run_report.json (se estiver na mesma pasta) sao copiados para pipeline/results/f5/ com o nome do job.

Uso (da raiz do projeto):
  pipeline\\.venv\\Scripts\\python.exe -I kaggle\\import_outputs.py <pasta_ou_tar.gz> --job f5a [--dry-run]
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
PIPE = ROOT / "pipeline"
RULES = (
    (("runs",), PIPE / "runs"),
    (("cache",), PIPE / "cache"),
    (("f4", "paper_extract"), PIPE / "results" / "paper_extract"),
    (("f4", "b0_fix_validation"), PIPE / "results" / "b0_fix_validation"),
)


def destination(name: str) -> Path | None:
    parts = PurePosixPath(name).parts
    if not parts or name.startswith("/") or ".." in parts:
        raise SystemExit(f"caminho suspeito no arquivo: {name!r}")
    for prefix, dest in RULES:
        if parts[: len(prefix)] == prefix and len(parts) > len(prefix):
            return dest.joinpath(*parts[len(prefix):])
    return None


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="o taes_outputs.tar.gz, ou a pasta onde ele foi baixado")
    ap.add_argument("--job", default=None, help="nome do job (ex.: f5a); copia tar.gz e run_report.json para results/f5/")
    ap.add_argument("--dry-run", action="store_true", help="so conta, nao grava nada")
    a = ap.parse_args()
    src = Path(a.src)
    tar_path = src / "taes_outputs.tar.gz" if src.is_dir() else src
    if not tar_path.is_file():
        raise SystemExit(f"nao achei {tar_path}")

    count = {"novos": 0, "iguais": 0, "conflitos": 0, "ignorados": 0, "sessoes_gpu_novas": 0}
    conflicts, ignored = [], set()
    sessions_file = PIPE / "runs" / "gpu_sessions.jsonl"
    with tarfile.open(tar_path, "r:gz") as tf:
        for m in tf:
            if not m.isfile():
                continue
            if m.name == "runs/gpu_sessions.jsonl":
                have = set(sessions_file.read_text(encoding="utf-8").splitlines()) if sessions_file.exists() else set()
                new = [ln for ln in tf.extractfile(m).read().decode("utf-8").splitlines() if ln.strip() and ln not in have]
                count["sessoes_gpu_novas"] += len(new)
                if new and not a.dry_run:
                    with open(sessions_file, "a", encoding="utf-8", newline="\n") as f:
                        f.writelines(ln + "\n" for ln in new)
                continue
            dest = destination(m.name)
            if dest is None:
                count["ignorados"] += 1
                ignored.add("/".join(PurePosixPath(m.name).parts[:2]))
                continue
            data = tf.extractfile(m).read()
            if dest.exists():
                if dest.read_bytes() == data:
                    count["iguais"] += 1
                else:
                    count["conflitos"] += 1
                    conflicts.append(str(dest.relative_to(ROOT)))
                continue
            count["novos"] += 1
            if not a.dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)

    if a.job:
        f5 = PIPE / "results" / "f5"
        copies = [(tar_path, f5 / f"taes_outputs_{a.job}.tar.gz"), (tar_path.parent / "run_report.json", f5 / f"run_report_{a.job}.json")]
        for s, d in copies:
            if not s.exists():
                continue
            if d.exists():
                print(f"ja existe, nao copiei: {d.relative_to(ROOT)}")
            elif not a.dry_run:
                f5.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(s, d)
                print(f"copiado: {d.relative_to(ROOT)}")

    print(("[simulacao] " if a.dry_run else "") + ", ".join(f"{k}: {v}" for k, v in count.items()))
    if ignored:
        print("ignorados (prefixos):", ", ".join(sorted(ignored)))
    if conflicts:
        print("CONFLITOS (mantida a versao do projeto):")
        for c in conflicts[:20]:
            print("  ", c)
    return 1 if conflicts else 0


if __name__ == "__main__":
    sys.exit(main())
