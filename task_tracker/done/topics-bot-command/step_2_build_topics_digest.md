# Шаг 2: Core-функция build_topics_digest (shared бот+CLI)

> Зависит от: нет (но логически парный к шагу 1)
> Статус: [x] done

## Задача

В `delivery/cli.py` вынести core-функцию `build_topics_digest` по образцу
существующей `build_digest` — единый путь сборки hot-topics дайджеста, который
переиспользуют И бот (шаг 3), И CLI (`_run_topics`). Сейчас вся логика сидит
внутри `_run_topics`; выносим её в чистую функцию, возвращающую СТРУКТУРУ (не
печать), чтобы бот мог взять `result['text']` и отправить в DM.

```python
def build_topics_digest(
    topic_arg: str,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int | None = None,
) -> dict | None:
    """Core: store → build_topics → render_topics → return result (NO sending).

    The single shared hot-topics path used by BOTH the CLI `topics` subcommand
    and the bot's /topics command. The caller picks the channel.

    Returns {'text': str, 'found': int} where `found` = number of embedded
    fragments the period had (BEFORE flood-filter). Returns None if there were
    0 fragments (caller skips OpenAI spend — build_topics never runs). Also
    returns a result with an explanatory text (found>0 but 0 topics) — see below.

    until is the UPPER bound EXCLUSIVE (see get_embedded_fragments_for_period).
    'all' topic is rejected (variant A is single-topic) — raises ValueError.
    """
```

Реализация (перенести из текущего `_run_topics`, адаптировать):
1. Если `topic_arg == "all"` → `raise ValueError("topics поддерживает только ОДИН
   топик (вариант А), не 'all'")`. (В CLI это было SystemExit; теперь ValueError,
   а `_run_topics` и бот ловят и показывают дружелюбно. Правило #1 — один путь
   обработки ошибки в core, представление — на вызывающем.)
2. `header = _digest_header(topic_arg, since, until)` (переиспользуем как есть).
   ⚠️ ПОРЯДОК ВАЖЕН: header строится ОДИН раз ДО шага 4 (`if not frags`), потому
   что он нужен в ветке п.6 (found>0, 0 тем). Если поставить header после
   `return None` — будет NameError в ветке «0 тем». НЕ переставлять.
3. `frags = get_embedded_fragments_for_period(topic_arg, since=since, until=until)`.
4. `if not frags: return None` (0 фрагментов — без спенда).
5. `topics = build_topics(frags, limit=limit)`.
6. `if not topics:` вернуть результат с пояснительным текстом, НЕ None:
   `return {'text': f"{header}\n\nЗа период тем не найдено (всё отсеяно как
   флуд/шум).", 'found': len(frags)}`. (found>0, но темы отсеяны фильтром —
   это НЕ «нет сообщений», caller должен показать пояснение, а не «нет».)
7. `text = render_topics(header, topics)`;
   `return {'text': text, 'found': len(frags)}`.

Рефактор `_run_topics` → тонкая обёртка. CLI `parse_period` НЕ даёт верхнюю
границу, поэтому `until` всегда None — фиксируем `until=None` в одной переменной
и переиспользуем её и в core-вызове, и в заголовке ветки «0 фрагментов» (не
хардкодим None дважды):
```python
def _run_topics(topic_arg, period, channel, limit):
    since = parse_period(period)
    until = None                       # CLI period has no upper bound
    try:
        result = build_topics_digest(topic_arg, since=since, until=until, limit=limit)
    except ValueError as e:
        raise SystemExit(str(e))       # CLI-представление ошибки 'all'
    if result is None:
        channels.send(f"{_digest_header(topic_arg, since, until)}\n\n"
                      "За период сообщений не найдено.", channel=channel)
        return 0
    channels.send(result['text'], channel=channel)
    return 0
```

ВАЖНО:
- НЕ менять `build_digest`, `_run_digest`, парсер `digest`, `humanize_*`.
- `_run_topics` сохраняет ТО ЖЕ внешнее поведение (CLI-вывод не меняется):
  0 фрагментов → «сообщений не найдено», 0 тем → «тем не найдено», 'all' →
  понятная ошибка. Проверяется тем, что команды CLI из прошлого плана работают.
- Импорты уже есть (get_embedded_fragments_for_period, build_topics,
  render_topics) — добавлены в прошлом плане.

## Тесты

- Юнит не обязателен (склейка), но поведение `_run_topics` проверяется
  существующими CLI-командами (они должны давать тот же вывод).
- Что может сломаться: CLI `topics` (рефакторнули _run_topics) и `digest`
  (не трогаем, но проверить отдельно).

## Команды для верификации

```bash
# CLI topics работает как раньше (тот же формат)
PYTHONUTF8=1 python -m delivery topics --topic boltalka --period 1m --limit 3

# build_topics_digest как функция отдаёт структуру
PYTHONUTF8=1 python -c "
from dotenv import load_dotenv; load_dotenv()
from delivery.cli import build_topics_digest
from datetime import datetime
r = build_topics_digest('boltalka', datetime(2026,5,1), datetime(2026,6,1), limit=3)
print('keys:', sorted(r.keys()))
print('found:', r['found'])
print(r['text'][:200])
"
# 'all' -> ValueError из core
PYTHONUTF8=1 python -c "
from dotenv import load_dotenv; load_dotenv()
from delivery.cli import build_topics_digest
try:
    build_topics_digest('all')
except ValueError as e:
    print('ValueError ok:', e)
"
# 'all' через CLI -> понятная ошибка (SystemExit), не трейсбек
PYTHONUTF8=1 python -m delivery topics --topic all --period 1m; echo "exit=$?"

# digest НЕ сломан
PYTHONUTF8=1 python -m delivery digest --topic offerings --period 1w | head -3
```

## Критерии готовности

- [x] `build_topics_digest` возвращает `{'text','found'}` или None (0 фрагментов).
- [x] found>0 но 0 тем → result с пояснительным текстом (НЕ None).
- [x] `'all'` топик → ValueError из core; CLI ловит → SystemExit с сообщением.
- [x] `python -m delivery topics --topic boltalka --period 1m` даёт ТОТ ЖЕ вывод,
      что до рефактора (эмодзи + темы + ссылки).
- [x] `python -m delivery digest --topic offerings --period 1w` не сломан.
