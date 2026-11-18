"""遊戲 5：小隊名冊卡 — knowing your patrol (item 2, M02).

The story: after the four challenges the scout reaches the seaside, where
the rest of the patrol is waiting by a raft. The raft carries the whole
patrol off the island, but every station on it — lookout, steering, the
signal station — needs the member who suits it best. So the scout first
gets to know the patrol from their member cards, then works out, station
by station, who belongs where. Eighty percent of the stations right and
the raft leaves the island.

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

MAX_SEATS = 8

# A station's requirement is worded from the member's own facts, in this
# order of preference: a strength or an interest usually names one member
# on its own; a shared job (two 隊員, say) is pinned down with a second fact.
_FACT_ORDER = ["strength", "interests", "position", "experience", "share"]
_FACT_LABEL = {
    "strength": ("強項是「{t}」", "strength is “{t}”"),
    "interests": ("興趣是「{t}」", "interests are “{t}”"),
    "position": ("職位是「{t}」", "patrol job is “{t}”"),
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


def _pick_crew(members: list[dict], viewer_id: str) -> list[dict]:
    """Who gets a station: the whole patrol, or the eight who suit it best."""
    if len(members) <= MAX_SEATS:
        return list(members)
    contact = contact_of(members)

    def rank(member: dict):
        if contact and member["id"] == contact["id"]:
            return 0
        if member["id"] == viewer_id:
            return 1
        if member.get("complete"):
            return 2
        if member.get("position"):
            return 3
        return 4

    chosen = sorted(members, key=rank)[:MAX_SEATS]
    keep = {m["id"] for m in chosen}
    return [m for m in members if m["id"] in keep]


def build_raft(members: list[dict], viewer_id: str, seed: int) -> tuple[list[dict], dict, list[str]]:
    """(stations for the page, {station id: member id} for the server, crew ids).

    Who sits where never reaches the browser: the page shows each
    station's job and its requirement only, and the server signs the
    seating plan into the run token.
    """
    rng = random.Random(seed)
    crew = _pick_crew(members, viewer_id)
    contact = contact_of(crew)
    roles = [r for r in RAFT_ROLES if r[0] != "signal"]
    seats: list[dict] = []
    key: dict[str, str] = {}
    role_at = 0
    for member in crew:
        if contact and member["id"] == contact["id"]:
            role = RAFT_ROLES[0]
            criterion = _contact_criterion(member)
        else:
            role = roles[min(role_at, len(roles) - 1)]
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
