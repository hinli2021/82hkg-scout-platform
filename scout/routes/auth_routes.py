"""
Signing in — one screen per decision, so a scout never faces a wall of fields:

    /login                 choose 小隊 (patrol) · or a demo tile · or leader sign-in
    /login/scout/<patrol>  tap your name
    /login/scout/<patrol>/<id>   password  (first time: choose a password + email)
    /login/leader          leader username + password
    /forgot/scout/<patrol>/<id>  «忘記密碼» → we email a one-time link to the address on file
    /reset/<token>         the page that link opens: choose a new password
    /forgot                the way in for an account with no email — a leader resets it
"""
from __future__ import annotations

from flask import Blueprint, g, jsonify, redirect, render_template, request, url_for

from ..auth import (
    check_password, consume_reset, create_reset_token, demo_username, end_session,
    home_for, live_reset_tokens, needs_first_time, public_user, reset_password,
    reset_token_state, scouts_in_patrol, set_password, sign_in, valid_email,
)
from .. import mailer
from ..mascots import mascot_for
from ..schema import DEMO_LOGIN_MAP, DEMO_PASSWORDS, patrol_label
from ..util import now_iso
from .helpers import audit, fail, ok, store, wants_json

auth_routes = Blueprint("auth_routes", __name__)


def _with_sid(url: str, token: str) -> str:
    """Put the session token in a redirect target as well as the cookie.

    Needed because the preview iframe is a third-party frame: the browser may
    refuse the cookie, and then `?sid=…` is the only thing keeping the scout
    signed in. app.py then carries it on every link.
    """
    if not url.startswith("/") or not token or "sid=" in url:
        return url
    return url + ("&" if "?" in url else "?") + "sid=" + token


def _set_session_cookie(response, token: str):
    response.set_cookie(
        "scout_sid", token, max_age=30 * 86400, httponly=True, samesite="Lax",
        secure=request.is_secure,
    )
    location = response.headers.get("Location", "")
    if location.startswith("/"):
        response.headers["Location"] = _with_sid(location, token)
    # The fetch-based (JS) sign-in follows `redirect` from the JSON body.
    if response.mimetype == "application/json":
        try:
            import json as _json

            data = response.get_json()
            if isinstance(data, dict) and isinstance(data.get("redirect"), str):
                data["redirect"] = _with_sid(data["redirect"], token)
                response.set_data(_json.dumps(data))
        except Exception:      # noqa: BLE001 — never break a sign-in over this
            pass
    return response


def _patrols(settings: dict) -> list[dict]:
    return [{"value": p, "label": patrol_label(p)} for p in (settings.get("patrols") or ["Tiger", "Otter", "Seagull"])]


def _in_scene_order(patrols: list[dict]) -> list[dict]:
    """The sign-in scene is a picture: otter, tiger, seagull, left to right.

    The narrow (three-column) version of that page is built from this list —
    column one gets the first patrol — so the buttons must be listed in the
    same order the animals stand in the artwork, or a card labelled TIGER ends
    up sitting on the otter. On a wide window the positions come from
    `--x` (absolute), so this changes nothing there but the tab order.
    """
    def where(patrol: dict) -> float:
        spot = mascot_for(patrol["value"]).get("spot_x")
        return spot if spot is not None else 999.0

    return sorted(patrols, key=where)


# ── the front door ──────────────────────────────────────────────────────────

USERNAME_RE = __import__("re").compile(r"^[a-z0-9][a-z0-9_.\-]{2,31}$")


@auth_routes.get("/")
def root():
    user = g.get("user")
    return redirect(home_for(user))


@auth_routes.get("/setup")
def setup():
    """第一次開啟：還沒有任何領袖帳戶時，先建立第一位領袖。

    正式上線的資料庫是空的（示範帳戶不會自動產生），所以這是唯一不用登入
    就可以建立帳戶的入口；一旦有領袖，這一頁就自動收起，改為轉去登入頁。
    """
    st = store()
    if not st.needs_setup():
        return redirect(home_for(g.get("user")) if g.get("user") else url_for("auth_routes.login"))
    defaults = st.settings_cached()
    return render_template("auth/setup.html", form={
        "unit_zh": defaults.get("unit_name_zh") or "港島第八十二旅童軍團",
        "unit_en": defaults.get("unit_name_en") or "Sample Scout Group",
        "name_zh": "", "name_en": "", "username": "leader1",
    })


@auth_routes.post("/setup")
def setup_create():
    st = store()
    if not st.needs_setup():
        return redirect(url_for("auth_routes.login"))
    form = request.form
    values = {key: (form.get(key) or "").strip() for key in
              ("unit_zh", "unit_en", "name_zh", "name_en", "username")}
    password = form.get("password") or ""
    password2 = form.get("password2") or ""

    def back(zh, en):
        return render_template("auth/setup.html", form={**values, "password": ""},
                               error_zh=zh, error_en=en), 400

    if not values["name_zh"]:
        return back("請填領袖姓名。", "Please enter the leader's name.")
    username = values["username"].lower()
    if not USERNAME_RE.match(username):
        return back("登入帳號請用小寫英文字母、數字、底線或橫線，3–32 個字。",
                    "The sign-in name uses lower-case letters, digits, _ or -, 3–32 characters.")
    if len(password) < 6:
        return back("密碼至少 6 個字。", "The password needs at least 6 characters.")
    if password != password2:
        return back("兩次輸入的密碼不相同。", "The two passwords do not match.")

    leader = st.create_first_leader(
        username=username, password=password,
        display_name_zh=values["name_zh"], display_name_en=values["name_en"],
        unit=values["unit_zh"])
    if values["unit_en"]:
        st.save_setting("unit_name_en", values["unit_en"])
    token, _ = sign_in(st, leader, request)
    audit(leader, "first_leader_created", "users", leader["id"], {"username": username})
    return _set_session_cookie(redirect(url_for("leader_routes.overview")), token)


@auth_routes.get("/login")
def login():
    st = store()
    if st.needs_setup():
        return redirect(url_for("auth_routes.setup"))
    settings = st.settings_cached()
    if g.get("user"):
        return redirect(home_for(g.user))
    return render_template(
        "auth/login.html",
        patrols=_in_scene_order(_patrols(settings)),
        demo_tiles=[
            {"handle": handle, "label_zh": info["label_zh"], "label_en": info["label_en"],
             "icon": {"demo1": "🧭", "demo2": "🦊"}.get(handle, "🆕")}
            for handle, info in DEMO_LOGIN_MAP.items()
        ] if st.config.get("demo_login", True) else [],
        demo_passwords=DEMO_PASSWORDS,
        next_url=request.args.get("next", ""),
    )


@auth_routes.get("/login/leader")
def leader_login_page():
    """The leaders' door.

    If a leader is *already* signed in (their session is still alive), say so
    on the card instead of quietly forwarding them in — otherwise it looks as
    though the code was never asked for. The card then offers the console and
    a sign-out button, which is also the way to test the code again.
    """
    if store().needs_setup():
        return redirect(url_for("auth_routes.setup"))
    if g.get("user") and g.user.get("role") == "leader":
        return render_template("auth/leader_login.html", already=public_user(g.user), username="")
    if g.get("user"):
        return render_template("auth/leader_login.html", already=None, other=public_user(g.user), username="")
    return render_template("auth/leader_login.html", already=None, username="")


@auth_routes.post("/login/leader")
def leader_login():
    st = store()
    form = request.form if not request.is_json else (request.get_json(silent=True) or {})
    username = (form.get("username") or "").strip().lower()
    password = form.get("password") or ""
    leaders = [u for u in st.list("users") if u.get("role") == "leader"]
    if username:                       # if a name is given, it must match
        leaders = [u for u in leaders if str(u.get("username", "")).lower() == username]
    # the door only really needs the code: whoever's code it is, that is who
    # walks in — so 領袖登入 works by typing 0082 alone
    user = next((u for u in leaders if password and check_password(u, password)), None)
    if not user:
        if wants_json():
            return fail(401, "bad_credentials", "帳號或密碼不正確", "Wrong username or password")
        return render_template("auth/leader_login.html",
                              error_zh="帳號或密碼不正確", error_en="Wrong username or password",
                              username=username), 401
    if user.get("status") != "active":
        if wants_json():
            return fail(403, "locked", "此帳號已被停用", "This account is locked")
        return render_template("auth/leader_login.html",
                              error_zh="此帳號已被停用", error_en="This account is locked"), 403
    token, _ = sign_in(st, user, request)
    if wants_json():
        return _set_session_cookie(jsonify({"ok": True, "redirect": home_for(user)}), token)
    return _set_session_cookie(redirect(home_for(user)), token)


# ── demo tiles ──────────────────────────────────────────────────────────────

@auth_routes.post("/login/demo/<handle>")
def demo_login(handle: str):
    """The 4-second path used at a meeting: demo1 = leader, demo2 = scout."""
    st = store()
    if not st.config.get("demo_login", True):
        return fail(403, "demo_off", "示範登入未開放", "Demo sign-in is off")
    username = demo_username(handle)
    user = next((u for u in st.list("users") if u.get("username") == username), None) if username else None
    if not user:
        return fail(404, "no_demo_user", "找不到示範帳戶", "Demo account not found")
    first_time = bool(DEMO_LOGIN_MAP.get(handle, {}).get("first_time"))
    if first_time:
        # The first-time demo must always show the first-time experience — so a
        # previous run (which set a password) is cleared before we walk in.
        if user.get("password_hash"):
            reset_password(st, user)
        target = url_for("scout_routes.welcome")
    else:
        # Demo shortcuts are not exempt from first-time setup. Existing demo2
        # scouts go home; a reset account goes to the required welcome form.
        target = home_for(user)
    token, _ = sign_in(st, user, request)
    if wants_json():
        return _set_session_cookie(jsonify({"ok": True, "redirect": target, "role": user.get("role")}), token)
    return _set_session_cookie(redirect(target), token)


# ── scout sign-in: patrol → name → password ─────────────────────────────────

@auth_routes.get("/login/scout/<patrol>")
def scout_names(patrol: str):
    st = store()
    label = patrol_label(patrol)
    scouts = scouts_in_patrol(st, patrol)
    return render_template("auth/scout_names.html", patrol=patrol, patrol_label=label, scouts=scouts,
                           all_patrols=_patrols(st.settings_cached()))


@auth_routes.get("/login/scout/<patrol>/<user_id>")
def scout_password(patrol: str, user_id: str):
    """Name tapped.

    • no password yet → enter without one, then MUST set password + email.
    • temporary/returning password → verify it first; temporary passwords
      still lead to required setup rather than the scout pages.
    """
    st = store()
    user = st.get("users", user_id)
    if not user or user.get("role") != "scout":
        return redirect(url_for("auth_routes.scout_names", patrol=patrol))
    if user.get("status") != "active":
        return render_template("auth/scout_password.html", patrol=patrol, patrol_label=patrol_label(patrol),
                               scout=public_user(user), locked=True,
                               self_reset=bool(st.settings_cached().get("scout_self_reset")))

    if not user.get("password_hash"):
        token, _ = sign_in(st, user, request)
        audit(user, "first_time_entry", "users", user["id"])
        response = redirect(url_for("scout_routes.welcome"))
        return _set_session_cookie(response, token)

    return render_template("auth/scout_password.html", patrol=patrol, patrol_label=patrol_label(patrol),
                           scout=public_user(user), locked=False,
                           self_reset=bool(st.settings_cached().get("scout_self_reset")))


@auth_routes.post("/login/scout/<patrol>/<user_id>")
def scout_sign_in(patrol: str, user_id: str):
    st = store()
    form = request.form if not request.is_json else (request.get_json(silent=True) or {})
    user = st.get("users", user_id)
    if not user or user.get("role") != "scout":
        return fail(404, "not_found", "找不到此童軍", "Scout not found")
    if user.get("status") != "active":
        return fail(403, "locked", "此帳號已被停用，請聯絡領袖", "This account is locked — ask a leader")

    if not user.get("password_hash"):
        # First tap needs no password. The scout is signed in only to complete
        # the mandatory setup; protected scout pages still redirect to it.
        token, _ = sign_in(st, user, request)
        if wants_json():
            return _set_session_cookie(jsonify({"ok": True, "redirect": url_for("scout_routes.welcome")}), token)
        return _set_session_cookie(redirect(url_for("scout_routes.welcome")), token)

    if not check_password(user, form.get("password") or ""):
        if wants_json():
            return fail(401, "bad_password", "密碼不正確", "Incorrect password")
        return render_template("auth/scout_password.html", patrol=patrol, patrol_label=patrol_label(patrol),
                               scout=public_user(user), locked=False,
                               self_reset=bool(st.settings_cached().get("scout_self_reset")),
                               error_zh="密碼不正確，請再試一次", error_en="Incorrect password"), 401

    token, _ = sign_in(st, user, request)
    target = home_for(user)
    if wants_json():
        return _set_session_cookie(jsonify({"ok": True, "redirect": target}), token)
    return _set_session_cookie(redirect(target), token)


# ── forgotten password ──────────────────────────────────────────────────────

@auth_routes.get("/forgot")
def forgot():
    st = store()
    return render_template("auth/forgot.html",
                           patrols=_patrols(st.settings_cached()),
                           self_reset=bool(st.settings_cached().get("scout_self_reset")))


@auth_routes.post("/forgot")
def forgot_request():
    """Either clears the password (self-reset on) or leaves a note for a leader."""
    st = store()
    form = request.form if not request.is_json else (request.get_json(silent=True) or {})
    patrol = (form.get("patrol") or "").strip()
    user_id = (form.get("user_id") or "").strip()
    user = st.get("users", user_id) if user_id else None
    if not user or user.get("role") != "scout" or str(user.get("patrol") or "") != patrol:
        if wants_json():
            return fail(404, "not_found", "找不到此童軍", "Scout not found")
        return render_template("auth/forgot.html", patrols=_patrols(st.settings_cached()),
                               self_reset=bool(st.settings_cached().get("scout_self_reset")),
                               patrol=patrol, scouts=scouts_in_patrol(st, patrol),
                               error_zh="請先選擇小隊和姓名", error_en="Pick your patrol and name first"), 404

    if st.settings_cached().get("scout_self_reset"):
        reset_password(st, user)
        audit(user, "self_reset_password", "users", user["id"])
        message_zh = "密碼已清除，下次登入時設定新密碼便可"
        message_en = "Password cleared — you will set a new one at your next sign-in"
    else:
        pending = next((r for r in st.list("password_reset_requests")
                        if r.get("user_id") == user["id"] and r.get("status") == "pending"), None)
        if not pending:
            st.insert("password_reset_requests", {
                "user_id": user["id"], "username": user.get("username", ""),
                "display_name_zh": user.get("display_name_zh", ""), "display_name_en": user.get("display_name_en", ""),
                "patrol": user.get("patrol", ""), "status": "pending",
                "requested_at": now_iso(), "handled_at": "", "handled_by": "",
            })
        audit(user, "reset_requested", "users", user["id"])
        message_zh = "已通知領袖，領袖重設後你便可用新密碼登入"
        message_en = "Your leader has been asked to reset it — you can sign in once they do"

    if wants_json():
        return ok(message_zh=message_zh, message_en=message_en)
    return render_template("auth/forgot_done.html", patrol=patrol, scout=public_user(user),
                           message_zh=message_zh, message_en=message_en)


@auth_routes.get("/forgot/scout/<patrol>")
def forgot_names(patrol: str):
    st = store()
    return render_template("auth/forgot.html", patrols=_patrols(st.settings_cached()),
                           self_reset=bool(st.settings_cached().get("scout_self_reset")),
                           patrol=patrol, scouts=scouts_in_patrol(st, patrol))


def _reset_context(st, patrol: str, user: dict, **extra) -> dict:
    cfg = mailer.config(st.settings_cached())
    on_file = (user.get("email") or "").strip()
    context = {
        "patrol": patrol, "patrol_label": patrol_label(patrol), "scout": public_user(user),
        "has_email": bool(valid_email(on_file)),
        "mail_ready": mailer.is_configured(cfg),
        "masked_email": mailer.mask_email(on_file),
        "minutes": int(cfg.get("reset_link_minutes") or 60),
        "error_zh": "", "error_en": "", "notice_zh": "", "notice_en": "",
    }
    context.update(extra)
    return context


def _reset_page(st, patrol: str, user: dict, error_zh: str = "", error_en: str = "",
                status: int = 200, **extra):
    """The reset page for one scout (email link first, on-the-spot method below)."""
    body = render_template("auth/forgot_reset.html",
                           **_reset_context(st, patrol, user, error_zh=error_zh, error_en=error_en, **extra))
    return (body, status) if status != 200 else body


def _scout_or_none(st, patrol: str, user_id: str) -> dict | None:
    user = st.get("users", user_id)
    if not user or user.get("role") != "scout" or str(user.get("patrol") or "") != patrol:
        return None
    return user


def _link_base() -> str:
    base = (store().settings_cached().get("public_base_url") or "").strip()
    return base.rstrip("/") if base else ""


@auth_routes.get("/forgot/scout/<patrol>/<user_id>")
def forgot_scout(patrol: str, user_id: str):
    """「忘記密碼」 from the password page — email a link, or fall back politely."""
    st = store()
    user = _scout_or_none(st, patrol, user_id)
    if not user:
        return redirect(url_for("auth_routes.login"))
    return _reset_page(st, patrol, user)


@auth_routes.post("/forgot/scout/<patrol>/<user_id>/send")
def forgot_send_link(patrol: str, user_id: str):
    """Mint a one-time link and email it to the address already on the account.

    Nothing is typed here: the scout never proves who they are by hand, so a
    stranger cannot reset someone else's password with a guessed address.
    """
    st = store()
    user = _scout_or_none(st, patrol, user_id)
    if not user:
        return fail(404, "not_found", "找不到此童軍", "Scout not found")
    if user.get("status") != "active":
        return fail(403, "locked", "此帳號已被停用，請聯絡領袖", "This account is locked — ask a leader")

    cfg = mailer.config(st.settings_cached())
    on_file = (user.get("email") or "").strip()
    if not mailer.is_configured(cfg):
        return _reset_page(st, patrol, user,
                           "領袖還未設定寄信的信箱，未能寄出電郵；請用下面的方法，或找領袖協助。",
                           "The unit mailbox is not set up yet, so no email can go out — "
                           "use the method below, or ask a leader.", 409)
    if not valid_email(on_file):
        return _reset_page(st, patrol, user,
                           "你的帳號還未有電郵，請找領袖協助重設密碼。",
                           "There is no email on your account yet — ask a leader to reset it.", 409)

    # one link a minute is plenty; five an hour is the ceiling
    recent = live_reset_tokens(st, user["id"])
    from ..util import parse_time as _pt
    if recent and _pt(now_iso()) - _pt(recent[0].get("created_at") or now_iso()) < 60:
        return redirect(url_for("auth_routes.forgot_sent", patrol=patrol, user_id=user_id, again=1))
    hour_ago = _pt(now_iso()) - 3600
    fresh = [r for r in st.list("password_resets")
             if r.get("user_id") == user["id"] and _pt(r.get("created_at") or now_iso()) > hour_ago]
    if len(fresh) >= 5:
        return _reset_page(st, patrol, user,
                           "今天已寄出多次，請過一會再試，或找領袖協助。",
                           "That is a lot of links in one hour — please try again later, or ask a leader.", 429)

    token, row = create_reset_token(st, user, minutes=cfg["reset_link_minutes"], requested_by="scout")
    base = _link_base()
    link = (base + url_for("auth_routes.reset_link", token=token)) if base else \
        url_for("auth_routes.reset_link", token=token, _external=True)
    ok_sent, error = mailer.send_reset_link(
        cfg, user, link, unit_zh=st.settings_cached().get("unit_name_zh") or "港島第八十二旅童軍團")
    audit(user, "reset_link_sent" if ok_sent else "reset_link_failed", "users", user["id"],
          {"to": mailer.mask_email(on_file), "error": error[:120]})
    if not ok_sent:
        from ..util import now_iso as _now
        st.update("password_resets", row["id"], {"used_at": _now()})
        return _reset_page(st, patrol, user,
                           f"電郵未能寄出（{error}）。請用下面的方法，或找領袖協助。",
                           f"The email could not be sent ({error}). Use the method below, "
                           "or ask a leader.", 502)
    return redirect(url_for("auth_routes.forgot_sent", patrol=patrol, user_id=user_id))


@auth_routes.get("/forgot/scout/<patrol>/<user_id>/sent")
def forgot_sent(patrol: str, user_id: str):
    """「請查看你的電郵」 — with the masked address and a resend button."""
    st = store()
    user = _scout_or_none(st, patrol, user_id)
    if not user:
        return redirect(url_for("auth_routes.login"))
    return render_template("auth/forgot_sent.html",
                           **_reset_context(st, patrol, user, again=request.args.get("again") == "1"))


@auth_routes.post("/forgot/scout/<patrol>/<user_id>")
def forgot_reset(patrol: str, user_id: str):
    """Without a mailbox: the scout's own email + a new password, on the spot.

    Kept as the fallback for a unit that has not set up mail (and for the offline
    demo). Never available while a working mailbox is configured *and* the scout
    reached this page from an emailed link.
    """
    st = store()
    user = _scout_or_none(st, patrol, user_id)
    if not user:
        return fail(404, "not_found", "找不到此童軍", "Scout not found")
    if user.get("status") != "active":
        return fail(403, "locked", "此帳號已被停用，請聯絡領袖", "This account is locked — ask a leader")

    form = request.form if not request.is_json else (request.get_json(silent=True) or {})
    on_file = (user.get("email") or "").strip()
    email = (form.get("email") or "").strip()
    password = form.get("password") or ""
    confirm = form.get("confirm") or ""

    if not valid_email(on_file):
        return _reset_page(st, patrol, user,
                           "你的帳號還未有電郵，請找領袖協助重設密碼。",
                           "There is no email on your account yet — ask a leader to reset it.", 409)
    if not email or email.lower() != on_file.lower():
        return _reset_page(st, patrol, user, "這個電郵與紀錄不同，請再試一次。",
                           "That email does not match our record — please try again.", 400)
    if len(password) < 6:
        return _reset_page(st, patrol, user, "密碼最少 6 個字。",
                           "Passwords need at least 6 characters.", 400)
    if password != confirm:
        return _reset_page(st, patrol, user, "兩次輸入的密碼不同。",
                           "The two passwords did not match.", 400)

    set_password(st, user, password, on_file)
    audit(user, "self_reset_password", "users", user["id"])
    message_zh = "密碼已更新，請用新密碼登入。"
    message_en = "Password updated — sign in with your new password."
    if wants_json():
        return ok(message_zh=message_zh, message_en=message_en)
    return redirect(url_for("auth_routes.scout_password", patrol=patrol, user_id=user_id, reset=1))


# ── the page an emailed link opens ──────────────────────────────────────────

@auth_routes.get("/reset/<token>")
def reset_link(token: str):
    st = store()
    state, row = reset_token_state(st, token)
    if state != "ok":
        return _reset_problem(state), (410 if state in {"used", "expired"} else 404)
    user = st.get("users", row.get("user_id"))
    if not user or user.get("status") != "active":
        return _reset_problem("unknown"), 404
    return render_template("auth/reset_password.html", token=token,
                           patrol=user.get("patrol") or "",
                           patrol_label=patrol_label(user.get("patrol") or ""),
                           scout=public_user(user))


@auth_routes.post("/reset/<token>")
def reset_link_save(token: str):
    st = store()
    state, row = reset_token_state(st, token)
    if state != "ok":
        return _reset_problem(state), (410 if state in {"used", "expired"} else 404)
    user = st.get("users", row.get("user_id"))
    if not user or user.get("status") != "active":
        return _reset_problem("unknown"), 404

    form = request.form if not request.is_json else (request.get_json(silent=True) or {})
    password = form.get("password") or ""
    confirm = form.get("confirm") or ""
    problem = ("", "")
    if len(password) < 6:
        problem = ("密碼最少 6 個字。", "Passwords need at least 6 characters.")
    elif password != confirm:
        problem = ("兩次輸入的密碼不同。", "The two passwords did not match.")
    if problem[0]:
        body = render_template("auth/reset_password.html", token=token,
                               patrol=user.get("patrol") or "",
                               patrol_label=patrol_label(user.get("patrol") or ""),
                               scout=public_user(user),
                               error_zh=problem[0], error_en=problem[1])
        return body, 400

    consume_reset(st, row, password)
    audit(user, "password_reset_by_link", "users", user["id"])
    if wants_json():
        return ok(message_zh="密碼已更新，請用新密碼登入。",
                  message_en="Password updated — sign in with your new password.")
    return redirect(url_for("auth_routes.scout_password",
                            patrol=user.get("patrol") or "", user_id=user["id"], reset=1))


def _reset_problem(state: str):
    words = {
        "used": ("這條連結已經用過了。", "This link has already been used."),
        "expired": ("這條連結已經過期。", "This link has expired."),
        "unknown": ("找不到這條連結。", "We cannot find this link."),
    }
    zh, en = words.get(state, words["unknown"])
    return render_template("auth/reset_invalid.html", state=state, reason_zh=zh, reason_en=en)


# ── signing out ─────────────────────────────────────────────────────────────

@auth_routes.post("/logout")
def logout():
    end_session(store(), request.cookies.get("scout_sid", "") or g.get("sid", ""))
    g.sid = ""                      # …and stop carrying the token on links
    if wants_json():
        response = jsonify({"ok": True, "redirect": url_for("auth_routes.login")})
    else:
        response = redirect(url_for("auth_routes.login"))
    response.delete_cookie("scout_sid")
    return response


@auth_routes.get("/logout")
def logout_link():
    return logout()
