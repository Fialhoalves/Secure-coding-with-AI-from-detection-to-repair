"""Agentes do pipeline: detector (A1), verificador do achado (A3a / A3 conjunto), corretor (A2), verificador da
correcao (A3b) e o B0 (prompt original do artigo + extracao). Cada funcao devolve o registro da chamada (dict)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from llm import StructuredCaller
from prompts import Prompt, numbered


@dataclass
class CodeItem:
    """Um arquivo do experimento (o codigo efetivamente enviado aos LLMs pelos autores)."""
    id: str                  # 'v8:File_01'
    snapshot: str
    file_number: int
    lang: str                # 'C' | 'C++' | 'C#'
    ext: str                 # '.c' | '.cpp' | '.cs'
    code: str
    cls: str = ""            # positive | negative (so para analise; NUNCA vai para um agente)


@dataclass
class Ctx:
    caller: StructuredCaller
    prompts: dict[str, Prompt]
    det: object              # cliente do detector/corretor
    ver: object              # cliente do verificador
    tools: object
    caps: dict = field(default_factory=lambda: {"b0_response": 4000, "b0_extract": 2000, "a1": 3000, "a3a": 1500,
                                                 "a3joint": 1500, "a2": 4000, "a3b": 1500})
    dedupe: bool = True      # remove achados repetidos do A1 (mesma CWE, linhas em comum) depois do teto
    max_findings: int = 4    # teto de achados do A1 por arquivo (na ordem do modelo: "mais plausivel primeiro"; nao usa a confianca)
    seed: int = 0            # execucao principal: seed 0, temperatura 0; estudo de variancia: seeds 1-3
    temp_det: float = 0.0
    temp_ver: float = 0.0

    def kw(self, client) -> dict:
        """seed e temperatura da repeticao atual para o cliente (detector/corretor ou verificador)."""
        return {"seed": self.seed, "temperature": self.temp_det if client is self.det else self.temp_ver}


def finding_json(finding: dict) -> str:
    """O verificador e o corretor veem o achado SEM a confianca do detector (evita ancoragem)."""
    f = {k: v for k, v in finding.items() if k != "confidence"}
    return json.dumps(f, indent=2, ensure_ascii=False)


def fence_lang(item: CodeItem) -> str:
    return item.ext.lstrip(".")   # igual ao dos autores: 'c', 'cpp', 'cs'
