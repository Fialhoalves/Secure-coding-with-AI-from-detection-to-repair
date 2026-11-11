"""A1 (detector) e B0 (prompt original do artigo, 1 chamada, + extracao dos achados da resposta em texto livre)."""
from __future__ import annotations

from agents import CodeItem, Ctx, fence_lang
from prompts import numbered
from schemas import A1Out, ExtractOut


def run_a1(ctx: Ctx, item: CodeItem) -> dict:
    p = ctx.prompts["a1"]
    msgs = p.messages(lang=item.lang, numbered_code=numbered(item.code))
    return ctx.caller.call(ctx.det, "a1", p, msgs, A1Out, max_tokens=ctx.caps["a1"], **ctx.kw(ctx.det))


def run_b0_response(ctx: Ctx, item: CodeItem) -> dict:
    """Prompt original do artigo (Apendice C), literal, sem mensagem de sistema. Resposta em texto livre."""
    p = ctx.prompts["b0"]
    msgs = p.messages(fence_lang=fence_lang(item), code=item.code)
    return ctx.caller.call(ctx.det, "b0_response", p, msgs, None, max_tokens=ctx.caps["b0_response"], **ctx.kw(ctx.det))


def run_b0_extract(ctx: Ctx, item: CodeItem, response_text: str) -> dict:
    """Converte a resposta do B0 em achados estruturados (CWE, linhas, descricao) com o mesmo modelo do A1."""
    p = ctx.prompts["b0_extract"]
    msgs = p.messages(lang=item.lang, numbered_code=numbered(item.code), review=response_text)
    # a extracao e deterministica de proposito (temperatura 0), qualquer que seja a repeticao
    return ctx.caller.call(ctx.det, "b0_extract", p, msgs, ExtractOut, max_tokens=ctx.caps["b0_extract"], seed=0, temperature=0.0)
