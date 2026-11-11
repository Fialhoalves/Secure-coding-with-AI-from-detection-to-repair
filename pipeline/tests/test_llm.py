"""Cache, prompts, schemas e o chamador estruturado (repeticoes, length, recusa, falha de rede)."""
import json

import pytest

from cache import DiskCache, make_key
from llm import FakeClient, ModelSpec, RawResponse, StructuredCaller, extract_json
from prompts import load_prompt, numbered, render
from schemas import A1Out, A3aOut, json_schema_of

SPEC = ModelSpec(key="detector", tag="m:1", digest="abc", parallel=1)
VALID_A1 = json.dumps({"no_vulnerability": True, "findings": []})


class Scripted:
    """Cliente que devolve respostas pre-definidas, na ordem; registra as chamadas."""
    is_fake = True

    def __init__(self, replies, spec=SPEC):
        self.spec, self.replies, self.calls = spec, list(replies), []

    def chat(self, step, messages, schema, temperature, seed, max_tokens):
        self.calls.append({"seed": seed, "max_tokens": max_tokens, "temperature": temperature, "schema": schema})
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        content, finish = r if isinstance(r, tuple) else (r, "stop")
        return RawResponse(content, 10, 5, 0.1, finish)


@pytest.fixture
def prompt(tmp_path):
    (tmp_path / "p_v1.md").write_text("### SYSTEM\nsys {{x}}\n\n### USER\nuser {{x}} {{y}}\n", encoding="utf-8")
    return load_prompt(tmp_path, "p_v1")


@pytest.fixture
def caller(tmp_path):
    return StructuredCaller(DiskCache(tmp_path / "c"))


MSGS = [{"role": "user", "content": "hi"}]


# --------------------------------------------------------------------------- prompts
def test_load_prompt_sections_and_hash(tmp_path, prompt):
    assert prompt.system == "sys {{x}}" and prompt.user == "user {{x}} {{y}}"
    assert len(prompt.hash) == 12
    (tmp_path / "p_v1.md").write_text("### SYSTEM\nsys {{x}}\n\n### USER\nuser CHANGED\n", encoding="utf-8")
    assert load_prompt(tmp_path, "p_v1").hash != prompt.hash          # editar sem trocar de versao muda o hash
    (tmp_path / "q.md").write_text("so texto\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_prompt(tmp_path, "q")


def test_render_is_single_pass_and_strict():
    # o codigo nao confiavel pode conter {{...}}: nao pode ser reprocessado como variavel
    assert render("A {{code}} B {{lang}}", code="{{lang}}", lang="C") == "A {{lang}} B C"
    with pytest.raises(KeyError):
        render("{{falta}}")


def test_numbered_code():
    assert numbered("a\nb") == "   1| a\n   2| b"


# --------------------------------------------------------------------------- schemas
def test_json_schema_has_no_refs_and_is_strict():
    s = json_schema_of(A1Out)
    txt = json.dumps(s)
    assert "$ref" not in txt and "$defs" not in txt
    item = s["properties"]["findings"]["items"]
    assert item["additionalProperties"] is False and set(item["required"]) == set(item["properties"])
    assert s["additionalProperties"] is False
    assert json_schema_of(A3aOut)["properties"]["verdict"]["enum"] == ["confirmed", "refuted", "uncertain"]


def test_confidence_is_clamped():
    f = A1Out.model_validate({"no_vulnerability": False, "findings": [{"id": "F1", "cwe": "CWE-1", "lines": [1], "title": "t",
                              "untrusted_source": "s", "sink": "k", "trigger": "g", "assumptions": "a", "confidence": 7}]})
    assert f.findings[0].confidence == 1.0


def test_extract_json_tolerates_fences_and_chatter():
    assert extract_json('```json\n{"a":1}\n```') == '{"a":1}'
    assert extract_json('Here you go: {"a":1} thanks') == '{"a":1}'


# --------------------------------------------------------------------------- cache
def test_cache_roundtrip_and_atomicity(tmp_path):
    c = DiskCache(tmp_path / "c")
    assert c.get("ab" * 32) is None and c.misses == 1
    c.put("ab" * 32, {"x": 1})
    assert c.get("ab" * 32) == {"x": 1} and c.hits == 1 and len(c) == 1
    assert not list((tmp_path / "c").rglob("*.tmp"))
    c.delete("ab" * 32)
    assert c.get("ab" * 32) is None


def test_cache_key_is_order_independent_and_sensitive():
    base = dict(step="a1", model="m", digest="d", prompt="a1_v1", phash="h", messages=[{"role": "user", "content": "x"}],
                temperature=0.0, seed=0)
    assert make_key(**base) == make_key(**dict(reversed(list(base.items()))))
    for k, v in (("digest", "d2"), ("phash", "h2"), ("seed", 1), ("temperature", 0.1), ("step", "a3a"), ("prompt", "a1_v2")):
        assert make_key(**{**base, k: v}) != make_key(**base), k


# --------------------------------------------------------------------------- chamador estruturado
def test_valid_call_is_cached(caller, prompt):
    cl = Scripted([VALID_A1])
    r1 = caller.call(cl, "a1", prompt, MSGS, A1Out)
    assert r1["ok"] and r1["parsed"]["no_vulnerability"] and not r1["from_cache"]
    assert r1["model"] == "m:1" and r1["digest"] == "abc" and r1["base_seed"] == 0 and r1["temperature"] == 0.0
    r2 = caller.call(cl, "a1", prompt, MSGS, A1Out)
    assert r2["from_cache"] and len(cl.calls) == 1 and caller.stats["cache_hits"] == 1


def test_schema_failure_retries_with_new_seed(caller, prompt):
    cl = Scripted(["isto nao e json", '{"no_vulnerability": "talvez"}', VALID_A1])
    r = caller.call(cl, "a1", prompt, MSGS, A1Out, seed=7)
    assert r["ok"] and r["attempts"] == 3 and r["schema_failures"] == 2
    assert [c["seed"] for c in cl.calls] == [7, 1007, 2007]             # mesma seed + temperatura 0 repetiria a resposta
    assert r["prompt_tokens"] == 30 and r["completion_tokens"] == 15    # custo soma todas as tentativas


def test_gives_up_after_two_retries_and_records_failure(caller, prompt):
    cl = Scripted(["x", "y", "z", "nunca"])
    r = caller.call(cl, "a1", prompt, MSGS, A1Out)
    assert not r["ok"] and r["attempts"] == 3 and r["error"] == "schema/vazio" and caller.stats["errors"] == 1
    assert caller.call(cl, "a1", prompt, MSGS, A1Out)["from_cache"]    # a falha tambem e cacheada (nao gasta GPU de novo)


def test_length_finish_retries_with_more_tokens(caller, prompt):
    cl = Scripted([('{"no_vulnerability": tr', "length"), VALID_A1])
    r = caller.call(cl, "a1", prompt, MSGS, A1Out, max_tokens=1000)
    assert r["ok"] and [c["max_tokens"] for c in cl.calls] == [1000, 2000]


def test_refusal_is_flagged_and_not_retried(caller, prompt):
    cl = Scripted(["I'm sorry, but I can't help with that request.", VALID_A1])
    r = caller.call(cl, "a1", prompt, MSGS, A1Out)
    assert r["refusal"] and not r["ok"] and r["attempts"] == 1 and r["error"] == "recusa" and caller.stats["refusals"] == 1


def test_network_error_is_not_cached(caller, prompt):
    cl = Scripted([RuntimeError("conexao recusada")])
    r = caller.call(cl, "a1", prompt, MSGS, A1Out)
    assert not r["ok"] and r["error"].startswith("rede") and len(caller.cache) == 0


def test_free_text_call_without_schema(caller, prompt):
    cl = Scripted(["texto livre"])
    r = caller.call(cl, "b0_response", prompt, MSGS, None)
    assert r["ok"] and r["parsed"] is None and r["content"] == "texto livre" and cl.calls[0]["schema"] is None


def test_cache_distinguishes_seed_temperature_digest_and_prompt(caller, prompt, tmp_path):
    cl = Scripted([VALID_A1] * 6)
    caller.call(cl, "a1", prompt, MSGS, A1Out)
    caller.call(cl, "a1", prompt, MSGS, A1Out, seed=1)
    caller.call(cl, "a1", prompt, MSGS, A1Out, temperature=0.7)
    caller.call(Scripted([VALID_A1], spec=ModelSpec(key="detector", tag="m:1", digest="OUTRO")), "a1", prompt, MSGS, A1Out)
    (tmp_path / "p_v1.md").write_text("### USER\nmudou\n", encoding="utf-8")
    caller.call(cl, "a1", load_prompt(tmp_path, "p_v1"), MSGS, A1Out)
    assert len(caller.cache) == 5 and len(cl.calls) == 4


def test_fake_and_real_results_never_share_cache_entries(caller, prompt):
    class Real(Scripted):
        is_fake = False
    caller.call(Scripted([VALID_A1]), "a1", prompt, MSGS, A1Out)
    r = caller.call(Real([VALID_A1]), "a1", prompt, MSGS, A1Out)
    assert not r["from_cache"] and len(caller.cache) == 2


def test_fake_client_is_deterministic_and_makes_no_network_calls(prompt):
    fc = FakeClient(SPEC)
    msgs = [{"role": "user", "content": "Language: C\n<code>\n   1| strcpy(a, b);\n</code>"}]
    a = fc.chat("a1", msgs, None, 0.0, 0, 100)
    b = fc.chat("a1", msgs, None, 0.0, 0, 100)
    assert a.content == b.content and fc.calls == 2
    assert json.loads(a.content)["findings"][0]["lines"] == [1]


def test_a1_flag_is_derived_from_findings():
    f = {"id": "F1", "cwe": "CWE-1", "lines": [1], "title": "t", "untrusted_source": "s", "sink": "k", "trigger": "g", "assumptions": "a", "confidence": 0.5}
    assert A1Out.model_validate({"no_vulnerability": True, "findings": [f]}).no_vulnerability is False      # modelo se contradiz
    assert A1Out.model_validate({"no_vulnerability": False, "findings": []}).no_vulnerability is True
