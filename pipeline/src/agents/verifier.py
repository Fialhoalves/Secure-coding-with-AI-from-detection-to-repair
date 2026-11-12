"""Verificadores adversariais. A3a e o A3 conjunto (C2) usam o MESMO prompt (a3_v1.md): so mudam o bloco do patch
e a especificacao de saida (mesma postura de julgamento nos dois formatos). O A3b julga a correcao com a saida das ferramentas."""
from __future__ import annotations

from agents import CodeItem, Ctx, finding_json
from prompts import numbered
from schemas import A3aOut, A3bOut, A3JointOut

SPEC_A3A = ('Reply with JSON: {"finding_id", "verdict": "confirmed" | "refuted" | "uncertain", "refutation_attempt", '
            '"evidence_lines", "confidence"}.')
SPEC_JOINT = ('Also judge the proposed patch above. Reply with JSON: {"finding_id", "verdict": "confirmed" | "refuted" | '
              '"uncertain" (is the REPORTED FINDING real?), "refutation_attempt", "evidence_lines", "confidence", '
              '"fix_verdict": "valid" | "partial" | "invalid" (does the patch fix the finding?), "trigger_blocked", '
              '"behavior_preserved", "unnecessary_changes"}.')


def run_a3a(ctx: Ctx, item: CodeItem, finding: dict, *, client=None, step: str = "a3a") -> dict:
    """Verifica UM achado por chamada (julgamentos independentes). NAO ve a correcao."""
    p = ctx.prompts["a3"]
    msgs = p.messages(lang=item.lang, numbered_code=numbered(item.code), finding_json=finding_json(finding),
                      patch_block="", output_spec=SPEC_A3A)
    c = client or ctx.ver
    return ctx.caller.call(c, step, p, msgs, A3aOut, max_tokens=ctx.caps["a3a"], **ctx.kw(c))


def run_a3_joint(ctx: Ctx, item: CodeItem, finding: dict, patched_code: str) -> dict:
    """C2: mesma postura adversarial do A3a, mas ve tambem o patch e julga a falha e a correcao numa resposta so."""
    p = ctx.prompts["a3"]
    patch_block = f"\nProposed patch (complete corrected code):\n<patch>\n{patched_code}\n</patch>\n"
    msgs = p.messages(lang=item.lang, numbered_code=numbered(item.code), finding_json=finding_json(finding),
                      patch_block=patch_block, output_spec=SPEC_JOINT)
    return ctx.caller.call(ctx.ver, "a3joint", p, msgs, A3JointOut, max_tokens=ctx.caps["a3joint"], **ctx.kw(ctx.ver))


def run_a3b(ctx: Ctx, item: CodeItem, finding: dict, patched_code: str, tool_report: str, *, client=None,
            step: str = "a3b") -> dict:
    p = ctx.prompts["a3b"]
    msgs = p.messages(lang=item.lang, numbered_code=numbered(item.code), finding_json=finding_json(finding),
                      patched_code=patched_code, tool_report=tool_report)
    c = client or ctx.ver
    return ctx.caller.call(c, step, p, msgs, A3bOut, max_tokens=ctx.caps["a3b"], **ctx.kw(c))
