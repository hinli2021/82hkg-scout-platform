"""遊戲 5：小隊名冊卡 — knowing your patrol (item 2, M02).

The story: after the four challenges the scout reaches the seaside, where
the rest of the patrol is waiting by a raft. The raft carries the whole
patrol off the island, but every station on it — lookout, steering, the
signal station — needs the member who suits it best.

Two stages sit between the scout and the raft. Before them, the scout
may browse a profile card for every patrol member — the same card the
member sees on their own profile page, drawn live from what they have
written, so an edit shows at once; a member who has written nothing yet
is still identified by their name, avatar, scout number, patrol and
job. Stage 1 is the wooden board at the shore, carrying the name of
every scout in the unit: the scout must pick out every member of their
own patrol, and only then does stage 2 open — seating the patrol on
the raft, station by station. Every station holding the right member
and the raft leaves the island.

The roster is read live from the platform's own records, never copied into
a separate list that can go stale:

  • members      — scout accounts in the same patrol (leaders create the
                   account when a scout joins, so a new member appears in
                   the game automatically, and a member who leaves is gone).
                   The leaders' test account (username `test`) is not a
                   member: it is left out of every roster and station,
                   though the account itself can still play the game.
  • 職位／興趣／強項 — each member's own profile (`profiles`), which the
                   member keeps up to date on 我的個人檔案. A station's
                   requirement is built from these facts, and the server
                   checks the wording picks out exactly one member, so the
                   puzzle can always be solved from the cards.
  • 聯絡          — the member whose 職位 contains 「聯絡」 (one per patrol)
                   always takes the signal station; the way to reach them
                   is in person at a meeting, or through the leader. Email
                   addresses are private and never enter the game.

Members who have not finished their profile still appear — their card
says so, and their station is worked out from what little is known
(their job, or their avatar).
"""
from __future__ import annotations

import random

CONTACT_WORD = "聯絡"
NO_POSITION = {"value": "", "zh": "暫時沒有職位", "en": "No position yet"}


def _name(user: dict, lang: str) -> str:
    if lang == "en":
        return str(user.get("display_name_en") or user.get("display_name_zh") or user.get("username") or "")
    return str(user.get("display_name_zh") or user.get("display_name_en") or user.get("username") or "")


TEST_USERNAME = "test"


def is_test_account(row: dict) -> bool:
    """The leaders' test account (username `test`) is not a patrol member.

    It never appears on member cards and is never asked about — but the
    account itself can still sign in and play, seeing the real patrol.
    """
    return str(row.get("username") or "").strip().lower() == TEST_USERNAME


def patrol_members(st, user: dict) -> list[dict]:
    """Every active scout in `user`'s patrol, with their profile folded in."""
    from .engine import progress_for
    from .mascots import mascot_for
    from .routes.profile_routes import load_profile, profile_complete

    patrol = str(user.get("patrol") or "").strip().lower()
    members: list[dict] = []
    for row in st.list("users"):
        if row.get("role") != "scout" or row.get("status") != "active":
            continue
        if is_test_account(row):
            continue
        if str(row.get("patrol") or "").strip().lower() != patrol:
            continue
        profile = load_profile(st, row["id"])
        position = str(profile.get("position") or "").strip()
        # the card in the game is the member's own profile card, so it
        # carries the same numbers and patrol colours that page shows
        mascot = mascot_for(row.get("patrol") or "")
        try:
            progress = progress_for(st, row["id"])
            card_stats, card_overall = progress["stats"], progress["overall"]
            earned = [{"emoji": b.get("emoji") or "🎖",
                       "title_zh": b.get("title_zh") or "",
                       "title_en": b.get("title_en") or ""}
                      for b in progress["badges"] if b["earned"]]
        except Exception:
            card_stats, card_overall, earned = {}, {}, []
        members.append({
            "id": row["id"],
            "name_zh": _name(row, "zh"),
            "name_en": _name(row, "en"),
            "avatar": str(row.get("avatar") or "🦊"),
            "scout_no": str(row.get("scout_no") or "").strip(),
            "card_image_url": str(profile.get("card_image_url") or "").strip(),
            "position_zh": str(profile.get("position_zh") or position),
            "position_en": str(profile.get("position_en") or position),
            "position": position,
            "interests": str(profile.get("interests") or "").strip(),
            "experience": str(profile.get("experience") or "").strip(),
            "share": str(profile.get("share") or "").strip(),
            "strength": str(profile.get("strength") or "").strip(),
            "complete": profile_complete(profile),
            "mascot": {key: mascot.get(key, "") for key in
                       ("emoji", "img", "tint", "tint_dark", "soft")},
            "points_balance": card_stats.get("points_balance", 0),
            "badges_done": card_stats.get("badges_done", 0),
            "badges_total": card_overall.get("badges_total", 0),
            "tasks_done": card_overall.get("tasks_done", 0),
            "tasks_total": card_overall.get("tasks_total", 0),
            "streak_current": card_stats.get("streak_current", 0),
            "earned_badges": earned,
            "is_self": row["id"] == user["id"],
            "is_contact": CONTACT_WORD in position,
            # No email here: addresses are private and never enter the game.
        })
    # The contact first, then leaders of the patrol, then by name — the order
    # a scout would be introduced to the patrol.
    def order(member: dict):
        rank = 0 if member["is_contact"] else 1 if member["position"] else 2
        return (rank, member["name_zh"])

    return sorted(members, key=order)


def contact_of(members: list[dict]) -> dict | None:
    return next((m for m in members if m["is_contact"]), None)


def unit_roster(st, seed: int) -> list[dict]:
    """Every active scout in the unit, for the stage 1 board.

    Names only — the board never says which patrol anyone belongs to,
    and the leaders' test account is not a scout on it either.
    """
    rng = random.Random(seed)
    board = [{
        "id": row["id"],
        "name_zh": _name(row, "zh"),
        "name_en": _name(row, "en"),
    } for row in st.list("users")
        if row.get("role") == "scout" and row.get("status") == "active"
        and not is_test_account(row)]
    rng.shuffle(board)
    return board


# ── the raft ─────────────────────────────────────────────────────────────
# Every station on the raft, with the job it does. The signal station is
# reserved for the patrol contact; the rest are filled in order.
RAFT_ROLES = [
    ("signal", "通訊站", "Signal station",
     "負責和岸上保持聯絡，記下全隊的位置。",
     "Keeps contact with the shore and notes where everyone is."),
    ("bow", "船頭瞭望", "Bow lookout",
     "留意前面的水面和礁石，及早提醒大家。",
     "Watches the water and rocks ahead and warns everyone in good time."),
    ("helm", "掌舵", "Steering",
     "控制木筏的方向，讓木筏避開礁石。",
     "Steers the raft clear of the rocks."),
    ("sail", "揚帆", "Sail hand",
     "照顧船帆和繩索，順著風前進。",
     "Looks after the sail and ropes and rides the wind."),
    ("stern", "船尾瞭望", "Stern lookout",
     "留意後面的水面，確保沒有人掉隊。",
     "Watches the water behind so nobody is left behind."),
    ("rope", "繩索整理", "Rope hand",
     "收好繩索，準備隨時靠岸。",
     "Coils the ropes, ready to reach shore."),
    ("port", "左舷船員", "Port-side crew",
     "保持木筏平衡，照顧這一邊的成員。",
     "Keeps the raft balanced and looks after this side."),
    ("starboard", "右舷船員", "Starboard-side crew",
     "保持木筏平衡，照顧這一邊的成員。",
     "Keeps the raft balanced and looks after this side."),
    ("middle", "船中船員", "Mid-raft crew",
     "照顧行李和物資，讓大家安心工作。",
     "Looks after the bags and supplies so everyone can work."),
]

# A station's requirement is worded from the member's own facts, in this
# order of preference: a strength or an interest usually names one member
# on its own; a shared job (two 隊員, say) is pinned down with a second fact.
_FACT_ORDER = ["strength", "interests", "position", "scout_no", "experience", "share"]
_FACT_LABEL = {
    "strength": ("強項是「{t}」", "strength is “{t}”"),
    "interests": ("興趣是「{t}」", "interests are “{t}”"),
    "position": ("職位是「{t}」", "patrol job is “{t}”"),
    "scout_no": ("童軍編號是「{t}」", "scout number is “{t}”"),
    "experience": ("童軍經驗是「{t}」", "Scout experience is “{t}”"),
    "share": ("想和大家分享「{t}」", "thing to share is “{t}”"),
    "avatar": ("頭像是 {t}", "avatar is {t}"),
}


def _facts(member: dict) -> list[tuple[str, str, str, str]]:
    """(field, value, wording_zh, wording_en) for everything known of a member."""
    facts = []
    for field in _FACT_ORDER:
        raw = str(member.get(field) or "").strip()
        if not raw:
            continue
        if field == "position":
            zh = str(member.get("position_zh") or raw)
            en = str(member.get("position_en") or raw)
        else:
            zh = en = raw[:48]
        facts.append((field, raw, zh, en))
    avatar = str(member.get("avatar") or "🦊")
    facts.append(("avatar", avatar, avatar, avatar))
    return facts


def _criterion(member: dict, crew: list[dict]) -> tuple[str, str]:
    """Wording that picks `member` out of the crew — and nobody else.

    The server tries one fact, then two together, until only the member
    the station belongs to matches everything the wording says. What the
    scout read on the member cards is therefore always enough to solve
    the station, and never points at two members at once.
    """
    facts = _facts(member)

    def matches(combo) -> int:
        return sum(1 for m in crew
                   if all(str(m.get(f) or "").strip() == v for f, v, _z, _e in combo))

    def render(combo) -> tuple[str, str]:
        zh = "需要一位" + "，而且".join(_FACT_LABEL[f][0].format(t=z) for f, _v, z, _e in combo) + "的成員"
        en = "Needs the member whose " + " and whose ".join(
            _FACT_LABEL[f][1].format(t=e) for f, _v, _z, e in combo)
        return zh, en

    for fact in facts:
        if matches([fact]) == 1:
            return render([fact])
    for i, first in enumerate(facts):
        for second in facts[i + 1:]:
            if second[0] == first[0]:
                continue
            if matches([first, second]) == 1:
                return render([first, second])
    return render(facts[:1])


def _contact_criterion(member: dict) -> tuple[str, str]:
    return ("需要由小隊聯絡負責。有事要找他，可以在集會時親自找他，或者請領袖幫忙聯絡。",
            "Needs the patrol contact. To reach them, find them in person at a "
            "meeting, or ask your leader to pass a message on.")


def _station_role(role_at: int) -> tuple:
    """The next station on the raft, however big the patrol is.

    The named stations come first; a larger patrol simply adds crew
    stations, so every member always gets a place — two members or
    twelve, nobody is left standing on the shore.
    """
    roles = [r for r in RAFT_ROLES if r[0] != "signal"]
    if role_at < len(roles):
        return roles[role_at]
    n = role_at - len(roles) + 1
    return ("crew", f"船員 {n}", f"Crew member {n}",
            "保持木筏平衡，幫助身邊的成員。",
            "Keeps the raft balanced and helps the members nearby.")


def build_raft(members: list[dict], viewer_id: str, seed: int) -> tuple[list[dict], dict, list[str]]:
    """(stations for the page, {station id: member id} for the server, crew ids).

    Who sits where never reaches the browser: the page shows each
    station's job and its requirement only, and the server signs the
    seating plan into the run token.
    """
    rng = random.Random(seed)
    crew = list(members)          # every member gets a station, any patrol size
    contact = contact_of(crew)
    seats: list[dict] = []
    key: dict[str, str] = {}
    role_at = 0
    for member in crew:
        if contact and member["id"] == contact["id"]:
            role = RAFT_ROLES[0]
            criterion = _contact_criterion(member)
        else:
            role = _station_role(role_at)
            role_at += 1
            criterion = _criterion(member, crew)
        seats.append({
            "role_zh": role[1], "role_en": role[2],
            "duty_zh": role[3], "duty_en": role[4],
            "criterion_zh": criterion[0], "criterion_en": criterion[1],
            "_member": member["id"],
        })
    rng.shuffle(seats)
    for index, seat in enumerate(seats, start=1):
        seat["id"] = f"s{index}"
        key[seat["id"]] = seat.pop("_member")
    return seats, key, [m["id"] for m in crew]


def grade(key: dict, given: dict) -> tuple[int, int]:
    correct = sum(1 for qid, answer in key.items() if str(given.get(qid) or "") == str(answer))
    return correct, len(key)
