# Step 6: Завершение плана

> Статус: done

## Чеклист

- [x] Все шаги плана выполнены ([x] в PLAN.md)
- [x] Критерии готовности из PLAN.md проверены (тесты + golden-прогон на реальной БД)
- [x] Smoke test: `python -m delivery digest --topic questions_to_women --period 1m` —
      дайджест без обрывов, блоки на месте, имена подставлены, голых [@N] нет,
      безличные формы соблюдены (см. вывод в сессии 2026-06-18)
- [x] Не сломано: `pytest tests/ -q` → 176 passed
- [x] ПРОЕКТНЫЙ CLAUDE.md обновлён: блок «Digest output quality» (gpt-4o Pass-2,
      критик Pass-3 за флагом, min_chars=80 + caveat, max_tokens guard, golden set)
      + env `WNDR_SYNTHESIS_MODEL` / `WNDR_DIGEST_CRITIC`
- [x] Известное ограничение (is_duplicate отстаёт до 6ч) задокументировано в CLAUDE.md
- [x] Мусор убран (снапшоты в tests/golden/snapshots/ — gitignored, не в git;
      baseline-файлы локальные)
- [x] Статус в PLAN.md → done
- [x] Папка перемещена: todo/ → done/digest-output-quality/

## Итог (2026-06-18)

Коммиты на ветке `feature/digest-output-quality`:
- 68a08f7 golden-каркас (snapshot-режим)
- d3e0435 max_tokens 3200 + truncation guard
- 5a9c642 Pass-2 gpt-4o из env WNDR_SYNTHESIS_MODEL
- 537791d min_chars 150→80
- 0fc4c80 self-критик за флагом WNDR_DIGEST_CRITIC
- 7a4226c реальные golden-кейсы
- 754cea2 fix критика: терпимый JSON-парсер (```json-fence)

Главные находки (подробно — progress.md «Learnings»): min_chars 80 поднял
объём (women 73→98, requests 33→60), НО для крупных топиков (offerings 114→202)
перекинул через порог Pass-1 и УКОРОТИЛ вывод — пересмотр
MAX_FRAGMENTS_WITHOUT_SELECTION = будущая задача. Критик находит дефекты, но
шумит (false positives на [@N]) — поэтому ВЫКЛ по умолчанию.

## НЕ сделано осознанно (вне scope / решения для пользователя)
- Merge `feature/digest-output-quality` → master НЕ сделан (ждёт решения).
- Деплой на VPS НЕ сделан (по отдельной команде, как обычно).
- Пересмотр порога Pass-1 селекции — отдельная задача (см. progress.md #2).
- Доработка промпта критика (меньше false positives) — будущее.

## Smoke-проверка вывода (главный критерий — качество саммари)

```bash
# на реальном кейсе глазами оценить: блоки на месте, нет обрыва, имена подставлены,
# нет голых [@N], в логах виден (или нет) warning критика
python -m delivery digest --topic questions_to_women --period 1m
```
