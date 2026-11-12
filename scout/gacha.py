"""抽卡 — a scout card pack, in the shape of a browser gacha.

The opening is the familiar one: tap a foil pack, flip five cards, rarities
from Common to Legend Rare, and a pity counter so ten dry packs guarantee an
SR or better. Packs do not refill on a timer. A scout earns one by finishing
a game, a task, the daily challenge, or a badge. Points can buy a normal pack
only; a gold pack cannot be bought.

The cards are this troop's own skills — membership, knots, drill, the three
patrols, and the proficiency badges already on the platform. They are not
Wikipedia articles.
"""
from __future__ import annotations

import hashlib
import json
import random
from typing import Any

from .util import new_id, now_iso

PITY_AFTER = 10
PACK_SIZE = 5
#: A normal pack can be bought. A gold pack cannot — it only comes with a badge.
PACK_PRICE = 10

#: weights per 1000 pulls — the same public table as a typical wiki gacha.
RATES: tuple[tuple[str, int], ...] = (
    ("C", 400),
    ("UC", 250),
    ("R", 180),
    ("SR", 100),
    ("SSR", 45),
    ("UR", 20),
    ("LR", 5),
)
SR_PLUS = {"SR", "SSR", "UR", "LR"}
RANK = {name: index for index, (name, _) in enumerate(RATES)}
MULTIPLIER = {"C": 1.0, "UC": 1.5, "R": 2.0, "SR": 3.0, "SSR": 5.0, "UR": 8.0, "LR": 12.0}
RARITY_NAME = {
    "C": ("普通", "Common"),
    "UC": ("優良", "Uncommon"),
    "R": ("稀有", "Rare"),
    "SR": ("超稀有", "Super Rare"),
    "SSR": ("特級稀有", "Super Special Rare"),
    "UR": ("極稀有", "Ultra Rare"),
    "LR": ("傳說", "Legend Rare"),
}

#: Membership, camp and drill cards. One line each, and only facts the platform
#: already teaches or that are the ordinary public names of the skill.
MEMBER_CARDS: list[dict] = [
    {"id": "promise", "zh": "童軍誓詞", "en": "Scout Promise",
     "line_zh": "入團時宣讀的三部分承諾。", "line_en": "The three-part promise made on joining.",
     "quote_zh": "說到，就要做到。", "quote_en": "A promise is something you keep.",
     "emoji": "🤝", "group_zh": "會員章", "group_en": "Membership"},
    {"id": "law", "zh": "童軍規律", "en": "Scout Law",
     "line_zh": "童軍生活的準則。", "line_en": "The rules a scout lives by.",
     "quote_zh": "規律不是背來交差，是用來過的。", "quote_en": "The Law is for living, not for reciting.",
     "emoji": "📜", "group_zh": "會員章", "group_en": "Membership"},
    {"id": "motto", "zh": "童軍銘言", "en": "Scout Motto",
     "line_zh": "童軍銘言是「準備」。", "line_en": "The Scout motto is “Be Prepared”.",
     "quote_zh": "準備，是在需要你之前已經準備好。", "quote_en": "Prepared means ready before you are needed.",
     "emoji": "⚜️", "group_zh": "會員章", "group_en": "Membership"},
    {"id": "salute", "zh": "三指禮", "en": "Three-finger salute",
     "line_zh": "三指代表誓詞的三部分。", "line_en": "Three fingers for the three parts of the Promise.",
     "quote_zh": "舉手之前，先記住自己答應過甚麼。", "quote_en": "Before the hand goes up, remember what you promised.",
     "emoji": "🖐️", "group_zh": "會員章", "group_en": "Membership"},
    {"id": "fleur", "zh": "百合花徽章", "en": "Fleur-de-lis",
     "line_zh": "徽章中間一瓣指向北方。", "line_en": "The middle petal of the badge points north.",
     "quote_zh": "方向對了，路才開始。", "quote_en": "The way starts once you know which way is north.",
     "emoji": "⚜️", "group_zh": "會員章", "group_en": "Membership"},
    {"id": "baden", "zh": "貝登堡", "en": "Baden-Powell",
     "line_zh": "貝登堡創立童軍運動。", "line_en": "Baden-Powell founded the Scout Movement.",
     "quote_zh": "一個露營，開出了一個運動。", "quote_en": "One camp started a movement.",
     "emoji": "⛺", "group_zh": "歷史", "group_en": "History"},
    {"id": "brownsea", "zh": "布朗西島", "en": "Brownsea Island",
     "line_zh": "1907 年，第一次童軍露營在布朗西島舉行。",
     "line_en": "The first Scout camp was held on Brownsea Island in 1907.",
     "quote_zh": "童軍的故事，從一個島上的營火開始。", "quote_en": "The story starts with a campfire on an island.",
     "emoji": "🏝️", "group_zh": "歷史", "group_en": "History"},
    {"id": "flag-prc", "zh": "五星紅旗", "en": "National flag",
     "line_zh": "中華人民共和國國旗，左上方有五顆黃星。",
     "line_en": "The national flag: red, with five yellow stars in the upper hoist.",
     "quote_zh": "先認得，才說得清它的意思。", "quote_en": "Recognise it before you explain it.",
     "emoji": "🚩", "group_zh": "會員章", "group_en": "Membership"},
    {"id": "emblem-prc", "zh": "國徽", "en": "National emblem",
     "line_zh": "國徽中央是天安門。", "line_en": "The national emblem centres on Tiananmen.",
     "quote_zh": "國旗和國徽，要分開認得。", "quote_en": "The flag and the emblem are not the same mark.",
     "emoji": "🏛️", "group_zh": "會員章", "group_en": "Membership"},
    {"id": "flag-hk", "zh": "香港區旗", "en": "Regional flag",
     "line_zh": "紅旗中央是一朵白色洋紫荊。",
     "line_en": "A red flag with a white bauhinia in the centre.",
     "quote_zh": "區旗要認得，含意也要說得出。", "quote_en": "Know the flag, and be able to say what it means.",
     "emoji": "🌺", "group_zh": "會員章", "group_en": "Membership"},
    {"id": "emblem-hk", "zh": "香港區徽", "en": "Regional emblem",
     "line_zh": "區徽同樣以洋紫荊為記。", "line_en": "The regional emblem also bears the bauhinia.",
     "quote_zh": "區旗是一面旗，區徽是一枚徽。", "quote_en": "The flag is a flag. The emblem is a badge.",
     "emoji": "🌺", "group_zh": "會員章", "group_en": "Membership"},
    {"id": "patrol-tiger", "zh": "老虎小隊", "en": "Tiger Patrol",
     "line_zh": "本團三個小隊之一。", "line_en": "One of this troop's three patrols.",
     "quote_zh": "小隊是一起出發的人。", "quote_en": "A patrol is the people you set out with.",
     "emoji": "🐯", "group_zh": "小隊", "group_en": "Patrol"},
    {"id": "patrol-otter", "zh": "水獺小隊", "en": "Otter Patrol",
     "line_zh": "本團三個小隊之一。", "line_en": "One of this troop's three patrols.",
     "quote_zh": "認得自己的小隊，也認得另外兩個。", "quote_en": "Know your own patrol, and the other two.",
     "emoji": "🦦", "group_zh": "小隊", "group_en": "Patrol"},
    {"id": "patrol-seagull", "zh": "海鷗小隊", "en": "Seagull Patrol",
     "line_zh": "本團三個小隊之一。", "line_en": "One of this troop's three patrols.",
     "quote_zh": "三個小隊，一個團。", "quote_en": "Three patrols, one troop.",
     "emoji": "🐦", "group_zh": "小隊", "group_en": "Patrol"},
    {"id": "reef", "zh": "平結", "en": "Reef knot",
     "line_zh": "用來連接兩條粗幼相近的繩。", "line_en": "Joins two ropes of similar thickness.",
     "quote_zh": "平結易打，也要易解。", "quote_en": "A reef knot should be as easy to undo as to tie.",
     "emoji": "🪢", "group_zh": "繩結", "group_en": "Knots"},
    {"id": "bowline", "zh": "稱人結", "en": "Bowline",
     "line_zh": "打一個不會收緊的固定繩圈。", "line_en": "A fixed loop that will not slip tighter.",
     "quote_zh": "繩圈要穩，人才能放心。", "quote_en": "The loop stays open, so the person stays safe.",
     "emoji": "🪢", "group_zh": "繩結", "group_en": "Knots"},
    {"id": "clove", "zh": "雙套結", "en": "Clove hitch",
     "line_zh": "把繩子臨時套在木或柱上。", "line_en": "A hitch for making a rope fast to a spar.",
     "quote_zh": "臨時固定，用完要解得開。", "quote_en": "Made fast for now, and easy to free again.",
     "emoji": "🪢", "group_zh": "繩結", "group_en": "Knots"},
    {"id": "sheetbend", "zh": "單編結", "en": "Sheet bend",
     "line_zh": "連接兩條粗幼不同的繩。", "line_en": "Joins two ropes of different thickness.",
     "quote_zh": "繩子不一樣粗，就不要用平結硬接。", "quote_en": "Different ropes need a different bend.",
     "emoji": "🪢", "group_zh": "繩結", "group_en": "Knots"},
    {"id": "attention", "zh": "立正", "en": "Attention",
     "line_zh": "步操的起始姿勢，雙腳併攏。", "line_en": "The drill position you start from, feet together.",
     "quote_zh": "先站穩，口令才聽得清。", "quote_en": "Stand still, then you can hear the word.",
     "emoji": "🧍", "group_zh": "步操", "group_en": "Drill"},
    {"id": "ease", "zh": "稍息", "en": "Stand at ease",
     "line_zh": "由立正轉為稍息，仍然看齊。", "line_en": "From attention to at ease, still dressed.",
     "quote_zh": "稍息不是解散。", "quote_en": "At ease is not dismissed.",
     "emoji": "🧍", "group_zh": "步操", "group_en": "Drill"},
    {"id": "halt", "zh": "立定", "en": "Halt",
     "line_zh": "行進中聽到立定，停步站好。", "line_en": "On the halt, the step stops and you stand still.",
     "quote_zh": "停得齊，隊伍才不散。", "quote_en": "Halt together, or the squad comes apart.",
     "emoji": "🛑", "group_zh": "步操", "group_en": "Drill"},
    {"id": "about", "zh": "向後轉", "en": "About turn",
     "line_zh": "原地轉一百八十度。", "line_en": "A turn of 180 degrees, on the spot.",
     "quote_zh": "轉完仍然是立正。", "quote_en": "When the turn ends, you are at attention again.",
     "emoji": "🔄", "group_zh": "步操", "group_en": "Drill"},
    {"id": "trace", "zh": "不留痕跡", "en": "Leave no trace",
     "line_zh": "離開營地時，把地方還原。", "line_en": "When you leave camp, leave the place as you found it.",
     "quote_zh": "後來的人，不應看得出你來過。", "quote_en": "The next person should not be able to tell you were there.",
     "emoji": "🌿", "group_zh": "露營", "group_en": "Camping"},
    {"id": "fire", "zh": "營火看管", "en": "A watched fire",
     "line_zh": "營火要有人看管，離開前要完全熄滅。",
     "line_en": "A campfire is watched, and it is out before you leave.",
     "quote_zh": "沒有人看的火，不是營火。", "quote_en": "A fire nobody is watching is not a campfire.",
     "emoji": "🔥", "group_zh": "露營", "group_en": "Camping"},
]


def _json(value, fallback):
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


def _base_stats(card_id: str) -> tuple[int, int]:
    digest = hashlib.sha256(card_id.encode("utf-8")).digest()
    return 48 + digest[0] % 38, 48 + digest[1] % 38


def pool() -> list[dict]:
    """Every card that can come out of a pack. Built once per process."""
    from .daily import BADGE_ART, MEMORY_BADGES

    cards = [dict(row, art="") for row in MEMBER_CARDS]
    for row in MEMORY_BADGES:
        cards.append({
            "id": f"badge-{row['id']}",
            "zh": row["zh"],
            "en": row["en"],
            "line_zh": row["what_zh"],
            "line_en": row["what_en"],
            "quote_zh": f"{row['group_zh']}的專科徽章。",
            "quote_en": f"A proficiency badge in the {row['group_en']} group.",
            "emoji": "🎖️",
            "art": f"{BADGE_ART}/{row['art']}",
            "group_zh": row["group_zh"],
            "group_en": row["group_en"],
        })
    return cards


def card_by_id(card_id: str) -> dict | None:
    return next((card for card in pool() if card["id"] == card_id), None)


def roll_rarity(rng: random.Random, floor: str | None = None) -> str:
    table = RATES if not floor else tuple(row for row in RATES if RANK[row[0]] >= RANK[floor])
    total = sum(weight for _, weight in table)
    pick = rng.randrange(total)
    acc = 0
    for name, weight in table:
        acc += weight
        if pick < acc:
            return name
    return table[-1][0]


def scaled(base: int, rarity: str) -> int:
    return int(round(base * MULTIPLIER[rarity]))


def until_sr(pity: int) -> int:
    return max(0, PITY_AFTER - int(pity or 0))


def blank_state(user_id: str) -> dict:
    return {
        "user_id": user_id,
        "packs_json": [],
        "owned_json": {},
        "grants_json": [],
        "last_open_json": None,
        "pity": 0,
        "opened": 0,
        "updated_at": now_iso(),
    }


def load_state(store, user_id: str) -> dict:
    row = store.get("gacha", user_id) or blank_state(user_id)
    return {
        "user_id": user_id,
        "packs_json": list(_json(row.get("packs_json"), [])),
        "owned_json": dict(_json(row.get("owned_json"), {})),
        "grants_json": list(_json(row.get("grants_json"), [])),
        "last_open_json": _json(row.get("last_open_json"), None),
        "pity": int(row.get("pity") or 0),
        "opened": int(row.get("opened") or 0),
        "updated_at": row.get("updated_at") or now_iso(),
    }


def save_state(store, state: dict) -> dict:
    state = dict(state)
    state["updated_at"] = now_iso()
    if store.get("gacha", state["user_id"]):
        store.update("gacha", state["user_id"], state)
    else:
        store.insert("gacha", state)
    return state


def grant_pack(store, user: dict, *, key: str, kind: str, source: str, ref_id: str,
               reason_zh: str, reason_en: str) -> bool:
    """Give one pack, once per key. Returns True only when a new pack is added."""
    state = load_state(store, user["id"])
    grants = list(state["grants_json"])
    if key in grants:
        return False
    grants.append(key)
    packs = list(state["packs_json"])
    packs.append({
        "id": new_id(),
        "kind": "gold" if kind == "gold" else "standard",
        "source": source,
        "ref_id": ref_id,
        "reason_zh": reason_zh,
        "reason_en": reason_en,
        "granted_at": now_iso(),
    })
    state["grants_json"] = grants
    state["packs_json"] = packs
    save_state(store, state)
    return True


def buy_standard_pack(store, user: dict) -> dict:
    """Spend points on one normal pack. Never a gold pack. No change if short."""
    from .engine import as_int, write_ledger

    balance = as_int(store.stats_for(user["id"]).get("points_balance"))
    if balance < PACK_PRICE:
        return {"ok": False, "balance": balance, "price": PACK_PRICE}
    key = f"buy:{new_id()}"
    write_ledger(
        store, user_id=user["id"], entry_type="gacha", points_delta=-PACK_PRICE,
        reason_zh="用積分換一個普通卡包",
        reason_en="Bought a normal card pack",
        ref_type="gacha", ref_id=key, created_by=user["id"],
    )
    granted = grant_pack(
        store, user, key=key, kind="standard", source="points", ref_id=key,
        reason_zh="用積分換的普通卡包",
        reason_en="A normal pack bought with points",
    )
    if not granted:
        write_ledger(
            store, user_id=user["id"], entry_type="gacha", points_delta=PACK_PRICE,
            reason_zh="換卡包未成功，積分退回",
            reason_en="The pack was not added, so the points were returned",
            ref_type="gacha", ref_id=key, created_by=user["id"],
        )
        return {"ok": False, "balance": balance, "price": PACK_PRICE}
    return {
        "ok": True,
        "balance": as_int(store.stats_for(user["id"]).get("points_balance")),
        "price": PACK_PRICE,
    }


def sync_earned_packs(store, user: dict) -> dict:
    """Backfill packs for work already on the record. Safe to call often."""
    user_id = user["id"]
    tasks = {row["id"]: row for row in store.list("tasks")}
    by_task: dict[str, list[dict]] = {}
    for row in store.list("progress_records"):
        if row.get("user_id") != user_id or row.get("status") != "completed":
            continue
        by_task.setdefault(str(row.get("task_id") or ""), []).append(row)
    for task_id, records in by_task.items():
        if not task_id:
            continue
        # 第 1 項在開局時已記入，那不是童軍自己完成的，不發卡包。
        if records and all((row.get("decided_by") or "") == "opening" for row in records):
            continue
        task = tasks.get(task_id) or {}
        title_zh = task.get("title_zh") or "任務"
        title_en = task.get("title_en") or "a task"
        grant_pack(
            store, user, key=f"task:{task_id}", kind="standard", source="task",
            ref_id=task_id,
            reason_zh=f"完成「{title_zh}」",
            reason_en=f"Finished “{title_en}”",
        )
    badges = {row["id"]: row for row in store.list("badges")}
    for award in store.list("badge_awards"):
        if award.get("user_id") != user_id:
            continue
        badge_id = str(award.get("badge_id") or "")
        badge = badges.get(badge_id) or {}
        grant_pack(
            store, user, key=f"badge:{badge_id}", kind="gold", source="badge",
            ref_id=badge_id,
            reason_zh=f"考獲「{badge.get('title_zh') or '獎章'}」",
            reason_en=f"Earned “{badge.get('title_en') or 'a badge'}”",
        )
    for row in store.list("points_ledger"):
        if row.get("user_id") != user_id or row.get("entry_type") != "daily":
            continue
        ref = str(row.get("ref_id") or "")
        if not ref.startswith("daily:"):
            continue
        day = ref.split(":", 1)[1]
        grant_pack(
            store, user, key=ref, kind="standard", source="daily", ref_id=ref,
            reason_zh=f"完成每日挑戰（{day}）",
            reason_en=f"Finished the daily challenge ({day})",
        )
    return load_state(store, user_id)


def present_card(card: dict, rarity: str, *, is_new: bool, upgraded: bool, count: int) -> dict:
    know, pract = _base_stats(card["id"])
    zh, en = RARITY_NAME[rarity]
    return {
        "id": card["id"],
        "rarity": rarity,
        "rarity_zh": zh,
        "rarity_en": en,
        "zh": card["zh"],
        "en": card["en"],
        "line_zh": card["line_zh"],
        "line_en": card["line_en"],
        "quote_zh": card["quote_zh"],
        "quote_en": card["quote_en"],
        "emoji": card.get("emoji") or "⚜️",
        "art": card.get("art") or "",
        "group_zh": card.get("group_zh") or "",
        "group_en": card.get("group_en") or "",
        "know": scaled(know, rarity),
        "pract": scaled(pract, rarity),
        "is_new": is_new,
        "upgraded": upgraded,
        "count": count,
    }


def draw_cards(rng: random.Random, owned: dict, *, guarantee: bool) -> tuple[list[dict], dict]:
    """Five distinct cards. `owned` is updated in a copy and returned."""
    chosen = rng.sample(pool(), PACK_SIZE)
    rarities = [roll_rarity(rng) for _ in chosen]
    if guarantee and not any(rarity in SR_PLUS for rarity in rarities):
        rarities[rng.randrange(PACK_SIZE)] = roll_rarity(rng, floor="SR")
    owned = {key: dict(value) for key, value in owned.items()}
    seen = set(owned)
    pulled = []
    for card, rarity in zip(chosen, rarities):
        is_new = card["id"] not in seen
        seen.add(card["id"])
        prev = owned.get(card["id"])
        upgraded = bool(prev) and RANK[rarity] > RANK[str(prev.get("best") or "C")]
        if prev:
            prev["count"] = int(prev.get("count") or 0) + 1
            if RANK[rarity] >= RANK[str(prev.get("best") or "C")]:
                prev["best"] = rarity
            count = prev["count"]
        else:
            owned[card["id"]] = {"count": 1, "best": rarity, "first_at": now_iso()}
            count = 1
        pulled.append(present_card(card, rarity, is_new=is_new, upgraded=upgraded, count=count))
    return pulled, owned


def open_next(store, user: dict, rng: random.Random | None = None) -> dict | None:
    """Open the oldest waiting pack. None when the scout has nothing to open."""
    state = load_state(store, user["id"])
    packs = list(state["packs_json"])
    if not packs:
        return None
    pack = packs.pop(0)
    rng = rng or random.SystemRandom()
    guarantee = pack.get("kind") == "gold" or int(state["pity"] or 0) >= PITY_AFTER
    pulled, owned = draw_cards(rng, state["owned_json"], guarantee=guarantee)
    hit = any(card["rarity"] in SR_PLUS for card in pulled)
    state["packs_json"] = packs
    state["owned_json"] = owned
    state["pity"] = 0 if hit else int(state["pity"] or 0) + 1
    state["opened"] = int(state["opened"] or 0) + 1
    opened = {
        "pack": pack,
        "cards": pulled,
        "pity": state["pity"],
        "until_sr": until_sr(state["pity"]),
        "opened_at": now_iso(),
    }
    state["last_open_json"] = opened
    save_state(store, state)
    return opened


#: Album order. The first word is the anchor, which stays in English on both
#: languages so the English page does not carry a Chinese id.
GROUP_ORDER = (
    ("membership", "skill", "會員章", "Membership"),
    ("history", "skill", "歷史", "History"),
    ("patrol", "skill", "小隊", "Patrol"),
    ("knots", "skill", "繩結", "Knots"),
    ("drill", "skill", "步操", "Drill"),
    ("camping", "skill", "露營", "Camping"),
    ("pursuit", "badge", "技能組", "Pursuit"),
    ("service", "badge", "服務組", "Service"),
    ("interest", "badge", "興趣組", "Interest"),
)
FAMILIES = {
    "skill": ("技能卡", "Skill cards"),
    "badge": ("專科徽章", "Proficiency badges"),
    "other": ("其他", "Other"),
}


def _slug(text: str) -> str:
    slug = "".join(ch.lower() if ch.isascii() and ch.isalnum() else "-" for ch in text)
    slug = "-".join(part for part in slug.split("-") if part)
    return slug or "other"


def album_sections(state: dict) -> list[dict]:
    """The album split by category, in a fixed order. Nothing is dropped."""
    buckets: dict[tuple[str, str], list[dict]] = {}
    for card in album(state):
        buckets.setdefault((card.get("group_zh") or "", card.get("group_en") or ""), []).append(card)
    known = {(zh, en): (sid, family) for sid, family, zh, en in GROUP_ORDER}
    keys = [(zh, en) for _, _, zh, en in GROUP_ORDER if (zh, en) in buckets]
    keys.extend(key for key in buckets if key not in known)
    sections = []
    seen_family: set[str] = set()
    used_ids: set[str] = set()
    for zh, en in keys:
        sid, family = known.get((zh, en), (_slug(en or zh), "other"))
        if sid in used_ids:
            sid = f"{sid}-{len(used_ids)}"
        used_ids.add(sid)
        cards = buckets[(zh, en)]
        sections.append({
            "id": sid,
            "zh": zh or "其他",
            "en": en or "Other",
            "family": family,
            "family_zh": FAMILIES[family][0],
            "family_en": FAMILIES[family][1],
            "show_family": family not in seen_family,
            "owned": sum(1 for card in cards if card.get("owned")),
            "total": len(cards),
            "cards": cards,
        })
        seen_family.add(family)
    return sections


def album(state: dict) -> list[dict]:
    """Owned cards first, then the rest of the pool still to pull."""
    owned = state.get("owned_json") or {}
    rows = []
    for card in pool():
        slot = owned.get(card["id"])
        if slot:
            rarity = str(slot.get("best") or "C")
            if rarity not in RANK:
                rarity = "C"
            rows.append({
                **present_card(card, rarity, is_new=False, upgraded=False,
                               count=int(slot.get("count") or 1)),
                "owned": True,
            })
        else:
            know, pract = _base_stats(card["id"])
            rows.append({
                "id": card["id"], "rarity": "", "rarity_zh": "", "rarity_en": "",
                "zh": card["zh"], "en": card["en"],
                "line_zh": card["line_zh"], "line_en": card["line_en"],
                "quote_zh": "", "quote_en": "",
                "emoji": card.get("emoji") or "⚜️", "art": card.get("art") or "",
                "group_zh": card.get("group_zh") or "", "group_en": card.get("group_en") or "",
                "know": know, "pract": pract,
                "is_new": False, "upgraded": False, "count": 0, "owned": False,
            })
    rows.sort(key=lambda row: (not row["owned"], -RANK.get(row["rarity"], -1), row["en"]))
    return rows


def summary(store, user: dict) -> dict:
    state = sync_earned_packs(store, user)
    packs = state["packs_json"]
    return {
        "packs": len(packs),
        "gold": sum(1 for pack in packs if pack.get("kind") == "gold"),
        "owned": sum(1 for slot in state["owned_json"].values() if int(slot.get("count") or 0) > 0),
        "total": len(pool()),
        "until_sr": until_sr(state["pity"]),
        "opened": int(state["opened"] or 0),
        "next_kind": (packs[0].get("kind") if packs else "standard"),
        "next_reason_zh": (packs[0].get("reason_zh") if packs else ""),
        "next_reason_en": (packs[0].get("reason_en") if packs else ""),
        "points": int(store.stats_for(user["id"]).get("points_balance") or 0),
        "price": PACK_PRICE,
    }


def enabled(settings: dict | None) -> bool:
    flags = (settings or {}).get("feature_flags") or {}
    return bool(flags.get("gacha", True))
