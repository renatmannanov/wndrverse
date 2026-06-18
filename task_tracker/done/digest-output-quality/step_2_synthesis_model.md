# Шаг 2: модель синтеза Pass-2 → gpt-4o (Pass-1 остаётся mini)

> Зависит от: нет (но делать после шага 1 — атомарные коммиты)
> Статус: [x] done

## Задача

Разнести модель ВЫБОРА (Pass-1, выбор id — дёшево, mini хватает) и модель
СИНТЕЗА (Pass-2, качество прозы — нужен gpt-4o).

1. `core/llm/client.py`:
   - Оставить `COMPLETION_MODEL = "gpt-4o-mini"` как есть (дефолт `complete`, селекция).
   - Добавить новую константу, читаемую из env с дефолтом:
     `COMPLETION_MODEL_SYNTHESIS = os.getenv("WNDR_SYNTHESIS_MODEL", "gpt-4o")`.
     (env позволяет A/B без правки кода — например попробовать gpt-4.1; дефолт
     gpt-4o, решено на этапе уточнений 2026-06-18). Убедиться, что `import os`
     в client.py уже есть (если нет — добавить).
   - Прокомментировать: mini = id-выбор/служебное; синтез-модель = пользовательская
     проза дайджеста, настраивается через `WNDR_SYNTHESIS_MODEL`.
   - Pass-1 селекция через env НЕ настраивается — остаётся жёстко на `COMPLETION_MODEL`.

2. `core/brain/synthesis.py`:
   - Импортировать `COMPLETION_MODEL_SYNTHESIS` рядом с `COMPLETION_MODEL`.
   - В `_synthesize_fragments` (Pass-2) передать `model=COMPLETION_MODEL_SYNTHESIS`
     в `complete(...)`.
   - В `_select_fragments` (Pass-1) НИЧЕГО не менять — остаётся на дефолтной
     `COMPLETION_MODEL` (mini).
   - В возвращаемом `result['model']` (в `synthesize`) указывать модель СИНТЕЗА
     (`COMPLETION_MODEL_SYNTHESIS`), т.к. это модель, сформировавшая контент.
     Сейчас там `COMPLETION_MODEL` — поменять на синтез-модель.

Модель синтеза настраивается через env `WNDR_SYNTHESIS_MODEL` (дефолт gpt-4o) —
решено 2026-06-18, чтобы можно было A/B без правки кода. Pass-1 селекция через
env НЕ настраивается.

## Тесты

- `tests/test_synthesis_prompt.py` — не затрагивается (промпт не меняем).
- Новый мини-тест в `tests/test_synthesis_model.py` (DB/OpenAI-free):
  - `from core.llm.client import COMPLETION_MODEL, COMPLETION_MODEL_SYNTHESIS`
  - `assert COMPLETION_MODEL_SYNTHESIS == "gpt-4o"` (дефолт, когда env не задан;
    тест запускать без `WNDR_SYNTHESIS_MODEL` в окружении, либо ассертить
    `os.getenv("WNDR_SYNTHESIS_MODEL", "gpt-4o")` чтобы тест не падал при override).
  - `assert COMPLETION_MODEL == "gpt-4o-mini"` (селекция не деградировала)
  - monkeypatch `synthesis.complete` чтобы захватить kwargs и проверить, что
    `_synthesize_fragments` зовёт его с `model="gpt-4o"`, а `_select_fragments`
    — без явного model (или с дефолтным mini). Захват: подменить `complete`
    на функцию, пишущую вызовы в список, вернуть фейковый текст/ids.

Что может сломаться: код (тесты И прод), читающий `result['model']`. Проверить
перед правкой, что от значения этого поля никто не зависит логикой:
```bash
grep -rn "\['model'\]" core/ delivery/ digest/ bot/ tests/
grep -rn "COMPLETION_MODEL" .
```
Ожидание: `result['model']` нигде не используется для ветвления (только логи/
артефакт). Если найдётся зависимость — обновить её ожидание.

## Команды для верификации

```bash
cd c:/Users/renat/projects/wndrverse
python -c "from core.llm.client import COMPLETION_MODEL, COMPLETION_MODEL_SYNTHESIS as S; print(COMPLETION_MODEL, S)"
# ожидаем: gpt-4o-mini gpt-4o
pytest tests/test_synthesis_model.py -q
pytest tests/ -q
```

## Критерии готовности

- [ ] `COMPLETION_MODEL_SYNTHESIS` читается из `WNDR_SYNTHESIS_MODEL` (дефолт "gpt-4o")
      в client.py; `COMPLETION_MODEL` не тронут.
- [ ] Pass-2 (`_synthesize_fragments`) зовёт `complete(..., model=gpt-4o)`.
- [ ] Pass-1 (`_select_fragments`) НЕ изменён (остаётся mini).
- [ ] `result['model']` = модель синтеза.
- [ ] `pytest tests/ -q` зелёный.
