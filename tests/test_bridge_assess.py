"""遊戲 2 的後半 — 過橋之後，領袖在領袖帳戶按「批准」.

The crossing (bridge-submit) lays the words in order, but item 5 is not done
until a leader has heard the scout recite and explain, and pressed approve.
Nobody types a code any more. These tests hold that line:

  • a crossing files `crossed`, not `completed` — nothing is counted, awarded
    or ticked yet;
  • the map and the journey move on to game 3 anyway (the approval can wait);
  • the finished crossing stands in the leader's queue, with what to check,
    and one press of 批准 completes the item — with points, badge credit and
    an audit trail;
  • the scout's pages then show ✓ (and the status route says so);
  • a scout cannot finish the item without a real crossing;
  • existing completions from before the change are never touched.
"""
from __future__ import annotations

import html
import json
import pathlib

import pytest

from scout import engine

RIVER = json.loads((pathlib.Path(__file__).resolve().parent.parent / 'content'
                    / 'member-badge' / 'river.json').read_text(encoding='utf-8'))


def bridge_data():
    """Every plank of every stage, in order — a complete crossing."""
    data = {}
    for n, stage in enumerate(RIVER['stages'], start=1):
        data[f'stage{n}'] = [plank['key'] for plank in stage['planks']]
    return data


def task_of(store, code='M05'):
    return next(t for t in store.list('tasks') if t.get('code') == code)


def records_of(store, scout, task_id):
    return [r for r in store.list('progress_records')
            if r.get('user_id') == scout.id and r.get('task_id') == task_id]


def badge_of(progress, code='SC-01'):
    return next(b for b in progress['badges'] if b.get('code') == code)


def cross(store, scout, task=None):
    task = task or task_of(store)
    return scout.post(f"/tasks/{task['id']}/bridge-submit", data=bridge_data()).get_json()


def approve(leader, record_id, **extra):
    data = {'action': 'approve', **extra}
    return leader.post(f"/leader/review/{record_id}", data=data)


def finish_cave(store, scout):
    """Game 1 out of the way, so the map's next pointer can stand on area 2."""
    cave = task_of(store, 'M04')
    config = store.get('tasks', cave['id'])['config_json']
    config = json.loads(config) if isinstance(config, str) else config
    answers = {f"q{i}": str(q['answer']) for i, q in enumerate(config['questions'])}
    reply = scout.post(f"/tasks/{cave['id']}/cave-submit", data=answers).get_json()
    assert reply['passed'], 'the cave must clear before the bridge in these tests'


def test_a_crossing_is_recorded_but_the_item_is_not_done(app, store, new_scout):
    task = task_of(store)
    reply = cross(store, new_scout)
    assert reply['ok'] and reply['status'] == 'crossed' and not reply['passed']

    rows = records_of(store, new_scout, task['id'])
    assert len(rows) == 1 and rows[0]['status'] == 'crossed'
    assert not rows[0]['points_awarded'], 'no points until the leader has pressed approve'

    progress = engine.progress_for(store, new_scout.id)
    badge = badge_of(progress)
    m05 = next(t for t in badge['tasks'] if t['code'] == 'M05')
    assert m05['status'] == 'crossed'
    assert badge['progress_done'] == 0 and not badge['earned'], \
        'the crossing alone must not light up the badge counter'


def test_the_map_moves_on_to_game_3_while_the_approval_waits(app, store, new_scout):
    """已過橋未批准：第 2 區未算完成，但「你在這裡」已走到第 3 區."""
    task = task_of(store)
    finish_cave(store, new_scout)
    cross(store, new_scout)

    progress = engine.progress_for(store, new_scout.id)
    badge = badge_of(progress)
    stages = engine.stage_list(store, user=new_scout.user, badge=badge)
    second, third = stages[1], stages[2]
    assert not second['done'] and second['crossed']
    assert not second['next'], 'the walk does not wait at a crossed bridge'
    assert third['next'], 'the scout may carry on to game 3'

    # the journey offer follows the same rule: the bridge counts as played
    from scout.routes import scout_routes as routes
    with app.app_context():
        onward = routes._journey_next(new_scout.user, task)
    assert onward is None or onward['task']['id'] != task['id']

    # the home page still points the scout at their unfinished half
    overall = progress['overall']
    assert overall['next_task'] and overall['next_task']['task']['code'] == 'M05', \
        'home suggests the assess card, not a task behind it'


def test_the_finished_crossing_stands_in_the_leaders_queue(app, store, new_scout, leader_client):
    task = task_of(store)
    cross(store, new_scout)

    page = leader_client.get('/leader/review').get_data(as_text=True)
    assert '已完成遊戲 · 等考核' in page, 'the queue names it as a finished game'
    assert '渡口三關木板都排對了' in page, 'the leader is told what to listen for'
    assert '背誦' in page and '講解' in page, 'the 考核 is spelled out, not guessed'
    assert '變成 ✓' in page, 'the leader is told what the press does'

    # it is in the same queue as ordinary submissions — one approve button
    record = records_of(store, new_scout, task['id'])[0]
    assert f'/leader/review/{record["id"]}' in page


def test_the_leaders_approval_completes_the_item_with_points(app, store, new_scout, leader_client):
    task = task_of(store)
    cross(store, new_scout)
    before = store.stats_for(new_scout.id)
    record = records_of(store, new_scout, task['id'])[0]

    response = approve(leader_client, record['id'])
    assert response.status_code == 200 and response.get_json()['ok']

    rows = records_of(store, new_scout, task['id'])
    assert [r['status'] for r in rows] == ['completed'], \
        'the crossing record itself becomes the completion — no second row'
    done = rows[0]
    assert done['score'] == 100
    assert done['decided_by'] == new_scout_by(store)['id'], 'a person signed it, not a code'

    stats = store.stats_for(new_scout.id)
    assert stats['points_balance'] == before['points_balance'] + int(task['points'])
    ledger = [row for row in store.list('points_ledger') if row['user_id'] == new_scout.id]
    assert any(row['ref_id'] == task['id'] and row['entry_type'] == 'task' for row in ledger)

    progress = engine.progress_for(store, new_scout.id)
    badge = badge_of(progress)
    m05 = next(t for t in badge['tasks'] if t['code'] == 'M05')
    assert m05['status'] == 'completed' and badge['progress_done'] == 1

    actions = [(row['action'], row['entity_id']) for row in store.list('audit_log')
               if row.get('actor_id') == new_scout_by(store)['id']]
    assert ('approve', record['id']) in actions


def new_scout_by(store):
    """The leader row — what `decided_by` must point at."""
    return next(u for u in store.list('users') if u.get('username') == 'leader1')


def test_the_scout_sees_the_tick_once_the_leader_approves(app, store, new_scout, leader_client):
    task = task_of(store)
    cross(store, new_scout)
    record = records_of(store, new_scout, task['id'])[0]

    # before: the queue is the message, no tick
    badge = badge_of(engine.progress_for(store, new_scout.id))
    page = new_scout.get(f"/badges/{badge['id']}/requirements").get_data(as_text=True)
    assert '已提交 · 等領袖批准' in page
    assert '已完成' in page and '✔' not in page.split('第 5 項')[0][-200:]

    status = new_scout.get(f"/tasks/{task['id']}/status").get_json()
    assert status['status'] == 'crossed' and status['ok']

    approve(leader_client, record['id'])

    status = new_scout.get(f"/tasks/{task['id']}/status").get_json()
    assert status['status'] == 'completed', 'the assess card polls this'
    assert status['comment'], 'the leader’s sentence comes back with it'

    badge = badge_of(engine.progress_for(store, new_scout.id))
    page = new_scout.get(f"/badges/{badge['id']}/requirements").get_data(as_text=True)
    assert '領袖批准 · 已完成' in page

    # the task page sends a game task to the game itself; the tick is the pill
    mine = new_scout.get('/api/me/progress').get_json()['badges'][0]['tasks']
    m05 = next(t for t in mine if t['code'] == 'M05')
    assert m05['status'] == 'completed'


def test_a_scout_cannot_finish_item_5_without_a_real_crossing(app, store, new_scout):
    task = task_of(store)
    status = new_scout.get(f"/tasks/{task['id']}/status").get_json()
    assert status['status'] == 'todo', 'nothing on file yet'

    response = new_scout.post(f"/tasks/{task['id']}/submit", data={'notes': 'done'})
    assert response.status_code == 403
    assert response.get_json()['error'] == 'play_the_bridge'
    assert '領袖批准' in response.get_json()['message_zh']
    assert not records_of(store, new_scout, task['id']), 'nothing was filed'


def test_the_code_route_is_gone(app, store, new_scout):
    """The leader approves in the leader account — there is no code to type."""
    task = task_of(store)
    cross(store, new_scout)
    response = new_scout.client.post(
        f"/tasks/{task['id']}/bridge-code", data={'code': '82BP'},
        headers={'Accept': 'application/json', 'X-Requested-With': 'fetch'})
    assert response.status_code in (404, 405), 'the code route no longer exists'
    assert [r['status'] for r in records_of(store, new_scout, task['id'])] == ['crossed']


def test_the_assess_card_holds_no_code_box(app, store, new_scout):
    task = task_of(store)
    cross(store, new_scout)
    source = html.unescape(new_scout.get(f"/tasks/{task['id']}/bridge").get_data(as_text=True))
    assert 'data-bridge-code' not in source, 'no code form is shipped to the browser'
    assert 'data-bridge-code-input' not in source
    assert '"status_url": "/tasks/' in source, 'the card knows where to ask'
    assert '"demo_approve"' not in source, 'the live page never stands in for the leader'


def test_a_second_crossing_does_not_double_file(app, store, new_scout):
    task = task_of(store)
    cross(store, new_scout)
    cross(store, new_scout)
    assert [r['status'] for r in records_of(store, new_scout, task['id'])] == ['crossed']


def test_a_rejected_crossing_can_be_played_again(app, store, new_scout, leader_client):
    task = task_of(store)
    cross(store, new_scout)
    record = records_of(store, new_scout, task['id'])[0]

    leader_client.post(f"/leader/review/{record['id']}",
                       data={'action': 'reject', 'comment': '再練一次誓詞'})
    assert [r['status'] for r in records_of(store, new_scout, task['id'])] == ['rejected']

    reply = cross(store, new_scout)
    assert reply['ok'] and reply['status'] == 'crossed'
    assert [r['status'] for r in records_of(store, new_scout, task['id'])] == \
        ['rejected', 'crossed'], 'the retry is a fresh record'


def test_later_on_an_awaiting_game_keeps_it_in_the_queue(app, store, new_scout, leader_client):
    task = task_of(store)
    cross(store, new_scout)
    record = records_of(store, new_scout, task['id'])[0]
    leader_client.post(f"/leader/review/{record['id']}", data={'action': 'reset'})
    assert [r['status'] for r in records_of(store, new_scout, task['id'])] == ['crossed'], \
        'reset must not turn a finished game into an ordinary submission'


def test_completions_never_double_award_on_a_replay(app, store, new_scout, leader_client):
    task = task_of(store)
    cross(store, new_scout)
    approve(leader_client, records_of(store, new_scout, task['id'])[0]['id'])
    before = store.stats_for(new_scout.id)['points_balance']

    # a scout who re-plays a finished crossing: the game says already done
    reply = cross(store, new_scout)
    assert reply['ok'] and reply['status'] == 'completed' and reply['already_done']
    assert store.stats_for(new_scout.id)['points_balance'] == before


def test_the_badge_page_holds_no_code_form_for_a_crossed_scout(app, store, new_scout):
    task = task_of(store)
    cross(store, new_scout)
    badge = badge_of(engine.progress_for(store, new_scout.id))
    page = new_scout.get(f"/badges/{badge['id']}/requirements").get_data(as_text=True)
    assert '/bridge-code' not in page and '領袖代碼' not in page
    assert '等領袖批准' in page and '等領袖在帳戶批准' in page


def test_the_game_page_opens_on_the_assess_card_once_crossed(app, store, new_scout):
    task = task_of(store)
    page = new_scout.get(f"/tasks/{task['id']}/bridge")
    assert '河水擋住了去路' in page.get_data(as_text=True)
    assert '"crossed_now": false' in html.unescape(page.get_data(as_text=True))
    cross(store, new_scout)
    # after: the assess card is what greets the scout (no re-laying needed).
    source = html.unescape(new_scout.get(f"/tasks/{task['id']}/bridge").get_data(as_text=True))
    assert '已提交，等領袖批准' in source, 'the assess card is the opening screen'
    assert '"crossed_now": true' in source, 'the game config carries the state'
    assert '<h1 class="cave-title">河水擋住了去路</h1>' not in source, \
        'the bank headline is only the pre-crossing card'


def test_the_assess_wording_teaches_the_two_halves():
    """考核卡要把話講清楚：背誦 + 講解日常生活怎樣實行，批准在領袖手上."""
    assess = RIVER['assess']
    assert '背誦' in assess['points_zh'][0] and '講解' in assess['points_zh'][1]
    assert '批准' in assess['after_zh'] and '第 5 項' in assess['after_zh']
    assert '代碼' not in json.dumps(assess, ensure_ascii=False), 'no code is left in the copy'
    crossed = RIVER['crossed']
    assert '考核通過' in crossed['pass_title_zh']
    assert '領袖' in crossed['paras_zh'][1], 'the far bank names the next step'


def test_the_crossing_files_the_finish_time(store, new_scout):
    """渡口榜看完成時間：過橋的記錄帶 `_ms`，木板照舊留在 answers_json。"""
    task = task_of(store)
    data = {**bridge_data(), 'elapsed_ms': '312000'}
    assert new_scout.post(f"/tasks/{task['id']}/bridge-submit", data=data).status_code == 200
    record = records_of(store, new_scout, task['id'])[-1]
    blob = json.loads(record['answers_json'])
    assert blob['_ms'] == 312000
    assert sum(1 for key in blob if key.startswith('stage')) == len(RIVER['stages'])


def test_an_impossible_clock_keeps_the_scout_off_the_time_board(store, new_scout):
    """3 秒鐘的「過橋」不是過橋：仍然記錄通關，但榜上不給名次。"""
    task = task_of(store)
    data = {**bridge_data(), 'elapsed_ms': '3000'}
    assert new_scout.post(f"/tasks/{task['id']}/bridge-submit", data=data).status_code == 200
    boards = engine.leaderboard_sections(store)
    rows = next(board for board in boards['games']['columns'] if board['code'] == 'M05')['rows']
    row = next(r for r in rows if r['user_id'] == new_scout.id)
    assert row['value'] is None and row['rank'] is None and row['done'] is False
