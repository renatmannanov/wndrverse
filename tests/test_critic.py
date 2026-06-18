"""Self-critic (Pass-3) — DB-free, OpenAI mocked.

Covers: the WNDR_DIGEST_CRITIC flag, tolerant JSON parsing, fail-soft on garbage,
the PII contract (no names in the critic prompt), and synthesize() integration.
"""

import core.brain.synthesis as syn


# --- flag -------------------------------------------------------------------

def test_critic_disabled_by_default(monkeypatch):
    monkeypatch.delenv("WNDR_DIGEST_CRITIC", raising=False)
    assert syn._critic_enabled() is False


def test_critic_flag_truthy(monkeypatch):
    for v in ("1", "true", "TRUE", "yes", " Yes "):
        monkeypatch.setenv("WNDR_DIGEST_CRITIC", v)
        assert syn._critic_enabled() is True
    for v in ("0", "false", "no", ""):
        monkeypatch.setenv("WNDR_DIGEST_CRITIC", v)
        assert syn._critic_enabled() is False


# --- _critique parsing ------------------------------------------------------

def test_critique_returns_defect_list(monkeypatch):
    monkeypatch.setattr(syn, "_load_prompt", lambda n: "{digest}{sources}")
    monkeypatch.setattr(syn, "complete",
                        lambda *a, **k: '["обрыв в конце", "выдуман [@9]"]')
    out = syn._critique("дайджест [@1]", "[@1]:\nтекст")
    assert out == ["обрыв в конце", "выдуман [@9]"]


def test_critique_garbage_is_empty(monkeypatch):
    monkeypatch.setattr(syn, "_load_prompt", lambda n: "{digest}{sources}")
    monkeypatch.setattr(syn, "complete", lambda *a, **k: "не json вообще")
    assert syn._critique("d", "s") == []


def test_critique_empty_array(monkeypatch):
    monkeypatch.setattr(syn, "_load_prompt", lambda n: "{digest}{sources}")
    monkeypatch.setattr(syn, "complete", lambda *a, **k: "[]")
    assert syn._critique("d", "s") == []


def test_critique_non_list_json_is_empty(monkeypatch):
    monkeypatch.setattr(syn, "_load_prompt", lambda n: "{digest}{sources}")
    monkeypatch.setattr(syn, "complete", lambda *a, **k: '{"x": 1}')
    assert syn._critique("d", "s") == []


def test_critique_uses_synthesis_model(monkeypatch):
    monkeypatch.setattr(syn, "_load_prompt", lambda n: "{digest}{sources}")
    seen = {}

    def fake(prompt, **kwargs):
        seen.update(kwargs)
        return "[]"

    monkeypatch.setattr(syn, "complete", fake)
    syn._critique("d", "s")
    assert seen["model"] == syn.COMPLETION_MODEL_SYNTHESIS
    assert seen["temperature"] == 0.0


# --- PII: no names reach the critic prompt ----------------------------------

def test_critique_prompt_has_no_names(monkeypatch):
    captured = {}

    def capture(prompt, **kwargs):
        captured["prompt"] = prompt
        return "[]"

    monkeypatch.setattr(syn, "complete", capture)
    # real prompt template (not mocked) so we test the actual wiring
    frags = [
        {"id": 1, "text": "первое сообщение длинное", "created_at": "2026-05-01",
         "author_name": "Иван Петров", "username": "ivanp", "sender_id": 111},
        {"id": 2, "text": "второе сообщение тоже", "created_at": "2026-05-02",
         "author_name": "Мария Сидорова", "username": "mary", "sender_id": 222},
    ]
    grouped_text, refs = syn._group_by_author(frags)
    syn._critique("дайджест [@1] [@2]", grouped_text)

    prompt = captured["prompt"]
    for name in ("Иван", "Петров", "Мария", "Сидорова", "ivanp", "mary"):
        assert name not in prompt, f"PII leak: {name!r} in critic prompt"
    # the anonymous keys ARE expected
    assert "[@1]" in prompt and "[@2]" in prompt


# --- synthesize() integration ----------------------------------------------

def _frags(n=4):
    return [{"id": i, "text": f"содержательное сообщение номер {i}",
             "created_at": f"2026-05-0{i}", "author_name": f"A{i}",
             "username": None, "sender_id": i} for i in range(1, n + 1)]


def test_synthesize_critic_off_no_call(monkeypatch):
    monkeypatch.delenv("WNDR_DIGEST_CRITIC", raising=False)
    monkeypatch.setattr(syn, "_synthesize_fragments", lambda *a, **k: "Готовый дайджест.")
    monkeypatch.setattr(syn, "save_artifact", lambda **k: 1)

    def boom(*a, **k):
        raise AssertionError("critic must not run when disabled")

    monkeypatch.setattr(syn, "_critique", boom)
    result = syn.synthesize("offerings", _frags())
    assert result["critic_issues"] == []
    assert result["content"] == "Готовый дайджест."


def test_synthesize_critic_on_attaches_issues(monkeypatch):
    monkeypatch.setenv("WNDR_DIGEST_CRITIC", "1")
    monkeypatch.setattr(syn, "_synthesize_fragments", lambda *a, **k: "Готовый дайджест.")
    monkeypatch.setattr(syn, "_critique", lambda d, s: ["обрыв в конце"])
    result = syn.synthesize("offerings", _frags())
    assert result["critic_issues"] == ["обрыв в конце"]
    # content untouched by the critic
    assert result["content"] == "Готовый дайджест."
