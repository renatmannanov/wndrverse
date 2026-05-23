# Backlog: Переезд curator/ в agents/curator/

> Status: backlog
> Дата: 2026-05-23
> Связано с: `task_tracker/todo/community-brain-mvp/` (ядро core/)

## Контекст

При проектировании community-brain MVP решили структуру репозитория:

```
wndrverse/
├── core/        ← ядро (ingest/enrich/brain), осмысляет сообщения
├── delivery/    ← вывод (CLI → tg группа/личка)
└── agents/      ← потребители ядра (curator, claude)
```

Сейчас `curator/` лежит в корне репозитория. По новой логике curator — это
**потребитель** данных ядра (берёт готовые дайджесты/мэтчи и постит), а не само
ядро. Логичное место — `agents/curator/`, рядом с `agents/claude/`.

## Почему не сейчас

- curator/ — рабочий код, трогать его в рамках задачи про дайджест незачем
- MVP ядра (core/ + delivery/) не зависит от расположения curator/
- Переезд = чистый рефактор импортов/путей, делается отдельным коммитом без риска

## Что сделать

1. Переместить `curator/` → `agents/curator/`
2. Обновить импорты и пути в коде (bus.py, reader.py, showcase.py, prompts/)
3. Обновить ссылки в `CLAUDE.md` (секция Commands: `python curator/main.py` →
   `python agents/curator/main.py`)
4. Проверить что существующие запуски/тесты не сломались (`test_stand.py`)

## Критерий готовности

- `curator/` больше нет в корне, код живёт в `agents/curator/`
- `python -m ...` (актуальная команда запуска куратора) работает из нового места
- CLAUDE.md обновлён
