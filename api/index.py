"""Vercel entry point — the official platform, served as a serverless function.

This is the production door for 港島第八十二旅童軍團. It sets the *official*
defaults before the Flask app is imported:

* ``DEMO_LOGIN`` / ``SEED_DEMO`` — **off**. No one-tap demo accounts and no
  seeded 示範童軍 on the live site. The first person to open the site sees
  「建立第一位領袖」 (`/setup`) and becomes the unit's leader; every other
  account is created by that leader in the console.
* ``DATA_DRIVER`` — ``sheets`` as soon as a Google Sheet is configured
  (``GOOGLE_SHEET_ID`` set), because that is the only storage here that
  survives: the filesystem is read-only apart from ``/tmp``, which is
  per-instance and recycled. Without a Sheet the platform still runs, but the
  leader console shows 資料暫存警告 and data resets by itself.
* ``SESSION_SECRET`` — required for real use. If it is not set in the Vercel
  project, one is generated once and kept in the store's settings, so it stays
  the same across cold starts instead of signing everybody out on every
  restart.
* ``TZ`` — Asia/Hong_Kong, so the dates a leader sees are the unit's dates.
"""
from __future__ import annotations

import os
import secrets
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── the unit runs on Hong Kong time ─────────────────────────────────────────
os.environ.setdefault("TZ", "Asia/Hong_Kong")
try:
    import time as _time
    _time.tzset()
except (AttributeError, OSError):        # pragma: no cover — platforms without tzset
    pass

# ── official defaults (a demo deployment can override these in Vercel) ──────
os.environ.setdefault("DEMO_LOGIN", "false")
os.environ.setdefault("SEED_DEMO", "false")
os.environ.setdefault("DATA_DIR", "/tmp/scout-platform-data")
if not os.environ.get("DATA_DRIVER"):
    # a configured Sheet is the real database; otherwise fall back to /tmp
    if os.environ.get("GOOGLE_SHEET_ID") or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") \
            or os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE"):
        os.environ["DATA_DRIVER"] = "sheets"

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _session_secret() -> str:
    """A secret that outlives the instance, without anyone having to set it.

    Kept in the store's own settings when the store is durable (a Google
    Sheet). With /tmp storage it is regenerated whenever the instance is
    recycled — which is one more reason to configure a Sheet.
    """
    if os.environ.get("SESSION_SECRET"):
        return os.environ["SESSION_SECRET"]
    try:
        from scout.store import Store          # imported here: needs DATA_DIR first
        from scout.util import now_iso

        store = Store.from_env()
        for row in store.list("settings"):
            if row.get("key") == "session_secret":
                value = row.get("value_json")
                if isinstance(value, str) and len(value) >= 32:
                    return value
        value = secrets.token_hex(32)
        store.insert("settings", {"key": "session_secret", "value_json": value,
                                  "updated_at": now_iso()})
        return value
    except Exception:                          # pragma: no cover — never block boot
        return secrets.token_hex(32)


os.environ.setdefault("SESSION_SECRET", _session_secret())

from app import app  # noqa: E402  (the factory ran at import time)

handler = app          # Vercel looks for `handler`
application = app
