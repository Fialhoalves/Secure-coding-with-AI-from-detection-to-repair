"""Cliente LLM unico (API compativel com a OpenAI, apontando para o Ollama no Kaggle), cliente simulado para o
dry-run e o chamador estruturado (cache, validacao Pydantic, repeticoes, registro completo de cada chamada)."""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError

from cache import DiskCache, make_key
from prompts import Prompt
from schemas import json_schema_of

MAX_SCHEMA_RETRIES = 2          # plano: "repita ate 2 vezes e registre a falha"
MAX_TOKENS_CAP = 16000
REFUSAL = re.compile(r"\b(i can'?t (help|assist)|i cannot (help|assist)|i can not|i'?m sorry|i am sorry|unable to (assist|help|comply)|"
                     r"cannot comply|against my (guidelines|policy))\b", re.I)


@dataclass
class ModelSpec:
    key: str                         # 'detector' | 'verifier'
    tag: str                         # ex.: 'qwen2.5-coder:14b'
    base_url: str = "http://127.0.0.1:11434/v1"
    digest: str | None = None        # 'ollama list' / /api/tags: a tag pode passar a apontar para outros pesos
    quantization: str | None = None
    ollama_version: str | None = None
    reasoning_effort: str | None = None   # gpt-oss: fixado em 'medium'
    parallel: int = 1                # requisicoes simultaneas permitidas neste servidor
    infer_cfg: dict = field(default_factory=dict)   # contexto, tipo de cache KV etc. (entra na chave de cache)


@dataclass
class RawResponse:
    content: str
    prompt_tokens: int
    completion_tokens: int
    seconds: float
    finish_reason: str


# --------------------------------------------------------------------------- clientes
class RealClient:
    """Fala com um servidor Ollama pela API compativel com a OpenAI (pacote `openai`)."""

    is_fake = False

    def __init__(self, spec: ModelSpec, api_key: str = "ollama", timeout: float = 1800.0):
        from openai import OpenAI
        self.spec = spec
        self._client = OpenAI(base_url=spec.base_url, api_key=api_key, timeout=timeout, max_retries=0)
        self._sem = threading.Semaphore(max(1, spec.parallel))

    def chat(self, step: str, messages: list[dict], schema: dict | None, temperature: float, seed: int,
             max_tokens: int) -> RawResponse:
        kw: dict = dict(model=self.spec.tag, messages=messages, temperature=temperature, seed=seed, max_tokens=max_tokens)
        if schema is not None:
            kw["response_format"] = {"type": "json_schema",
                                     "json_schema": {"name": step, "schema": schema, "strict": True}}
        if self.spec.reasoning_effort:
            kw["extra_body"] = {"reasoning_effort": self.spec.reasoning_effort}
        last: Exception | None = None
        for attempt in range(4):                     # erros de rede (reset de conexao etc.), nao de schema
            try:
                with self._sem:
                    t0 = time.time()
                    r = self._client.chat.completions.create(**kw)
                    dt = time.time() - t0
                u = r.usage
                return RawResponse(content=r.choices[0].message.content or "",
                                   prompt_tokens=int(getattr(u, "prompt_tokens", 0) or 0),
                                   completion_tokens=int(getattr(u, "completion_tokens", 0) or 0),
                                   seconds=dt, finish_reason=r.choices[0].finish_reason or "")
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(2 ** attempt)
        raise RuntimeError(f"falha de rede/servidor apos 4 tentativas: {last!r}")


class FakeClient:
    """Cliente simulado e deterministico (dry-run e testes): nenhuma chamada de rede, nenhum modelo."""

    is_fake = True
    TOKEN_CWE = {"strcpy": "CWE-120", "strcat": "CWE-120", "gets": "CWE-242", "sprintf": "CWE-120", "memcpy": "CWE-120",
                 "scanf": "CWE-20", "system": "CWE-78", "fopen": "CWE-22", "open": "CWE-362", "malloc": "CWE-401",
                 "strlen": "CWE-126", "printf": "CWE-134"}

    def __init__(self, spec: ModelSpec):
        self.spec = spec
        self.calls = 0
        self._lock = threading.Lock()

    # -- utilidades
    @staticmethod
    def _h(*parts) -> int:
        return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)

    @staticmethod
    def _code_of(text: str) -> str:
        m = re.search(r"<code>\n(.*?)\n</code>", text, re.S)
        if m:
            return "\n".join(re.sub(r"^\s*\d+\| ?", "", ln) for ln in m.group(1).splitlines())
        m = re.search(r"```\w*\n(.*?)\n```", text, re.S)
        return m.group(1) if m else ""

    def chat(self, step: str, messages: list[dict], schema: dict | None, temperature: float, seed: int,
             max_tokens: int) -> RawResponse:
        with self._lock:
            self.calls += 1
        user = messages[-1]["content"]
        h = self._h(step, user, seed)
        code = self._code_of(user)
        lines = code.splitlines()
        if step == "b0_response":
            hits = [(i + 1, t) for i, ln in enumerate(lines) for t in self.TOKEN_CWE if re.search(rf"\b{t}\s*\(", ln)]
            body = ["## Security analysis", ""]
            for n, (ln, t) in enumerate(hits[:4] or [(1, "printf")], 1):
                body += [f"### {n}. Problem with `{t}` (line {ln}) ({self.TOKEN_CWE[t]})", f"The call to {t} can be abused.", ""]
            fixed = "\n".join(lines) + "\n/* fixed */"
            out = "\n".join(body) + f"\n## Fixed code\n```c\n{fixed}\n```\n"
        elif step == "b0_extract":
            review = user.split("<review>", 1)[-1]
            found = []
            for m in re.finditer(r"###\s*\d+\.\s*(.*?)\(line (\d+)\)\s*\((CWE-\d+)\)", review):
                found.append({"cwe": m.group(3), "lines": [int(m.group(2))], "description": m.group(1).strip() or "issue"})
            out = json.dumps({"findings": found})
        elif step == "a1":
            fs = []
            for i, ln in enumerate(lines, 1):
                for t, cwe in self.TOKEN_CWE.items():
                    if re.search(rf"\b{t}\s*\(", ln) and (t != "printf" or h % 2 == 0):
                        fs.append({"id": f"F{len(fs) + 1}", "cwe": cwe, "lines": [i], "title": f"{t} misuse",
                                   "untrusted_source": "argv", "sink": t, "trigger": "long input",
                                   "assumptions": "caller passes unvalidated data",
                                   "confidence": round(0.4 + (self._h(h, i) % 60) / 100, 2)})
                        break
            out = json.dumps({"no_vulnerability": not fs, "findings": fs[:4]})
        elif step in ("a3a", "a3joint", "a3a_mf"):
            fid = re.search(r'"id":\s*"([^"]+)"', user)
            fid = fid.group(1) if fid else "F1"
            verdict = ["refuted", "uncertain", "confirmed", "confirmed"][h % 4]
            rec = {"finding_id": fid, "verdict": verdict, "refutation_attempt": "checked other lines, constants, reachability",
                   "evidence_lines": [1], "confidence": round(0.3 + (h % 70) / 100, 2)}
            if step == "a3joint":
                rec.update({"fix_verdict": ["valid", "partial", "invalid"][self._h(h, "fix") % 3], "trigger_blocked": h % 3 != 0,
                            "behavior_preserved": True, "unnecessary_changes": h % 5 == 0})
            out = json.dumps(rec)
        elif step == "a2":
            fid = re.search(r'"id":\s*"([^"]+)"', user)
            patched = code.replace("strcpy(", "strncpy(").replace("gets(", "fgets(") + "\n/* patched */"
            out = json.dumps({"finding_id": fid.group(1) if fid else "F1", "patched_code": patched, "change_summary": "bounded the copy",
                              "how_trigger_is_blocked": "length is checked", "behavior_changes": "none"})
        elif step in ("a3b", "a3b_mf"):
            fid = re.search(r'"id":\s*"([^"]+)"', user)
            out = json.dumps({"finding_id": fid.group(1) if fid else "F1",
                              "fix_verdict": ["valid", "partial", "invalid"][h % 3], "trigger_blocked": h % 3 != 2,
                              "behavior_preserved": True, "new_issues": [], "unnecessary_changes": False, "notes": "fake"})
        else:
            raise ValueError(f"FakeClient: etapa desconhecida {step}")
        return RawResponse(content=out, prompt_tokens=max(1, len(user) // 4), completion_tokens=max(1, len(out) // 4),
                           seconds=0.0, finish_reason="stop")


# --------------------------------------------------------------------------- chamador estruturado
def extract_json(text: str) -> str:
    """Tolera cerca de markdown e texto em volta do JSON (modelos que ignoram o formato)."""
    t = text.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", t, re.S)
    if m:
        t = m.group(1)
    if not t.startswith("{"):
        i, j = t.find("{"), t.rfind("}")
        if i != -1 and j > i:
            t = t[i:j + 1]
    return t


class StructuredCaller:
    """Uma chamada de agente = uma entrada de cache. Registra modelo, digest, tokens, tempo, seed e finish_reason."""

    def __init__(self, cache: DiskCache, base_seed: int = 0, temperature: float = 0.0, max_tokens: int = 4000):
        self.cache, self.base_seed, self.temperature, self.max_tokens = cache, base_seed, temperature, max_tokens
        self._lock = threading.Lock()
        self.stats = {"calls": 0, "cache_hits": 0, "schema_failures": 0, "refusals": 0, "errors": 0}

    def call(self, client, step: str, prompt: Prompt, messages: list[dict], model_cls: type[BaseModel] | None, *,
             seed: int | None = None, temperature: float | None = None, max_tokens: int | None = None) -> dict:
        spec = client.spec
        seed = self.base_seed if seed is None else seed
        temperature = self.temperature if temperature is None else temperature
        max_tokens = self.max_tokens if max_tokens is None else max_tokens
        key = make_key(step=step, model=spec.tag, digest=spec.digest, effort=spec.reasoning_effort, infer=spec.infer_cfg,
                       prompt=prompt.name, phash=prompt.hash, messages=messages, temperature=temperature, seed=seed,
                       max_tokens=max_tokens, schema=model_cls.__name__ if model_cls else None, fake=client.is_fake)
        hit = self.cache.get(key)
        with self._lock:
            self.stats["calls"] += 1
            if hit is not None:
                self.stats["cache_hits"] += 1
        if hit is not None:
            hit["from_cache"] = True
            return hit

        schema = json_schema_of(model_cls) if model_cls else None
        rec = {"step": step, "model": spec.tag, "digest": spec.digest, "quantization": spec.quantization,
               "ollama_version": spec.ollama_version, "reasoning_effort": spec.reasoning_effort, "temperature": temperature,
               "base_seed": seed, "prompt": prompt.name, "prompt_hash": prompt.hash, "prompt_tokens": 0, "completion_tokens": 0,
               "seconds": 0.0, "attempts": 0, "schema_failures": 0, "refusal": False, "ok": False, "parsed": None,
               "content": "", "finish_reason": "", "error": None, "attempt_log": [], "from_cache": False, "cache_key": key}
        cur_max = max_tokens
        for attempt in range(1 + MAX_SCHEMA_RETRIES):
            a_seed = seed + 1000 * attempt                    # com temperature=0, repetir com a mesma seed daria o mesmo texto
            try:
                raw = client.chat(step, messages, schema, temperature, a_seed, cur_max)
            except RuntimeError as e:
                rec["error"] = f"rede: {e}"
                rec["attempts"] += 1
                break
            rec["attempts"] += 1
            rec["prompt_tokens"] += raw.prompt_tokens
            rec["completion_tokens"] += raw.completion_tokens
            rec["seconds"] += raw.seconds
            rec["content"], rec["finish_reason"] = raw.content, raw.finish_reason
            log = {"seed": a_seed, "max_tokens": cur_max, "finish_reason": raw.finish_reason,
                   "completion_tokens": raw.completion_tokens}
            rec["attempt_log"].append(log)
            if raw.finish_reason == "length" and cur_max < MAX_TOKENS_CAP:
                cur_max = min(MAX_TOKENS_CAP, cur_max * 2)    # plano: se for 'length', repita com mais tokens
                log["result"] = "length"
                continue
            if model_cls is None:                              # texto livre (B0)
                if raw.content.strip():
                    rec["ok"] = True
                    log["result"] = "ok"
                    break
                log["result"] = "vazio"
                continue
            try:
                parsed = model_cls.model_validate_json(extract_json(raw.content))
                rec["parsed"], rec["ok"] = parsed.model_dump(), True
                log["result"] = "ok"
                break
            except (ValidationError, ValueError) as e:
                rec["schema_failures"] += 1
                log["result"] = f"schema: {str(e)[:120]}"
                if REFUSAL.search(raw.content) and not raw.content.strip().startswith("{"):
                    rec["refusal"] = True
                    break                                      # recusa: nao adianta repetir
        if not rec["ok"] and rec["error"] is None:
            rec["error"] = "recusa" if rec["refusal"] else "schema/vazio"
        with self._lock:
            self.stats["schema_failures"] += rec["schema_failures"]
            self.stats["refusals"] += int(rec["refusal"])
            self.stats["errors"] += int(not rec["ok"])
        if not (rec["error"] or "").startswith("rede"):   # falha de rede e transitoria: nao entra no cache
            self.cache.put(key, rec)
        return rec


def sum_usage(records: list[dict]) -> dict:
    """Tokens e tempo de um conjunto de chamadas (custo de uma configuracao)."""
    recs = [r for r in records if r]
    return {"calls": len(recs), "prompt_tokens": sum(r["prompt_tokens"] for r in recs),
            "completion_tokens": sum(r["completion_tokens"] for r in recs),
            "seconds": round(sum(r["seconds"] for r in recs), 3),
            "failures": sum(1 for r in recs if not r["ok"]), "refusals": sum(1 for r in recs if r["refusal"])}
