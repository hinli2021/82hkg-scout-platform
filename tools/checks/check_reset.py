#!/usr/bin/env python3
"""The emailed reset link, end to end, against a real SMTP conversation.

    bash tools/bootstrap_browser.sh                                  # once
    LD_LIBRARY_PATH=/tmp/syslibs python3 tools/checks/check_reset.py

This check does not fake the mailer: it starts a tiny SMTP sink on a spare port,
points the platform's 「寄信信箱」at it, and then follows a scout through the
whole journey in a real browser —

    password page → 忘記密碼？ → 寄出重設連結 → 「請查看你的電郵」
    → read the message the sink received → open the link it contains
    → set a new password → sign in with it → 主頁

and then proves the link is dead (a second visit says 已經用過), that an expired
link is refused, and that after a password reset the old password no longer
works. Nothing touches the real `data/`: a throwaway data dir and a temporary
site are used, with screenshots in docs/screens/reset-*.png.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading

LIBS = subprocess.run("find /tmp/syslibs -name '*.so*' -printf '%h\\n' | sort -u | tr '\\n' ':'",
                      shell=True, capture_output=True, text=True).stdout
os.environ["LD_LIBRARY_PATH"] = LIBS + os.environ.get("LD_LIBRARY_PATH", "")

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHOTS = ROOT / "docs" / "screens"
PORT = int(os.environ.get("RESET_CHECK_PORT", "5078"))
SMTP_PORT = int(os.environ.get("RESET_CHECK_SMTP_PORT", "8026"))

MAILBOX: list[dict] = []
LETTER = {"to": "", "body": ""}


class Sink:
    """A one-message SMTP server: accepts anything, keeps the body."""

    def __init__(self, port: int):
        from aiosmtpd.controller import Controller

        class Handler:
            async def handle_DATA(self, server, session, envelope):
                from email import message_from_bytes
                parsed = message_from_bytes(envelope.content)
                body = ""
                for part in parsed.walk():
                    if part.get_content_type() == "text/plain":
                        body += part.get_payload(decode=True).decode("utf-8", "replace")
                MAILBOX.append({
                    "to": envelope.rcpt_tos[0] if envelope.rcpt_tos else "",
                    "subject": str(parsed.get("Subject") or ""),
                    "body": body,
                    "raw": envelope.content.decode("utf-8", "replace"),
                })
                return "250 Message accepted for delivery"

        self.controller = Controller(Handler(), hostname="127.0.0.1", port=port)

    def __enter__(self):
        self.controller.start()
        return self

    def __exit__(self, *exc):
        self.controller.stop()


def build_site() -> tuple[object, pathlib.Path]:
    workdir = pathlib.Path(tempfile.mkdtemp(prefix="reset-check-"))
    os.environ["DATA_DIR"] = str(workdir)
    os.environ["SEED_DEMO"] = "true"
    os.environ.setdefault("SECRET_KEY", "reset-check")
    os.environ.setdefault("DEMO_LOGIN", "true")
    sys.path.insert(0, str(ROOT))
    from app import create_app                                        # noqa: E402
    from scout.store import Store                                     # noqa: E402

    app = create_app()
    store = Store.from_env()
    store.save_setting("smtp_host", "127.0.0.1")
    store.save_setting("smtp_port", SMTP_PORT)
    store.save_setting("smtp_tls", "none")
    store.save_setting("smtp_user", "")
    store.save_setting("smtp_password", "")
    store.save_setting("smtp_from", "82hkg@example.com")
    store.save_setting("unit_name_zh", "港島第八十二旅童軍團")
    store.save_setting("reset_link_minutes", 60)
    return app, store, workdir


def serve(app):
    from werkzeug.serving import make_server
    server = make_server("127.0.0.1", PORT, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def link_from_letter(letter: dict) -> str:
    """The reset link, as the scout's mail app would show it."""
    found = re.search(r"https?://\S*?/reset/[A-Za-z0-9_\-]+", letter.get("body") or "")
    if not found:
        raise SystemExit(f"no reset link in the letter:\n{(letter.get('body') or '')[:800]}")
    return found.group(0)


def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []
    with Sink(SMTP_PORT) as sink:
        app, store, workdir = build_site()
        server = serve(app)
        base = f"http://127.0.0.1:{PORT}"
        scout = next(u for u in store.list("users") if u.get("username") == "scout01")
        email_on_file = scout.get("email") or ""
        print(f"temporary site {base} · SMTP sink 127.0.0.1:{SMTP_PORT} · data {workdir}")
        print(f"scout01 王小明 · email on file {email_on_file}")

        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            ctx = browser.new_context(viewport={"width": 900, "height": 950}, locale="zh-HK")
            page = ctx.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            # a reused link and a missing route answer 410/405 on purpose; only
            # script errors and other console noise are a problem
            page.on("console", lambda m: errors.append(m.text)
                    if m.type == "error" and "Failed to load resource" not in m.text else None)

            password_url = f"{base}/login/scout/Tiger/{scout['id']}"
            page.goto(password_url, wait_until="networkidle")
            page.click("a.link-btn")                                   # 忘記密碼？
            page.wait_for_load_state("networkidle")
            print(f"  forgot page      → {page.url.replace(base, '')}")
            body = page.inner_text("body")
            if "寄出重設連結" not in body:
                problems.append("the forgot page does not offer to email a link")
            if email_on_file not in body and "sc***@" not in body:
                problems.append("the page does not show the masked address")
            if email_on_file and email_on_file in body:
                problems.append("the page printed the full email address")
            page.screenshot(path=str(SHOTS / "reset-request.png"), full_page=True)

            page.click("button[type='submit']")                        # 寄出重設連結
            page.wait_for_load_state("networkidle")
            sent_page = page.inner_text("body")
            print(f"  after sending    → {page.url.replace(base, '')} · {sent_page.splitlines()[3][:40]}")
            if "請查看你的電郵" not in sent_page:
                problems.append("no 「請查看你的電郵」 page after sending")
            page.screenshot(path=str(SHOTS / "reset-sent.png"), full_page=True)

            if not MAILBOX:
                problems.append("the SMTP sink received nothing")
            else:
                letter = MAILBOX[0]
                print(f"  letter received  → to {letter['to']}")
                if letter["to"] != email_on_file:
                    problems.append(f"letter went to {letter['to']}, expected {email_on_file}")
                if "Reset" not in letter["subject"]:
                    problems.append(f"the subject does not name the reset: {letter['subject']!r}")
                for wanted in ("重設", "港島第八十二旅童軍團", "王小明", "Wong Siu Ming", "60"):
                    if wanted not in letter["body"]:
                        problems.append(f"the letter is missing {wanted!r}")
                if "scout1234" in letter["body"]:
                    problems.append("a password appeared in the letter")
                link = link_from_letter(letter)
                print(f"  link in letter   → {link.replace(base, '')}")

                page.goto(link, wait_until="networkidle")
                print(f"  link opens       → {page.inner_text('body').splitlines()[2][:30]}")
                page.screenshot(path=str(SHOTS / "reset-link.png"), full_page=True)
                page.fill('input[name="password"]', "newtiger99")
                page.fill('input[name="confirm"]', "newtiger99")
                page.click("button[type='submit']")
                page.wait_for_load_state("networkidle")
                landed = page.inner_text("body")
                print(f"  after saving     → {page.url.replace(base, '')}")
                if "密碼已更新" not in landed:
                    problems.append("no 「密碼已更新」 note after following the link")
                page.screenshot(path=str(SHOTS / "reset-done.png"), full_page=True)

                again = page.goto(link, wait_until="networkidle")
                if again.status != 410 or "已經用過" not in page.inner_text("body"):
                    problems.append(f"a used link still opened (status {again.status})")
                else:
                    print("  link reused      → refused (410 · 已經用過)")
                    page.screenshot(path=str(SHOTS / "reset-used.png"), full_page=True)

            # the new password works, the old one does not
            ctx2 = browser.new_context(locale="zh-HK")
            login = ctx2.new_page()
            login.goto(password_url, wait_until="networkidle")
            login.fill('input[name="password"]', "scout1234")
            login.click("button[type='submit']")
            login.wait_for_load_state("networkidle")
            old_refused = login.inner_text("body")
            if "密碼不正確" not in old_refused:
                problems.append("the old password still works after a reset")
            login.fill('input[name="password"]', "newtiger99")
            login.click("button[type='submit']")
            login.wait_for_load_state("networkidle")
            print(f"  new password     → {login.url.replace(base, '')}")
            if "/home" not in login.url:
                problems.append(f"signing in with the new password landed on {login.url}")
            ctx2.close()

            # an expired link is refused
            import urllib.request
            from datetime import datetime, timedelta, timezone
            urllib.request.urlopen(urllib.request.Request(
                f"{base}/forgot/scout/Tiger/{scout['id']}/send", method="POST"))
            if len(MAILBOX) < 2:
                problems.append("the second request sent no letter")
            else:
                expired_link = link_from_letter(MAILBOX[-1])
                fresh = max(store.list("password_resets"), key=lambda r: r["created_at"])
                past = (datetime.now(tz=timezone.utc) - timedelta(minutes=1)).isoformat()
                store.update("password_resets", fresh["id"], {"expires_at": past})
                probe_ctx = browser.new_context(locale="zh-HK")
                probe = probe_ctx.new_page()
                response = probe.goto(expired_link, wait_until="networkidle")
                said = probe.inner_text("body")
                if response.status != 410 or "過期" not in said:
                    problems.append(f"an expired link still opened (status {response.status})")
                else:
                    print("  expired link     → refused (410 · 過期)")
                probe_ctx.close()

            if errors:
                problems.append(f"browser errors: {errors[:3]}")
            ctx.close()
            browser.close()

        server.shutdown()
        shutil.rmtree(workdir, ignore_errors=True)

    if problems:
        print("\nFAILED")
        for problem in problems:
            print("  ✗", problem)
        return 1
    print("\nOK — 忘記密碼? → one button → a real SMTP letter → link → new password → "
          "signed in; the link is single-use, expires, and the old password is dead")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
