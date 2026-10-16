"""Return the dedicated demo scout07 to a blank membership-game slate.

Only records linked to that account and membership badge are removed; other
scouts, other badges and manual point adjustments are not touched. Browser
checks use this at both ends so running them repeatedly cannot accumulate
unmatched task points after removing the corresponding practice submissions.
Do NOT run this helper against a real scout's account.
"""
from __future__ import annotations

import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATA_DIR", str(ROOT / "data"))

from scout.store import Store           # noqa: E402


def complete_setup(base: str, ctx, password: str = "tiger777") -> None:
    """Open the first-entry gate for a browser check that follows the demo3 scout.

    Every scout page waits behind the password + email form until setup is done,
    so a check that wants to walk the cave (or the badge doors) has to finish it
    first. `POST /login/demo/demo3` clears scout07's password on every run, so
    this leaves no usable password behind.
    """
    response = ctx.request.post(f"{base}/welcome", form={
        "password": password, "confirm": password, "email": "scout07@example.com",
    })
    if response.status not in (200, 302):
        raise SystemExit(f"first-time setup refused: {response.status}")


def blank_slate() -> int:
    st = Store.from_env()
    scout = next(u for u in st.list("users") if u.get("username") == "scout07")
    badge = next(b for b in st.list("badges") if b.get("code") == "SC-01")
    user_id, badge_id = scout["id"], badge["id"]
    tasks = {t["id"] for t in st.list("tasks") if t.get("badge_id") == badge_id}
    removed = 0
    for row in st.list("progress_records"):
        if row.get("user_id") == user_id and row.get("task_id") in tasks:
            st.remove("progress_records", row["id"])
            removed += 1
    for row in st.list("badge_awards"):
        if row.get("user_id") == user_id and row.get("badge_id") == badge_id:
            st.remove("badge_awards", row["id"])
    for row in st.list("points_ledger"):
        if (row.get("user_id") == user_id
                and ((row.get("entry_type") == "task" and row.get("ref_id") in tasks)
                     or (row.get("entry_type") == "badge" and row.get("ref_id") == badge_id))):
            st.remove("points_ledger", row["id"])
    for row in st.list("audit_log"):
        if (row.get("actor_id") == user_id and row.get("action") == "start_quest"
                and row.get("entity_id") == badge_id):
            st.remove("audit_log", row["id"])
    st.rebuild_stats(user_id)
    return removed


def blank_game(username: str, codes: set[str], badge_code: str = "SC-01") -> int:
    """Clear one scout's records for a few game tasks (used by the bridge check).

    A browser walk of 迷霧渡口 writes a real completion, so the check clears the
    rows it created at both ends and leaves the demo exactly as it found it —
    but only for the accounts it names, and only for the codes it names.
    """
    st = Store.from_env()
    scout = next((u for u in st.list("users") if u.get("username") == username), None)
    if scout is None:
        raise SystemExit(f"{username} not found")
    badge = next((b for b in st.list("badges") if b.get("code") == badge_code), None)
    ids = {t["id"] for t in st.list("tasks")
           if badge and t.get("badge_id") == badge["id"] and t.get("code") in codes}
    removed = 0
    for row in st.list("progress_records"):
        if row.get("user_id") == scout["id"] and row.get("task_id") in ids:
            st.remove("progress_records", row["id"])
            removed += 1
    for row in st.list("points_ledger"):
        if (row.get("user_id") == scout["id"] and row.get("entry_type") == "task"
                and row.get("ref_id") in ids):
            st.remove("points_ledger", row["id"])
    st.rebuild_stats(scout["id"])
    return removed
