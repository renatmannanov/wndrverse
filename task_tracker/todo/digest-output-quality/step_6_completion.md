# Step 6: Завершение плана

> Статус: pending

## Чеклист

- [ ] Все шаги плана выполнены ([x] в PLAN.md)
- [ ] Критерии готовности из PLAN.md проверены (каждый — командой или тестом)
- [ ] Smoke test: `build_digest` end-to-end даёт дайджест без обрывов на реальном кейсе
      (через `python -m tests.golden.run` на ≥1 кейсе)
- [ ] Не сломано: `pytest tests/ -q` полностью зелёный
- [ ] ПРОЕКТНЫЙ CLAUDE.md обновлён (`c:\Users\renat\projects\wndrverse\CLAUDE.md`,
      НЕ глобальный): секция про digest-пайплайн — модель gpt-4o для Pass-2,
      критик Pass-3 (за флагом), min_chars=80, max_tokens guard, и про golden set
      (tests/golden/); в секцию «Env vars» добавлены `WNDR_SYNTHESIS_MODEL`
      (дефолт gpt-4o) и `WNDR_DIGEST_CRITIC` (дефолт off)
- [ ] Известное ограничение задокументировано в ПРОЕКТНОМ CLAUDE.md: асинхронный
      дедуп (is_duplicate отстаёт до 6ч, проставляется только в embedder) — НЕ
      чинится этим планом
- [ ] Мусор убран (временные снапшоты вне tests/golden/, пробные файлы)
- [ ] Статус в PLAN.md → done
- [ ] Папка перемещена: todo/digest-output-quality/ → done/digest-output-quality/

## Smoke-проверка вывода (главный критерий — качество саммари)

```bash
# на реальном кейсе глазами оценить: блоки на месте, нет обрыва, имена подставлены,
# нет голых [@N], в логах виден (или нет) warning критика
python -m delivery digest --topic questions_to_women --period 1m
```
