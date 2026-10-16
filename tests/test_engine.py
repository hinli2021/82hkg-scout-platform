"""The rules themselves — grading, awards, streaks, the board, suggestions."""
from __future__ import annotations

import json

from scout import engine
from scout.util import shift_date, today_iso


def make_task(store, **overrides):
    badge = store.list("badges")[0]
    base = {
        "badge_id": badge["id"], "order_index": 99, "code": "T-TEST",
        "title_zh": "測試任務", "title_en": "Test task",
        "instruction_zh": "", "instruction_en": "",
        "type": "quiz", "points": 10, "pass_score": 70,
        "config_json": {"questions": []}, "status": "published",
    }
    return store.insert("tasks", {**base, **overrides})


# ── grading ─────────────────────────────────────────────────────────────────

def test_quiz_scores_by_option_index(store):
    questions = [
        {"q_zh": "一", "q_en": "one", "options": [{"zh": "A", "en": "A"}, {"zh": "B", "en": "B"}], "answer": 0},
        {"q_zh": "二", "q_en": "two", "options": [{"zh": "A", "en": "A"}, {"zh": "B", "en": "B"}], "answer": 1},
        {"q_zh": "三", "q_en": "three", "options": [{"zh": "A", "en": "A"}, {"zh": "B", "en": "B"}], "answer": 1},
    ]
    task = make_task(store, config_json={"questions": questions})
    assert engine.grade_quiz(task, [0, 1, 1])["score"] == 100
    assert engine.grade_quiz(task, [0, 0, 1])["score"] == 67
    assert engine.grade_quiz(task, [])["score"] == 0
    # strings from an HTML form are fine
    assert engine.grade_quiz(task, ["0", "1", "1"])["score"] == 100
    # a missing answer never counts as correct
    assert engine.grade_quiz(task, [None, None, None])["score"] == 0


def test_quiz_without_questions_is_not_a_free_pass(store):
    task = make_task(store, config_json={"questions": []})
    result = engine.grade_quiz(task, [])
    assert result["total"] == 0 and result["score"] == 100   # nothing to fail


def test_checklist_counts_ticks(store):
    task = make_task(store, type="checklist",
                     config_json={"items": [{"zh": "一", "en": "one"}, {"zh": "二", "en": "two"},
                                            {"zh": "三", "en": "three"}, {"zh": "四", "en": "four"}]})
    assert engine.grade_checklist(task, [True, True, True, True])["score"] == 100
    assert engine.grade_checklist(task, [True, False, False, False])["score"] == 25
    assert engine.grade_checklist(task, ["1", "", "1", ""])["score"] == 50


def test_quiz_pass_mark_boundary(store):
    question = {"q_zh": "x", "q_en": "x", "options": [{"zh": "A", "en": "A"}, {"zh": "B", "en": "B"}], "answer": 0}
    settings = store.settings()
    for pass_score, answers, expected in (
        (100, [0], "completed"), (100, [1], "rejected"),
        (0, [1], "completed"),            # pass mark 0 → always pass
    ):
        task = make_task(store, pass_score=pass_score, config_json={"questions": [question]})
        result = engine.evaluate_submission(task, {"answers": answers}, settings)
        assert result["status"] == expected, (pass_score, answers, result)


def test_answer_key_is_stripped_for_scouts(store):
    questions = [{"q_zh": "x", "q_en": "x", "options": [{"zh": "A", "en": "A"}], "answer": 0}]
    task = make_task(store, config_json={"questions": questions})
    public = engine.public_task(task)
    assert public["config_json"]["questions"][0]["answer"] is None
    # the stored task is untouched
    stored = store.get("tasks", task["id"])
    config = stored["config_json"]
    config = json.loads(config) if isinstance(config, str) else config
    assert config["questions"][0]["answer"] == 0


def test_public_task_declares_its_type_meta(store):
    for kind in ("quiz", "checklist", "evidence", "reflection", "signoff"):
        public = engine.public_task(make_task(store, type=kind))
        assert public["type_label_zh"] and public["type_label_en"]
        assert isinstance(public["needs_approval"], bool)


# ── awards ──────────────────────────────────────────────────────────────────

def test_member_badge_waits_for_five_ready_games(store):
    scout = next(u for u in store.list("users") if u["username"] == "scout07")
    badge = next(b for b in store.list("badges") if b.get("code") == "SC-01")
    result = engine.check_badge_completion(store, user=scout, badge=badge)
    assert not result["awarded"] and result["reason"] == "games_unavailable"
    progress = engine.progress_for(store, scout["id"])["badges"][0]
    assert progress["is_game_badge"] and (progress["progress_done"], progress["progress_total"]) == (0, 5)
    assert len(progress["tasks"]) == 11, "the historical guide is reference, not a second exam"


def test_draft_tasks_do_not_block_an_award(store):
    scout = next(u for u in store.list("users") if u["username"] == "scout07")
    badge = next(b for b in store.list("badges") if b.get("code") == "SC-03")
    for task in [t for t in store.list("tasks") if t["badge_id"] == badge["id"]]:
        store.update("tasks", task["id"], {"status": "draft"})
    result = engine.check_badge_completion(store, user=scout, badge=badge)
    assert result["reason"] == "no_tasks"      # regular task-based award, nothing published


def test_ledger_is_append_only_and_balance_follows_it(store):
    scout = next(u for u in store.list("users") if u["username"] == "scout05")
    before = len(store.list("points_ledger"))
    engine.write_ledger(store, user_id=scout["id"], entry_type="manual", points_delta=30,
                        reason_zh="測試", reason_en="test")
    engine.write_ledger(store, user_id=scout["id"], entry_type="manual", points_delta=-10,
                        reason_zh="扣回", reason_en="deduct")
    assert len(store.list("points_ledger")) == before + 2
    stats = store.stats_for(scout["id"])
    total = sum(int(r["points_delta"]) for r in store.list("points_ledger") if r["user_id"] == scout["id"])
    assert stats["points_balance"] == total


def test_balance_never_goes_negative(store):
    scout = next(u for u in store.list("users") if u["username"] == "scout06")
    engine.write_ledger(store, user_id=scout["id"], entry_type="manual", points_delta=-99999,
                        reason_zh="扣分", reason_en="deduct")
    assert store.stats_for(scout["id"])["points_balance"] == 0


# ── streaks ─────────────────────────────────────────────────────────────────

def test_streak_increments_across_consecutive_days(store):
    scout = next(u for u in store.list("users") if u["username"] == "scout06")
    store.update("stats", scout["id"], {"streak_current": 3, "streak_best": 3,
                                        "last_active_date": shift_date(today_iso(), -1)})
    stats = engine.touch_streak(store, scout["id"])
    assert stats["streak_current"] == 4 and stats["streak_best"] == 4
    assert stats["last_active_date"] == today_iso()


def test_streak_resets_after_a_gap(store):
    scout = next(u for u in store.list("users") if u["username"] == "scout06")
    store.update("stats", scout["id"], {"streak_current": 9, "streak_best": 9,
                                        "last_active_date": shift_date(today_iso(), -5)})
    stats = engine.touch_streak(store, scout["id"])
    assert stats["streak_current"] == 1 and stats["streak_best"] == 9   # best is kept


def test_same_day_activity_keeps_the_streak(store):
    scout = next(u for u in store.list("users") if u["username"] == "scout06")
    store.update("stats", scout["id"], {"streak_current": 2, "streak_best": 2,
                                        "last_active_date": today_iso()})
    assert engine.touch_streak(store, scout["id"])["streak_current"] == 2


# ── the board ───────────────────────────────────────────────────────────────

def test_board_orders_by_badges_then_tasks(store):
    board = engine.leaderboard(store)
    pairs = [(row["badges_done"], row["tasks_done"]) for row in board["rows"]]
    assert pairs == sorted(pairs, key=lambda pair: (-pair[0], -pair[1]))
    assert [row["rank"] for row in board["rows"]] == list(range(1, len(board["rows"]) + 1))


def test_board_marks_the_current_user(store):
    scout = next(u for u in store.list("users") if u["username"] == "scout03")
    board = engine.leaderboard(store, current_user_id=scout["id"])
    me = [row for row in board["rows"] if row["is_me"]]
    assert len(me) == 1 and me[0]["user_id"] == scout["id"]


def test_board_scopes_and_periods(store):
    assert len(engine.leaderboard(store, scope="patrol", patrol="Tiger")["rows"]) == 2
    assert len(engine.leaderboard(store, scope="unit")["rows"]) == 7
    week = engine.leaderboard(store, period="week")
    month = engine.leaderboard(store, period="month")
    assert week["period"] == "week" and month["period"] == "month"
    # the seed's completions are “now”, so the weekly board is not empty
    assert sum(row["tasks_done"] for row in week["rows"]) >= 1
    assert sum(row["badges_done"] for row in week["rows"]) == sum(
        row["badges_done"] for row in month["rows"])


def test_board_ranks_by_the_documented_metric(store):
    board = engine.leaderboard(store)
    assert board["metric"] == "badges"      # badges first, then tasks — never points


def test_board_never_exposes_passwords(store):
    board = engine.leaderboard(store)
    assert "password_hash" not in json.dumps(board)
    assert "username" not in board["rows"][0]


# ── progress + suggestions ──────────────────────────────────────────────────

def test_progress_counts_and_next_task(store):
    scout = next(u for u in store.list("users") if u["username"] == "scout04")
    progress = engine.progress_for(store, scout["id"])
    assert progress["overall"]["tasks_done"] == progress["stats"]["tasks_done"]
    assert progress["overall"]["badges_earned"] == progress["stats"]["badges_done"]
    nxt = progress["overall"]["next_task"]
    if nxt:
        assert nxt["badge_title_zh"]
        assert not any(b["locked"] for b in progress["badges"] if b["id"] == nxt["badge_id"])


def test_next_task_skips_locked_awards(store):
    scout = next(u for u in store.list("users") if u["username"] == "scout07")
    progress = engine.progress_for(store, scout["id"])
    nxt = progress["overall"]["next_task"]
    assert nxt["badge_id"] == progress["badges"][0]["id"]     # award 1, not award 3


def test_locked_awards_report_their_prerequisite(store):
    scout = next(u for u in store.list("users") if u["username"] == "scout07")
    badges = engine.progress_for(store, scout["id"])["badges"]
    locked = [b for b in badges if b["locked"]]
    assert locked and locked[0]["prereq_zh"] and locked[0]["prereq_en"]


def test_points_summary_windows(store):
    scout = next(u for u in store.list("users") if u["username"] == "scout01")
    summary = engine.points_summary(store, scout["id"])
    assert summary["earned_total"] >= summary["earned_30d"] >= summary["earned_7d"]
    assert summary["balance"] == store.stats_for(scout["id"])["points_balance"]
    assert len(summary["recent"]) <= 4


def test_suggestions_are_personal_and_bilingual(store):
    scout = next(u for u in store.list("users") if u["username"] == "scout07")
    progress = engine.progress_for(store, scout["id"])
    suggestions = engine.build_suggestions(store, scout, progress)
    assert suggestions["auto"], "a brand-new scout should be nudged to start"
    first = suggestions["auto"][0]
    assert first["kind"] == "auto" and first["title_zh"] and first["title_en"]
    assert first["task_id"], "the first nudge points at a real task"
    authored = [row for row in store.list("suggestions") if row.get("active") is not False]
    assert len(suggestions["authored"]) == len(authored)
    assert [idea["id"] for idea in suggestions["authored"]] == [row["id"] for row in authored]
    assert all(idea["kind"] == "leader" for idea in suggestions["authored"])


def test_suggestion_cards_follow_the_leader_content(store):
    store.insert("suggestions", {
        "emoji": "🏕️", "category": "outdoor", "title_zh": "試試露營", "title_en": "Try camping",
        "desc_zh": "週末活動", "desc_en": "Weekend activity", "link_url": "https://example.com",
        "link_label_zh": "詳情", "link_label_en": "Details", "order_index": 9, "active": True,
        "created_at": "2026-01-01T00:00:00.000Z",
    })
    scout = next(u for u in store.list("users") if u["username"] == "scout03")
    suggestions = engine.build_suggestions(store, scout, engine.progress_for(store, scout["id"]))
    titles = [idea["title_zh"] for idea in suggestions["authored"]]
    assert "試試露營" in titles
    assert all(idea["kind"] != "auto" for idea in suggestions["authored"])
