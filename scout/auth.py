"""
Sign-in, sessions and guards.

Scouts sign in as 小隊 → 姓名 → 密碼 (patrol → name → password): the whole
point is that a 10-year-old never has to type a long username. Leaders sign in
with a username and password. A scout's *first* sign-in has no password at all —
they choose one and add an email so they can recover it later.

Passwords are stored with scrypt in exactly the format the Node build writes
(same salt length, same parameters, same hex encoding), so the two editions can
share one Google Sheet and the same accounts work in both.
"""
from __future__ import annotations

import functools
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from flask import g, jsonify, redirect, request, url_for

from .schema import DEMO_LOGIN_MAP
from .util import EMAIL_RE, hash_password, now_iso, parse_time, verify_password

SESSION_DAYS = 30
PUBLIC_USER_FIELDS = (
    "id", "role", "username", "display_name_zh", "display_name_en", "email",
    "scout_no", "section", "patrol", "unit", "avatar", "status",
    "must_change_password", "show_on_leaderboard", "created_at", "created_by",
)


def public_user(user: dict | None) -> dict | None:
    """Never let password columns reach a template or a JSON response."""
    if not user:
        return None
    out = {field: user.get(field) for field in PUBLIC_USER_FIELDS if field in user}
    out["has_password"] = bool(user.get("password_hash"))
    return out


# ── sessions ────────────────────────────────────────────────────────────────

def create_session(store, user: dict, request_obj=None) -> str:
    token = secrets.token_hex(32)
    expires = parse_time(now_iso()) + SESSION_DAYS * 86400
    from datetime import datetime, timezone

    store.insert("sessions", {
        "token": token,
        "user_id": user["id"],
        "created_at": now_iso(),
        "expires_at": datetime.fromtimestamp(expires, tz=timezone.utc).isoformat(),
        "user_agent": (request_obj.headers.get("User-Agent", "")[:180] if request_obj else ""),
    })
    return token


def end_session(store, token: str) -> None:
    if token:
        store.remove("sessions", token)


def user_from_request(store, request_obj=None, token: str = "") -> dict | None:
    """Resolve the session token (cookie, or ?sid= from the preview iframe)."""
    request_obj = request_obj or request
    token = token or request_obj.cookies.get("scout_sid", "")
    if not token:
        return None
    row = store.get("sessions", token)
    if not row:
        return None
    if row.get("expires_at") and parse_time(row["expires_at"]) < parse_time(now_iso()):
        store.remove("sessions", token)
        return None
    user = store.get("users", row.get("user_id"))
    if not user or user.get("status") != "active":
        return None
    return user


# ── guards ──────────────────────────────────────────────────────────────────

def _wants_json() -> bool:
    return request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json"


def _deny(status: int, code: str, zh: str, en: str):
    if _wants_json():
        return jsonify({"error": code, "message_zh": zh, "message_en": en}), status
    return redirect(url_for("auth_routes.login", next=request.path))


def login_required(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        if not g.get("user"):
            return _deny(401, "not_signed_in", "請先登入", "Please sign in")
        return view(*args, **kwargs)

    return wrapper


def scout_required(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        user = g.get("user")
        if not user:
            return _deny(401, "not_signed_in", "請先登入", "Please sign in")
        if user.get("role") != "scout":
            return _deny(403, "scout_only", "此頁只供童軍使用", "Scouts only")
        # The welcome form is the only scout action available until BOTH a
        # personal password and contact email have been saved. Guard every
        # scout GET/POST, not just the visible Home link: a bookmarked cave,
        # direct API call, or disabled browser validation must not bypass it.
        if needs_first_time(user) and request.endpoint not in {
            "scout_routes.welcome", "scout_routes.save_password",
        }:
            if (_wants_json() or request.headers.get("X-Requested-With") == "fetch"):
                return jsonify({
                    "error": "setup_required",
                    "message_zh": "請先設定密碼及電郵，才可進入平台。",
                    "message_en": "Set your password and email before entering the platform.",
                }), 403
            return redirect(url_for("scout_routes.welcome"))
        return view(*args, **kwargs)

    return wrapper


def leader_required(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        user = g.get("user")
        if not user:
            return _deny(401, "not_signed_in", "請先登入", "Please sign in")
        if user.get("role") != "leader":
            return _deny(403, "leader_only", "此頁只供領袖使用", "Leaders only")
        return view(*args, **kwargs)

    return wrapper


def home_for(user: dict | None) -> str:
    """Where a signed-in user belongs, including unfinished first-time setup."""
    if not user:
        return url_for("auth_routes.login")
    if user.get("role") == "leader":
        return url_for("leader_routes.overview")
    return url_for("scout_routes.welcome" if needs_first_time(user) else "scout_routes.home")


# ── signing in ──────────────────────────────────────────────────────────────

def demo_username(handle: str) -> str | None:
    entry = DEMO_LOGIN_MAP.get(str(handle or "").strip().lower())
    return entry["username"] if entry else None


def scouts_in_patrol(store, patrol: str) -> list[dict]:
    wanted = str(patrol or "").strip().lower()
    rows = [
        public_user(u) for u in store.list("users")
        if u.get("role") == "scout" and u.get("status") == "active"
        and str(u.get("patrol") or "").strip().lower() == wanted
    ]
    rows.sort(key=lambda u: str(u.get("display_name_zh") or u.get("username")))
    return rows


def sign_in(store, user: dict, request_obj=None) -> tuple[str, dict]:
    token = create_session(store, user, request_obj)
    g.user = user
    store.insert("audit_log", {
        "actor_id": user["id"], "actor_role": user.get("role", ""), "action": "sign_in",
        "entity": "users", "entity_id": user["id"], "detail_json": "{}", "created_at": now_iso(),
    })
    return token, user


def check_password(user: dict, password: str) -> bool:
    if not user.get("password_hash") or not user.get("password_salt"):
        return False
    return verify_password(password, user["password_hash"], user["password_salt"])


def set_password(store, user: dict, password: str, email: str) -> dict:
    """Complete setup in a single update; never clear the flag without email."""
    if len(password) < 6 or not valid_email(email):
        raise ValueError("A password and a valid email are required")
    hashed, salt = hash_password(password)
    return store.update("users", user["id"], {
        "password_hash": hashed, "password_salt": salt,
        "email": email.strip(), "must_change_password": False,
    })


def needs_first_time(user: dict) -> bool:
    """A scout with no password or a temporary/reset password must finish setup."""
    return (user.get("role") == "scout" and
            (not user.get("password_hash") or bool(user.get("must_change_password"))))


def valid_email(value: str) -> bool:
    return bool(EMAIL_RE.match(str(value or "").strip()))


def lock_user(store, user: dict) -> dict:
    return store.update("users", user["id"], {"status": "locked"})


def unlock_user(store, user: dict) -> dict:
    return store.update("users", user["id"], {"status": "active"})


def reset_password(store, user: dict) -> dict:
    """Leader-side reset — the scout's next sign-in asks for a new password."""
    return store.update("users", user["id"], {
        "password_hash": "", "password_salt": "", "must_change_password": True,
    })


# ── one-time reset links (emailed to the address on the account) ────────────

def token_hash(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def create_reset_token(store, user: dict, minutes: int = 60, requested_by: str = "scout") -> tuple[str, dict]:
    """Mint a single-use reset link token: raw for the email, hashed on disk."""
    token = secrets.token_urlsafe(32)
    now = now_iso()
    expires = datetime.fromtimestamp(parse_time(now) + max(5, int(minutes)) * 60, tz=timezone.utc)
    row = store.insert("password_resets", {
        "user_id": user["id"], "token_hash": token_hash(token),
        "email": (user.get("email") or "").strip(), "created_at": now,
        "expires_at": expires.isoformat(), "used_at": "",
        "requested_by": requested_by, "sent_to": (user.get("email") or "").strip(),
    })
    return token, row


def live_reset_tokens(store, user_id: str) -> list[dict]:
    """Links for this scout that are still good for another minute (newest first)."""
    now = parse_time(now_iso())
    live = []
    for row in store.list("password_resets"):
        if row.get("user_id") != user_id or row.get("used_at"):
            continue
        if row.get("expires_at") and parse_time(row["expires_at"]) > now:
            live.append(row)
    return sorted(live, key=lambda r: r.get("created_at") or "", reverse=True)


def find_reset(store, token: str) -> dict | None:
    """The row behind a token from an email link, if it is still usable."""
    if not token:
        return None
    wanted = token_hash(token)
    for row in store.list("password_resets"):
        if row.get("token_hash") == wanted:
            return row
    return None


def reset_token_state(store, token: str) -> tuple[str, dict | None]:
    """'ok' | 'unknown' | 'used' | 'expired' — plus the row when there is one."""
    row = find_reset(store, token)
    if not row:
        return "unknown", None
    if row.get("used_at"):
        return "used", row
    if row.get("expires_at") and parse_time(row["expires_at"]) < parse_time(now_iso()):
        return "expired", row
    return "ok", row


def consume_reset(store, row: dict, password: str) -> dict:
    """Set the new password and burn the link (and every other link for that scout)."""
    user = store.get("users", row.get("user_id"))
    if not user:
        raise ValueError("The account is gone")
    saved = set_password(store, user, password, user.get("email") or "")
    store.update("password_resets", row["id"], {"used_at": now_iso()})
    for other in live_reset_tokens(store, user["id"]):
        store.update("password_resets", other["id"], {"used_at": now_iso()})
    for session in store.list("sessions"):                    # old sessions die with the old password
        if session.get("user_id") == user["id"]:
            store.remove("sessions", session.get("token"))
    return saved
