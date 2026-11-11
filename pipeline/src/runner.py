"""Runner: fila por arquivo, reaproveitamento do A1, checkpoint por cache, retomada e guarda de horas de GPU.

Configuracoes:
  B0   prompt original do artigo (1 chamada) + extracao dos achados
  B1   so A1
  C1   A1 -> A3a
  C2   A1 -> A2 (todos) -> A3 conjunto (ve falha e patch, MESMO prompt adversarial do A3a)
  C3   A1 -> A3a -> A2 (so confirmados) -> A3b (com ferramentas)
  C3mf C3 com o verificador do MESMO modelo do A1 (ablacao H5, opcional)

Uso (da raiz do projeto):
  pipeline\\.venv\\Scripts\\python.exe -I pipeline\\src\\runner.py --dry-run --select first:3
  python pipeline/src/runner.py --config pipeline/config.yaml --select pilot --reps main      (no Kaggle, com servidores no ar)
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import re
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agents import CodeItem, Ctx  # noqa: E402
from agents.detector import run_a1, run_b0_extract, run_b0_response  # noqa: E402
from agents.fixer import run_a2  # noqa: E402
from agents.verifier import run_a3_joint, run_a3a, run_a3b  # noqa: E402
from config import build_ctx, load_config, rep_params  # noqa: E402
from dataset import read_text  # noqa: E402
from llm import sum_usage  # noqa: E402
from tools.scan import diff_scans, format_tool_report  # noqa: E402

ALL_CONFIGS = ("B0", "B1", "C1", "C2", "C3", "C3mf")
KEEP = ("step", "ok", "parsed", "prompt_tokens", "completion_tokens", "seconds", "refusal", "schema_failures", "attempts",
        "finish_reason", "cache_key", "model", "digest", "temperature", "base_seed", "error", "from_cache")


def compact(rec: dict | None) -> dict | None:
    """Registro de chamada sem o texto bruto (que fica no cache, indexado por cache_key)."""
    return None if rec is None else {k: rec.get(k) for k in KEEP}


def safe_name(file_id: str) -> str:
    return file_id.replace(":", "_")


def last_code_block(text: str) -> str | None:
    """Patch do B0: o ultimo bloco de codigo cercado da resposta (o prompt pede 'all code in one code fragment')."""
    blocks = re.findall(r"```[\w+#-]*\n(.*?)```", text or "", flags=re.S)
    return blocks[-1].rstrip("\n") if blocks else None


# --------------------------------------------------------------------------- dados
def load_items(raw_root: Path, files_jsonl: Path, select: str = "all") -> list[CodeItem]:
    """Arquivos analisados (48 positivos + 66 negativos). O 'excluido' (v8 File_02) fica de fora."""
    items = []
    with open(files_jsonl, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["class"] not in ("positive", "negative"):
                continue
            items.append(CodeItem(id=f"{r['snapshot']}:{r['folder']}", snapshot=r["snapshot"], file_number=r["file_number"],
                                  lang=r["language"], ext=r["code"]["ext"], code=read_text(raw_root / r["code"]["path"]), cls=r["class"]))
    return select_items(items, select)


def select_pilot(items: list[CodeItem], n_pos: int = 5, n_neg: int = 5) -> list[CodeItem]:
    """5 positivos + 5 negativos, estratificados por linguagem (rodizio C++, C, C#; deterministico)."""
    def pick(cls: str, n: int) -> list[CodeItem]:
        by_lang: dict[str, list[CodeItem]] = {}
        # ordena por (numero, snapshot) para intercalar v8 e v10 em vez de esgotar um snapshot primeiro
        for it in sorted((i for i in items if i.cls == cls), key=lambda i: (i.file_number, i.snapshot)):
            by_lang.setdefault(it.lang, []).append(it)
        order = sorted(by_lang, key=lambda lg: (-len(by_lang[lg]), lg))
        out: list[CodeItem] = []
        while len(out) < n and any(by_lang.values()):
            for lg in order:
                if by_lang[lg] and len(out) < n:
                    out.append(by_lang[lg].pop(0))
        return out
    return pick("positive", n_pos) + pick("negative", n_neg)


def select_items(items: list[CodeItem], select: str) -> list[CodeItem]:
    if select == "all":
        return items
    if select == "pilot":
        return select_pilot(items)
    if select.startswith("first:"):          # dry-run: os N primeiros (misturando classes)
        n = int(select.split(":")[1])
        pos = [i for i in items if i.cls == "positive"][: (n + 1) // 2]
        neg = [i for i in items if i.cls == "negative"][: n // 2]
        return (pos + neg)[:n]
    if select.startswith("part:"):           # F5: parte K de N (0-based), por posicao; intercala classes/linguagens e equilibra o custo
        k, n = (int(x) for x in select.split(":")[1].split("/"))
        return items[k::n]
    ids = set(select.split(","))
    return [i for i in items if i.id in ids]


# --------------------------------------------------------------------------- ferramentas de avaliacao
class FileTools:
    """Resultados de ferramentas de UM arquivo: o original e computado uma vez; cada patch uma vez."""

    def __init__(self, tools, item: CodeItem):
        self.tools, self.item = tools, item
        self.orig = {"compile": tools.compile(item.code, item.lang), "scan": tools.scan(item.code, item.lang)}
        self._patch: dict[str, dict] = {}

    def of_patch(self, patch_code: str) -> dict:
        if patch_code not in self._patch:
            self._patch[patch_code] = {"compile": self.tools.compile(patch_code, self.item.lang),
                                       "scan": self.tools.scan(patch_code, self.item.lang)}
        return self._patch[patch_code]

    def stored(self, patch_code: str) -> dict:
        """O que fica gravado em runs/: compilacao e achados dos scanners (original e patch)."""
        p = self.of_patch(patch_code)
        return {"compile_orig": self.orig["compile"], "compile_patch": p["compile"],
                "scan_orig": self.orig["scan"].get("findings", []), "scan_patch": p["scan"].get("findings", []),
                "scan_status": self.orig["scan"].get("status"), "available": self.orig["scan"].get("available", {})}

    def report_for(self, finding: dict, patch_code: str) -> str:
        """Relatorio que o A3b recebe (so saida de ferramentas; nada do gabarito)."""
        p = self.of_patch(patch_code)
        diff = diff_scans(self.orig["scan"], p["scan"], target_line=finding.get("lines") or [])
        return format_tool_report(self.orig["compile"], p["compile"], self.orig["scan"], p["scan"], diff)


# --------------------------------------------------------------------------- um arquivo
def _cwe_key(cwe: str) -> tuple:
    nums = re.findall(r"[0-9]+", str(cwe))
    return tuple(int(x) for x in nums[:1]) if nums else (str(cwe).strip().lower(),)


def dedupe_findings(findings: list[dict]) -> tuple[list[dict], int]:
    """Tira achados repetidos do A1: mesma CWE e alguma linha em comum com um achado anterior (fica o primeiro, na ordem do modelo).
    Achado sem linhas nunca e considerado repetido (nao ha como saber). Mesma CWE na mesma linha casaria com a mesma issue do
    gabarito, entao nao muda o recall; so evita pagar de novo o A3a/A2 pelo mesmo achado."""
    kept: list[dict] = []
    for f in findings:
        lines = set(int(x) for x in f.get("lines") or [])
        dup = bool(lines) and any(_cwe_key(k["cwe"]) == _cwe_key(f["cwe"]) and lines & set(int(x) for x in k.get("lines") or []) for k in kept)
        if not dup:
            kept.append(f)
    return kept, len(findings) - len(kept)


def process_file(ctx: Ctx, item: CodeItem, configs: list[str], rep: str) -> dict[str, dict]:
    """Roda as etapas necessarias e devolve {config: resultado}. Cada etapa pode ser compartilhada por varias configs."""
    out: dict[str, dict] = {}
    ft = FileTools(ctx.tools, item)
    base = {"file": item.id, "rep": rep, "class": item.cls, "lang": item.lang}

    # ---- B0
    if "B0" in configs:
        r0 = run_b0_response(ctx, item)
        ex = run_b0_extract(ctx, item, r0["content"]) if r0["ok"] else None
        fs = []
        if ex and ex["ok"]:
            for i, f in enumerate(ex["parsed"]["findings"], 1):
                fs.append({"id": f"E{i}", "cwe": f["cwe"], "lines": f["lines"], "title": f["description"], "confidence": None})
        patch = last_code_block(r0["content"]) if r0["ok"] else None
        out["B0"] = {**base, "config": "B0", "findings": [{"finding": f, "accepted": True, "accepted_sens": True} for f in fs],
                     "accepted": [f["id"] for f in fs], "response_chars": len(r0["content"]), "patch": patch,
                     "tools": ft.stored(patch) if patch else None,
                     "steps": {"b0_response": compact(r0), "b0_extract": compact(ex)}, "usage": sum_usage([r0, ex]),
                     "no_vulnerability": not fs}

    need_a1 = any(c in configs for c in ("B1", "C1", "C2", "C3", "C3mf"))
    if not need_a1:
        return out
    r1 = run_a1(ctx, item)
    findings = list(r1["parsed"]["findings"])[: ctx.max_findings] if r1["ok"] else []
    findings, n_dup = dedupe_findings(findings) if ctx.dedupe else (findings, 0)
    base["duplicates_removed"] = n_dup
    a1_ok = r1["ok"]

    # ---- B1
    if "B1" in configs:
        out["B1"] = {**base, "config": "B1", "a1_ok": a1_ok, "no_vulnerability": bool(r1["parsed"]["no_vulnerability"]) if a1_ok else None,
                     "findings": [{"finding": f, "accepted": True, "accepted_sens": True} for f in findings],
                     "accepted": [f["id"] for f in findings], "steps": {"a1": compact(r1)}, "usage": sum_usage([r1])}

    # ---- A3a (compartilhado por C1 e C3) e variante da mesma familia (C3mf)
    va = {f["id"]: run_a3a(ctx, item, f) for f in findings} if any(c in configs for c in ("C1", "C3")) else {}
    va_mf = ({f["id"]: run_a3a(ctx, item, f, client=ctx.det, step="a3a_mf") for f in findings} if "C3mf" in configs else {})

    def verdict(rec: dict | None) -> str | None:
        return rec["parsed"]["verdict"] if rec and rec["ok"] else None

    def tri(v: str | None) -> tuple[bool, bool]:
        return v == "confirmed", v in ("confirmed", "uncertain")   # (principal, sensibilidade: 'uncertain' conta como aceito)

    if "C1" in configs:
        rows = [{"finding": f, "a3a": compact(va[f["id"]]), "verdict": verdict(va[f["id"]]),
                 "accepted": tri(verdict(va[f["id"]]))[0], "accepted_sens": tri(verdict(va[f["id"]]))[1]} for f in findings]
        out["C1"] = {**base, "config": "C1", "a1_ok": a1_ok, "findings": rows, "accepted": [r["finding"]["id"] for r in rows if r["accepted"]],
                     "steps": {"a1": compact(r1)}, "usage": sum_usage([r1, *va.values()])}

    # ---- A2: todos os achados se C2 esta nas configuracoes; senao so os confirmados (C3 / C3mf)
    confirmed = {fid for fid, r in va.items() if verdict(r) == "confirmed"}
    confirmed_mf = {fid for fid, r in va_mf.items() if verdict(r) == "confirmed"}
    need_patch = {f["id"] for f in findings} if "C2" in configs else (confirmed | confirmed_mf)
    patches = {f["id"]: run_a2(ctx, item, f) for f in findings if f["id"] in need_patch}

    def patch_code(fid: str) -> str | None:
        r = patches.get(fid)
        return r["parsed"]["patched_code"] if r and r["ok"] else None

    # ---- C2
    if "C2" in configs:
        joints, rows = {}, []
        for f in findings:
            pc = patch_code(f["id"])
            j = run_a3_joint(ctx, item, f, pc) if pc is not None else None
            joints[f["id"]] = j
            v = verdict(j)
            rows.append({"finding": f, "a2": compact(patches.get(f["id"])), "a3joint": compact(j), "verdict": v,
                         "fix_verdict": (j["parsed"]["fix_verdict"] if j and j["ok"] else None),
                         "status": "a2_failed" if pc is None else "judged", "accepted": tri(v)[0], "accepted_sens": tri(v)[1],
                         "tools": ft.stored(pc) if pc is not None else None})
        out["C2"] = {**base, "config": "C2", "a1_ok": a1_ok, "findings": rows, "accepted": [r["finding"]["id"] for r in rows if r["accepted"]],
                     "steps": {"a1": compact(r1)}, "usage": sum_usage([r1, *patches.values(), *joints.values()])}

    # ---- C3 e C3mf
    for cfg, vmap, conf, a3b_step, a3b_client in (("C3", va, confirmed, "a3b", None), ("C3mf", va_mf, confirmed_mf, "a3b_mf", ctx.det)):
        if cfg not in configs:
            continue
        rows, a3bs = [], []
        for f in findings:
            v = verdict(vmap[f["id"]])
            row = {"finding": f, "a3a": compact(vmap[f["id"]]), "verdict": v, "accepted": tri(v)[0], "accepted_sens": tri(v)[1]}
            if f["id"] in conf:
                pc = patch_code(f["id"])
                row["a2"] = compact(patches.get(f["id"]))
                if pc is None:
                    row["status"] = "a2_failed"
                else:
                    b = run_a3b(ctx, item, f, pc, ft.report_for(f, pc), client=a3b_client, step=a3b_step)
                    a3bs.append(b)
                    row.update({"a3b": compact(b), "fix_verdict": b["parsed"]["fix_verdict"] if b["ok"] else None,
                                "status": "fixed_judged", "tools": ft.stored(pc)})
            rows.append(row)
        used_a2 = [patches[fid] for fid in conf if fid in patches]
        out[cfg] = {**base, "config": cfg, "a1_ok": a1_ok, "findings": rows, "accepted": [r["finding"]["id"] for r in rows if r["accepted"]],
                    "steps": {"a1": compact(r1)}, "usage": sum_usage([r1, *vmap.values(), *used_a2, *a3bs])}
    return out


# --------------------------------------------------------------------------- guarda de cota
class QuotaGuard:
    """Para de iniciar arquivos novos depois de `limit_hours` de sessao (sessoes do Kaggle caem em ate 12 h)."""

    def __init__(self, limit_hours: float, clock=time.time):
        self.limit_s, self.clock, self.t0 = limit_hours * 3600, clock, clock()

    def elapsed_hours(self) -> float:
        return (self.clock() - self.t0) / 3600

    def exceeded(self) -> bool:
        return (self.clock() - self.t0) >= self.limit_s


def log_session(runs_dir: Path, rec: dict) -> None:
    runs_dir.mkdir(parents=True, exist_ok=True)
    with open(runs_dir / "gpu_sessions.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- execucao
def run(cfg: dict, ctx: Ctx, items: list[CodeItem], reps: list[str], *, configs: list[str] | None = None,
        workers: int | None = None, guard: QuotaGuard | None = None, log=print) -> dict:
    runs_dir = Path(cfg["paths"]["runs_dir"])
    workers = workers or int(cfg.get("workers", {}).get("files_in_parallel", 4))
    summary = {"reps": {}}
    for rep in reps:
        params = rep_params(cfg, rep)
        cfgs = [c for c in (configs or params["configs"]) if c in params["configs"] or configs]
        rctx = dataclasses.replace(ctx, seed=params["seed"], temp_det=params["temp_det"], temp_ver=params["temp_ver"])
        pending = [it for it in items if not all((runs_dir / c / rep / f"{safe_name(it.id)}.json").exists() for c in cfgs)]
        log(f"[{rep}] configs={cfgs} seed={params['seed']} temp=({params['temp_det']},{params['temp_ver']}) "
            f"arquivos pendentes={len(pending)}/{len(items)}")
        it, lock, done, errors = iter(pending), threading.Lock(), [], []

        def worker() -> None:
            while True:
                if guard and guard.exceeded():
                    return
                with lock:
                    item = next(it, None)
                if item is None:
                    return
                try:
                    res = process_file(rctx, item, cfgs, rep)
                    for c, r in res.items():
                        p = runs_dir / c / rep
                        p.mkdir(parents=True, exist_ok=True)
                        tmp = p / f".{safe_name(item.id)}.tmp"
                        tmp.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
                        tmp.replace(p / f"{safe_name(item.id)}.json")
                    with lock:
                        done.append(item.id)
                        if len(done) % 5 == 0 or len(done) == len(pending):
                            log(f"[{rep}] {len(done)}/{len(pending)} arquivos")
                except Exception as e:  # noqa: BLE001 - um arquivo com erro nao derruba a fila; fica registrado
                    with lock:
                        errors.append({"file": item.id, "error": repr(e)})
                        log(f"[{rep}] ERRO em {item.id}: {e!r}")

        threads = [threading.Thread(target=worker, daemon=True) for _ in range(max(1, workers))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        stopped = bool(guard and guard.exceeded() and len(done) + len(errors) < len(pending))
        summary["reps"][rep] = {"done": len(done), "errors": errors, "stopped_by_quota_guard": stopped, "pending_left": len(pending) - len(done) - len(errors)}
        if stopped:
            log(f"[{rep}] guarda de cota: {guard.elapsed_hours():.2f} h de sessao; parando. Rode de novo para retomar (cache).")
            break
    summary["llm"] = dict(ctx.caller.stats)
    summary["cache_entries"] = len(ctx.caller.cache)
    if guard:
        summary["session_hours"] = round(guard.elapsed_hours(), 3)
        log_session(runs_dir, {"t_start": guard.t0, "hours": summary["session_hours"], "reps": reps, "files": len(items),
                               "done": {r: v["done"] for r, v in summary["reps"].items()}, "llm_calls": ctx.caller.stats["calls"],
                               "cache_hits": ctx.caller.stats["cache_hits"]})
    return summary


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    here = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(here / "config.yaml"))
    ap.add_argument("--root", default=None, help="raiz do projeto (no Kaggle: pasta do Dataset)")
    ap.add_argument("--work-dir", default=None, help="onde ficam cache/ e runs/ (no Kaggle: /kaggle/working)")
    ap.add_argument("--select", default="pilot", help="all | pilot | first:N | id1,id2")
    ap.add_argument("--reps", default="main")
    ap.add_argument("--configs", default=None, help="ex.: B0,B1,C1,C2,C3 (padrao: o que o config.yaml define por repeticao)")
    ap.add_argument("--dry-run", action="store_true", help="clientes e ferramentas simulados: nenhuma chamada a modelo")
    ap.add_argument("--det-url", default=None)
    ap.add_argument("--ver-url", default=None)
    ap.add_argument("--session-hours", type=float, default=None, help="guarda de cota: para de iniciar arquivos apos N horas")
    a = ap.parse_args()
    cfg = load_config(a.config, a.root, a.work_dir)
    if a.dry_run:
        import tempfile
        work = Path(tempfile.mkdtemp(prefix="taes_dry_"))
        cfg["paths"]["cache_dir"], cfg["paths"]["runs_dir"] = work / "cache", work / "runs"
        print(f"DRY-RUN: nenhuma chamada a modelo; saidas em {work}")
    ctx = build_ctx(cfg, dry_run=a.dry_run, det_url=a.det_url, ver_url=a.ver_url)
    items = load_items(cfg["paths"]["raw_root"], cfg["paths"]["data_dir"] / "files.jsonl", a.select)
    guard = QuotaGuard(a.session_hours or cfg["gpu"]["session_limit_hours"])
    summary = run(cfg, ctx, items, a.reps.split(","), configs=a.configs.split(",") if a.configs else None, guard=guard)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if a.dry_run:
        assert ctx.det.calls + ctx.ver.calls == ctx.caller.stats["calls"] - ctx.caller.stats["cache_hits"], "chamada inesperada"
    return 1 if any(v["errors"] for v in summary["reps"].values()) else 0


if __name__ == "__main__":
    sys.exit(main())
