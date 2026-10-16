"""童軍歷史山洞 — 第 4 項 as the badge's first game.

The cave is item 4: four wall paintings, each teaching one group of the fifty
questions, with the answers given in the chambers and a dead end (which revises
the history) for every wrong one. These tests pin the game the leader asked for
— the groups and their walls, the timelines on those walls, fifty questions in
total, the options shuffled every time, the score coming from the platform's own
grading, and the same walk inside the offline demo file.
"""
from __future__ import annotations

import html as H
import json
import pathlib
import re

import pytest

from scout.content import cave_adventure, cave_images

ROOT = pathlib.Path(__file__).resolve().parent.parent


def member_badge(store) -> dict:
    return sorted(store.list("badges"), key=lambda b: int(b["order_index"]))[0]


def paper_task(store) -> dict:
    badge = member_badge(store)
    return next(t for t in store.list("tasks")
                if t["badge_id"] == badge["id"] and t["type"] == "quiz")


def bank() -> dict:
    return json.loads((ROOT / "content" / "member-badge"
                       / "item4-question-bank.json").read_text())


def answer_key() -> list[int]:
    """The key lives apart from the bank: the paper must not carry it."""
    rows = json.loads((ROOT / "content" / "member-badge"
                       / "item4-answer-key.json").read_text())["answers"]
    by_id = {row["id"]: row["answerIndex"] for row in rows}
    return [by_id[q["id"]] for q in bank()["questions"]]


def config_of(page: str) -> dict:
    """The JSON the browser plays — read straight off the rendered page."""
    raw = re.search(r'data-cave-config="([^"]*)"', page).group(1)
    return json.loads(H.unescape(raw))


@pytest.fixture()
def cave_page(app, store, scout_client):
    task = paper_task(store)
    return scout_client.get(f"/tasks/{task['id']}/cave").get_data(as_text=True)


# ── 一段錯三次 → 回頭的故事 ───────────────────────────────────────────────


def test_three_wrong_turns_in_a_stretch_send_the_scout_back(cave_page):
    """The leader's setback rule: five or six stories, one every third miss.

    The page must hand the stories over (with a painting each), say how many
    wrong turns a stretch allows, and keep the wording bilingual — the rule is
    told to the scout in the same breath as the dead-end recap.
    """
    payload = config_of(cave_page)
    setback = payload["setbacks"]
    assert int(setback["wrong_limit"]) == 3
    stories = setback["stories"]
    assert len(stories) >= 5, "five or six excuses were asked for"
    assert len({story["id"] for story in stories}) == len(stories)
    for story in stories:
        for key in ("title_zh", "title_en"):
            assert story[key].strip(), (story["id"], key)
        assert len(story["paras_zh"]) >= 2 and len(story["paras_zh"]) == len(story["paras_en"]), \
            story["id"]
        assert all(line.strip() for line in story["paras_zh"] + story["paras_en"]), story["id"]
    for key in ("torch_zh", "torch_en", "back_zh", "back_en", "note_zh", "note_en"):
        assert setback[key].strip(), key
    assert "{left}" in setback["torch_zh"] and "{left}" in setback["torch_en"]
    # the scout is told what the torch has left before the third miss
    assert "火把" in setback["torch_zh"] and "torch" in setback["torch_en"].lower()


def test_every_setback_painting_is_ready_to_show():
    """A story without its picture would send the scout back into the dark."""
    adventure = cave_adventure()
    names = cave_images(adventure)
    art_dir = ROOT / "static" / "img" / "quest" / "cave"
    for story in adventure["setbacks"]["stories"]:
        assert story["image"] in names, story["id"]
        assert (art_dir / f"{story['image']}.jpg").exists(), story["id"]


def test_the_stories_are_plain_written_chinese():
    """Scout-facing 中文 stays 書面語 — no 口語 particles in the setback stories."""
    adventure = cave_adventure()
    lines = []
    for story in adventure["setbacks"]["stories"]:
        lines += [story["kicker_zh"], story["title_zh"], *story["paras_zh"]]
    lines += [adventure["setbacks"]["note_zh"], adventure["setbacks"]["back_zh"]]
    spoken = re.compile(r"嘅|嘞|喇|囉|咗|係咪|唔|點解|嗰")
    for line in lines:
        assert not spoken.search(line), line


# ── the script of the game ────────────────────────────────────────────────

def test_the_cave_teaches_four_groups_before_it_asks():
    adventure = cave_adventure()
    groups = adventure["groups"]
    assert len(groups) == 4, "the leader asked for four groups of questions"
    for index, group in enumerate(groups, start=1):
        assert group["n"] == index and group["name_zh"] and group["name_en"]
        wall = group["wall"]
        assert wall["image"], "every group has its own wall painting"
        assert wall["title_zh"] and wall["title_en"]
        # the wall introduces the group: a few lines, a timeline, and the facts
        assert len(wall["lead_zh"]) >= 2 and len(wall["lead_zh"]) == len(wall["lead_en"])
        assert len(wall["timeline"]) >= 1, "the wall reads as a timeline"
        for row in wall["timeline"]:
            for key in ("when_zh", "when_en", "text_zh", "text_en"):
                assert row.get(key), key
        assert wall["facts"] and all(f.get("label_zh") and f.get("value_zh") for f in wall["facts"])
        # …and a wrong answer has a dead end that revises that history
        assert group["deadend_zh"] and group["deadend_en"]
        assert group["questions"], "a group with no questions teaches nothing"


def test_every_scene_has_its_own_photo_and_they_are_reused():
    adventure = cave_adventure()
    needed = {name + ".jpg" for name in cave_images(adventure)}
    for name in sorted(needed):
        art = ROOT / "static" / "img" / "quest" / "cave" / name
        assert art.exists(), f"{name} is missing — every scene needs a photo"
        assert art.stat().st_size > 20_000, f"{name} looks empty"
    # the leader's shortcut: a few chambers and dead ends, used again and again
    assert 3 <= len(adventure["chambers"]) <= 4
    assert 3 <= len(adventure["deadends"]) <= 4
    assert adventure["intro"]["image"] and adventure["exit"]["image"]


def test_the_fifty_questions_are_all_placed():
    adventure = cave_adventure()
    placed = [qid for group in adventure["groups"] for qid in group["questions"]]
    assert len(placed) == 50, "item 4 is the 50-question paper"
    assert len(set(placed)) == 50, "no question may be asked twice"
    assert set(placed) == {q["id"] for q in bank()["questions"]}


def test_the_group_history_is_in_the_story(store):
    """八十二旅's own facts must appear — the leader asked for them by name."""
    text = json.dumps(cave_adventure(), ensure_ascii=False)
    for fact in ("1907", "1909", "筲箕灣區", "Tiger", "Otter", "Sea-gull", "十月一日",
                 "我願以信譽為誓", "金錢村", "梅含理", "82"):
        assert fact in text, fact


def test_the_cave_speaks_written_chinese():
    """Every scout-facing line is 書面語 — no colloquial Hong Kong Cantonese."""
    text = json.dumps(cave_adventure(), ensure_ascii=False)
    for colloquial in ("嘅", "唔", "咗", "喺", "撳", "睇", "佢", "冇", "係", "入去", "返(?!回)"):
        assert not re.search(colloquial, text), colloquial


# ── the page ──────────────────────────────────────────────────────────────

def test_the_item_four_page_is_the_cave_only(app, store, scout_client):
    task = paper_task(store)
    response = scout_client.get(f"/tasks/{task['id']}")
    assert response.status_code == 302 and response.headers['Location'].split('?')[0].endswith(f"/tasks/{task['id']}/cave")
    page = scout_client.get(response.headers['Location']).get_data(as_text=True)
    assert 'data-cave' in page and '50 題' in page
    assert 'data-task-submit' not in page, 'item 4 has no separate paper'
    old_form = scout_client.post(f"/tasks/{task['id']}/submit", data={})
    assert old_form.status_code == 403 and old_form.get_json()['error'] == 'play_the_cave'


def test_the_page_hands_over_four_groups_of_questions(cave_page):
    config = config_of(cave_page)
    assert [g["n"] for g in config["groups"]] == [1, 2, 3, 4]
    sizes = [len(g["questions"]) for g in config["groups"]]
    assert sum(sizes) == 50, sizes
    assert all(size >= 4 for size in sizes), sizes
    # the wall, the scene words, and the automatic completion endpoint
    for group in config["groups"]:
        assert group["wall"]["timeline"] and group["wall"]["facts"]
        for question in group["questions"]:
            assert question["q_zh"] and len(question["options"]) == 4
            assert sum(1 for o in question["options"] if o["ok"]) == 1
    assert config["submit_url"].endswith("/cave-submit")
    assert config["score"]["completion"] == "all_questions"
    assert config["score"]["per_question"] == 2 and "pass" not in config["score"]
    assert config["labels"]["pass_note_zh"] and config["labels"]["review_title_zh"]
    assert config["labels"]["recap_zh"] and config["labels"]["recap_en"]
    # every painting the game can show is in the page, ready to swap in
    # the entrance is the visible <img>; the rest wait in the hidden block, and
    # every name the game can ask for is in the page exactly once
    assert cave_page.count("data-cave-art=") == len(cave_images(cave_adventure()))
    assert 'class="cave-sources"' in cave_page            # the pictures wait in the page
    script = (ROOT / "static" / "js" / "cave.js").read_text()
    assert "cave-timeline" in script and "cave-milestone" in script   # the wall reads as one


def test_the_answer_never_travels_with_the_question(cave_page):
    """The page marks the right option for the game, but never the bank's index."""
    config = config_of(cave_page)
    positions = []
    for group in config["groups"]:
        for question in group["questions"]:
            order = [i for i, o in enumerate(question["options"]) if o["ok"]]
            assert len(order) == 1
            positions.append(order[0])
    assert len(set(positions)) > 1, "the right option must move around the card"
    # and the score itself is worked out again by the platform, not the browser
    assert "cave-submit" in config["submit_url"]


def test_the_game_can_be_played_without_a_mouse(cave_page):
    script = (ROOT / "static" / "js" / "cave.js").read_text()
    assert 'aria-live="polite"' in cave_page
    assert "art.setAttribute('alt'" in script
    assert '<button class="cave-option"' in script       # the options are buttons
    assert "closest('[data-cave-option]')" in script      # …read by one listener
    # every scene the game can reach is in the whitelist the script renders
    for scene in ("intro", "wall", "question", "verdict", "groupdone",
                  "submitting", "save-error", "result"):
        assert f"'{scene}'" in script, scene
    assert 'data-cave-go="finish"' in script and 'data-cave-go="submit"' not in script


def test_wrong_turn_revises_the_history_without_revealing_the_option(cave_page):
    """A dead end gives a recap and retry, never a labelled correct choice."""
    script = (ROOT / "static" / "js" / "cave.js").read_text()
    wrong_screen = script.split("function verdictHtml(ok, q)", 1)[1].split(
        "function groupDoneHtml()", 1)[0]
    assert "L.recap_zh" in wrong_screen and "L.recap_en" in wrong_screen
    assert "esc(explain || '')" in wrong_screen
    assert 'data-cave-go="question"' in wrong_screen
    assert "cave-picks" not in wrong_screen and "cave-pick-good" not in wrong_screen
    assert "answer_label" not in wrong_screen, "the final review can still show it later"


def test_the_english_page_explains_itself_in_english(app, store, scout_client):
    """The bank is written in Chinese, so the game carries its own English."""
    scout_client.get("/set-language/en")
    task = paper_task(store)
    page = scout_client.get(f"/tasks/{task['id']}/cave").get_data(as_text=True)
    config = config_of(page)
    for group in config["groups"]:
        assert re.search(r"[A-Za-z]{4,}", group["name_en"])
        assert group["deadend_en"] and group["wall"]["title_en"]
        assert all(row["when_en"] and row["text_en"] for row in group["wall"]["timeline"])
        assert all(f["label_en"] and f["value_en"] for f in group["wall"]["facts"])
    assert config["labels"]["pass_note_en"] and config["labels"]["review_title_en"]
    scout_client.get("/set-language/zh")


def test_the_cave_hands_its_paper_to_the_platform(app, store, new_scout):
    """Fifty answers in, a score and a review out — and the badge's task filed."""
    task = paper_task(store)
    answers = {f"q{i}": str(key if i % 5 else (key + 1) % len(q["options"]))
               for i, (q, key) in enumerate(zip(bank()["questions"], answer_key()))}
    response = new_scout.post(f"/tasks/{task['id']}/cave-submit", data=answers)
    payload = response.get_json()
    assert response.status_code == 200 and payload["ok"]
    assert payload["score"] == 80, payload          # ten missed, two marks each
    assert payload["passed"] is True
    assert payload["detail"]["correct"] == 40

    # a pass files the task, so the badge page shows item 4 done and the points land
    progress = new_scout.get(f"/tasks/{task['id']}/cave").get_data(as_text=True)
    assert "data-cave" in progress                  # the page still opens after passing
    record = next(r for r in store.list("progress_records")
                  if r["user_id"] == new_scout.id and r["task_id"] == task["id"])
    assert record["status"] == "completed" and record["score"] == 80


def test_even_zero_marks_clears_game_one_and_awards_once(app, store, new_scout):
    """The first-try score is informative; finishing all 50 is the win."""
    task = paper_task(store)
    # An installation that still has the old threshold must also work without
    # asking scouts to replay. This route never consults that quiz pass mark.
    store.update("tasks", task["id"], {"pass_score": 80})
    answers = {f"q{i}": str((key + 1) % len(q["options"]))
               for i, (q, key) in enumerate(zip(bank()["questions"], answer_key()))}
    before = store.stats_for(new_scout.id)["points_balance"]
    response = new_scout.post(f"/tasks/{task['id']}/cave-submit", data=answers)
    payload = response.get_json()
    assert response.status_code == 200 and payload["passed"] is True
    assert payload["status"] == "completed" and payload["score"] == 0
    assert payload["detail"]["correct"] == 0
    records = [r for r in store.list("progress_records")
               if r["user_id"] == new_scout.id and r["task_id"] == task["id"]]
    assert len(records) == 1 and records[0]["status"] == "completed" and records[0]["score"] == 0
    assert store.stats_for(new_scout.id)["points_balance"] == before + task["points"]
    from scout.engine import progress_for
    badge = progress_for(store, new_scout.id)["badges"][0]
    assert badge["progress_done"] == 1 and badge["progress_total"] == 5
    assert not badge["earned"], "games 2–5 are still required"

    again = new_scout.post(f"/tasks/{task['id']}/cave-submit", data=answers).get_json()
    assert again["passed"] and again["already_done"]
    assert len([r for r in store.list("progress_records")
                if r["user_id"] == new_scout.id and r["task_id"] == task["id"]]) == 1
    assert store.stats_for(new_scout.id)["points_balance"] == before + task["points"]


def test_missing_or_invalid_cave_answers_cannot_award_completion(store, new_scout):
    """Removing the threshold must not make an empty POST a free win."""
    task = paper_task(store)
    full = {f"q{i}": str(key) for i, key in enumerate(answer_key())}
    for data in ({}, {k: v for k, v in full.items() if k != "q49"},
                 {**full, "q0": "-1"}, {**full, "q0": "4"},
                 {**full, "q0": "not-an-index"}):
        response = new_scout.post(f"/tasks/{task['id']}/cave-submit", data=data)
        assert response.status_code == 400 and response.get_json()["error"] == "cave_incomplete"
    assert not any(r["user_id"] == new_scout.id and r["task_id"] == task["id"]
                   for r in store.list("progress_records"))
    assert not any(r["user_id"] == new_scout.id and r["ref_id"] == task["id"]
                   for r in store.list("points_ledger"))
    assert new_scout.post(f"/tasks/{task['id']}/cave-submit", data=full).get_json()["passed"]


def test_other_quizzes_keep_their_own_pass_marks(store):
    """Changing the cave must not loosen the rest of the task engine."""
    from scout.engine import evaluate_submission
    quiz = next(t for t in store.list("tasks") if t.get("code") == "T-11")
    assert quiz["pass_score"] == 80
    result = evaluate_submission(quiz, {"answers": ["-1"]}, store.settings())
    assert result["status"] == "rejected" and not result["auto_award"]


def test_tasks_without_a_cave_do_not_get_one(app, store, scout_client):
    badge = member_badge(store)
    checklist = next(t for t in store.list("tasks")
                     if t["badge_id"] == badge["id"] and t["type"] != "quiz")
    assert "進入山洞歷險" not in scout_client.get(f"/tasks/{checklist['id']}").get_data(as_text=True)
    response = scout_client.get(f"/tasks/{checklist['id']}/cave")
    assert response.status_code in (302, 404), "no cave for a non-quiz task"


def test_the_cave_is_for_scouts_who_are_signed_in(app, store):
    task = paper_task(store)
    strangers = app.test_client()
    for path, method in ((f"/tasks/{task['id']}/cave", "get"),
                         (f"/tasks/{task['id']}/cave-submit", "post")):
        response = getattr(strangers, method)(path)
        assert response.status_code in (302, 401)
        if response.status_code == 302:
            assert "/login" in response.headers["Location"]


def test_every_cave_exit_warns_that_reentry_starts_over(cave_page):
    """Both top exits and other navigation use the same cancelable warning."""
    script = (ROOT / 'static' / 'js' / 'cave.js').read_text()
    assert cave_page.count('class="cave-hud-link"') == 2
    assert '返回會員章' in cave_page and '🏠 主頁' in cave_page
    assert 'role="alertdialog"' in script and 'aria-modal="true"' in script
    assert '再次進入遊戲需要從頭開始' in script
    assert 'start the game again when you return' in script
    assert "[data-cave-stay]" in script and "[data-cave-leave]" in script
    assert "event.stopImmediatePropagation()" in script, 'cancel must block navigation'
    assert "document.addEventListener('click'" in script
    assert "document.addEventListener('submit'" in script
    assert "window.addEventListener('beforeunload'" in script, 'Back/Reload have a fallback'
    assert "reset();\n        show('intro');" in script, 'confirmed exit resets the next run'


def test_offline_router_guards_pane_exits_and_keeps_badge_progress():
    """Offline pane switches cannot skip the warning or resume old answers."""
    offline = (ROOT / 'tools' / 'offline_demo.py').read_text()
    # both games are guarded: whatever game is on screen asks before it goes
    assert "(shown === 'cave' && id !== 'cave') || (shown === 'bridge' && id !== 'bridge')" in offline
    assert 'game.requestExit(function () { go(id, true); })' in offline
    assert "return shown === 'cave' ? window.CaveGame : window.BridgeGame;" in offline
    assert "trail[trail.length - 1]" in offline, 'canceling Escape keeps history'
    assert "var game1Cleared = false" in offline
    assert "var game2Cleared = false" in offline
    assert "document.addEventListener('bridge:result'" in offline
    assert "'2 / 5 個遊戲'" in offline
