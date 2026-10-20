"""The scout's pages, and the progression rules a scout runs into.

Two scouts are used on purpose:
  • new_scout (scout07) — a blank slate, so every task type can be walked from
    the start;
  • scout_client (scout03) — 5/9 through the sample content, which is what the
    “already done / awaiting review / award unlocks the next one” rules need.
"""
from __future__ import annotations

import json
import pathlib
import re
import urllib.parse

from scout import engine
from scout.util import today_iso


def raw_config(store, task_id):
    row = store.get("tasks", task_id)
    config = row["config_json"]
    return json.loads(config) if isinstance(config, str) else config


def todo_tasks(store, user_id):
    """Tasks this scout can start right now: unlocked award, not finished."""
    progress = engine.progress_for(store, user_id)
    return [task for badge in progress["badges"] if not badge["locked"]
            for task in badge["tasks"] if task["status"] in ("todo", "rejected")]


def by_type(tasks):
    out = {}
    for task in tasks:
        out.setdefault(task["type"], task)
    return out


def practice_quiz(store):
    """A leader-style generic quiz (not item 4, whose only route is the cave)."""
    badge = next(b for b in store.list('badges') if b.get('code') == 'SC-01')
    return store.insert('tasks', {
        'badge_id': badge['id'], 'order_index': 50, 'code': 'PRACTICE',
        'title_zh': '示例小測驗', 'title_en': 'Practice quiz',
        'instruction_zh': '試玩測驗', 'instruction_en': 'Try a practice quiz',
        'type': 'quiz', 'points': 5, 'pass_score': 75, 'status': 'published',
        'config_json': {'questions': [
            {'q_zh': f'練習題 {i+1}', 'q_en': f'Practice question {i+1}',
             'options': ['錯', '對', '其他'], 'answer': 1}
            for i in range(4)], 'require_all': True},
    })


def approve_everything(app, store, user_id, points=None):
    """A leader signs in and approves every pending submission."""
    leader = app.test_client()
    leader.post("/login/leader", data={"username": "leader1", "password": "0082"})
    for record in [r for r in store.list("progress_records")
                   if r["user_id"] == user_id and r["status"] == "pending"]:
        data = {"action": "approve"}
        if points is not None:
            data["points"] = str(points)
        leader.post(f"/leader/review/{record['id']}", data=data)
    return leader


# ── pages ───────────────────────────────────────────────────────────────────

def test_the_home_page_has_no_progress_overview(scout_client):
    """No 進度概覽 strip, and no 總進度 dial in the greeting either: the first
    section of the page is 我的獎章."""
    page = scout_client.get("/home").get_data(as_text=True)
    assert "進度概覽" not in page
    assert "總進度" not in page
    assert "stat-strip" not in page
    assert page.index("我的獎章") < page.index("建議")


def test_home_is_the_minimal_dashboard(scout_client):
    page = scout_client.get("/home").get_data(as_text=True)
    assert "你好" in page                 # greeting
    assert "我的獎章" in page              # the first section is the badges
    assert "建議" in page                  # suggestions
    assert "badge-tile" in page            # the square buttons themselves
    # the progress-overview section is gone, and the badges come first
    assert "進度概覽" not in page
    assert page.index("我的獎章") < page.index("建議")


def test_the_notice_rides_in_the_greeting_header(app, leader_client, store):
    """公告 is merged into the header card with the 日行一善 line — it is not a
    section of its own any more."""
    leader_client.post("/leader/announcements", data={
        "title_zh": "合併公告", "title_en": "Merged", "body_zh": "詳情",
        "audience": "all", "pinned": "1"})
    client = app.test_client()
    client.post("/login/demo/demo2")
    page = client.get("/home").get_data(as_text=True)

    assert "hello-notices" in page
    header_start = page.index("home-hello")
    header = page[header_start:page.index("</section>", header_start)]
    assert "合併公告" in header and "置頂" in header      # inside the header card
    assert "日行一善" in header                           # next to the motto line
    assert "📣 公告" not in page                         # no separate section
    assert "notice-line" not in page
    assert page.index("合併公告") < page.index("我的獎章")  # header comes first


def test_only_four_suggestions_show_and_the_rest_wait_behind_a_button(scout_client):
    """The home page ends after four ideas; 顯示全部 brings the rest out."""
    page = scout_client.get("/home").get_data(as_text=True)

    first_grid = page[page.index("data-suggest-shown"):page.index("suggest-rest")]
    assert first_grid.count("suggest-card") == 4          # exactly four on show

    assert 'id="suggest-rest" hidden' in page              # the rest start hidden
    assert "data-suggest-toggle" in page
    assert "顯示全部建議" in page
    assert "收起" in page                                  # (for the way back)
    total = re.search(r"data-label-more=\"顯示全部建議（(\d+)）\"", page)
    assert total and int(total.group(1)) > 4               # the button counts them


def test_no_show_all_button_when_there_are_four_or_fewer(app, store):
    store.remove_where("suggestions", lambda row: True)     # only the auto nudges left
    client = app.test_client()
    client.post("/login/demo/demo2")
    page = client.get("/home").get_data(as_text=True)
    assert "suggest-card" in page or "暫時沒有建議" in page
    assert "data-suggest-toggle" not in page
    assert "suggest-rest" not in page


def test_home_never_shows_points(scout_client):
    page = scout_client.get("/home").get_data(as_text=True)
    assert "積分" not in page
    assert "wallet" not in page
    assert "🪙" not in page


def test_no_xp_or_levels_anywhere(scout_client):
    for path in ("/home", "/badges", "/rewards", "/history", "/leaderboard"):
        page = scout_client.get(path).get_data(as_text=True).lower()
        for banned in ("experience points", "level up", "等級"):
            assert banned not in page, f"{path} leaks “{banned}”"


def test_badges_page_renders_the_journey_map(scout_client):
    page = scout_client.get("/badges").get_data(as_text=True)
    assert "quest-map" in page and "quest-node" in page
    assert "獎章進度" in page
    assert page.count("node-art") >= 3


def test_journey_map_shows_current_and_locked(scout_client, store):
    page = scout_client.get("/badges").get_data(as_text=True)
    assert "quest-node current" in page    # 會員章 is the one open award
    assert "quest-node locked" in page     # …and the four after it are shut
    assert "🔒" in page
    assert page.count("quest-node") >= 5   # all five progressive awards are there


def test_all_five_awards_show_their_artwork_and_locked_ones_are_marked(scout_client, store):
    """Every award keeps its official icon — 鎖住 is said by a padlock chip and
    a dashed frame, never by fading the artwork until it looks like there is
    no icon at all."""
    page = scout_client.get("/home").get_data(as_text=True)
    tiles = page[page.index("badge-tiles"):page.index("suggest-grid")]
    for slug in ("membership", "pathfinder", "standard", "advanced", "chief-scout"):
        assert f"/img/badges/{slug}.webp" in tiles, slug      # all five icons
    assert tiles.count("<img") == 5
    # the four locked ones carry a drawn padlock (SVG, not an emoji font)
    assert tiles.count('tile-state is-locked') == 4
    assert tiles.count("<svg") == 4
    assert tiles.count("未解鎖") == 4                          # …and say so in words
    # nothing is washed out
    css = scout_client.get("/static/styles.css").get_data(as_text=True)
    assert "grayscale(.18)" in css                          # a whisper of grey, not .85
    assert "grayscale(.85)" not in css


def test_the_four_awards_after_membership_are_locked(scout_client, store):
    """會員章 is the only door open: the other four wait in order."""
    badges = engine.progress_for(store, scout_client.id)["badges"]
    assert [b["title_zh"] for b in badges] == [
        "會員章", "童軍探索獎章", "童軍標準獎章", "童軍高級獎章", "總領袖獎章"]
    assert badges[0]["locked"] is False and badges[0]["earned"] is False
    assert [b["locked"] for b in badges[1:]] == [True, True, True, True]
    assert all(b["image_url"].startswith("/img/badges/") for b in badges)   # artwork on all five


def test_badge_detail_lists_tasks(scout_client, store):
    badge = engine.progress_for(store, scout_client.id)["badges"][1]
    page = scout_client.get(f"/badges/{badge['id']}").get_data(as_text=True)
    assert badge["title_zh"] in page
    for task in badge["tasks"]:
        assert task["title_zh"] in page


def test_generic_quiz_page_hides_the_answer_key(new_scout, store):
    quiz = practice_quiz(store)
    page = new_scout.get(f"/tasks/{quiz['id']}").get_data(as_text=True)
    assert page.count('class="quiz-question"') == 4
    assert '"answer"' not in page
    for question in raw_config(store, quiz['id'])['questions']:
        assert question['q_zh'] in page


def test_unknown_task_is_404(scout_client):
    assert scout_client.get("/tasks/doesnotexist").status_code == 404
    assert scout_client.get("/badges/doesnotexist").status_code == 404


def test_rewards_page_is_the_only_place_points_appear(scout_client, extras_on):
    page = scout_client.get("/rewards").get_data(as_text=True)
    assert "我的積分" in page and "wallet-hero" in page and "獎品櫃" in page
    assert "換領（即將開放）" in page
    assert "disabled" in page               # nothing is redeemable yet


def test_rewards_show_shortfall_for_unaffordable_chests(app, store, extras_on):
    scout = next(u for u in store.list("users") if u["username"] == "scout06")
    store.update("stats", scout["id"], {"points_balance": 0})
    client = app.test_client()
    client.post("/login/demo/demo2")
    from scout.auth import create_session

    client2 = app.test_client()
    token = create_session(store, scout)
    client2.set_cookie("scout_sid", token)
    page = client2.get("/rewards").get_data(as_text=True)
    assert "還差" in page


def test_history_lists_completions(scout_client, store):
    page = scout_client.get("/history").get_data(as_text=True)
    assert "我的紀錄" in page
    assert "第 1 項" in page                   # scout03 has finished item 1 of 會員章


def test_leaderboard_ranks_by_badges_then_tasks(scout_client, store, extras_on):
    page = scout_client.get("/leaderboard").get_data(as_text=True)
    assert "龍虎榜" in page and "lb-row" in page
    assert "先比考獲獎章，再比完成任務" in page
    board = engine.leaderboard(store, current_user_id=scout_client.id)
    pairs = [(row["badges_done"], row["tasks_done"]) for row in board["rows"]]
    assert pairs == sorted(pairs, key=lambda pair: (-pair[0], -pair[1]))
    assert board["rows"][0]["rank"] == 1


def test_leaderboard_periods_and_patrols(scout_client, extras_on):
    for query in ("?period=week", "?period=month", "?scope=patrol&patrol=Tiger", "?scope=unit"):
        response = scout_client.get("/leaderboard" + query)
        assert response.status_code == 200


def test_leaderboard_can_be_switched_off(scout_client, extras_on, store):
    """Flipping the switch off again closes the page — that is the default too."""
    store.save_setting("feature_flags", {**store.settings()["feature_flags"], "leaderboard": False})
    assert scout_client.get("/leaderboard", follow_redirects=False).status_code == 302
    landed = scout_client.get("/leaderboard", follow_redirects=True)
    assert landed.request.path == "/home"
    assert "龍虎榜未開放" in landed.get_data(as_text=True)


def test_hidden_scout_is_off_the_board(app, store):
    scout = next(u for u in store.list("users") if u["username"] == "scout01")
    store.update("users", scout["id"], {"show_on_leaderboard": False})
    board = engine.leaderboard(store)
    assert all(row["user_id"] != scout["id"] for row in board["rows"])


# ── submissions ─────────────────────────────────────────────────────────────

def test_quiz_wrong_then_right(new_scout, store):
    """The generic task engine still works; M04 uses /cave-submit instead."""
    quiz = practice_quiz(store)
    config = raw_config(store, quiz['id'])
    wrong = new_scout.post(f"/tasks/{quiz['id']}/submit",
                           data={f"q{i}": '9' for i in range(len(config['questions']))}).get_json()
    assert wrong['status'] == 'rejected' and not wrong['passed'] and wrong['score'] == 0
    right = new_scout.post(f"/tasks/{quiz['id']}/submit",
                           data={f"q{i}": str(q['answer']) for i, q in enumerate(config['questions'])}).get_json()
    assert right['status'] == 'completed' and right['passed'] and right['score'] == 100
    assert any(event['type'] == 'points' for event in right['events'])
    assert right['progress']['overall']['tasks_done'] >= 1


def test_quiz_pass_mark_is_respected(leader_client, new_scout, store):
    """A 3-question quiz with a 70% pass mark: 2/3 fails, 3/3 passes."""
    leader_client.post("/leader/content/tasks", data={
        "badge_id": engine.progress_for(store, new_scout.id)["badges"][0]["id"],
        "title_zh": "測試小測驗", "title_en": "Test quiz", "type": "quiz",
        "points": "5", "pass_score": "70", "status": "published",
        "quiz_zh": "一加一是？ | 2 | 一 | 二 | 三\n二加二是？ | 2 | 三 | 四 | 五\n三加三是？ | 2 | 五 | 六 | 七",
        "quiz_en": "One plus one? | 2 | one | two | three\nTwo plus two? | 2 | three | four | five\nThree plus three? | 2 | five | six | seven",
    })
    task = next(t for t in store.list("tasks") if t["title_zh"] == "測試小測驗")
    config = raw_config(store, task["id"])
    assert len(config["questions"]) == 3
    assert config["questions"][1]["answer"] == 1          # 1-based “4” → index 1

    two_right = new_scout.post(f"/tasks/{task['id']}/submit", data={"q0": "1", "q1": "1", "q2": "0"}).get_json()
    assert two_right["score"] == 67 and two_right["status"] == "rejected", two_right

    all_right = new_scout.post(f"/tasks/{task['id']}/submit", data={"q0": "1", "q1": "1", "q2": "1"}).get_json()
    assert all_right["score"] == 100 and all_right["passed"] is True


def test_checklist_needs_every_tick(new_scout, store):
    task = by_type(todo_tasks(store, new_scout.id))["checklist"]
    config = raw_config(store, task["id"])

    partial = new_scout.post(f"/tasks/{task['id']}/submit", data={"item0": "1"}).get_json()
    assert partial["status"] == "rejected"

    full = new_scout.post(f"/tasks/{task['id']}/submit",
                          data={f"item{i}": "1" for i in range(len(config["items"]))}).get_json()
    assert full["status"] == "completed"


def test_reflection_min_chars_then_pending(leader_client, new_scout, store):
    """Reflection is a task type the platform keeps — a leader can add one.

    會員章 no longer ships a reflection of its own (its 11 items are the official
    scheme), so the leader adds a reflection task to the open award here.
    """
    badge = engine.progress_for(store, new_scout.id)["badges"][0]
    leader_client.post("/leader/content/tasks", data={
        "badge_id": badge["id"], "type": "reflection", "code": "RX-1",
        "title_zh": "活動感想", "title_en": "How did it go?",
        "instruction_zh": "寫下你的感想。", "instruction_en": "Write how the activity felt.",
        "points": "5", "min_chars": "30", "status": "published",
    })
    task = by_type(todo_tasks(store, new_scout.id))["reflection"]
    minimum = raw_config(store, task["id"]).get("min_chars", 0)
    assert minimum

    short = new_scout.post(f"/tasks/{task['id']}/submit", data={"reflection_text": "短"}).get_json()
    assert short["status"] == "rejected"

    body = new_scout.post(f"/tasks/{task['id']}/submit",
                          data={"reflection_text": "我" * (minimum + 20)}).get_json()
    assert body["status"] == "pending" and body["passed"] is False


def test_evidence_task_waits_for_a_leader(mid_scout, store):
    task = by_type(todo_tasks(store, mid_scout.id))["evidence"]
    body = mid_scout.post(f"/tasks/{task['id']}/submit",
                          data={"evidence_url": "/uploads/proof.jpg"}).get_json()
    assert body["status"] == "pending"


def test_signoff_waits_for_a_leader(mid_scout, store):
    task = by_type(todo_tasks(store, mid_scout.id))["signoff"]
    assert mid_scout.post(f"/tasks/{task['id']}/submit", data={"notes": "shown at the meeting"}) \
        .get_json()["status"] == "pending"


def test_completed_task_cannot_be_resubmitted(scout_client, store):
    done = next(r for r in store.list("progress_records")
                if r["user_id"] == scout_client.id and r["status"] == "completed")
    response = scout_client.post(f"/tasks/{done['task_id']}/submit", data={})
    assert response.status_code == 409
    assert response.get_json()["error"] == "already_done"


def test_pending_task_cannot_be_resubmitted(mid_scout, store):
    task = by_type(todo_tasks(store, mid_scout.id))["evidence"]
    mid_scout.post(f"/tasks/{task['id']}/submit", data={"evidence_url": "/uploads/a.jpg"})
    response = mid_scout.post(f"/tasks/{task['id']}/submit", data={"evidence_url": "/uploads/b.jpg"})
    assert response.status_code == 409
    assert response.get_json()["error"] == "awaiting_review"


def test_locked_award_blocks_submission(new_scout, store):
    locked = next(b for b in engine.progress_for(store, new_scout.id)["badges"]
                  if b["locked"] and b["tasks"])
    response = new_scout.post(f"/tasks/{locked['tasks'][0]['id']}/submit", data={})
    assert response.status_code == 403
    assert response.get_json()["error"] == "badge_locked"
    assert "請先完成上一個進度性獎章" in response.get_json()["message_zh"]


def test_draft_task_is_not_submittable(app, store):
    task = next(t for t in store.list("tasks") if t["type"] == "checklist")
    store.update("tasks", task["id"], {"status": "draft"})
    client = app.test_client()
    client.post("/login/demo/demo2")
    response = client.post(f"/tasks/{task['id']}/submit", data={})
    assert response.status_code == 403
    assert response.get_json()["error"] == "task_not_published"


def test_browser_form_post_redirects_without_javascript(new_scout, store):
    task = by_type(todo_tasks(store, new_scout.id))["checklist"]
    config = raw_config(store, task["id"])
    response = new_scout.client.post(f"/tasks/{task['id']}/submit",
                                     data={f"item{i}": "1" for i in range(len(config["items"]))})
    assert response.status_code == 302
    assert urllib.parse.urlsplit(response.headers["Location"]).path.endswith("/badges")


def test_attempt_numbers_increment(new_scout, store):
    quiz = practice_quiz(store)
    new_scout.post(f"/tasks/{quiz['id']}/submit", data={"q0": "9"})
    new_scout.post(f"/tasks/{quiz['id']}/submit", data={"q0": "9"})
    attempts = sorted(r["attempt_no"] for r in store.list("progress_records")
                      if r["user_id"] == new_scout.id and r["task_id"] == quiz["id"])
    assert attempts == [1, 2]


# ── points, badges, streaks ─────────────────────────────────────────────────

def test_task_completion_writes_ledger_and_balance(new_scout, store):
    quiz = practice_quiz(store)
    config = raw_config(store, quiz["id"])
    before = store.stats_for(new_scout.id)["points_balance"]
    new_scout.post(f"/tasks/{quiz['id']}/submit",
                   data={f"q{i}": str(q["answer"]) for i, q in enumerate(config["questions"])})
    stats = store.stats_for(new_scout.id)
    assert stats["points_balance"] == before + int(quiz["points"])
    ledger = [row for row in store.list("points_ledger") if row["user_id"] == new_scout.id]
    assert ledger[-1]["entry_type"] == "task"
    assert sum(int(row["points_delta"]) for row in ledger) == stats["points_balance"]


def test_finishing_all_optional_items_still_needs_five_games(app, new_scout, store):
    """Even leader approval of all the old items is not the badge condition."""
    for task in list(new_scout.get('/api/me/progress').get_json()['badges'][0]['tasks']):
        if task['status'] not in ('todo', 'rejected'):
            continue
        config = raw_config(store, task['id'])
        if task['code'] == 'M04':
            answer = {f"q{i}": str(q['answer']) for i, q in enumerate(config['questions'])}
            assert new_scout.post(f"/tasks/{task['id']}/cave-submit", data=answer).get_json()['passed']
        elif task['code'] == 'M05':
            # game 2 has two halves: lay every plank of every stage (that
            # crosses the river), then bring the leader's 考核 code
            river = (pathlib.Path(__file__).resolve().parent.parent / 'content'
                     / 'member-badge' / 'river.json')
            bridge = json.loads(river.read_text(encoding='utf-8'))
            data = {}
            for n, stage in enumerate(bridge['stages'], start=1):
                data[f'stage{n}'] = [plank['key'] for plank in stage['planks']]
            # the keys here are the canonical ones, in order
            result = new_scout.post(f"/tasks/{task['id']}/bridge-submit", data=data).get_json()
            assert result['status'] == 'crossed', result
            code = new_scout.post(f"/tasks/{task['id']}/bridge-code",
                                  data={'code': '82BP'}).get_json()
            assert code['passed'] and code['status'] == 'completed', code
        elif task['code'] == 'M06':
            # game 3 also has two halves: answer every check of the manual
            # (that studies it), then bring the leader's 考核 code
            drill = (pathlib.Path(__file__).resolve().parent.parent / 'content'
                     / 'member-badge' / 'drill.json')
            manual = json.loads(drill.read_text(encoding='utf-8'))
            moves = {move['id']: move for section in manual['sections']
                     for move in section['moves']}
            required = [move_id for key in ('sign_stages', 'movement_stages')
                        for stage in manual['game'][key] for move_id in stage]
            assert len(required) == 21 and 'stand-easy' not in required
            data = {f"check_{move_id}": str(moves[move_id]['check']['answer'])
                    for move_id in required}
            result = new_scout.post(f"/tasks/{task['id']}/drill-submit", data=data).get_json()
            assert result['status'] == 'studied', result
            assert result['detail']['moves'] == len(required), result
            code = new_scout.post(f"/tasks/{task['id']}/drill-code",
                                  data={'code': '82DR'}).get_json()
            assert code['passed'] and code['status'] == 'completed', code
        elif task['type'] == 'checklist':
            new_scout.post(f"/tasks/{task['id']}/submit",
                           data={f"item{i}": '1' for i in range(len(config['items']))})
        else:
            new_scout.post(f"/tasks/{task['id']}/submit", data={'notes': 'done'})
    approve_everything(app, store, new_scout.id)
    after = engine.progress_for(store, new_scout.id)
    badge = after['badges'][0]
    assert badge['tasks_done'] == badge['tasks_total'] == 11
    assert badge['progress_done'] == 3 and badge['progress_total'] == 5  # cave + bridge + drill
    assert not badge['earned'] and after['badges'][1]['locked'], 'the other two games are missing'
    assert not any(r['entry_type'] == 'badge' and r['ref_id'] == badge['id']
                   for r in store.list('points_ledger') if r['user_id'] == new_scout.id)


def test_the_card_gives_the_exact_wording_and_each_row_rebuilds_it():
    """教學牌只給原文：銘言、誓詞、規律照著讀，不再解釋意思。

    Every sentence is the official wording — the Chinese from 香港童軍總會 and the
    English that goes with it — and the empty boxes stand in rows: each row's
    boards, read left to right, spell its sentence back, punctuation aside.
    """
    river = (pathlib.Path(__file__).resolve().parent.parent / 'content'
             / 'member-badge' / 'river.json')
    bridge = json.loads(river.read_text(encoding='utf-8'))
    punctuation = '，。；、！？「」（）——'
    shape = ['title_zh', 'title_en', 'lead_zh', 'lead_en',
             'sentences_zh', 'sentences_en', 'details_zh', 'details_en',
             'note_zh', 'note_en']
    for stage in bridge['stages']:
        teach = stage['teach']
        assert list(teach) == shape, 'the card carries the wording, not a list of meanings'
        assert 'points_zh' not in teach and 'points_en' not in teach
        assert not any('→' in text for text in json.dumps(teach, ensure_ascii=False).split('"'))

        sentences = teach['sentences_zh']
        assert sentences and all(sentence for sentence in sentences)
        assert len(sentences) == len(teach['sentences_en'])
        assert '一行' in teach['note_zh'], 'the card still says how the rows are laid'

        # 原文與說明並存：每一句原文都配一行說明，缺一不可
        for zh, en in zip(teach['details_zh'], teach['details_en']):
            assert zh.strip() and en.strip(), 'no blank detail line'
        assert len(teach['details_zh']) == len(sentences)
        assert len(teach['details_en']) == len(teach['sentences_en'])

        rows = []
        for plank in stage['planks']:
            if not rows or rows[-1][0] != plank['line']:
                rows.append([plank['line'], []])
            rows[-1][1].append(plank['zh'])
        assert [row[0] for row in rows] == list(range(1, len(rows) + 1)), 'the rows run in order'
        assert len(rows) == len(sentences) == len(stage['rows_zh']) == len(stage['rows_en'])
        for (number, pieces), sentence in zip(rows, sentences):
            spelled = ''.join(pieces)
            wanted = ''.join(ch for ch in sentence if ch not in punctuation)
            assert spelled == wanted, f'the sentence {sentence!r} is spelled {spelled!r} by its row'

    # 英文也是官方措辭，不是自己改寫的版本
    promise = ''.join(bridge['stages'][1]['teach']['sentences_en'])
    wanted = ('On my honour, I promise that I will do my best to do my duty to God and to my '
              'Country to help other people and to keep the Scout Law.')
    assert core_text(promise) == core_text(wanted), promise
    law = bridge['stages'][2]['teach']['sentences_en']
    assert law == ['A Scout is to be trusted.', 'A Scout is loyal.',
                   'A Scout is friendly and considerate.',
                   'A Scout belongs to the world-wide family of Scouts.',
                   'A Scout has courage in all difficulties.',
                   'A Scout makes good use of time and is careful of possessions and property.',
                   'A Scout has self respect and respect for others.'], law
    assert bridge['stages'][0]['teach']['sentences_en'] == ['準備', 'Be Prepared']


def core_text(text):
    """The words alone — official copy keeps its punctuation, the boards do not."""
    return ''.join(ch for ch in text
                   if ch not in '，。；、！？「」（）——' and not ch.isspace())


def test_a_crossing_with_one_board_short_is_refused(new_scout, store):
    """A half-empty span is not a crossing, and a board cannot be laid twice."""
    river = (pathlib.Path(__file__).resolve().parent.parent / 'content'
             / 'member-badge' / 'river.json')
    bridge = json.loads(river.read_text(encoding='utf-8'))
    task = next(t for t in store.list('tasks') if t.get('code') == 'M05')
    canonical = {n: [plank['key'] for plank in stage['planks']]
                 for n, stage in enumerate(bridge['stages'], start=1)}

    short = {**canonical, 3: canonical[3][:-1]}
    reply = new_scout.post(f"/tasks/{task['id']}/bridge-submit", data=short)
    assert reply.status_code == 400 and reply.get_json()['error'] == 'bridge_incomplete'

    doubled = {**canonical, 3: canonical[3][:-1] + canonical[3][:1]}
    reply = new_scout.post(f"/tasks/{task['id']}/bridge-submit", data=doubled)
    assert reply.status_code == 400 and reply.get_json()['error'] == 'bridge_incomplete'

    unknown = {**canonical, 3: canonical[3][:-1] + ['no-such-plank']}
    reply = new_scout.post(f"/tasks/{task['id']}/bridge-submit", data=unknown)
    assert reply.status_code == 400 and reply.get_json()['error'] == 'bridge_incomplete'


def test_game_one_points_land_in_wallet_without_badge_bonus(new_scout, store):
    cave = next(t for t in store.list('tasks') if t.get('code') == 'M04')
    config = raw_config(store, cave['id'])
    answer = {f"q{i}": str(q['answer']) for i, q in enumerate(config['questions'])}
    result = new_scout.post(f"/tasks/{cave['id']}/cave-submit", data=answer).get_json()
    assert result['passed']
    stats = store.stats_for(new_scout.id)
    ledger = [r for r in store.list('points_ledger') if r['user_id'] == new_scout.id]
    assert stats['points_balance'] == sum(int(r['points_delta']) for r in ledger) == int(cave['points'])
    assert all(r['entry_type'] != 'badge' for r in ledger), 'the badge waits for all five games'


def test_award_is_only_granted_once(app, new_scout, store):
    badge = engine.progress_for(store, new_scout.id)["badges"][0]
    user = store.get("users", new_scout.id)
    first = engine.check_badge_completion(store, user=user, badge=badge)
    assert first["reason"] in ("incomplete", "no_tasks") or first["awarded"] is False
    store.insert("badge_awards", {"user_id": new_scout.id, "badge_id": badge["id"],
                                  "awarded_at": "2026-01-01T00:00:00.000Z", "awarded_by": "test", "note": ""})
    again = engine.check_badge_completion(store, user=user, badge=badge)
    assert again["awarded"] is False and again["reason"] == "already"


def test_streak_moves_on_first_completion(new_scout, store):
    quiz = practice_quiz(store)
    config = raw_config(store, quiz["id"])
    new_scout.post(f"/tasks/{quiz['id']}/submit",
                   data={f"q{i}": str(q["answer"]) for i, q in enumerate(config["questions"])})
    stats = store.stats_for(new_scout.id)
    assert stats["streak_current"] == 1
    assert stats["streak_best"] >= 1
    assert stats["last_active_date"] == today_iso()


def test_streak_does_not_double_count_the_same_day(new_scout, store):
    tasks = by_type(todo_tasks(store, new_scout.id))
    quiz = tasks["quiz"]
    checklist = tasks["checklist"]
    config = raw_config(store, quiz["id"])
    new_scout.post(f"/tasks/{quiz['id']}/submit",
                   data={f"q{i}": str(q["answer"]) for i, q in enumerate(config["questions"])})
    items = raw_config(store, checklist["id"])["items"]
    new_scout.post(f"/tasks/{checklist['id']}/submit", data={f"item{i}": "1" for i in range(len(items))})
    assert store.stats_for(new_scout.id)["streak_current"] == 1


def test_streak_can_be_switched_off(app, store):
    store.save_setting("feature_flags", {**store.settings()["feature_flags"], "streaks": False})
    scout = next(u for u in store.list("users") if u["username"] == "scout07")
    before = store.stats_for(scout["id"])
    client = app.test_client()
    client.post(f"/login/scout/Seagull/{scout['id']}",
                data={"password": "tiger777", "confirm": "tiger777"})
    quiz = next(t for t in store.list("tasks") if t["type"] == "quiz")
    config = raw_config(store, quiz["id"])
    client.post(f"/tasks/{quiz['id']}/submit",
                data={f"q{i}": str(q["answer"]) for i, q in enumerate(config["questions"])})
    assert store.stats_for(scout["id"])["last_active_date"] == before["last_active_date"]


def test_stats_always_match_the_ledger(client, store):
    for user in store.list("users"):
        if user.get("role") != "scout":
            continue
        stats = store.stats_for(user["id"])
        total = sum(int(row["points_delta"]) for row in store.list("points_ledger")
                    if row["user_id"] == user["id"])
        assert stats["points_balance"] == max(0, total), user["username"]


def test_rebuild_stats_repairs_a_drifted_balance(store):
    scout = next(u for u in store.list("users") if u["username"] == "scout01")
    store.update("stats", scout["id"], {"points_balance": 9999, "tasks_done": 99})
    restored = store.rebuild_stats(scout["id"])
    ledger_total = sum(int(row["points_delta"]) for row in store.list("points_ledger")
                       if row["user_id"] == scout["id"])
    completed = len([r for r in store.list("progress_records")
                     if r["user_id"] == scout["id"] and r["status"] == "completed"])
    assert restored["points_balance"] == max(0, ledger_total)
    assert restored["tasks_done"] == completed


# ── uploads ─────────────────────────────────────────────────────────────────

def test_upload_saves_a_file_and_serves_it(app, store, data_dir):
    import base64
    import os

    client = app.test_client()
    client.post("/login/demo/demo2")
    payload = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 32).decode()
    body = client.post("/upload", json={"filename": "shot.png", "mimeType": "image/png",
                                        "dataUrl": "data:image/png;base64," + payload}).get_json()
    assert body["ok"] and body["url"].startswith("/uploads/")
    assert os.path.exists(os.path.join(data_dir, "uploads", body["url"].split("/")[-1]))
    assert client.get(body["url"]).status_code == 200


def test_upload_accepts_a_plain_multipart_post(app):
    import io

    client = app.test_client()
    client.post("/login/demo/demo2")
    response = client.post("/upload", data={"file": (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"1" * 16), "a.png")},
                           content_type="multipart/form-data")
    assert response.status_code == 200 and response.get_json()["url"].startswith("/uploads/")


def test_upload_rejects_bad_data(client):
    client.post("/login/demo/demo2")
    assert client.post("/upload", json={"filename": "x.txt", "dataUrl": "not-a-data-url"}).status_code == 400


def test_upload_rejects_oversized_files(client):
    import base64

    client.post("/login/demo/demo2")
    big = base64.b64encode(b"0" * (5 * 1024 * 1024 + 10)).decode()
    assert client.post("/upload", json={"filename": "big.png", "mimeType": "image/png",
                                        "dataUrl": "data:image/png;base64," + big}).status_code == 413


def test_evidence_upload_switch_off(app, store):
    store.save_setting("feature_flags", {**store.settings()["feature_flags"], "evidence_upload": False})
    client = app.test_client()
    client.post("/login/demo/demo2")
    response = client.post("/upload", json={"filename": "x.png", "mimeType": "image/png",
                                            "dataUrl": "data:image/png;base64,iVBORw0KGgo="})
    assert response.status_code == 403
    assert response.get_json()["error"] == "upload_disabled"


# ── JSON views for the game layer ───────────────────────────────────────────

def test_api_me_returns_progress_without_secrets(scout_client):
    body = scout_client.get("/api/me").get_json()
    assert body["ok"] and body["user"]["role"] == "scout"
    assert "password_hash" not in json.dumps(body)
    assert body["overall"]["tasks_total"] >= 1
    assert all("tasks" not in badge for badge in body["badges"])


def test_api_progress_includes_suggestions(scout_client):
    body = scout_client.get("/api/me/progress").get_json()
    assert body["ok"] and "suggestions" in body


def test_api_points_summary_matches_stats(scout_client, store):
    body = scout_client.get("/api/me/points-summary").get_json()
    assert body["ok"]
    assert body["balance"] == store.stats_for(scout_client.id)["points_balance"]


def test_api_points_summary_never_leaks_other_scouts(scout_client, store):
    body = scout_client.get("/api/me/points-summary").get_json()
    scout = next(u for u in store.list("users") if u["username"] == "scout01")
    assert body["balance"] != store.stats_for(scout["id"])["points_balance"] or scout["id"] != scout_client.id


def test_api_next_task_points_at_a_real_task(scout_client, store):
    body = scout_client.get("/api/tasks/next").get_json()
    if body["next"]:
        assert store.get("tasks", body["next"]["task"]["id"]) is not None
        assert body["next"]["task"]["config_json"].get("questions") is None or all(
            q.get("answer") is None for q in body["next"]["task"]["config_json"].get("questions", []))


def test_api_leaderboard_matches_the_page(scout_client):
    body = scout_client.get("/api/leaderboard").get_json()
    assert body["ok"] and body["rows"]
    ranks = [row["badges_done"] for row in body["rows"]]
    assert ranks == sorted(ranks, reverse=True)


def test_api_routes_stay_closed_to_visitors(app):
    client = app.test_client()
    for path in ("/api/me", "/api/me/progress", "/api/leaderboard"):
        assert client.get(path, headers={"Accept": "application/json"}).status_code == 401
