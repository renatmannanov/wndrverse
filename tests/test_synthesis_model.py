"""Pass-2 synthesis model split — DB-free / OpenAI-free."""

import os

from core.llm.client import COMPLETION_MODEL, COMPLETION_MODEL_SYNTHESIS
import core.brain.synthesis as syn


def test_selection_model_unchanged():
    assert COMPLETION_MODEL == "gpt-4o-mini"


def test_synthesis_model_default_or_env():
    # default gpt-4o unless overridden via env at import time
    assert COMPLETION_MODEL_SYNTHESIS == os.getenv("WNDR_SYNTHESIS_MODEL", "gpt-4o")


def test_synthesize_fragments_calls_synthesis_model(monkeypatch):
    calls = []

    def fake_complete(prompt, **kwargs):
        calls.append(kwargs)
        return "Готовый дайджест."

    monkeypatch.setattr(syn, "complete", fake_complete)
    monkeypatch.setattr(syn, "_load_prompt", lambda name: "{topic}{topic_hint}{fragments_text}")

    syn._synthesize_fragments("offerings", "hint", "[@1]:\nтекст")

    assert len(calls) == 1
    assert calls[0]["model"] == COMPLETION_MODEL_SYNTHESIS
    assert calls[0]["model"] == "gpt-4o"


def test_select_fragments_uses_default_model(monkeypatch):
    """Pass-1 selection must NOT pass an explicit model (stays on mini default)."""
    calls = []

    def fake_complete(prompt, **kwargs):
        calls.append(kwargs)
        return "1, 2, 3, 4, 5, 6"

    monkeypatch.setattr(syn, "complete", fake_complete)
    monkeypatch.setattr(syn, "_load_prompt", lambda name: "{topic}{topic_hint}{target}{fragments_list}")

    frags = [{"id": i, "created_at": "2026-05-01", "text": f"t{i}"} for i in range(1, 7)]
    syn._select_fragments("offerings", "hint", frags)

    assert len(calls) == 1
    assert "model" not in calls[0]  # default COMPLETION_MODEL (mini)
