"""
The leader console — /leader/… pages, one per job:

    /leader                  overview + six quick actions
    /leader/content          badges & tasks (the 進度性獎章 ladder)
    /leader/review           approve / reject / send back scout submissions
    /leader/accounts         create scouts, reset passwords, CSV import & export
    /leader/announcements    公告
    /leader/rewards          獎品 catalogue (points)
    /leader/settings         unit name, patrols, feature switches
    /leader/audit            the safety net: who changed what, and when
"""
from __future__ import annotations

import copy
import json

from flask import Blueprint, Response, abort, flash, g, redirect, render_template, request, url_for

from .. import mailer
from ..auth import create_reset_token, leader_required, public_user, reset_password as clear_password
from ..content import cave_adventure
from ..engine import (
    as_json, award_task_completion, check_badge_completion, leaderboard, progress_for,
    public_badge, public_task, write_ledger,
)
from ..schema import DEFAULT_SETTINGS, PATROL_LABELS, TASK_TYPES, patrol_label
from ..util import generate_password, hash_password, new_id, now_iso, parse_time, slug, to_bool
from .helpers import audit, checkbox, fail, field_list, ok, parse_csv, sanitize, store, to_csv, wants_json

leader_routes = Blueprint("leader_routes", __name__)


def _redirect_default():
    return redirect(url_for("leader_routes.overview"))


def _done(message_zh: str, message_en: str, endpoint: str, **values):
    """A leader action from a plain HTML form: return to the page it came from."""
    if wants_json():
        return ok(message_zh=message_zh, message_en=message_en)
    return redirect(url_for(endpoint, **values))


def _setting_switch(key: str) -> None:
    store().save_setting(key, checkbox(key))


# ══ overview ═══════════════════════════════════════════════════════════════

def _overview_context() -> dict:
    st = store()
    users = st.list("users")
    scouts = [u for u in users if u.get("role") == "scout"]
    records = st.list("progress_records")
    resets = st.list("password_reset_requests")
    pending = [r for r in records if r.get("status") == "pending"]
    badges = st.list("badges")
    tasks = st.list("tasks")
    awards = st.list("badge_awards")

    tasks_by_id = {t["id"]: t for t in tasks}
    users_by_id = {u["id"]: u for u in users}
    badges_by_id = {b["id"]: b for b in badges}

    for row in pending:
        row["_who"] = users_by_id.get(row.get("user_id"), {})
        row["_task"] = tasks_by_id.get(row.get("task_id"), {})
        row["_badge"] = badges_by_id.get(row.get("badge_id"), {})

    patrol_rows = []
    for patrol in (st.settings_cached().get("patrols") or ["Tiger", "Otter", "Seagull"]):
        members = [u for u in scouts if u.get("patrol") == patrol]
        patrol_rows.append({
            "patrol": patrol, "label": patrol_label(patrol), "count": len(members),
            "badges": sum(st.stats_for(u["id"]).get("badges_done", 0) for u in members) if members else 0,
            "tasks": sum(st.stats_for(u["id"]).get("tasks_done", 0) for u in members) if members else 0,
        })

    recent_activity = sorted(
        [r for r in records if r.get("decided_at")],
        key=lambda r: str(r.get("decided_at") or ""), reverse=True,
    )[:8]
    for row in recent_activity:
        row["_who"] = users_by_id.get(row.get("user_id"), {})
        row["_task"] = tasks_by_id.get(row.get("task_id"), {})

    return {
        "counts": {
            "scouts": len(scouts), "badges": len([b for b in badges if b.get("status") == "published"]),
            "tasks": len([t for t in tasks if t.get("status") == "published"]),
            "pending": len(pending), "awards": len(awards),
            "resets": len([r for r in resets if r.get("status") == "pending"]),
            "drafts": len([b for b in badges if b.get("status") != "published"]),
        },
        "pending": pending[:6],
        "patrols": patrol_rows,
        "recent_activity": recent_activity,
        "reset_requests": [r for r in resets if r.get("status") == "pending"],
        "quick_actions": [
            {"emoji": "✅", "zh": "審批提交", "en": "Review submissions", "endpoint": "leader_routes.review",
             "badge": len(pending)},
            {"emoji": "🔑", "zh": "重設密碼申請", "en": "Password requests", "endpoint": "leader_routes.accounts",
             "badge": len([r for r in resets if r.get("status") == "pending"])},
            {"emoji": "➕", "zh": "新增獎章任務", "en": "Add badge / task", "endpoint": "leader_routes.content"},
            {"emoji": "🧑‍🤝‍🧑", "zh": "開設童軍帳戶", "en": "Create scout account", "endpoint": "leader_routes.accounts"},
            {"emoji": "📣", "zh": "發公告", "en": "Post a notice", "endpoint": "leader_routes.announcements"},
        ],
        # 快速連結 only lists what is switched on — see 設定 → 功能開關
        "quick_extras": ([{"emoji": "🎁", "zh": "獎品目錄", "en": "Rewards catalogue",
                           "endpoint": "leader_routes.rewards"}]
                         if (st.settings_cached().get("feature_flags") or {}).get("redeem", False) else []),
    }


@leader_routes.get("/leader")
@leader_required
def overview():
    return render_template("leader/overview.html", **_overview_context())


# ══ content: badges & tasks ════════════════════════════════════════════════

def _content_context() -> dict:
    st = store()
    badges = sorted(st.list("badges"), key=lambda b: (int(float(b.get("order_index") or 0)), str(b.get("code") or "")))
    tasks = st.list("tasks")
    settings = st.settings_cached()
    for badge in badges:
        badge["_tasks"] = sorted([t for t in tasks if t.get("badge_id") == badge["id"]],
                                 key=lambda t: int(float(t.get("order_index") or 0)))
        quest = (as_json(badge.get("guide_json"), {}) or {}).get("quest") or {}
        if quest.get("award_rule") == "five_games":
            badge["_game_areas"] = quest.get("areas") or []
            reference_codes = {f"M{n:02}" for n in range(1, 12)}
            codes = [t.get("code") for t in badge["_tasks"]]
            assigned_codes = {(a.get("game") or {}).get("task_code")
                              for a in badge["_game_areas"]}
            played_ids = {r.get("task_id") for r in st.list("progress_records")}
            badge["_game_candidates"] = [
                t for t in badge["_tasks"]
                if t.get("status") == "published" and t.get("code")
                and t["code"] not in reference_codes and codes.count(t["code"]) == 1
                and (t["id"] not in played_ids or t["code"] in assigned_codes)
            ]
    return {"badges": badges, "task_types": TASK_TYPES, "settings": settings,
            "next_order": len(badges) + 1}


@leader_routes.get("/leader/content")
@leader_required
def content():
    return render_template("leader/content.html", **_content_context())


@leader_routes.post("/leader/content/badges")
@leader_required
def create_badge():
    st = store()
    body = sanitize("badges", {**request.form.to_dict(), **({"prerequisite_badge_ids": json.dumps(field_list(request.form.getlist("prerequisite_badge_ids")))} if request.form.getlist("prerequisite_badge_ids") else {})})
    body.pop("updated_at", None)
    record = st.insert("badges", {
        **body,
        "section": body.get("section") or "scout",
        "status": body.get("status") or "draft",
        "order_index": body.get("order_index") or len(st.list("badges")) + 1,
        "emoji": body.get("emoji") or "🎖",
        "color": body.get("color") or "#2c7d4f",
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    audit(g.user, "create_badge", "badges", record["id"], {"code": record.get("code")})
    return _done("已新增獎章", "Badge added", "leader_routes.content")


@leader_routes.post("/leader/content/badges/<badge_id>")
@leader_required
def update_badge(badge_id: str):
    st = store()
    existing = st.get("badges", badge_id)
    if not existing:
        abort(404)
    body = sanitize("badges", request.form.to_dict() if request.form else None, partial=True)
    if (as_json(existing.get("guide_json"), {}) or {}).get("quest", {}).get("award_rule") == "five_games":
        if body.get("code", existing.get("code")) != existing.get("code"):
            return fail(409, "game_badge_code", "不能更改五區遊戲獎章的代號",
                        "The game badge's code is fixed")
        body.pop("guide_json", None)  # edit games only via the validated area forms
    prereqs = request.form.getlist("prerequisite_badge_ids") if request.form else None
    if prereqs is not None:
        body["prerequisite_badge_ids"] = prereqs
    record = st.update("badges", badge_id, body)
    if not record:
        abort(404)
    audit(g.user, "update_badge", "badges", badge_id, {})
    return _done("已更新獎章", "Badge updated", "leader_routes.content")


@leader_routes.post("/leader/content/badges/<badge_id>/games/<int:area_n>")
@leader_required
def configure_area_game(badge_id: str, area_n: int):
    """A leader can name the five places and attach a NEW task to games 2–5.

    The cave in location 1 is structural, not an optional paper that can be
    replaced. A game is only live after a separately authored, published task
    is explicitly linked here. No task or progress is created by this form.
    """
    st = store()
    badge = st.get("badges", badge_id)
    if not badge:
        abort(404)
    guide = copy.deepcopy(as_json(badge.get("guide_json"), {}) or {})
    quest = guide.get("quest") or {}
    areas = quest.get("areas") or []
    if badge.get("code") != "SC-01" or quest.get("award_rule") != "five_games" or len(areas) != 5:
        return fail(400, "not_game_badge", "這個獎章沒有五區遊戲", "This award has no five-game map")
    if not 1 <= area_n <= 5:
        return fail(400, "bad_area", "請選擇第一至第五區", "Choose a location from one to five")
    area = areas[area_n - 1]
    if area_n == 1 and (area.get("game") or {}).get("task_code") != "M04":
        return fail(409, "cave_missing", "第一區的山洞設定有誤", "The first cave is missing")
    task_id = str(request.form.get("task_id") or "").strip() if area_n > 1 else ""
    task = st.get("tasks", task_id) if task_id else None
    old_code = (area.get("game") or {}).get("task_code")
    if area_n > 1 and task_id and not task:
        return fail(400, "bad_task", "找不到這項遊戲任務", "That game task was not found")
    if task:
        code = str(task.get("code") or "").strip()
        siblings = [t for t in st.list("tasks") if t.get("badge_id") == badge_id]
        if (task.get("badge_id") != badge_id or task.get("status") != "published"
                or not code or code in {f"M{n:02}" for n in range(1, 12)}
                or sum(t.get("code") == code for t in siblings) != 1):
            return fail(400, "bad_task", "須選擇本獎章新建、已發佈而代號獨一的任務",
                        "Choose a new, published task of this award with a unique code")
        if any((other.get("game") or {}).get("task_code") == code
               for i, other in enumerate(areas) if i != area_n - 1):
            return fail(409, "duplicate_game", "每一區必須使用不同的遊戲", "Each area needs a different game")
        config = as_json(task.get("config_json"), {}) or {}
        if ((task.get("type") == "quiz" and not config.get("questions"))
                or (task.get("type") == "checklist" and not config.get("items"))
                or not task.get("title_zh") or not task.get("title_en")
                or not task.get("instruction_zh") or not task.get("instruction_en")):
            return fail(400, "empty_game", "請先填好遊戲題目及中英文名稱",
                        "Add playable content and both language titles first")
        if old_code != code and any(r.get("task_id") == task_id for r in st.list("progress_records")):
            return fail(409, "old_progress", "這項任務已有童軍進度，不能當作新遊戲",
                        "This task has prior progress; use a new task for a new game")
    current_code = (area.get("game") or {}).get("task_code") if area_n > 1 else ""
    current = next((t for t in st.list("tasks") if t.get("code") == current_code), None) if current_code else None
    if ((area.get("game") or {}).get("ready") and area_n > 1
            and str(request.form.get("replace") or "") != "1"
            and task_id != (current["id"] if current else "")):
        return fail(409, "area_taken",
                    f"第 {area_n} 區已經有遊戲（{(area.get('game') or {}).get('name_zh')}）。要更換，請先勾選「確定取代這一區的遊戲」。",
                    f"Area {area_n} already has a game. To swap it, tick “replace this area's game”.")
    if area_n > 1 and old_code != (str(task.get("code")) if task else "") and old_code:
        old_task = next((t for t in st.list("tasks")
                         if t.get("badge_id") == badge_id and t.get("code") == old_code), None)
        if old_task and any(r.get("task_id") == old_task["id"] for r in st.list("progress_records")):
            return fail(409, "game_in_progress", "已有童軍玩過本區遊戲，不能更換遊戲任務",
                        "Scouts have played this game; its task cannot be replaced")

    for lang in ("zh", "en"):
        name = (request.form.get(f"area_name_{lang}") or "").strip()
        if name:
            area[f"name_{lang}"] = name[:120]
    if area_n > 1:
        game = dict(area.get("game") or {})
        game.update(n=area_n, kind="task" if task else "", ready=bool(task),
                    task_code=str(task["code"]) if task else "")
        for lang in ("zh", "en"):
            name = (request.form.get(f"game_name_{lang}") or "").strip()
            blurb = (request.form.get(f"game_blurb_{lang}") or "").strip()
            game[f"name_{lang}"] = (name or (task.get(f"title_{lang}") if task else
                                       ("即將推出" if lang == "zh" else "Coming soon")))[:120]
            game[f"blurb_{lang}"] = (blurb or (task.get(f"instruction_{lang}") if task else
                                            ("內容待領袖提供。" if lang == "zh" else
                                             "The leader will add this game later.")))[:600]
        area["game"] = game
        if area_n == 2:
            area["hint_zh"] = game["blurb_zh"] if task else "穿過迷霧，尋找下一個遊戲。領袖稍後會公布這裡的考驗。"
            area["hint_en"] = game["blurb_en"] if task else "Beyond the mist, the leader will reveal this area's game later."
    st.update("badges", badge_id, {"guide_json": guide})
    audit(g.user, "configure_game", "badges", badge_id,
          {"area": area_n, "task_code": (task or {}).get("code") or ""})
    return _done("已更新區域及遊戲", "Location and game updated", "leader_routes.content")


@leader_routes.post("/leader/content/badges/<badge_id>/delete")
@leader_required
def delete_badge(badge_id: str):
    st = store()
    for task in [t for t in st.list("tasks") if t.get("badge_id") == badge_id]:
        st.remove("tasks", task["id"])
    st.remove("badges", badge_id)
    audit(g.user, "delete_badge", "badges", badge_id, {})
    return _done("已刪除獎章（及其任務）", "Badge deleted (with its tasks)", "leader_routes.content")


@leader_routes.post("/leader/content/badges/<badge_id>/move")
@leader_required
def move_badge(badge_id: str):
    """↑ / ↓ in the 進度性獎章 ladder — order matters, it is the pathway."""
    st = store()
    direction = request.form.get("direction") or (request.get_json(silent=True) or {}).get("direction") or "up"
    badges = sorted(st.list("badges"), key=lambda b: (int(float(b.get("order_index") or 0)), str(b.get("code") or "")))
    index = next((i for i, b in enumerate(badges) if b["id"] == badge_id), -1)
    if index < 0:
        abort(404)
    swap = index - 1 if direction == "up" else index + 1
    if 0 <= swap < len(badges):
        a, b = badges[index], badges[swap]
        st.update("badges", a["id"], {"order_index": int(float(b.get("order_index") or 0)) or swap + 1})
        st.update("badges", b["id"], {"order_index": int(float(a.get("order_index") or 0)) or index + 1})
    return _done("已更新次序", "Order updated", "leader_routes.content")


@leader_routes.post("/leader/content/tasks")
@leader_required
def create_task():
    st = store()
    body = sanitize("tasks", request.form.to_dict())
    body.pop("updated_at", None)
    badge_id = body.get("badge_id") or request.form.get("badge_id")
    if not badge_id or not st.get("badges", badge_id):
        return fail(400, "bad_badge", "請先選擇獎章", "Pick a badge first")
    siblings = [t for t in st.list("tasks") if t.get("badge_id") == badge_id]
    # The map refers to a stable task code; make one for newly created tasks
    # so a leader can attach a game without editing JSON or choosing an ID.
    body["code"] = str(body.get("code") or f"G-{new_id()[:12]}").strip()
    if any(t.get("code") == body["code"] for t in siblings):
        return fail(400, "duplicate_code", "任務代號已存在", "This task code already exists")
    task_type = body.get("type") or "checklist"
    config = body.get("config_json") or {}
    if request.form and not request.form.get("config_json"):
        config = _config_from_form(task_type, request.form, {}) or {}
    record = st.insert("tasks", {
        **body, "badge_id": badge_id,
        "order_index": body.get("order_index") or len(siblings) + 1,
        "type": task_type,
        "status": body.get("status") or "draft",
        "config_json": config,
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    audit(g.user, "create_task", "tasks", record["id"], {"badge_id": badge_id})
    return _done("已新增任務", "Task added", "leader_routes.content")


@leader_routes.get("/leader/content/tasks/<task_id>")
@leader_required
def edit_task(task_id: str):
    st = store()
    task = st.get("tasks", task_id)
    if not task:
        abort(404)
    badge = st.get("badges", task.get("badge_id"))
    return render_template("leader/task_editor.html", task=public_task(task), raw=task,
                           raw_config=as_json(task.get("config_json"), {}), badge=badge,
                           cave_task=_is_editable_cave(task, badge), task_types=TASK_TYPES)


def _is_editable_cave(task: dict, badge: dict | None) -> bool:
    """Only game 1's M04 bank gets the stable-ID cave question editor."""
    if not badge or badge.get("code") != "SC-01" or task.get("code") != "M04" or task.get("type") != "quiz":
        return False
    areas = ((as_json(badge.get("guide_json"), {}) or {}).get("quest") or {}).get("areas") or []
    game = (areas[0].get("game") or {}) if areas else {}
    return (game.get("ready") and game.get("kind") == "cave"
            and game.get("task_code") == task.get("code"))


def _cave_editor_data(task_id: str):
    st = store()
    task = st.get("tasks", task_id)
    badge = st.get("badges", task.get("badge_id")) if task else None
    if not task or not _is_editable_cave(task, badge):
        abort(404)
    config = as_json(task.get("config_json"), {}) or {}
    questions = config.get("questions") or []
    adventure = cave_adventure()
    groups = adventure.get("groups") or []
    ids = [q.get("id") for q in questions if isinstance(q, dict)]
    placed = [qid for group in groups for qid in (group.get("questions") or [])]
    if (len(questions) != 50 or len(ids) != 50 or len(set(ids)) != 50
            or len(placed) != 50 or set(placed) != set(ids)):
        abort(409, "The cave's 50 question IDs no longer match its four walls.")
    return st, task, badge, config, groups


@leader_routes.get("/leader/content/tasks/<task_id>/cave-questions")
@leader_required
def cave_questions(task_id: str):
    """Edit one of the cave's 50 questions without rewriting the other 49."""
    _, task, badge, config, groups = _cave_editor_data(task_id)
    try:
        index = int(request.args.get("q", "0"))
    except ValueError:
        abort(404)
    questions = config["questions"]
    if not (0 <= index < len(questions)):
        abort(404)
    selected = questions[index]
    by_id = {q["id"]: i for i, q in enumerate(questions)}
    sections = [{"n": group["n"], "name_zh": group["name_zh"],
                 "name_en": group["name_en"], "icon": group.get("icon", ""),
                 "questions": [{"index": by_id[qid], **questions[by_id[qid]]}
                               for qid in group["questions"]]}
                for group in groups]
    choices = []
    for option in selected.get("options") or []:
        if isinstance(option, dict):
            choices.append({"zh": option.get("zh") or "", "en": option.get("en") or ""})
        else:
            choices.append({"zh": str(option), "en": str(option)})
    choices += [{"zh": "", "en": ""} for _ in range(max(0, 4 - len(choices)))]
    section = next((part for part in sections if selected["id"] in [q["id"] for q in part["questions"]]), None)
    # The third and fourth walls interleave IDs in the stored question bank.
    # Browse in the actual PLAY order, while posting to the stable bank index.
    wall_order = [q["index"] for part in sections for q in part["questions"]]
    position = wall_order.index(index)
    return render_template("leader/cave_questions.html", task=task, badge=badge,
                           sections=sections, section=section, question=selected,
                           choices=choices, index=index, position=position,
                           prev_index=wall_order[position - 1] if position else None,
                           next_index=wall_order[position + 1] if position < 49 else None)


@leader_routes.post("/leader/content/tasks/<task_id>/cave-questions/<int:bank_index>")
@leader_required
def save_cave_question(task_id: str, bank_index: int):
    """Keep the wall's ID, group, order and metadata; replace only one question."""
    st, task, _, config, _ = _cave_editor_data(task_id)
    questions = config["questions"]
    if not (0 <= bank_index < len(questions)):
        abort(404)
    old = questions[bank_index]
    if request.form.get("question_id") != old.get("id"):
        return fail(409, "question_changed", "題目已改動，請重新載入後再試。",
                    "This question changed; reload it before saving.")
    q_zh = (request.form.get("q_zh") or "").strip()
    q_en = (request.form.get("q_en") or "").strip()
    recap_zh = (request.form.get("explain_zh") or "").strip()
    recap_en = (request.form.get("explain_en") or "").strip()
    if (not q_zh or not q_en or not recap_zh or len(q_zh) > 600 or len(q_en) > 600
            or len(recap_zh) > 1200 or len(recap_en) > 1200):
        return fail(400, "cave_wording", "請填寫題目與中文溫習提示（請勿超出字數限制）。",
                    "Enter the question and Chinese recap within the length limits.")
    options = []
    for i in range(4):
        zh = (request.form.get(f"option_{i}_zh") or "").strip()
        en = (request.form.get(f"option_{i}_en") or "").strip()
        if (i < 3 and not zh) or (not zh and en) or len(zh) > 300 or len(en) > 300:
            return fail(400, "cave_options", "請填寫首三個選項；第四個可留空。",
                        "Fill the first three choices; the fourth is optional.")
        if zh:
            options.append({"zh": zh, "en": en or zh})
    if (len({option["zh"].casefold() for option in options}) != len(options)
            or len({option["en"].casefold() for option in options}) != len(options)):
        return fail(400, "duplicate_options", "中英文選項內容均不可重複。",
                    "Choices must be distinct in both languages.")
    answer = request.form.get("answer", "")
    if not answer.isdecimal() or len(answer) != 1 or not (0 <= int(answer) < len(options)):
        return fail(400, "cave_answer", "請選擇一個有效的正確答案。",
                    "Choose a correct answer among the filled choices.")

    updated = {**old, "q_zh": q_zh, "q_en": q_en, "options": options,
               "answer": int(answer), "explain_zh": recap_zh, "explain_en": recap_en}
    # The group lookup in /tasks/<id>/cave uses these IDs and the original bank
    # indices. Never allow an edit to reorder or remove any of the 50 questions.
    config["questions"] = [updated if i == bank_index else q for i, q in enumerate(questions)]
    st.update("tasks", task_id, {"config_json": config, "updated_at": now_iso()})
    audit(g.user, "edit_cave_question", "tasks", task_id,
          {"question_id": old["id"], "index": bank_index + 1,
           "answer_changed": int(answer) != old.get("answer")})
    return _done("題目已儲存，新一局會使用更新後的內容。",
                 "Question saved; new cave runs will use it.",
                 "leader_routes.cave_questions", task_id=task_id, q=bank_index, saved=1)


def _config_from_form(task_type: str, form, existing: dict) -> dict | None:
    """Turn the leader's plain-text task box into the structured config.

    Leaders type a quiz as one question per line:
        題目 | 正確選項（1 起） | 選項一 | 選項二 …
    and a checklist as one item per line. This is deliberately forgiving — it is
    a notebook, not a programming language.
    """
    if isinstance(existing, str):
        try:
            existing = json.loads(existing or "{}")
        except json.JSONDecodeError:
            existing = {}
    config = dict(existing) if isinstance(existing, dict) else {}

    def lines(value: str) -> list[str]:
        return [line.strip() for line in str(value or "").splitlines() if line.strip()]

    def split_row(line: str) -> list[str]:
        for separator in ("|", "｜"):
            if separator in line:
                return [part.strip() for part in line.split(separator)]
        return [line.strip()]

    if task_type == "quiz" or any(form.get(key) for key in ("quiz_zh", "quiz_en")):
        zh_lines, en_lines = lines(form.get("quiz_zh")), lines(form.get("quiz_en"))
        questions = []
        for index, zh_line in enumerate(zh_lines):
            zh_parts = split_row(zh_line)
            en_parts = split_row(en_lines[index]) if index < len(en_lines) else []
            q_zh, q_en = zh_parts[0], (en_parts[0] if en_parts else zh_parts[0])
            try:
                answer = max(0, int(float(zh_parts[1])) - 1) if len(zh_parts) > 1 else 0
            except ValueError:
                answer = 0
            options_zh = zh_parts[2:]
            options_en = en_parts[2:] if len(en_parts) > 2 else []
            if not options_zh:
                continue
            answer = max(0, min(answer, len(options_zh) - 1))   # forgiving: clamp into range
            questions.append({
                "q_zh": q_zh, "q_en": q_en, "answer": answer,
                "options": [
                    {"zh": text, "en": options_en[i] if i < len(options_en) else text}
                    for i, text in enumerate(options_zh)
                ],
            })
        if questions:
            config["questions"] = questions

    if task_type == "checklist" or any(form.get(key) for key in ("items_zh", "items_en")):
        zh_items, en_items = lines(form.get("items_zh")), lines(form.get("items_en"))
        items = [
            {"zh": text, "en": en_items[i] if i < len(en_items) else text}
            for i, text in enumerate(zh_items)
        ]
        if items:
            config["items"] = items

    if task_type == "reflection" and form.get("min_chars"):
        try:
            config["min_chars"] = int(float(form["min_chars"]))
        except ValueError:
            pass
    for hint_key in ("hint_zh", "hint_en"):
        if form.get(hint_key):
            config[hint_key] = form[hint_key]
    if form.get("max_chars"):
        try:
            config["max_chars"] = int(float(form["max_chars"]))
        except ValueError:
            pass
    return config if config else None


@leader_routes.post("/leader/content/tasks/<task_id>")
@leader_required
def update_task(task_id: str):
    st = store()
    existing = st.get("tasks", task_id)
    if not existing:
        abort(404)
    body = sanitize("tasks", request.form.to_dict() if request.form else None, partial=True)
    for key in ("title_zh", "title_en", "instruction_zh", "instruction_en", "type", "status"):
        raw = request.form.get(f"raw_{key}") if request.form else None
        if raw is not None:
            body[key] = raw
    task_type = body.get("type") or existing.get("type") or "checklist"
    if request.form:
        if request.form.get("config_json"):
            try:
                body["config_json"] = json.loads(request.form["config_json"])
            except json.JSONDecodeError:
                pass
        else:
            config = _config_from_form(task_type, request.form, existing.get("config_json") or {})
            if config:
                body["config_json"] = config
    badge = st.get("badges", existing.get("badge_id"))
    areas = ((as_json((badge or {}).get("guide_json"), {}) or {}).get("quest") or {}).get("areas") or []
    assigned = any((a.get("game") or {}).get("ready")
                   and (a.get("game") or {}).get("task_code") == existing.get("code") for a in areas)
    if assigned and (body.get("code", existing.get("code")) != existing.get("code")
                     or body.get("type", existing.get("type")) != existing.get("type")
                     or body.get("status", existing.get("status")) != "published"):
        return fail(409, "game_task_locked", "遊戲已掛接，不能更改任務代號、類型或發佈狀態",
                    "An assigned game's code, type and publish status are fixed")
    if _is_editable_cave(existing, badge):
        # A generic quiz paste discards the IDs that connect the 50 questions
        # to the four walls. Only the dedicated editor may change this bank.
        if any(key in request.form for key in ("quiz_zh", "quiz_en", "config_json")):
            return fail(400, "cave_questions", "請在「編輯山洞題目」逐題修改題目和答案。",
                        "Use Edit cave questions to change its questions and answers safely.")
        body.pop("config_json", None)
        body["pass_score"] = 0  # finishing the cave, not passing a mark, clears game 1
    record = st.update("tasks", task_id, body)
    audit(g.user, "update_task", "tasks", task_id, {})
    return _done("已更新任務", "Task updated", "leader_routes.content")


@leader_routes.post("/leader/content/tasks/<task_id>/delete")
@leader_required
def delete_task(task_id: str):
    st = store()
    task = st.get("tasks", task_id)
    if not task:
        abort(404)
    badge = st.get("badges", task.get("badge_id"))
    areas = ((as_json((badge or {}).get("guide_json"), {}) or {}).get("quest") or {}).get("areas") or []
    if any((a.get("game") or {}).get("ready")
           and (a.get("game") or {}).get("task_code") == task.get("code") for a in areas):
        return fail(409, "assigned_game", "請先解除區域的遊戲設定；第一區山洞不可刪除",
                    "Unassign this game from its area first; game 1's cave cannot be deleted")
    st.remove("tasks", task_id)
    audit(g.user, "delete_task", "tasks", task_id, {})
    return _done("已刪除任務", "Task deleted", "leader_routes.content")


@leader_routes.post("/leader/content/tasks/<task_id>/move")
@leader_required
def move_task(task_id: str):
    st = store()
    task = st.get("tasks", task_id)
    if not task:
        abort(404)
    direction = request.form.get("direction") or "up"
    siblings = sorted([t for t in st.list("tasks") if t.get("badge_id") == task.get("badge_id")],
                      key=lambda t: int(float(t.get("order_index") or 0)))
    index = next((i for i, t in enumerate(siblings) if t["id"] == task_id), -1)
    swap = index - 1 if direction == "up" else index + 1
    if 0 <= swap < len(siblings):
        a, b = siblings[index], siblings[swap]
        st.update("tasks", a["id"], {"order_index": int(float(b.get("order_index") or 0)) or swap + 1})
        st.update("tasks", b["id"], {"order_index": int(float(a.get("order_index") or 0)) or index + 1})
    return _done("已更新次序", "Order updated", "leader_routes.content")


# ══ review queue ═══════════════════════════════════════════════════════════

@leader_routes.get("/leader/review")
@leader_required
def review():
    st = store()
    users = {u["id"]: u for u in st.list("users")}
    tasks = {t["id"]: t for t in st.list("tasks")}
    badges = {b["id"]: b for b in st.list("badges")}
    records = st.list("progress_records")

    def decorate(rows):
        out = []
        for row in rows:
            task = tasks.get(row.get("task_id"), {})
            out.append({
                **row,
                "who": users.get(row.get("user_id"), {}),
                "task": task,
                "badge": badges.get(row.get("badge_id"), {}),
                "answers": _as_list(row.get("answers_json")),
                "checklist": _as_list(row.get("checklist_json")),
                "task_type": task.get("type", ""),
            })
        return out

    pending = decorate(sorted([r for r in records if r.get("status") == "pending"],
                              key=lambda r: str(r.get("submitted_at") or "")))
    decided = decorate(sorted([r for r in records if r.get("status") in ("completed", "rejected") and r.get("decided_by") not in ("auto", "")],
                              key=lambda r: str(r.get("decided_at") or r.get("submitted_at") or ""), reverse=True)[:25])
    return render_template("leader/review.html", pending=pending, decided=decided,
                           filter_status=request.args.get("status", "pending"))


def _as_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


@leader_routes.post("/leader/review/<record_id>")
@leader_required
def review_action(record_id: str):
    st = store()
    body = request.get_json(silent=True) or request.form.to_dict() or {}
    action = str(body.get("action") or "")
    comment = str(body.get("comment") or "").strip()
    points_override = body.get("points")
    record = st.get("progress_records", record_id)
    if not record:
        return fail(404, "not_found", "找不到紀錄", "Record not found")
    if action not in ("approve", "reject", "reset"):
        return fail(400, "bad_action", "無效的動作", "Invalid action")

    user = st.get("users", record.get("user_id")) or {}
    task = st.get("tasks", record.get("task_id")) or {}
    badge = st.get("badges", task.get("badge_id")) if task else None

    if action == "reject":
        st.update("progress_records", record_id, {
            "status": "rejected", "leader_comment": comment, "decided_at": now_iso(),
            "decided_by": g.user["id"], "points_awarded": 0,
        })
        audit(g.user, "reject", "progress_records", record_id, {"comment": comment})
        return _done("已退回並附上評語", "Sent back with a comment", "leader_routes.review")

    if action == "reset":
        st.update("progress_records", record_id, {
            "status": "pending", "leader_comment": "", "decided_at": "", "decided_by": "",
        })
        audit(g.user, "reset", "progress_records", record_id, {})
        return _done("已重新放入待審批", "Moved back to the queue", "leader_routes.review")

    # approve → pay out now (this is where evidence/reflection/signoff earn points)
    st.update("progress_records", record_id, {"status": "completed", "leader_comment": comment})
    events = []
    if record.get("status") != "completed":
        override_task = task if points_override in (None, "") else {**task, "points": int(float(points_override))}
        result = award_task_completion(st, user=user, task=override_task, badge=badge,
                                       record={**record, "points_awarded": 0}, awarded_by=g.user["id"])
        events = result["events"]
        from ..engine import touch_streak

        touch_streak(st, user.get("id", ""))
    audit(g.user, "approve", "progress_records", record_id, {"comment": comment, "points": points_override})
    if wants_json():
        return ok(status="completed", events=events)
    return _done("已批准並加分", "Approved — points awarded", "leader_routes.review")


# ══ accounts ═══════════════════════════════════════════════════════════════

@leader_routes.get("/leader/accounts")
@leader_required
def accounts():
    st = store()
    settings = st.settings_cached()
    patrol_filter = request.args.get("patrol", "")
    search = (request.args.get("q") or "").strip().lower()
    rows = []
    for user in st.list("users"):
        if user.get("role") != "scout":
            continue
        if patrol_filter and user.get("patrol") != patrol_filter:
            continue
        if search and search not in f"{user.get('display_name_zh','')} {user.get('display_name_en','')} {user.get('username','')}".lower():
            continue
        stats = st.stats_for(user["id"])
        rows.append({**public_user(user), "stats": stats})
    rows.sort(key=lambda r: (str(r.get("patrol") or ""), str(r.get("display_name_zh") or "")))
    resets = [r for r in st.list("password_reset_requests") if r.get("status") == "pending"]
    return render_template("leader/accounts.html", scouts=rows, patrols=settings.get("patrols") or [],
                           patrol_filter=patrol_filter, search=request.args.get("q", ""),
                           reset_requests=resets, reset_patrols={r.get("user_id"): r.get("patrol") for r in resets},
                           mail_ready=mailer.is_configured(mailer.config(settings)))


@leader_routes.post("/leader/accounts")
@leader_required
def create_scout():
    st = store()
    form = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})
    name_zh = (form.get("display_name_zh") or "").strip()
    if not name_zh:
        return fail(400, "bad_name", "請輸入姓名", "Enter a name")
    patrol = (form.get("patrol") or "").strip()
    if not patrol:
        return fail(400, "bad_patrol", "請選擇小隊", "Pick a patrol")
    username = (form.get("username") or "").strip().lower()
    if not username:
        base = slug(form.get("display_name_en") or name_zh) or "scout"
        username = base
        taken = {u.get("username") for u in st.list("users")}
        counter = 2
        while username in taken:
            username = f"{base}{counter}"
            counter += 1
    if any(u.get("username") == username for u in st.list("users")):
        return fail(409, "username_taken", "此用戶名稱已被使用", "That username is taken")

    temp_password = (form.get("password") or "").strip()
    hashed, salt = hash_password(temp_password) if temp_password else ("", "")
    record = st.insert("users", {
        "role": "scout", "username": username,
        "password_hash": hashed, "password_salt": salt,
        "display_name_zh": name_zh,
        "display_name_en": (form.get("display_name_en") or name_zh).strip(),
        "email": (form.get("email") or "").strip(),
        "scout_no": (form.get("scout_no") or "").strip(),
        "section": "scout", "patrol": patrol,
        "unit": (form.get("unit") or st.settings_cached().get("unit_name_zh") or "").strip(),
        "avatar": (form.get("avatar") or "🦊").strip() or "🦊",
        "status": "active",
        "must_change_password": True,  # even a temporary password needs personal password + email
        "show_on_leaderboard": to_bool(form.get("show_on_leaderboard", True)),
        "created_at": now_iso(), "created_by": g.user["id"],
    })
    st.stats_for(record["id"])
    audit(g.user, "create_scout", "users", record["id"], {"patrol": patrol})
    if wants_json():
        return ok(user=public_user(record), temp_password=temp_password)
    return redirect(url_for("leader_routes.accounts"))


@leader_routes.post("/leader/accounts/<user_id>")
@leader_required
def update_scout(user_id: str):
    st = store()
    form = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})
    patch = {k: v for k, v in sanitize("users", form, partial=True).items()
             if k in {"display_name_zh", "display_name_en", "email", "scout_no", "patrol", "avatar", "unit"}}
    if "show_on_leaderboard" in form:
        patch["show_on_leaderboard"] = to_bool(form["show_on_leaderboard"])
    record = st.update("users", user_id, patch)
    if not record:
        abort(404)
    audit(g.user, "update_scout", "users", user_id, patch)
    if wants_json():
        return ok(user=public_user(record))
    return redirect(url_for("leader_routes.accounts"))


@leader_routes.post("/leader/accounts/<user_id>/<action>")
@leader_required
def account_action(user_id: str, action: str):
    """lock · unlock · reset (password) · delete — the panel's row buttons."""
    st = store()
    user = st.get("users", user_id)
    if not user or user.get("role") != "scout":
        return fail(404, "not_found", "找不到此童軍", "Scout not found")

    if action == "lock":
        st.update("users", user_id, {"status": "locked"})
        audit(g.user, "lock_scout", "users", user_id, {})
        return _done("已停用帳戶", "Account locked", "leader_routes.accounts")
    if action == "unlock":
        st.update("users", user_id, {"status": "active"})
        audit(g.user, "unlock_scout", "users", user_id, {})
        return _done("已重新啟用帳戶", "Account unlocked", "leader_routes.accounts")
    if action == "reset":
        clear_password(st, user)
        _resolve_reset_requests(user_id)
        audit(g.user, "reset_password", "users", user_id, {})
        message = "已重設密碼：童軍下次登入時自行設定新密碼"
        if wants_json():
            return ok(message_zh=message, message_en="Password reset — the scout sets a new one at next sign-in")
        return redirect(url_for("leader_routes.accounts"))
    if action == "delete":
        st.remove("users", user_id)
        for collection in ("progress_records", "badge_awards", "points_ledger"):
            st.remove_where(collection, lambda row, uid=user_id: row.get("user_id") == uid)
        st.remove("stats", user_id)
        audit(g.user, "delete_scout", "users", user_id, {})
        return _done("已刪除帳戶及其紀錄", "Account and records deleted", "leader_routes.accounts")
    return fail(400, "bad_action", "無效的動作", "Invalid action")


def _resolve_reset_requests(user_id: str) -> None:
    st = store()
    for row in st.list("password_reset_requests"):
        if row.get("user_id") == user_id and row.get("status") == "pending":
            st.update("password_reset_requests", row["id"], {
                "status": "handled", "handled_at": now_iso(), "handled_by": g.user["id"],
            })


@leader_routes.post("/leader/reset-requests/<request_id>/dismiss")
@leader_required
def dismiss_reset(request_id: str):
    st = store()
    row = st.get("password_reset_requests", request_id)
    if not row:
        abort(404)
    st.update("password_reset_requests", request_id, {
        "status": "dismissed", "handled_at": now_iso(), "handled_by": g.user["id"],
    })
    audit(g.user, "dismiss_reset_request", "users", row.get("user_id", ""), {})
    return _done("已略過此申請", "Request dismissed", "leader_routes.accounts")


@leader_routes.get("/leader/accounts/export.csv")
@leader_required
def export_scouts():
    st = store()
    rows = []
    for user in st.list("users"):
        if user.get("role") != "scout":
            continue
        stats = st.stats_for(user["id"])
        rows.append({
            "username": user.get("username", ""), "display_name_zh": user.get("display_name_zh", ""),
            "display_name_en": user.get("display_name_en", ""), "patrol": user.get("patrol", ""),
            "scout_no": user.get("scout_no", ""), "email": user.get("email", ""),
            "avatar": user.get("avatar", ""), "status": user.get("status", ""),
            "has_password": "yes" if user.get("password_hash") else "no",
            "points_balance": stats.get("points_balance", 0), "tasks_done": stats.get("tasks_done", 0),
            "badges_done": stats.get("badges_done", 0),
        })
    csv_text = to_csv(rows, ["username", "display_name_zh", "display_name_en", "patrol", "scout_no",
                             "email", "avatar", "status", "has_password", "points_balance",
                             "tasks_done", "badges_done"])
    audit(g.user, "export_scouts", "users", "", {"rows": len(rows)})
    return Response(csv_text, mimetype="text/csv", headers={
        "Content-Disposition": f"attachment; filename=scouts-{now_iso()[:10]}.csv",
    })


@leader_routes.post("/leader/accounts/import")
@leader_required
def import_scouts():
    """CSV columns: username, display_name_zh, display_name_en, patrol, scout_no, email, avatar"""
    st = store()
    text = ""
    if request.files.get("file"):
        text = request.files["file"].read().decode("utf-8", errors="replace")
    elif request.form.get("csv"):
        text = request.form["csv"]
    elif request.is_json:
        text = (request.get_json(silent=True) or {}).get("csv", "")
    if not text.strip():
        return fail(400, "empty", "沒有內容", "Nothing to import")

    created, skipped = 0, 0
    existing = {u.get("username") for u in st.list("users")}
    for row in parse_csv(text):
        name_zh = (row.get("display_name_zh") or row.get("name_zh") or "").strip()
        if not name_zh:
            skipped += 1
            continue
        username = (row.get("username") or "").strip().lower()
        if not username:
            username = slug(row.get("display_name_en") or name_zh) or f"scout{created + 1}"
        if username in existing:
            skipped += 1
            continue
        record = st.insert("users", {
            "role": "scout", "username": username, "password_hash": "", "password_salt": "",
            "display_name_zh": name_zh,
            "display_name_en": (row.get("display_name_en") or name_zh).strip(),
            "email": (row.get("email") or "").strip(), "scout_no": (row.get("scout_no") or "").strip(),
            "section": "scout", "patrol": (row.get("patrol") or "").strip(),
            "unit": st.settings_cached().get("unit_name_zh", ""), "avatar": (row.get("avatar") or "🦊").strip() or "🦊",
            "status": "active", "must_change_password": True, "show_on_leaderboard": True,
            "created_at": now_iso(), "created_by": g.user["id"],
        })
        st.stats_for(record["id"])
        existing.add(username)
        created += 1
    audit(g.user, "import_scouts", "users", "", {"created": created, "skipped": skipped})
    if wants_json():
        return ok(created=created, skipped=skipped)
    return redirect(url_for("leader_routes.accounts"))


# ══ announcements ══════════════════════════════════════════════════════════

@leader_routes.get("/leader/announcements")
@leader_required
def announcements():
    rows = sorted(store().list("announcements"), key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return render_template("leader/announcements.html", items=rows)


@leader_routes.post("/leader/announcements")
@leader_required
def create_announcement():
    st = store()
    form = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})
    if not (form.get("title_zh") or form.get("title_en") or "").strip():
        return fail(400, "bad_title", "請輸入標題", "Enter a title")
    item = st.insert("announcements", {
        "title_zh": (form.get("title_zh") or "").strip(), "title_en": (form.get("title_en") or "").strip(),
        "body_zh": (form.get("body_zh") or "").strip(), "body_en": (form.get("body_en") or "").strip(),
        "audience": form.get("audience") or "all",
        "pinned": to_bool(form.get("pinned")), "created_at": now_iso(),
        "expires_at": (form.get("expires_at") or "").strip(),
    })
    audit(g.user, "create_announcement", "announcements", item["id"], {})
    return _done("已發佈公告", "Notice posted", "leader_routes.announcements")


@leader_routes.post("/leader/announcements/<item_id>")
@leader_required
def update_announcement(item_id: str):
    st = store()
    form = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})
    patch = sanitize("announcements", form, partial=True)
    if "pinned" in form:
        patch["pinned"] = to_bool(form["pinned"])
    patch.pop("audience", None) if not form.get("audience") else None
    record = st.update("announcements", item_id, patch)
    if not record:
        abort(404)
    audit(g.user, "update_announcement", "announcements", item_id, {})
    return _done("已更新公告", "Notice updated", "leader_routes.announcements")


@leader_routes.post("/leader/announcements/<item_id>/delete")
@leader_required
def delete_announcement(item_id: str):
    store().remove("announcements", item_id)
    audit(g.user, "delete_announcement", "announcements", item_id, {})
    return _done("已刪除公告", "Notice deleted", "leader_routes.announcements")


# ══ rewards ════════════════════════════════════════════════════════════════

@leader_routes.get("/leader/rewards")
@leader_required
def rewards():
    st = store()
    if not (st.settings_cached().get("feature_flags") or {}).get("redeem", False):
        # hidden until the unit switches 獎品 on — see 設定 → 功能開關
        flash({"kind": "warn", "zh": "獎品未開放 — 在設定中開啟即可管理。",
               "en": "Rewards are not open yet — switch them on in Settings."}, "result")
        return redirect(url_for("leader_routes.overview"))
    items = sorted(st.list("rewards"), key=lambda r: int(float(r.get("points_cost") or 0)))
    return render_template("leader/rewards.html", items=items,
                           redemptions_enabled=bool((st.settings_cached().get("feature_flags") or {}).get("redeem")))


@leader_routes.post("/leader/rewards")
@leader_required
def create_reward():
    st = store()
    form = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})
    if not (form.get("title_zh") or form.get("title_en") or "").strip():
        return fail(400, "bad_title", "請輸入獎品名稱", "Enter a reward name")
    item = st.insert("rewards", {
        "title_zh": (form.get("title_zh") or "").strip(), "title_en": (form.get("title_en") or "").strip(),
        "desc_zh": (form.get("desc_zh") or "").strip(), "desc_en": (form.get("desc_en") or "").strip(),
        "emoji": (form.get("emoji") or "🎁").strip() or "🎁",
        "points_cost": int(float(form.get("points_cost") or 0)),
        "stock": int(float(form.get("stock") or 0)),
        "category": (form.get("category") or "general").strip(),
        "active": to_bool(form.get("active", True)),
    })
    audit(g.user, "create_reward", "rewards", item["id"], {})
    return _done("已新增獎品", "Reward added", "leader_routes.rewards")


@leader_routes.post("/leader/rewards/<item_id>")
@leader_required
def update_reward(item_id: str):
    st = store()
    form = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})
    patch = sanitize("rewards", form, partial=True)
    if "active" in form:
        patch["active"] = to_bool(form["active"])
    record = st.update("rewards", item_id, patch)
    if not record:
        abort(404)
    audit(g.user, "update_reward", "rewards", item_id, {})
    return _done("已更新獎品", "Reward updated", "leader_routes.rewards")


@leader_routes.post("/leader/rewards/<item_id>/delete")
@leader_required
def delete_reward(item_id: str):
    store().remove("rewards", item_id)
    audit(g.user, "delete_reward", "rewards", item_id, {})
    return _done("已刪除獎品", "Reward deleted", "leader_routes.rewards")


@leader_routes.post("/leader/rewards/adjust-points")
@leader_required
def adjust_points():
    """Manual ±points with a reason — every movement is explainable."""
    st = store()
    form = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})
    user = st.get("users", form.get("user_id"))
    if not user:
        return fail(404, "not_found", "找不到此童軍", "Scout not found")
    delta = int(float(form.get("points_delta") or 0))
    reason = (form.get("reason") or "").strip()
    write_ledger(st, user_id=user["id"], entry_type="manual", points_delta=delta,
                 reason_zh=reason or "領袖調整", reason_en=reason or "Leader adjustment",
                 ref_type="manual", ref_id="", created_by=g.user["id"])
    audit(g.user, "adjust_points", "users", user["id"], {"delta": delta, "reason": reason})
    return _done("已調整積分", "Points adjusted", "leader_routes.accounts")


# ══ 上線檢查（只讀：一眼看到設定是否齊全）═════════════════════════════════

def _game_content(tasks: list[dict]) -> dict[str, bool]:
    """遊戲內容是否就緒。

    遊戲的內容（洞穴壁畫、過河木板）隨程式提供，放在
    `content/member-badge/cave.json` 與 `river.json`；任務分頁則負責讓童軍
    找得到入口。所以兩邊都要有：內容檔案讀得到，對應的任務（第 4、5 項）也在。
    """
    from ..content import cave_adventure, river_adventure

    def load(loader):
        try:
            return loader() or {}
        except Exception:                     # noqa: BLE001 — a broken file is "not ready"
            return {}

    cave = load(cave_adventure)
    river = load(river_adventure)
    codes = {str(task.get("code") or "") for task in tasks}
    return {
        "cave": bool(cave.get("groups")) and "M04" in codes,
        "river": bool(river.get("stages")) and "M05" in codes,
    }


def setup_checks(st) -> dict:
    """給領袖後台「設定檢查」卡用的清單 —— 只讀，不會改動任何資料。"""
    from ..store import storage_advice as _advice

    reason, advice = _advice(getattr(st, "config", {}).get("storage_error", ""))
    settings = st.settings()
    badges = st.list("badges")
    tasks = st.list("tasks")
    users = st.list("users")
    leaders = [row for row in users if row.get("role") == "leader"]
    scouts = [row for row in users if row.get("role") == "scout"]
    games = _game_content(tasks)
    on_sheets = st.driver.name == "sheets"
    sheet_id = str(getattr(st.driver, "spreadsheet_id", "") or "")
    mail_ready = bool(str(settings.get("smtp_host") or "").strip())

    def row(key, ok, zh, en, detail_zh, detail_en, fix_zh="", fix_en="", optional=False):
        return {"key": key, "ok": bool(ok), "zh": zh, "en": en, "detail_zh": detail_zh,
                "detail_en": detail_en, "fix_zh": fix_zh, "fix_en": fix_en, "optional": optional}

    checks = [
        row("storage", on_sheets,
            "資料儲存在 Google 試算表" if on_sheets else "連不上 Google 試算表，資料暫存中",
            "Data lives in the Google Sheet" if on_sheets else "Cannot reach the Sheet — storage is temporary",
            ("試算表 ID：" + sheet_id[:12] + "…") if on_sheets else reason or "目前寫在執行個體暫存空間，會被回收",
            ("Spreadsheet ID: " + sheet_id[:12] + "…") if on_sheets else "Currently in the instance /tmp — it will be recycled",
            advice or "在 Vercel 加入 GOOGLE_SHEET_ID 與 GOOGLE_SERVICE_ACCOUNT_JSON，然後 Redeploy（docs/02）",
            "Add GOOGLE_SHEET_ID and GOOGLE_SERVICE_ACCOUNT_JSON in Vercel, then Redeploy (docs/02)"),
        row("badges", len(badges) >= 5, "獎章目錄已經建立", "Badge catalogue created",
            str(len(badges)) + " 個獎章", str(len(badges)) + " badges",
            "目錄會在第一次連上空試算表時自動建立；若一直是 0，代表正在執行的版本未含此功能，請部署最新版本",
            "The catalogue is created once on the first connection; 0 means the running version is out of date — redeploy"),
        row("tasks", len(tasks) >= 11, "任務與遊戲項目齊全", "Tasks and game items present",
            str(len(tasks)) + " 個項目", str(len(tasks)) + " items",
            "部署最新版本；已建立過的目錄不會被覆蓋",
            "Deploy the latest version; existing rows are never overwritten"),
        row("games", games["cave"] and games["river"],
            "遊戲 1（石室）與遊戲 2（過河）已就緒", "Game 1 (cave) and Game 2 (river) ready",
            ("石室題目與過河木板都已載入" if games["cave"] and games["river"]
             else "石室：" + ("有" if games["cave"] else "缺") + "，過河：" + ("有" if games["river"] else "缺")),
            "cave: " + ("yes" if games["cave"] else "missing") + ", river: " + ("yes" if games["river"] else "missing"),
            "部署最新版本（遊戲內容隨程式提供）",
            "Deploy the latest version (game content ships with the code)"),
        row("leaders", len(leaders) >= 1, "領袖帳戶", "Leader account",
            str(len(leaders)) + " 位領袖", str(len(leaders)) + " leader(s)"),
        row("scouts", len(scouts) >= 1, "童軍帳戶已經開好", "Scout accounts created",
            str(len(scouts)) + " 位童軍", str(len(scouts)) + " scout(s)",
            "領袖後台 → 帳戶 → 開設童軍帳戶",
            "Leader console → Accounts → Create a scout account"),
        row("email", mail_ready, "找回密碼的寄信信箱", "Mailbox for password resets",
            "已設定，可以寄出重設連結" if mail_ready else "未設定；童軍仍可在密碼頁用電郵即時設定新密碼",
            "Set up — reset links can be sent" if mail_ready else "Not set — scouts fall back to the on-the-spot method",
            "設定 → 寄信信箱（docs/03-email-setup.md）",
            "Settings → Mailbox (docs/03-email-setup.md)", optional=True),
    ]
    required = [item for item in checks if not item["optional"]]
    return {
        "checks": checks,
        "ready": all(item["ok"] for item in required),
        "pending": sum(1 for item in required if not item["ok"]),
        "optional_pending": sum(1 for item in checks if item["optional"] and not item["ok"]),
        "counts": {"badges": len(badges), "tasks": len(tasks),
                   "leaders": len(leaders), "scouts": len(scouts)},
    }


# ══ settings ═══════════════════════════════════════════════════════════════

@leader_routes.get("/leader/settings")
@leader_required
def settings_page():
    st = store()
    return render_template("leader/settings.html", current=st.settings(force=True),
                           defaults=DEFAULT_SETTINGS, mail_result=mailer.LAST_RESULT or None,
                           setup=setup_checks(st))


@leader_routes.post("/leader/settings")
@leader_required
def save_settings():
    st = store()
    form = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})
    current = st.settings()
    bool_keys = [k for k, v in DEFAULT_SETTINGS.items() if isinstance(v, bool)]
    flag_keys = list((DEFAULT_SETTINGS.get("feature_flags") or {}).keys())

    # Simple text/number settings
    for key in ("unit_name_zh", "unit_name_en", "motto_zh", "motto_en"):
        if key in form:
            st.save_setting(key, str(form[key]).strip())
    # ── the mailbox that sends reset links ──
    for key in ("smtp_host", "smtp_user", "smtp_from", "public_base_url"):
        if key in form:
            st.save_setting(key, str(form[key]).strip())
    if "smtp_tls" in form:
        st.save_setting("smtp_tls", (str(form["smtp_tls"]).strip().lower() or "tls"))
    if "smtp_port" in form:
        try:
            st.save_setting("smtp_port", max(1, min(65535, int(str(form["smtp_port"]).strip() or 587))))
        except ValueError:
            st.save_setting("smtp_port", 587)
    if "reset_link_minutes" in form:
        try:
            st.save_setting("reset_link_minutes",
                            max(5, min(1440, int(str(form["reset_link_minutes"]).strip() or 60))))
        except ValueError:
            st.save_setting("reset_link_minutes", 60)
    # the app password: blank keeps what is stored, a single hyphen clears it
    if "smtp_password" in form:
        typed = str(form["smtp_password"]).strip()
        if typed == "-":
            st.save_setting("smtp_password", "")
        elif typed and set(typed) != {"•"}:
            st.save_setting("smtp_password", typed)
    if request.form and request.form.getlist("patrols"):
        patrols = [p.strip() for p in request.form.getlist("patrols") if p.strip()]
        st.save_setting("patrols", patrols or DEFAULT_SETTINGS["patrols"])
    # Switches: an unticked checkbox posts nothing, so the settings form sends a
    # marker meaning “every switch on this page is here” — then absent = off.
    switches_posted = bool(request.form and request.form.get("switches") == "1")
    for key in bool_keys:
        if key == "feature_flags":
            continue
        st.save_setting(key, checkbox(key) if switches_posted else current.get(key, False))
    flags = dict(current.get("feature_flags") or {})
    for key in flag_keys:
        flags[key] = checkbox(f"flag_{key}") if switches_posted else flags.get(key, True)
    st.save_setting("feature_flags", flags)
    audit(g.user, "update_settings", "settings", "", {"keys": sorted(form)[:20]})
    return _done("已儲存設定", "Settings saved", "leader_routes.settings_page")


@leader_routes.post("/leader/settings/test-mail")
@leader_required
def test_mail():
    """Send one test message so the leader can see the mailbox really works."""
    st = store()
    cfg = mailer.config(st.settings(force=True))
    to = (request.form.get("to") or "").strip() or cfg.get("smtp_from") or cfg.get("smtp_user") or ""
    if not mailer.is_configured(cfg):
        audit(g.user, "test_mail_blocked", "settings", "")
        return _done("還未填好寄信設定（主機、寄件人）", "Fill in the mail settings first (host and sender)",
                     "leader_routes.settings_page")
    ok_sent, error = mailer.send_test(cfg, to, unit_zh=st.settings_cached().get("unit_name_zh") or "")
    audit(g.user, "test_mail_sent" if ok_sent else "test_mail_failed", "settings", "", {"error": error[:160]})
    if ok_sent:
        return _done(f"測試郵件已寄到 {to}", f"Test email sent to {to}", "leader_routes.settings_page")
    return _done(f"未能寄出：{error[:120]}", f"Could not send: {error[:120]}", "leader_routes.settings_page")


@leader_routes.post("/leader/accounts/<user_id>/send-reset")
@leader_required
def send_reset_link(user_id: str):
    """Email a reset link to one scout from the accounts panel."""
    st = store()
    user = st.get("users", user_id)
    if not user or user.get("role") != "scout":
        return fail(404, "not_found", "找不到此童軍", "Scout not found")
    cfg = mailer.config(st.settings(force=True))
    email = (user.get("email") or "").strip()
    if not mailer.is_configured(cfg):
        return _done("還未設定寄信信箱（設定 → 電郵）", "No mailbox set up yet (Settings → Email)",
                     "leader_routes.accounts")
    if not email:
        return _done("這位童軍未有電郵，請先為他填寫。", "That scout has no email yet — add one first.",
                     "leader_routes.accounts")
    token, row = create_reset_token(st, user, minutes=int(cfg.get("reset_link_minutes") or 60),
                                    requested_by="leader")
    base = (st.settings_cached().get("public_base_url") or "").strip().rstrip("/")
    link = (base + url_for("auth_routes.reset_link", token=token)) if base else \
        url_for("auth_routes.reset_link", token=token, _external=True)
    ok_sent, error = mailer.send_reset_link(
        cfg, user, link, unit_zh=st.settings_cached().get("unit_name_zh") or "")
    audit(g.user, "reset_link_sent_by_leader" if ok_sent else "reset_link_failed", "users", user["id"],
          {"to": mailer.mask_email(email), "error": error[:120]})
    if not ok_sent:
        st.update("password_resets", row["id"], {"used_at": now_iso()})   # nothing left dangling
    if ok_sent:
        return _done(f"重設連結已寄到 {mailer.mask_email(email)}",
                     f"Reset link sent to {mailer.mask_email(email)}", "leader_routes.accounts")
    return _done(f"未能寄出：{error[:120]}", f"Could not send: {error[:120]}", "leader_routes.accounts")


# ══ audit log ══════════════════════════════════════════════════════════════

@leader_routes.get("/leader/audit")
@leader_required
def audit_log():
    st = store()
    users = {u["id"]: u for u in st.list("users")}
    rows = sorted(st.list("audit_log"), key=lambda r: str(r.get("created_at") or ""), reverse=True)[:300]
    for row in rows:
        row["_actor"] = users.get(row.get("actor_id"), {})
        try:
            row["detail"] = json.loads(row.get("detail_json") or "{}")
        except json.JSONDecodeError:
            row["detail"] = {}
    return render_template("leader/audit.html", rows=rows)


# ══ JSON helpers the console uses for live updates ═════════════════════════

@leader_routes.get("/api/leader/overview")
@leader_required
def api_overview():
    return ok(**_overview_context())


@leader_routes.get("/api/leader/scouts")
@leader_required
def api_scouts():
    st = store()
    rows = [{**public_user(u), "stats": st.stats_for(u["id"])}
            for u in st.list("users") if u.get("role") == "scout"]
    rows.sort(key=lambda r: (-int(float(r["stats"].get("badges_done") or 0)), str(r.get("display_name_en") or "")))
    return ok(scouts=rows)


@leader_routes.get("/api/leader/scouts/<user_id>")
@leader_required
def api_scout_detail(user_id: str):
    st = store()
    user = st.get("users", user_id)
    if not user:
        return fail(404, "not_found", "找不到此童軍", "Scout not found")
    progress = progress_for(st, user_id)
    ledger = sorted([r for r in st.list("points_ledger") if r.get("user_id") == user_id],
                    key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return ok(user=public_user(user), progress=progress, ledger=ledger)


@leader_routes.get("/api/leader/leaderboard")
@leader_required
def api_leaderboard():
    board = leaderboard(store(), scope=request.args.get("scope", "unit"), patrol=request.args.get("patrol", ""),
                        period=request.args.get("period", "all"), include_hidden=True)
    return ok(**board)


@leader_routes.get("/api/leader/audit")
@leader_required
def api_audit():
    rows = sorted(store().list("audit_log"), key=lambda r: str(r.get("created_at") or ""), reverse=True)[:200]
    return ok(items=rows)


@leader_routes.get("/api/leader/reset-requests")
@leader_required
def api_reset_requests():
    rows = [r for r in store().list("password_reset_requests") if r.get("status") == "pending"]
    return ok(items=rows)


@leader_routes.post("/api/leader/scouts/<user_id>/award-badge/<badge_id>")
@leader_required
def api_award_badge(user_id: str, badge_id: str):
    """Manual override for the rare case a leader needs to grant an award."""
    st = store()
    user = st.get("users", user_id)
    badge = st.get("badges", badge_id)
    if not user or not badge:
        return fail(404, "not_found", "找不到帳戶或獎章", "Account or badge not found")
    if any(a.get("user_id") == user_id and a.get("badge_id") == badge_id for a in st.list("badge_awards")):
        return fail(409, "already", "已考獲此獎章", "Already awarded")
    # Grant without the completeness check — that is what "manual" means.
    st.insert("badge_awards", {
        "user_id": user_id, "badge_id": badge_id, "awarded_at": now_iso(),
        "awarded_by": g.user["id"], "note": "manual award",
    })
    points = int(float(badge.get("points_reward") or 0))
    if points:
        write_ledger(st, user_id=user_id, entry_type="badge", points_delta=points,
                     reason_zh=f"考獲「{badge.get('title_zh','')}」",
                     reason_en=f"Earned the \"{badge.get('title_en','')}\" badge",
                     ref_type="badge", ref_id=badge_id, created_by=g.user["id"])
    stats = st.stats_for(user_id)
    st.update("stats", user_id, {"badges_done": int(float(stats.get("badges_done") or 0)) + 1})
    audit(g.user, "manual_badge_award", "badges", badge_id, {"user_id": user_id})
    return ok(awarded=True, points=points)
