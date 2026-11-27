"""意見箱 — scouts report bugs and offer ideas; leaders reward the good ones.

A scout files a report (kind `bug`) or an idea (kind `idea`) with a title and
a short explanation. The row waits as `new` until a leader reads it on
/leader/feedback and either rewards it — points paid once through the ordinary
ledger, so the balance and the 龍虎榜 pick them up — or closes it. The scout
sees the outcome and the leader's reply on their own 意見箱 page.
"""
from __future__ import annotations

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from ..auth import leader_required, scout_required
from ..engine import as_int, write_ledger
from ..util import now_iso
from .helpers import audit, fail, ok, store, wants_json

feedback_routes = Blueprint("feedback_routes", __name__)

KINDS = {
    "bug": {"zh": "問題報告", "en": "Bug report", "emoji": "🐛"},
    "idea": {"zh": "建議", "en": "Idea", "emoji": "💡"},
}
STATUSES = ("new", "rewarded", "closed")
MAX_POINTS = 50
TITLE_MAX = 80
BODY_MAX = 2000


def _rows_for(st, user_id: str) -> list[dict]:
    rows = [row for row in st.list("feedback") if row.get("user_id") == user_id]
    return sorted(rows, key=lambda r: str(r.get("created_at") or ""), reverse=True)


def teaser(st, user_id: str) -> dict:
    """Home tile: how many of this scout's reports are still waiting."""
    rows = [row for row in st.list("feedback") if row.get("user_id") == user_id]
    return {
        "waiting": sum(1 for row in rows if row.get("status") == "new"),
        "sent": len(rows),
    }


# ── the scout side ──────────────────────────────────────────────────────────

@feedback_routes.get("/feedback")
@scout_required
def page():
    st = store()
    return render_template(
        "scout/feedback.html",
        kinds=KINDS,
        mine=_rows_for(st, g.user["id"]),
        sent=request.args.get("sent", ""),
    )


@feedback_routes.post("/feedback")
@scout_required
def submit():
    st = store()
    body = request.form
    kind = str(body.get("kind") or "")
    title = str(body.get("title") or "").strip()
    text = str(body.get("body") or "").strip()
    if kind not in KINDS:
        return fail(400, "feedback_kind", "請先選擇這是問題報告還是建議。",
                    "Choose whether this is a bug report or an idea first.")
    if not title or not text:
        return fail(400, "feedback_empty", "請填寫標題和內容。",
                    "Please fill in both the title and the details.")
    if len(title) > TITLE_MAX or len(text) > BODY_MAX:
        return fail(400, "feedback_long", "內容太長，請寫短一點。",
                    "That is too long — please keep it shorter.")
    row = st.insert("feedback", {
        "user_id": g.user["id"], "kind": kind, "title": title, "body": text,
        "status": "new", "points_awarded": 0, "leader_comment": "",
        "created_at": now_iso(), "decided_at": "", "decided_by": "",
    })
    audit(g.user, "feedback_submit", "feedback", row["id"], {"kind": kind})
    if wants_json():
        return ok(id=row["id"])
    flash({"kind": "success",
           "zh": "已送出，謝謝你。領袖查看後，可能會給你積分作獎勵。",
           "en": "Sent — thank you. After a leader reads it, you may earn points for it."}, "result")
    return redirect(url_for("feedback_routes.page", sent="1"))


# ── the leader side ─────────────────────────────────────────────────────────

@feedback_routes.get("/leader/feedback")
@leader_required
def leader_feedback():
    st = store()
    users = {u["id"]: u for u in st.list("users")}
    rows = []
    for row in st.list("feedback"):
        rows.append({**row, "who": users.get(row.get("user_id"), {})})
    # still-waiting first, newest at the top of each group
    rows.sort(key=lambda r: (0 if r.get("status") == "new" else 1,
                             str(r.get("created_at") or "")), reverse=False)
    waiting = [row for row in rows if row.get("status") == "new"]
    waiting.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    handled = [row for row in rows if row.get("status") != "new"]
    handled.sort(key=lambda r: str(r.get("decided_at") or r.get("created_at") or ""), reverse=True)
    return render_template(
        "leader/feedback.html", kinds=KINDS, max_points=MAX_POINTS,
        waiting=waiting, handled=handled[:30],
        show_handled=request.args.get("status", "") == "handled",
    )


@feedback_routes.post("/leader/feedback/<feedback_id>")
@leader_required
def leader_feedback_action(feedback_id: str):
    st = store()
    body = request.get_json(silent=True) or request.form.to_dict() or {}
    action = str(body.get("action") or "")
    comment = str(body.get("comment") or "").strip()
    row = st.get("feedback", feedback_id)
    if not row:
        return fail(404, "not_found", "找不到這項意見", "That entry was not found")
    if action not in ("reward", "close", "reopen"):
        return fail(400, "bad_action", "無效的動作", "Invalid action")

    if action == "reopen":
        st.update("feedback", feedback_id, {
            "status": "new", "decided_at": "", "decided_by": "",
        })
        audit(g.user, "feedback_reopen", "feedback", feedback_id, {})
        return _done("已放回待處理", "Moved back to waiting", "feedback_routes.leader_feedback")

    if action == "close":
        st.update("feedback", feedback_id, {
            "status": "closed", "leader_comment": comment,
            "decided_at": now_iso(), "decided_by": g.user["id"],
        })
        audit(g.user, "feedback_close", "feedback", feedback_id, {"comment": comment})
        return _done("已結束處理", "Closed", "feedback_routes.leader_feedback")

    # reward — paid once: a rewarded row can be closed or reopened (reopening
    # keeps the points already paid, and it cannot be rewarded a second time)
    if row.get("status") == "rewarded" or as_int(row.get("points_awarded")) > 0:
        return fail(409, "feedback_paid", "這項意見已經給了積分，不可以重複給分。",
                    "Points were already given for this entry — it cannot be paid twice.")
    points = as_int(body.get("points"))
    if points < 1 or points > MAX_POINTS:
        return fail(400, "feedback_points",
                    f"獎勵積分要在 1 至 {MAX_POINTS} 分之間。",
                    f"Reward points must be between 1 and {MAX_POINTS}.")
    scout = st.get("users", row.get("user_id")) or {}
    if not scout:
        return fail(404, "not_found", "找不到這位童軍", "That scout was not found")
    write_ledger(
        st, user_id=scout["id"], entry_type="feedback", points_delta=points,
        reason_zh=f"意見箱獎勵：{row.get('title', '')}",
        reason_en=f"Feedback reward: {row.get('title', '')}",
        ref_type="feedback", ref_id=feedback_id, created_by=g.user["id"],
    )
    st.update("feedback", feedback_id, {
        "status": "rewarded", "points_awarded": points, "leader_comment": comment,
        "decided_at": now_iso(), "decided_by": g.user["id"],
    })
    audit(g.user, "feedback_reward", "feedback", feedback_id,
          {"points": points, "comment": comment, "scout": scout["id"]})
    return _done(f"已給 {points} 分獎勵", f"Gave {points} points", "feedback_routes.leader_feedback")


def _done(message_zh: str, message_en: str, endpoint: str):
    if wants_json():
        return ok(message_zh=message_zh, message_en=message_en)
    flash({"kind": "success", "zh": message_zh, "en": message_en}, "result")
    return redirect(url_for(endpoint))
