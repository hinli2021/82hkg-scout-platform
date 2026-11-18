"""遊戲 5 — 小隊名冊卡（第 2 項，M02）.

The bluff's game is the patrol itself: member cards are read live from the
accounts and profiles, so a scout who joins appears at once. The member
whose 職位 is 聯絡 is asked about by name, and the way to reach them is the
email on their account. Members without a finished profile still appear —
their name and 職位 are tested, nothing more. Scoring 80% completes item 2
with no leader code; below that, nothing is filed.
"""
from __future__ import annotations

import json
import re

from itsdangerous import URLSafeTimedSerializer

HEADERS = {"Accept": "application/json", "X-Requested-With": "fetch"}


def find(store, username):
    return next(u for u in store.list("users") if u["username"] == username)


def task_of(store, code="M02"):
    return next(t for t in store.list("tasks") if t.get("code") == code)


def add_member(store, username, zh, en, email, profile=None):
    user = store.insert("users", {
        "role": "scout", "username": username, "password_hash": "x", "password_salt": "y",
        "display_name_zh": zh, "display_name_en": en, "email": email,
        "scout_no": "", "section": "scout", "patrol": "Otter",
        "unit": "Sample Scout Group", "avatar": "🦊", "status": "active",
        "must_change_password": False, "show_on_leaderboard": True,
        "created_at": "2026-01-01", "created_by": "",
    })
    if profile is not None:
        store.insert("profiles", {"user_id": user["id"], "visible": True,
                                  "updated_at": "2026-01-01", **profile})
    return user


def full_profile(position, interests, strength):
    return {"position": position, "interests": interests, "strength": strength,
            "experience": "參加了童軍兩年。", "share": "喜歡在營地幫忙。"}


def seed_patrol(store):
    """scout04 (Otter) views a patrol with a contact, two finished profiles
    and one member who has not filled in a profile yet."""
    viewer = find(store, "scout04")
    store.insert("profiles", {"user_id": viewer["id"], "visible": True,
                              "updated_at": "2026-01-01",
                              **full_profile("隊員", "足球", "跑步")})
    contact = add_member(store, "patrolcontact", "陳聯絡", "Chan Contact",
                         "contact@82hkg.example",
                         full_profile("小隊聯絡", "露營", "繩結"))
    singer = add_member(store, "patrolsinger", "黃歌手", "Wong Singer",
                        "singer@82hkg.example",
                        full_profile("隊員", "音樂", "唱歌"))
    rookie = add_member(store, "patrolrookie", "新成員", "New Member", "", None)
    return viewer, contact, singer, rookie


def login(app, user):
    client = app.test_client()
    reply = client.post(f"/login/scout/{user['patrol']}/{user['id']}",
                        data={"password": "scout1234"})
    assert reply.status_code in (200, 302)
    return client


def scene_of(client, task_id):
    page = client.get(f"/tasks/{task_id}/patrol").get_data(as_text=True)
    match = re.search(r'<script id="pat-scene" type="application/json">(.*?)</script>',
                      page, re.S)
    assert match, "the game page carries its scene"
    return page, json.loads(match.group(1))


def key_of(scene):
    run = URLSafeTimedSerializer("test-secret", salt="patrol-run-v1").loads(scene["run_key"])
    return run["key"]


def completed_records(store, user_id, task_id):
    return [r for r in store.list("progress_records")
            if r.get("user_id") == user_id and r.get("task_id") == task_id
            and r.get("status") == "completed"]


def test_the_roster_is_the_live_patrol(store, app):
    viewer, contact, singer, rookie = seed_patrol(store)
    task = task_of(store)
    client = login(app, viewer)
    page, scene = scene_of(client, task["id"])

    assert "data-patrol-root" in page and "patrol.js" in page
    assert "小隊名冊卡" in page and "第 2 項" in page
    members = {m["id"]: m for m in scene["members"]}
    # every Otter scout is on a card: the seeded pair, the new members, and
    # the member with no profile at all
    assert {viewer["id"], contact["id"], singer["id"], rookie["id"]} <= set(members)
    assert members[contact["id"]]["is_contact"] is True
    assert members[contact["id"]]["contact_email"] == "contact@82hkg.example"
    # nobody else's address is handed to the game
    assert all(m["contact_email"] == "" for m in members.values()
               if m["id"] != contact["id"])
    # the unfinished profile is marked, not hidden
    assert members[rookie["id"]]["complete"] is False
    assert members[singer["id"]]["strength"] == "唱歌"

    kinds = {q["kind"] for q in scene["questions"]}
    assert {"contact_who", "contact_way", "position", "clue"} <= kinds
    contact_way = next(q for q in scene["questions"] if q["kind"] == "contact_way")
    assert any("contact@82hkg.example" in o["zh"] for o in contact_way["options"])
    # the answers themselves never reach the page
    assert "run_key" in scene and scene["run_key"]
    for question in scene["questions"]:
        assert "answer" not in question


def test_the_test_account_is_ignored_but_can_play(store, app):
    """The leaders' test account is not a patrol member: it never appears
    on a card or in a question — yet the account itself can still play."""
    from scout.util import hash_password

    viewer, contact, singer, rookie = seed_patrol(store)
    hashed, salt = hash_password("scout1234")
    tester = store.insert("users", {
        "role": "scout", "username": "test", "password_hash": hashed,
        "password_salt": salt, "display_name_zh": "測試帳戶",
        "display_name_en": "Test Account", "email": "test@82hkg.example",
        "scout_no": "", "section": "scout", "patrol": "Otter",
        "unit": "Sample Scout Group", "avatar": "🧪", "status": "active",
        "must_change_password": False, "show_on_leaderboard": True,
        "created_at": "2026-01-01", "created_by": "",
    })
    store.insert("profiles", {"user_id": tester["id"], "visible": True,
                              "updated_at": "2026-01-01",
                              **full_profile("隊員", "測試", "測試")})
    task = task_of(store)

    # a real scout never meets the test account in the game
    client = login(app, viewer)
    _, scene = scene_of(client, task["id"])
    assert tester["id"] not in {m["id"] for m in scene["members"]}
    assert tester["id"] not in key_of(scene).values()
    for question in scene["questions"]:
        assert tester["id"] not in [o["value"] for o in question["options"]]

    # …but the test account itself signs in and plays the real patrol
    client = login(app, tester)
    _, scene = scene_of(client, task["id"])
    ids = {m["id"] for m in scene["members"]}
    assert tester["id"] not in ids
    assert {viewer["id"], contact["id"], singer["id"], rookie["id"]} <= ids
    reply = client.post(f"/tasks/{task['id']}/patrol-submit",
                        data={**key_of(scene), "run_key": scene["run_key"],
                              "elapsed_ms": "60000"}, headers=HEADERS)
    assert reply.get_json()["passed"] is True


def test_scoring_eighty_percent_completes_item_two(store, app):
    viewer, contact, singer, rookie = seed_patrol(store)
    task = task_of(store)
    client = login(app, viewer)
    _, scene = scene_of(client, task["id"])
    key = key_of(scene)
    url = f"/tasks/{task['id']}/patrol-submit"

    wrong = {qid: "__wrong__" for qid in key}
    reply = client.post(url, data={**wrong, "run_key": scene["run_key"],
                                   "elapsed_ms": "60000"}, headers=HEADERS)
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "patrol_short"
    assert completed_records(store, viewer["id"], task["id"]) == []

    reply = client.post(url, data={**key, "run_key": scene["run_key"],
                                   "elapsed_ms": "60000"}, headers=HEADERS)
    body = reply.get_json()
    assert reply.status_code == 200 and body["passed"] is True
    records = completed_records(store, viewer["id"], task["id"])
    assert len(records) == 1 and records[0]["score"] >= 80
    ledger = [row for row in store.list("points_ledger")
              if row.get("user_id") == viewer["id"] and row.get("ref_id") == task["id"]]
    assert len(ledger) == 1 and ledger[0]["points_delta"] == task["points"]

    # playing again is allowed, but item 2 and its points are filed once
    _, scene = scene_of(client, task["id"])
    reply = client.post(url, data={**key_of(scene), "run_key": scene["run_key"],
                                   "elapsed_ms": "60000"}, headers=HEADERS)
    assert reply.get_json()["already_done"] is True
    assert len(completed_records(store, viewer["id"], task["id"])) == 1
    assert len([row for row in store.list("points_ledger")
                if row.get("user_id") == viewer["id"]
                and row.get("ref_id") == task["id"]]) == 1


def test_a_forged_score_is_regraded_and_a_bad_token_refused(store, app):
    viewer, *_ = seed_patrol(store)
    task = task_of(store)
    client = login(app, viewer)
    _, scene = scene_of(client, task["id"])
    url = f"/tasks/{task['id']}/patrol-submit"

    # the browser claims a perfect score without answers — the server marks
    # what it was actually sent
    reply = client.post(url, data={"run_key": scene["run_key"], "score": "100",
                                   "elapsed_ms": "60000"}, headers=HEADERS)
    assert reply.status_code == 400
    assert completed_records(store, viewer["id"], task["id"]) == []

    reply = client.post(url, data={"run_key": "not-a-token", "elapsed_ms": "1"},
                        headers=HEADERS)
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "patrol_expired"


def test_the_old_signoff_item_upgrades_itself(store):
    """An installation still holding item 2 as a leader sign-off gets the
    game on the next start — task shape and area 5 together."""
    from scout.engine import as_json

    task = task_of(store)
    store.update("tasks", task["id"], {"type": "signoff", "config_json": {}})
    badge = next(b for b in store.list("badges") if b.get("code") == "SC-01")
    guide = as_json(badge.get("guide_json"), {})
    guide["quest"]["areas"][4]["game"] = {
        "n": 5, "kind": "", "ready": False, "task_code": "",
        "name_zh": "即將推出", "name_en": "Coming soon",
        "blurb_zh": "", "blurb_en": ""}
    store.update("badges", badge["id"], {"guide_json": guide})

    assert store.upgrade_patrol_game() is True
    task = store.get("tasks", task["id"])
    assert task["type"] == "quiz" and task["pass_score"] == 80
    assert as_json(task.get("config_json"), {}).get("kind") == "patrol"
    game = as_json(store.get("badges", badge["id"]).get("guide_json"), {})[
        "quest"]["areas"][4]["game"]
    assert game["ready"] is True and game["kind"] == "patrol"
    assert game["task_code"] == "M02"
    # a second run changes nothing
    assert store.upgrade_patrol_game() is False


def member(uid, name, position="", complete=False, **fields):
    base = {"id": uid, "name_zh": name, "name_en": name, "avatar": "🦊",
            "position_zh": position, "position_en": position, "position": position,
            "interests": "", "experience": "", "share": "", "strength": "",
            "complete": complete, "is_self": False,
            "is_contact": "聯絡" in position,
            "contact_email": "c@example.com" if "聯絡" in position else ""}
    base.update(fields)
    return base


def test_every_question_can_be_answered_from_its_options():
    from scout.patrol_game import build_questions

    members = [member("me", "阿明", "隊員", True, interests="足球", strength="跑步")]
    members += [member(f"m{i}", f"成員{i}", position, True,
                       interests=f"興趣{i}", strength=f"強項{i}")
                for i, position in enumerate(
                    ["小隊長", "副小隊長", "隊員", "小隊聯絡", "紀錄", "物資管理"])]
    questions, key = build_questions(members, "me", seed=7)
    assert questions and len(questions) == len(key)
    for question in questions:
        values = [o["value"] for o in question["options"]]
        assert key[question["id"]] in values, question
        assert len(values) <= 4
    contact_who = next(q for q in questions if q["kind"] == "contact_who")
    assert key[contact_who["id"]] == "m3"          # the member whose job is 聯絡
    assert any("強項" in q["zh"] for q in questions)  # strengths are asked about


def test_the_contact_can_play_too():
    from scout.patrol_game import build_questions

    members = [member("me", "阿明", "小隊聯絡", True, interests="足球", strength="跑步"),
               member("m1", "成員一", "隊員", True, interests="音樂", strength="唱歌")]
    questions, key = build_questions(members, "me", seed=3)
    contact_who = next(q for q in questions if q["kind"] == "contact_who")
    assert key[contact_who["id"]] == "me"
    assert any(o["value"] == "me" for o in contact_who["options"])


def test_strength_is_part_of_a_finished_profile(store, new_scout):
    reply = new_scout.post("/profile", data={
        "position": "隊員", "interests": "露營",
        "experience": "參加了童軍兩年。", "share": "喜歡幫忙。",
    })
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "profile_empty"
    assert store.get("profiles", new_scout.id) is None

    reply = new_scout.post("/profile", data={
        "position": "隊員", "interests": "露營", "strength": "繩結",
        "experience": "參加了童軍兩年。", "share": "喜歡幫忙。",
    })
    assert reply.status_code == 200
    assert store.get("profiles", new_scout.id)["strength"] == "繩結"
    page = new_scout.get("/profile").get_data(as_text=True)
    assert "我的強項" in page and "繩結" in page
