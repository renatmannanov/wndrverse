"""Unit tests for core.ingest.normalize.message_to_fragment (the parser)."""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ingest.normalize import message_to_fragment, _extract_tags


def _msg(**over):
    base = {
        'id': 5595, 'date': '2026-01-22T17:24:57', 'user_id': 25533754,
        'sender_name': 'Dmitry Dumik', 'username': 'ddumik',
        'text': 'Привет всем! Я делаю #startup про #community и ищу со-основателя.',
        'char_count': 60, 'reply_to_msg_id': 5593,
        'reactions': [{'emoji': '🔥', 'count': 3}],
    }
    base.update(over)
    return base


def test_basic_mapping():
    f = message_to_fragment(_msg(), topic='intro', chat_name='WNDR chat', thread_root_id=5593)
    assert f['external_id'] == 'wndr_WNDR chat_5595'
    assert f['source'] == 'telegram'
    assert f['sender_id'] == 25533754
    assert f['author_name'] == 'Dmitry Dumik'
    assert f['topic'] == 'intro'
    assert f['message_thread_id'] == 5593
    assert isinstance(f['created_at'], datetime)          # datetime for insert, not string
    assert f['created_at'] == datetime(2026, 1, 22, 17, 24, 57)
    assert set(f['tags']) == {'startup', 'community'}      # hashtags extracted
    assert f['metadata']['username'] == 'ddumik'
    assert f['metadata']['reactions'] == [{'emoji': '🔥', 'count': 3}]
    print('test_basic_mapping OK')


def test_empty_text_skipped():
    assert message_to_fragment(_msg(text=''), topic='intro', chat_name='c', thread_root_id=1) is None
    assert message_to_fragment(_msg(text='   '), topic='intro', chat_name='c', thread_root_id=1) is None
    m = _msg(); del m['text']
    assert message_to_fragment(m, topic='intro', chat_name='c', thread_root_id=1) is None
    print('test_empty_text_skipped OK')


def test_null_user_id_ok():
    f = message_to_fragment(_msg(user_id=None), topic='intro', chat_name='c', thread_root_id=1)
    assert f is not None and f['sender_id'] is None        # must not crash on null user_id
    print('test_null_user_id_ok OK')


def test_extract_tags():
    assert _extract_tags('no tags here') == []
    assert _extract_tags('#one #two text') == ['one', 'two']
    assert _extract_tags('lone # not a tag') == []         # bare '#' ignored
    print('test_extract_tags OK')


if __name__ == "__main__":
    test_basic_mapping()
    test_empty_text_skipped()
    test_null_user_id_ok()
    test_extract_tags()
    print("ALL TESTS PASSED")
