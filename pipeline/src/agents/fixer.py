"""A2 (corretor): patch minimo para UM achado; devolve o codigo completo corrigido."""
from __future__ import annotations

from agents import CodeItem, Ctx, finding_json
from prompts import numbered
from schemas import A2Out


def run_a2(ctx: Ctx, item: CodeItem, finding: dict) -> dict:
    p = ctx.prompts["a2"]
    msgs = p.messages(lang=item.lang, numbered_code=numbered(item.code), finding_json=finding_json(finding))
    return ctx.caller.call(ctx.det, "a2", p, msgs, A2Out, max_tokens=ctx.caps["a2"], **ctx.kw(ctx.det))
