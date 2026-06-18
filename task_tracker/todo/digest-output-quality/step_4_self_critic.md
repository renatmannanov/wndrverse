# Шаг 4: Self-критик (Pass-3) — валидатор дефектов

> Зависит от: шаг 2 (использует COMPLETION_MODEL_SYNTHESIS)
> Статус: [ ] pending

## Задача

Добавить ТРЕТИЙ LLM-проход после синтеза: критик проверяет готовый дайджест
против исходных сообщений и ВОЗВРАЩАЕТ СПИСОК ДЕФЕКТОВ. Текст НЕ переписывает
(решено: режим «валидатор»). Дефекты логируются warning'ом.

### Включение — за флагом, по умолчанию ВЫКЛ (решено 2026-06-18)
Критик стоит +1 вызова синтез-модели (gpt-4o) на каждый дайджест, а в режиме
валидатора только пишет warning в лог. Поэтому он ВЫКЛючен по умолчанию и
включается через env-флаг `WNDR_DIGEST_CRITIC` (truthy: `1`/`true`/`yes`,
регистр игнор). Когда выключен — `_critique` НЕ вызывается, `result['critic_issues']`
= `[]` (поле есть всегда, для стабильной формы результата и golden-раннера).
Включают флаг при golden-прогонах и отладке качества, не в обычном проде.
Проверку флага оформить чистым хелпером `_critic_enabled() -> bool`
(`os.getenv` внутри), тестируемым через monkeypatch env.

### Что ловит критик
- Обрезанная фраза в конце (обрыв на полуслове).
- Приписан тезис не тому `[@N]` (путаница «кто что»).
- Выдуманный факт, которого нет в исходных сообщениях.
- `[@N]`, которого НЕ было во входе (приведёт к голому «[@7]» в выводе).
- Родовые формы прошедшего времени («предложил/выбрала») — промпт их запрещает.

### PII-контракт (КРИТИЧНО — ОДИН путь, без вариантов)
Критик получает РОВНО две переменные из `synthesize`, обе на момент ПОСЛЕ Pass-2
и ДО подстановки имён:
- `content` — результат `_synthesize_fragments` (строка ~120 в текущем коде),
  ещё в `[@N]`-форме. ВАЖНО: НЕ передавать сюда humanized-текст
  (`humanize_author_refs` вызывается ПОЗЖЕ, уже в `delivery/cli.build_digest`, не
  в `synthesize`) — в `synthesize` имён нет вообще, но это нужно держать в голове.
- `grouped_text` — вход Pass-2 из `_group_by_author` (строка ~115), тоже `[@N]`,
  без имён (имена живут только в `author_refs`, отдельной переменной — её критику
  НЕ передавать).

Вызов строго: `_critique(content, grouped_text)`. НИ author_name, НИ username, НИ
`author_refs`, НИ display-имена в OpenAI не уходят. Нарушать нельзя. Тест на
отсутствие имён в prompt критика — обязателен (см. ниже).

### Реализация
1. Новый промпт `core/prompts/digest_critic.md`:
   - Вход: `{digest}` (готовый `[@N]`-дайджест) + `{sources}` (тот же `grouped_text`).
   - Инструкция: найти перечисленные выше дефекты. Вернуть СТРОГО JSON-массив
     строк-описаний (пустой `[]` если дефектов нет). Без пояснений вокруг.
   - Подчеркнуть: участники — это `[@N]`, имён нет и быть не должно; не выдумывать.

2a. `core/brain/synthesis.py` — добавить `import json` вверху модуля (рядом с
   `import os`, `import logging`). Сейчас `json` НЕ импортирован, а `_critique`
   зовёт `json.loads()` → без импорта будет `NameError`.

2b. `core/brain/synthesis.py` — новая функция `_critique(digest: str, grouped_text: str) -> list[str]`:
   - Грузит промпт, зовёт `complete(prompt, model=COMPLETION_MODEL_SYNTHESIS, temperature=0.0)`.
   - Парсит JSON-массив строк терпимо (как `_select_fragments` терпим к формату):
     `json.loads`; при ошибке парсинга — вернуть `[]` и `logger.warning` («critic
     output unparseable») — критик НЕ должен ронять дайджест.
   - Возвращает список строк-дефектов.

3. Встроить в `synthesize` точно в слот МЕЖДУ строкой ~120
   (`content = _synthesize_fragments(...)`) и строкой ~122 (формирование
   `result = {...}`). На этот момент `content` и `grouped_text` существуют и оба
   `[@N]`. Код:
   - `defects = _critique(content, grouped_text) if _critic_enabled() else []`
     — когда флаг ВЫКЛ, `_critique` не зовётся вообще (нет вызова OpenAI).
   - Если непусто: `logger.warning("digest critic found %d issue(s) on '%s': %s",
     len(defects), topic, defects)`.
   - Добавить в возвращаемый `result` поле `'critic_issues': defects` (всегда,
     даже при ВЫКЛ флаге — тогда `[]`, форма результата стабильна).
   - Текст `content` НЕ менять.

4. Ветка `< 3 fragments` — НИЧЕГО не добавлять. Это ранний `return` в начале
   `synthesize` (строки ~93–96, ветка `_insufficient_data_message`), он
   возвращается ДО Pass-2 и до слота вставки критика → критик туда физически не
   попадёт. Отдельной защиты/флага НЕ нужно. (Просто не вставляй вызов критика
   выше этого return.)

5. Проброс `critic_issues` до golden-раннера (решено ОДНОЗНАЧНО, не опционально):
   `delivery/cli.py` → `build_digest` уже читает `result` из `synthesize_and_save`.
   Добавить в возвращаемый dict `build_digest` поле:
   `'critic_issues': result.get('critic_issues', [])`. Это единственная правка в
   cli.py для этого шага. Раннер (шаг 5) затем читает его из результата.
   `_run_digest` и bot-хендлеры это поле игнорируют — менять их НЕ нужно.

### Цена / поведение
- +1 вызов синтез-модели (gpt-4o) на каждый дайджест — ТОЛЬКО когда
  `WNDR_DIGEST_CRITIC` truthy. По умолчанию ВЫКЛ → 0 доп. вызовов в обычном проде.
- Ошибка критика (сеть/парсинг) НЕ ломает дайджест — fail-soft, пустой список.

## Тесты

`tests/test_critic.py` (DB-free; OpenAI замокан):
- `_critic_enabled()`: с monkeypatch env `WNDR_DIGEST_CRITIC=1` → True;
  без переменной / `0` / пусто → False.
- `synthesize` с ВЫКЛ флагом (env не задан): `_critique` НЕ вызван
  (подменить `_critique` на счётчик/raise), `result['critic_issues'] == []`.
- `_critique` с monkeypatch `complete` → возвращает `'["обрыв в конце", "выдуман [@9]"]'`:
  результат == список из 2 строк.
- `complete` вернул мусор (`'не json'`) → `_critique` возвращает `[]`, не падает.
- `complete` вернул `'[]'` → `[]`.
- PII: подменить `complete` на захват prompt; убедиться, что в prompt критика
  НЕТ строк-имён (передать grouped_text вида `[@1]:\nтекст`, проверить отсутствие
  любого реального имени — например прогнать через `_group_by_author` и убедиться,
  что refs-имена не попали в prompt).
- `synthesize` с замоканными `_select_fragments`/`complete`: при дефектах в
  result есть `'critic_issues'` непустой, а `content` не изменён критиком.

Что может сломаться:
- `tests/test_group_by_author.py::test_synthesize_and_save_keeps_author_refs` —
  там `synthesize` замокан ЦЕЛИКОМ, критик не вызовется. ОК.
- Любой тест, реально доходящий до `_synthesize_fragments` без мока `complete`,
  теперь словит лишний вызов критика. Grep: таких в репо нет (синтез всегда
  мокается), но проверить `grep -rn "_synthesize_fragments\|synthesize(" tests/`.

## Команды для верификации

```bash
cd c:/Users/renat/projects/wndrverse
ls core/prompts/digest_critic.md
python -c "from core.brain.synthesis import _critique; print(callable(_critique))"
pytest tests/test_critic.py -q
pytest tests/ -q
```

## Критерии готовности

- [ ] `import json` добавлен в `core/brain/synthesis.py`.
- [ ] `core/prompts/digest_critic.md` существует, просит строгий JSON-массив строк.
- [ ] `_critic_enabled()` читает `WNDR_DIGEST_CRITIC` (truthy → True, иначе False).
- [ ] `_critique(content, grouped_text)` зовёт синтез-модель (COMPLETION_MODEL_SYNTHESIS),
      temperature 0.0, терпим к мусору (возвращает [] + warning).
- [ ] `synthesize` кладёт `result['critic_issues']` (всегда; `[]` при ВЫКЛ флаге),
      логирует warning при дефектах, `content` не меняет, критик не зовётся в `<3`
      ветке (он ниже раннего return) И не зовётся при ВЫКЛ флаге (нет OpenAI-вызова).
- [ ] `build_digest` (delivery/cli.py) прокидывает `'critic_issues'` в свой результат.
- [ ] PII-тест: имён в prompt критика нет (передан только [@N]-текст).
- [ ] `pytest tests/ -q` зелёный.
