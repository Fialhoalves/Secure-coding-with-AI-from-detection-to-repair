"""Bootstrap do ambiente de inferencia no Kaggle (Ubuntu, root, 2x T4 ou CPU no ensaio): ferramentas do A3b, Ollama, dois servidores
(um por GPU), download dos modelos, conferencia dos digests e ajuste do detector. So roda no Kaggle."""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import subprocess
import sys
import time
import urllib.request

MODELS_DIR = "/tmp/ollama_models"
LOG_DIR = "/tmp/ollama_logs"
TOOLS_VENV = "/tmp/tools_venv"
T0 = time.time()


def log(*a) -> None:
    print(f"[{time.time() - T0:7.1f}s]", *a, flush=True)


def sh(cmd: str, timeout: int | None = None, env: dict | None = None) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, env=env)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"


def http_json(port: int, path: str, payload=None, timeout: int = 60):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=None if payload is None else json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def install_tools() -> dict:
    """gcc ja vem no ambiente; cppcheck por apt; flawfinder e semgrep num venv isolado (virtualenv: `python -m venv` falha no Kaggle).
    O semgrep usa o pacote p/default (reproduz as regras dos autores); as regras vem do registro a cada chamada."""
    sh("apt-get update -qq", 300)
    sh("DEBIAN_FRONTEND=noninteractive apt-get install -y -qq cppcheck zstd curl", 600)
    sh(f"{sys.executable} -m pip install -q virtualenv", 300)
    sh(f"{sys.executable} -m virtualenv -q {TOOLS_VENV}", 300)
    rc, _ = sh(f"{TOOLS_VENV}/bin/pip install -q flawfinder semgrep", 900)
    os.environ["PATH"] = f"{TOOLS_VENV}/bin:" + os.environ["PATH"]
    return {"pip_rc": rc}


def install_ollama() -> str:
    if sh("which ollama")[0] != 0:
        sh("curl -fsSL https://ollama.com/install.sh | sh", 900)
    rc, out = sh("ollama --version")
    if rc != 0:
        raise RuntimeError("ollama nao instalou")
    return out.strip()


class Server:
    def __init__(self, port: int, gpu: int | None):
        self.port, self.gpu, self.proc = port, gpu, None   # gpu=None: CPU (ensaio)

    def start(self, parallel: int, kv: str, context: int) -> None:
        self.stop()
        os.makedirs(MODELS_DIR, exist_ok=True)
        os.makedirs(LOG_DIR, exist_ok=True)
        env = dict(os.environ)
        env.update({"OLLAMA_HOST": f"127.0.0.1:{self.port}", "OLLAMA_NUM_PARALLEL": str(parallel), "OLLAMA_CONTEXT_LENGTH": str(context),
                    "OLLAMA_MODELS": MODELS_DIR, "OLLAMA_FLASH_ATTENTION": "1", "OLLAMA_KV_CACHE_TYPE": kv, "OLLAMA_KEEP_ALIVE": "24h",
                    "OLLAMA_MAX_LOADED_MODELS": "1"})
        env["CUDA_VISIBLE_DEVICES"] = "" if self.gpu is None else str(self.gpu)
        self.proc = subprocess.Popen(["ollama", "serve"], env=env, stdout=open(f"{LOG_DIR}/server_{self.port}.log", "ab"),
                                     stderr=subprocess.STDOUT)
        for _ in range(120):
            try:
                http_json(self.port, "/api/version", timeout=2)
                log(f"servidor :{self.port} ({'CPU' if self.gpu is None else 'GPU ' + str(self.gpu)}) no ar: NUM_PARALLEL={parallel} KV={kv} ctx={context}")
                return
            except Exception:  # noqa: BLE001
                time.sleep(1)
        raise RuntimeError(f"servidor :{self.port} nao subiu")

    def env(self) -> dict:
        e = dict(os.environ)
        e["OLLAMA_HOST"] = f"127.0.0.1:{self.port}"
        return e

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None


def pull_and_check(server: Server, spec: dict) -> dict:
    """Baixa o modelo e compara o digest com o do config.yaml (se houver). Se mudou, ABORTA: a tag passou a apontar para outros pesos."""
    rc, out = sh(f"ollama pull {spec['tag']}", 2700, env=server.env())
    if rc != 0:
        raise RuntimeError(f"pull {spec['tag']} falhou: {out[-300:]}")
    info = next(m for m in http_json(server.port, "/api/tags")["models"] if m["name"] == spec["tag"] or m.get("model") == spec["tag"])
    want = spec.get("digest")
    ok = want is None or info["digest"] == want
    log(f"{spec['tag']}: digest {info['digest'][:16]} " + ("(sem digest de referencia)" if want is None else ("= config" if ok else "!= CONFIG " + want[:16])))
    if not ok:
        raise RuntimeError(f"digest de {spec['tag']} mudou ({info['digest']}); salvar a pasta de modelos como Dataset e usar essa copia")
    return {"name": info["name"], "digest": info["digest"], "size": info.get("size"), "details": info.get("details")}


def warm(port: int, tag: str, effort: str | None) -> float:
    """Carrega o modelo antes de comecar (a 1a chamada demora minutos). Devolve os segundos gastos."""
    from openai import OpenAI
    kw = {"extra_body": {"reasoning_effort": effort}} if effort else {}
    t0 = time.time()
    OpenAI(base_url=f"http://127.0.0.1:{port}/v1", api_key="ollama", timeout=1800, max_retries=0).chat.completions.create(
        model=tag, messages=[{"role": "user", "content": "Say OK."}], max_tokens=8, temperature=0, **kw)
    return round(time.time() - t0, 1)


def fits(port: int, tag: str) -> tuple[bool, dict]:
    """O modelo carregado cabe 100% na GPU? (size_vram == size em /api/ps). Na CPU (ensaio) devolve True."""
    for m in http_json(port, "/api/ps").get("models", []):
        if m.get("name") == tag or m.get("model") == tag:
            return (m["size"] > 0 and m.get("size_vram", 0) >= 0.99 * m["size"]), {"size": m["size"], "size_vram": m.get("size_vram", 0)}
    return False, {"error": "modelo nao aparece em /api/ps"}


def tune_detector(cfg: dict, server: Server, items: list, candidates: list[tuple[str, int]], *, cpu: bool = False,
                  min_speedup: float = 1.3, min_agreement: float = 0.75) -> dict:
    """Mede o A1 nos arquivos do piloto com cada configuracao do detector (cache KV, NUM_PARALLEL) e escolhe a mais rapida cuja saida
    concorda com a de referencia (f16, 1 em paralelo): vazao >= 1,3x e concordancia (Jaccard dos achados cwe+linhas) >= 0,75.
    Se nenhuma serve, mantem a referencia. O A1 usa temperatura 0 e seed 0; diferencas so podem vir da numerica do cache KV."""
    import tempfile
    from agents import Ctx
    from agents.detector import run_a1
    from cache import DiskCache
    from config import spec_of
    from llm import RealClient, StructuredCaller
    from prompts import load_prompt

    m = cfg["models"]["detector"]
    ctxlen = int(m["infer"]["context_length"])
    prompts = {"a1": load_prompt(cfg["paths"]["prompts_dir"], cfg["prompts"]["a1"])}
    results, base_keys = [], None
    for kv, par in [("f16", 1)] + list(candidates):
        r: dict = {"kv_cache_type": kv, "num_parallel": par}
        try:
            server.start(par, kv, ctxlen)
            r["load_seconds"] = warm(server.port, m["tag"], None)
            r["fits_on_gpu"], r["ps"] = (True, {}) if cpu else fits(server.port, m["tag"])
            if not r["fits_on_gpu"]:
                results.append(r)
                continue
            spec = spec_of(cfg, "detector")
            spec.parallel, spec.infer_cfg = par, {**m["infer"], "kv_cache_type": kv}
            cl = RealClient(spec)
            ctx = Ctx(caller=StructuredCaller(DiskCache(tempfile.mkdtemp(prefix="tune_"))), prompts=prompts, det=cl, ver=cl, tools=None)
            t0 = time.time()
            with cf.ThreadPoolExecutor(max_workers=par) as ex:
                recs = list(ex.map(lambda it: (it.id, run_a1(ctx, it)), items))
            wall = time.time() - t0
            toks = sum(rec["completion_tokens"] for _, rec in recs)
            keys = {(fid, f["cwe"], tuple(f["lines"])) for fid, rec in recs if rec["ok"] for f in rec["parsed"]["findings"]}
            r.update({"files": len(items), "wall_s": round(wall, 1), "completion_tokens": toks, "agg_tok_per_s": round(toks / wall, 1) if wall else None,
                      "a1_ok": sum(1 for _, rec in recs if rec["ok"]), "n_findings": len(keys)})
            if base_keys is None:
                base_keys = keys
            union = keys | base_keys
            r["agreement_with_reference"] = round(len(keys & base_keys) / len(union), 3) if union else 1.0
        except Exception as e:  # noqa: BLE001
            r["error"] = repr(e)[:300]
        log("tuning:", {k: v for k, v in r.items() if k != "ps"})
        results.append(r)
    ref = results[0]
    good = [r for r in results[1:] if r.get("a1_ok") == r.get("files") and r.get("agg_tok_per_s") and ref.get("agg_tok_per_s")
            and r["agg_tok_per_s"] >= min_speedup * ref["agg_tok_per_s"] and r["agreement_with_reference"] >= min_agreement]
    chosen = max(good, key=lambda r: r["agg_tok_per_s"]) if good else ref
    return {"results": results, "chosen": {"kv_cache_type": chosen["kv_cache_type"], "num_parallel": chosen["num_parallel"]},
            "rule": f"vazao >= {min_speedup}x e concordancia >= {min_agreement} com f16/1; senao f16/1"}
