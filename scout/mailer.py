"""
Sending mail — the one-time password-reset link.

A scout asks for a reset, the platform mails a single-use link to the address on
their account, and the link opens a page where they choose a new password. No
password is ever mailed, and nobody has to type an address to prove who they are.

Mail only leaves the building when a leader has filled in the SMTP settings
(unit Gmail with an app password is the usual choice):

    smtp_host      smtp.gmail.com
    smtp_port      587
    smtp_tls       tls                       (587 = TLS, 465 = SSL)
    smtp_user      yourunit@gmail.com        (also the sign-in name)
    smtp_password  the 16-character app password
    smtp_from      yourunit@gmail.com        (may be “82nd HK Group <…@gmail.com>”)

With no mailbox configured nothing breaks: the scout is offered the on-the-spot
method instead (their email + a new password), or the leader can reset the
account from the console. `is_configured()` is what the pages ask.

`deliver()` is the only place that talks to the network, so the test suite can
swap it for a recorder and check the message that would have gone out.
"""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

DEFAULTS = {
    "smtp_host": "",
    "smtp_port": 587,
    "smtp_tls": "tls",          # tls | ssl | none
    "smtp_user": "",
    "smtp_password": "",
    "smtp_from": "",
    "public_base_url": "",      # only needed if the link must use another address
    "reset_link_minutes": 60,   # how long a reset link stays good
}

#: the last send attempt, for the leader console (never contains the password)
LAST_RESULT: dict = {}


def config(settings: dict | None) -> dict:
    """The SMTP settings, with sensible fallbacks for anything unset."""
    settings = settings or {}
    out = dict(DEFAULTS)
    for key in DEFAULTS:
        value = settings.get(key)
        if value not in (None, ""):
            out[key] = value
    if not out["smtp_from"]:
        out["smtp_from"] = out["smtp_user"]
    try:
        out["smtp_port"] = int(out["smtp_port"] or 587)
    except (TypeError, ValueError):
        out["smtp_port"] = 587
    try:
        out["reset_link_minutes"] = max(5, min(24 * 60, int(out["reset_link_minutes"] or 60)))
    except (TypeError, ValueError):
        out["reset_link_minutes"] = 60
    return out


def is_configured(cfg: dict) -> bool:
    return bool((cfg or {}).get("smtp_host") and (cfg or {}).get("smtp_from"))


def mask_email(address: str) -> str:
    """A hint, not the address: `sc***@82hkg.example` — enough to be recognised."""
    address = str(address or "").strip()
    if "@" not in address:
        return "***"
    local, _, domain = address.partition("@")
    head = local[:2] if len(local) > 2 else local[:1]
    return f"{head}***@{domain}"


def _address(value: str) -> tuple[str, str]:
    name, address = parseaddr(str(value or ""))
    return (name, address or str(value or "").strip())


def build_message(cfg: dict, to: str, subject: str, text: str) -> EmailMessage:
    message = EmailMessage()
    name, sender = _address(cfg.get("smtp_from") or cfg.get("smtp_user") or "")
    message["From"] = formataddr((name, sender)) if name else sender
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    return message


def deliver(cfg: dict, message: EmailMessage) -> tuple[bool, str]:
    """Hand the message to the SMTP server. Returns (ok, error)."""
    host = cfg.get("smtp_host")
    port = int(cfg.get("smtp_port") or 587)
    mode = (cfg.get("smtp_tls") or "tls").lower()
    try:
        if mode == "ssl":
            server = smtplib.SMTP_SSL(host, port, timeout=20, context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(host, port, timeout=20)
        with server:
            server.ehlo()
            if mode == "tls":
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            if cfg.get("smtp_user"):
                server.login(cfg["smtp_user"], cfg.get("smtp_password") or "")
            server.send_message(message)
        return True, ""
    except Exception as error:                       # noqa: BLE001 — the reason is shown to the leader
        return False, f"{type(error).__name__}: {error}"


def send(cfg: dict, to: str, subject: str, text: str) -> tuple[bool, str]:
    """Build and deliver one message, remembering how it went."""
    global LAST_RESULT
    if not is_configured(cfg):
        LAST_RESULT = {"ok": False, "error": "no_mailbox", "to": to}
        return False, "no_mailbox"
    if not to:
        LAST_RESULT = {"ok": False, "error": "no_recipient", "to": ""}
        return False, "no_recipient"
    message = build_message(cfg, to, subject, text)
    ok, error = deliver(cfg, message)
    LAST_RESULT = {"ok": ok, "error": error, "to": to, "subject": subject}
    return ok, error


# ── the letter itself ───────────────────────────────────────────────────────

def reset_body(scout_name_zh: str, scout_name_en: str, link: str, minutes: int, unit_zh: str) -> str:
    return f"""{scout_name_zh}（{scout_name_en}）你好：

你在{unit_zh}的童軍進度平台要求重設密碼。請打開下面這條連結，設定一個新密碼：

{link}

· 連結 {minutes} 分鐘內有效，而且只可以用一次。
· 設定完成後，請用新密碼登入。
· 如果你沒有按過「忘記密碼」，可以不理會這封電郵，你的密碼不會改變。

—

Hello {scout_name_en},

Someone asked to reset the password for your {unit_zh} scout account. Open this link to choose a new password:

{link}

· The link works for {minutes} minutes, and only once.
· After setting it, sign in with your new password.
· If this was not you, simply ignore this email — your password stays unchanged.
"""


def send_reset_link(cfg: dict, user: dict, link: str, unit_zh: str = "港島第八十二旅童軍團") -> tuple[bool, str]:
    minutes = int(cfg.get("reset_link_minutes") or 60)
    subject = "重設童軍平台密碼 / Reset your scout platform password"
    body = reset_body(user.get("display_name_zh") or "", user.get("display_name_en") or "",
                      link, minutes, unit_zh)
    return send(cfg, (user.get("email") or "").strip(), subject, body)


def send_test(cfg: dict, to: str, unit_zh: str = "港島第八十二旅童軍團") -> tuple[bool, str]:
    body = (f"這是一封測試郵件，由{unit_zh}的童軍進度平台寄出。\n"
            "你見到這封信，就表示重設密碼的電郵可以正常寄出。\n\n"
            "This is a test message from the scout platform. Mail is working — "
            "a scout who forgets their password will be able to receive a reset link.\n")
    return send(cfg, to, "測試郵件 / Test message — scout platform", body)
