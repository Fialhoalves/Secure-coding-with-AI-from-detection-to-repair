"""Carrega o config.yaml e monta o contexto (clientes, cache, prompts, ferramentas)."""
from __future__ import annotations

import tempfile
from pathlib import Path

import yaml

from agents import Ctx
from cache import DiskCache
from llm import FakeClient, ModelSpec, RealClient, StructuredCaller
from prompts import load_prompt
from tools import FakeTools, ToolRunner


def load_config(path: str | Path, root: str | Path | None = None, work_dir: str | Path | None = None) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    root = Path(root) if root else Path(path).resolve().parent.parent
    cfg["_root"] = root
    p = cfg["paths"]
    for k, v in list(p.items()):
        p[k] = Path(v) if Path(v).is_absolute() else root / v
    if work_dir:
        p["cache_dir"], p["runs_dir"] = Path(work_dir) / "cache", Path(work_dir) / "runs"
    return cfg


def spec_of(cfg: dict, key: str, base_url: str | None = None) -> ModelSpec:
    m = cfg["models"][key]
    return ModelSpec(key=key, tag=m["tag"], base_url=base_url or m["base_url"], digest=m.get("digest"),
                     quantization=m.get("quantization"), ollama_version=m.get("ollama_version"),
                     reasoning_effort=m.get("reasoning_effort"), parallel=int(m.get("parallel", 1)),
                     infer_cfg=dict(m.get("infer", {})))


def rep_params(cfg: dict, rep: str) -> dict:
    """seed e temperaturas (detector, verificador) de uma repeticao; 'model_card' usa a temperatura do cartao."""
    r = cfg["repetitions"][rep]

    def temp(key: str) -> float:
        t = r["temperature"]
        return float(cfg["models"][key]["temperature_variance"]) if t == "model_card" else float(t)

    return {"seed": int(r["seed"]), "temp_det": temp("detector"), "temp_ver": temp("verifier"),
            "configs": list(r["configs"])}


def build_ctx(cfg: dict, *, dry_run: bool = False, cache_dir: str | Path | None = None,
              det_url: str | None = None, ver_url: str | None = None) -> Ctx:
    """dry_run=True: clientes e ferramentas simulados (nenhuma chamada de rede, nenhum modelo, nenhum processo externo)."""
    cache = DiskCache(cache_dir or cfg["paths"]["cache_dir"])
    prompts = {k: load_prompt(cfg["paths"]["prompts_dir"], v) for k, v in cfg["prompts"].items()}
    det_spec, ver_spec = spec_of(cfg, "detector", det_url), spec_of(cfg, "verifier", ver_url)
    if dry_run:
        det, ver, tools = FakeClient(det_spec), FakeClient(ver_spec), FakeTools()
    else:
        det, ver, tools = RealClient(det_spec), RealClient(ver_spec), ToolRunner(cache)
    return Ctx(caller=StructuredCaller(cache), prompts=prompts, det=det, ver=ver, tools=tools)


def temp_cache_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="taes_cache_"))
