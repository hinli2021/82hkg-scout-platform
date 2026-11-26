"""遊戲 5 — 小隊名冊卡（第 2 項，M02）.

The bluff's game is the patrol itself: member cards are read live from the
accounts and profiles, so a scout who joins appears at once. The scout
then seats the patrol on the raft — every station states a requirement
worded from one member's own facts, and the member whose 職位 is 聯絡
always takes the signal station, reached in person or through the leader.
Email addresses are private: none of them ever appears in the game.
Members without a finished profile still appear. Seating 80% of the
stations right completes item 2 with no leader code; below that, nothing
is filed.
"""
from __future__ import annotations

import json
import re

import pytest
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
    match = re.search(r'data-patrol-config="([^"]*)"', page, re.S)
    assert match, "the game page carries its scene"
    import html as _html
    return page, json.loads(_html.unescape(match.group(1)))


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
    # the game wears the same shell as the other games: the whole window,
    # the bluff painting with its HUD, and the dark glass card of words
    assert 'class="is-game"' in page and 'class="cave patrol"' in page
    assert "img/quest/patrol/bluff.jpg" in page and "cave-hud" in page
    assert "cave-card" in page and "patrol.css" not in page
    assert "data-pat-more" in page          # the same shell pieces as games 1–4

    # the story is told first, page by page; only then do the members show
    assert "data-pat-story" in page and "海邊的木筏" in page
    assert page.count("data-pat-page") == 3
    assert 'data-pat-cards hidden' in page and "data-pat-story-next" in page
    # the card's patrol strip carries the label words, never a raw object
    assert isinstance(scene["patrol_zh"], str) and scene["patrol_zh"]
    assert "[object Object]" not in page
    # phones and tablets: the flip card, board and raft shrink to fit,
    # with finger-sized tap targets
    import pathlib
    css = (pathlib.Path(__file__).resolve().parent.parent / "static"
           / "styles.css").read_text(encoding="utf-8")
    assert "@media (max-width: 700px)" in css and ".pat-card" in css
    assert "@media (min-width: 701px) and (max-width: 1100px)" in css
    assert "min-height: 44px" in css
    # the painting belongs to the story at the opening: once the game is
    # under way it folds away and the panel takes the whole window
    assert ".patrol.is-playing .cave-picture" in css
    assert ".patrol.is-playing .cave-card-wrap" in css
    import pathlib as _p
    js = (_p.Path(__file__).resolve().parent.parent / "static" / "js"
          / "patrol.js").read_text(encoding="utf-8")
    # from the member cards onward the painting folds away and the
    # seaside is the background; nothing brings the painting back
    assert 'root.classList.add("is-playing")' in js
    assert 'root.classList.remove("is-playing")' not in js
    assert "data-pat-view-cards" in page and "返回木筏" in js
    # every member card is on the table at once — no flipping through
    # them one at a time with previous/next buttons
    assert "data-pat-prev" not in page and "data-pat-next" not in page
    assert ".map(memberCard)" in js and "renderCards" in js
    # the position wears a medal pill; the patrol's leaders are marked
    # apart (the contact's card looks like everyone else's)
    assert "poke-position" in js and "is-leader" in js and "is-contact" not in js
    # after the cards, the scout decides their own position in the game:
    # the step is on the page, its save address and list are in the scene,
    # and a raft submitted without one is sent back to that step
    assert "data-pat-position" in page and "決定你的職位" in page
    assert scene["position_url"].endswith("/patrol-position")
    # the seeded 隊員 is one of the removed ranks: it comes back as Other
    assert scene["my_position_choice"] == "__other__"
    assert scene["my_position_other"] == "隊員"
    assert any(pair[0] == "聯絡" for pair in scene["position_options"])
    # every listed position carries what the role has to do
    assert scene["position_descriptions"]["聯絡"][0] == "記錄出席，聯絡和通知大家。"
    assert "data-pat-position-desc" in page and 'name="position_desc"' in page
    assert "j.need_position" in js and "enterPosition" in js
    # a replay starts from the beginning too, story first; leaving
    # before the raft sets off asks first, like every other game
    assert "if (data.cleared_now)" not in js
    assert "patrol-exit-title" in js and "要離開海邊嗎？" in js
    assert "[data-pat-stay]" in js and "[data-pat-leave]" in js
    assert 'window.addEventListener("beforeunload"' in js
    # while playing, the panel rests on a soft seaside background
    assert "img/quest/patrol/seaside.jpg" in css
    assert (_p.Path(__file__).resolve().parent.parent / "static" / "img"
            / "quest" / "patrol" / "seaside.jpg").is_file()
    # the member card IS the profile page's card: the same char-card
    # markup and classes, fed with the same mascot colours and numbers
    assert "pat-card char-card" in js and "poke-head" in js
    assert "char-back" in js and "char-stats" in js
    # the card carries no badge count, task count or streak numbers
    assert "poke-bottom" not in js and "Day streak" not in js
    assert ".pat-card.char-card" in css and ".pat-phead" not in css
    # the picture window keeps its space on the narrower game card
    assert ".pat-card .char-portrait" in css and "min-height: 9rem" in css
    from scout.engine import progress_for
    members = {m["id"]: m for m in scene["members"]}
    mine = progress_for(store, viewer["id"])
    card = members[viewer["id"]]
    assert card["points_balance"] == mine["stats"]["points_balance"]
    assert card["badges_done"] == mine["stats"]["badges_done"]
    assert card["badges_total"] == mine["overall"]["badges_total"]
    assert card["tasks_done"] == mine["overall"]["tasks_done"]
    assert card["streak_current"] == mine["stats"]["streak_current"]
    assert card["mascot"]["emoji"] == "🦦" and card["mascot"]["tint"]
    assert card["earned_badges"] == [
        {"emoji": b.get("emoji") or "🎖", "title_zh": b.get("title_zh") or "",
         "title_en": b.get("title_en") or ""}
        for b in mine["badges"] if b["earned"]]
    # every Otter scout is on a card: the seeded pair, the new members, and
    # the member with no profile at all
    assert {viewer["id"], contact["id"], singer["id"], rookie["id"]} <= set(members)
    assert members[contact["id"]]["is_contact"] is True
    # email addresses are private: no member of the game carries one, and
    # no address appears anywhere on the page
    assert all("contact_email" not in m and "email" not in m
               for m in members.values())
    assert "contact@82hkg.example" not in page
    assert "singer@82hkg.example" not in page
    # the unfinished profile is marked, not hidden
    assert members[rookie["id"]]["complete"] is False
    assert members[singer["id"]]["strength"] == "唱歌"

    # the raft: one station per crew member, each with its own requirement,
    # and the contact's signal station carries the way to reach them
    seats = scene["raft"]
    assert len(seats) == len(scene["crew"]) >= 4
    assert {viewer["id"], contact["id"], singer["id"], rookie["id"]} <= set(scene["crew"])
    signal = next(s for s in seats if s["role_zh"] == "通訊站")
    assert "小隊聯絡" in signal["criterion_zh"] and "@" not in signal["criterion_zh"]
    assert len({s["criterion_zh"] for s in seats}) == len(seats)
    # who sits where never reaches the page — the key stays in the token
    assert "run_key" in scene and scene["run_key"]
    for seat in seats:
        assert "member" not in seat and "member_id" not in seat
    assert set(key_of(scene).values()) == set(scene["crew"])

    # stage 1: the board names every scout in the unit, patrols unmarked,
    # and every member has a profile card drawn from their live profile
    board = scene["roster_board"]
    assert {m["id"] for m in members.values()} <= {b["id"] for b in board}
    assert len(board) > len(members)            # other patrols are on it too
    assert all(set(b) == {"id", "name_zh", "name_en"} for b in board)
    assert scene["roster_size"] == len(members)
    by_id = {m["id"]: m for m in scene["members"]}
    assert by_id[singer["id"]]["strength"] == "唱歌"
    assert by_id[singer["id"]]["card_photo_url"] == ""  # no leader-approved photo yet

    # editing the profile redraws the card at once
    store.update("profiles", singer["id"], {"strength": "彈結他"})
    _, scene = scene_of(client, task["id"])
    by_id = {m["id"]: m for m in scene["members"]}
    assert by_id[singer["id"]]["strength"] == "彈結他"


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
    assert tester["id"] not in scene["crew"]
    assert tester["id"] not in {b["id"] for b in scene["roster_board"]}

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


def test_new_members_and_profile_edits_are_matched_on_the_next_load(store, app):
    """The game reads the patrol live on every load: a scout who joins
    the patrol appears on the cards, the board and the raft at once, an
    edit to anyone's profile redraws their card and re-words their
    station, and a scout who leaves the patrol leaves the game."""
    viewer, contact, singer, rookie = seed_patrol(store)
    task = task_of(store)
    client = login(app, viewer)

    _, scene = scene_of(client, task["id"])
    baseline_ids = {m["id"] for m in scene["members"]}

    # a new member joins the patrol — with no profile written yet
    newbie = add_member(store, "patrolnewbie", "新隊員", "New Member", "", None)
    _, scene = scene_of(client, task["id"])
    member_ids = {m["id"] for m in scene["members"]}
    assert newbie["id"] in member_ids and newbie["id"] not in baseline_ids
    assert newbie["id"] in {b["id"] for b in scene["roster_board"]}
    assert newbie["id"] in scene["crew"]
    assert newbie["id"] in key_of(scene).values()

    # the new member then fills in their profile: the next load shows the
    # new facts on the card, and their raft station is worded from them
    store.insert("profiles", {"user_id": newbie["id"], "visible": True,
                              "updated_at": "2026-01-02",
                              **full_profile("康樂", "天文", "急救")})
    _, scene = scene_of(client, task["id"])
    by_id = {m["id"]: m for m in scene["members"]}
    assert by_id[newbie["id"]]["strength"] == "急救"
    assert by_id[newbie["id"]]["position"] == "康樂"
    seat_id = next(sid for sid, uid in key_of(scene).items()
                   if uid == newbie["id"])
    seat = next(s for s in scene["raft"] if s["id"] == seat_id)
    assert "急救" in seat["criterion_zh"]

    # editing an existing member's details is matched too
    store.update("profiles", singer["id"], {"strength": "彈結他"})
    _, scene = scene_of(client, task["id"])
    by_id = {m["id"]: m for m in scene["members"]}
    assert by_id[singer["id"]]["strength"] == "彈結他"

    # and a member who moves to another patrol is gone from the game,
    # though their name stays on the unit board for stage 1
    store.update("users", newbie["id"], {"patrol": "Tiger"})
    _, scene = scene_of(client, task["id"])
    assert newbie["id"] not in {m["id"] for m in scene["members"]}
    assert newbie["id"] not in scene["crew"]
    assert newbie["id"] in {b["id"] for b in scene["roster_board"]}


def test_stage_one_needs_the_exact_patrol(store, app):
    """The board names the whole unit; only the exact patrol — nobody
    missing, nobody extra — opens stage 2, and a miss is answered with
    counts only."""
    viewer, contact, singer, rookie = seed_patrol(store)
    task = task_of(store)
    client = login(app, viewer)
    _, scene = scene_of(client, task["id"])
    url = f"/tasks/{task['id']}/patrol-stage1"
    patrol_ids = [m["id"] for m in scene["members"]]
    outsider = next(b["id"] for b in scene["roster_board"]
                    if b["id"] not in patrol_ids)

    # one missing, one extra: refused, with counts and no names
    reply = client.post(url, data={"run_key": scene["run_key"],
                                   "members": patrol_ids[1:] + [outsider]},
                        headers=HEADERS)
    body = reply.get_json()
    assert reply.status_code == 400 and body["error"] == "patrol_roster"
    assert body["detail"] == {"right": len(patrol_ids) - 1, "extra": 1, "missing": 1}
    assert contact["display_name_zh"] not in body["message_zh"]

    # the exact patrol opens stage 2
    reply = client.post(url, data={"run_key": scene["run_key"],
                                   "members": patrol_ids}, headers=HEADERS)
    body = reply.get_json()
    assert reply.status_code == 200 and body["passed"] is True

    # a forged run is refused
    reply = client.post(url, data={"run_key": "not-a-token",
                                   "members": patrol_ids}, headers=HEADERS)
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "patrol_expired"


def test_a_two_member_patrol_can_play_the_whole_game(store, app):
    """Patrols are not always six: with just two members the cards, the
    board and the raft all size themselves down and the game completes."""
    viewer = find(store, "scout04")          # the seeded Otter pair
    store.insert("profiles", {"user_id": viewer["id"], "visible": True,
                              "updated_at": "2026-01-01",
                              **full_profile("聯絡", "足球", "跑步")})
    task = task_of(store)
    client = login(app, viewer)
    _, scene = scene_of(client, task["id"])
    assert len(scene["members"]) == 2
    assert len(scene["raft"]) == len(scene["crew"]) == 2

    reply = client.post(f"/tasks/{task['id']}/patrol-stage1",
                        data={"run_key": scene["run_key"],
                              "members": [m["id"] for m in scene["members"]]},
                        headers=HEADERS)
    assert reply.get_json()["passed"] is True
    reply = client.post(f"/tasks/{task['id']}/patrol-submit",
                        data={**key_of(scene), "run_key": scene["run_key"],
                              "elapsed_ms": "60000"}, headers=HEADERS)
    assert reply.get_json()["passed"] is True
    assert len(completed_records(store, viewer["id"], task["id"])) == 1


def test_the_raft_sizes_itself_to_any_patrol():
    """Fewer than six, exactly six, or far more: every member gets one
    station, every station keeps its own name, and the plan covers all."""
    from scout.patrol_game import build_raft

    for size in (2, 5, 6, 7, 12, 13):
        members = [member(f"m{i}", f"成員{i}",
                          "小隊聯絡" if i == 0 else "隊員", True,
                          interests=f"興趣{i}", strength=f"強項{i}")
                   for i in range(size)]
        seats, key, crew = build_raft(members, "m1", seed=11)
        assert len(seats) == len(key) == len(crew) == size
        assert set(key.values()) == {m["id"] for m in members}
        assert len({s["role_zh"] for s in seats}) == size
        signal = next(s for s in seats if s["role_zh"] == "通訊站")
        assert key[signal["id"]] == "m0"


@pytest.mark.parametrize("size", range(3, 9))
def test_patrols_of_three_to_eight_play_the_whole_game(store, app, size):
    """Patrols run from three to eight scouts: at every size the cards
    step lays out one profile card per member, the board asks for
    exactly that patrol, the raft seats everyone, and the game files."""
    viewer = find(store, "scout04")
    store.update("users", viewer["id"], {"patrol": "Falcon"})
    viewer = find(store, "scout04")
    store.insert("profiles", {"user_id": viewer["id"], "visible": True,
                              "updated_at": "2026-01-01",
                              **full_profile("聯絡", "足球", "跑步")})
    duties = ["康樂", "文書", "物資管理", "氣象員", "報時員", "情緒輔助", "法官"]
    for i in range(size - 1):
        member = add_member(store, f"falcon{i}", f"隼隊員{i}", f"Falcon {i}", "",
                            full_profile(duties[i], f"興趣{i}", f"強項{i}"))
        store.update("users", member["id"], {"patrol": "Falcon"})
    task = task_of(store)
    client = login(app, viewer)
    _, scene = scene_of(client, task["id"])

    # the introduction: one card per member, every card carrying the
    # facts its profile card is drawn from
    assert scene["playable"] is True
    assert len(scene["members"]) == size and scene["roster_size"] == size
    assert len({m["id"] for m in scene["members"]}) == size
    for member in scene["members"]:
        assert member["name_zh"] and "position_zh" in member
        assert "camping_days" in member and "earned_badges" in member
    assert {m["id"] for m in scene["members"]} <= {
        b["id"] for b in scene["roster_board"]}

    # the raft seats the whole patrol, each station telling one member
    assert len(scene["raft"]) == len(scene["crew"]) == size
    assert len({seat["criterion_zh"] for seat in scene["raft"]}) == size

    reply = client.post(f"/tasks/{task['id']}/patrol-stage1",
                        data={"run_key": scene["run_key"],
                              "members": [m["id"] for m in scene["members"]]},
                        headers=HEADERS)
    assert reply.get_json()["passed"] is True
    reply = client.post(f"/tasks/{task['id']}/patrol-submit",
                        data={**key_of(scene), "run_key": scene["run_key"],
                              "elapsed_ms": "60000"}, headers=HEADERS)
    assert reply.get_json()["passed"] is True
    assert len(completed_records(store, viewer["id"], task["id"])) == 1


def test_game_5_cannot_finish_until_the_scout_decides_a_position(store, app):
    """The position is the last step: a perfect raft is graded and held,
    but item 2 is not filed until the scout decides a position inside
    the game. A wrong raft earns no shortcut to that step."""
    viewer, *_ = seed_patrol(store)
    store.update("profiles", viewer["id"], {"position": ""})
    task = task_of(store)
    client = login(app, viewer)
    _, scene = scene_of(client, task["id"])
    url = f"/tasks/{task['id']}/patrol-submit"

    # a wrong raft is just wrong — the position step is not offered
    wrong = {seat_id: "" for seat_id, _ in key_of(scene).items()}
    reply = client.post(url, data={**wrong, "run_key": scene["run_key"],
                                   "elapsed_ms": "60000"}, headers=HEADERS)
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "patrol_short"
    assert completed_records(store, viewer["id"], task["id"]) == []

    # the perfect raft is held at the last step, not filed
    reply = client.post(url, data={**key_of(scene), "run_key": scene["run_key"],
                                   "elapsed_ms": "60000"}, headers=HEADERS)
    body = reply.get_json()
    assert reply.status_code == 200
    assert body["passed"] is False and body["need_position"] is True
    assert completed_records(store, viewer["id"], task["id"]) == []

    reply = client.post(f"/tasks/{task['id']}/patrol-position",
                        data={"position_choice": "康樂"}, headers=HEADERS)
    body = reply.get_json()
    assert reply.status_code == 200 and body["position"] == "康樂"
    assert store.get("profiles", viewer["id"])["position"] == "康樂"
    fresh = body["scene"]
    mine = next(m for m in fresh["members"] if m["id"] == viewer["id"])
    assert mine["position"] == "康樂"  # the rebuilt cards carry it at once

    # the same seating sent once more now finishes the game
    reply = client.post(url, data={**key_of(scene), "run_key": scene["run_key"],
                                   "elapsed_ms": "60000"}, headers=HEADERS)
    assert reply.get_json()["passed"] is True
    assert len(completed_records(store, viewer["id"], task["id"])) == 1


def test_leaders_lead_the_deck_and_the_contact_is_ordinary(store, app):
    """隊長 and 副隊長 stand at the front of the cards, marked as
    leaders; the patrol contact keeps an ordinary card."""
    viewer, contact, *_ = seed_patrol(store)
    leader = add_member(store, "patrolleader", "鄭隊長", "Cheng Leader",
                        "", full_profile("隊長", "露營", "領導"))
    deputy = add_member(store, "patroldeputy", "黃副隊", "Wong Deputy",
                        "", full_profile("副隊長", "行山", "繩結"))
    task = task_of(store)
    client = login(app, viewer)
    _, scene = scene_of(client, task["id"])
    ids = [m["id"] for m in scene["members"]]
    assert ids[0] == leader["id"] and ids[1] == deputy["id"]
    assert ids[2] == contact["id"]  # leaders first, then the contact
    tiers = {m["id"]: m["leader_tier"] for m in scene["members"]}
    assert tiers[leader["id"]] == 2 and tiers[deputy["id"]] == 1
    assert tiers[contact["id"]] == 0
    # the insignia bars from the troop's chart ride on the same members:
    # one stripe for the deputy, two for the leader, none for the rest
    bars = {m["id"]: m["rank_bar"] for m in scene["members"]}
    assert bars[leader["id"]] == 2 and bars[deputy["id"]] == 1
    assert bars[contact["id"]] == 0
    # a senior stored under the old spelling 高級小隊長 is the 團隊長
    senior = add_member(store, "patrolsenior", "高隊長", "Senior",
                        "", full_profile("高級小隊長", "露營", "領導"))
    _, scene = scene_of(client, task["id"])
    senior_row = next(m for m in scene["members"] if m["id"] == senior["id"])
    assert senior_row["rank_bar"] == 3 and senior_row["leader_tier"] == 2


def test_member_cards_carry_the_profile_cards_own_facts(store, app):
    """The card in the game is the member's profile card: the scene
    carries the camping and hiking counts the profile card shows in
    place of the old written experience, so both faces can say exactly
    what the profile page says."""
    viewer, *_ = seed_patrol(store)
    camper = add_member(store, "patrolcamper", "陳營友", "Chan Camper", "",
                        {"position": "康樂", "interests": "露營",
                         "strength": "生火", "experience": "",
                         "camping_days": "6", "hiking_times": "20+",
                         "share": "喜歡在營地幫忙。"})
    task = task_of(store)
    client = login(app, viewer)
    _, scene = scene_of(client, task["id"])
    row = next(m for m in scene["members"] if m["id"] == camper["id"])
    assert row["camping_days"] == "6" and row["hiking_times"] == "20+"


def test_game_5_cannot_hand_out_a_leader_rank(store, app):
    """The last step decides a duty, never a rank: 隊長 and friends
    are the leader's appointment, in the game as much as on the form."""
    viewer, *_ = seed_patrol(store)
    task = task_of(store)
    client = login(app, viewer)
    reply = client.post(f"/tasks/{task['id']}/patrol-position",
                        data={"position_choice": "__other__",
                              "position_other": "隊長",
                              "position_desc": "帶領小隊"}, headers=HEADERS)
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "profile_position_rank"
    assert store.get("profiles", viewer["id"])["position"] == "隊員"


def test_a_new_position_in_game_5_needs_its_description(store, app):
    """Inventing a position at the last step means describing it: the
    description is kept, and the next scout sees it on the list."""
    viewer, *_ = seed_patrol(store)
    task = task_of(store)
    client = login(app, viewer)
    url = f"/tasks/{task['id']}/patrol-position"

    reply = client.post(url, data={"position_choice": "__other__",
                                   "position_other": "天氣預報員"}, headers=HEADERS)
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "profile_position_desc"
    assert store.get("profiles", viewer["id"])["position"] == "隊員"

    reply = client.post(url, data={"position_choice": "__other__",
                                   "position_other": "天氣預報員",
                                   "position_desc": "出發前報告天氣"}, headers=HEADERS)
    body = reply.get_json()
    assert reply.status_code == 200 and body["position"] == "天氣預報員"
    assert store.get("profiles", viewer["id"])["position"] == "天氣預報員"
    assert body["position_descriptions"]["天氣預報員"][0] == "出發前報告天氣"

    _, scene = scene_of(client, task["id"])
    assert any(pair[0] == "天氣預報員" for pair in scene["position_options"])
    assert scene["position_descriptions"]["天氣預報員"][0] == "出發前報告天氣"
    assert scene["my_position_choice"] == "天氣預報員"


def test_only_a_fully_correct_raft_completes_item_two(store, app):
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

    # one wrong member is still a miss, and the reply gives no hint:
    # no count, no score, nothing about which station is wrong
    seats = list(key)
    almost = dict(key)
    almost[seats[0]], almost[seats[1]] = key[seats[1]], key[seats[0]]
    reply = client.post(url, data={**almost, "run_key": scene["run_key"],
                                   "elapsed_ms": "60000"}, headers=HEADERS)
    body = reply.get_json()
    assert reply.status_code == 400 and body["error"] == "patrol_short"
    assert "安排對了" not in body["message_zh"] and "of" not in body["message_en"].split(":")[0]
    assert not body.get("detail")
    assert completed_records(store, viewer["id"], task["id"]) == []

    reply = client.post(url, data={**key, "run_key": scene["run_key"],
                                   "elapsed_ms": "60000"}, headers=HEADERS)
    body = reply.get_json()
    assert reply.status_code == 200 and body["passed"] is True
    records = completed_records(store, viewer["id"], task["id"])
    assert len(records) == 1 and records[0]["score"] == 100
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
    assert task["type"] == "quiz" and task["pass_score"] == 100
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
            "is_contact": "聯絡" in position}
    base.update(fields)
    return base


def test_the_raft_seats_every_member_once_and_stays_solvable():
    """Each station's wording picks out exactly one member, so the cards
    the scout just flipped are always enough to seat the raft."""
    from scout.patrol_game import build_raft

    members = [member("me", "阿明", "隊員", True, interests="足球", strength="跑步")]
    members += [member(f"m{i}", f"成員{i}", position, True,
                       interests=f"興趣{i}", strength=f"強項{i}")
                for i, position in enumerate(
                    ["小隊長", "副小隊長", "隊員", "小隊聯絡", "紀錄", "物資管理"])]
    seats, key, crew = build_raft(members, "me", seed=7)
    assert len(seats) == len(key) == len(crew) == 7
    assert set(key.values()) == {m["id"] for m in members}
    assert len({s["criterion_zh"] for s in seats}) == len(seats)
    for seat in seats:
        assert "member" not in seat          # the seating plan stays server-side
    signal = next(s for s in seats if s["role_zh"] == "通訊站")
    assert key[signal["id"]] == "m3"          # the member whose job is 聯絡
    assert "小隊聯絡" in signal["criterion_zh"] and "@" not in signal["criterion_zh"]


def test_two_members_with_the_same_job_are_still_told_apart():
    """A shared 職位 cannot name a member on its own; the wording adds a
    second fact until only one member matches both."""
    from scout.patrol_game import build_raft

    members = [member("me", "阿明", "隊員", True, interests="足球", strength="跑步"),
               member("m1", "成員一", "隊員", True, interests="音樂", strength="唱歌"),
               member("m2", "成員二", "小隊聯絡", True, interests="露營", strength="繩結")]
    seats, key, _crew = build_raft(members, "me", seed=3)
    by_member = {key[s["id"]]: s for s in seats}
    assert "唱歌" in by_member["m1"]["criterion_zh"]
    assert "跑步" in by_member["me"]["criterion_zh"]
    assert key[by_member["m2"]["id"]] == "m2"


def test_the_contact_can_play_too():
    from scout.patrol_game import build_raft

    members = [member("me", "阿明", "小隊聯絡", True, interests="足球", strength="跑步"),
               member("m1", "成員一", "隊員", True, interests="音樂", strength="唱歌")]
    seats, key, _crew = build_raft(members, "me", seed=3)
    signal = next(s for s in seats if s["role_zh"] == "通訊站")
    assert key[signal["id"]] == "me"          # the contact seats themselves


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


def test_a_replay_still_tells_the_story(store, app):
    """A replay looks like starting the game again: the same opening a
    first-time scout sees, with no "already done" recap in front of it."""
    viewer, *_ = seed_patrol(store)
    task = task_of(store)
    store.insert("progress_records", {
        "user_id": viewer["id"], "task_id": task["id"], "status": "completed",
        "attempt_no": 1, "submitted_at": "2026-01-02"})
    client = login(app, viewer)
    page, scene = scene_of(client, task["id"])
    assert scene["cleared_now"] is True
    assert page.count("data-pat-page") == 3
    assert "海邊的木筏" in page and "沙灘上，你的小隊正在等你" in page
    assert "木筏已經離岸" not in page


def test_the_patrol_story_closes_the_linked_journey(store):
    """Game 5 gathers the four earlier places and escapes the island;
    the badge map's last area tells the same ending."""
    from scout.content import member_badge_guide
    area5 = member_badge_guide()["quest"]["areas"][4]
    assert "木筏" in area5["hint_zh"] and "小隊" in area5["hint_zh"]


def test_an_upgraded_patrol_task_moves_from_80_to_100(store):
    """A patrol task already in game shape but still marked 80 follows
    the every-station rule, shown as 100, on the next start."""
    task = task_of(store)
    store.update("tasks", task["id"], {"pass_score": 80})
    assert store.upgrade_patrol_game() is True
    assert store.get("tasks", task["id"])["pass_score"] == 100
    assert store.upgrade_patrol_game() is False


def test_patrol_finish_offers_a_clear_way_on():
    """When the raft sets off, one big button leads on: the next game the map
    still owes, or back to the badge when game 5 was the last one."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    tpl = (root / "templates/scout/patrol.html").read_text(encoding="utf-8")
    assert "data-pat-finish" in tpl and "data-pat-finish-link" in tpl
    js = (root / "static/js/patrol.js").read_text(encoding="utf-8")
    assert "data-pat-finish" in js and "next_game" in js and "badge_url" in js
