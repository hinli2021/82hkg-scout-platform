"""Sign-in: patrol → name (no password first time) → password, demo tiles, resets."""
from __future__ import annotations

import re
import urllib.parse


import pytest                                    # noqa: E402

from scout.mailer import mask_email as mailer_mask   # noqa: E402


def _find(store, username):
    return next(u for u in store.list("users") if u["username"] == username)


# ── the doors ───────────────────────────────────────────────────────────────

def test_health_reports_storage_mode(client):
    body = client.get("/health").get_json()
    assert body["ok"] is True
    assert body["storage"] == "local"


def test_login_page_is_just_the_scene_and_the_leader_door(client):
    """Front page: the three animals, one line of coaching, the leader door.

    No title, no demo shortcuts, no "forgot password", no language switch —
    those live elsewhere (see the name picker and the password pages).
    """
    page = client.get("/login").get_data(as_text=True)
    for patrol in ("Tiger", "Otter", "Seagull"):                    # the patrols, in English
        assert patrol in page
    assert "老虎" not in page and "水獺" not in page                  # …not the 中文 labels
    assert "領袖登入" in page                                       # bottom-right door
    assert "demo1" not in page and "demo3" not in page              # no demo buttons
    assert "忘記密碼" not in page                                    # no reset link here
    assert "/set-language/" not in page                             # no language switch
    assert "<h1" not in page.split('class="scene-hud bc"')[0]  # no title over the camp scene
    assert "scene-hud tl" not in page                               # …and no top-left HUD
    assert "scene-leader" in page                                   # styled as a button


def test_the_leaders_door_opens_with_0082(client):
    """領袖登入 uses the short unit code 0082 (leader1)."""
    from scout.schema import DEMO_PASSWORDS

    assert DEMO_PASSWORDS["leader"] == "0082"
    page = client.get("/login/leader").get_data(as_text=True)
    assert "0082" in page                                  # the hint on the card
    assert page.count('type="password"') == 1               # one box: the code
    assert 'required autofocus' in page                     # and the cursor starts in it
    assert "用戶名稱" not in page                            # no username to fill in
    wrong = client.post("/login/leader", data={"password": "leader1234"})
    assert wrong.status_code == 401                        # the old password is gone
    empty = client.post("/login/leader", data={"password": ""})
    assert empty.status_code == 401                        # and an empty box signs nobody in
    # the code on its own is enough — that is the whole point of 0082
    code_only = client.post("/login/leader", data={"password": "0082"}, follow_redirects=False)
    assert code_only.status_code in (302, 303), code_only.status_code
    assert "/leader" in code_only.headers["Location"]
    # and the long way round still works, for anyone who has a username to type
    named = client.post("/login/leader", data={"username": "leader1", "password": "0082"},
                        follow_redirects=False)
    assert named.status_code in (302, 303)
    assert "/leader" in named.headers["Location"]


def test_an_already_signed_in_leader_is_told_so(client):
    """Opening the leaders' door with a live session must not look like
    "the code was never asked for": the card says you are already in and
    offers the console plus a sign-out (which is how to test the code again).
    """
    client.post("/login/leader", data={"password": "0082"})
    page = client.get("/login/leader").get_data(as_text=True)
    assert "你已經以" in page                                  # told plainly
    assert "進入領袖後台" in page                               # and offered the console
    import re
    assert re.search(r'action="/logout[^"]*"', page)            # and a way out (token rides along)
    assert 'name="password"' not in page                       # the code box is not shown again


def test_a_scout_at_the_leaders_door_is_told_who_they_are(client, store):
    """A scout who opens the leaders' door sees the code box, with a note that
    entering the code switches them to a leader."""
    scout = next(u for u in store.list("users") if u.get("role") == "scout")
    scout["password_hash"] = ""                                # first-time: tap and in
    from scout.util import hash_password
    hashed, salt = hash_password("scout1234")
    store.update("users", scout["id"], {"password_hash": hashed, "password_salt": salt})
    client.post(f"/login/scout/{scout['patrol']}/{scout['id']}", data={"password": "scout1234"})
    page = client.get("/login/leader").get_data(as_text=True)
    assert "你現時以" in page and 'name="password"' in page


def test_the_leaders_card_offers_both_demo_accounts(client):
    """The leaders' sign-in page carries one-tap demo accounts: a leader and a
    scout. Neither needs a password."""
    page = client.get("/login/leader").get_data(as_text=True)
    assert 'data-demo="leader"' in page and 'data-demo="scout"' in page
    assert "示範領袖" in page and "示範童軍" in page
    assert 'action="/login/demo/demo1"' in page          # the leader demo door
    assert 'action="/login/demo/demo2"' in page          # the scout demo door


def test_the_demo_accounts_walk_straight_in(app):
    """One tap each, and no password is asked for on the way."""
    leader = app.test_client()
    r = leader.post("/login/demo/demo1", follow_redirects=False)
    assert r.status_code == 302 and "/leader" in r.headers["Location"]

    scout = app.test_client()
    r = scout.post("/login/demo/demo2", follow_redirects=False)
    assert r.status_code == 302 and "/home" in r.headers["Location"]


def test_root_redirects_to_login_when_signed_out(client):
    assert client.get("/").status_code == 302
    assert "/login" in client.get("/").headers["Location"]


def test_scouts_cannot_self_register(client):
    for path in ("/register", "/signup", "/sign-up", "/join"):
        assert client.get(path).status_code == 404


def test_patrol_picker_lists_only_that_patrols_scouts(client, store):
    page = client.get("/login/scout/Tiger").get_data(as_text=True)
    assert "王小明" in page and "李美儀" in page
    assert "張家豪" not in page          # Otter
    otter = client.get("/login/scout/Otter").get_data(as_text=True)
    assert "張家豪" in otter and "王小明" not in otter


def test_the_name_list_carries_no_first_time_notice(app, client, store):
    """The sign-in page is a plain list of the patrol's names.

    A scout who has not set a password yet is not singled out on it: the tap
    itself leads to the set-a-password form. (Reported: drop the 🆕 第一次登入
    notice from the login page.)
    """
    page = client.get("/login/scout/Seagull").get_data(as_text=True)
    assert "第一次登入" not in page and "First time in" not in page
    assert "new-badge-flag" not in page
    fresh = [u for u in store.list("users")
             if u.get("patrol") == "Seagull" and not u.get("password_hash")]
    assert fresh, "the sample data should keep one scout without a password"
    response = client.get(f"/login/scout/Seagull/{fresh[0]['id']}")
    assert response.status_code == 302 and "/welcome" in response.headers["Location"]


# ── scout sign-in ───────────────────────────────────────────────────────────

def test_scout_signs_in_with_patrol_name_password(app, store):
    scout = _find(store, "scout01")
    client = app.test_client()
    assert client.get(f"/login/scout/Tiger/{scout['id']}").status_code == 200
    response = client.post(f"/login/scout/Tiger/{scout['id']}", data={"password": "scout1234"})
    assert response.status_code == 302
    assert _path(response.headers["Location"]) == "/home"


def test_wrong_password_is_refused(app, store):
    scout = _find(store, "scout01")
    client = app.test_client()
    response = client.post(f"/login/scout/Tiger/{scout['id']}", data={"password": "nope"})
    assert response.status_code == 401


def test_locked_account_cannot_sign_in(app, store):
    scout = _find(store, "scout02")
    app.extensions["store"].update("users", scout["id"], {"status": "locked"})
    client = app.test_client()
    response = client.post(f"/login/scout/Tiger/{scout['id']}", data={"password": "scout1234"})
    assert response.status_code == 403


def _path(location: str) -> str:
    return urllib.parse.urlsplit(location).path


def test_first_tap_needs_no_password(app, store, fresh_scout):
    """Tapping your own name walks you in — nothing is asked on the way."""
    response = fresh_scout.get(f"/login/scout/Seagull/{fresh_scout.id}")
    assert response.status_code == 302
    assert _path(response.headers["Location"]) == "/welcome"   # …then we ask
    assert store.get("users", fresh_scout.id)["password_hash"] in (None, "")


def test_first_entry_lands_on_the_mandatory_setup(fresh_scout):
    """Tap a name without a password, then require both new fields."""
    tap = fresh_scout.get(f"/login/scout/Seagull/{fresh_scout.id}")
    page = fresh_scout.get(_path(tap.headers["Location"])).get_data(as_text=True)
    assert "設定你的密碼及電郵" in page
    assert "歡迎" in page and "兩項均為必填" in page
    assert 'name="password"' in page and 'name="confirm"' in page
    assert 'name="email"' in page and 'autocomplete="email" required' in page
    assert "稍後再設定" not in page and "Do it later" not in page
    assert 'href="/home' not in page  # no skip link


def test_unfinished_setup_cannot_open_scout_pages_or_submit_a_game(
        app, store, scout_client, fresh_scout):
    """Direct links/API calls may not bypass the first-time form."""
    assert scout_client.get("/home").status_code == 200
    fresh_scout.get(f"/login/scout/Seagull/{fresh_scout.id}")
    cave = next(t for t in store.list("tasks") if t.get("code") == "M04")
    badge = next(b for b in store.list("badges") if b.get("code") == "SC-01")
    for path in ("/", "/login", "/home", "/badges", f"/badges/{badge['id']}",
                 f"/tasks/{cave['id']}/cave", "/history", "/rewards", "/leaderboard"):
        response = fresh_scout.get(path)
        assert response.status_code == 302 and _path(response.headers["Location"]) == "/welcome", path
    for path in (f"/tasks/{cave['id']}/cave-submit", f"/tasks/{cave['id']}/submit", "/upload"):
        response = fresh_scout.post(path, data={})
        assert response.status_code == 403 and response.get_json()["error"] == "setup_required", path
    assert not any(row.get("user_id") == fresh_scout.id for row in store.list("points_ledger"))
    assert fresh_scout.get("/welcome").status_code == 200


def test_the_ask_is_not_shown_to_scouts_who_already_have_a_password(scout_client):
    response = scout_client.get("/welcome")
    assert response.status_code == 302
    assert _path(response.headers["Location"]) == "/home"


def test_first_time_password_rules(fresh_scout, store):
    fresh_scout.get(f"/login/scout/Seagull/{fresh_scout.id}")

    short = fresh_scout.post("/welcome", data={"password": "abc", "confirm": "abc"})
    assert short.status_code == 400 and short.get_json()["error"] == "bad_password"
    mismatch = fresh_scout.post("/welcome", data={"password": "tiger777", "confirm": "tiger778"})
    assert mismatch.status_code == 400
    for missing in ({"password": "tiger777", "confirm": "tiger777"},
                    {"password": "tiger777", "confirm": "tiger777", "email": "   "}):
        result = fresh_scout.post("/welcome", data=missing)
        assert result.status_code == 400 and result.get_json()["error"] == "bad_email"
    bad_mail = fresh_scout.post("/welcome", data={"password": "tiger777", "confirm": "tiger777",
                                                  "email": "not-an-email"})
    assert bad_mail.status_code == 400 and bad_mail.get_json()["error"] == "bad_email"
    saved_before = store.get("users", fresh_scout.id)
    assert saved_before["password_hash"] in (None, "")
    assert saved_before["email"] == "" and saved_before["must_change_password"] is True
    assert _path(fresh_scout.get("/home").headers["Location"]) == "/welcome"

    saved = fresh_scout.post("/welcome", data={"password": "tiger777", "confirm": "tiger777",
                                               "email": "ng@example.com"})
    assert saved.status_code == 200 and saved.get_json()["ok"] is True
    row = store.get("users", fresh_scout.id)
    assert row["password_hash"] and row["email"] == "ng@example.com"
    assert row["must_change_password"] is False
    assert fresh_scout.get("/home").status_code == 200
    assert fresh_scout.post("/welcome", data={"password": "reset123", "confirm": "reset123",
                                               "email": "other@example.com"}).status_code == 409


def test_leader_initial_password_still_requires_personal_password_and_email(
        app, store, leader_client):
    leader_client.post("/leader/accounts", data={
        "display_name_zh": "新小隊員", "patrol": "Tiger", "password": "temp-0082",
    })
    user = next(u for u in store.list("users") if u.get("display_name_zh") == "新小隊員")
    assert user["password_hash"] and user["must_change_password"] is True
    client = app.test_client()
    url = f"/login/scout/Tiger/{user['id']}"
    assert 'name="password"' in client.get(url).get_data(as_text=True)
    assert client.post(url, data={"password": "wrong"}).status_code == 401
    login = client.post(url, data={"password": "temp-0082"})
    assert login.status_code == 302 and _path(login.headers["Location"]) == "/welcome"
    assert _path(client.get("/home").headers["Location"]) == "/welcome"
    refused = client.post("/welcome", data={"password": "personal42", "confirm": "personal42"},
                          headers={"Accept": "application/json"})
    assert refused.status_code == 400 and refused.get_json()["error"] == "bad_email"
    assert store.get("users", user["id"])["must_change_password"] is True
    done = client.post("/welcome", data={"password": "personal42", "confirm": "personal42",
                                         "email": "member@example.com"})
    assert done.status_code == 302 and _path(done.headers["Location"]) == "/home"
    assert client.get("/home").status_code == 200
    assert store.get("users", user["id"])["must_change_password"] is False
    client.post("/logout")
    assert client.post(url, data={"password": "temp-0082"}).status_code == 401
    assert _path(client.post(url, data={"password": "personal42"}).headers["Location"]) == "/home"


def test_plain_form_post_redirects_home_with_a_flash(fresh_scout):
    fresh_scout.get(f"/login/scout/Seagull/{fresh_scout.id}")
    fresh_scout.client.post("/welcome", data={"password": "tiger777", "confirm": "tiger777",
                                               "email": "ng@example.com"})
    page = fresh_scout.get("/home").get_data(as_text=True)
    assert "密碼及電郵已設定" in page


def test_scout_can_sign_in_again_with_the_new_password(app, store, new_scout):
    client = app.test_client()
    good = client.post(f"/login/scout/Seagull/{new_scout.id}", data={"password": "tiger777"})
    assert good.status_code == 302
    assert client.post(f"/login/scout/Seagull/{new_scout.id}",
                       data={"password": "wrong"}).status_code == 401


def test_returning_scout_gets_a_password_box_not_a_setup_form(app, store):
    scout = _find(store, "scout01")                     # already has a password
    client = app.test_client()
    page = client.get(f"/login/scout/Tiger/{scout['id']}").get_data(as_text=True)
    assert "請輸入你的密碼" in page and 'name="confirm"' not in page


def test_a_plain_form_post_does_not_sign_the_scout_out(app, store, fresh_scout):
    """flash() must not clobber the sign-in cookie (it used to share the name)."""
    fresh_scout.get(f"/login/scout/Seagull/{fresh_scout.id}")
    fresh_scout.client.post("/welcome", data={"password": "tiger777", "confirm": "tiger777",
                                               "email": "ng@example.com"})
    page = fresh_scout.get("/home")
    assert page.status_code == 200
    assert "密碼及電郵已設定" in page.get_data(as_text=True)  # the flash survived too
    assert 'class="setup-card' not in page.get_data(as_text=True)


# ── the preview iframe blocks cookies, so the token rides in the URL ────────

def _drop_cookies(thing):
    """A brand-new browser that stores nothing — the preview iframe case."""
    flask_app = getattr(thing, "application", thing)      # accepts app or client
    return flask_app.test_client()


def test_demo_tile_survives_blocked_cookies(app):
    client = _drop_cookies(app.test_client())
    r = client.post("/login/demo/demo2")
    assert r.status_code == 302
    assert "sid=" in r.headers["Location"]                    # token rides along…
    page = _drop_cookies(app).get(r.headers["Location"])   # …with no cookie at all
    assert page.status_code == 200
    assert "你好" in page.get_data(as_text=True)


def test_leader_demo_tile_survives_blocked_cookies(app):
    client = _drop_cookies(app.test_client())
    r = client.post("/login/demo/demo1")
    assert "sid=" in r.headers["Location"]
    page = _drop_cookies(app).get(r.headers["Location"])
    assert page.status_code == 200 and "領袖總覽" in page.get_data(as_text=True)


def test_every_link_keeps_the_token(app):
    client = _drop_cookies(app.test_client())
    r = client.post("/login/demo/demo2")
    page = _drop_cookies(app).get(r.headers["Location"]).get_data(as_text=True)
    assert "sid=" in page                                  # nav links carry it
    href = re.search(r'href="(/badges[^"]*sid=[^"]+)"', page).group(1)
    follow = _drop_cookies(app).get(href)
    assert follow.status_code == 200 and "獎章" in follow.get_data(as_text=True)


def test_first_tap_and_welcome_card_survive_blocked_cookies(app, store):
    scout = _find(store, "scout07")
    client = _drop_cookies(app.test_client())
    tap = client.get(f"/login/scout/Seagull/{scout['id']}")
    assert tap.status_code == 302 and _path(tap.headers["Location"]) == "/welcome"
    page = _drop_cookies(app).get(tap.headers["Location"]).get_data(as_text=True)
    assert "設定你的密碼" in page

    assert _path(_drop_cookies(app).get("/home?" + urllib.parse.urlsplit(tap.headers["Location"]).query)
                 .headers["Location"]) == "/welcome"
    action = re.search(r'<form method="post" action="([^"]*/welcome[^"]*)"', page).group(1)
    missing = _drop_cookies(app).post(action, data={"password": "tiger777", "confirm": "tiger777"})
    assert _path(missing.headers["Location"]) == "/welcome" and "err=missing_email" in missing.headers["Location"]
    saved = _drop_cookies(app).post(action, data={"password": "tiger777", "confirm": "tiger777",
                                                  "email": "ng@example.com"})
    assert saved.status_code == 302
    assert "ok=password" in saved.headers["Location"]        # news rides in the URL
    home = _drop_cookies(app).get(saved.headers["Location"]).get_data(as_text=True)
    assert "密碼及電郵已設定" in home
    assert 'class="setup-card' not in home


def test_a_form_post_keeps_the_token_in_its_action(app):
    client = _drop_cookies(app.test_client())
    r = client.post("/login/demo/demo2")
    page = _drop_cookies(app).get(r.headers["Location"]).get_data(as_text=True)
    assert re.search(r'<form method="post" action="[^"]*sid=[^"]*"', page)


# ── demo tiles ──────────────────────────────────────────────────────────────

def test_demo_tile_signs_in_without_a_password(client):
    response = client.post("/login/demo/demo2")
    assert response.status_code == 302
    assert _path(response.headers["Location"]) == "/home"


def test_demo_leader_tile_goes_to_the_console(app):
    client = app.test_client()
    response = client.post("/login/demo/demo1")
    assert response.status_code == 302
    assert _path(response.headers["Location"]).startswith("/leader")


def test_demo_login_can_be_switched_off(app, store):
    store.config["demo_login"] = False
    client = app.test_client()
    assert client.post("/login/demo/demo2").status_code == 403
    assert "demo2" not in client.get("/login").get_data(as_text=True)


def test_first_time_demo_tile_always_shows_the_ask(app, store):
    """demo3 = the whole first-time experience, in one tap, every time."""
    from scout.auth import reset_password
    scout = _find(store, "scout07")
    for _ in range(2):                      # run it twice: it must still ask
        client = app.test_client()
        r = client.post("/login/demo/demo3")
        assert r.status_code == 302
        assert _path(r.headers["Location"]) == "/welcome"
        page = client.get("/welcome").get_data(as_text=True)
        assert "設定你的密碼" in page and 'name="confirm"' in page and 'name="email"' in page
        assert _path(client.get("/home").headers["Location"]) == "/welcome"
        assert not store.get("users", scout["id"])["password_hash"]
        # …and completing it turns the next run back into a first-time ask
        client.post("/welcome", data={"password": "tiger777", "confirm": "tiger777",
                                      "email": "ng@example.com"})
        assert store.get("users", scout["id"])["password_hash"]


def test_the_demo_tiles_are_reachable_by_url_but_not_advertised(client):
    """They were taken off the front page on purpose — the routes still work."""
    assert "demo3" not in client.get("/login").get_data(as_text=True)
    r = client.post("/login/demo/demo3")
    assert r.status_code == 302


# ── leader sign-in ──────────────────────────────────────────────────────────

def test_leader_signs_in_and_reaches_the_console(app):
    client = app.test_client()
    response = client.post("/login/leader", data={"username": "leader1", "password": "0082"})
    assert response.status_code == 302
    assert _path(response.headers["Location"]).startswith("/leader")


def test_leader_wrong_password(app):
    client = app.test_client()
    assert client.post("/login/leader", data={"username": "leader1", "password": "x"}).status_code == 401
    assert client.post("/login/leader", data={"username": "ghost", "password": "x"}).status_code == 401


# ── roles are separate ──────────────────────────────────────────────────────

def test_scout_cannot_open_leader_pages(scout_client):
    for path in ("/leader", "/leader/accounts", "/leader/review", "/leader/settings",
                 "/leader/content", "/leader/audit", "/leader/rewards", "/leader/announcements"):
        response = scout_client.get(path)
        assert response.status_code in (302, 403), f"{path} → {response.status_code}"


def test_leader_cannot_open_scout_pages(leader_client):
    for path in ("/home", "/badges", "/rewards", "/history", "/leaderboard"):
        assert leader_client.get(path).status_code in (302, 403)


def test_anonymous_visitors_are_redirected_to_login(client):
    assert client.get("/home").status_code == 302
    assert client.get("/leader").status_code == 302


# ── forgotten password ──────────────────────────────────────────────────────

def test_forgot_password_files_a_leader_request(client, store):
    scout = _find(store, "scout03")
    client.post(f"/login/scout/Otter/{scout['id']}", data={"password": "scout1234"})   # signed in, then out
    client.post("/logout")
    response = client.post("/forgot", data={"patrol": "Otter", "user_id": scout["id"]})
    assert response.status_code == 200
    pending = [r for r in store.list("password_reset_requests")
               if r["user_id"] == scout["id"] and r["status"] == "pending"]
    assert pending, "a reset request should have been filed"


def test_self_reset_clears_the_password_immediately(app, store):
    store.save_setting("scout_self_reset", True)
    scout = _find(store, "scout03")
    client = app.test_client()
    client.post("/forgot", data={"patrol": "Otter", "user_id": scout["id"]})
    assert store.get("users", scout["id"])["password_hash"] == ""
    # …so the next visit is the no-password entry again, and the card comes back
    tap = client.get(f"/login/scout/Otter/{scout['id']}")
    assert tap.status_code == 302 and _path(tap.headers["Location"]) == "/welcome"
    assert 'name="confirm"' in client.get("/welcome").get_data(as_text=True)


def test_forgot_without_choosing_fails(client):
    assert client.post("/forgot", data={"patrol": "Tiger", "user_id": ""}).status_code == 404


def test_leaders_reset_from_the_accounts_panel(leader_client, store):
    scout = _find(store, "scout05")
    response = leader_client.post(f"/leader/accounts/{scout['id']}/reset")
    assert response.status_code in (200, 302)
    saved = store.get("users", scout["id"])
    assert saved["password_hash"] == "" and saved["must_change_password"] is True


def test_leader_can_dismiss_a_reset_request(client, leader_client, store):
    scout = _find(store, "scout04")
    client.post("/forgot", data={"patrol": "Otter", "user_id": scout["id"]})
    request_row = next(r for r in store.list("password_reset_requests") if r["user_id"] == scout["id"])
    leader_client.post(f"/leader/reset-requests/{request_row['id']}/dismiss")
    assert store.get("password_reset_requests", request_row["id"])["status"] == "dismissed"


def test_the_forgot_link_lives_on_the_password_page_only(client, store):
    """A scout asks for help at the password step, not on the name list.

    (Reported: no forget-password on the name-choose page; they only need it
    where they type their password.)
    """
    names = client.get("/login/scout/Tiger").get_data(as_text=True)
    assert "忘記密碼" not in names and "/forgot" not in names
    assert "Tiger" in names and "Otter" in names          # the patrol switches stay

    scout = _find(store, "scout01")
    page = client.get(f"/login/scout/Tiger/{scout['id']}").get_data(as_text=True)
    assert "忘記密碼" in page
    assert f"/forgot/scout/Tiger/{scout['id']}" in page    # …and it is this scout's own reset


def test_a_scout_changes_their_own_password_with_their_email(app, store):
    """The reset is self-service: the email on the account is the key."""
    scout = _find(store, "scout01")
    assert scout["email"].endswith("@82hkg.example"), "the sample scout has an email on file"
    client = app.test_client()
    url = f"/forgot/scout/Tiger/{scout['id']}"
    page = client.get(url).get_data(as_text=True)
    assert 'name="email"' in page and 'name="password"' in page and 'name="confirm"' in page

    # a different email changes nothing
    wrong = client.post(url, data={"email": "somebody-else@example.hk",
                                   "password": "newpass99", "confirm": "newpass99"})
    assert wrong.status_code == 400 and "電郵" in wrong.get_data(as_text=True)
    assert client.post(f"/login/scout/Tiger/{scout['id']}",
                       data={"password": "scout1234"}).status_code == 302      # old one still works

    # their own email (any case) does
    good = client.post(url, data={"email": scout["email"].upper(),
                                  "password": "newpass99", "confirm": "newpass99"})
    assert good.status_code == 302
    assert _path(good.headers["Location"]).endswith(f"/login/scout/Tiger/{scout['id']}")
    assert "reset=1" in good.headers["Location"]

    fresh = app.test_client()
    assert fresh.post(f"/login/scout/Tiger/{scout['id']}", data={"password": "scout1234"}).status_code == 401
    assert fresh.post(f"/login/scout/Tiger/{scout['id']}", data={"password": "newpass99"}).status_code == 302
    note = fresh.get(f"/login/scout/Tiger/{scout['id']}?reset=1").get_data(as_text=True)
    assert "密碼已更新" in note


def test_the_reset_form_checks_the_new_password(app, store):
    scout = _find(store, "scout04")                     # 何嘉欣 · Otter · has an email
    client = app.test_client()
    url = f"/forgot/scout/Otter/{scout['id']}"
    short = client.post(url, data={"email": scout["email"], "password": "abc", "confirm": "abc"})
    assert short.status_code == 400 and "6 個字" in short.get_data(as_text=True)
    mismatch = client.post(url, data={"email": scout["email"], "password": "newpass99", "confirm": "newpass98"})
    assert mismatch.status_code == 400 and "不同" in mismatch.get_data(as_text=True)
    assert client.post(f"/login/scout/Otter/{scout['id']}",
                       data={"password": "scout1234"}).status_code == 302      # untouched


def test_an_account_without_an_email_asks_a_leader_instead(app, store):
    """A leader-made account that never finished setup has no email to check."""
    row = store.insert("users", {
        "role": "scout", "username": "tiger-fresh", "password_hash": "", "password_salt": "",
        "display_name_zh": "陳小美", "display_name_en": "Chan Siu Mei", "email": "",
        "scout_no": "T9001", "section": "scout", "patrol": "Tiger", "unit": "港島第八十二旅童軍團",
        "avatar": "🦊", "status": "active", "must_change_password": True,
        "show_on_leaderboard": True, "created_at": "2026-01-01T00:00:00", "created_by": "test",
    })
    client = app.test_client()
    url = f"/forgot/scout/Tiger/{row['id']}"
    page = client.get(url).get_data(as_text=True)
    assert "還未有電郵" in page
    assert 'name="user_id"' in page and "通知領袖" in page        # the leader-request form
    blocked = client.post(url, data={"email": "made-up@example.hk",
                                     "password": "newpass99", "confirm": "newpass99"})
    assert blocked.status_code == 409
    assert store.get("users", row["id"])["password_hash"] == ""

    # the button on that page still files the request the leader console shows
    client.post("/forgot", data={"patrol": "Tiger", "user_id": row["id"]})
    assert [r for r in store.list("password_reset_requests") if r["user_id"] == row["id"]]


# ── the emailed reset link ──────────────────────────────────────────────────

class Mailbox:
    """Stands in for the SMTP server: keeps whatever would have been sent."""

    def __init__(self):
        self.sent = []

    def __call__(self, cfg, message):
        self.sent.append({"to": message["To"], "subject": message["Subject"],
                          "body": message.get_content()})
        return True, ""

    @property
    def links(self):
        import re
        return re.findall(r"https?://\S*/reset/[A-Za-z0-9_\-]+", " ".join(m["body"] for m in self.sent))


@pytest.fixture()
def mailbox(app, store, monkeypatch):
    """A unit with a working Gmail, replaced by a recorder."""
    import scout.mailer as mailer
    store.save_setting("smtp_host", "smtp.gmail.com")
    store.save_setting("smtp_port", 587)
    store.save_setting("smtp_tls", "tls")
    store.save_setting("smtp_user", "82hkg@example.com")
    store.save_setting("smtp_password", "app-password")
    store.save_setting("smtp_from", "82hkg@example.com")
    store.save_setting("reset_link_minutes", 60)
    recorder = Mailbox()
    monkeypatch.setattr(mailer, "deliver", recorder)
    return recorder


def test_the_reset_page_offers_to_email_a_link(app, store, mailbox):
    """The scout taps once; we mail the address already on the account."""
    scout = _find(store, "scout01")
    client = app.test_client()
    page = client.get(f"/forgot/scout/Tiger/{scout['id']}").get_data(as_text=True)
    assert f"/forgot/scout/Tiger/{scout['id']}/send" in page      # the email button
    assert mailer_mask(scout["email"]) in page                    # the hint, not the address
    assert scout["email"] not in page, "the full address is never printed on the page"
    assert 'name="email"' not in page.split("mini-details")[0], "nothing to type in the main flow"

    posted = client.post(f"/forgot/scout/Tiger/{scout['id']}/send")
    assert posted.status_code == 302
    assert _path(posted.headers["Location"]).endswith(f"/forgot/scout/Tiger/{scout['id']}/sent")

    assert len(mailbox.sent) == 1
    letter = mailbox.sent[0]
    assert letter["to"] == scout["email"]
    assert "重設" in letter["subject"] and "Reset" in letter["subject"]
    assert "王小明" in letter["body"] and "Wong Siu Ming" in letter["body"]
    assert "60" in letter["body"]
    link = mailbox.links[0]
    assert "/reset/" in link

    rows = [r for r in store.list("password_resets") if r["user_id"] == scout["id"]]
    assert len(rows) == 1 and not rows[0]["used_at"]
    token = link.rsplit("/", 1)[-1]
    assert token not in str(rows[0]), "only the hash of the token is stored"


def test_the_emailed_link_sets_a_new_password_once(app, store, mailbox):
    scout = _find(store, "scout02")
    client = app.test_client()
    client.post(f"/forgot/scout/Tiger/{scout['id']}/send")
    link = mailbox.links[0]
    path = urllib.parse.urlparse(link).path

    page = client.get(path).get_data(as_text=True)
    assert "設定新密碼" in page and "王小明" not in page and "李美儀" in page
    assert "Tiger" in page

    short = client.post(path, data={"password": "abc", "confirm": "abc"})
    assert short.status_code == 400
    mismatch = client.post(path, data={"password": "tiger777", "confirm": "tiger778"})
    assert mismatch.status_code == 400
    assert app.test_client().post(f"/login/scout/Tiger/{scout['id']}",
                                  data={"password": "scout1234"}).status_code == 302

    saved = client.post(path, data={"password": "tiger777", "confirm": "tiger777"})
    assert saved.status_code == 302
    assert _path(saved.headers["Location"]).endswith(f"/login/scout/Tiger/{scout['id']}")

    fresh = app.test_client()
    assert fresh.post(f"/login/scout/Tiger/{scout['id']}",
                      data={"password": "scout1234"}).status_code == 401
    assert fresh.post(f"/login/scout/Tiger/{scout['id']}",
                      data={"password": "tiger777"}).status_code == 302
    assert "密碼已更新" in fresh.get(f"/login/scout/Tiger/{scout['id']}?reset=1").get_data(as_text=True)

    # one use only
    again = client.get(path)
    assert again.status_code == 410 and "已經用過" in again.get_data(as_text=True)
    assert client.post(path, data={"password": "newpass99", "confirm": "newpass99"}).status_code == 410


def test_an_expired_or_unknown_link_is_refused(app, store, mailbox):
    from datetime import datetime, timedelta, timezone
    scout = _find(store, "scout03")
    client = app.test_client()
    client.post(f"/forgot/scout/Otter/{scout['id']}/send")
    path = urllib.parse.urlparse(mailbox.links[0]).path
    row = next(r for r in store.list("password_resets") if r["user_id"] == scout["id"])
    past = datetime.now(tz=timezone.utc) - timedelta(minutes=5)
    store.update("password_resets", row["id"], {"expires_at": past.isoformat()})

    expired = client.get(path)
    assert expired.status_code == 410 and "過期" in expired.get_data(as_text=True)
    assert client.post(path, data={"password": "tiger777", "confirm": "tiger777"}).status_code == 410
    assert app.test_client().post(f"/login/scout/Otter/{scout['id']}",
                                  data={"password": "scout1234"}).status_code == 302

    missing = client.get("/reset/not-a-real-token")
    assert missing.status_code == 404 and "找不到" in missing.get_data(as_text=True)


def test_one_link_a_minute_and_no_more_than_five_an_hour(app, store, mailbox):
    scout = _find(store, "scout05")
    client = app.test_client()
    url = f"/forgot/scout/Seagull/{scout['id']}/send"
    assert client.post(url).status_code == 302
    again = client.post(url)
    assert again.status_code == 302 and "again=1" in again.headers["Location"]
    assert len([m for m in mailbox.sent]) == 1, "the second tap does not send another letter"

    # five in an hour is the ceiling — each send is backdated two minutes
    from datetime import datetime, timedelta, timezone
    for _ in range(5):
        two_minutes_ago = (datetime.now(tz=timezone.utc) - timedelta(minutes=2)).isoformat()
        client.post(url)
        fresh_row = max(store.list("password_resets"), key=lambda r: r["created_at"])
        store.update("password_resets", fresh_row["id"], {"created_at": two_minutes_ago})
    refused = client.post(url)
    assert refused.status_code == 429 and "多次" in refused.get_data(as_text=True)
    assert len(store.list("password_resets")) == 5      # …and the ceiling held


def test_without_a_mailbox_the_on_the_spot_method_still_works(app, store):
    """No mail configured (the sandbox, the offline demo): nothing breaks."""
    scout = _find(store, "scout01")
    client = app.test_client()
    page = client.get(f"/forgot/scout/Tiger/{scout['id']}").get_data(as_text=True)
    assert "還未設定寄信的信箱" in page
    assert 'name="email"' in page and 'name="password"' in page
    blocked = client.post(f"/forgot/scout/Tiger/{scout['id']}/send")
    assert blocked.status_code == 409
    saved = client.post(f"/forgot/scout/Tiger/{scout['id']}",
                        data={"email": scout["email"], "password": "tiger777", "confirm": "tiger777"})
    assert saved.status_code == 302
    assert app.test_client().post(f"/login/scout/Tiger/{scout['id']}",
                                  data={"password": "tiger777"}).status_code == 302


def test_a_failed_send_says_so_and_offers_the_way_round(app, store, monkeypatch):
    import scout.mailer as mailer_mod
    scout = _find(store, "scout06")
    store.save_setting("smtp_host", "smtp.gmail.com")
    store.save_setting("smtp_from", "82hkg@example.com")
    store.save_setting("smtp_user", "82hkg@example.com")
    monkeypatch.setattr(mailer_mod, "deliver",
                        lambda cfg, message: (False, "SMTPAuthenticationError: bad credentials"))
    client = app.test_client()
    page = client.post(f"/forgot/scout/Seagull/{scout['id']}/send")
    assert page.status_code == 502
    body = page.get_data(as_text=True)
    assert "未能寄出" in body and "SMTPAuthenticationError" in body
    assert 'name="email"' in body                       # the fallback is right there
    from scout.auth import live_reset_tokens
    assert live_reset_tokens(store, scout["id"]) == [], "a letter that failed leaves no live link" 


def test_the_mask_hides_the_address_but_keeps_it_recognisable():
    from scout.mailer import mask_email
    assert mask_email("scout01@82hkg.example") == "sc***@82hkg.example"
    assert mask_email("ab@example.com") == "a***@example.com"
    assert mask_email("") == "***"


# ── sessions ────────────────────────────────────────────────────────────────

def test_logout_ends_the_session(client, store):
    client.post("/login/demo/demo2")
    assert client.get("/home").status_code == 200
    client.post("/logout")
    assert client.get("/home").status_code == 302


def test_session_token_is_not_the_user_id(client, store):
    response = client.post("/login/demo/demo2")
    token = response.headers.get("Set-Cookie", "")
    scout = _find(store, "scout03")
    assert scout["id"] not in token
    assert "scout_sid=" in token


def test_password_hash_never_reaches_a_page(client, store):
    page = client.post("/login/demo/demo2", follow_redirects=True).get_data(as_text=True)
    for user in store.list("users"):
        if user.get("password_hash"):
            assert user["password_hash"] not in page

# ── 第一次開啟：建立第一位領袖（正式上線的入口） ───────────────────────────

def test_a_fresh_database_asks_for_the_first_leader(client, store):
    """還沒有任何領袖時，任何人都被帶到建立第一位領袖那一頁。

    這是正式上線的唯一無需登入入口：示範帳戶不會自動出現，帳戶由領袖建立。
    """
    assert store.needs_setup() is False, "the seeded fixture already has leader1"

    store.remove_where("users", lambda row: row.get("role") == "leader")
    assert store.needs_setup() is True

    page = client.get("/", follow_redirects=True)
    body = page.get_data(as_text=True)
    assert page.status_code == 200
    assert "建立第一位領袖" in body
    assert "建立領袖帳戶" in body

    door = client.get("/login/leader", follow_redirects=False)
    assert door.status_code == 302 and door.headers["Location"].endswith("/setup")


def test_the_first_leader_form_makes_an_account_and_signs_it_in(client, store):
    store.remove_where("users", lambda row: row.get("role") == "leader")

    bad = client.post("/setup", data={"name_zh": "陳大文", "username": "Chan!",
                                      "password": "abcdef", "password2": "abcdef"})
    assert bad.status_code == 400 and "登入帳號" in bad.get_data(as_text=True)

    short = client.post("/setup", data={"name_zh": "陳大文", "username": "leader9",
                                        "password": "abc", "password2": "abc"})
    assert short.status_code == 400 and "至少 6" in short.get_data(as_text=True)

    mismatch = client.post("/setup", data={"name_zh": "陳大文", "username": "leader9",
                                           "password": "abcdef", "password2": "abcdeX"})
    assert mismatch.status_code == 400 and "不相同" in mismatch.get_data(as_text=True)

    made = client.post("/setup", data={
        "unit_zh": "港島第八十二旅童軍團", "unit_en": "82nd Hong Kong Scout Group",
        "name_zh": "陳大文", "name_en": "Chan Tai Man",
        "username": "Leader9", "password": "harbour-82", "password2": "harbour-82",
    }, follow_redirects=False)
    assert made.status_code == 302 and "/leader" in made.headers["Location"]

    leader = _find(store, "leader9")            # the name is stored lower-case
    assert leader["display_name_zh"] == "陳大文" and leader["role"] == "leader"
    assert "password_hash" not in leader.get("public", {})
    assert store.settings()["unit_name_zh"] == "港島第八十二旅童軍團"
    assert store.settings()["unit_name_en"] == "82nd Hong Kong Scout Group"

    console = client.get("/leader")
    assert console.status_code == 200 and "陳大文" in console.get_data(as_text=True)

    # 建立之後這一頁自動收起，改為轉去登入頁
    again = client.get("/setup", follow_redirects=False)
    assert again.status_code == 302 and again.headers["Location"].startswith("/leader")


def test_the_leader_code_signs_in_after_setup(client, store):
    """領袖代碼就是第一位領袖設定的密碼（預設提示 0082 是示範帳戶的）。"""
    store.remove_where("users", lambda row: row.get("role") == "leader")
    client.post("/setup", data={"unit_zh": "港島第八十二旅童軍團", "name_zh": "陳大文",
                                "username": "leader1", "password": "harbour-82",
                                "password2": "harbour-82"})
    client.post("/logout")
    door = client.post("/login/leader", data={"password": "harbour-82"}, follow_redirects=False)
    assert door.status_code == 302 and "/leader" in door.headers["Location"]
    wrong = client.post("/logout") and client.post("/login/leader", data={"password": "0082"})
    assert wrong.status_code == 401


def test_official_defaults_leave_the_demo_accounts_out(client):
    """正式上線：登入頁沒有示範帳戶、沒有示範提示（示範要明確開啟）。"""
    page = client.get("/login").get_data(as_text=True)
    assert "demo-accounts" not in page and "示範帳戶" not in page
