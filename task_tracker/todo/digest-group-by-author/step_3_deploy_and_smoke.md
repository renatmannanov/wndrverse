# Шаг 3: Деплой на VPS + прод-smoke

> Зависит от: шаги 1-2 (код+промпт готовы, тесты зелёные локально)
> Статус: [ ] pending

## Задача

Выкатить фичу на прод, перезапустить ingest-бот, прогнать реальную команду.

### 0. Pre-merge gate (на feature-ветке, ДО слияния)
Прод-smoke требует задеплоенного кода, поэтому ПЕРЕД merge снижаем риск локально:
- `pytest tests/ -q` зелёный;
- локальный реальный прогон из step_1/step_2 (`build_digest('commits', …)`)
  проверен ГЛАЗАМИ: «КТО ЧТО» по автору, имена не дублируются, нет `[@N]`, PII ок.
Только если это прошло — идём к merge.

### 1. Влить и запушить
⛔ **СТОП-ТОЧКА:** НЕ выполнять merge/push БЕЗ явного подтверждения владельца
(«да/давай/го»). Это правка прод-ветки master. Дождись слова.
```bash
# только после подтверждения владельца:
git checkout master && git merge --no-ff feature/digest-group-by-author \
  -m "Merge feature/digest-group-by-author: КТО ЧТО grouped by author"
pytest tests/ -q          # зелёный на master
git push origin master
```
Откат, если прод-smoke (п.4) провалится: `git revert` merge-коммита на master +
push + VPS `git pull` + restart (возврат к предыдущему поведению). Зафиксировать
в progress.md, что именно не так, прежде чем откатывать.

### 2. Обновить код на VPS
```bash
ssh -i ~/.ssh/openclaw_hetzner rm_agent@62.238.31.95
cd ~/wndrverse
git pull origin master
git log --oneline -1               # новый merge-коммит
```
Env НЕ меняется (новых переменных нет).

### 3. Перезапустить ingest-бот (подхватит новый код)
```bash
sudo systemctl restart wndr-ingest-bot
sleep 2 && systemctl is-active wndr-ingest-bot          # active
journalctl -u wndr-ingest-bot -n 20 --no-pager -q | grep -iE "whitelist|started|error"
```

### 4. Прод-smoke реальной командой (СТОП-ТОЧКА: трата OpenAI)
Владелец в ЛС бота от вайт-лист аккаунта:
```
/summary commits 2026-05-16 2026-05-31
```
Проверить:
- блок «КТО ЧТО»: одна строка на участника, имена НЕ повторяются;
- текст живее (не шаблонные повторы);
- безличные формы, нет «предложил/предложила»;
- PII локальная (имена есть, но в OpenAI не уходили);
- нет сырых `[@N]`;
- длина ≤ 4096.

## Команды для верификации

```bash
sudo systemctl is-active wndr-ingest-bot
journalctl -u wndr-ingest-bot -n 30 --no-pager -q | grep -iE "summary|error"
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT count(*), count(*)-count(DISTINCT external_id) dup FROM fragments;"
# ingest жив: dup=0, total не упал
```

## Критерии готовности

- [ ] master запушен; VPS на новом коммите; бот перезапущен, active.
- [ ] Реальная `/summary commits 2026-05-16 2026-05-31`: «КТО ЧТО» по автору,
      имена не повторяются, текст живее, нет `[@N]`, PII локальная.
- [ ] Realtime-ingest продолжает писать (dup=0, total не упал).
- [ ] OpenClaw/Hermes не затронуты.
