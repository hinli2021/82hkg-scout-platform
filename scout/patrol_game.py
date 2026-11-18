"""遊戲 5：小隊名冊卡 — knowing your patrol (item 2, M02).

The roster is read live from the platform's own records, never copied into a
separate list that can go stale:

  • members      — scout accounts in the same patrol (leaders create the
                   account when a scout joins, so a new member appears in
                   the game automatically, and a member who leaves is gone)
  • 職位／興趣／強項 — each member's own profile (`profiles`), which the
                   member keeps up to date on 我的個人檔案
  • 聯絡          — the member whose 職位 contains 「聯絡」 (one per patrol);
                   the way to reach them is the email on their account

Members who have not finished their profile still appear — the game tests
their name and 職位 — but their card says so, and no interest/strength
question is drawn from an empty field.
"""
from __future__ import annotations

import random

CONTACT_WORD = "聯絡"
NO_POSITION = {"value": "", "zh": "暫時沒有職位", "en": "No position yet"}


def _name(user: dict, lang: str) -> str:
    if lang == "en":
        return str(user.get("display_name_en") or user.get("display_name_zh") or user.get("username") or "")
    return str(user.get("display_name_zh") or user.get("display_name_en") or user.get("username") or "")


def patrol_members(st, user: dict) -> list[dict]:
    """Every active scout in `user`'s patrol, with their profile folded in."""
    from .routes.profile_routes import load_profile, profile_complete

    patrol = str(user.get("patrol") or "").strip().lower()
    members: list[dict] = []
    for row in st.list("users"):
        if row.get("role") != "scout" or row.get("status") != "active":
            continue
        if str(row.get("patrol") or "").strip().lower() != patrol:
            continue
        profile = load_profile(st, row["id"])
        position = str(profile.get("position") or "").strip()
        members.append({
            "id": row["id"],
            "name_zh": _name(row, "zh"),
            "name_en": _name(row, "en"),
            "avatar": str(row.get("avatar") or "🦊"),
            "position_zh": str(profile.get("position_zh") or position),
            "position_en": str(profile.get("position_en") or position),
            "position": position,
            "interests": str(profile.get("interests") or "").strip(),
            "experience": str(profile.get("experience") or "").strip(),
            "share": str(profile.get("share") or "").strip(),
            "strength": str(profile.get("strength") or "").strip(),
            "complete": profile_complete(profile),
            "is_self": row["id"] == user["id"],
            "is_contact": CONTACT_WORD in position,
            # The contact's email is the way to reach them; only the contact
            # member's address is handed to the game, nobody else's.
            "contact_email": str(row.get("email") or "").strip()
            if CONTACT_WORD in position else "",
        })
    # The contact first, then leaders of the patrol, then by name — the order
    # a scout would be introduced to the patrol.
    def order(member: dict):
        rank = 0 if member["is_contact"] else 1 if member["position"] else 2
        return (rank, member["name_zh"])

    return sorted(members, key=order)


def contact_of(members: list[dict]) -> dict | None:
    return next((m for m in members if m["is_contact"]), None)


def _options(rng: random.Random, pool: list[dict], target: dict, label: str) -> list[dict]:
    others = [m for m in pool if m["id"] != target["id"]]
    rng.shuffle(others)
    chosen = [target] + others[:3]
    rng.shuffle(chosen)
    return [{"value": m["id"], "zh": m[f"name_zh"], "en": m[f"name_en"]} for m in chosen]


MAX_QUESTIONS = 12


def build_questions(members: list[dict], viewer_id: str, seed: int) -> tuple[list[dict], dict]:
    """(questions for the page, {question id: right value} for the server).

    Right answers never reach the browser: the page shows the prompts and
    options only, and the server signs the key into the run token.
    """
    rng = random.Random(seed)
    others = [m for m in members if m["id"] != viewer_id]
    questions: list[dict] = []
    key: dict[str, str] = {}

    def add(kind: str, target: dict, zh: str, en: str, options: list[dict], answer: str,
            member_id: str = ""):
        qid = f"q{len(questions) + 1}"
        questions.append({"id": qid, "kind": kind, "zh": zh, "en": en,
                          "options": options, "member_id": member_id})
        key[qid] = answer

    contact = contact_of(members)
    if contact:
        add("contact_who", contact,
            "誰是本小隊的聯絡？", "Who is your patrol's contact?",
            _options(rng, members, contact, "name"), contact["id"], contact["id"])
    else:
        qid = f"q{len(questions) + 1}"
        questions.append({"id": qid, "kind": "contact_none",
                          "zh": "本小隊現在有誰擔任聯絡？",
                          "en": "Who is your patrol's contact right now?",
                          "options": [
                              {"value": "none", "zh": "尚未有人擔任，請向領袖查詢",
                               "en": "Nobody yet — ask your leader"},
                              {"value": "leader", "zh": "由領袖擔任", "en": "The leader"}],
                          "member_id": ""})
        key[qid] = "none"

    if contact:
        options = []
        if contact["contact_email"]:
            options.append({"value": "email",
                            "zh": f"發電郵：{contact['contact_email']}",
                            "en": f"Send an email: {contact['contact_email']}"})
            answer = "email"
        else:
            answer = "meeting"
        options += [
            {"value": "meeting", "zh": "在集會時親自向領袖查詢",
             "en": "Ask your leader in person at a meeting"},
            {"value": "noticeboard", "zh": "在小隊布告板留言",
             "en": "Leave a note on the patrol noticeboard"},
        ]
        rng.shuffle(options)
        add("contact_way", contact,
            "有事要聯絡小隊的聯絡，可以怎樣做？",
            "How can you reach your patrol's contact?",
            options, answer, contact["id"])

    # Names and positions: one question per other member who holds a position.
    positions = []
    for member in members:
        label = member["position"] or ""
        if label and label not in [p["value"] for p in positions]:
            positions.append({"value": label, "zh": member["position_zh"] or label,
                              "en": member["position_en"] or label})
    if not any(p["value"] == "" for p in positions):
        positions.append(dict(NO_POSITION))
    for member in others:
        if not member["position"]:
            continue
        # at most four options, but the right one is never trimmed away
        target_opt = next(p for p in positions if p["value"] == member["position"])
        rest = [p for p in positions if p["value"] != member["position"]]
        rng.shuffle(rest)
        opts = [target_opt] + rest[:3]
        rng.shuffle(opts)
        add("position", member,
            f"{member['name_zh']}（{member['name_en']}）在本小隊擔任甚麼職位？",
            f"What job does {member['name_en']} hold in the patrol?",
            opts, member["position"], member["id"])

    # Knowing the person: a clue from their own words, name the member.
    clue_fields = [
        ("interests", "以下哪一位成員的興趣是：{text}",
         "Which member's interests are these: {text}"),
        ("strength", "以下哪一位成員的強項是：{text}",
         "Which member's strength is this: {text}"),
        ("share", "以下哪一位成員想和大家分享：{text}",
         "Which member wants to share this: {text}"),
        ("experience", "以下哪一位成員的童軍經驗是：{text}",
         "Whose Scout experience is this: {text}"),
    ]
    clues = []
    for member in others:
        if not member["complete"]:
            continue
        for field, zh_tpl, en_tpl in clue_fields:
            text = member[field].strip()
            if text:
                clues.append((member, text[:60], zh_tpl, en_tpl))
    rng.shuffle(clues)
    clue_counts: dict[str, int] = {}
    for member, text, zh_tpl, en_tpl in clues:
        # at most two clues per member, so the whole patrol gets a turn
        if clue_counts.get(member["id"], 0) >= 2:
            continue
        clue_counts[member["id"]] = clue_counts.get(member["id"], 0) + 1
        add("clue", member,
            zh_tpl.format(text=text), en_tpl.format(text=text),
            _options(rng, members, member, "name"), member["id"], member["id"])

    rng.shuffle(questions)
    # Keep the contact questions in play even when the roster is large.
    contact_qs = [q for q in questions if q["kind"].startswith("contact")]
    rest = [q for q in questions if not q["kind"].startswith("contact")]
    questions = (contact_qs + rest)[:MAX_QUESTIONS]
    key = {q["id"]: key[q["id"]] for q in questions}
    # Renumber so the ids run 1..n after trimming.
    renumbered = []
    new_key: dict[str, str] = {}
    for index, question in enumerate(questions, start=1):
        old = question["id"]
        question = {**question, "id": f"q{index}"}
        renumbered.append(question)
        new_key[question["id"]] = key[old]
    return renumbered, new_key


def grade(key: dict, given: dict) -> tuple[int, int]:
    correct = sum(1 for qid, answer in key.items() if str(given.get(qid) or "") == str(answer))
    return correct, len(key)
