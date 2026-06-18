"""Anti-truncation guard — pure, DB-free / OpenAI-free."""

from core.brain.synthesis import SYNTHESIS_MAX_TOKENS, _looks_truncated


def test_max_tokens_constant():
    assert SYNTHESIS_MAX_TOKENS == 3200


def test_truncated_no_terminal_punct():
    assert _looks_truncated("...текст без точки") is True
    assert _looks_truncated("оборвалось на полусл") is True


def test_complete_endings_not_truncated():
    assert _looks_truncated("Текст с точкой.") is False
    assert _looks_truncated("Вопрос?") is False
    assert _looks_truncated("Восклицание!") is False
    assert _looks_truncated("Многоточие…") is False
    assert _looks_truncated("Цитата»") is False
    assert _looks_truncated("...)") is False


def test_typographic_closing_quote():
    assert _looks_truncated("текст в кавычках”") is False  # U+201D


def test_rstrip_trailing_whitespace():
    assert _looks_truncated("текст с переводом.\n\n  ") is False


def test_empty_is_false():
    assert _looks_truncated("") is False
    assert _looks_truncated("   \n") is False
