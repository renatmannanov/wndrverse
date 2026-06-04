# Review Summary — digest-group-by-author

> Дата: 2026-06-04
> Ревью: code + risks + structure (3 агента, sonnet)

## Критичное (блокирует / даёт неверный результат)

1. **`_REF_RE` ломает `[@N]`-текст** (code #1). Старый регэксп `\[?#?(\d+)\]?`
   в delivery/cli.py:25 матчит цифру внутри `[@N]` → если по тексту с `[@N]`
   случайно прогонится `humanize_refs`, выйдет каша. План переключает на
   `humanize_author_refs`, но НЕ предупреждает агента, что прогонять обе нельзя.
   → step_1 должен явно: build_digest зовёт ТОЛЬКО `humanize_author_refs`, и
   `_AUTHOR_REF_RE` (`\[@(\d+)\]`) не пересекается с `_REF_RE`.

2. **«Заменить», а не «добавить» вызов в build_digest** (structure C1). step_1
   формулирует нечётко — агент может оставить и `humanize_refs`, и
   `humanize_author_refs` рядом. → явно: УДАЛИТЬ строку
   `humanize_refs(result['content'], result['fragment_ids'])`, поставить
   `humanize_author_refs(result['content'], result.get('author_refs', {}))`.

3. **Имена авторов могут утечь в логи** (risks #3). `author_refs={N: "Реальное
   Имя"}` теперь в возврате `synthesize()`. Если что-то логирует весь `result`
   на DEBUG — реальные имена попадут в journalctl на VPS. PII-правило проекта.
   → step_1: добавить пункт «не логировать author_refs / result целиком»;
   проверить, что synthesize_and_save и build_digest не пишут result в лог.

## Важное

4. **Merge в master ДО smoke + нет отката** (risks #5, structure W2). step_3
   мержит feature→master и пушит ДО прод-smoke. Если smoke провалит — плохой
   код уже в master. И согласование merge написано как комментарий, а не
   СТОП-точка → агент может запушить автономно (нарушение протокола CLAUDE.md).
   → step_3: (а) явная СТОП-точка «дождись подтверждения владельца перед merge»;
   (б) порядок — либо smoke на feature-ветке до merge, либо план отката.

5. **`_insufficient_data_message` (<3 фрагментов) остаётся на `[#id]`** (code #2).
   synthesis.py:160-162 строит текст с `[#id]`; после переключения на
   `humanize_author_refs` эти ссылки не раскроются. План возвращает
   `author_refs:{}` для этой ветки, но не чинит сам текст. → step_1: либо
   `_insufficient_data_message` тоже перевести на имена/без ссылок, либо
   осознанно оставить (мелкий UX в редкой ветке) — зафиксировать ОДИН вариант.

6. **Нет теста build_digest на `[@N]`→`[Имя]`** (code #4, risks #6). План требует
   его, но стоит подчеркнуть как обязательный (мок synthesize_and_save → content
   с `[@1]` + author_refs → вывод содержит `[Имя]`, не содержит `[@1]`).
   Заодно тест, что author_refs не теряется в synthesize_and_save.

7. **Фраза «Сигнатура на выбор — ОДИН вариант»** (structure W1, risks). Вариант
   по сути зафиксирован, но формулировка «на выбор» сбивает. → убрать слова «на
   выбор», оставить однозначно: `_synthesize_fragments(topic, topic_hint, grouped_text)`.

## Мелочи

- Много анонимов → много `[@N]` строк (risks #4, THEORETICAL-ish, CONFIRMED по
  механике). Для commits-кейса неактуально; отметить как известное ограничение.
- LLM может выдумать `[@N]` которого нет → останется сырым (risks #2). Низкая
  вероятность при temp 0.4; `humanize_author_refs` оставляет as-is — не падает.
- `delivery/markup.py` / test_markup docstrings описывают формат `[Имя, дата]` —
  после фичи в КТО ЧТО будет `[Имя]` без даты. Тесты markup не сломаются, но
  доки устареют (code #3). Обновить комментарий при случае.
- step_4 не даёт путь к context.md (structure). Мелочь — есть в глобальном CLAUDE.md.
- «опционально» у теста промпта в step_2 — сделать тест обязательным (regression).

## Проверено ревьюером-оркестратором (НЕ риск)

- **Pass 1 НЕ сломается** (risks #1 — снято). Проверено: `_select_fragments`
  использует ОТДЕЛЬНЫЙ файл `digest_selection.md`, а step_2 правит только
  `digest_synthesis.md`. Конфликта нет. Но step_2 стоит явно написать: «правишь
  ТОЛЬКО digest_synthesis.md, digest_selection.md не трогаешь».

## Противоречия между ревьюерами
- Нет. Находки дополняют друг друга.

## Рекомендации (что поправить в плане до запуска)
1. step_1: явно «УДАЛИТЬ humanize_refs-вызов, поставить humanize_author_refs»
   + «не пересекается с _REF_RE» + «не логировать author_refs/result».
2. step_1: зафиксировать судьбу `_insufficient_data_message` (один вариант).
3. step_1: убрать «Сигнатура на выбор».
4. step_2: «правишь только digest_synthesis.md».
5. step_3: явная СТОП-точка перед merge + порядок smoke/merge или откат.
6. Тест build_digest [@N]→[Имя] — сделать обязательным.
