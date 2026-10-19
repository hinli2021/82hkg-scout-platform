"""The local demo upgrade must never wipe earlier scouts or their scores."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

from scout import engine


ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_existing_demo_upgrade_is_idempotent_and_preserves_progress(store, data_dir):
    badge = next(b for b in store.list('badges') if b.get('code') == 'SC-01')
    guide = engine.as_json(badge['guide_json'], {})
    # Recreate the former layout on a disposable seeded database: item 4
    # doubled as a paper in area 2, and other tasks sat in area 1.
    quest = guide['quest']
    quest['award_rule'] = 'all_tasks'
    quest['areas'][0]['items'] = [1, 2]
    quest['areas'][0]['game'] = {'n': 1, 'kind': '', 'ready': False, 'task_code': ''}
    quest['areas'][1]['items'] = [3, 4]
    quest['areas'][1]['game'] = {'n': 1, 'kind': 'cave', 'ready': True,
                                'task_code': 'M04'}
    store.update('badges', badge['id'], {'guide_json': guide})
    cave = next(t for t in store.list('tasks') if t.get('code') == 'M04')
    old_cfg = engine.as_json(cave['config_json'], {})
    old_cfg['links'] = [{'label_zh': '舊試卷',
                         'url': 'https://forms.gle/M4vtu6GwsMd5do1J8'}]
    store.update('tasks', cave['id'], {'title_zh': '舊第 4 項試卷', 'config_json': old_cfg})
    counts_before = {name: len(store.list(name)) for name in
                     ('users', 'progress_records', 'points_ledger', 'badge_awards')}
    env = {**os.environ, 'DATA_DIR': data_dir, 'SEED_DEMO': 'false',
           'DATA_DRIVER': 'local'}
    script = ROOT / 'tools' / 'migrate_member_five_games.py'
    result = subprocess.run([sys.executable, str(script)], cwd=ROOT, env=env,
                            capture_output=True, text=True, check=True)
    assert 'SC-01 updated' in result.stdout
    updated = engine.as_json(store.get('badges', badge['id'])['guide_json'], {})
    assert updated['quest']['award_rule'] == 'five_games'
    assert updated['quest']['areas'][0]['items'] == []
    assert updated['quest']['areas'][0]['game']['task_code'] == 'M04'
    assert updated['quest']['areas'][1]['items'] == [3]
    second_area = updated['quest']['areas'][1]['game']
    assert second_area['task_code'] == 'M05' and second_area['ready']
    assert second_area['kind'] == 'bridge'
    third_area = updated['quest']['areas'][2]['game']
    assert third_area['task_code'] == 'M06' and third_area['ready']
    assert third_area['kind'] == 'drill'
    assert all(not a['game']['ready'] for a in updated['quest']['areas'][3:])
    changed = store.get('tasks', cave['id'])
    assert changed['title_zh'] == '第 4 項：童軍歷史山洞（遊戲 1）'
    assert len(engine.as_json(changed['config_json'], {})['questions']) == 50
    assert 'forms.gle/M4vtu6GwsMd5do1J8' not in json.dumps(changed)
    second = subprocess.run([sys.executable, str(script)], cwd=ROOT, env=env,
                            capture_output=True, text=True, check=True)
    assert 'nothing changed' in second.stdout
    assert counts_before == {name: len(store.list(name)) for name in counts_before}


def test_old_signoff_item_six_becomes_the_drill_game(store, data_dir):
    """A pre-drill install knows item 6 as a sign-off task; the migration
    raises it to game 3 (步操訓練場) and wires area 3, keeping leader text."""
    badge = next(b for b in store.list('badges') if b.get('code') == 'SC-01')
    guide = engine.as_json(badge['guide_json'], {})
    # the former shape: area 3 held no game, item 6 was listed as a syllabus row
    guide['quest']['areas'][2]['items'] = [5, 6]
    guide['quest']['areas'][2]['game'] = {'n': 3, 'kind': '', 'ready': False,
                                          'name_zh': '即將推出', 'name_en': 'Coming soon',
                                          'blurb_zh': '這一區的遊戲正在製作，等待領袖加入。',
                                          'blurb_en': 'This area’s game is being built. '
                                                      'Your leader will add it later.',
                                          'task_code': ''}
    store.update('badges', badge['id'], {'guide_json': guide})
    m06 = next(t for t in store.list('tasks') if t.get('code') == 'M06')
    store.update('tasks', m06['id'], {
        'title_zh': '第 6 項：宣誓禮儀與中式隊列',
        'title_en': 'Item 6 — investiture customs and drill',
        'instruction_zh': ('認識宣誓時應有之童軍禮儀，以及中式隊列之基本動作。考核動作：salute；'
                           'alert／stand-at-ease；right turn／left turn／about turn；pace '
                           'forward／backward／left／right march；dressing right dress；mark '
                           'time；by the front quick march。'),
        'instruction_en': ('Know the Scout customs for the investiture ceremony and the '
                           'basic movements of Chinese-style drill. Show: salute; alert / '
                           'stand-at-ease; right turn / left turn / about turn; pace '
                           'forward / backward / left / right march; dressing right dress; '
                           'mark time; by the front quick march.'),
        'type': 'signoff',
        'config_json': {'links': [{'label_zh': '步操示範資源', 'label_en': 'Drill reference',
                                   'url': 'https://example.org/drill'}]},
    })
    counts = {name: len(store.list(name)) for name in
              ('users', 'progress_records', 'points_ledger', 'badge_awards')}
    env = {**os.environ, 'DATA_DIR': data_dir, 'SEED_DEMO': 'false',
           'DATA_DRIVER': 'local'}
    script = ROOT / 'tools' / 'migrate_member_five_games.py'
    result = subprocess.run([sys.executable, str(script)], cwd=ROOT, env=env,
                            capture_output=True, text=True, check=True)
    assert 'gained game 3, the drill ground' in result.stdout

    task = store.get('tasks', m06['id'])
    assert task['type'] == 'quiz' and task['pass_score'] == 0
    assert task['title_zh'] == '第 6 項：步操訓練場（遊戲 3）'
    config = engine.as_json(task['config_json'], {})
    assert config['kind'] == 'drill'
    assert any(row.get('url') == 'https://example.org/drill'
               for row in config.get('links', [])), \
        'the leader’s own drill link survives the upgrade'

    updated = engine.as_json(store.get('badges', badge['id'])['guide_json'], {})
    area = updated['quest']['areas'][2]
    assert area['items'] == [5]                      # item 6 moved into its game
    assert area['game']['task_code'] == 'M06' and area['game']['ready']
    assert area['game']['kind'] == 'drill'
    assert area['game']['name_zh'] == '步操訓練場'
    assert counts == {name: len(store.list(name)) for name in counts}
    second = subprocess.run([sys.executable, str(script)], cwd=ROOT, env=env,
                            capture_output=True, text=True, check=True)
    assert 'nothing changed' in second.stdout


def test_existing_five_game_badge_gets_new_directions_without_overwriting_leader_copy(
        store, data_dir):
    """Upgrading the interface must refresh old default prompts, not custom text."""
    badge = next(b for b in store.list('badges') if b.get('code') == 'SC-01')
    guide = engine.as_json(badge['guide_json'], {})
    original = guide['quest'].copy()
    guide['quest']['start_zh'] = '划出去 →'
    guide['quest']['start_en'] = 'Cast off →'
    guide['quest']['trail_lead_en'] = (
        'This is your island treasure map. Tap any area to see its game. '
        'Clear all five games to reach the raft on the beach.')
    guide['quest']['start_note_en'] = 'Leader-written invitation to the island'
    store.update('badges', badge['id'], {'guide_json': guide})
    counts = {name: len(store.list(name)) for name in
              ('users', 'progress_records', 'points_ledger', 'badge_awards')}
    env = {**os.environ, 'DATA_DIR': data_dir, 'SEED_DEMO': 'false',
           'DATA_DRIVER': 'local'}
    script = ROOT / 'tools' / 'migrate_member_five_games.py'
    result = subprocess.run([sys.executable, str(script)], cwd=ROOT, env=env,
                            capture_output=True, text=True, check=True)
    assert 'journey copy updated' in result.stdout
    updated = engine.as_json(store.get('badges', badge['id'])['guide_json'], {})['quest']
    for key in ('start_zh', 'start_en', 'trail_lead_en'):
        assert updated[key] == original[key]
    assert updated['start_note_en'] == 'Leader-written invitation to the island'
    assert counts == {name: len(store.list(name)) for name in counts}
    second = subprocess.run([sys.executable, str(script)], cwd=ROOT, env=env,
                            capture_output=True, text=True, check=True)
    assert 'nothing changed' in second.stdout


def test_existing_cave_pass_mark_is_retired_without_erasing_leader_copy(store, data_dir):
    badge = next(b for b in store.list('badges') if b.get('code') == 'SC-01')
    cave = next(t for t in store.list('tasks') if t.get('code') == 'M04')
    guide = engine.as_json(badge['guide_json'], {})
    item = guide['items'][3]
    item['req_zh'][0] = (
        '在第一個區域完成「童軍歷史山洞」遊戲：閱讀四面壁畫，逐組完成 50 題；滿分 100 分，80 分合格。')
    item['req_en'][0] = (
        'In area one, clear The Cave of Scouting History: read four wall paintings and '
        'answer all 50 questions in groups. The pass mark is 80 out of 100.')
    item['req_en'][1] = 'Leader-written note about the cave'
    item['stage_hint_zh'] = '看完四段壁畫，在石室回答共 50 題；80 分合格，無須另做試卷。'
    store.update('badges', badge['id'], {'guide_json': guide})
    store.update('tasks', cave['id'], {
        'pass_score': 80,
        'instruction_zh': (
            '第一個區域只有童軍歷史山洞：先閱讀四段壁畫，再在石室走過 50 題；每題 2 分，'
            '80 分合格。完成山洞就完成第 4 項，不必另做試卷。'),
        'instruction_en': 'A leader wrote this instruction.',
    })
    config_before = engine.as_json(cave['config_json'], {})
    counts = {name: len(store.list(name)) for name in
              ('users', 'progress_records', 'points_ledger', 'badge_awards')}
    env = {**os.environ, 'DATA_DIR': data_dir, 'SEED_DEMO': 'false',
           'DATA_DRIVER': 'local'}
    script = ROOT / 'tools' / 'migrate_member_five_games.py'
    result = subprocess.run([sys.executable, str(script)], cwd=ROOT, env=env,
                            capture_output=True, text=True, check=True)
    assert 'cave completion rule updated' in result.stdout
    updated = engine.as_json(store.get('badges', badge['id'])['guide_json'], {})['items'][3]
    assert '不設合格分數' in updated['req_zh'][0]
    assert 'whatever your score' in updated['req_en'][0]
    assert updated['req_en'][1] == 'Leader-written note about the cave'
    assert '分數只供回顧' in updated['stage_hint_zh']
    task = store.get('tasks', cave['id'])
    assert task['pass_score'] == 0 and '自動通關' in task['instruction_zh']
    assert task['instruction_en'] == 'A leader wrote this instruction.'
    assert engine.as_json(task['config_json'], {}) == config_before
    assert counts == {name: len(store.list(name)) for name in counts}
    second = subprocess.run([sys.executable, str(script)], cwd=ROOT, env=env,
                            capture_output=True, text=True, check=True)
    assert 'nothing changed' in second.stdout
