# Step 9: Завершение плана

> Статус: done

## Чеклист

- [x] Все шаги плана выполнены ([x] в PLAN.md)
- [x] Критерии готовности из PLAN.md проверены (каждый — командой или тестом)
- [x] Smoke test: дайджест работает end-to-end на реальных данных (шаг 8)
- [x] Не сломано: `curator/`, `agent-template/`, `test_stand.py` не затронуты (`git diff master` пуст)
- [x] Нет хардкод-путей к `C:\Users\renat\...` — всё через .env / аргументы (grep пуст)
- [x] Данные сообщества НЕ закоммичены в git (`git ls-files data/` → только .gitkeep)
- [x] В OpenAI не уходили имена (embed шлёт только f['text']; synthesis — [#id]+text, без author_name)
- [x] CLAUDE.md обновлён (секция Commands core/ + структура + Stack)
- [ ] context.md проекта обновлён — не ведётся для wndrverse (живёт у 00_anna; н/п)
- [x] Мусор убран (все _tmp/_digest/_sem скрипты удалены; в репо нет _*.py)
- [x] README обновлён: секция Community Brain (docker compose, пайплайн, privacy, handoff)
- [x] Статус в PLAN.md → done
- [x] Папка перемещена: todo/community-brain-mvp/ → done/community-brain-mvp/

## Передаваемость (проверить отдельно — это требование проекта)

- [x] `docker compose up` + `.env` достаточно чтобы поднять проект с нуля (README «Run it»)
- [x] Инструкция передачи зафиксирована: код = git, данные = отдельный дамп БД (README «Handoff»)
- [x] Нет зависимостей на локальные проекты (ayda/gather) в runtime — весь код перенесён в core/,
      ayda/gather читались только как ИСТОЧНИК при разработке, в импортах их нет (проверено imports OK)
