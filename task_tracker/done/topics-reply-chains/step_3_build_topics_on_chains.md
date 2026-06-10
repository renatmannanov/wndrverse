# Шаг 3: build_topics кластеризует документы

> Зависит от: шаг 1, шаг 2
> Статус: [x] done (2026-06-10)

## Задача

### 3.1 hotness.py: статистика по документам

Добавить в `core/brain/hotness.py` чистую функцию (existing `cluster_stats`
НЕ трогать — её юниты остаются):

```python
def chain_cluster_stats(documents: list[dict]) -> dict:
    """Агрегаты кластера из документов-тредов (build_chains contract).

    msgs    = sum(len(d['substantive']))        # решение: только содержательные
    likes   = sum(likes_of(m['reactions']) for d in documents
                  for m in d['messages'])        # ВСЕ сообщения — реакции дают вклад
    authors = unique sender_id (not None) по ВСЕМ messages всех документов
    """
```

Юниты на `chain_cluster_stats` — в `tests/test_hotness.py` (рядом с
существующими тестами `cluster_stats`): msgs не включает реакции, likes
включает лайки реакций, authors по всем сообщениям, пустые reactions/None.

### 3.2 topics.py: конвейер на документах

Переписать тело `build_topics` (сигнатура, параметры, возвращаемый контракт
`[{name, msgs, anchor_channel_id, anchor_external_id}]` — НЕ меняются):

1. Layer 1 теперь живёт внутри `build_chains` (substantive-фильтр):
   `docs = build_chains(fragments, min_chars=min_chars)`.
   УДАЛИТЬ конкретно: list-comprehension `kept = [f for f in fragments if
   len(f.get('text') or '') >= min_chars and _is_substantive(f['text'])]`
   и её лог-строку «после flood-filter» (topics.py, тело build_topics,
   секция «Layer 1»). Определения `_is_substantive`/`_WORD_RE` уже уехали
   в chains.py шагом 2 — здесь их НЕ трогать.
2. `if len(docs) < min_cluster_size: return []` (как раньше с kept).
3. `labels, probs = cluster_embeddings([d['embedding'] for d in docs],
   min_cluster_size=min_cluster_size)` — кластеризуем документы.
4. Группировка по label: skip -1 и probs < min_probability; член кластера =
   `{**doc, 'probability': p}` (копия, как в ab6af26).
5. Stats: `chain_cluster_stats(members)`; `min_authors` — по stats как раньше.
6. Анкор: самый ранний КРЕПКИЙ документ (probability >= ANCHOR_MIN_PROBABILITY,
   fallback все), ранний = по `root['created_at']`; анкор-сообщение =
   `doc['root']` → его channel_id/external_id. Комментарий про перенос логики
   ab6af26 на документы обновить, константу переиспользовать.
7. Ранжирование/maxes/score — без изменений (числа теперь от chain_cluster_stats).
8. LLM-сэмплы для названия: substantive-сообщения ВСЕХ документов кластера,
   flatten + sort by created_at, каждый ~(len/5)-й, максимум 5 — та же схема
   шага равномерного сэмплинга, что сейчас, только по flatten-списку.
   ВНИМАНИЕ: текущий код читает `f['text']` у членов кластера — у ДОКУМЕНТА
   поля `text` НЕТ. Заменить источник:
   `flat = sorted((m for d in c['members'] for m in d['substantive']),
   key=lambda m: m['created_at'])` и сэмплировать из `flat` (тексты —
   `m['text']`). В промпт уходят ТОЛЬКО тексты (PII-инвариант не трогается).

### 3.3 Лог

В лог build_topics добавить число документов:
`"build_topics: %d fragments → %d docs after chains (min_chars=%d)"`
(заменяет старую строку про flood-filter — сообщение одно, не два).

## Тесты

`tests/test_topics_build.py` — обновить под документы + добавить:
- Существующие тесты (two_clusters_ranked, monologue_dropped, anchor_skips_
  loose, anchor_falls_back) должны пройти БЕЗ изменения своих фрагментов:
  их синтетические сообщения не имеют reply_to/серий (разные sender'ы или
  большие разрывы) → каждый документ = одно сообщение, поведение эквивалентно.
  Если у _frag нет полей msg_id/reply_to_msg_id — build_chains обязан
  переживать их отсутствие (`f.get(...)`) — проверяется именно здесь.
- НОВЫЙ тест: серия длинное+2 реакции-reply (короткие, с лайками) + второй
  отдельный кластер. Проверить: msgs темы НЕ включает реакции; likes включает
  лайки реакций; anchor = root серии.
- НОВЫЙ тест: два разговора с разными reply-деревьями, но «реакционными»
  текстами одинаковой лексики — раньше слипались бы, теперь каждый документ
  несёт эмбеддинг содержательного корня. (Синтетика: вектора корней далеко,
  вектора реакций между ними; проверить 2 темы, не 1.)

Что может сломаться: test_topics_command.py / test_topics_render.py /
test_hotness.py (likes_of, cluster_stats не трогаем) — прогнать всё.

## Команды для верификации

```bash
PYTHONUTF8=1 python -m pytest tests/test_topics_build.py tests/test_hotness.py -q
PYTHONUTF8=1 python -m pytest tests/ -q
# контракт CLI не сломан (формат тот же; состав тем оценивается в шаге 4)
PYTHONUTF8=1 python -m delivery topics --topic boltalka --period 1m --limit 3
```

## Критерии готовности

- [ ] `build_topics` принимает/возвращает ТО ЖЕ, что до шага (контракт).
- [ ] msgs = содержательные; likes — со вкладом реакций (юнит).
- [ ] Анкор = root самого раннего крепкого документа (юнит).
- [ ] Все существующие тесты зелёные без правки их данных.
- [ ] `python -m pytest tests/ -q` — все зелёные.
