"""每日挑戰 — the daily puzzle: open it, finish it, earn a few points.

One game a day, the same board for everybody, chosen and built by
`scout.daily` from the Hong Kong date. The page hands the browser the board
and a signed ticket; finishing posts the ticket and the clock back, and the
points are paid once a day through the ordinary ledger (so the 龍虎榜 and the
scout's balance pick them up without any new plumbing).
"""
from __future__ import annotations

import json

from flask import Blueprint, g, render_template, request, url_for
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .. import daily
from ..engine import as_int, write_ledger
from ..util import now_iso
from .helpers import audit, fail, ok, store, wants_json
from ..auth import scout_required

daily_routes = Blueprint("daily_routes", __name__)


def _signer() -> URLSafeTimedSerializer:
    from flask import current_app
    return URLSafeTimedSerializer(current_app.secret_key, salt="daily-puzzle-v1")


def _ticket(day: str, kind: str) -> str:
    return _signer().dumps({"d": day, "k": kind, "u": g.user["id"]})


def _claimed(st, user_id: str, day: str) -> dict | None:
    """The ledger row that says today's points are already paid."""
    key = daily.ref_id(day)
    for row in st.list("points_ledger"):
        if (row.get("user_id") == user_id and row.get("entry_type") == "daily"
                and row.get("ref_id") == key):
            return row
    return None


def _streak(st, user_id: str, day: str) -> int:
    """How many days in a row (ending today or yesterday) this scout has played."""
    from datetime import date, timedelta

    played = {str(row.get("ref_id", "")).replace("daily:", "")
              for row in st.list("points_ledger")
              if row.get("user_id") == user_id and row.get("entry_type") == "daily"}
    here = date.fromisoformat(day)
    run = 0
    probe = here if day in played else here - timedelta(days=1)
    while probe.isoformat() in played:
        run += 1
        probe -= timedelta(days=1)
    return run


@daily_routes.get("/daily")
@scout_required
def daily_page():
    st = store()
    today = daily.today_key()
    today_puzzle = daily.puzzle()
    day = today_puzzle["date"]
    claimed = _claimed(st, g.user["id"], day)
    played_today = claimed is not None

    stats = st.stats_for(g.user["id"])
    config = {
        "date": day,
        "kind": today_puzzle["kind"],
        "meta": today_puzzle["meta"],
        "board": today_puzzle["board"],
        "ticket": _ticket(day, today_puzzle["kind"]),
        "submit_url": url_for("daily_routes.daily_finish"),
        "points": {"done": daily.POINTS_DONE, "fast": daily.POINTS_FAST},
        "fast_ms": daily.FAST_MS,
        "already": played_today,
        "language": (request.cookies.get("scout_lang") or "zh"),
    }

    # the last week, newest first — what was played and what it paid
    from datetime import timedelta
    from datetime import date as _date

    history = []
    for offset in range(7):
        probe = (_date.fromisoformat(day) - timedelta(days=offset)).isoformat()
        row = _claimed(st, g.user["id"], probe)
        history.append({
            "date": probe,
            "points": as_int((row or {}).get("points_delta")),
            "done": row is not None,
            "today": probe == day,
        })

    return render_template(
        "scout/daily.html",
        config=config,
        scene_json=json.dumps(config, ensure_ascii=False),
        meta=today_puzzle["meta"],
        points={"done": daily.POINTS_DONE, "fast": daily.POINTS_FAST},
        fast_ms=daily.FAST_MS,
        played=played_today,
        last_points=as_int((claimed or {}).get("points_delta")),
        # 頂欄那粒火要與主頁一致：用同一個 streak（stats 的活躍連續天數）；
        # 每日遊戲自己的連續紀錄，留在下面的「這一個星期」顯示。
        streak=as_int(stats.get("streak_current")),
        daily_streak=_streak(st, g.user["id"], day),
        balance=as_int(stats.get("points_balance")),
        history=history,
        games=daily.GAMES,
        order=daily.ORDER,
    )


@daily_routes.post("/daily/finish")
@scout_required
def daily_finish():
    """Pay for today's puzzle — once. The ticket proves which board it was."""
    st = store()
    body = request.get_json(silent=True) or {}
    try:
        data = _signer().loads(str(body.get("ticket") or ""), max_age=12 * 3600)
    except BadSignature:
        return fail(400, "daily_ticket", "這一局的門票已失效，請重新整理再玩。",
                    "This game's ticket expired — reload and play again.")
    if not isinstance(data, dict) or data.get("u") != g.user["id"]:
        return fail(400, "daily_ticket", "這一局不屬於這個帳戶。", "This game belongs to another account.")

    day = str(data.get("d") or "")
    if day != daily.today_key():
        return fail(409, "daily_closed", "這一天的挑戰已完結，明天再來。",
                    "That day's challenge is over — come back tomorrow.")
    today_puzzle = daily.puzzle()
    if data.get("k") != today_puzzle["kind"]:
        return fail(409, "daily_kind", "棋盤與今天的不符，請重新整理。", "That board is not today's.")

    elapsed = as_int(body.get("elapsed_ms"))
    if elapsed < daily.MIN_MS:
        # not an accusation — a clock that never started looks exactly like this
        return fail(400, "daily_clock", "時間好像沒有開始計，請重新整理再玩一次。",
                    "The clock does not look started — reload and play once more.")
    if elapsed > daily.MAX_MS:
        return fail(400, "daily_clock", "這一局太久了，請重新開始。", "That took too long — start again.")

    if _claimed(st, g.user["id"], day):
        return ok(points=0, balance=as_int(st.stats_for(g.user["id"]).get("points_balance")),
                  already=True, points_max=daily.POINTS_FAST)

    points = daily.points_for(elapsed)
    meta = today_puzzle["meta"]
    write_ledger(
        st, user_id=g.user["id"], entry_type="daily", points_delta=points,
        reason_zh=f"每日挑戰：{meta['name_zh']}",
        reason_en=f"Daily challenge: {meta['name_en']}",
        ref_type="daily", ref_id=daily.ref_id(day), created_by="auto",
    )
    from ..gacha import enabled, grant_pack
    pack = False
    if enabled(st.settings_cached()):
        pack = grant_pack(
            st, g.user, key=daily.ref_id(day), kind="standard", source="daily",
            ref_id=daily.ref_id(day),
            reason_zh=f"完成每日挑戰：{meta['name_zh']}",
            reason_en=f"Finished the daily challenge: {meta['name_en']}",
        )
    audit(g.user, "daily_finish", "daily", day, {"kind": today_puzzle["kind"], "points": points,
                                                 "elapsed_ms": elapsed})
    stats_row = st.stats_for(g.user["id"])
    balance = as_int(stats_row.get("points_balance"))
    return ok(points=points, balance=balance, elapsed_ms=elapsed, pack=pack,
              # 同一個 streak 定義，回應與頂欄、主頁一致
              streak=as_int(stats_row.get("streak_current")),
              daily_streak=_streak(st, g.user["id"], day), already=False,
              points_max=daily.POINTS_FAST, finished_at=now_iso())
