"""Regression guard: the synthesis prompt uses the [@N] author contract.

After digest-group-by-author the prompt must instruct the LLM in [@N] terms and
must NOT carry the old [#ID]/[#id] message-ref contract (which would desync with
humanize_author_refs and leave raw refs in the output).
"""

from core.brain.synthesis import _load_prompt


def test_synthesis_prompt_uses_author_contract():
    prompt = _load_prompt("digest_synthesis.md")
    assert "[@" in prompt                     # new author-ref contract present
    assert "[#ID]" not in prompt              # old message-ref contract gone
    assert "[#id]" not in prompt
    # placeholders the code fills must still be there
    assert "{topic}" in prompt
    assert "{topic_hint}" in prompt
    assert "{fragments_text}" in prompt


def test_main_themes_block_demands_substance():
    """ГЛАВНЫЕ ТЕМЫ now wants 1-2 sentences of substance per theme, and the
    other two blocks must still be present (we only touched the themes block)."""
    prompt = _load_prompt("digest_synthesis.md")
    assert "ГЛАВНЫЕ ТЕМЫ" in prompt
    assert "СУТИ" in prompt or "суть" in prompt.lower()   # substance demanded
    # the [@N] ban inside the themes block is preserved
    assert "НЕ ставь ссылки `[@N]`" in prompt
    # the other blocks were NOT removed
    assert "КТО ЧТО" in prompt
    assert "ЗАПРОСЫ И ПРЕДЛОЖЕНИЯ" in prompt
