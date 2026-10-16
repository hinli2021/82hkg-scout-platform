"""
Scout Progress Platform — Python edition
========================================
A Flask + Jinja rewrite of the Node/Express build. Real pages, real URLs,
server-rendered: scouts and leaders each get their own screens, and the rules
(badges, points ledger, streaks, leaderboard) live in `scout/engine.py`.

Storage is pluggable and identical to the Node build:
  DATA_DRIVER=local   → JSON files in ./data/db  + uploads in ./data/uploads
  DATA_DRIVER=sheets  → your Google Spreadsheet IS the database, and photo
                        evidence is uploaded into your Google Drive folder.

The Google Sheet layout is the same one the Node build uses (one tab per
collection, row 1 = headers, complex values stored as JSON text), so a Sheet
created for either version works in both.
"""
from __future__ import annotations

import os

from datetime import datetime

from flask import render_template, Flask, abort, g, redirect, request, session, url_for

APP_BUILD = datetime.now().strftime('%Y-%m-%d %H:%M')

from scout import auth as auth_module
from scout.auth import public_user
from scout.schema import TASK_TYPES, patrol_label
from scout.mascots import MASCOTS, mascot_for
from scout.store import Store
from scout.routes.auth_routes import auth_routes
from scout.routes.leader_routes import leader_routes
from scout.routes.scout_routes import scout_routes



def setup_health_checks(store, counts: dict, on_sheets: bool) -> list[dict]:
    """健康檢查頁上的幾行：每一行都說「現在怎樣」和「怎樣做」。"""
    badge_count = counts.get("badges", 0)
    task_count = counts.get("tasks", 0)
    return [
        {
            "ok": on_sheets,
            "title": "資料儲存在 Google 試算表" if on_sheets else "資料暫存在執行個體空間",
            "detail": ("帳戶、進度、積分都存在你的試算表，重新部署不會影響。"
                       if on_sheets else
                       "現在寫在執行個體的 /tmp，一段時間沒有流量就會被回收 —— 帳戶與進度會消失。"),
            "fix": ("", "在 Vercel → Settings → Environment Variables 加入 GOOGLE_SHEET_ID 與 "
                        "GOOGLE_SERVICE_ACCOUNT_JSON，然後到 Deployments → ⋯ → Redeploy。"),
        },
        {
            "ok": badge_count >= 5 and task_count >= 11,
            "title": "獎章目錄與遊戲項目" if badge_count >= 5 and task_count >= 11
                     else "獎章目錄還未建立",
            "detail": f"獎章 {badge_count}／任務 {task_count}。"
                      + ("已完成，之後不會被更新覆蓋。" if badge_count >= 5 else
                         "連上試算表後，第一次開啟會自動建立一次。"),
            "fix": ("", "確認 Vercel 正在執行最新版本（Deployments → Redeploy），"
                        "再重新打開平台一次。"),
        },
    ]

def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.update(
        SECRET_KEY=(os.environ.get("SESSION_SECRET") or os.environ.get("SECRET_KEY")
                    or os.urandom(32).hex()),
        # NB: the platform's own sign-in token also travels in a cookie called
        # `scout_sid` (see auth_routes._set_session_cookie). Flask's flash
        # session must therefore live under a *different* name, or every
        # flash() would overwrite the token and silently sign the scout out.
        SESSION_COOKIE_NAME="scout_flash",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
        MAX_CONTENT_LENGTH=6 * 1024 * 1024,  # photo evidence cap
    )
    if config:
        app.config.update(config)

    store: Store = app.config.get("STORE") or Store.from_env()
    app.extensions["store"] = store

    # One context processor feeds every template the things all pages need.
    @app.context_processor
    def inject_globals():
        lang = request.cookies.get("scout_lang", "zh")
        lang = "en" if lang == "en" else "zh"
        return {
            "lang": lang,
            "L": lambda zh, en="": (en or zh) if lang == "en" else (zh or en),
            "settings": store.settings_cached(),
            # Templates never see password columns — only the public view.
            "user": public_user(g.get("user")),
            "raw_user": g.get("user"),
            "storage_mode": store.driver.name,
            # 領袖後台要知道資料放在哪裡：試算表模式顯示連結，暫存模式顯示警告
            "storage_sheet_id": getattr(store.driver, "spreadsheet_id", ""),
            "storage_drive_folder": getattr(store.driver, "drive_folder_id", ""),
            # 正式上線時，若資料只寫在暫存空間，領袖後台要提醒（會自己重置）
            "ephemeral_storage": (store.driver.name == "local"
                                  and str(store.config.get("data_dir", "")).startswith("/tmp")),
            "demo_login": store.config.get("demo_login", True),
            "patrol_label": patrol_label,
            "mascot_for": mascot_for,       # 三個小隊吉祥物（登入卡、名牌）
            "MASCOTS": MASCOTS,
            "TASK_TYPES": TASK_TYPES,
        }

    @app.before_request
    def load_user():
        """Who is this?

        The sign-in token normally arrives in the `scout_sid` cookie. Inside the
        preview iframe, though, the page is a *third-party* frame, so browsers
        quietly drop that cookie and every sign-in bounces back to /login. The
        same token is therefore also accepted (and carried along) as `?sid=…`,
        which works in any frame, on any device, with cookies switched off.
        """
        token = (request.values.get("sid")       # ?sid=… or a hidden form field
                 or request.headers.get("X-Session-Token", "")
                 or request.cookies.get("scout_sid", ""))
        g.sid = token
        g.sid_from_url = bool(token) and not request.cookies.get("scout_sid")
        g.user = auth_module.user_from_request(store, request, token=token)

    app.register_blueprint(auth_routes)
    app.register_blueprint(scout_routes)
    app.register_blueprint(leader_routes)

    # Every link/form in every template goes through url_for, so carrying the
    # token is a one-line job: keep ?sid=… on the URLs we generate.
    from flask import url_for as _flask_url_for

    def url_for(endpoint, **values):          # noqa: F811  (shadow on purpose)
        url = _flask_url_for(endpoint, **values)
        token = g.get("sid") if hasattr(g, "sid") else ""
        if token and endpoint != "static" and not url.startswith(("http://", "https://")):
            if "sid=" not in url:
                url += ("&" if "?" in url else "?") + "sid=" + token
        return url

    app.jinja_env.globals["url_for"] = url_for
    # A stamp on every page: 一看原始碼或 console 便知是哪一個版本。
    # (app.py: APP_BUILD / 離線檔: window.OFFLINE_DEMO_BUILD)
    app.jinja_env.globals["BUILD"] = APP_BUILD

    @app.after_request
    def no_stale_pages(response):
        """Page HTML is never cached.

        A preview panel (or a browser) that keeps yesterday's HTML is the
        fastest way to make a change look like it never happened, so pages are
        marked no-store; static files keep their normal caching.
        """
        if response.mimetype == "text/html":
            response.headers["Cache-Control"] = "no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response

    @app.after_request
    def carry_token(response):
        """Redirects must carry the token too, or a form post drops the session."""
        token = g.get("sid") if hasattr(g, "sid") else ""
        if token:
            location = response.headers.get("Location", "")
            if location.startswith("/") and "sid=" not in location:
                response.headers["Location"] = location + ("&" if "?" in location else "?") + "sid=" + token
            # A normal browser tab gets the cookie back as well, so the token
            # stops appearing in the address bar once cookies work.
            if getattr(g, "sid_from_url", False) and g.get("user"):
                response.set_cookie("scout_sid", token, max_age=30 * 86400, httponly=True,
                                    samesite="Lax", secure=request.is_secure)
        return response

    @app.template_filter("status_word")
    def status_word(value):
        words = {
            "completed": {"zh": "已完成", "en": "Completed"},
            "pending": {"zh": "待領袖核實", "en": "Waiting for a leader"},
            "rejected": {"zh": "可重做", "en": "Redo"},
            "todo": {"zh": "未開始", "en": "Not started"},
        }
        hit = words.get(str(value), {"zh": str(value), "en": str(value)})
        return hit["en"] if request.cookies.get("scout_lang") == "en" else hit["zh"]

    @app.get("/health")
    def health():
        """部署是否就緒 —— 供上線檢查用（只回報數字，不含任何個人資料）。

        用瀏覽器打開會看到一張人看的狀態頁；程式（curl、檢查腳本）拿到的是 JSON。
        """
        counts: dict[str, int] = {}
        for name in ("badges", "tasks", "users"):
            try:
                counts[name] = len(store.list(name))
            except Exception:                       # noqa: BLE001 — health must never 500
                counts[name] = -1
        on_sheets = store.driver.name == "sheets"
        payload = {
            "ok": True,
            "storage": store.driver.name,
            "unit": store.settings_cached().get("unit_name_zh", ""),
            "demo": bool(store.config.get("demo_login") or store.config.get("seed_demo")),
            "counts": counts,
            "setup_ready": counts.get("badges", 0) >= 5 and counts.get("tasks", 0) >= 11,
        }
        # 人在瀏覽器打開（Accept: text/html）就給他一張看得懂的頁；程式仍然拿 JSON
        if request.accept_mimetypes["text/html"]:
            return render_template("health.html", data=payload, on_sheets=on_sheets,
                                   setup=setup_health_checks(store, counts, on_sheets))
        return payload

    @app.get("/img/badges/<path:filename>")
    def badge_art(filename: str):
        """Award artwork. The stored path (/img/badges/…) is the one the Node
        build writes, so a Sheet filled by either edition renders the same."""
        from flask import send_from_directory

        return send_from_directory(os.path.join(app.static_folder, "img"), filename)

    @app.get("/uploads/<path:filename>")
    def uploaded_file(filename: str):
        """Photo evidence stored locally (with DATA_DRIVER=sheets these live in Drive)."""
        from flask import send_from_directory

        if store.driver.name != "local":
            abort(404)
        return send_from_directory(store.driver.uploads_dir, filename)

    @app.get("/set-language/<code>")
    def set_language(code: str):
        """Language is a plain cookie — every page renders in the chosen one."""
        nxt = request.args.get("next") or request.referrer or "/"
        resp = redirect(nxt if str(nxt).startswith("/") else "/")
        resp.set_cookie("scout_lang", "en" if code == "en" else "zh", max_age=86400 * 365, samesite="Lax")
        return resp

    return app


app = create_app()


if __name__ == "__main__":
    from scout.store import bootstrap_data_dir

    bootstrap_data_dir(app.extensions["store"])
    port = int(os.environ.get("PORT", "5001"))
    app.run(host=os.environ.get("HOST", "0.0.0.0"), port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
