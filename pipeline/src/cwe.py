"""Compatibilidade entre CWEs: igualdade, ancestral/descendente na CWE Research View 1000, ou familia."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

NS = "{http://cwe.mitre.org/cwe-8}"  # o XML atual usa cwe-8; versoes antigas usam cwe-7 (tratado abaixo)


class CWEHierarchy:
    """Pais (ChildOf) de cada CWE na view escolhida, mais nome e nivel de abstracao."""

    def __init__(self, parents: dict[int, set[int]], abstraction: dict[int, str], names: dict[int, str]):
        self.parents, self.abstraction, self.names = parents, abstraction, names
        self._anc: dict[int, dict[int, int]] = {}

    @classmethod
    def from_xml(cls, path: str | Path, view_id: str = "1000") -> "CWEHierarchy":
        parents: dict[int, set[int]] = {}
        abstraction: dict[int, str] = {}
        names: dict[int, str] = {}
        for _, el in ET.iterparse(str(path), events=("end",)):
            tag = el.tag.split("}")[-1]
            if tag != "Weakness":
                continue
            cid = int(el.get("ID"))
            abstraction[cid], names[cid] = el.get("Abstraction", ""), el.get("Name", "")
            ps = parents.setdefault(cid, set())
            for rel in el.iter():
                if rel.tag.split("}")[-1] == "Related_Weakness" and rel.get("Nature") == "ChildOf" \
                        and rel.get("View_ID") == view_id:
                    ps.add(int(rel.get("CWE_ID")))
            el.clear()
        return cls(parents, abstraction, names)

    def ancestors(self, cid: int) -> dict[int, int]:
        """{ancestral: numero minimo de saltos ChildOf}."""
        if cid in self._anc:
            return self._anc[cid]
        out: dict[int, int] = {}
        frontier, hops = {cid}, 0
        while frontier:
            hops += 1
            nxt: set[int] = set()
            for c in frontier:
                for p in self.parents.get(c, ()):
                    if p not in out and p != cid:
                        out[p] = hops
                        nxt.add(p)
            frontier = nxt
        self._anc[cid] = out
        return out

    def is_pillar(self, cid: int) -> bool:
        return self.abstraction.get(cid) == "Pillar"


def load_families(path: str | Path) -> list[frozenset[int]]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [frozenset(int(x) for x in members) for members in data["families"].values()]


def compatible(a: int, b: int, hierarchy: CWEHierarchy | None = None, families=(),
               allow_pillars: bool = False, max_hops: int | None = None) -> str | None:
    """Motivo da compatibilidade ('igual' | 'hierarquia' | 'familia') ou None.

    Hierarquia: um e ancestral do outro na view 1000. Por padrao o ancestral nao pode ser um Pillar
    (ex.: CWE-664, 707), porque casaria com quase tudo; `max_hops` limita a distancia.
    """
    if a == b:
        return "igual"
    if hierarchy is not None:
        for x, y in ((a, b), (b, a)):  # y ancestral de x
            hops = hierarchy.ancestors(x).get(y)
            if hops is not None and (max_hops is None or hops <= max_hops) \
                    and (allow_pillars or not hierarchy.is_pillar(y)):
                return "hierarquia"
    for fam in families:
        if a in fam and b in fam:
            return "familia"
    return None


def any_compatible(cwes_a, cwes_b, **kw) -> tuple[str, int, int] | None:
    """Primeiro par compativel entre duas listas de CWE: (motivo, a, b) ou None."""
    for a in cwes_a:
        for b in cwes_b:
            why = compatible(int(a), int(b), **kw)
            if why:
                return why, int(a), int(b)
    return None
