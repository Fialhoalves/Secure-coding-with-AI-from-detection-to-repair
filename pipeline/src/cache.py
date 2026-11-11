"""Cache em disco por SHA-256. Rodar de novo nunca repete trabalho ja feito; a execucao pode ser retomada
(o Kaggle derruba sessoes em ate 12 horas)."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
from pathlib import Path


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def make_key(**parts) -> str:
    """SHA-256 da forma canonica de (config, etapa, modelo e digest, versao do prompt, entrada, temperatura, seed...)."""
    return hashlib.sha256(canonical_json(parts).encode("utf-8")).hexdigest()


def seed_cache(src: str | Path, dst: str | Path) -> int:
    """Copia entradas de cache (<ab>/<chave>.json) de `src` para `dst` sem sobrescrever nenhuma existente; devolve quantas copiou.
    Usado no Kaggle para o C3-mf reaproveitar os achados do A1 (e os patches do A2) da execucao principal: mesma chave = mesmo achado."""
    src, dst, n = Path(src), Path(dst), 0
    for p in src.glob("*/*.json"):
        q = dst / p.parent.name / p.name
        if not q.exists():
            q.parent.mkdir(parents=True, exist_ok=True)
            q.write_bytes(p.read_bytes())
            n += 1
    return n


class DiskCache:
    """cache/<ab>/<chave>.json. Escrita atomica (arquivo temporario + rename); segura entre threads."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def _path(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.json"

    def get(self, key: str) -> dict | None:
        p = self._path(key)
        rec = None
        for attempt in range(5):               # no Windows, ler enquanto outra thread substitui o arquivo da erro de permissao
            try:
                with open(p, encoding="utf-8") as f:
                    rec = json.load(f)
                break
            except (FileNotFoundError, json.JSONDecodeError):
                break
            except PermissionError:
                time.sleep(0.02 * (attempt + 1))
        if rec is None:
            with self._lock:
                self.misses += 1
            return None
        with self._lock:
            self.hits += 1
        return rec

    def put(self, key: str, record: dict) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=p.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False)
            for attempt in range(8):           # idem: substituir um arquivo que outra thread esta lendo (Windows)
                try:
                    os.replace(tmp, p)
                    break
                except PermissionError:
                    if attempt == 7:
                        raise
                    time.sleep(0.02 * (attempt + 1))
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink()
        except FileNotFoundError:
            pass

    def __len__(self) -> int:
        return sum(1 for _ in self.root.glob("*/*.json"))
