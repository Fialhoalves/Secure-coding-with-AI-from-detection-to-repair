"""Prompts versionados (pipeline/prompts/<nome>.md). O nome (ex.: 'a1_v1') e a versao; o hash do texto tambem
entra na chave de cache, para que uma edicao sem troca de versao nao reaproveite respostas antigas."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

_TOKEN = re.compile(r"\{\{(\w+)\}\}")


@dataclass(frozen=True)
class Prompt:
    name: str
    system: str | None
    user: str
    hash: str

    def messages(self, **vars) -> list[dict]:
        msgs = []
        if self.system:
            msgs.append({"role": "system", "content": render(self.system, **vars)})
        msgs.append({"role": "user", "content": render(self.user, **vars)})
        return msgs


def render(template: str, **vars) -> str:
    """Troca {{chave}} em UMA passada: o conteudo substituido (codigo nao confiavel) nao e reprocessado."""
    def sub(m):
        key = m.group(1)
        if key not in vars:
            raise KeyError(f"variavel de prompt ausente: {key}")
        return str(vars[key])
    return _TOKEN.sub(sub, template)


def load_prompt(prompts_dir: str | Path, name: str) -> Prompt:
    text = (Path(prompts_dir) / f"{name}.md").read_text(encoding="utf-8")
    parts = re.split(r"^### (SYSTEM|USER)\n", text, flags=re.M)
    # parts = ['', 'SYSTEM', corpo, 'USER', corpo] ou ['', 'USER', corpo]
    sections = {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}
    if "USER" not in sections:
        raise ValueError(f"{name}: falta a secao '### USER'")
    system = sections.get("SYSTEM")
    return Prompt(name=name,
                  system=system.strip("\n") if system else None,
                  user=sections["USER"].rstrip("\n"),
                  hash=hashlib.sha256(text.encode("utf-8")).hexdigest()[:12])


def numbered(code: str) -> str:
    """Codigo com numeros de linha ('   1| ...'), como o A1/A3/A2 o recebem."""
    return "\n".join(f"{i:>4}| {line}" for i, line in enumerate(code.splitlines(), 1))
