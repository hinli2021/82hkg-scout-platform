"""遊戲 3 的後半 — 手冊學完之後，領袖在領袖帳戶按「批准」.

The studying (drill-submit) answers every check in the manual, but item 6 is
not done until a leader has watched the scout perform the movements and the
fall-in signs, and pressed approve. No code is typed any more:

  • the studying files `studied` — no points, no tick, the badge counter
    stays put;
  • the finished manual stands in the leader's queue with what to watch for;
  • one press of 批准 completes the item, with points and the tick;
  • a scout cannot finish item 6 without a real studying;
  • the code route is gone.
"""
from __future__ import annotations

import json
import pathlib

from scout import engine

DRILL = json.loads((pathlib.Path(__file__).resolve().parent.parent / 'content'
                    / 'member-badge' / 'drill.json').read_text(encoding='utf-8'))


def task_of(store, code='M06'):
    return next(t for t in store.list('tasks') if t.get('code') == code)


def records_of(store, scout, task_id):
    return [r for r in store.list('progress_records')
            if r.get('user_id') == scout.id and r.get('task_id') == task_id]


def badge_of(progress, code='SC-01'):
    return next(b for b in progress['badges'] if b.get('code') == code)


def drill_data():
    """Every required movement, answered with its own answer."""
    moves = {move['id']: move for section in DRILL['sections'] for move in section['moves']}
    required = [move_id for key in ('sign_stages', 'movement_stages')
                for stage in DRILL['game'][key] for move_id in stage]
    return {f'check_{move_id}': str(moves[move_id]['check']['answer']) for move_id in required}


def study(store, scout, task=None):
    task = task or task_of(store)
    return scout.post(f"/tasks/{task['id']}/drill-submit", data=drill_data()).get_json()


def test_studying_is_not_finishing(app, store, new_scout):
    task = task_of(store)
    reply = study(store, new_scout)
    assert reply['ok'] and reply['status'] == 'studied' and not reply['passed']

    rows = records_of(store, new_scout, task['id'])
    assert len(rows) == 1 and rows[0]['status'] == 'studied'
    assert not rows[0]['points_awarded']
    badge = badge_of(engine.progress_for(store, new_scout.id))
    m06 = next(t for t in badge['tasks'] if t['code'] == 'M06')
    assert m06['status'] == 'studied'


def test_the_finished_manual_stands_in_the_leaders_queue(app, store, new_scout, leader_client):
    study(store, new_scout)
    page = leader_client.get('/leader/review').get_data(as_text=True)
    assert '已完成遊戲 · 等考核' in page
    assert '步操訓練場兩節都完成了' in page
    assert '現在看他親身做出各個動作與集隊手號' in page
    assert '變成 ✓' in page


def test_the_leaders_approval_completes_item_6(app, store, new_scout, leader_client):
    task = task_of(store)
    study(store, new_scout)
    before = store.stats_for(new_scout.id)['points_balance']
    record = records_of(store, new_scout, task['id'])[0]

    response = leader_client.post(f"/leader/review/{record['id']}", data={'action': 'approve'})
    assert response.status_code == 200 and response.get_json()['ok']

    rows = records_of(store, new_scout, task['id'])
    assert [r['status'] for r in rows] == ['completed']
    assert rows[0]['score'] == 100
    leader = next(u for u in store.list('users') if u.get('username') == 'leader1')
    assert rows[0]['decided_by'] == leader['id']
    assert '步操' in rows[0]['leader_comment'], 'the file says what was checked'

    assert store.stats_for(new_scout.id)['points_balance'] == before + int(task['points'])
    badge = badge_of(engine.progress_for(store, new_scout.id))
    assert next(t for t in badge['tasks'] if t['code'] == 'M06')['status'] == 'completed'

    status = new_scout.get(f"/tasks/{task['id']}/status").get_json()
    assert status['status'] == 'completed'

    page = new_scout.get(f"/badges/{badge['id']}/requirements").get_data(as_text=True)
    assert '領袖批准 · 已完成' in page


def test_the_drill_page_waits_without_a_code_box(app, store, new_scout):
    task = task_of(store)
    study(store, new_scout)
    import html as _html
    source = _html.unescape(new_scout.get(f"/tasks/{task['id']}/drill").get_data(as_text=True))
    assert 'data-drill-code' not in source
    assert '"studied_now": true' in source
    assert '已提交，等領袖批准' in source
    assert '"status_url"' in source

    response = new_scout.client.post(
        f"/tasks/{task['id']}/drill-code", data={'code': '82DR'},
        headers={'Accept': 'application/json', 'X-Requested-With': 'fetch'})
    assert response.status_code in (404, 405), 'the code route no longer exists'


def test_the_drill_page_keys_its_saved_manual_to_the_scout(app, store, new_scout):
    """Game 3's half-read answers live in the browser: the page must say
    whose they are, so the game keys them by account, not by task alone —
    a shared tablet (or the leaders' test account after a reset) must not
    resume somebody else's stage."""
    import pathlib
    task = task_of(store)
    import html as _html
    source = _html.unescape(new_scout.get(f"/tasks/{task['id']}/drill").get_data(as_text=True))
    assert f'"user_id": "{new_scout.id}"' in source
    js = (pathlib.Path(__file__).resolve().parent.parent / "static" / "js" / "drill.js").read_text(encoding="utf-8")
    assert "drill-manual-" in js and "(cfg.user_id || 'demo')" in js


def test_an_unstudied_manual_cannot_be_signed_off(app, store, new_scout):
    task = task_of(store)
    status = new_scout.get(f"/tasks/{task['id']}/status").get_json()
    assert status['status'] == 'todo'
    response = new_scout.post(f"/tasks/{task['id']}/submit", data={'notes': 'done'})
    assert response.status_code == 403
    assert response.get_json()['error'] == 'play_the_drill'
    assert not records_of(store, new_scout, task['id'])


def test_the_wording_names_the_leader_not_a_code():
    assess = DRILL['assess']
    assert '批准' in assess['after_zh'] and '領袖帳戶' in assess['after_zh']
    assert '代碼' not in json.dumps(assess, ensure_ascii=False)
    assert '批准' in DRILL['studied']['pass_zh']


def test_the_drill_files_the_finish_time(store, new_scout):
    """步操訓練場榜看完成時間：記錄帶 `_ms`，自查答案照舊保留。"""
    task = task_of(store)
    data = {**drill_data(), 'elapsed_ms': '485000'}
    assert new_scout.post(f"/tasks/{task['id']}/drill-submit", data=data).status_code == 200
    record = records_of(store, new_scout, task['id'])[-1]
    blob = json.loads(record['answers_json'])
    assert blob['_ms'] == 485000
    assert len([key for key in blob if key != '_ms']) == len(drill_data())   # 每個動作的自查答案

    from scout import engine

    rows = next(board for board in engine.leaderboard_sections(store)['games']['columns']
                if board['code'] == 'M06')['rows']
    row = next(r for r in rows if r['user_id'] == new_scout.id)
    assert row['value'] == 485000 and row['rank'] == 1 and row['done'] is False


def test_a_replay_starts_from_the_beginning_story_first():
    """Playing the drill again starts at the gate, story first."""
    import pathlib
    js = (pathlib.Path(__file__).resolve().parent.parent / "static" / "js"
          / "drill.js").read_text(encoding="utf-8")
    assert "function restart()" in js and "show('intro');" in js
    assert "if (where === 'restart') { stopWaiting(); restart(); return; }" in js
    # leaving mid-drill asks first, like every other game
    assert "drill-exit-title" in js and ("beforeunload" in js)


def test_the_drill_story_arrives_from_the_crossing_and_is_paged():
    """Game 3 opens where game 2 ended, and tells its story page by page."""
    import json, pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    drill = json.loads((root / "content/member-badge/drill.json").read_text(encoding="utf-8"))
    assert "迷霧渡口" in drill["intro"]["paras_zh"][0]
    assert "沙灘" in drill["studied"]["pass_note_zh"]
    js = (root / "static/js/drill.js").read_text(encoding="utf-8")
    assert 'data-drill-go="intro-next"' in js and "state.ipage" in js


def test_drill_finish_screens_offer_a_clear_way_on():
    """Waiting or approved, the drill ground ends with a clear next-game button.

    On the waiting (assess) card the button is the big primary one and the
    notice beside it says the item still needs the leader's approval; on the
    approved card the same clear button is there too (it used to be missing).
    """
    import json, pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    drill = json.loads((root / "content/member-badge/drill.json").read_text(encoding="utf-8"))
    note = drill["assess"]["pending_note_zh"]
    assert "領袖批准" in note and "下一個遊戲" in note
    assert "leader approves" in drill["assess"]["pending_note_en"]
    js = (root / "static/js/drill.js").read_text(encoding="utf-8")
    assert "function nextGameButton" in js and "nextGameButton()" in js
    assert "next-game-note" in js and 'btn primary big' in js
