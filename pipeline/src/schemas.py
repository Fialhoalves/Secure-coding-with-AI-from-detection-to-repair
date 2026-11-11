"""Saidas estruturadas dos agentes. Validadas com Pydantic; o JSON schema
(sem $ref) vai na requisicao ao Ollama."""
from __future__ import annotations

import copy
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


class Finding(BaseModel):
    id: str
    cwe: str
    lines: list[int]
    title: str
    untrusted_source: str
    sink: str
    trigger: str
    assumptions: str
    confidence: float

    @field_validator("confidence")
    @classmethod
    def _conf(cls, v: float) -> float:
        return _clamp01(v)


class A1Out(BaseModel):
    no_vulnerability: bool
    findings: list[Finding]

    @model_validator(mode="after")
    def _consistent(self) -> "A1Out":
        """Modelos pequenos as vezes dizem 'nenhuma vulnerabilidade' e listam achados (visto no ensaio em CPU): os achados
        sao a saida substantiva, entao a flag passa a ser derivada deles."""
        self.no_vulnerability = not self.findings
        return self


class A3aOut(BaseModel):
    finding_id: str
    verdict: Literal["confirmed", "refuted", "uncertain"]
    refutation_attempt: str
    evidence_lines: list[int]
    confidence: float

    @field_validator("confidence")
    @classmethod
    def _conf(cls, v: float) -> float:
        return _clamp01(v)


class A2Out(BaseModel):
    finding_id: str
    patched_code: str
    change_summary: str
    how_trigger_is_blocked: str
    behavior_changes: str


class A3bOut(BaseModel):
    finding_id: str
    fix_verdict: Literal["valid", "partial", "invalid"]
    trigger_blocked: bool
    behavior_preserved: bool
    new_issues: list[str]
    unnecessary_changes: bool
    notes: str


class A3JointOut(BaseModel):
    """A3 conjunto (C2): julga a falha (como o A3a) e a correcao numa resposta so."""
    finding_id: str
    verdict: Literal["confirmed", "refuted", "uncertain"]
    refutation_attempt: str
    evidence_lines: list[int]
    confidence: float
    fix_verdict: Literal["valid", "partial", "invalid"]
    trigger_blocked: bool
    behavior_preserved: bool
    unnecessary_changes: bool

    @field_validator("confidence")
    @classmethod
    def _conf(cls, v: float) -> float:
        return _clamp01(v)


class ExtractedFinding(BaseModel):
    cwe: str
    lines: list[int]
    description: str


class ExtractOut(BaseModel):
    """Achados que a resposta em texto livre do B0 AFIRMA (sem julgar se sao verdadeiros)."""
    findings: list[ExtractedFinding]


def inline_refs(schema: dict) -> dict:
    """Remove $defs/$ref (o conversor JSON schema -> gramatica do Ollama e mais seguro sem referencias)."""
    defs = schema.get("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].split("/")[-1]
                return walk(copy.deepcopy(defs[name]))
            return {k: walk(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(schema)


def json_schema_of(model: type[BaseModel]) -> dict:
    """JSON schema do modelo, sem referencias, com additionalProperties=false em todo objeto."""
    s = inline_refs(model.model_json_schema())

    def strict(node):
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
            for v in node.values():
                strict(v)
        elif isinstance(node, list):
            for v in node:
                strict(v)

    strict(s)
    s.pop("title", None)
    return s
