# Шаг 1: Группировка по автору + ссылки [@N] + подстановка

> Зависит от: нет
> Статус: [ ] pending

## Задача

Перевести синтез с `[#id]` (по сообщению) на `[@N]` (по автору) и группировать
вход для Pass 2 по автору. Подстановку имён сделать по `[@N]`.

### 1. Группировка в `_synthesize_fragments` (core/brain/synthesis.py)

Заменить построение `fragments_text` на группировку по автору.

```python
def _author_key(f: dict):
    """Stable per-author key: sender_id if present, else author_name, else anon."""
    if f.get('sender_id') is not None:
        return ('id', f['sender_id'])
    if f.get('author_name'):
        return ('name', f['author_name'])
    return ('anon', f['id'])  # each anon message its own "author"

def _group_by_author(fragments: list[dict]) -> tuple[str, dict[int, str]]:
    """Group fragments by author (date order preserved).

    Returns (grouped_text, author_refs) where:
      grouped_text feeds the LLM: each author is one [@N] block with all texts,
        NO names — PII never leaves.
      author_refs maps N -> display name (from DB), for local substitution later.
    """
    order: list = []                 # author keys in first-seen order
    by_key: dict = {}                # key -> {'name': str, 'texts': [str]}
    for f in sorted(fragments, key=lambda x: x['created_at'] or ''):
        k = _author_key(f)
        if k not in by_key:
            order.append(k)
            name = f.get('author_name') or 'аноним'
            if f.get('sender_id') is None and not f.get('author_name'):
                name = 'аноним'
            by_key[k] = {'name': name, 'texts': []}
        by_key[k]['texts'].append(f['text'])

    blocks, author_refs = [], {}
    for n, k in enumerate(order, start=1):
        author_refs[n] = by_key[k]['name']
        texts = by_key[k]['texts']
        joined = "\n---\n".join(texts)
        head = f"[@{n}] ({len(texts)} сообщ.):" if len(texts) > 1 else f"[@{n}]:"
        blocks.append(f"{head}\n{joined}")
    return "\n\n".join(blocks), author_refs
```

Разделение ответственности (ФИКСИРОВАНО, без вариантов):
- `synthesize()` зовёт `_group_by_author(selected)` → `(grouped_text, author_refs)`,
  кладёт `author_refs` в результат.
- `_synthesize_fragments(topic, topic_hint, grouped_text)` принимает УЖЕ
  сгруппированный текст (новая сигнатура — третий аргумент `grouped_text`, не
  `fragments`). Группировку сам НЕ делает.

В `synthesize()`:
```python
grouped_text, author_refs = _group_by_author(selected)
content = _synthesize_fragments(topic, topic_hint, grouped_text)
result = {
    'content': content,
    'fragment_ids': [f['id'] for f in selected],
    'author_refs': author_refs,           # NEW: {N: name}
    'found': found,
    'model': COMPLETION_MODEL,
}
```
Ветку `< 3` (insufficient) вернуть с `author_refs: {}` (пустой).
ФИКСИРОВАНО: переписать `_insufficient_data_message` так, чтобы оно НЕ
использовало `[#id]`-ссылки (иначе после переключения на `humanize_author_refs`
они останутся сырыми). Заменить `[#{f['id']}]` на имя автора прямо из БД:
`name = f.get('author_name') or 'аноним'` (sender_id is None → 'аноним'),
формат строки: `• [{name}] {text[:150]}`. Тогда ветка <3 не зависит от
подстановки вообще.

`_synthesize_fragments`:
```python
def _synthesize_fragments(topic, topic_hint, grouped_text: str) -> str:
    prompt = _load_prompt("digest_synthesis.md").format(
        topic=topic, topic_hint=topic_hint, fragments_text=grouped_text)
    return complete(prompt, temperature=0.4, max_tokens=2200)   # 0.2 -> 0.4
```

### 2. Подстановка [@N] → [Имя] (delivery/cli.py)

Добавить НОВУЮ функцию (не трогая `humanize_refs`, она остаётся для совместимости):
```python
_AUTHOR_REF_RE = re.compile(r"\[@(\d+)\]")

def humanize_author_refs(content: str, author_refs: dict) -> str:
    """Replace [@N] with [name] from author_refs (names come from our DB, not LLM).

    Unknown N left as-is. No date — an author spans several messages.
    """
    def repl(m):
        n = int(m.group(1))
        name = author_refs.get(n) or author_refs.get(str(n))
        return f"[{name}]" if name else m.group(0)
    return _AUTHOR_REF_RE.sub(repl, content)
```
⚠️ `author_refs` ключи — int (из synthesize). Подстраховка `.get(str(n))` на случай
сериализации.

⚠️⚠️ В `build_digest` ОБЯЗАТЕЛЬНО **УДАЛИТЬ** старую строку
`text = humanize_refs(result['content'], result['fragment_ids'])` и поставить
ВМЕСТО неё:
```python
result = synthesize_and_save(topic_arg, fragments, topic_type=topic_type)
text = humanize_author_refs(result['content'], result.get('author_refs', {}))
```
НЕ оставлять оба вызова. `humanize_refs` (старая, `_REF_RE = \[?#?(\d+)\]?`) НЕ
должна прогоняться по `[@N]`-тексту: её регэксп матчит цифру внутри `[@N]` и
испортит вывод. Новая `humanize_author_refs` использует `_AUTHOR_REF_RE =
\[@(\d+)\]`, который матчит только `[@N]` и не пересекается с `[#id]`.

### 3. `synthesize_and_save` — пробросить author_refs

`synthesize_and_save` сейчас зовёт `synthesize` и добавляет `artifact_id`. Оно
возвращает тот же dict (`result = synthesize(...); result['artifact_id'] = ...;
return result`), поэтому `author_refs` пробрасывается автоматически. ПРОВЕРИТЬ
явно тестом (см. ниже), что ключ `author_refs` присутствует в возврате.

### 4. PII в логах (КРИТИЧНО)

`author_refs` содержит РЕАЛЬНЫЕ имена. PII-правило: имена не должны утекать.
- НЕ логировать `author_refs` и НЕ логировать `result` целиком ни в `synthesize`,
  ни в `synthesize_and_save`, ни в `build_digest` (даже на DEBUG).
- Проверить существующие `logger.*` в этих функциях: если где-то логируется весь
  dict результата — убрать имена/author_refs из лога. Логи на VPS (journalctl)
  не должны содержать имён.

## Тесты

`tests/` — без реального OpenAI/Telegram (мокать `complete`):
- `_group_by_author`: 3 фрагмента одного автора (один sender_id) → один `[@1]`
  блок с 3 текстами; `author_refs == {1: 'Имя'}`.
- 2 автора → `[@1]`, `[@2]`, порядок по дате первого сообщения.
- аноним (sender_id=None, author_name=None) → `'аноним'`.
- PII: в `grouped_text` НЕТ ни одного `author_name` (проверить `assert name not in text`).
- `humanize_author_refs`: `[@1][@2]` → `[Имя1][Имя2]`; неизвестный `[@9]` не тронут;
  даты нет (`assert ',' not in result` для подставленного имени-блока, аккуратно).
- `build_digest` (ОБЯЗАТЕЛЬНЫЙ тест; мок synthesize_and_save, возвращающий content
  c `[@1][@2]` + `author_refs={1:'Имя1',2:'Имя2'}`) → `result['text']` содержит
  `[Имя1]` и `[Имя2]`, НЕ содержит `[@1]`/`[@2]`. И `humanize_refs` НЕ вызывается.
- `synthesize_and_save` пробрасывает `author_refs`: мок `synthesize` →
  `synthesize_and_save` результат содержит ключ `author_refs` (не теряется).
- `_insufficient_data_message` (<3 фрагментов): результат содержит имя автора,
  НЕ содержит `[#` / `[@` (ветка не зависит от подстановки).

## Команды для верификации

```bash
pytest tests/ -q
# локальный реальный прогон (БД поднята, тратит ~$0.002 OpenAI):
python -c "from delivery.cli import build_digest, parse_date_range; \
  s,u=parse_date_range('2026-05-16','2026-05-31'); r=build_digest('commits',s,u); \
  print(r['text'])"
# проверить глазами: в «КТО ЧТО» каждое имя один раз, нет [@N] в выводе.
```

## Критерии готовности

- [ ] `_group_by_author` группирует по автору, возвращает `(grouped_text, author_refs)`.
- [ ] В `grouped_text` нет имён (PII); только `[@N]` + тексты.
- [ ] `synthesize` кладёт `author_refs` в результат; temperature синтеза 0.4.
- [ ] `humanize_author_refs` подставляет `[@N] → [Имя]` без даты.
- [ ] `build_digest` использует новый путь (старый `humanize_refs`-вызов УДАЛЁН);
      в выводе нет `[@N]`, имена не дублируются.
- [ ] PII: `author_refs`/`result` не логируются (имён нет в journalctl).
- [ ] `_insufficient_data_message` не использует `[#id]` (ветка <3 самодостаточна).
- [ ] `pytest tests/ -q` зелёный; scheduler не сломан (build_digest контракт цел).
