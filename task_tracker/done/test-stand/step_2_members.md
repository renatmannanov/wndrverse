# Step 2: Написать members.json с 3 участниками

> Статус: pending

## Что делаем

Обновить members.json: 3 участника, один источник (iwacado), у каждого свой промпт.

## Формат

```json
{
  "source_channel": "iwacado",
  "members": [
    {
      "name": "Renat",
      "tg_username": "ray_mann",
      "agent_bot": "test_wndr_agentbot",
      "agent_token_env": "AGENT_RENAT_TOKEN",
      "mode": "managed",
      "prompt_file": "curator/prompts/renat.md",
      "interests": ["AI", "агенты", "автоматизация", "vibe-coding", "дети"]
    },
    {
      "name": "Vasya",
      "tg_username": "vasya_test",
      "agent_bot": "wndr_vasya_bot",
      "agent_token_env": "AGENT_VASYA_TOKEN",
      "mode": "managed",
      "prompt_file": "curator/prompts/vasya.md",
      "interests": ["парсинг", "авито", "автоматизация", "Python"]
    },
    {
      "name": "Masha",
      "tg_username": "masha_test",
      "agent_bot": "wndr_masha_bot",
      "agent_token_env": "AGENT_MASHA_TOKEN",
      "mode": "managed",
      "prompt_file": "curator/prompts/masha.md",
      "interests": ["дети", "образование", "AI для детей", "vibe-coding"]
    }
  ]
}
```

## Зависимости

- Шаг 1 (боты созданы, username-ы известны)

## Критерии готовности

```bash
python -c "
import json
with open('members.json') as f:
    data = json.load(f)
assert 'source_channel' in data
assert len(data['members']) == 3
for m in data['members']:
    assert all(k in m for k in ['name','tg_username','agent_bot','agent_token_env','mode','prompt_file','interests'])
print('OK: 3 members, all fields present')
"
```

- [ ] members.json содержит 3 участника
- [ ] Все обязательные поля заполнены
- [ ] source_channel = "iwacado"
