# Шаг 1: max_tokens 2200→3200 + anti-truncation guard

> Зависит от: нет
> Статус: [x] done

## Задача

В `core/brain/synthesis.py`, функция `_synthesize_fragments`:

1. Поднять `max_tokens` с `2200` до `3200`.
   - Причина: промпт целится в ~2800 симв. кириллицы (до 3500). Кириллица дорогая
     в токенах (~0.5–0.7 токена/симв на токенайзере gpt-4o), 2200 режет вывод
     на полуслове при выводе у верхней границы.
2. После получения `content` из `complete(...)` добавить anti-truncation guard:
   - Если текст НЕ заканчивается на терминальную пунктуацию (`.`, `!`, `?`, `…`,
     `)`, `»`, или emoji-конец блока) И длина близка к лимиту — залогировать
     `logger.warning("synthesis output may be truncated: len=%d, ends with %r", ...)`.
   - Это НЕ исключение и НЕ повтор вызова — только сигнал (для golden set и
     прод-мониторинга). Текст возвращается как есть.
   - Проверку оформить отдельной чистой функцией `_looks_truncated(text: str) -> bool`
     (тестируемой без OpenAI).

`_looks_truncated`: вернуть True если `text` непустой и его последний
непробельный символ НЕ входит в множество терминальных. Множество (включая
типографские кавычки, которые реально встречаются в выводе):
`{'.', '!', '?', '…', ')', '»', '"', '”', '"'}`
(ASCII `"`, закрывающая `”` U+201D, и `»` U+00BB). Хвостовые пробелы/переводы
строк игнорировать (`text.rstrip()`). Пустой текст → False (не наша забота здесь).

Константу лимита вынести: `SYNTHESIS_MAX_TOKENS = 3200` рядом с другими
константами вверху модуля (не магическое число в теле функции).

## Тесты

Новый файл `tests/test_truncation_guard.py` (DB-free, OpenAI-free):
- `_looks_truncated("...текст без точки")` → True
- `_looks_truncated("Текст с точкой.")` → False
- `_looks_truncated("Вопрос?")` → False, `"Цитата»"` → False, `"...)"` → False
- `_looks_truncated("текст в кавычках”")` → False (закрывающая U+201D)
- `_looks_truncated("текст с переводом.\n\n  ")` → False (rstrip)
- `_looks_truncated("")` → False
- `_looks_truncated("оборвалось на полусл")` → True

Существующие тесты, которые могут сломаться: нет (значение max_tokens нигде не
ассертится; `_synthesize_fragments` зовёт OpenAI, в юнит-тестах не дёргается).

## Команды для верификации

```bash
cd c:/Users/renat/projects/wndrverse
python -c "from core.brain.synthesis import SYNTHESIS_MAX_TOKENS, _looks_truncated; print(SYNTHESIS_MAX_TOKENS); print(_looks_truncated('обрыв'), _looks_truncated('конец.'))"
# ожидаем: 3200 / True False
pytest tests/test_truncation_guard.py -q
```

## Критерии готовности

- [ ] `SYNTHESIS_MAX_TOKENS = 3200` объявлена вверху модуля, используется в `_synthesize_fragments`.
- [ ] `_looks_truncated` существует, чистая, покрыта тестами выше — все зелёные.
- [ ] При обрыве пишется `logger.warning` (проверено чтением кода / caplog-тестом опц.).
- [ ] `pytest tests/ -q` зелёный.
