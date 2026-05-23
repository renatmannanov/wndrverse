"""
Brain — community digest synthesis (two-pass).

Ported from ayda synthesis_service, rewritten for a COMMUNITY digest (not one
person's thought evolution). Prompts live in core/prompts/*.md. LLM via
core.llm.client.complete.

PII: fragments are fed to the LLM as "[#id] (date)\\ntext" — no author_name /
username. The digest comes back with [#id] refs; names are substituted locally
on output (delivery), never sent to OpenAI.
"""

import os
import logging

from core.llm.client import complete, COMPLETION_MODEL
from core.store.fragments_db import save_artifact

logger = logging.getLogger(__name__)

MAX_FRAGMENTS_WITHOUT_SELECTION = 30   # below this, no Pass-1 selection
SELECTION_TARGET = 20                   # Pass 1 picks ~this many
INPUT_HARD_CAP = 800                    # cap fed into Pass 1 (last-by-date) — context guard

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), os.pardir, "prompts")

# Topic semantics injected into prompts so harvest ≠ offerings ≠ requests, etc.
TOPIC_HINTS = {
    'harvest': "Топик «итоги цикла»: люди подводят результаты завершённого этапа.",
    'commits': "Топик «начало цикла»: люди берут на себя обязательства/планы на этап.",
    'daily': "Топик «дневник/прогресс»: ежедневные апдейты о ходе работы.",
    'offerings': "Топик «офферы»: что люди ПРЕДЛАГАЮТ (услуги, навыки, ресурсы).",
    'requests': "Топик «запросы»: что людям НУЖНО (помощь, контакты, ресурсы).",
    'intro': "Топик «знакомства»: кто пришёл в сообщество, чем занимается.",
    'sales': "Топик «продажи»: предложения о продаже/покупке.",
    'boltalka': "Топик «болталка»: свободное общение, выдели ценное среди шума.",
    'announcements': "Топик «анонсы»: важные объявления сообщества.",
    'together': "Топик «ретро/вместе»: совместная рефлексия, что получилось у группы.",
}


def _load_prompt(name: str) -> str:
    with open(os.path.join(_PROMPTS_DIR, name), encoding="utf-8") as fh:
        return fh.read()


def synthesize(topic: str, fragments: list[dict], topic_type: str | None = None) -> dict:
    """Two-pass community digest.

    fragments: [{id, text, created_at(str), author_name, sender_id, tags}, ...] by date.
    topic_type: semantic key for the prompt hint (defaults to topic).
    Returns {'content': str, 'fragment_ids': [int], 'model': str}.
    """
    topic_type = topic_type or topic
    topic_hint = TOPIC_HINTS.get(topic_type, "")

    if len(fragments) < 3:
        content = _insufficient_data_message(topic, fragments)
        return {'content': content, 'fragment_ids': [f['id'] for f in fragments],
                'model': COMPLETION_MODEL}

    # Hard-cap input BEFORE Pass 1: take the most recent by date (context guard).
    if len(fragments) > INPUT_HARD_CAP:
        logger.info("Capping input %d → %d (last by date)", len(fragments), INPUT_HARD_CAP)
        fragments = sorted(fragments, key=lambda f: f['created_at'])[-INPUT_HARD_CAP:]

    # Pass 1: LLM selection (by text, NOT vector search) if too many.
    if len(fragments) > MAX_FRAGMENTS_WITHOUT_SELECTION:
        logger.info("Pass 1: selecting ~%d from %d", SELECTION_TARGET, len(fragments))
        selected_ids = _select_fragments(topic, topic_hint, fragments)
        selected = [f for f in fragments if f['id'] in selected_ids]
        selected.sort(key=lambda f: f['created_at'])
        logger.info("Pass 1 done: %d selected", len(selected))
    else:
        selected = fragments

    # Pass 2: synthesis.
    logger.info("Pass 2: synthesizing %d fragments on '%s'", len(selected), topic)
    content = _synthesize_fragments(topic, topic_hint, selected)

    result = {
        'content': content,
        'fragment_ids': [f['id'] for f in selected],
        'model': COMPLETION_MODEL,
    }
    return result


def _select_fragments(topic: str, topic_hint: str, fragments: list[dict]) -> set[int]:
    """Pass 1: LLM picks most relevant fragment IDs. No names sent — only id+date+text."""
    fragments_list = "\n".join(
        f"[{f['id']}] {(f['created_at'] or '')[:10]} — {f['text'][:100]}"
        for f in fragments
    )
    prompt = _load_prompt("digest_selection.md").format(
        topic=topic, topic_hint=topic_hint, target=SELECTION_TARGET,
        fragments_list=fragments_list,
    )
    raw = complete(prompt, temperature=0.3)
    logger.debug("Selection raw: %s", raw)

    valid_ids = {f['id'] for f in fragments}
    selected: set[int] = set()
    for token in raw.replace('\n', ',').split(','):
        token = token.strip().strip('[]#')
        try:
            fid = int(token)
        except ValueError:
            continue
        if fid in valid_ids:
            selected.add(fid)

    # Fallback: if too few returned, keep the most recent SELECTION_TARGET.
    if len(selected) < 5:
        logger.warning("Selection returned %d ids; falling back to last %d by date",
                       len(selected), SELECTION_TARGET)
        recent = sorted(fragments, key=lambda f: f['created_at'])[-SELECTION_TARGET:]
        return {f['id'] for f in recent}
    return selected


def _synthesize_fragments(topic: str, topic_hint: str, fragments: list[dict]) -> str:
    """Pass 2: build the digest. No names sent — only [#id] (date) text."""
    fragments_text = "\n\n".join(
        f"[#{f['id']}] ({(f['created_at'] or '')[:10]})\n{f['text']}"
        for f in fragments
    )
    prompt = _load_prompt("digest_synthesis.md").format(
        topic=topic, topic_hint=topic_hint, fragments_text=fragments_text,
    )
    return complete(prompt, temperature=0.5)


def _insufficient_data_message(topic: str, fragments: list[dict]) -> str:
    lines = [f"По топику «{topic}» найдено только {len(fragments)} сообщений — "
             f"недостаточно для дайджеста.\n"]
    for f in fragments:
        lines.append(f"• [#{f['id']}] ({(f['created_at'] or '')[:10]}) {f['text'][:150]}")
    return "\n".join(lines)


def synthesize_and_save(topic: str, fragments: list[dict], topic_type: str | None = None) -> dict:
    """synthesize() + persist the digest as an artifact. Returns the result + artifact_id."""
    result = synthesize(topic, fragments, topic_type=topic_type)
    artifact_id = save_artifact(
        topic=topic, content=result['content'], fragment_ids=result['fragment_ids']
    )
    result['artifact_id'] = artifact_id
    return result
