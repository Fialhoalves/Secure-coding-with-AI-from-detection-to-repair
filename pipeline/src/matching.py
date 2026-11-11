"""Correspondencia entre achados (ou respostas em texto livre) e o gabarito dos autores.

Dois usos:
  * F2 (respostas do artigo, texto livre): `mentions_issue` - a resposta cita um CWE compativel OU o
    identificador-chave da linha do gabarito.
  * F6 (achados estruturados do pipeline): `finding_matches_issue` - mesmo arquivo, linha a +-3 e CWE compativel.
"""
from __future__ import annotations

import re

from cwe import any_compatible

LINE_TOLERANCE = 3
NL = chr(10)
C_KEYWORDS = {"if", "for", "while", "switch", "return", "sizeof", "catch", "else", "do", "case", "goto", "new",
              "delete", "const", "static", "struct", "class", "int", "char", "void", "long", "short", "unsigned",
              "signed", "float", "double", "bool", "auto", "var", "string", "using", "namespace", "public",
              "private", "protected", "typedef", "enum", "union", "true", "false", "null", "nullptr", "this"}
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def cwe_mentions(text: str) -> list[int]:
    """Numeros de CWE citados no texto ('CWE-120', 'CWE 120'), sem repeticao, na ordem de aparicao."""
    seen: list[int] = []
    for m in re.finditer(r"CWE[-\s]?([0-9]+)", text or "", flags=re.I):
        n = int(m.group(1))
        if n not in seen:
            seen.append(n)
    return seen


def key_identifiers(source_code: str | None, include_names: bool = False) -> list[str]:
    """Identificadores que 'nomeiam' a linha do gabarito: chamadas de funcao; se nao houver, os demais nomes.

    include_names=True acrescenta sempre os demais nomes (variaveis, argumentos), alem das chamadas.
    """
    if not source_code:
        return []
    code = re.sub(r'"(?:\\.|[^"\\])*"', '""', source_code)       # tira literais de string
    code = re.sub(r"'(?:\\.|[^'\\])*'", "''", code)
    calls = [m.group(1) for m in re.finditer(r"([A-Za-z_][A-Za-z0-9_:.>-]*)\s*\(", code)]
    calls = [c.split("::")[-1].split(".")[-1].split(">")[-1] for c in calls]
    calls = [c for c in dict.fromkeys(calls) if c and c.lower() not in C_KEYWORDS and len(c) >= 3]
    names = [n for n in dict.fromkeys(_IDENT.findall(code)) if n.lower() not in C_KEYWORDS and len(n) >= 3]
    if include_names:
        return list(dict.fromkeys(calls + names))
    return calls or names


def cites_identifier(text: str, identifiers: list[str]) -> str | None:
    """Primeiro identificador citado no texto como palavra inteira (diferencia maiusculas)."""
    for ident in identifiers:
        if re.search(r"(?<![A-Za-z0-9_])" + re.escape(ident) + r"(?![A-Za-z0-9_])", text or ""):
            return ident
    return None


def split_sections(text: str) -> list[str]:
    """Divide a resposta em secoes: cada titulo markdown ('#') ou item numerado em negrito abre uma secao.

    Blocos de codigo cercados ficam dentro da secao em que aparecem (e sao removidos depois, se for o caso).
    """
    parts, cur, in_code = [], [], False
    for line in (text or "").splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        starts = (not in_code) and re.match(r"^\s*(#{1,6}\s|\*\*[0-9]+[.)]|[0-9]+[.)]\s+\*\*|[0-9]+[.)]\s)", line)
        if starts and cur:
            parts.append(NL.join(cur))
            cur = []
        cur.append(line)
    if cur:
        parts.append(NL.join(cur))
    return parts


def strip_code_blocks(text: str) -> str:
    """Remove os blocos de codigo cercados (```...```): o patch repete quase todo identificador do original."""
    return re.sub(r"```.*?(```|\Z)", " ", text or "", flags=re.S)


def mentions_issue(response: str, issue_cwes: list[int], source_code: str | None, *, mode: str = "cwe_or_ident",
                   ident_scope: str = "prose", ident_names: bool = False, section: bool = False,
                   **compat_kw) -> dict:
    """A resposta em texto livre menciona o issue? mode: 'cwe' | 'ident' | 'cwe_or_ident' | 'cwe_and_ident'.

    ident_scope: 'prose' (so a analise, sem blocos de codigo) ou 'full' (resposta inteira).
    """
    idents = key_identifiers(source_code, include_names=ident_names)
    if section:  # CWE compativel e identificador na MESMA secao da resposta
        for sec in split_sections(response):
            c = cwe_mentions(sec)
            h = any_compatible(c, issue_cwes, **compat_kw) if (c and issue_cwes) else None
            i = cites_identifier(strip_code_blocks(sec) if ident_scope == "prose" else sec, idents)
            if (mode == "cwe_and_ident" and h and i) or (mode == "cwe" and h) or (mode == "ident" and i)                     or (mode == "cwe_or_ident" and (h or i)):
                return {"mention": True, "cwe_hit": h, "ident_hit": i}
        return {"mention": False, "cwe_hit": None, "ident_hit": None}
    cited = cwe_mentions(response)
    hit = any_compatible(cited, issue_cwes, **compat_kw) if (cited and issue_cwes) else None
    ident = cites_identifier(strip_code_blocks(response) if ident_scope == "prose" else response, idents)
    if mode == "cwe":
        ok = hit is not None
    elif mode == "ident":
        ok = ident is not None
    elif mode == "cwe_and_ident":
        ok = hit is not None and ident is not None
    else:
        ok = hit is not None or ident is not None
    return {"mention": ok, "cwe_hit": hit, "ident_hit": ident}


def finding_matches_issue(finding: dict, issue: dict, *, tolerance: int = LINE_TOLERANCE, require_cwe: bool = True,
                          **compat_kw) -> dict:
    """Achado do pipeline x issue do gabarito (F6).

    finding: {"cwe": int|str, "lines": [int, ...]}; issue: {"line": int, "cwe_ids": [int, ...]}.
    Mesma linha a +-`tolerance` (qualquer linha do achado) e CWE compativel. Issue sem CWE em nenhuma fonte
    casa so por linha. `require_cwe=False` = sensibilidade "so linha".
    """
    lines = [int(x) for x in finding.get("lines") or []]
    near = [x for x in lines if abs(x - int(issue["line"])) <= tolerance]
    if not near:
        return {"match": False, "reason": "linha"}
    if not require_cwe or not issue.get("cwe_ids"):
        return {"match": True, "reason": "linha(sem CWE)" if not issue.get("cwe_ids") else "linha"}
    raw = str(finding.get("cwe", ""))
    f_cwes = cwe_mentions(raw) or [int(x) for x in re.findall(r"(?<![0-9])[0-9]{1,4}(?![0-9])", raw)]  # aceita "120"
    hit = any_compatible(f_cwes, issue["cwe_ids"], **compat_kw) if f_cwes else None
    return {"match": hit is not None, "reason": hit[0] if hit else "cwe"}
