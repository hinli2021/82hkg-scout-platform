"""Content that ships with the platform.

Two things live under `content/member-badge/`:

* `guide.json` — the 11 items of the 會員章 (Membership Badge) with the unit's
  own requirements, assessment method and resource links.
* `item4-question-bank.json` + `item4-answer-key.json` — the original 50
  item-4 questions (世界及香港童軍運動). The bank retains its old standalone
  paper scoring metadata for reference; the cave reuses the QUESTIONS but
  clears game 1 when all 50 are finished, regardless of score.

They are plain JSON so a leader can edit the wording or the questions without
touching Python. The answer key is merged into the task on the server and is
stripped again before anything reaches the browser (see `engine.strip_answers`).
"""
from __future__ import annotations

import json
import os

CONTENT_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "content")
MEMBER_BADGE_DIR = os.path.join(CONTENT_ROOT, "member-badge")


def _read_json(path: str):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def member_badge_guide() -> dict:
    """The 11-item guide, or {} when a unit has not set one up."""
    guide = _read_json(os.path.join(MEMBER_BADGE_DIR, "guide.json")) or {}
    items = [item for item in (guide.get("items") or []) if isinstance(item, dict)]
    if not items:
        return {}
    return {**guide, "items": items}


def item4_questions() -> list[dict]:
    """The item-4 questions in the shape the task player renders.

    Each question carries its answer and an explanation; both are removed by
    `engine.strip_answers` on the way out, and the explanation is only handed
    back after a submission has been marked.
    """
    bank = _read_json(os.path.join(MEMBER_BADGE_DIR, "item4-question-bank.json")) or {}
    key = _read_json(os.path.join(MEMBER_BADGE_DIR, "item4-answer-key.json")) or {}
    answers = {row.get("id"): row for row in (key.get("answers") or []) if isinstance(row, dict)}
    parts = {part.get("id"): part for part in (bank.get("parts") or []) if isinstance(part, dict)}

    questions: list[dict] = []
    for row in (bank.get("questions") or []):
        if not isinstance(row, dict):
            continue
        answer = answers.get(row.get("id")) or {}
        part = parts.get(row.get("partId")) or {}
        prompt = row.get("prompt") or ""
        questions.append({
            "id": row.get("id"),
            "part": row.get("partId"),
            "part_zh": part.get("title") or row.get("partTitle") or "",
            "part_en": part.get("titleEn") or part.get("title") or row.get("partTitle") or "",
            "q_zh": prompt, "q_en": prompt,          # the paper is set in Chinese
            "options": row.get("options") or [],
            "answer": answer.get("answerIndex"),
            "explain_zh": answer.get("explanation") or "",
            "review_note": answer.get("reviewNote") or "",
        })
    return [q for q in questions if isinstance(q.get("answer"), int)]


def item4_meta() -> dict:
    bank = _read_json(os.path.join(MEMBER_BADGE_DIR, "item4-question-bank.json")) or {}
    scoring = bank.get("scoring") or {}
    return {
        "title_zh": bank.get("title") or "第4項｜認識世界及香港童軍運動發展",
        "per_question": scoring.get("pointsPerQuestion", 2),
        "max_score": scoring.get("maxScore", 100),
        "pass_score": scoring.get("passScore", 80),  # historical paper only; cave ignores it
        "parts": [{"id": p.get("id"), "title": p.get("title")}
                  for p in (bank.get("parts") or []) if isinstance(p, dict)],
    }

def cave_adventure() -> dict:
    """第 4 項的洞穴歷險（the cave game），or {} when it is not set up.

    The story — the four wall paintings, their timelines, the dead ends and the
    exit — lives in `cave.json`; each group names the questions it teaches for,
    so the wording and the answer key still live in the question bank and only
    there. Change the story file and the game changes with it.
    """
    adventure = _read_json(os.path.join(MEMBER_BADGE_DIR, "cave.json")) or {}
    groups = [row for row in (adventure.get("groups") or []) if isinstance(row, dict)]
    if not groups:
        return {}
    return {**adventure, "groups": groups}


def river_adventure() -> dict:
    """第 5 項的迷霧渡口（the bridge game），or {} when it is not set up.

    Three stages — 銘言, 誓詞, 規律 — and each one teaches first, then asks for
    the planks in order. Everything a leader may rewrite (the words on the
    boards, the explanations, every line of interface text) lives in
    `river.json`; the game only knows how to lay planks.
    """
    adventure = _read_json(os.path.join(MEMBER_BADGE_DIR, "river.json")) or {}
    stages = [row for row in (adventure.get("stages") or [])
              if isinstance(row, dict) and (row.get("planks") or [])]
    if not stages:
        return {}
    return {**adventure, "stages": stages}


def drill_manual() -> dict:
    """第 6 項的步操訓練場（the drill game），or {} when it is not set up.

    Seven chapters of the leader's 《步操手冊》 — positions, turns, the salute,
    paces, quick time, the seven fall-in hand signs and the right dress — each
    movement carrying its manual page, its points and one self-check question.
    Everything a leader may rewrite lives in `drill.json`; the game only knows
    how to turn the pages. Finishing every check sends the scout to a leader
    for the 考核 in person, and the leader's code completes the item.
    """
    manual = _read_json(os.path.join(MEMBER_BADGE_DIR, "drill.json")) or {}
    sections = []
    for section in (manual.get("sections") or []):
        if not isinstance(section, dict):
            continue
        moves = [m for m in (section.get("moves") or [])
                 if isinstance(m, dict) and (m.get("check") or {}).get("q_zh")
                 and (m.get("check") or {}).get("options_zh")]
        if moves:
            sections.append({**section, "moves": moves})
    if not sections:
        return {}
    return {**manual, "sections": sections}


def drill_required_moves(manual: dict) -> list[dict]:
    """The movements game 3 actually asks the scout to clear, in play order.

    The manual file may also carry background movements that are not part of
    either section's stages (for example Stand Easy and the fall-in page
    itself). They stay readable in the content, but the game only files the
    studying once every movement named by `game.sign_stages` and
    `game.movement_stages` has been answered. Older content without those
    stage lists falls back to every movement in the manual.
    """
    by_id: dict[str, dict] = {}
    ordered: list[dict] = []
    for section in (manual.get("sections") or []):
        for move in (section.get("moves") or []):
            if isinstance(move, dict) and move.get("id") and move["id"] not in by_id:
                by_id[move["id"]] = move
                ordered.append(move)
    game = manual.get("game") or {}
    required: list[dict] = []
    seen: set[str] = set()
    for key in ("sign_stages", "movement_stages"):
        for stage in (game.get(key) or []):
            for move_id in (stage or []):
                if move_id in by_id and move_id not in seen:
                    seen.add(move_id)
                    required.append(by_id[move_id])
    return required or ordered


def drill_images(manual: dict) -> list[str]:
    """Every picture the drill ground can show, in the order first needed.

    The chapter pages are the manual's own scans (portrait A5); the ridge
    painting stands behind the intro, the assess card and every movement that
    carries no manual page of its own (the right dress).
    """
    art = manual.get("images") or {}
    names: list[str] = []

    def take(name):
        if name and name not in names:
            names.append(name)

    take((manual.get("intro") or {}).get("image") or art.get("ridge"))
    for section in manual.get("sections") or []:
        for move in section.get("moves") or []:
            for key in ("img", "img2", "img3", "figure"):
                take(move.get(key))
    return names


def river_images(adventure: dict) -> list[str]:
    """Every picture the crossing can show, in the order it is first needed."""
    art = adventure.get("images") or {}
    names: list[str] = []

    def take(name):
        if name and name not in names:
            names.append(name)

    take((adventure.get("intro") or {}).get("image"))
    for key in ("bank", "crossed", "slip"):
        take(art.get(key))
    # each stage may bring its own painting (the motto, the Promise, the Law)
    take((adventure.get("planks") or {}).get("image"))
    for stage in adventure.get("stages") or []:
        take((stage or {}).get("image"))
    take((adventure.get("wrong") or {}).get("image"))
    take((adventure.get("crossed") or {}).get("image"))
    return names


def cave_images(adventure: dict) -> list[str]:
    """Every picture the game can show, in the order it is first needed.

    The scout walks entrance → walls → chambers and dead ends → the exit, and
    the same chamber or dead-end painting may stand behind several questions.
    """
    names: list[str] = []

    def take(name):
        if name and name not in names:
            names.append(name)

    take((adventure.get("intro") or {}).get("image"))
    for group in adventure.get("groups") or []:
        take((group.get("wall") or {}).get("image"))
    for name in adventure.get("chambers") or []:
        take(name)
    for name in adventure.get("deadends") or []:
        take(name)
    # the setback stories: each one sends the scout back to a stretch's wall
    for story in (adventure.get("setbacks") or {}).get("stories") or []:
        take((story or {}).get("image"))
    take((adventure.get("exit") or {}).get("image"))
    return names
