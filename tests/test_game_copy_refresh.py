"""遊戲 2、3 的完成方式改了：舊部署的說明文字要跟上，但不可蓋過領袖的修改.

The task instructions were seeded into the data store when a deployment was
first created, so an existing site would still say "輸入領袖代碼". The boot
migration swaps only the untouched seed sentence; anything a leader wrote is
left alone.
"""
from __future__ import annotations

from scout.schema import SEED_BADGES


def task_of(store, code):
    return next(t for t in store.list('tasks') if t.get('code') == code)


def test_the_old_seed_sentence_is_swapped_for_the_new_one(store):
    task = task_of(store, 'M05')
    old_zh = next(old[0] for code, fields in store.GAME_COPY_REFRESH.items() if code == 'M05'
                  for field, old in fields.items() if field == 'instruction_zh')
    store.update('tasks', task['id'], {'instruction_zh': old_zh})
    assert '輸入領袖代碼' not in old_zh

    assert store.refresh_game_copy() == 1
    after = task_of(store, 'M05')['instruction_zh']
    seed = next(t for b in SEED_BADGES for t in b['tasks'] if t.get('code') == 'M05')
    assert after == seed['instruction_zh']
    assert '批准' in after and '代碼' not in after


def test_a_leaders_own_wording_is_never_touched(store):
    task = task_of(store, 'M06')
    mine = '我自己的寫法：學會步操，找領袖看一次。'
    store.update('tasks', task['id'], {'instruction_zh': mine})
    assert store.refresh_game_copy() == 0
    assert task_of(store, 'M06')['instruction_zh'] == mine


def test_the_refresh_is_idempotent_on_a_fresh_seed(store):
    """A new deployment is already on the new copy: no write happens."""
    assert store.refresh_game_copy() == 0
    assert '批准' in task_of(store, 'M05')['instruction_zh']
