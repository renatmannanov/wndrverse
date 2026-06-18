# Review: Code

## Критичное (блокирует выполнение)

### 1. `test_topics_build.py` line 60 — жёсткий ассерт на set ключей сломается

Файл: `tests/test_topics_build.py`, строка 60:
```python
assert set(t.keys()) == {'name', 'msgs', 'anchor_channel_id', 'anchor_external_id'}
```
После шага 1 `build_topics` добавляет ключ `'intrigue'` в каждую тему. Этот ассерт упадёт с `AssertionError` потому что `'intrigue'` не входит в ожидаемое множество. Нужно добавить `'intrigue'` в ожидаемый set (или переписать ассерт как `assert 'intrigue' in t`).

---

### 2. `_parse_json_array` (synthesis.py) — НЕ подходит как образец для парсинга объекта `{name, intrigue}`

Шаг 1 говорит: «переиспользовать ту же логику, что `_critique` уже применяет». Но `_parse_json_array` (строки 290–310) парсит **массив** (`[...]`), а fallback ищет `s.find("[")` и `s.rfind("]")`. Для объекта `{"name": "...", "intrigue": "..."}` нужен парс **dict** через `json.loads`, а fallback должен искать `{` и `}`. Логика `_parse_json_array` нельзя использовать напрямую — нужна новая локальная функция (например `_parse_json_object`) с аналогичным tolerant-подходом, но для `{...}`. Иначе fence-stripping сработает, но fallback по `[`/`]` пропустит валидный ответ-объект и поднимет исключение, которое catch перехватит как `intrigue=""`.

---

## Важное (стоит исправить до начала)

### 3. `test_topics_build.py` — мок `complete` возвращает строку, но после шага 1 ожидается JSON

В тестах `test_build_topics_two_clusters_ranked`, `test_anchor_skips_loose_early_member`, `test_anchor_falls_back_when_no_tight_members`, `test_chain_msgs_exclude_reactions_likes_include`, `test_reaction_texts_dont_glue_two_conversations`, `test_monologue_dropped` — все они патчат `complete` возвращающий строку (`"стаб-тема"`, `"x"`):
```python
monkeypatch.setattr(topics_mod, "complete", lambda *a, **k: "стаб-тема")
```
После шага 1 `build_topics` будет делать `json.loads` на этой строке. Fail-soft поймает исключение и вернёт `name="тема"`, `intrigue=""`. Тест `test_build_topics_two_clusters_ranked` явно проверяет `t['name'] == "стаб-тема"` — он упадёт. Все остальные мок-тесты молча получат `name="тема"` вместо мокового значения (не упадут, но будут тестировать не то).

Нужно обновить моки на валидный JSON: `lambda *a, **k: '{"name": "стаб-тема", "intrigue": ""}'`.

---

### 4. `tests/test_topics_render.py` — все фикстуры тем не содержат ключ `'intrigue'`

Строки 33–37, 49–51 — все `topics` в фикстурах не имеют поля `'intrigue'`. Если `render_topics` будет обращаться как `t['intrigue']` (а не `t.get('intrigue')`), тесты упадут с `KeyError`. Шаг 1 правильно предписывает использовать `.get('intrigue')` — это нужно строго соблюдать, иначе существующие тесты сломаются без модификации фикстур.

---

### 5. `test_synthesis_prompt.py` — тест ассертит точные фразы, которые план меняет

Файл: `tests/test_synthesis_prompt.py`. Текущие ассерты минималистичны (только `"[@"`, `"[#ID]"`, плейсхолдеры) — они НЕ ассертят конкретные фразы блока ГЛАВНЫЕ ТЕМЫ. Однако план (шаг 2) говорит «Может сломаться: `test_synthesis_prompt.py` — если он ассертит точные фразы блока». Проверка: в `test_synthesis_prompt.py` нет ассертов на `"короткой формулировкой"` или другой точной фразы из блока тем. Значит существующие тесты НЕ сломаются от правки промпта — но нужно НАПИСАТЬ новый ассерт на наличие «сути» / «предложения» в блоке, как и предписывает шаг 2.

---

## Мелочи (можно по ходу)

### 6. Докстринг `build_topics` (topics.py) не обновлён

Строки 56–57:
```python
Returns [{name, msgs, anchor_channel_id, anchor_external_id}, ...] sorted by ...
```
После шага 1 туда добавляется `intrigue`. Докстринг станет неточным. Некритично, но лучше обновить сразу при правке этой функции.

---

### 7. Докстринг `topics_render.py` — `TopicCluster contract` не включает `intrigue`

Строки 8–15:
```python
TopicCluster contract (built by brain.topics.build_topics):
    {
      'name': str,
      'msgs': int,
      ...
    }
```
Контракт в шапке файла станет неполным после добавления поля `'intrigue'`. Обновить комментарий при правке файла.

---

### 8. Golden runner (`tests/golden/run.py`) использует только `build_digest`, не `build_topics_digest`

Файл: `tests/golden/run.py` строки 31, 70. Runner вызывает `build_digest` (для `/summary`) — golden покрывает только шаг 2 (themes block в синтезе). Для проверки шага 1 (`/topics` с интригой) golden нет и, согласно шагу 3, не планируется — только ручной smoke. Это осознанный out-of-scope, но стоит держать в голове: регрессия в `/topics` не будет поймана автоматически.

---

## Не найдено проблем

- `_critique` (synthesis.py) как образец tolerant fence-stripping: сам подход (strip ` ```json ` fence → `json.loads` → fallback) КОРРЕКТЕН для нового JSON-парса в topics.py. Проблема только в том, что нужен отдельный tolerant-парсер для `{}` (объект), а не `[]` (массив) — см. пункт 2 выше.
- PII-контракт: план корректно описывает, что в topic_label.md идут только тексты, и что в digest_synthesis.md `[@N]` запрет в блоке тем сохраняется. Код это подтверждает — `_group_by_author` + `humanize_author_refs` цепочка не затрагивается.
- `delivery/cli.py`: шаг 1 и 2 НЕ требуют изменений в cli.py. Проверено — `build_topics_digest` вызывает `render_topics(header, topics)`, а `build_digest` вызывает `synthesize_and_save`. Оба пути правятся в правильных местах.
- `max_tokens=30` — план корректно идентифицирует это значение в topics.py строка 139 и предписывает поднять до ~120. Значение совпадает с реальным кодом.
