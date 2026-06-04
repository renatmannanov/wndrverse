# Review: Code

## Критичное (блокирует выполнение)

### 1. `test_markup.py` — тест `test_pii_ref_passes_through_untouched` сломается после изменения контракта

Файл: `tests/test_markup.py`, строки 53–56.

```python
def test_pii_ref_passes_through_untouched():
    src = "Важно [Имя, 2026-05-29] и ещё [аноним]"
    assert markdown_to_telegram_html(src) == src
```

Тест проверяет старый формат `[Имя, дата]`. После плана имена подставляются без даты: `[Имя]` (не `[Имя, дата]`). Код `markdown_to_telegram_html` сам по себе не меняется — но тест документирует формат PII-ссылки. Если реальный e2e прогон выдаёт `[Имя]` вместо `[Имя, дата]`, тест продолжает зеленеть (он тестирует `markup.py`, не `cli.py`), но он описывает устаревший контракт. Это не технический слом, но есть смежный риск:

`test_realistic_digest_block` (строки 59–73) содержит:
```python
assert "- запрос на менторство [Лена, 2026-05-30]" in out
assert "[Аня, 2026-05-29]" in out
```
Эти ассерты жёстко прибиты к формату `[Имя, дата]`. Если впоследствии `markup.py` придётся адаптировать под новый формат `[Имя]`, тест сломается. Сейчас не блокирует, но `markup.py` явно задокументирован под старый формат (комментарий в docstring строка 11: `PII refs \`[Имя, 2026-05-29]\``). **Не обновить комментарий и docstring в `markup.py` — технический долг, который собьёт следующего агента.**

### 2. `_REF_RE` в `delivery/cli.py` будет матчить числа внутри `[@N]` — потенциальный двойной реплейс

Файл: `delivery/cli.py`, строка 25:
```python
_REF_RE = re.compile(r"\[?#?(\d+)\]?")
```

После плана `build_digest` переключается на `humanize_author_refs` и больше не вызывает `humanize_refs`. Но `_REF_RE` остаётся в модуле. Это не само по себе баг. **Критично другое:** если в коде (сейчас или потом) оба вызова окажутся активны одновременно — `_REF_RE` с паттерном `\[?#?(\d+)\]?` будет матчить `[@3]` как `[3]` (группа `(\d+)` поймает `3`). Это приведёт к тому что `[@N]` будет «humanize_refs»-ован в `[аноним, дата]` вместо `[@N]`.

**Конкретная проблема:** паттерн `\[?#?(\d+)\]?` — `#?` означает «ноль или один `#`». Строка `[@3]` содержит `@3]` — `@` НЕ является `#`, поэтому паттерн НЕ поймает `[@3]` как целое. НО: поймает ли он отдельную цифру `3` внутри строки `[@3] — предлагает`? Да, если применить `re.sub` ко всему тексту — паттерн `\[?#?(\d+)\]?` поймает голую `3` в середине `[@3]` как `(\d+)` без квадратных скобок, потому что `\[?` = необязательная `[`. Проверить: `re.sub(r"\[?#?(\d+)\]?", repl, "[@3] — текст")` — матчнётся `@3]` или `3`? Паттерн `\[?` матчит буквально `[` (необязательно). Символ `@` не входит в паттерн, поэтому `[@3]` начнётся матч с позиции после `@`: группа `(\d+)` захватит `3`, а `\]?` захватит `]`. Итог: `[@` останется, `3]` будет заменено.

**Вывод:** `_REF_RE.sub(repl, "[@3] — текст")` заменит `3]` на `[аноним, дата]` и оставит `[@`. Это **тихая корруптирация вывода** если `humanize_refs` когда-либо применяется к тексту с `[@N]`. План говорит «заменить вызов `humanize_refs` на `humanize_author_refs`» — это правильно, но план не говорит агенту удалить или задокументировать опасность `_REF_RE`.

**Что нужно:** в step_1 явно указать либо убрать вызов `humanize_refs` в `build_digest` (уже указано), либо добавить примечание что `_REF_RE` нельзя применять к тексту с `[@N]`.

---

## Важное (стоит исправить до начала)

### 3. `synthesize_and_save` — `author_refs` из `synthesize` пробрасывается автоматически, но план предлагает «убедиться»

Файл: `core/brain/synthesis.py`, строки 165–172:
```python
def synthesize_and_save(...) -> dict:
    result = synthesize(topic, fragments, topic_type=topic_type)
    artifact_id = save_artifact(
        topic=topic, content=result['content'], fragment_ids=result['fragment_ids']
    )
    result['artifact_id'] = artifact_id
    return result
```

Паттерн `result['artifact_id'] = artifact_id; return result` означает что `author_refs` из `synthesize` автоматически попадёт в возврат `synthesize_and_save` — поскольку это тот же dict. Хорошо. **Но:** `save_artifact` принимает `content=result['content']` — это уже после `author_refs` добавлен в dict? Нет — `synthesize` возвращает dict с `author_refs`, потом `save_artifact` вызывается, потом `result['artifact_id'] = artifact_id`. Порядок нормальный. `author_refs` не теряется. Это ОК, агенту только надо убедиться что новый ключ `author_refs` добавляется в `synthesize()` ДО `return result`, что и написано в плане.

### 4. Ветка `< 3` фрагментов в `synthesize` возвращает без `author_refs`

Файл: `core/brain/synthesis.py`, строки 70–73:
```python
if len(fragments) < 3:
    content = _insufficient_data_message(topic, fragments)
    return {'content': content, 'fragment_ids': [f['id'] for f in fragments],
            'found': found, 'model': COMPLETION_MODEL}
```

Этот return НЕ содержит `author_refs`. В `build_digest` план предлагает:
```python
text = humanize_author_refs(result['content'], result.get('author_refs', {}))
```
Защитный `.get('author_refs', {})` покрывает этот кейс. Но план говорит «Ветку `< 3` тоже вернуть с `author_refs: {}` для единообразия» — это корректное требование, агент должен добавить явно.

**Проблема:** `_insufficient_data_message` строит текст с `[#{f['id']}]` (строки 160–162 в `synthesis.py`). Если `humanize_refs` при этом НЕ вызывается (заменён на `humanize_author_refs`), то `[#id]`-ссылки в сообщении «недостаточно данных» НЕ будут substituted — останутся голые `[#207]` в выводе пользователю. Это небольшой регресс в UX для редкого кейса. **План этого не замечает и не решает.**

### 5. Сигнатура `_synthesize_fragments` расходится с описанием в PLAN.md

PLAN.md (строки 54–55) описывает существующую сигнатуру:
> `_synthesize_fragments(topic, topic_hint, fragments)` (стр. ~141)

Реальный код (строка 141):
```python
def _synthesize_fragments(topic: str, topic_hint: str, fragments: list[dict]) -> str:
```

Это совпадает. Но step_1 предлагает переписать на:
```python
def _synthesize_fragments(topic, topic_hint, grouped_text: str) -> str:
```

Вопрос: есть ли ещё кто-то, кто вызывает `_synthesize_fragments` напрямую? Проверка — нет, функция с именем `_synthesize_fragments` вызывается только из `synthesize()` (строка 92). Риска нет, но стоит знать.

### 6. `test_markup.py` — docstring `markup.py` и комментарий в коде описывают старый формат `[Имя, дата]`

Файл: `delivery/markup.py`, строки 10–11 и строки 44–46:
```python
# Why HTML: the digest's PII refs `[Имя, 2026-05-29]` ... pass through untouched.
# PII refs like [Имя, 2026-05-29] contain none of < > & ...
```

После плана формат станет `[Имя]` (без даты). Комментарий устареет. Технически `markdown_to_telegram_html` будет работать верно и с `[Имя]` — квадратные скобки без спецсимволов проходят насквозь. Но если агент читает `markup.py` в другом окне, он увидит старый формат и может засомневаться. **Рекомендация:** обновить комментарий в рамках шага 1 или 4.

### 7. `test_summary_command.py` — `test_valid_call_acks_then_dms_clean_digest` мокает `build_digest` возвращающим `{"text": "DIGEST TEXT", ...}` — тест будет зелёным независимо от изменений в `build_digest`

Файл: `tests/test_summary_command.py`, строки 128–150.

Тест мокает `build_digest` целиком — он не проверяет что `build_digest` внутри использует `humanize_author_refs` вместо `humanize_refs`. Это нормально для юнит-теста бота. Но **плановых тестов на `build_digest` с реальным вызовом `humanize_author_refs`** в step_1 нет явно. Step_1 говорит «`build_digest` (мок synthesize_and_save, возвращающий content c `[@1]` + `author_refs`) → итог содержит `[Имя]`, не содержит `[@1]`». Этого достаточно, но агент должен создать такой тест — в существующем suite его нет.

---

## Мелочи (можно по ходу)

### 8. `_author_key` для аноним возвращает `('anon', f['id'])` — `f['id']` это int из БД, уникально per-fragment

Файл: step_1_group_and_refs.md, строка с `return ('anon', f['id'])`.

Это корректно — каждое анонимное сообщение будет своим «автором» `[@N]`. Задокументировано в самом коде. Без замечаний.

### 9. `_group_by_author` сортирует по `f['created_at'] or ''` — пустая строка сортируется первой

Если у фрагмента `created_at = None` (теоретически возможно по DB-схеме: `nullable=False`, но для страховки), то `None or ''` = `''`, и такие фрагменты будут первыми. Реально `created_at` всегда есть (NOT NULL в схеме). Не блокирует.

### 10. Паттерн `_AUTHOR_REF_RE = re.compile(r"\[@(\d+)\]")` — строгий, не толерантный

В отличие от `_REF_RE` который толерантен к форматам LLM (`[207]`, `#207`, `(#207)`), новый `_AUTHOR_REF_RE` требует ровно `[@N]`. Это корректно — `[@N]` — наш собственный контракт, LLM должен его строго соблюдать (промпт это требует). Если LLM напишет `@1` без скобок — не подставится, но останется `@1` в тексте, что заметно. Низкий риск, упоминать как ожидаемое поведение при smoke test.

### 11. Нет теста на `_select_fragments` (Pass 1) с `[@N]`-вводом — но Pass 1 НЕ меняется, риска нет

Pass 1 использует `[{f['id']}]` (plain int без `#`). После плана Pass 1 остаётся без изменений и работает ДО группировки по автору. Верно.

---

## Не найдено проблем

- **Scheduler** (`digest/scheduler.py`) вызывает `_run_digest` → `build_digest` → внутри будет новый путь. Сигнатура `build_digest(topic_arg, since, until) -> {text, found, used}` не меняется — scheduler не сломается.
- **`synthesize_and_save`** пробрасывает `author_refs` автоматически (dict мутируется in-place перед return).
- **`get_fragments_for_digest`** уже возвращает `sender_id` и `author_name` (строки 282–293 в `fragments_db.py`) — план это учёл верно.
- **Существующие тесты** `test_scheduler.py`, `test_channels.py`, `test_ingest_bot.py`, `test_dedup_unify.py`, `test_date_range.py`, `test_topic_map.py`, `test_ingest_normalize.py`, `test_bot_adapter.py` не тестируют логику синтеза напрямую — не сломаются.
- **`bot/ingest_bot.py`** импортирует `build_digest` из `delivery.cli` и вызывает его как `build_digest(topic, since, until)` — сигнатура не меняется, не сломается.
- **Номера строк в PLAN.md** («стр. ~141» для `_synthesize_fragments`) — совпадают с реальным кодом (строка 141 в `synthesis.py`). «стр. ~81» для `humanize_refs` — совпадает (строка 81).
- **Плейсхолдер `{fragments_text}`** в промпте — совпадает с тем что использует код (строка 148 в `synthesis.py`).
