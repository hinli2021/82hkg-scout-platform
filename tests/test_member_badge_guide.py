"""會員章: five location games (first = cave); the official items remain reference.

Playing game 1 covers item 4, with no second exam or automatic item 1 task.
The badge unlocks only after all five distinct area games are cleared.
"""
from __future__ import annotations

import json
import pathlib
import re

import pytest

from scout import engine


def member_badge(store) -> dict:
    return sorted(store.list("badges"), key=lambda b: int(b["order_index"]))[0]


def tasks_of(store, badge) -> list[dict]:
    return sorted([t for t in store.list("tasks") if t["badge_id"] == badge["id"]],
                  key=lambda t: int(t["order_index"]))


def raw_config(store, task_id: str) -> dict:
    row = store.get("tasks", task_id)
    config = row["config_json"]
    return json.loads(config) if isinstance(config, str) else config


@pytest.fixture()
def guide_page(app, store):
    scout = next(u for u in store.list("users") if u["username"] == "scout01")
    client = app.test_client()
    client.post(f"/login/scout/{scout['patrol']}/{scout['id']}", data={"password": "scout1234"})
    badge = member_badge(store)
    # the 11 items in full live at /requirements — /badges/<id> is the game now
    return client.get(f"/badges/{badge['id']}/requirements").get_data(as_text=True)


# ── the guide itself ──────────────────────────────────────────────────────

def test_the_badge_carries_eleven_official_items(store):
    badge = member_badge(store)
    guide = badge.get("guide_json")
    guide = json.loads(guide) if isinstance(guide, str) else guide
    assert guide and len(guide["items"]) == 11
    assert [item["n"] for item in guide["items"]] == list(range(1, 12))
    # every item says what to do, and how it is checked
    for item in guide["items"]:
        assert item["title_zh"] and item["title_en"]
        assert item["req_zh"] and item["req_en"]
        assert item["method"] in ("leader", "self", "event")


def test_the_award_holds_one_task_per_item(store):
    """Eleven items, eleven tasks, in the same order — no gaps."""
    badge = member_badge(store)
    tasks = tasks_of(store, badge)
    guide = badge["guide_json"]
    guide = json.loads(guide) if isinstance(guide, str) else guide
    assert len(tasks) == len(guide["items"]) == 11
    for index, item in enumerate(guide["items"]):
        assert item["n"] == index + 1
        assert tasks[index]["title_zh"].startswith(f"第 {index + 1} 項")


def test_the_guide_page_lists_all_eleven_items(guide_page):
    assert "童軍綱要參考" in guide_page and "不需要另外做試卷" in guide_page
    assert guide_page.count('class="guide-item') == 11
    for n in range(1, 12):
        assert f'data-guide-item="{n}"' in guide_page


def test_the_guide_page_carries_the_units_own_requirements(guide_page):
    # the wording the unit decided on, straight from its reference doc
    assert "24 分／30 分" in guide_page          # items 7–10
    assert "不設合格分數" in guide_page           # cave now clears on completion
    assert "80 分合格" not in guide_page
    assert "六次團集會" in guide_page
    assert "小隊長商議" in guide_page
    assert "兒童侵害" in guide_page              # item 11 of the official scheme


def test_each_item_says_who_checks_it(guide_page):
    for method in ("guide-method-leader", "guide-method-self"):
        assert method in guide_page
    assert "領袖考核" in guide_page


def test_the_links_to_the_papers_and_resources_are_on_the_page(guide_page):
    assert "https://forms.gle/M4vtu6GwsMd5do1J8" not in guide_page      # no item-4 paper
    assert "https://forms.gle/NmdM72WapUpbajFHA" in guide_page          # items 7–10 paper
    assert "drive.google.com/drive/folders/" in guide_page
    assert "香港童軍訓練綱要" in guide_page       # the source is credited


def test_every_guide_row_opens_its_own_task(guide_page, store):
    badge = member_badge(store)
    for task in tasks_of(store, badge):
        suffix = "/cave" if task["code"] == "M04" else ""
        assert f"/tasks/{task['id']}{suffix}" in guide_page


def test_the_later_awards_keep_the_plain_task_list(app, store):
    """The guide belongs to 會員章; the rest of the chain shows tasks as before."""
    scout = next(u for u in store.list("users") if u["username"] == "scout02")
    client = app.test_client()
    client.post(f"/login/scout/{scout['patrol']}/{scout['id']}", data={"password": "scout1234"})
    badge = sorted(store.list("badges"), key=lambda b: int(b["order_index"]))[2]   # 標準獎章
    page = client.get(f"/badges/{badge['id']}").get_data(as_text=True)
    assert "童軍綱要參考" not in page and 'class="guide-item' not in page


# ── item 4: cave only (bank used to score the game) ──────────────────────────────────────────────────────

def test_the_cave_bank_is_fifty_questions_with_an_answer_for_each(store):
    quiz = next(t for t in tasks_of(store, member_badge(store)) if t["type"] == "quiz")
    config = raw_config(store, quiz["id"])
    questions = config["questions"]
    assert len(questions) == 50 and quiz["pass_score"] == 0
    parts = {q["part"] for q in questions}
    assert parts == {"world", "hk", "group"}              # 甲 世界 · 乙 香港 · 丙 本旅
    for question in questions:
        assert isinstance(question["answer"], int)
        assert 0 <= question["answer"] < len(question["options"])
        assert question["explain_zh"]                       # every one is explained


def cave_answers(store, task, *, wrong_every=0):
    questions = raw_config(store, task["id"])["questions"]
    return {f"q{i}": str((q["answer"] + 1) % len(q["options"])
                            if wrong_every and i % wrong_every == 0 else q["answer"])
            for i, q in enumerate(questions)}


def test_item_four_redirects_to_cave_without_a_second_paper(new_scout, store):
    task = next(t for t in tasks_of(store, member_badge(store)) if t["code"] == "M04")
    response = new_scout.get(f"/tasks/{task['id']}")
    assert response.status_code == 302 and response.headers["Location"].split('?')[0].endswith("/cave")
    page = new_scout.get(response.headers["Location"]).get_data(as_text=True)
    assert "50 題" in page and "走到洞口即自動通關" in page and 'data-cave' in page
    assert "80 分合格" not in page
    assert 'class="quiz-question"' not in page and 'data-task-submit' not in page
    forbidden = new_scout.post(f"/tasks/{task['id']}/submit", data=cave_answers(store, task))
    assert forbidden.status_code == 403 and forbidden.get_json()["error"] == "play_the_cave"


def test_below_80_cave_succeeds_without_replaying(new_scout, store):
    task = next(t for t in tasks_of(store, member_badge(store)) if t["code"] == "M04")
    body = new_scout.post(f"/tasks/{task['id']}/cave-submit",
                          data=cave_answers(store, task, wrong_every=4)).get_json()
    assert body["passed"] and body["status"] == "completed" and body["score"] < 80
    records = [r for r in store.list("progress_records")
               if r["task_id"] == task["id"] and r["user_id"] == new_scout.id]
    assert len(records) == 1 and records[0]["status"] == "completed"
    assert records[0]["score"] == body["score"]


def test_a_passed_cave_earns_game_one_and_its_points(new_scout, store):
    task = next(t for t in tasks_of(store, member_badge(store)) if t["code"] == "M04")
    before = store.stats_for(new_scout.id)["points_balance"]
    result = new_scout.post(f"/tasks/{task['id']}/cave-submit",
                            data=cave_answers(store, task)).get_json()
    assert result["passed"] and result["score"] == 100
    progress = engine.progress_for(store, new_scout.id)
    row = next(t for t in progress["badges"][0]["tasks"] if t["code"] == "M04")
    badge = progress["badges"][0]
    assert row["status"] == "completed" and row["score"] == 100
    assert (badge["progress_done"], badge["progress_total"]) == (1, 5)
    assert not badge["earned"], "four more games are required"
    assert store.stats_for(new_scout.id)["points_balance"] == before + task["points"]


def test_a_sample_scout_has_cave_progress_not_a_second_paper(store):
    scout = next(u for u in store.list("users") if u["username"] == "scout02")
    badge = engine.progress_for(store, scout["id"])["badges"][0]
    cave = next(t for t in badge["tasks"] if t["code"] == "M04")
    assert cave["status"] == "completed" and cave["score"] < 100
    assert badge["progress_done"] == 1 and not badge["earned"]


def test_a_leader_notes_item_reaches_the_review_queue(app, store):
    """The 領袖考核 note the scout types is what the leader reads back."""
    scout = next(u for u in store.list("users") if u["username"] == "scout01")
    record = next(r for r in store.list("progress_records")
                  if r["user_id"] == scout["id"] and r["status"] == "pending")
    parent = store.get("tasks", record["task_id"])
    assert parent["type"] == "signoff" and record["reflection_text"]

    leader = app.test_client()
    leader.post("/login/leader", data={"username": "leader1", "password": "0082"})
    page = leader.get("/leader/review").get_data(as_text=True)
    assert record["reflection_text"] in page


def test_a_leader_editing_the_badge_does_not_lose_the_guide(leader_client, store):
    """The guide lives on the badge row — the content editor must not wipe it."""
    badge = member_badge(store)
    before = store.get("badges", badge["id"])["guide_json"]
    assert before

    leader_client.post(f"/leader/content/badges/{badge['id']}",
                       data={"subtitle_zh": "11 項考核", "subtitle_en": "11 items"})
    after = store.get("badges", badge["id"])
    assert after["subtitle_zh"] == "11 項考核"
    assert after["guide_json"] == before, "the 11-item guide is still on the badge"


# ── the adventure ─────────────────────────────────────────────────────────
# 會員章 has ONE page: 玩法 — the island story, the treasure map over the five
# areas. The first game's explanation is ON location 1; one bottom button goes
# directly to the cave. ?started=1 remains only for old deep links.

def test_every_door_to_the_badge_opens_the_one_page(new_scout, store):
    """主頁 tile, 獎章 map, a stale ?intro=1 link — all land on 玩法."""
    badge = member_badge(store)
    page = new_scout.get(f"/badges/{badge['id']}").get_data(as_text=True)
    assert "你被困住了" in page                              # the one page is the story
    assert "你的逃生路線" in page and "map-canvas" in page   # …with the treasure map
    assert '"story-hero"' in page                            # …on the island artwork
    # the separate game/trail page is gone, in the template and in the markup
    assert "quest-board" not in page and "trail-card" not in page
    assert not (pathlib.Path(__file__).resolve().parent.parent
                / "templates/scout/badge_quest.html").exists()
    # …and every door points at that same URL
    doors = [new_scout.get("/home").get_data(as_text=True),
             new_scout.get("/badges").get_data(as_text=True)]
    for door in doors:
        assert f"/badges/{badge['id']}" in door
    # the old ?intro=1 link still works — it is the same page
    alias = new_scout.get(f"/badges/{badge['id']}?intro=1").get_data(as_text=True)
    assert "你被困住了" in alias and "你的逃生路線" in alias


def test_first_location_is_readable_in_place_with_one_direct_start(new_scout, store):
    """Nothing to select, no cast-off step: one bottom CTA opens the cave."""
    badge = member_badge(store)
    cave = next(t for t in tasks_of(store, badge) if t['code'] == 'M04')
    page = new_scout.get(f"/badges/{badge['id']}").get_data(as_text=True)
    first = page[page.index('class="stage-chip stage-chip-first'):]
    first = first[:first.index('</li>')]
    assert '叢林深處' in first and '童軍歷史山洞' in first
    # the map carries no description (2026-10-18): place, game and state only —
    # what the game is about is read inside the game itself
    assert 'stage-chip-desc' not in first and '四段壁畫' not in first
    assert 'data-game-state' in first
    assert 'stage-radio' not in page and 'stage-panel' not in page
    assert page.count('data-journey-play') == 1
    launch = page[page.index('class="story-launch" data-journey-launch'):].split('</div>', 1)[0]
    assert launch.count('data-journey-play') == 1
    assert launch.count('<a ') == 1, 'only the direct game entry belongs here'
    assert '童軍綱要參考' not in page and 'Syllabus reference' not in page
    assert f'/tasks/{cave["id"]}/cave' in launch
    assert '開始歷險 · 進入遊戲 1' in launch
    assert 'data-quest-start' not in page and '划出去' not in page
    assert 'class="stage-items"' not in page, 'syllabus remains on its own reference page'


def test_a_first_time_scout_is_told_the_story_in_pictures(new_scout, store):
    """Nine picture cards inside the island page — click through, no scrolling:
       the escape-route map is one of the cards, and the last card sets off
       for stop 1 (leader's ask, 2026-10-18)."""
    badge = member_badge(store)
    page = new_scout.get(f"/badges/{badge['id']}").get_data(as_text=True)
    assert 'data-quest-intro' in page and 'data-quest-page' in page
    assert page.count('data-slide="') == 9
    # the story sits inside the page (top bar stays the way out), and the
    # third card is the real treasure map with the route numbered
    assert 'aria-modal' not in page
    assert 'map-canvas-story' in page and 'story-stops' in page
    assert 'data-slide-dot="9"' in page              # …and every card has its dot
    assert 'is-note-dark' in page                     # the ink adapts to each picture
    assert 'data-intro-skip' in page and '跳過' in page
    assert 'data-intro-begin' in page and '出發' in page
    assert page.count('data-journey-play') == 1       # the intro button is its own thing
    cave = next(t for t in tasks_of(store, badge) if t['code'] == 'M04')
    assert f'/tasks/{cave["id"]}/cave' in page[page.index('data-intro-begin'):]
    # the story lives in the shipped content file, so every existing badge gets it
    slides = json.loads((pathlib.Path(__file__).resolve().parent.parent / "content"
                         / "member-badge" / "guide.json").read_text())["quest"]["intro_slides"]
    assert len(slides) == 9


def test_dismissing_the_story_opens_the_escape_route_from_then_on(new_scout, store):
    """Skip or 出發 writes the old cast-off mark; from then on the badge page
       opens on the escape route only — no island hero, no story beats."""
    badge = member_badge(store)
    new_scout.post(f"/badges/{badge['id']}/start",
                   headers={"X-Requested-With": "fetch"})
    page = new_scout.get(f"/badges/{badge['id']}").get_data(as_text=True)
    assert 'data-quest-intro' not in page             # the pictures do not come back
    assert '"story-hero"' not in page and 'class="story-step"' not in page
    assert "你被困住了" not in page
    assert "你的逃生路線" in page and page.count('<li class="stage-chip') == 5
    assert "0 / 5 個遊戲已完成" in page                 # the counts moved to the slim header
    assert 'data-intro-replay' in page                # …and the story can be rewatched
    replay = new_scout.get(f"/badges/{badge['id']}?intro=1").get_data(as_text=True)
    assert 'data-quest-intro' in replay and 'data-started="1"' in replay


def test_the_story_is_drawn_in_the_same_hand_as_the_sign_in_page(new_scout, store):
    """Same world, same palette: the island art sits with the camp artwork."""
    badge = member_badge(store)
    page = new_scout.get(f"/badges/{badge['id']}?intro=1").get_data(as_text=True)
    assert "img/mascots/quest-island.jpg" in page
    assert "story-hero" in page
    assert f"img/mascots/{new_scout.user['patrol'].lower()}.webp" in page


def test_legacy_start_route_credits_no_other_task(app, store):
    """An old POST bookmark still works, but the new page has no cast-off form."""
    scout = next(u for u in store.list("users") if u["username"] == "scout07")
    client = app.test_client()
    client.get(f"/login/scout/{scout['patrol']}/{scout['id']}")
    client.post("/welcome", data={"password": "tiger777", "confirm": "tiger777",
                                  "email": "scout@example.com"},
                headers={"Accept": "application/json", "X-Requested-With": "fetch"})
    badge = member_badge(store)
    response = client.post(f"/badges/{badge['id']}/start", follow_redirects=False)
    assert response.status_code == 302 and "started=1" in response.headers["Location"]
    progress = engine.progress_for(store, scout["id"])["badges"][0]
    assert progress["tasks_done"] == 0 and progress["progress_done"] == 0
    assert not any(r["user_id"] == scout["id"] and r["badge_id"] == badge["id"]
                   for r in store.list("progress_records"))
    page = client.get(f"/badges/{badge['id']}?started=1").get_data(as_text=True)
    assert "冒險開始" in page and "童軍歷史山洞" in page
    assert "quest-opening" in page
    # the story has been told: the page opens straight on the escape route
    assert "你被困住了" not in page and '"story-hero"' not in page
    assert "你的逃生路線" in page and page.count('<li class="stage-chip') == 5
    assert page.count('data-journey-play') == 1 and '划出去' not in page


def test_legacy_start_alias_is_idempotent(app, store):
    scout = next(u for u in store.list("users") if u["username"] == "scout06")
    client = app.test_client()
    client.post(f"/login/scout/{scout['patrol']}/{scout['id']}", data={"password": "scout1234"})
    badge = member_badge(store)
    client.post(f"/badges/{badge['id']}/start")
    client.post(f"/badges/{badge['id']}/start")
    starts = [r for r in store.list("audit_log")
              if r.get("actor_id") == scout["id"] and r.get("action") == "start_quest"
              and r.get("entity_id") == badge["id"]]
    assert len(starts) == 1
    assert not any(r.get("user_id") == scout["id"] and r.get("badge_id") == badge["id"]
                   for r in store.list("progress_records"))


def test_a_cave_cleared_scout_lands_on_the_same_page(app, store):
    """Location 1 stays readable and location 2 becomes current, but is locked."""
    badge = member_badge(store)
    scout = next(u for u in store.list("users") if u["username"] == "scout02")
    client = app.test_client()
    client.post(f"/login/scout/{scout['patrol']}/{scout['id']}", data={"password": "scout1234"})
    page = client.get(f"/badges/{badge['id']}").get_data(as_text=True)
    # a started scout opens on the escape route, not the story (2026-10-18)
    assert "你被困住了" not in page and '"story-hero"' not in page
    assert "你的逃生路線" in page and page.count('<li class="stage-chip') == 5
    assert "1 / 5 個遊戲已完成" in page
    first = page[page.index('class="stage-chip stage-chip-first'):]
    first = first[:first.index('</li>')]
    assert 'is-done' in first and '童軍歷史山洞' in first and '✔ 已完成' in first
    second = page[page.index('data-stage="2"'):]
    second = second[:second.index('</li>')]
    assert 'aria-current="step"' in second and '迷霧渡口' in second
    assert "1 / 5 個遊戲已完成" in page
    third = page[page.index('data-stage="3"'):]
    third = third[:third.index('</li>')]
    assert '等待領袖加入' in third                # areas 3–5 are still to be built
    assert 'quest-board' not in page


def test_the_badge_is_five_games_one_per_area(scout_client, store):
    """Five markers, each showing its game in place; two are built so far."""
    badge = member_badge(store)
    page = scout_client.get(f"/badges/{badge['id']}").get_data(as_text=True)
    assert page.count('<li class="stage-chip') == 5
    assert page.count('class="stage-chip-game"') == 5
    assert all(f"🎮 遊戲 {n}" in page for n in range(1, 6))
    assert "五個遊戲全部完成" in page
    assert page.count('即將推出') == 3          # games 3–5 wait for the leader
    assert page.count('data-journey-play') == 1  # …and only the next one is offered
    assert 'stage-picker' not in page and 'stage-panel' not in page
    assert '個遊戲已完成' in page

    first = page[page.index('class="stage-chip stage-chip-first'):]
    first = first[:first.index('</li>')]
    assert '童軍歷史山洞' in first and '叢林深處' in first
    assert '童軍初體驗' not in first and '小隊集結' not in first
    second = page[page.index('data-stage="2"'):]
    assert '童軍歷史山洞' not in second[:second.index('</li>')]


def test_a_cleared_game_says_so(scout_client, store):
    """A scout who has finished a game sees it cleared, and may play again."""
    badge = member_badge(store)
    paper = {t["code"]: t for t in tasks_of(store, badge)}["M04"]
    rows = json.loads((pathlib.Path(__file__).resolve().parent.parent / "content"
                       / "member-badge" / "item4-answer-key.json").read_text())["answers"]
    bank = json.loads((pathlib.Path(__file__).resolve().parent.parent / "content"
                       / "member-badge" / "item4-question-bank.json").read_text())["questions"]
    key = {row["id"]: row["answerIndex"] for row in rows}
    answers = {f"q{i}": str(key[q["id"]]) for i, q in enumerate(bank)}
    assert scout_client.post(f"/tasks/{paper['id']}/cave-submit", data=answers).get_json()["passed"]

    page = scout_client.get(f"/badges/{badge['id']}").get_data(as_text=True)
    assert "1 / 5 個遊戲已完成" in page
    assert page.count("即將推出") == 3, "the three games still to be made"
    assert page.count('data-journey-play') == 1, "the next game is the only offer on the page"
    bridge = next(t for t in tasks_of(store, badge) if t["code"] == "M05")
    launch = page[page.index('data-journey-play'):]
    launch = launch[:launch.index('</a>')]
    assert f'/tasks/{bridge["id"]}' in launch, "the offer is the bridge, the next unplayed game"
    assert '進入遊戲 2' in launch


def test_syllabus_reference_has_no_map_entry_but_direct_url_still_works(scout_client, store):
    badge = member_badge(store)
    map_page = scout_client.get(f"/badges/{badge['id']}").get_data(as_text=True)
    guide_response = scout_client.get(f"/badges/{badge['id']}/requirements")
    assert '童軍綱要參考' not in map_page and '/requirements' not in map_page
    assert 'class="stage-items"' not in map_page, 'syllabus notes are not game stops'
    assert guide_response.status_code == 200, 'old direct bookmarks must still work'
    guide = guide_response.get_data(as_text=True)
    assert 'data-guide-item="5"' in guide and guide.count('class="guide-item') == 11


def test_the_requirements_page_still_carries_the_eleven_items(scout_client, store):
    badge = member_badge(store)
    page = scout_client.get(f"/badges/{badge['id']}/requirements").get_data(as_text=True)
    assert page.count('class="guide-item') == 11
    assert "童軍綱要參考" in page


def test_the_page_uses_game_names_not_first_area_tasks(scout_client, store):
    badge = member_badge(store)
    page = scout_client.get(f"/badges/{badge['id']}").get_data(as_text=True)
    assert "童軍大考驗" not in page, "the old paper is gone"
    assert "童軍初體驗" not in page and "小隊集結" not in page
    for name in ("叢林深處", "迷霧小徑", "石壁山嶺", "溪谷旗桿", "臨海山崗"):
        assert name in page
    assert page.count('class="stage-chip-game"') == 5
    assert 'class="stage-chip stage-chip-first' in page and '🎮 遊戲 1' in page


def test_the_only_start_link_directly_opens_cave_without_awarding_points(app, store):
    """A normal GET, not a POST/cast-off/AJAX step, so it works without JS."""
    scout = next(u for u in store.list("users") if u["username"] == "scout06")
    client = app.test_client()
    client.post(f"/login/scout/{scout['patrol']}/{scout['id']}", data={"password": "scout1234"})
    badge = member_badge(store)
    page = client.get(f"/badges/{badge['id']}").get_data(as_text=True)
    link = re.search(r'<a[^>]*data-journey-play[^>]*href="([^"]+)"', page)
    assert link and re.search(r'/tasks/[^/]+/cave', link.group(1))
    assert client.get(link.group(1)).status_code == 200
    assert not any(r.get('actor_id') == scout['id'] and r.get('action') == 'start_quest'
                   for r in store.list('audit_log'))
    assert engine.progress_for(store, scout['id'])['badges'][0]['progress_done'] == 0
    assert not any(r.get('user_id') == scout['id'] and r.get('badge_id') == badge['id']
                   for r in store.list('progress_records'))


def test_the_how_to_play_page_tells_the_island_story(new_scout, store):
    """玩法 — the one page — is a story: stranded on an island, five areas, a raft.

    The boxes are gone. What is left is the island itself, the beats of the
    escape, and then the escape route — the treasure map — as the last beat.
    """
    page = new_scout.get(f"/badges/{member_badge(store)['id']}").get_data(as_text=True)
    assert "你被困住了" in page                      # the story starts here
    assert "荒島" in page                            # …on an island
    assert page.count('class="story-step"') == 3     # three beats (the route li has its own class)
    assert page.count('class="story-step story-step-trail"') == 1
    for beat in ("在荒島醒來", "走過五個區域", "沙灘上的木筏"):
        assert beat in page, beat
    assert page.count('data-cheer') >= 4             # every beat pops when tapped

    # the story is drawn on its own artwork, the jungle island
    assert "img/mascots/quest-island.jpg" in page
    assert 'class="story-hero"' in page and "story-spark" in page
    assert f"img/mascots/{new_scout.user['patrol'].lower()}.webp" in page

    # the route is the last beat: five areas, then the raft on the beach
    assert "你的逃生路線" in page
    assert page.count('<li class="stage-chip') == 5
    assert 'stage-radio' not in page
    assert "木筏" in page and "沙灘" in page

    # one button enters game 1 directly; no voyage confirmation step
    assert 'data-journey-play' in page and '划出去' not in page


def test_the_map_marks_the_next_location_without_any_selection(new_scout, app, store):
    """The current location is visible without clicking a map pin."""
    badge_id = member_badge(store)['id']
    fresh = new_scout.get(f"/badges/{badge_id}").get_data(as_text=True)
    first = fresh[fresh.index('data-stage="1"'):]
    assert 'aria-current="step"' in first[:first.index('</li>')]
    scout = next(u for u in store.list("users") if u["username"] == "scout02")
    client = app.test_client()
    client.post(f"/login/scout/{scout['patrol']}/{scout['id']}", data={"password": "scout1234"})
    midway = client.get(f"/badges/{badge_id}").get_data(as_text=True)
    second = midway[midway.index('data-stage="2"'):]
    assert 'aria-current="step"' in second[:second.index('</li>')]
    assert 'stage-radio' not in fresh and 'stage-radio' not in midway


def test_the_stage_board_keeps_its_pictures_still_when_asked(new_scout, store):
    """prefers-reduced-motion: no drifting sparkles, no endless loop of dots."""
    page = new_scout.get(f"/badges/{member_badge(store)['id']}").get_data(as_text=True)
    css = pathlib.Path(__file__).resolve().parent.parent / "static/styles.css"
    styles = css.read_text()
    block = styles[styles.index("@media (prefers-reduced-motion: reduce)") :]
    for moving in (".story-spark", ".story-step-icon", ".stage-chip-me"):
        assert moving in block, moving


def test_only_five_distinct_game_wins_award_and_unlocks_next(app, new_scout, store):
    """Even unfinished M01/M02 cannot block the award once games 1–5 clear."""
    badge = member_badge(store)
    guide = engine.as_json(badge['guide_json'], {})
    cave = next(t for t in tasks_of(store, badge) if t['code'] == 'M04')
    games = []
    for n, area in enumerate(guide['quest']['areas'][1:], start=2):
        code = f'G0{n}'
        task = store.insert('tasks', {
            'badge_id': badge['id'], 'order_index': 11 + n, 'code': code,
            'title_zh': f'遊戲 {n}', 'title_en': f'Game {n}',
            'instruction_zh': '示範遊戲', 'instruction_en': 'Demo game',
            'type': 'checklist', 'points': 10, 'pass_score': 0,
            'config_json': {'items': [{'zh': '完成', 'en': 'Done'}]},
            'status': 'published',
        })
        area['game'].update(ready=True, kind='task', task_code=code,
                            name_zh=f'遊戲 {n}', name_en=f'Game {n}')
        games.append(task)
    store.update('badges', badge['id'], {'guide_json': guide})

    cave_result = new_scout.post(f"/tasks/{cave['id']}/cave-submit",
                                 data=cave_answers(store, cave)).get_json()
    assert cave_result['passed'] and not engine.progress_for(store, new_scout.id)['badges'][0]['earned']
    for task in games[:3]:
        result = new_scout.post(f"/tasks/{task['id']}/submit", data={'item0': '1'}).get_json()
        assert result['status'] == 'completed'
    mid = engine.progress_for(store, new_scout.id)['badges'][0]
    assert mid['progress_done'] == 4 and not mid['earned']
    assert engine.check_badge_completion(store, user=new_scout.user,
                                         badge=store.get('badges', badge['id']))['remaining'] == 1

    finish = new_scout.post(f"/tasks/{games[3]['id']}/submit", data={'item0': '1'}).get_json()
    assert finish['status'] == 'completed'
    end = engine.progress_for(store, new_scout.id)
    member = end['badges'][0]
    assert member['earned'] and member['progress_done'] == member['progress_total'] == 5
    assert end['badges'][1]['locked'] is False
    assert next(t for t in member['tasks'] if t['code'] == 'M01')['status'] == 'todo'
    assert next(t for t in member['tasks'] if t['code'] == 'M02')['status'] == 'todo'
    assert sum(r['ref_id'] == badge['id'] for r in store.list('points_ledger')
               if r.get('user_id') == new_scout.id and r.get('entry_type') == 'badge') == 1
    assert engine.check_badge_completion(store, user=new_scout.user,
                                         badge=store.get('badges', badge['id']))['reason'] == 'already'


def test_duplicate_game_task_cannot_pretend_to_be_five(store):
    badge = member_badge(store)
    guide = engine.as_json(badge['guide_json'], {})
    for area in guide['quest']['areas']:
        area['game'].update(ready=True, task_code='M04')
    store.update('badges', badge['id'], {'guide_json': guide})
    scout = next(u for u in store.list('users') if u['username'] == 'scout02')
    result = engine.check_badge_completion(store, user=scout, badge=store.get('badges', badge['id']))
    assert result['reason'] == 'games_unavailable' and not result['awarded']
