"""
GAME ENGINE — every progression rule lives here, ported line-for-line from the
Node build so both versions behave identically:

  • Points  — the spendable wallet (task points + badge bonus). Scouts only see
              the balance on the 獎品 / rewards page.
  • Badge   — 會員章 is awarded after all five area games are complete; other
              awards use all published tasks. Prerequisites gate later awards.
  • Streak  — consecutive days with at least one completed task (Asia/Hong_Kong).
  • Board   — ranked by badges earned, then tasks done.

Points are always derived from the append-only ledger, so a balance can never
drift and every award is explainable.
"""
from __future__ import annotations

import json

from .schema import TASK_TYPES, patrol_label
from .util import days_between, local_date, now_iso, parse_time, shift_date, today_iso


# ── small helpers ───────────────────────────────────────────────────────────

def as_json(value, fallback):
    """Rows read from a Sheet may carry JSON text; normalise on the way in."""
    if value is None or value == "":
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback
    return fallback


def as_int(value, fallback: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return fallback


def game_areas(badge: dict) -> list[dict] | None:
    """The five-game rule is explicit; other badges retain their task-based rule.

    None means this badge does not use games. An empty list means it *does* use
    games but no playable areas are configured yet — it must not be awarded.
    """
    guide = badge.get("guide") or as_json(badge.get("guide_json"), {}) or {}
    quest = guide.get("quest") or {}
    if quest.get("award_rule") == "five_games":
        return quest.get("areas") or []
    return None


def game_slot_task(area: dict, tasks: list[dict]) -> dict | None:
    """Resolve an area's game anywhere in its badge, not just among its notes.

    The cave teaches item 4 but is physically in area one; M04 is intentionally
    absent from that area's supplemental syllabus rows.
    """
    game = area.get("game") or {}
    code = str(game.get("task_code") or "").strip()
    if not code:
        return None
    return next((task for task in tasks if task.get("code") == code
                 and task.get("status") != "draft"), None)


def strip_answers(task: dict) -> dict:
    """Quizzes must never ship the answer key to the browser."""
    config = json.loads(json.dumps(as_json(task.get("config_json"), {})))
    if isinstance(config.get("questions"), list):
        config["questions"] = [{**q, "answer": None} for q in config["questions"]]
    return config


def public_task(task: dict) -> dict:
    meta = TASK_TYPES.get(task.get("type"), TASK_TYPES["checklist"])
    return {
        "id": task.get("id"),
        "badge_id": task.get("badge_id"),
        "order_index": as_int(task.get("order_index")),
        "code": task.get("code", ""),
        "title_zh": task.get("title_zh", ""), "title_en": task.get("title_en", ""),
        "instruction_zh": task.get("instruction_zh", ""), "instruction_en": task.get("instruction_en", ""),
        "type": task.get("type", "checklist"),
        "points": as_int(task.get("points")),
        "pass_score": as_int(task.get("pass_score")),
        "config_json": strip_answers(task),
        "links": [link for link in (as_json(task.get("config_json"), {}).get("links") or [])
                  if isinstance(link, dict) and link.get("url")],
        "needs_approval": meta["needs_approval"],
        "auto": meta["auto"],
        "icon": meta["icon"],
        "type_label_zh": meta["label_zh"], "type_label_en": meta["label_en"],
    }


def public_badge(badge: dict) -> dict:
    return {
        "id": badge.get("id"), "code": badge.get("code", ""),
        "order_index": as_int(badge.get("order_index")),
        "title_zh": badge.get("title_zh", ""), "title_en": badge.get("title_en", ""),
        "subtitle_zh": badge.get("subtitle_zh", ""), "subtitle_en": badge.get("subtitle_en", ""),
        "desc_zh": badge.get("desc_zh", ""), "desc_en": badge.get("desc_en", ""),
        "emoji": badge.get("emoji", "🎖"), "image_url": badge.get("image_url", ""),
        "color": badge.get("color", "#2c7d4f"),
        "points_reward": as_int(badge.get("points_reward")),
        "prerequisite_badge_ids": as_json(badge.get("prerequisite_badge_ids"), []),
        # 完成指南 (the unit's own wording for each item) rides along with the badge
        "guide": as_json(badge.get("guide_json"), None),
    }


# ── grading ─────────────────────────────────────────────────────────────────

def grade_quiz(task: dict, answers: list) -> dict:
    questions = as_json(task.get("config_json"), {}).get("questions") or []
    if not questions:
        return {"score": 100, "correct": 0, "total": 0}
    correct = 0
    for index, question in enumerate(questions):
        given = answers[index] if index < len(answers) else None
        if given is not None and as_int(given, -1) == as_int(question.get("answer"), -2):
            correct += 1
    return {"score": round(correct / len(questions) * 100), "correct": correct, "total": len(questions)}


def grade_checklist(task: dict, ticks: list) -> dict:
    items = as_json(task.get("config_json"), {}).get("items") or []
    if not items:
        return {"score": 100, "done": 0, "total": 0}
    done = sum(1 for index in range(len(items)) if index < len(ticks) and ticks[index])
    return {"score": round(done / len(items) * 100), "done": done, "total": len(items)}


def evaluate_submission(task: dict, payload: dict, settings: dict) -> dict:
    """What happens when a scout submits? Returns the record fields + feedback."""
    kind = task.get("type")

    if kind == "quiz":
        result = grade_quiz(task, payload.get("answers") or [])
        pass_score = as_int(task.get("pass_score"))
        passed = result["score"] >= pass_score
        return {
            "status": "completed" if passed else "rejected",
            "score": result["score"], "detail": result, "auto_award": passed,
            "feedback_zh": "測驗合格！" if passed else f"再試一次：得分 {result['score']}%（合格 {pass_score}%）",
            "feedback_en": "Quiz passed!" if passed else f"Try again: {result['score']}% (pass mark {pass_score}%)",
        }

    if kind == "checklist":
        result = grade_checklist(task, payload.get("checklist") or [])
        complete = result["total"] == 0 or result["done"] == result["total"]
        # An unfinished checklist is simply unfinished — stored as "rejected"
        # (redoable) rather than "pending", which would block the scout.
        return {
            "status": "completed" if complete else "rejected",
            "score": result["score"], "detail": result, "auto_award": complete,
            "feedback_zh": "全部完成！" if complete else f"還有 {result['total'] - result['done']} 項未完成，請繼續",
            "feedback_en": "All items ticked!" if complete else f"{result['total'] - result['done']} item(s) left — keep going",
        }

    # evidence / reflection / signoff → a leader must confirm
    config = as_json(task.get("config_json"), {})
    min_chars = as_int(config.get("min_chars"))
    if kind == "reflection" and min_chars and len(str(payload.get("reflection_text") or "").strip()) < min_chars:
        return {
            "status": "rejected", "score": 0, "detail": {}, "auto_award": False,
            "feedback_zh": f"字數不足（最少 {min_chars} 字）",
            "feedback_en": f"Too short (minimum {min_chars} characters)",
        }
    return {
        "status": "pending", "score": 0, "detail": {}, "auto_award": False,
        "feedback_zh": "已提交，等待領袖核實", "feedback_en": "Submitted — waiting for a leader to verify",
    }


# ── awarding ────────────────────────────────────────────────────────────────

def task_rewards(task: dict) -> dict:
    return {"points": as_int(task.get("points"))}


def write_ledger(store, *, user_id: str, entry_type: str, points_delta: int,
                 reason_zh: str, reason_en: str, ref_type: str = "",
                 ref_id: str = "", created_by: str = "system") -> dict:
    entry = store.insert("points_ledger", {
        "user_id": user_id, "entry_type": entry_type, "points_delta": points_delta,
        "reason_zh": reason_zh, "reason_en": reason_en, "ref_type": ref_type,
        "ref_id": ref_id, "created_at": now_iso(), "created_by": created_by,
    })
    stats = store.stats_for(user_id)
    store.update("stats", user_id, {
        "points_balance": max(0, as_int(stats.get("points_balance")) + points_delta),
        "updated_at": now_iso(),
    })
    return entry


def award_task_completion(store, *, user: dict, task: dict, badge: dict | None,
                          record: dict | None, awarded_by: str = "auto") -> dict:
    points = task_rewards(task)["points"]
    write_ledger(
        store, user_id=user["id"], entry_type="task", points_delta=points,
        reason_zh=f"完成任務「{task.get('title_zh','')}」",
        reason_en=f"Completed task \"{task.get('title_en','')}\"",
        ref_type="task", ref_id=task.get("id", ""), created_by=awarded_by,
    )
    stats = store.stats_for(user["id"])
    store.update("stats", user["id"], {
        "tasks_done": as_int(stats.get("tasks_done")) + 1, "updated_at": now_iso(),
    })
    if record:
        store.update("progress_records", record["id"], {
            "points_awarded": points, "decided_at": now_iso(), "decided_by": awarded_by,
        })

    events = [{"type": "points", "points": points}]
    badge_result = check_badge_completion(store, user=user, badge=badge)
    if badge_result and badge_result.get("awarded"):
        events.append({"type": "badge", "badge": badge_result["badge"], "points": badge_result["points"]})
    return {"events": events, "badge": badge_result}


def credit_opening_stages(store, *, user: dict, badge: dict | None) -> list[dict]:
    """Stages that are already earned before the scout does anything.

    第 1 關 is the 簡介會 — every new member has been through it, so the moment
    the adventure starts that stage is cleared and its star lights up. Anything
    a leader has already signed off counts too. Idempotent: it only ever fills a
    gap, never overwrites a record the scout or a leader made.
    """
    if not badge:
        return []
    mine = [r for r in store.list("progress_records") if r.get("user_id") == user["id"]]
    credited: list[dict] = []
    for task in sorted([t for t in store.list("tasks")
                        if t.get("badge_id") == badge["id"] and t.get("status") == "published"],
                       key=lambda t: as_int(t.get("order_index"))):
        config = as_json(task.get("config_json"), {})
        if not config.get("start_credited"):
            continue
        if any(r.get("task_id") == task["id"] for r in mine):
            continue
        record = store.insert("progress_records", {
            "user_id": user["id"], "badge_id": task["badge_id"], "task_id": task["id"],
            "attempt_no": 1, "status": "completed", "score": 100,
            "answers_json": None, "checklist_json": None, "evidence_url": "",
            "reflection_text": "", "leader_comment": "", "points_awarded": 0,
            "submitted_at": now_iso(), "decided_at": now_iso(), "decided_by": "opening",
        })
        award_task_completion(store, user=user, task=task, badge=badge,
                              record=record, awarded_by="opening")
        credited.append({**public_task(task), "record_id": record["id"]})
        mine.append(record)
    return credited


def _stage_entry(index: int, item: dict, task: dict, next_taken: bool) -> dict:
    """One gate: its game name from the guide, its state from the task."""
    status = task.get("status", "todo")
    done = status == "completed"
    is_next = False
    if not done and not next_taken:
        is_next, next_taken = True, True
    return {
        "n": index + 1,
        "icon": item.get("stage_icon") or task.get("icon") or "•",
        "name_zh": item.get("stage_zh") or task.get("title_zh", ""),
        "name_en": item.get("stage_en") or task.get("title_en", ""),
        "hint_zh": item.get("stage_hint_zh") or task.get("instruction_zh", ""),
        "hint_en": item.get("stage_hint_en") or task.get("instruction_en", ""),
        "title_zh": item.get("title_zh") or task.get("title_zh", ""),
        "title_en": item.get("title_en") or task.get("title_en", ""),
        "method": item.get("method") or "self",
        "method_note_zh": item.get("method_note_zh") or "",
        "method_note_en": item.get("method_note_en") or "",
        "status": status, "done": done, "next": is_next,
        "pending": status == "pending", "rejected": status == "rejected",
        # a requirement the platform clears by itself when the adventure starts
        # (第 1 關 = the 簡介會): the how-to-play page says so on its card
        "opening": bool(as_json(task.get("config_json"), {}).get("start_credited")),
        "task": task,
    }


def _item_range_label(numbers: list[int]) -> tuple[str, str]:
    """綱要第 1–2 項 / Syllabus items 1–2 — however many items the area holds."""
    if not numbers:
        return "", ""
    if len(numbers) == 1:
        return f"綱要第 {numbers[0]} 項", f"Syllabus item {numbers[0]}"
    return (f"綱要第 {numbers[0]}–{numbers[-1]} 項",
            f"Syllabus items {numbers[0]}–{numbers[-1]}")


def stage_list(store, *, user: dict, badge: dict) -> list[dict]:
    """One gate per area: its game clears the area; optional items are notes.

    The route lives in the badge guide under quest.areas. Game 1 lives in the
    first area while its history content is also syllabus item 4. Locations do
    not need to hold a syllabus item to hold a game.
    """
    # the decorated badge carries `guide`; a raw row carries `guide_json`
    guide = badge.get("guide") or as_json(badge.get("guide_json"), {}) or {}
    items = guide.get("items") or []
    tasks = badge.get("tasks") or []
    areas = (guide.get("quest") or {}).get("areas") or []
    if not areas:
        stages, next_taken = [], False
        for index, task in enumerate(tasks):
            item = items[index] if index < len(items) else {}
            entry = _stage_entry(index, item, task, next_taken)
            next_taken = next_taken or entry["next"]
            stages.append(entry)
        return stages

    stages: list[dict] = []
    next_taken = False
    for index, area in enumerate(areas):
        numbers = [as_int(n) for n in (area.get("items") or []) if as_int(n) > 0]
        members: list[dict] = []
        for number in numbers:
            if not (1 <= number <= len(tasks)):
                continue
            item = items[number - 1] if number - 1 < len(items) else {}
            entry = _stage_entry(number - 1, item, tasks[number - 1], False)
            entry["n"] = number                      # the item's own number
            entry["next"] = False                    # 你在此 stands on the area
            members.append(entry)
        # A location is crossed only by clearing *its game*. Supplemental
        # syllabus rows (if any) do not change the map or the badge counter.
        # The bridge is the one game in two halves: `crossed` means the planks
        # are laid but the leader's 考核 code has not arrived — the area is not
        # counted done, yet the walk may carry on to the next game.
        game = area.get("game") or {}
        holder = game_slot_task(area, tasks)
        game_ready = bool(game.get("ready") and holder)
        done = bool(game_ready and holder["status"] == "completed")
        crossed = bool(game_ready and holder["status"] == "crossed")
        pending = bool(game_ready and holder["status"] == "pending")
        rejected = bool(game_ready and holder["status"] == "rejected")
        status = ("completed" if done else "crossed" if crossed
                  else "pending" if pending else "rejected" if rejected else "todo")
        is_next = False
        if not done and not crossed and not next_taken:
            is_next, next_taken = True, True
        label_zh, label_en = _item_range_label(numbers)
        stages.append({
            "n": index + 1,
            "icon": area.get("icon") or "•",
            "name_zh": area.get("name_zh", ""),
            "name_en": area.get("name_en", ""),
            "hint_zh": area.get("hint_zh", ""),
            "hint_en": area.get("hint_en", ""),
            "title_zh": area.get("name_zh", ""),
            "title_en": area.get("name_en", ""),
            "method": "self", "method_note_zh": "", "method_note_en": "",
            "items_label_zh": label_zh, "items_label_en": label_en,
            "status": status, "done": done, "next": is_next,
            "crossed": crossed,
            "pending": pending, "rejected": rejected,
            "opening": False,
            "done_count": int(done), "total": 1,
            "tasks": members,              # optional syllabus reference in this area
            "task": holder,
            "game_n": as_int(game.get("n")) or index + 1,
            "game_kind": game.get("kind") or "",
            "game_ready": game_ready,
            "game_done": done,
            "game_name_zh": game.get("name_zh", ""), "game_name_en": game.get("name_en", ""),
            "game_blurb_zh": game.get("blurb_zh", ""), "game_blurb_en": game.get("blurb_en", ""),
            "game_task": holder,
        })
    return stages


def check_badge_completion(store, *, user: dict, badge: dict | None) -> dict | None:
    """The five-game badge needs five *distinct, ready* game completions.

    A missing/not-yet-built game blocks the award even when every legacy task
    happens to be done. Other badges retain the published-task rule.
    """
    if not badge:
        return None
    awards = store.list("badge_awards")
    if any(a.get("user_id") == user["id"] and a.get("badge_id") == badge["id"] for a in awards):
        return {"awarded": False, "reason": "already"}

    tasks = [t for t in store.list("tasks")
             if t.get("badge_id") == badge["id"] and t.get("status") == "published"]
    areas = game_areas(badge)
    done_ids = {r.get("task_id") for r in store.list("progress_records")
                if r.get("user_id") == user["id"] and r.get("status") == "completed"}
    if areas is not None:
        # Each location is a separate game; duplicates cannot masquerade as
        # five games. The placeholders stay locked until a leader adds each one.
        slots = [game_slot_task(area, tasks) if (area.get("game") or {}).get("ready")
                 else None for area in areas]
        codes = [task.get("code") for task in slots if task]
        if (len(areas) != 5 or any(task is None for task in slots)
                or len(set(codes)) != 5):
            return {"awarded": False, "reason": "games_unavailable"}
        missing = [task for task in slots if task["id"] not in done_ids]
        if missing:
            return {"awarded": False, "reason": "incomplete", "remaining": len(missing)}
    else:
        if not tasks:
            return {"awarded": False, "reason": "no_tasks"}
        missing = [task for task in tasks if task["id"] not in done_ids]
        if missing:
            return {"awarded": False, "reason": "incomplete", "remaining": len(missing)}

    store.insert("badge_awards", {
        "user_id": user["id"], "badge_id": badge["id"], "awarded_at": now_iso(),
        "awarded_by": "auto", "note": "",
    })
    points = as_int(badge.get("points_reward"))
    if points:
        write_ledger(
            store, user_id=user["id"], entry_type="badge", points_delta=points,
            reason_zh=f"考獲「{badge.get('title_zh','')}」",
            reason_en=f"Earned the \"{badge.get('title_en','')}\" badge",
            ref_type="badge", ref_id=badge["id"], created_by="auto",
        )
    stats = store.stats_for(user["id"])
    store.update("stats", user["id"], {"badges_done": as_int(stats.get("badges_done")) + 1})
    return {"awarded": True, "badge": badge, "points": points}


# ── streaks ─────────────────────────────────────────────────────────────────

def touch_streak(store, user_id: str) -> dict:
    settings = store.settings()
    stats = store.stats_for(user_id)
    if not (settings.get("feature_flags") or {}).get("streaks", True):
        return stats
    today = today_iso()
    gap = days_between(stats.get("last_active_date") or "", today)
    current = as_int(stats.get("streak_current"))
    if gap == 0:
        pass                      # already counted today
    elif gap == 1:
        current += 1
    else:
        current = 1
    patch = {
        "streak_current": current,
        "streak_best": max(current, as_int(stats.get("streak_best"))),
        "last_active_date": today,
        "updated_at": now_iso(),
    }
    store.update("stats", user_id, patch)
    return {**stats, **patch}


# ── leaderboard ─────────────────────────────────────────────────────────────

def leaderboard(store, *, scope: str = "unit", patrol: str = "", period: str = "all",
                current_user_id: str = "", include_hidden: bool = False) -> dict:
    settings = store.settings()
    users = [u for u in store.list("users")
             if u.get("role") == "scout" and u.get("status") == "active"
             and (include_hidden or u.get("show_on_leaderboard", True) is not False)]

    if period == "all":
        since = 0.0
        awards, records = [], []
    else:
        window_days = 7 if period == "week" else 30
        since = parse_time(now_iso()) - window_days * 86400
        awards = store.list("badge_awards")
        records = store.list("progress_records")

    def in_range(value: str) -> bool:
        return parse_time(value) >= since

    rows = []
    for user in users:
        if scope == "patrol" and patrol and user.get("patrol") != patrol:
            continue
        stats = store.stats_for(user["id"])
        if period == "all":
            badges_done = as_int(stats.get("badges_done"))
            tasks_done = as_int(stats.get("tasks_done"))
        else:
            badges_done = sum(1 for a in awards if a.get("user_id") == user["id"] and in_range(a.get("awarded_at")))
            tasks_done = sum(1 for r in records if r.get("user_id") == user["id"]
                             and r.get("status") == "completed"
                             and in_range(r.get("decided_at") or r.get("submitted_at")))
        rows.append({
            "user_id": user["id"],
            "display_name_zh": user.get("display_name_zh", ""),
            "display_name_en": user.get("display_name_en", ""),
            "patrol": user.get("patrol", ""),
            "avatar": user.get("avatar", "🦊"),
            "badges_done": badges_done,
            "tasks_done": tasks_done,
            "streak_current": as_int(stats.get("streak_current")),
            "is_me": user["id"] == current_user_id,
        })

    rows.sort(key=lambda r: (-r["badges_done"], -r["tasks_done"], str(r.get("display_name_en") or "")))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return {"metric": (settings.get("leaderboard_metrics") or ["badges"])[0], "period": period, "scope": scope, "rows": rows}


# ── the scout's own progress ────────────────────────────────────────────────

def progress_for(store, user_id: str) -> dict:
    badges = store.list("badges")
    tasks = store.list("tasks")
    records = store.list("progress_records")
    awards = store.list("badge_awards")
    stats = store.stats_for(user_id)

    mine = [r for r in records if r.get("user_id") == user_id]
    mine.sort(key=lambda r: as_int(r.get("attempt_no"), 1))
    best_by_task: dict[str, dict] = {}
    for record in mine:
        previous = best_by_task.get(record.get("task_id"))
        if (previous is None or record.get("status") == "completed"
                or (record.get("status") == "pending" and previous.get("status") != "completed")):
            best_by_task[record["task_id"]] = record

    awarded_ids = {a.get("badge_id") for a in awards if a.get("user_id") == user_id}
    published = sorted([b for b in badges if b.get("status") == "published"],
                       key=lambda b: as_int(b.get("order_index")))

    result = []
    for badge in published:
        badge_tasks = sorted([t for t in tasks if t.get("badge_id") == badge["id"] and t.get("status") == "published"],
                             key=lambda t: as_int(t.get("order_index")))
        decorated = []
        for task in badge_tasks:
            record = best_by_task.get(task["id"])
            decorated.append({
                **public_task(task),
                "status": (record or {}).get("status") or "todo",
                "score": (record or {}).get("score"),
                "record_id": (record or {}).get("id"),
                "leader_comment": (record or {}).get("leader_comment", ""),
                "submitted_at": (record or {}).get("submitted_at", ""),
                "evidence_url": (record or {}).get("evidence_url", ""),
                "reflection_text": (record or {}).get("reflection_text", ""),
                "checklist_json": (record or {}).get("checklist_json"),
                "answers_json": (record or {}).get("answers_json"),
            })
        done = sum(1 for t in decorated if t["status"] == "completed")
        areas = game_areas(badge)
        if areas is not None:
            # Badge tiles and maps describe *games*, not the old 11-item
            # reference list. An unbuilt game counts as a slot, not as done.
            game_done = sum(1 for area in areas
                            if (area.get("game") or {}).get("ready")
                            and (holder := game_slot_task(area, decorated))
                            and holder["status"] == "completed")
            progress_done, progress_total = game_done, 5
        else:
            progress_done, progress_total = done, len(decorated)
        prereqs = [p for p in as_json(badge.get("prerequisite_badge_ids"), []) if p]
        locked = any(p not in awarded_ids for p in prereqs)
        result.append({
            **public_badge(badge),
            "tasks": decorated,
            "tasks_done": done,                 # legacy / optional syllabus records
            "tasks_total": len(decorated),
            "is_game_badge": areas is not None,
            "progress_done": progress_done,       # what actually earns this badge
            "progress_total": progress_total,
            "percent": round(progress_done / progress_total * 100) if progress_total else 0,
            "earned": badge["id"] in awarded_ids,
            "locked": locked,
            "prereq_titles": [
                {"zh": b.get("title_zh"), "en": b.get("title_en")}
                for b in published if b["id"] in prereqs
            ],
            "prereq_zh": next((b.get("title_zh") for b in published if b["id"] in prereqs), ""),
            "prereq_en": next((b.get("title_en") for b in published if b["id"] in prereqs), ""),
        })

    overall_total = sum(b["tasks_total"] for b in result)
    overall_done = sum(b["tasks_done"] for b in result)
    next_task = find_next_task(result)

    return {
        "stats": {
            "points_balance": as_int(stats.get("points_balance")),
            "tasks_done": as_int(stats.get("tasks_done")),
            "badges_done": as_int(stats.get("badges_done")),
            "streak_current": as_int(stats.get("streak_current")),
            "streak_best": as_int(stats.get("streak_best")),
            "last_active_date": stats.get("last_active_date", ""),
        },
        "overall": {
            "tasks_total": overall_total, "tasks_done": overall_done,
            "percent": round(overall_done / overall_total * 100) if overall_total else 0,
            "badges_total": len(result),
            "badges_earned": sum(1 for b in result if b["earned"]),
            "badges_available": sum(1 for b in result if not b["locked"] and not b["earned"]),
            "next_task": next_task,
            # The award the scout is on right now: the one holding the next task,
            # or — when everything open is waiting on a leader — the first award
            # that is open and not yet earned. Pages use it to mark "you are here".
            "focus_badge_id": ((next_task or {}).get("badge_id")
                               or next((b["id"] for b in result if not b["locked"] and not b["earned"]), None)),
        },
        "badges": result,
    }


def find_next_task(badges: list[dict]) -> dict | None:
    for badge in badges:
        if badge["locked"] or badge["earned"]:
            continue
        if badge.get("is_game_badge"):
            # Never offer an optional syllabus task as the way to earn the
            # badge. Suggest the next *playable* area game instead. A crossed
            # bridge counts too: the scout's next step there is the leader's
            # 考核 code, and /tasks/<id> opens straight onto the assess card.
            for area in game_areas(badge) or []:
                if not (area.get("game") or {}).get("ready"):
                    continue
                task = game_slot_task(area, badge["tasks"])
                if task and task["status"] in {"todo", "rejected", "crossed"}:
                    return {
                        "badge_id": badge["id"],
                        "badge_title_zh": badge["title_zh"], "badge_title_en": badge["title_en"],
                        "task": task,
                    }
            continue
        for task in badge["tasks"]:
            if task["status"] in {"todo", "rejected"}:
                return {
                    "badge_id": badge["id"],
                    "badge_title_zh": badge["title_zh"], "badge_title_en": badge["title_en"],
                    "task": task,
                }
    return None


# ── points + suggestions (home page extras) ─────────────────────────────────

def points_summary(store, user_id: str) -> dict:
    ledger = [row for row in store.list("points_ledger") if row.get("user_id") == user_id]
    stats = store.stats_for(user_id)
    today = today_iso()
    recent = sorted(ledger, key=lambda row: str(row.get("created_at") or ""), reverse=True)[:4]
    return {
        "balance": as_int(stats.get("points_balance")),
        "earned_total": sum(as_int(r.get("points_delta")) for r in ledger if as_int(r.get("points_delta")) > 0),
        "earned_7d": sum(as_int(r.get("points_delta")) for r in ledger
                         if local_date(r.get("created_at")) >= shift_date(today, -6)),
        "earned_30d": sum(as_int(r.get("points_delta")) for r in ledger
                          if local_date(r.get("created_at")) >= shift_date(today, -29)),
        "recent": recent,
    }


def build_suggestions(store, user: dict, progress: dict) -> dict:
    """Automatic nudges from the scout's own progress + leader-authored ideas."""
    auto: list[dict] = []
    overall = progress["overall"]
    next_task = overall.get("next_task")

    if next_task:
        task = next_task["task"]
        auto.append({
            "id": "auto-next-task", "kind": "auto", "emoji": task.get("icon") or "🎯",
            "category": "task",
            "title_zh": f"繼續任務：{task.get('title_zh','')}",
            "title_en": f"Continue: {task.get('title_en','')}",
            "desc_zh": task.get("instruction_zh", ""), "desc_en": task.get("instruction_en", ""),
            "badge_id": next_task["badge_id"], "task_id": task.get("id"),
        })

    pending = sum(1 for r in store.list("progress_records")
                  if r.get("user_id") == user["id"] and r.get("status") == "pending")
    if pending:
        auto.append({
            "id": "auto-pending", "kind": "auto", "emoji": "⏳", "category": "status",
            "title_zh": f"有 {pending} 項提交等待領袖核實",
            "title_en": f"{pending} submission(s) waiting for a leader",
            "desc_zh": "領袖核實之後，這項任務就會完成。",
            "desc_en": "Once a leader has checked it, the task is complete.",
            "route": "badges",
        })

    about_to = [b for b in progress["badges"]
                if not b["locked"] and not b["earned"] and b["progress_total"] and b["progress_done"] == b["progress_total"] - 1]
    if about_to:
        badge = about_to[0]
        unit_zh = "遊戲" if badge.get("is_game_badge") else "任務"
        unit_en = "game" if badge.get("is_game_badge") else "task"
        auto.append({
            "id": "auto-unlock", "kind": "auto", "emoji": "🔓", "category": "status",
            "title_zh": f"「{badge['title_zh']}」只差一個{unit_zh}！",
            "title_en": f"“{badge['title_en']}” is one {unit_en} away!",
            "desc_zh": "完成它就可以考獲這個獎章。",
            "desc_en": "Finish it to earn the award.",
            "route": "badges",
        })

    streak = progress["stats"]["streak_current"]
    if streak:
        auto.append({
            "id": "auto-streak", "kind": "auto", "emoji": "🔥", "category": "status",
            "title_zh": f"連續活躍 {streak} 天 — 保持下去！",
            "title_en": f"{streak}-day streak — keep it going!",
            "desc_zh": "今天完成一個任務就可以延續紀錄。",
            "desc_en": "Complete one task today to extend the run.",
            "route": "badges",
        })

    # Leader-authored ideas are marked so the home page can label them.
    authored = [{**row, "kind": "leader"} for row in store.list("suggestions")
                if row.get("active") is not False]
    authored.sort(key=lambda s: as_int(s.get("order_index")))
    return {"auto": auto, "authored": authored, "all": auto + authored}
