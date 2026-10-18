"""
The scout's own pages — 主頁 · 獎章 · 任務 · 獎品 · 紀錄 · 龍虎榜.

Forms post to real URLs, so the whole platform works with JavaScript off; when
the game layer *is* running it posts the same URLs with `X-Requested-With:
fetch` and gets JSON back (score, confetti events, updated rings) instead of a
redirect.
"""
from __future__ import annotations

import json
import unicodedata

from flask import Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request, url_for
from itsdangerous import BadSignature, URLSafeTimedSerializer

from ..auth import needs_first_time, public_user, scout_required
from ..content import cave_adventure, cave_images, river_adventure, river_images
from ..engine import (
    as_int, as_json, award_task_completion, build_suggestions, credit_opening_stages,
    evaluate_submission, game_areas, points_summary, progress_for,
    stage_list, touch_streak,
)
from ..content import member_badge_guide
from ..schema import TASK_TYPES, patrol_label
from ..util import now_iso
from .helpers import audit, fail, ok, store, wants_json

scout_routes = Blueprint("scout_routes", __name__)


# ── context builders ────────────────────────────────────────────────────────

def _active_announcements(st, audience: str = "scout") -> list[dict]:
    today = now_iso()[:10]
    rows = []
    for row in st.list("announcements"):
        if row.get("audience") not in ("all", audience):
            continue
        expires = str(row.get("expires_at") or "")[:10]
        if expires and expires < today:
            continue
        rows.append(row)
    rows.sort(key=lambda r: (not r.get("pinned"), str(r.get("created_at") or "")), reverse=False)
    rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    rows.sort(key=lambda r: bool(r.get("pinned")), reverse=True)
    return rows


def _home_context(user: dict) -> dict:
    st = store()
    progress = progress_for(st, user["id"])
    suggestions = build_suggestions(st, user, progress)
    return {
        # First-time scouts never reach Home before finishing setup.
        "url_ok": request.args.get("ok", ""),
        "progress": progress,
        "stats": progress["stats"],
        "overall": progress["overall"],
        "badges": progress["badges"],
        "suggestions": suggestions,
        "announcements": _active_announcements(st, "scout"),
        "next_task": progress["overall"]["next_task"],
    }


# ── 主頁 ────────────────────────────────────────────────────────────────────

@scout_routes.get("/home")
@scout_required
def home():
    return render_template("scout/home.html", **_home_context(g.user))


# ── 獎章 / journey map ──────────────────────────────────────────────────────

def _quest_started(st, user_id: str, badge_id: str) -> bool:
    """Casting off is a journey move, NOT an automatic syllabus task award."""
    return any(row.get("actor_id") == user_id and row.get("action") == "start_quest"
               and row.get("entity_id") == badge_id for row in st.list("audit_log"))


def _game_kind_for(task: dict, badge: dict | None) -> str:
    """Which arcade game this task is: 'cave', 'bridge' or '' for a normal task.

    A game plays in its own full-bleed page (`/tasks/<id>/cave`, `/tasks/<id>/bridge`)
    rather than the ordinary task form, and finishing it files the item. The
    kind is read from the area the task fills, so the leader keeps one place —
    the badge guide — to say which game lives where.
    """
    if not badge or task.get("type") != "quiz":
        return ""
    kind = ((as_json(task.get("config_json"), {}) or {}).get("kind") or "").strip()
    for area in (game_areas(badge) or []):
        game = area.get("game") or {}
        if game.get("task_code") != task.get("code") or not game.get("ready"):
            continue
        area_kind = (game.get("kind") or "").strip()
        if area_kind in ("cave", "bridge") and (not kind or kind == area_kind):
            return area_kind
    return ""


def _is_badge_cave_task(task: dict, badge: dict | None) -> bool:
    """The assigned cave is the only way to complete item 4's game slot."""
    if not cave_adventure().get("groups"):
        return False
    return _game_kind_for(task, badge) == "cave"


def _is_badge_bridge_task(task: dict, badge: dict | None) -> bool:
    """The assigned crossing is the only way to complete item 5's game slot."""
    if not river_adventure().get("stages"):
        return False
    return _game_kind_for(task, badge) == "bridge"


@scout_routes.get("/badges")
@scout_required
def badges():
    st = store()
    progress = progress_for(st, g.user["id"])
    done = st.get("tasks", request.args.get("done", "")) if request.args.get("done") else None
    return render_template("scout/badges.html", progress=progress, badges=progress["badges"],
                           overall=progress["overall"], stats=progress["stats"],
                           done_task=done,
                           url_err=request.args.get("err", ""))


@scout_routes.get("/badges/<badge_id>")
@scout_required
def badge_detail(badge_id: str):
    """會員章 是 one page: 玩法 — the story, the treasure map, the areas.

    Every door to the badge (the 主頁 tile, the 獎章 journey map, any old link)
    lands here; `?intro=1` is kept as an alias. `?started=1` — where 划出去 sends
    the scout — is the same page with the 冒險開始！ strip on top. A badge whose
    guide carries no quest keeps the plain requirement list.
    """
    st = store()
    progress = progress_for(st, g.user["id"])
    badge = next((b for b in progress["badges"] if b["id"] == badge_id), None)
    if not badge:
        abort(404)
    context = dict(badge=badge, progress=progress, stats=progress["stats"],
                   overall=progress["overall"])
    guide = badge.get("guide") or {}
    if not guide.get("quest"):
        return render_template("scout/badge_detail.html", **context)
    context["guide"] = guide
    context["stages"] = stage_list(st, user=g.user, badge=badge)
    # The quest the page reads is the leader's stored guide, with the shipped
    # content file filling any newer key (the intro slides, 2026-10-18) the
    # stored copy does not carry yet — a leader's own wording always wins.
    context["quest"] = {**((member_badge_guide().get("quest") or {})),
                        **(guide.get("quest") or {})}
    # The voyage starts without awarding a hidden task: the audit entry marks
    # the cast-off, and the game progress places the scout on the treasure map.
    context["started"] = (_quest_started(st, g.user["id"], badge_id)
                          or any(stage["game_done"] for stage in context["stages"])
                          or request.args.get("started") == "1")
    # A first-time scout is told the story as a click-through picture intro;
    # once the quest has begun (or the story is replayed) the page opens
    # straight on the escape route. `?intro=1` replays the pictures.
    context["intro"] = ((not context["started"])
                        or request.args.get("intro") == "1")
    context["intro_slides"] = context["quest"].get("intro_slides") or []
    return render_template("scout/badge_intro.html", **context)


@scout_routes.get("/badges/<badge_id>/requirements")
@scout_required
def badge_requirements(badge_id: str):
    """The 11 items in full: requirements, who checks them, and the resources."""
    st = store()
    progress = progress_for(st, g.user["id"])
    badge = next((b for b in progress["badges"] if b["id"] == badge_id), None)
    if not badge:
        abort(404)
    return render_template("scout/badge_detail.html", badge=badge, progress=progress,
                           stats=progress["stats"], overall=progress["overall"])


@scout_routes.post("/badges/<badge_id>/start")
@scout_required
def start_quest(badge_id: str):
    """開始冒險 — the opening stage is credited and the star lights up."""
    st = store()
    progress = progress_for(st, g.user["id"])
    badge = next((b for b in progress["badges"] if b["id"] == badge_id), None)
    if not badge:
        abort(404)
    if badge.get("locked"):
        return fail(403, "badge_locked", "請先完成上一個進度性獎章", "Finish the earlier award first")
    if badge.get("is_game_badge"):
        # There is no other task in area one. Casting off must not complete M01
        # or award points; the first real progress is clearing the cave.
        first = not _quest_started(st, g.user["id"], badge_id)
        if first:
            audit(g.user, "start_quest", "badges", badge_id)
        credited = []
    else:
        credited = credit_opening_stages(st, user=g.user, badge=badge)
        first = bool(credited)
    trail = url_for("scout_routes.badge_detail", badge_id=badge_id,
                    started=1 if first else None)
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify(ok=True, trail=trail, credited=[t["code"] for t in credited],
                       message_zh="冒險開始！", message_en="The adventure begins!")
    return redirect(trail)


# ── the task player ─────────────────────────────────────────────────────────

def as_int_or(value, default=None):
    """A tolerant int for comparing a stored answer with the key."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _cave_option_text(option) -> tuple[str, str]:
    """Existing bank options are strings; leader-edited ones can be bilingual."""
    if isinstance(option, dict):
        zh = str(option.get("zh") or option.get("en") or "")
        en = str(option.get("en") or option.get("zh") or "")
        return zh, en
    return str(option), str(option)


def _cave_run_signer() -> URLSafeTimedSerializer:
    """Pin an opened cave to its answer key so mid-run leader edits stay fair."""
    return URLSafeTimedSerializer(current_app.secret_key, salt="cave-question-bank-v1")


def _cave_run_key(task_id: str, questions: list[dict]) -> str:
    # Only the grading essentials go into the signed token, not the whole bank.
    # Each browser tab gets its own copy; nothing about a scout's run is stored
    # until all 50 questions have been answered and the exit is reached.
    return _cave_run_signer().dumps({
        "task": task_id, "scout": g.user["id"],
        "questions": [[q.get("id"), as_int_or(q.get("answer"), -1),
                       len(q.get("options") or [])] for q in questions],
    })


def _game_url(task: dict, kind: str) -> str:
    """The one URL that opens a game — the same routing the map's button uses."""
    if kind == "cave":
        return url_for("scout_routes.task_cave", task_id=task["id"])
    if kind == "bridge":
        return url_for("scout_routes.task_bridge", task_id=task["id"])
    return url_for("scout_routes.task_player", task_id=task["id"])


def _journey_next(user: dict, task: dict) -> dict | None:
    """The next game still to be played after this one, if it is ready.

    This is the map's own rule — walk the five areas in order and offer the first
    one whose game is built and not yet cleared — so the button at the cave mouth
    says exactly what the treasure map says next. A crossing that is laid but
    still waiting on the leader's code counts as played: the walk moves on to
    game 3, and the code can be typed in any time afterwards.
    """
    st = store()
    badge = st.get("badges", task.get("badge_id"))
    if not badge:
        return None
    guide = as_json(badge.get("guide_json"), {}) or {}
    areas = (guide.get("quest") or {}).get("areas") or []
    if not areas:
        return None
    done = {row.get("task_id") for row in st.list("progress_records")
            if row.get("user_id") == user["id"]
            and row.get("status") in ("completed", "crossed")}
    tasks = [t for t in st.list("tasks") if t.get("badge_id") == badge["id"]]
    for area in areas:
        game = area.get("game") or {}
        code = str(game.get("task_code") or "")
        found = next((t for t in tasks if t.get("code") == code), None)
        if not game.get("ready") or not found or found.get("status") != "published":
            continue
        if found["id"] == task["id"] or found["id"] in done:
            continue
        return {"n": area.get("n") or game.get("n") or 0, "task": found,
                "kind": str(game.get("kind") or ""),
                "name_zh": game.get("name_zh") or found.get("title_zh") or "",
                "name_en": game.get("name_en") or found.get("title_en") or ""}
    return None


def _task_context(user: dict, task_id: str) -> dict | None:
    st = store()
    task = st.get("tasks", task_id)
    if not task:
        return None
    progress = progress_for(st, user["id"])
    badge = next((b for b in progress["badges"] if b["id"] == task.get("badge_id")), None)
    decorated = next((t for t in (badge or {}).get("tasks", []) if t["id"] == task_id), None)
    if not decorated:
        return None
    index = next((i for i, t in enumerate(badge["tasks"]) if t["id"] == task_id), 0)
    # The answer key is added back only once the scout has submitted the paper —
    # never before, or the quiz would be pointless. This is a self-check paper
    # (自行考核) with unlimited retakes, so the review is handed over either way:
    # it is how the scout learns the bits they missed.
    from ..engine import as_json

    questions = as_json(task.get("config_json"), {}).get("questions") or []
    answer_key: list = []
    quiz_review: list = []
    if task.get("type") == "quiz" and decorated.get("answers_json"):
        given = as_json(decorated.get("answers_json"), [])
        answer_key = [q.get("answer") for q in questions]
        for index, question in enumerate(questions):
            # form answers arrive as strings; the review works in indices
            mine = as_int_or(given[index]) if index < len(given) else None
            key = as_int_or(question.get("answer"))
            ok = mine is not None and mine == key
            quiz_review.append({
                "n": index + 1,
                "q_zh": question.get("q_zh", ""), "q_en": question.get("q_en", ""),
                "options": question.get("options") or [],
                "given": mine, "answer": key, "correct": ok,
                "explain_zh": question.get("explain_zh", ""),
                "explain_en": question.get("explain_en", ""),
                "review_note": question.get("review_note", ""),
            })
    return {
        "task": decorated,
        "answer_key": answer_key,
        "quiz_review": quiz_review,
        # A game owns its item: /tasks/<id> redirects to the game, never a form.
        "cave_ready": _is_badge_cave_task(task, badge),
        "bridge_ready": _is_badge_bridge_task(task, badge),
        "badge": badge,
        "progress": progress,
        "stats": progress["stats"],
        "position": index + 1,
        "type_meta": TASK_TYPES.get(task.get("type"), {}),
        "next_task": badge["tasks"][index + 1] if index + 1 < len(badge["tasks"]) else None,
    }


@scout_routes.get("/tasks/<task_id>")
@scout_required
def task_player(task_id: str):
    context = _task_context(g.user, task_id)
    if not context:
        abort(404)
    if context["cave_ready"]:
        # Old links to item 4 reach the game, never another 50-question form.
        return redirect(url_for("scout_routes.task_cave", task_id=task_id))
    if context["bridge_ready"]:
        return redirect(url_for("scout_routes.task_bridge", task_id=task_id))
    return render_template("scout/task.html", **context)


@scout_routes.get("/tasks/<task_id>/cave")
@scout_required
def task_cave(task_id: str):
    """第 4 項的洞穴歷險 — the badge's first game: four walls, then 50 questions.

    The game is *client-side* (so it also plays inside the offline demo file):
    this route hands it the wall paintings with their timelines, and the fifty
    questions of the bank sorted into the four groups the walls teach, with the
    options in a shuffled order and the words for every button. The answers are
    automatically filed on reaching the exit through `POST /tasks/<id>/cave-submit`
    — the only submission path for this item. There is no separate paper to sit.
    """
    from ..engine import as_json

    st = store()
    task = st.get("tasks", task_id)
    context = _task_context(g.user, task_id) if task else None
    if not context or not context["cave_ready"] or task.get("status") != "published":
        abort(404)
    if context["badge"].get("locked"):
        abort(403)
    adventure = cave_adventure()

    config = as_json(task.get("config_json"), {})
    bank = [q for q in (config.get("questions") or []) if isinstance(q, dict)]
    by_id = {q.get("id"): (index, q) for index, q in enumerate(bank)}
    groups = []
    for group in adventure["groups"]:
        questions = []
        for qid in group.get("questions") or []:
            found = by_id.get(qid)
            if not found:
                continue                                   # a question the bank no longer has
            bank_index, question = found
            options = list(question.get("options") or [])
            answer = as_int_or(question.get("answer"))
            if answer is None or not (0 <= answer < len(options)):
                continue
            # the right answer sits in a different place question by question, so
            # pressing the same spot teaches nothing
            order = list(range(len(options)))
            order.insert(len(questions) % len(options), order.pop(answer))
            ordered_options = []
            for position, i in enumerate(order):
                zh, en = _cave_option_text(options[i])
                ordered_options.append({
                    "label": zh, "label_zh": zh, "label_en": en,
                    "idx": i, "ok": i == answer,
                    "key": f"{group['n']}-{len(questions)}-{position}",
                })
            questions.append({
                "id": qid, "bank": bank_index,
                "q_zh": question.get("q_zh") or "", "q_en": question.get("q_en") or "",
                "explain_zh": question.get("explain_zh") or "",
                "explain_en": question.get("explain_en") or "",
                "options": ordered_options,
            })
        if questions:
            groups.append({**group, "questions": questions})
    if not groups:
        abort(404)  # do not redirect to the form: this item has no paper

    onward = _journey_next(g.user, task)
    scenes = {**adventure, "groups": groups,
              "labels": adventure.get("labels") or {},
              "score": {"per_question": config.get("per_question", 2),
                        "max": 100, "completion": "all_questions"},
              "run_key": _cave_run_key(task_id, bank),
              "submit_url": url_for("scout_routes.cave_submit", task_id=task_id),
              "badge_url": url_for("scout_routes.badge_detail", badge_id=task["badge_id"])}
    return render_template(
        "scout/cave.html",
        task=context["task"], badge=context["badge"],
        adventure=scenes, scene_json=json.dumps(scenes, ensure_ascii=False),
        art_names=cave_images(adventure),
        badge_url=scenes["badge_url"],
        next_game=({"url": _game_url(onward["task"], onward["kind"]), **onward}
                   if onward else None),
    )


@scout_routes.post("/tasks/<task_id>/cave-submit")
@scout_required
def cave_submit(task_id: str):
    """Completing all 50 cave questions clears game 1, regardless of score.

    The server still grades each first attempt for feedback, but it only files
    a win when all 50 valid answers arrive. An incomplete POST cannot skip the
    walls, and the ordinary quiz pass mark still applies to OTHER tasks.
    """
    st = store()
    task = st.get("tasks", task_id)
    context = _task_context(g.user, task_id) if task else None
    if not context or not context["cave_ready"] or task.get("status") != "published":
        return fail(404, "task_not_found", "找不到遊戲", "Game not found")
    if context["badge"].get("locked"):
        return fail(403, "badge_locked", "請先完成上一個進度性獎章", "Finish the earlier award first")
    config = as_json(task.get("config_json"), {})
    questions = [q for q in (config.get("questions") or []) if isinstance(q, dict)]
    if len(questions) != 50:
        return fail(503, "cave_unavailable", "山洞遊戲正在準備中", "The cave is not ready yet")
    # An opened cave carries a signed snapshot of its 50 answer indices and
    # option counts. If a leader edits a question while a scout is playing,
    # grade the answers as they were shown at entry, not against the new bank.
    # Old clients with no key can still finish against the current bank.
    run_key = request.form.get("run_key")
    if run_key is not None:
        try:
            run = _cave_run_signer().loads(run_key, max_age=7 * 86400)
        except BadSignature:
            return fail(400, "cave_run_expired", "這一局的記錄已失效，請重新進入山洞。",
                        "This cave run expired. Please reopen the cave.")
        keys = run.get("questions") if isinstance(run, dict) else None
        if (not isinstance(keys, list) or len(keys) != 50
                or run.get("task") != task_id or run.get("scout") != g.user["id"]
                or any(not isinstance(row, list) or len(row) != 3
                       or row[0] != q.get("id") or type(row[1]) is not int
                       or type(row[2]) is not int or not (3 <= row[2] <= 4)
                       or not (0 <= row[1] < row[2])
                       for row, q in zip(keys, questions))):
            return fail(400, "cave_run_mismatch", "這一局與帳戶或題庫不符，請重新進入山洞。",
                        "This cave run does not match your account or its question bank.")
        expected = [row[1] for row in keys]
        sizes = [row[2] for row in keys]
    else:
        expected = [as_int_or(q.get("answer"), -1) for q in questions]
        sizes = [len(q.get("options") or []) for q in questions]

    # The cave shuffles options visually; each first attempt arrives as its
    # original bank index. Require all 50 *valid* indices before giving credit.
    # Merely POSTing an empty form or supplying impossible choices is not a run.
    answers = [request.form.get(f"q{i}") for i in range(50)]
    if any(answer is None or len(answer) > 3 or not answer.isdecimal() or
           not (0 <= int(answer) < size)
           for answer, size in zip(answers, sizes)):
        return fail(400, "cave_incomplete", "請先完成山洞的全部 50 題。",
                    "Finish all 50 cave questions before completing the game.")

    correct = sum(int(given) == answer for given, answer in zip(answers, expected))
    # The cave reports every graded tap: how many in all, and how many were
    # wrong (a wrong turn, a retry after a dead end, or a stretch that had to
    # start again). Those extra taps lower the *accuracy* — a scout who guessed
    # their way through the first stretch ends with a visibly lower figure —
    # but never the mark: the mark stays the first-try percentage, which is
    # what the progress record has always held.
    wrong_taps = min(max(as_int_or(request.form.get("wrong"), 0), 0), 500)
    tries = min(max(as_int_or(request.form.get("tries"), 0), len(expected) + wrong_taps), 1000)
    right_taps = max(tries - wrong_taps, len(expected))
    tries = right_taps + wrong_taps
    graded = {"correct": correct, "total": len(expected),
              "score": round(correct / len(expected) * 100),
              "tries": tries,
              "accuracy": round(right_taps / tries * 100) if tries else 100}
    detail = {"correct": graded["correct"], "total": graded["total"], "score": graded["score"],
              "tries": graded["tries"], "wrong": wrong_taps, "accuracy": graded["accuracy"]}
    mine = [r for r in st.list("progress_records")
            if r.get("user_id") == g.user["id"] and r.get("task_id") == task_id]
    already_done = any(r.get("status") == "completed" for r in mine)
    if not already_done:
        progress = progress_for(st, g.user["id"])
        badge = next((b for b in progress["badges"] if b["id"] == task.get("badge_id")), None)
        decorated = next((t for t in (badge or {}).get("tasks", []) if t["id"] == task_id), None)
        record = st.insert("progress_records", {
            "user_id": g.user["id"], "badge_id": task.get("badge_id"), "task_id": task_id,
            "attempt_no": len(mine) + 1, "status": "completed",
            "score": graded["score"], "leader_comment": "",
            "answers_json": json.dumps(answers, ensure_ascii=False),
            "checklist_json": None, "evidence_url": "", "reflection_text": "",
            "points_awarded": 0, "submitted_at": now_iso(),
            "decided_at": now_iso(), "decided_by": "auto",
        })
        if decorated:
            award_task_completion(st, user=g.user, task=decorated, badge=badge,
                                  record=record, awarded_by="auto")
            touch_streak(st, g.user["id"])
        audit(g.user, "cave_submit", "tasks", task_id,
              {"status": "completed", "score": graded["score"]})
    return ok(score=graded["score"], passed=True, status="completed",
              already_done=already_done, detail=detail,
              message_zh="已走完山洞，遊戲 1 通關！成績只供回顧。",
              message_en="Cave complete! Game 1 cleared; your score is for review only.")


@scout_routes.get("/tasks/<task_id>/bridge")
@scout_required
def task_bridge(task_id: str):
    """第 5 項的迷霧渡口 — the badge's second game: three stages, planks in order.

    Like the cave, the whole thing runs in the browser (so it also plays inside
    the offline demo file) from the content in `content/member-badge/river.json`.
    The route hands over the three teaching cards, their planks and every line of
    text. Finishing all three stages crosses the river, but the crossing is only
    the first half of game 2: the scout then sees the leader for the 考核
    (recite the motto, Promise and Law, and say how the Law is lived), and brings
    back the leader's code. `POST /tasks/<id>/bridge-submit` files the crossing;
    `POST /tasks/<id>/bridge-code` files the completion.
    """
    st = store()
    task = st.get("tasks", task_id)
    context = _task_context(g.user, task_id) if task else None
    if not context or not context["bridge_ready"] or task.get("status") != "published":
        abort(404)
    if context["badge"].get("locked"):
        abort(403)
    adventure = river_adventure()
    stages = []
    for stage in adventure["stages"]:
        planks = [p for p in (stage.get("planks") or []) if p.get("key")]
        if not planks:
            continue
        stages.append({**stage, "planks": planks})
    if not stages:
        abort(404)

    # where this scout stands: a crossing already laid (waiting on the code), or
    # the item already finished. The game opens straight onto the assess card in
    # the first case, so the code can be typed without laying the planks again.
    mine = [r for r in st.list("progress_records")
            if r.get("user_id") == g.user["id"] and r.get("task_id") == task_id]
    completed_now = any(r.get("status") == "completed" for r in mine)
    crossed_now = not completed_now and any(r.get("status") == "crossed" for r in mine)
    onward = _journey_next(g.user, task)

    scenes = {
        **adventure,
        "stages": stages,
        "labels": adventure.get("labels") or {},
        "assess": adventure.get("assess") or {},
        "submit_url": url_for("scout_routes.bridge_submit", task_id=task_id),
        "code_url": url_for("scout_routes.bridge_code", task_id=task_id),
        "badge_url": url_for("scout_routes.badge_detail", badge_id=task["badge_id"]),
        "plank_total": sum(len(stage["planks"]) for stage in stages),
        "crossed_now": crossed_now,
        "completed_now": completed_now,
        "next_game": ({"name_zh": onward["name_zh"], "name_en": onward["name_en"],
                       "url": _game_url(onward["task"], onward["kind"])}
                      if onward else None),
    }
    config = context["task"].get("config_json") or {}
    config = json.loads(config) if isinstance(config, str) else config
    return render_template(
        "scout/bridge.html",
        task=context["task"], badge=context["badge"],
        adventure=scenes, scene_json=json.dumps(scenes, ensure_ascii=False),
        art_names=river_images(adventure),
        badge_url=scenes["badge_url"],
        crossed_now=crossed_now,
        # the item's own revision links (promise, Law, the leader's sheet)
        links=[row for row in (config.get("links") or []) if row.get("url")],
    )


@scout_routes.post("/tasks/<task_id>/bridge-submit")
@scout_required
def bridge_submit(task_id: str):
    """Laying every stage crosses the river — but a crossing is not the item yet.

    The record goes in as `crossed`: the words are proven in order, and the scout
    is sent to the leader for the 考核 (recite, and explain how the Law is lived).
    Item 5 is cleared only when the leader's code arrives at bridge-code below.
    """
    st = store()
    task = st.get("tasks", task_id)
    context = _task_context(g.user, task_id) if task else None
    if not context or not context["bridge_ready"] or task.get("status") != "published":
        return fail(404, "task_not_found", "找不到遊戲", "Game not found")
    if context["badge"].get("locked"):
        return fail(403, "badge_locked", "請先完成上一個進度性獎章", "Finish the earlier award first")
    adventure = river_adventure()
    stages = [{**stage, "planks": [p for p in (stage.get("planks") or []) if p.get("key")]}
              for stage in (adventure.get("stages") or [])]
    stages = [stage for stage in stages if stage["planks"]]
    if len(stages) < 3:
        return fail(503, "bridge_unavailable", "渡口遊戲正在準備中", "The crossing is not ready yet")

    # The client reports each stage's laid order as plank keys. A stage may carry
    # planks that read the same — all seven points of the Law begin with 童軍 —
    # so the board is judged by what each plank says, not by which copy was
    # lifted: any copy of the right word is the right word. Every stage must
    # still arrive complete, with no key lifted twice: a half-filled bridge
    # cannot be handed in as a crossing.
    for stage in stages:
        wanted = [(p.get("zh") or p.get("en") or "") for p in stage["planks"]]
        by_key = {p["key"]: (p.get("zh") or p.get("en") or "") for p in stage["planks"]}
        given = request.form.getlist(f"stage{stage['n']}")
        laid = [by_key[key] for key in given if key in by_key]
        if (len(given) != len(wanted) or len(set(given)) != len(given)
                or len(laid) != len(given) or laid != wanted):
            return fail(400, "bridge_incomplete",
                        f"第 {stage['n']} 關的木板還未排好，請先鋪好三關。",
                        f"Stage {stage['n']} of the crossing is not finished yet.")

    mine = [r for r in st.list("progress_records")
            if r.get("user_id") == g.user["id"] and r.get("task_id") == task_id]
    already_done = any(r.get("status") == "completed" for r in mine)
    already_crossed = any(r.get("status") == "crossed" for r in mine)
    if not already_done and not already_crossed:
        st.insert("progress_records", {
            "user_id": g.user["id"], "badge_id": task.get("badge_id"), "task_id": task_id,
            "attempt_no": len(mine) + 1, "status": "crossed", "score": None,
            "leader_comment": "",
            "answers_json": json.dumps(
                {f"stage{stage['n']}": request.form.getlist(f"stage{stage['n']}")
                 for stage in stages}, ensure_ascii=False),
            "checklist_json": None, "evidence_url": "", "reflection_text": "",
            "points_awarded": 0, "submitted_at": now_iso(),
            "decided_at": "", "decided_by": "",
        })
        audit(g.user, "bridge_submit", "tasks", task_id,
              {"status": "crossed", "stages": len(stages)})
    return ok(passed=already_done, status="completed" if already_done else "crossed",
              already_done=already_done, detail={"stages": len(stages)},
              message_zh="橋鋪好了！請找領袖考核：背誦銘言、誓詞、規律，並講出日常生活怎樣實行；考核後輸入領袖代碼，第 5 項就完成。",
              message_en="The bridge holds! Now see your leader: recite the motto, the Promise and the Law, say how you live them, then enter the leader's code to finish item 5.")


def _bridge_assess_code(st) -> str:
    """The leader's word that finishes game 2 — given by hand after the 考核.

    Default 82BP. A `bridge_assess_code` row in settings can change it (the
    leader edits the settings sheet); the comparison ignores case, spaces and
    full-width typing, so ８２ｂｐ works just as well as 82BP.
    """
    raw = (st.settings().get("bridge_assess_code") or "82BP")
    return unicodedata.normalize("NFKC", str(raw)).replace(" ", "").upper().strip()


def _bridge_code_normalise(value: str) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).replace(" ", "").upper().strip()


@scout_routes.post("/tasks/<task_id>/bridge-code")
@scout_required
def bridge_code(task_id: str):
    """領袖考核後的代碼 — the second half of game 2.

    The crossing (bridge-submit) proves the words can be laid in order; this
    proves a leader heard the scout recite them and explain how the Law is
    lived. The code only counts once the crossing is on file — a code alone
    cannot skip the bridge — and only the right code completes the item.
    """
    st = store()
    task = st.get("tasks", task_id)
    context = _task_context(g.user, task_id) if task else None
    if not context or not context["bridge_ready"] or task.get("status") != "published":
        return fail(404, "task_not_found", "找不到遊戲", "Game not found")
    if context["badge"].get("locked"):
        return fail(403, "badge_locked", "請先完成上一個進度性獎章", "Finish the earlier award first")
    assess = (river_adventure().get("assess") or {})

    mine = [r for r in st.list("progress_records")
            if r.get("user_id") == g.user["id"] and r.get("task_id") == task_id]
    if any(r.get("status") == "completed" for r in mine):
        return ok(passed=True, status="completed", already_done=True,
                  message_zh="第 5 項已完成，不用再輸入代碼。",
                  message_en="Item 5 is already complete — no code needed.")
    crossed = next((r for r in mine if r.get("status") == "crossed"), None)
    if crossed is None:
        return fail(400, "bridge_not_crossed",
                    "請先完成渡口遊戲（鋪好三關木板），再找領袖考核。",
                    "Finish the crossing first — lay all three stages — then see your leader.")

    given = _bridge_code_normalise(request.form.get("code"))
    if given != _bridge_assess_code(st):
        audit(g.user, "bridge_code_wrong", "tasks", task_id, {})
        zh = assess.get("code_wrong_zh") or "代碼不對。請向領袖再問一次。"
        en = assess.get("code_wrong_en") or "That code does not match. Ask your leader again."
        if wants_json():
            return fail(400, "bridge_code_wrong", zh, en)
        return redirect(url_for("scout_routes.badge_requirements",
                                badge_id=task["badge_id"], assess="wrong"))

    progress = progress_for(st, g.user["id"])
    badge = next((b for b in progress["badges"] if b["id"] == task.get("badge_id")), None)
    decorated = next((t for t in (badge or {}).get("tasks", []) if t["id"] == task_id), None)
    record = st.insert("progress_records", {
        "user_id": g.user["id"], "badge_id": task.get("badge_id"), "task_id": task_id,
        "attempt_no": len(mine) + 1, "status": "completed", "score": 100,
        "leader_comment": "領袖考核通過：已背誦銘言、誓詞、規律，並講解日常生活怎樣實行。",
        "answers_json": crossed.get("answers_json"),
        "checklist_json": None, "evidence_url": "", "reflection_text": "",
        "points_awarded": 0, "submitted_at": now_iso(),
        "decided_at": now_iso(), "decided_by": "leader-code",
    })
    if decorated:
        award_task_completion(st, user=g.user, task=decorated, badge=badge,
                              record=record, awarded_by="leader-code")
        touch_streak(st, g.user["id"])
    audit(g.user, "bridge_code", "tasks", task_id, {"status": "completed"})
    if wants_json():
        return ok(passed=True, status="completed", already_done=False,
                  detail={"code": True},
                  message_zh="✓ 代碼正確 — 遊戲 2 通關，第 5 項完成！",
                  message_en="✓ The code is right — game 2 cleared, and item 5 with it!")
    return redirect(url_for("scout_routes.badge_requirements",
                            badge_id=task["badge_id"], assess="ok"))


@scout_routes.post("/tasks/<task_id>/submit")
@scout_required
def submit(task_id: str):
    st = store()
    user = g.user
    task = st.get("tasks", task_id)
    if not task:
        return fail(404, "task_not_found", "找不到任務", "Task not found")

    # A draft task is not part of any scout's path, but the scout may still hold
    # an old link to it — tell them plainly instead of pretending it is missing.
    if task.get("status") != "published":
        return fail(403, "task_not_published", "此任務尚未開放", "This task is not open yet")

    progress = progress_for(st, user["id"])
    badge = next((b for b in progress["badges"] if b["id"] == task.get("badge_id")), None)
    decorated = next((t for t in (badge or {}).get("tasks", []) if t["id"] == task_id), None)
    if not decorated:
        return fail(404, "task_not_found", "找不到任務", "Task not found")
    if badge and badge["locked"]:
        return fail(403, "badge_locked", "請先完成上一個進度性獎章", "Finish the earlier award first")
    if _is_badge_cave_task(task, badge):
        # No second exam: all item-4 credits come from playing the cave.
        return fail(403, "play_the_cave", "第 4 項請在第一個區域完成山洞遊戲，不需要另做試卷。",
                    "Play the cave in area one to finish item 4; no separate paper is needed.")
    if _is_badge_bridge_task(task, badge):
        return fail(403, "play_the_bridge",
                    "第 5 項請在第二個區域完成渡口遊戲：過橋後找領袖考核（背誦及講解規律），輸入領袖代碼即完成。",
                    "Cross the river in area two to finish item 5: after the crossing, see your leader and enter the leader's code.")

    mine = [r for r in st.list("progress_records")
            if r.get("user_id") == user["id"] and r.get("task_id") == task_id]
    if any(r.get("status") == "completed" for r in mine):
        return fail(409, "already_done", "此任務已完成", "Already completed")
    if any(r.get("status") == "pending" for r in mine):
        return fail(409, "awaiting_review", "已提交，等待領袖核實", "Already submitted — waiting for a leader")

    body = request.get_json(silent=True) or {}
    form = request.form
    answers = body.get("answers")
    if answers is None and task.get("type") == "quiz":
        config = json.loads(task.get("config_json") or "{}") if isinstance(task.get("config_json"), str) else (task.get("config_json") or {})
        answers = [request.form.get(f"q{i}") for i in range(len(config.get("questions") or []))]
    checklist = body.get("checklist")
    if checklist is None and task.get("type") == "checklist":
        config = json.loads(task.get("config_json") or "{}") if isinstance(task.get("config_json"), str) else (task.get("config_json") or {})
        checklist = [bool(request.form.get(f"item{i}")) for i in range(len(config.get("items") or []))]

    submission = {
        "answers": answers,
        "checklist": checklist,
        "evidence_url": (body.get("evidence_url") or form.get("evidence_url") or "").strip(),
        # a reflection has its own box; a 領袖考核 item has "notes" — both land in
        # the one free-text column so the leader reads it in the review queue
        "reflection_text": (body.get("reflection_text") or form.get("reflection_text")
                            or body.get("notes") or form.get("notes") or "").strip(),
    }
    evaluation = evaluate_submission(task, submission, st.settings())
    attempt_no = len(mine) + 1

    record = st.insert("progress_records", {
        "user_id": user["id"], "badge_id": task.get("badge_id"), "task_id": task_id,
        "attempt_no": attempt_no, "status": evaluation["status"], "score": evaluation.get("score") or 0,
        "answers_json": json.dumps(submission["answers"], ensure_ascii=False) if submission["answers"] is not None else None,
        "checklist_json": json.dumps(submission["checklist"], ensure_ascii=False) if submission["checklist"] is not None else None,
        "evidence_url": submission["evidence_url"], "reflection_text": submission["reflection_text"],
        "leader_comment": "", "points_awarded": 0, "submitted_at": now_iso(),
        "decided_at": now_iso() if evaluation["auto_award"] else "",
        "decided_by": "auto" if evaluation["auto_award"] else "",
    })

    events: list[dict] = []
    if evaluation["auto_award"]:
        result = award_task_completion(st, user=user, task=task, badge=badge, record=record, awarded_by="auto")
        events = result["events"]
        touch_streak(st, user["id"])
    audit(user, "submit_task", "tasks", task_id, {"status": evaluation["status"], "score": evaluation.get("score")})

    fresh = progress_for(st, user["id"])
    if wants_json():
        return ok(
            record_id=record["id"], status=evaluation["status"], score=evaluation.get("score"),
            passed=evaluation["auto_award"], feedback_zh=evaluation["feedback_zh"],
            feedback_en=evaluation["feedback_en"], detail=evaluation.get("detail") or {},
            events=events,
            progress={"overall": fresh["overall"], "stats": fresh["stats"],
                      "badges": [{"id": b["id"], "percent": b["percent"], "earned": b["earned"],
                                  "locked": b["locked"], "tasks_done": b["tasks_done"],
                                  "tasks_total": b["tasks_total"]} for b in fresh["badges"]]},
        )

    flash({"kind": "success" if evaluation["status"] == "completed" else "warn",
           "zh": evaluation["feedback_zh"], "en": evaluation["feedback_en"],
           "events": events}, "result")
    # `?done=`/`?redo=` carries the same news in the URL, so it still shows up
    # where cookies are refused (the preview iframe).
    if evaluation["status"] == "completed":
        return redirect(url_for("scout_routes.badges", done=task_id))
    return redirect(url_for("scout_routes.task_player", task_id=task_id, redo=1))


# ── creating your own password (asked once, on the way in) ──────────────────

@scout_routes.get("/welcome")
@scout_required
def welcome():
    """Mandatory first-entry step: password AND contact email before Home.

    A scout with no password enters without typing one; a leader's temporary
    password is checked at the door. Both routes finish setup here. Existing
    accounts that completed setup are redirected to their home page.
    """
    if not needs_first_time(g.user):
        return redirect(url_for("scout_routes.home"))
    return render_template("auth/welcome.html",
                           patrol=g.user.get("patrol") or "",
                           patrol_label=patrol_label(g.user.get("patrol") or ""),
                           scout=public_user(g.user),
                           email=g.user.get("email") or "",
                           err=request.args.get("err", ""))


@scout_routes.post("/welcome")
@scout_required
def save_password():
    """Complete onboarding atomically; neither field may be omitted."""
    from ..auth import set_password, valid_email

    if not needs_first_time(g.user):
        if wants_json():
            return fail(409, "setup_complete", "帳戶已完成設定。", "This account is already set up.")
        return redirect(url_for("scout_routes.home"))
    st = store()
    form = request.form if not request.is_json else (request.get_json(silent=True) or {})
    password = (form.get("password") or "").strip()
    confirm = (form.get("confirm") or "").strip()
    email = (form.get("email") or "").strip()

    if len(password) < 6:
        return _setup_problem("密碼最少 6 個字", "Password must be at least 6 characters", "short")
    if password != confirm:
        return _setup_problem("兩次輸入的密碼不同", "The two passwords do not match", "mismatch")
    if not email:
        return _setup_problem("請填寫聯絡電郵", "Enter a contact email address", "missing_email")
    if not valid_email(email):
        return _setup_problem("電郵格式不正確", "That email address looks wrong", "email")

    set_password(st, g.user, password, email)
    audit(g.user, "first_time_password", "users", g.user["id"])

    if wants_json():
        return ok(message_zh="密碼及電郵已設定！下次登入就用這個密碼。",
                  message_en="Password and email saved! Use your new password next time.")
    flash({"kind": "success", "celebrate": True,
           "zh": "🎉 密碼及電郵已設定！下次登入時，輸入這個密碼就可以進來。",
           "en": "🎉 Password and email saved! Next time, sign in with your new password."}, "result")
    return redirect(url_for("scout_routes.home", ok="password"))


def _setup_problem(zh: str, en: str, code: str = "short"):
    if wants_json():
        return fail(400, "bad_email" if code in {"missing_email", "email"} else "bad_password", zh, en)
    flash({"kind": "warn", "zh": zh, "en": en}, "result")
    return redirect(url_for("scout_routes.welcome", err=code))


# ── evidence upload ─────────────────────────────────────────────────────────

@scout_routes.post("/upload")
@scout_required
def upload():
    """Accepts a data-URL (JSON) or a real file post; returns a link either way."""
    st = store()
    if not (st.settings_cached().get("feature_flags") or {}).get("evidence_upload", True):
        return fail(403, "upload_disabled", "上載功能未開放", "Uploads are disabled")

    data: bytes
    name, mime_type = "", ""
    if request.files.get("file"):
        blob = request.files["file"]
        name, mime_type = blob.filename or "evidence.jpg", blob.mimetype or "image/jpeg"
        data = blob.read()
    else:
        body = request.get_json(silent=True) or {}
        name = body.get("filename") or "evidence.jpg"
        mime_type = body.get("mimeType") or ""
        data_url = str(body.get("dataUrl") or "")
        if not data_url.startswith("data:") or ";base64," not in data_url:
            return fail(400, "bad_data", "檔案格式不正確", "Invalid file data")
        header, _, encoded = data_url.partition(";base64,")
        mime_type = mime_type or header[5:]
        import base64

        try:
            data = base64.b64decode(encoded)
        except Exception:
            return fail(400, "bad_data", "檔案格式不正確", "Invalid file data")
        if not mime_type.startswith("image/"):
            return fail(400, "bad_data", "只可上載相片", "Images only")

    if len(data) > 5 * 1024 * 1024:
        return fail(413, "too_big", "檔案不可超過 5MB", "File must be under 5MB")

    uploaded = st.upload_file(name=name, mime_type=mime_type, data=data)
    audit(g.user, "upload_evidence", "users", g.user["id"], {"stored": uploaded.get("stored")})
    return ok(url=uploaded["url"], id=uploaded["id"], stored=uploaded.get("stored"))


def _not_open_yet(zh: str, en: str):
    """A page the unit has not switched on yet: go home and say so.

    The feature flags in 設定 decide which extras are live; this keeps a
    half-finished corner from being reachable by typing its URL.
    """
    flash({"kind": "warn", "zh": f"{zh}未開放 — 領袖可在設定中開啟。",
           "en": f"{en} is not open yet — a leader can switch it on in Settings."}, "result")
    return redirect(url_for("scout_routes.home"))


# ── 獎品 (the only place points are shown) ──────────────────────────────────

@scout_routes.get("/rewards")
@scout_required
def rewards():
    st = store()
    if not (st.settings_cached().get("feature_flags") or {}).get("redeem", False):
        return _not_open_yet("獎品", "Rewards")
    user = g.user
    summary = points_summary(st, user["id"])
    items = []
    for reward in st.list("rewards"):
        if reward.get("active") is False:
            continue
        cost = int(float(reward.get("points_cost") or 0))
        items.append({
            **reward, "points_cost": cost,
            "affordable": summary["balance"] >= cost,
            "short_by": max(0, cost - summary["balance"]),
            "stock": reward.get("stock"),
        })
    items.sort(key=lambda r: r["points_cost"])
    return render_template("scout/rewards.html", summary=summary, rewards=items,
                           redemption_enabled=bool((st.settings_cached().get("feature_flags") or {}).get("redeem")))


# ── 紀錄 (timeline) ─────────────────────────────────────────────────────────

@scout_routes.get("/history")
@scout_required
def history():
    st = store()
    user = g.user
    tasks = {t["id"]: t for t in st.list("tasks")}
    badges = {b["id"]: b for b in st.list("badges")}
    records = [r for r in st.list("progress_records") if r.get("user_id") == user["id"]]
    awards = [a for a in st.list("badge_awards") if a.get("user_id") == user["id"]]

    timeline = []
    for record in records:
        task = tasks.get(record.get("task_id"), {})
        timeline.append({
            "kind": "task", "at": record.get("decided_at") or record.get("submitted_at"),
            "status": record.get("status"),
            "title_zh": task.get("title_zh", ""), "title_en": task.get("title_en", ""),
            "type": task.get("type", ""), "score": record.get("score"),
            "badge_zh": badges.get(record.get("badge_id"), {}).get("title_zh", ""),
            "badge_en": badges.get(record.get("badge_id"), {}).get("title_en", ""),
            "comment": record.get("leader_comment", ""),
            "task_id": record.get("task_id"),
            "attempt_no": record.get("attempt_no"),
        })
    for award in awards:
        badge = badges.get(award.get("badge_id"), {})
        timeline.append({
            "kind": "badge", "at": award.get("awarded_at"), "status": "earned",
            "title_zh": badge.get("title_zh", ""), "title_en": badge.get("title_en", ""),
            "emoji": badge.get("emoji", "🎖"), "color": badge.get("color", ""),
            "image_url": badge.get("image_url", ""),
        })
    timeline.sort(key=lambda row: str(row.get("at") or ""), reverse=True)
    return render_template("scout/history.html", timeline=timeline, stats=progress_for(st, user["id"])["stats"])


# ── 龍虎榜 ─────────────────────────────────────────────────────────────────

@scout_routes.get("/leaderboard")
@scout_required
def leaderboard_page():
    st = store()
    settings = st.settings_cached()
    if not (settings.get("feature_flags") or {}).get("leaderboard", False):
        return _not_open_yet("龍虎榜", "Leaderboard")

    period = request.args.get("period", "all")
    scope = request.args.get("scope", "unit")
    patrol = request.args.get("patrol", "")
    from ..engine import leaderboard as build_board

    board = build_board(st, scope=scope, patrol=patrol, period=period, current_user_id=g.user["id"])
    current = next((row for row in board["rows"] if row["is_me"]), None)
    return render_template("scout/leaderboard.html", disabled=False, rows=board["rows"], current=current,
                           period=period, scope=scope, patrol=patrol,
                           patrols=settings.get("patrols") or [])


# ── JSON views the game layer uses to refresh itself ───────────────────────

@scout_routes.get("/api/me")
@scout_required
def api_me():
    st = store()
    progress = progress_for(st, g.user["id"])
    return ok(user=public_user(g.user), stats=progress["stats"], overall=progress["overall"],
              badges=[{"id": b["id"], "code": b["code"], "title_zh": b["title_zh"], "title_en": b["title_en"],
                       "emoji": b["emoji"], "image_url": b["image_url"], "color": b["color"],
                       "percent": b["percent"], "earned": b["earned"], "locked": b["locked"],
                       "tasks_done": b["tasks_done"], "tasks_total": b["tasks_total"]} for b in progress["badges"]])


@scout_routes.get("/api/me/progress")
@scout_required
def api_progress():
    st = store()
    progress = progress_for(st, g.user["id"])
    return ok(stats=progress["stats"], overall=progress["overall"],
              badges=progress["badges"], suggestions=build_suggestions(st, g.user, progress))


@scout_routes.get("/api/me/points-summary")
@scout_required
def api_points():
    return ok(**points_summary(store(), g.user["id"]))


@scout_routes.get("/api/tasks/next")
@scout_required
def api_next_task():
    st = store()
    progress = progress_for(st, g.user["id"])
    nxt = progress["overall"]["next_task"]
    return ok(next=nxt, overall=progress["overall"])


@scout_routes.get("/api/leaderboard")
@scout_required
def api_leaderboard():
    from ..engine import leaderboard as build_board

    board = build_board(store(), scope=request.args.get("scope", "unit"),
                        patrol=request.args.get("patrol", ""), period=request.args.get("period", "all"),
                        current_user_id=g.user["id"])
    return ok(**board)
