"""Testes de cwe.py e matching.py com uma hierarquia CWE sintetica (nenhum arquivo externo)."""
import pytest

import matching as mt
from cwe import CWEHierarchy, any_compatible, compatible, load_families

XML = """<?xml version="1.0"?>
<Weakness_Catalog xmlns="http://cwe.mitre.org/cwe-8"><Weaknesses>
  <Weakness ID="664" Name="Pillar P" Abstraction="Pillar"><Related_Weaknesses/></Weakness>
  <Weakness ID="20" Name="Improper Input Validation" Abstraction="Class"><Related_Weaknesses>
      <Related_Weakness Nature="ChildOf" CWE_ID="664" View_ID="1000"/></Related_Weaknesses></Weakness>
  <Weakness ID="129" Name="Array index" Abstraction="Variant"><Related_Weaknesses>
      <Related_Weakness Nature="ChildOf" CWE_ID="20" View_ID="1000"/>
      <Related_Weakness Nature="ChildOf" CWE_ID="999" View_ID="700"/></Related_Weaknesses></Weakness>
  <Weakness ID="1284" Name="Quantity" Abstraction="Base"><Related_Weaknesses>
      <Related_Weakness Nature="ChildOf" CWE_ID="20" View_ID="1000"/></Related_Weaknesses></Weakness>
  <Weakness ID="401" Name="Leak" Abstraction="Base"><Related_Weaknesses>
      <Related_Weakness Nature="ChildOf" CWE_ID="664" View_ID="1000"/></Related_Weaknesses></Weakness>
</Weaknesses></Weakness_Catalog>"""


@pytest.fixture
def hier(tmp_path):
    p = tmp_path / "v.xml"
    p.write_text(XML, encoding="utf-8")
    return CWEHierarchy.from_xml(p)


@pytest.fixture
def families(tmp_path):
    p = tmp_path / "f.yaml"
    p.write_text("families:\n  buffer: [119, 120, 787]\n  command: [77, 78]\n", encoding="utf-8")
    return load_families(p)


def test_hierarchy_only_uses_requested_view(hier):
    assert hier.parents[129] == {20}                      # o pai da view 700 foi ignorado
    assert hier.ancestors(129) == {20: 1, 664: 2}
    assert hier.is_pillar(664) and not hier.is_pillar(20)


def test_compatible_equal_hierarchy_family(hier, families):
    assert compatible(120, 120) == "igual"
    assert compatible(129, 20, hier) == "hierarquia" and compatible(20, 129, hier) == "hierarquia"
    assert compatible(129, 1284, hier) is None             # irmaos: nao sao ancestral um do outro
    assert compatible(120, 787, None, families) == "familia"
    assert compatible(120, 78, None, families) is None
    assert compatible(129, 20) is None                     # sem hierarquia nem familia


def test_pillars_and_hops(hier):
    assert compatible(401, 664, hier) is None              # ancestral e Pillar: generico demais
    assert compatible(401, 664, hier, allow_pillars=True) == "hierarquia"
    assert compatible(129, 664, hier, allow_pillars=True) == "hierarquia"
    assert compatible(129, 664, hier, allow_pillars=True, max_hops=1) is None   # 2 saltos > 1


def test_any_compatible_returns_first_pair(hier):
    assert any_compatible([77, 129], [20, 999], hierarchy=hier) == ("hierarquia", 129, 20)
    assert any_compatible([77], [78]) is None
    assert any_compatible([], [20]) is None


def test_real_families_file_loads():
    from pathlib import Path
    fams = load_families(Path(__file__).resolve().parent.parent / "matching_families.yaml")
    assert len(fams) == 7 and frozenset({119, 120, 121, 122, 125, 126, 131, 787, 805}) in fams


# --------------------------------------------------------------------------- texto livre
def test_cwe_mentions():
    assert mt.cwe_mentions("CWE-120 e CWE 120, cwe-20; 'CWE-1164: x'") == [120, 20, 1164]
    assert mt.cwe_mentions(None) == []


def test_key_identifiers():
    assert mt.key_identifiers('int fd = open("/dev/ttyS0", O_RDWR);') == ["open"]
    assert mt.key_identifiers("if (x) memcpy(dst, src, n);") == ["memcpy"]              # 'if' e palavra-chave
    assert mt.key_identifiers('printf("scanf inside string");') == ["printf"]           # literal de string removido
    assert mt.key_identifiers("char request[BUFFER_SIZE];") == ["request", "BUFFER_SIZE"]  # sem chamadas: nomes
    assert mt.key_identifiers("int fd = open(path, flags);", include_names=True) == ["open", "path", "flags"]
    assert mt.key_identifiers("obj->read(a)") == ["read"] and mt.key_identifiers(None) == []


def test_cites_identifier_whole_word_only():
    assert mt.cites_identifier("usa strcpy sem checar", ["strcpy"]) == "strcpy"
    assert mt.cites_identifier("usa strcpy_s com cuidado", ["strcpy"]) is None
    assert mt.cites_identifier("my_open()", ["open"]) is None


def test_strip_code_blocks_and_sections():
    txt = "## A\ntexto strcpy\n```c\nstrcpy(a,b);\n```\n## B\nfim"
    assert "strcpy(a,b)" not in mt.strip_code_blocks(txt) and "texto strcpy" in mt.strip_code_blocks(txt)
    assert len(mt.split_sections(txt)) == 2
    assert len(mt.split_sections("1. **Um**\nx\n2. **Dois**\ny")) == 2
    assert len(mt.split_sections("```\n# nao e titulo\n```")) == 1                      # '#' dentro de codigo


RESP = ("## 1. Unchecked copy (CWE-120)\nThe call to `strcpy` overflows the buffer.\n"
        "## 2. Other (CWE-20)\nInput not validated.\n```c\nmemcpy(a, b, n);\n```\n")


def test_mentions_issue_modes():
    kw = dict(issue_cwes=[120], source_code="strcpy(buf, src);")
    assert mt.mentions_issue(RESP, mode="cwe", **kw)["mention"]
    assert mt.mentions_issue(RESP, mode="ident", **kw)["ident_hit"] == "strcpy"
    assert mt.mentions_issue(RESP, mode="cwe_and_ident", **kw)["mention"]
    # CWE diferente + identificador so dentro do bloco de codigo
    kw2 = dict(issue_cwes=[78], source_code="memcpy(a, b, n);")
    assert not mt.mentions_issue(RESP, mode="cwe_or_ident", ident_scope="prose", **kw2)["mention"]
    assert mt.mentions_issue(RESP, mode="cwe_or_ident", ident_scope="full", **kw2)["mention"]


def test_mentions_issue_section_level_requires_cooccurrence():
    # CWE-20 esta na secao 2 e 'strcpy' na secao 1: no nivel global casam; no nivel de secao, nao
    kw = dict(issue_cwes=[20], source_code="strcpy(buf, src);", mode="cwe_and_ident")
    assert mt.mentions_issue(RESP, **kw)["mention"]
    assert not mt.mentions_issue(RESP, section=True, **kw)["mention"]
    assert mt.mentions_issue(RESP, section=True, issue_cwes=[120], source_code="strcpy(buf, src);",
                             mode="cwe_and_ident")["mention"]


# --------------------------------------------------------------------------- achados estruturados (F6)
@pytest.mark.parametrize("lines,expected", [([10], True), ([13], True), ([7], True), ([14], False), ([6], False),
                                            ([20, 11], True), ([], False)])
def test_line_tolerance_is_inclusive_3(lines, expected):
    issue = {"line": 10, "cwe_ids": [120]}
    assert mt.finding_matches_issue({"cwe": "CWE-120", "lines": lines}, issue)["match"] is expected


def test_finding_cwe_rules(hier, families):
    issue = {"line": 10, "cwe_ids": [20]}
    kw = dict(hierarchy=hier, families=families)
    assert mt.finding_matches_issue({"cwe": "CWE-129: Array index", "lines": [10]}, issue, **kw) == {"match": True, "reason": "hierarquia"}
    assert mt.finding_matches_issue({"cwe": "120", "lines": [10]}, {"line": 10, "cwe_ids": [787]}, **kw)["reason"] == "familia"
    assert not mt.finding_matches_issue({"cwe": "CWE-401", "lines": [10]}, issue, **kw)["match"]
    assert mt.finding_matches_issue({"cwe": "CWE-401", "lines": [10]}, issue, require_cwe=False)["match"]   # sensibilidade
    no_cwe = {"line": 10, "cwe_ids": []}                                            # falso alarme sem CWE: so linha
    assert mt.finding_matches_issue({"cwe": "CWE-401", "lines": [11]}, no_cwe, **kw) == {"match": True, "reason": "linha(sem CWE)"}
    assert not mt.finding_matches_issue({"cwe": "", "lines": [10]}, issue, **kw)["match"]
