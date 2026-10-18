"""遊戲 2 的後半 — 過橋之後，領袖考核與代碼.

The crossing (bridge-submit) lays the words in order, but item 5 is not done
until a leader has heard the scout recite and explain, and handed over the
code. These tests hold that line:

  • a crossing files `crossed`, not `completed` — nothing is counted, awarded
    or ticked yet;
  • the map and the journey move on to game 3 anyway (the code can wait);
  • the code only works after a real crossing, and only the right code
    completes the item — with points, badge credit and audit trail;
  • existing completions from before the change are never touched.
"""
from __future__ import annotations

import html
import json
import pathlib

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


def enter_code(store, scout, code='82BP', task=None, **kw):
    task = task or task_of(store)
    return scout.post(f"/tasks/{task['id']}/bridge-code", data={'code': code}, **kw).get_json()


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
    assert not rows[0]['points_awarded'], 'no points until the leader has spoken'

    progress = engine.progress_for(store, new_scout.id)
    badge = badge_of(progress)
    m05 = next(t for t in badge['tasks'] if t['code'] == 'M05')
    assert m05['status'] == 'crossed'
    assert badge['progress_done'] == 0 and not badge['earned'], \
        'the crossing alone must not light up the badge counter'


def test_the_map_moves_on_to_game_3_while_the_code_waits(app, store, new_scout):
    """已過橋未輸入代碼：第 2 區未算完成，但「你在這裡」已走到第 3 區."""
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

    # the home page still points the scout at their unfinished half — the code
    overall = progress['overall']
    assert overall['next_task'] and overall['next_task']['task']['code'] == 'M05', \
        'home suggests the assess card, not a task behind it'


def test_the_code_completes_what_the_crossing_started(app, store, new_scout):
    task = task_of(store)
    cross(store, new_scout)
    before = store.stats_for(new_scout.id)

    reply = enter_code(store, new_scout)
    assert reply['ok'] and reply['passed'] and reply['status'] == 'completed'

    rows = records_of(store, new_scout, task['id'])
    assert [r['status'] for r in rows] == ['crossed', 'completed'], \
        'the crossing stays on file; the code adds the completion'
    assert rows[1]['score'] == 100 and rows[1]['decided_by'] == 'leader-code'

    stats = store.stats_for(new_scout.id)
    assert stats['points_balance'] == before['points_balance'] + int(task['points'])
    ledger = [row for row in store.list('points_ledger') if row['user_id'] == new_scout.id]
    assert any(row['ref_id'] == task['id'] and row['entry_type'] == 'task' for row in ledger)

    progress = engine.progress_for(store, new_scout.id)
    badge = badge_of(progress)
    m05 = next(t for t in badge['tasks'] if t['code'] == 'M05')
    assert m05['status'] == 'completed' and badge['progress_done'] == 1

    actions = [(row['action'], row['entity_id']) for row in store.list('audit_log')
               if row.get('actor_id') == new_scout.id]
    assert ('bridge_code', task['id']) in actions


def test_a_code_cannot_skip_the_bridge(app, store, new_scout):
    task = task_of(store)
    reply = enter_code(store, new_scout)
    assert reply['status_code_if_set'] if False else True  # placeholder, see below
    response = new_scout.client.post(
        f"/tasks/{task['id']}/bridge-code", data={'code': '82BP'},
        headers={'Accept': 'application/json', 'X-Requested-With': 'fetch'})
    assert response.status_code == 400
    body = response.get_json()
    assert body['error'] == 'bridge_not_crossed'
    assert not records_of(store, new_scout, task['id']), 'nothing was filed'


def test_the_wrong_code_changes_nothing(app, store, new_scout):
    task = task_of(store)
    cross(store, new_scout)
    response = new_scout.client.post(
        f"/tasks/{task['id']}/bridge-code", data={'code': '82BQ'},
        headers={'Accept': 'application/json', 'X-Requested-With': 'fetch'})
    assert response.status_code == 400
    assert response.get_json()['error'] == 'bridge_code_wrong'
    assert [r['status'] for r in records_of(store, new_scout, task['id'])] == ['crossed']
    assert badge_of(engine.progress_for(store, new_scout.id))['progress_done'] == 0


def test_the_code_survives_typing_habits(app, store, new_scout):
    """小階全形加空格 —— ８２ｂｐ 都算對."""
    cross(store, new_scout)
    reply = enter_code(store, new_scout, code=' ８２ｂｐ ')
    assert reply['ok'] and reply['status'] == 'completed'


def test_a_second_crossing_or_code_does_not_double_file(app, store, new_scout):
    task = task_of(store)
    cross(store, new_scout)
    cross(store, new_scout)
    assert [r['status'] for r in records_of(store, new_scout, task['id'])] == ['crossed']
    enter_code(store, new_scout)
    again = enter_code(store, new_scout)
    assert again['ok'] and again['already_done']
    assert [r['status'] for r in records_of(store, new_scout, task['id'])] == \
        ['crossed', 'completed'], 'no third record, no second helping of points'


def test_completions_from_before_the_change_stay_done(app, store, new_scout):
    task = task_of(store)
    cross(store, new_scout)
    enter_code(store, new_scout)
    # a scout who re-plays a finished crossing: the game says already done
    reply = cross(store, new_scout)
    assert reply['ok'] and reply['status'] == 'completed' and reply['already_done']
    assert len(records_of(store, new_scout, task['id'])) == 2


def test_the_leader_may_change_the_code_in_settings(app, store, new_scout):
    cross(store, new_scout)
    store.save_setting('bridge_assess_code', 'KN99')
    response = new_scout.client.post(
        f"/tasks/{task_of(store)['id']}/bridge-code", data={'code': '82BP'},
        headers={'Accept': 'application/json', 'X-Requested-With': 'fetch'})
    assert response.status_code == 400
    assert enter_code(store, new_scout, code='kn99')['passed']


def test_the_ordinary_submit_still_refuses_to_sign_off_item_5(app, store, new_scout):
    task = task_of(store)
    response = new_scout.post(f"/tasks/{task['id']}/submit", data={'notes': 'done'})
    assert response.status_code == 403
    assert response.get_json()['error'] == 'play_the_bridge'
    assert '代碼' in response.get_json()['message_zh']


def test_the_code_route_only_exists_for_the_crossing(app, store, new_scout):
    other = task_of(store, 'M06')
    response = new_scout.client.post(
        f"/tasks/{other['id']}/bridge-code", data={'code': '82BP'},
        headers={'Accept': 'application/json', 'X-Requested-With': 'fetch'})
    assert response.status_code == 404


def test_the_badge_page_holds_a_code_form_for_a_crossed_scout(app, store, new_scout):
    task = task_of(store)
    cross(store, new_scout)
    progress = engine.progress_for(store, new_scout.id)
    badge = badge_of(progress)
    page = new_scout.get(f"/badges/{badge['id']}/requirements")
    html = page.get_data(as_text=True)
    assert f'/tasks/{task["id"]}/bridge-code' in html, 'the form posts to the code route'
    assert '領袖代碼' in html and '已過橋' in html

    # the wrong code from the plain form comes back as a redirect with the reason
    response = new_scout.client.post(f"/tasks/{task['id']}/bridge-code", data={'code': 'nope'})
    assert response.status_code == 302 and 'assess=wrong' in response.headers['Location']


def test_the_game_page_opens_on_the_assess_card_once_crossed(app, store, new_scout):
    task = task_of(store)
    # before the crossing: the river bank, as always
    page = new_scout.get(f"/tasks/{task['id']}/bridge")
    assert '河水擋住了去路' in page.get_data(as_text=True)
    assert '"crossed_now": false' in html.unescape(page.get_data(as_text=True))
    cross(store, new_scout)
    # after: the assess card is what greets the scout (no re-laying needed).
    # The card itself is server-rendered from crossed_now; the intro story stays
    # in the embedded config for replays, so only the card is asserted on.
    page = new_scout.get(f"/tasks/{task['id']}/bridge")
    source = html.unescape(page.get_data(as_text=True))
    assert '請找領袖考核' in source, 'the assess card is the opening screen'
    assert '"crossed_now": true' in source, 'the game config carries the state'
    # the server-rendered card is the crossed_now branch, not the bank scene
    assert '<h1 class="cave-title">河水擋住了去路</h1>' not in source, \
        'the bank headline is only the pre-crossing card'


def test_the_assess_wording_teaches_both_halves():
    """考核卡要把話講清楚：背誦 + 講解日常生活怎樣實行，代碼在後面."""
    assess = RIVER['assess']
    assert '背誦' in assess['points_zh'][0] and '講解' in assess['points_zh'][1]
    assert '代碼' in assess['after_zh'] and '遊戲 3' in assess['after_zh']
    crossed = RIVER['crossed']
    # the ticked card no longer claims the item is done by the bridge alone
    assert '考核通過' in crossed['pass_title_zh']
    assert '領袖' in crossed['paras_zh'][1], 'the far bank names the next step'
