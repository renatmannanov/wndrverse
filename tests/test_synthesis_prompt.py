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
