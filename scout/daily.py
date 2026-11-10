"""每日挑戰 — one small puzzle a day, the same for everyone in the troop.

The shape is borrowed from puzzle sites: a daily game that takes a few minutes,
rotates between a handful of simple puzzles, and pays a few points. Everything
is deterministic from the Hong Kong date, so every scout in the troop opens the
same puzzle and the day's result is comparable.

Four games, each one pure data — the browser draws and judges it:

  pipes    旋轉水管   a net of pipes turned out of place; turn every piece
                      until the whole net joins up (6×6)
  fifteen  數字滑塊   the 15-puzzle, 4×4
  mines    營地排險   8×8; ten hazards hidden in the grass to clear before
                     the tents go up
  memory   記憶配對   4×4, eight pairs of Scout pictures

The daily seed also picks the game, so the order is the same for everybody and
a day's puzzle never repeats its neighbours.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone

#: Hong Kong has no daylight saving, so a fixed offset is exact.
HK = timezone(timedelta(hours=8))

#: 完成就 3 分；5 分鐘內完成 5 分。每天只算一次。
POINTS_DONE = 3
POINTS_FAST = 5
FAST_MS = 5 * 60 * 1000

#: 交回來的用時，太短（不可能）或太長（掛機）都不計。
MIN_MS = 8000
MAX_MS = 60 * 60 * 1000

GAMES: dict[str, dict] = {
    "pipes": {
        "name_zh": "營地水管", "name_en": "Camp water line",
        "short_zh": "轉動每一段水管，把水由河邊接到營地。",
        "short_en": "Turn each length of pipe until the water reaches camp.",
        "how_zh": ["點一下水管，它會順時針轉 90 度。",
                   "所有接口都要與鄰居對上，整條水路連成一體，水才到得了營地。",
                   "沒有計步限制，慢慢想 —— 就像在營地實地鋪水管一樣，接錯一節就漏水。"],
        "how_en": ["Tap a length to turn it a quarter turn clockwise.",
                   "Every opening must meet its neighbour's and the whole run must be one piece — "
                   "that is when the water reaches camp.",
                   "No move limit; take your time, exactly as you would laying a real line at camp."],
        "emoji": "🚰",
    },
    "fifteen": {
        "name_zh": "營地拼圖", "name_en": "Camp picture slide",
        "short_zh": "滑動方塊，把營地圖畫拼回原位。",
        "short_en": "Slide the pieces until the camp picture is whole again.",
        "how_zh": ["點空格旁邊的一塊，它就會滑進空格。",
                   "把整幅營地圖畫拼回原位（右下角留空）就完成 —— 太陽、旗、營帳、營火、樹林都要歸位。",
                   "每塊右下角有一個很小的號碼，記不住圖案時可以照號碼排；旁邊有完成圖可以對照。"],
        "how_en": ["Tap a piece beside the gap and it slides in.",
                   "Restore the camp picture — sun, flag, tent, fire and trees all back in place — "
                   "with the gap in the bottom-right corner.",
                   "Each piece keeps a tiny number in its corner if you lose track, and the finished "
                   "picture sits beside the board to compare with."],
        "emoji": "🏕️",
    },
    "mines": {
        "name_zh": "營地排險", "name_en": "Camp clearance",
        "short_zh": "起營之前，把草地上的鐵釘、玻璃碎和炭火一一標出來。",
        "short_en": "Before the tents go up, mark every nail, shard and live ember in the grass.",
        "how_zh": ["點一格撥開草；數字表示四周有幾件危險物。",
                   "按 🚩（或先按「標記」再點）插上小旗，標出你認為有危險的格。",
                   "第一次點的一定安全；踩中危險物就要重新清一次場。",
                   "這是童軍起營前的指定動作：場地未清好，營帳不落地。"],
        "how_en": ["Tap a square to part the grass; the number counts the hazards around it.",
                   "Tap 🚩 (or switch on “Mark” first) to plant a pennant on a square you think is dangerous.",
                   "Your first tap is always safe; stand on a hazard and the field has to be cleared again.",
                   "This is the Scouts' rule before camp: no ground cleared, no tent pitched."],
        "emoji": "🧹",
    },
    "memory": {
        "name_zh": "專科徽章配對", "name_en": "Proficiency badge pairs",
        "short_zh": "翻開兩張一樣的專科徽章，配成八對。",
        "short_en": "Turn up matching proficiency badges — eight pairs.",
        "how_zh": ["每次翻開兩張，同一個專科徽章就配成一對，留在桌上。",
                   "八對全部配好就完成；配對後會顯示這枚徽章要考甚麼。",
                   "每次玩的徽章都不同：專科徽章共有十多枚。"],
        "how_en": ["Turn two cards at a time; the same proficiency badge makes a pair, face up.",
                   "Eight pairs finishes the game — and each match tells you what the badge asks for.",
                   "The badges change from day to day; there are more than a dozen of them."],
        "emoji": "🎖️",
    },
}

ORDER = ["pipes", "fifteen", "mines", "memory"]

#: 專科徽章 — the proficiency badges the matching game is played with.
#:
#: The artwork is the official badge image from the Hong Kong Scout Association's
#: 童軍訓練綱要 (scoutsinfohub.org.hk / ScoutTrainingScheme/img), copied into
#: `static/img/badges/` rather than hot-linked, with the white frame knocked out
#: so the diamond sits on the card. The day draws eight of them, so the deck
#: changes from day to day.
#:
#: Each entry: art (file under static/img/badges), the official name in Chinese
#: and English, the badge's group in the training scheme, and one line saying
#: what a scout does to earn it.
MEMORY_BADGES = [
    {"id": "camper", "art": "camper.webp", "group_zh": "技能組", "group_en": "Pursuit",
     "zh": "露營", "en": "Camper", "colour": "#1f4b8f",
     "what_zh": "在野外露營，起營、收營", "what_en": "Camp out — pitch the tent and strike it"},
    {"id": "cook", "art": "cook.webp", "group_zh": "技能組", "group_en": "Pursuit",
     "zh": "烹飪", "en": "Cook", "colour": "#1f4b8f",
     "what_zh": "煮一餐，兼顧衞生與安全", "what_en": "Cook a meal, safely and cleanly"},
    {"id": "firstaider", "art": "firstaider.webp", "group_zh": "服務組", "group_en": "Service",
     "zh": "急救", "en": "First Aider", "colour": "#b3261e",
     "what_zh": "包紮傷口，處理意外", "what_en": "Dress a wound and handle an accident"},
    {"id": "mapreader", "art": "mapreader.webp", "group_zh": "技能組", "group_en": "Pursuit",
     "zh": "地圖閱讀", "en": "Map Reader", "colour": "#1f4b8f",
     "what_zh": "讀地圖、用指南針找方向", "what_en": "Read a map and take a bearing with a compass"},
    {"id": "pioneer", "art": "pioneer.webp", "group_zh": "技能組", "group_en": "Pursuit",
     "zh": "先鋒工程", "en": "Pioneer", "colour": "#1f4b8f",
     "what_zh": "用繩與木紮營架", "what_en": "Lash spars and ropes into a camp structure"},
    {"id": "astronomer", "art": "astronomer.webp", "group_zh": "技能組", "group_en": "Pursuit",
     "zh": "天象", "en": "Astronomer", "colour": "#1f4b8f",
     "what_zh": "認星座，看月相", "what_en": "Know the constellations and the phases of the moon"},
    {"id": "swimmer", "art": "swimmer.webp", "group_zh": "興趣組", "group_en": "Interest",
     "zh": "游泳", "en": "Swimmer", "colour": "#1f4b8f",
     "what_zh": "游一段距離，懂水上安全", "what_en": "Swim a set distance and know water safety"},
    {"id": "cyclist", "art": "cyclist.webp", "group_zh": "興趣組", "group_en": "Interest",
     "zh": "單車", "en": "Cyclist", "colour": "#1f4b8f",
     "what_zh": "安全騎行，保養單車", "what_en": "Ride safely and keep the bike in order"},
    {"id": "birdwatcher", "art": "birdwatcher.webp", "group_zh": "興趣組", "group_en": "Interest",
     "zh": "觀鳥", "en": "Birdwatcher", "colour": "#1f4b8f",
     "what_zh": "辨認常見雀鳥", "what_en": "Recognise the birds around you"},
    {"id": "photographer", "art": "photographer.webp", "group_zh": "興趣組", "group_en": "Interest",
     "zh": "攝影", "en": "Photographer", "colour": "#1f4b8f",
     "what_zh": "用照片記錄旅程", "what_en": "Tell the trip in photographs"},
    {"id": "meteorologist", "art": "meteorologist.webp", "group_zh": "興趣組", "group_en": "Interest",
     "zh": "氣象", "en": "Meteorologist", "colour": "#1f4b8f",
     "what_zh": "看雲識天氣，記錄氣象", "what_en": "Read the clouds and keep a weather log"},
    {"id": "campfirehost", "art": "campfirehost.webp", "group_zh": "興趣組", "group_en": "Interest",
     "zh": "營火", "en": "Campfire Host", "colour": "#1f4b8f",
     "what_zh": "主持營火會，帶唱帶玩", "what_en": "Host a campfire — songs, stunts and all"},
    {"id": "lifesaver", "art": "lifesaver.webp", "group_zh": "服務組", "group_en": "Service",
     "zh": "拯溺", "en": "Lifesaver", "colour": "#b3261e",
     "what_zh": "水上救援，救人自救", "what_en": "Rescue in the water, and keep yourself safe"},
    {"id": "fireman", "art": "fireman.webp", "group_zh": "服務組", "group_en": "Service",
     "zh": "消防", "en": "Fireman", "colour": "#b3261e",
     "what_zh": "防火、滅火、疏散", "what_en": "Prevent fires, put them out, get people clear"},
    {"id": "orienteer", "art": "orienteer.webp", "group_zh": "技能組", "group_en": "Pursuit",
     "zh": "野外定向", "en": "Orienteer", "colour": "#1f4b8f",
     "what_zh": "按地圖找控制點", "what_en": "Find the checkpoints from the map"},
    {"id": "footdrill", "art": "footdrill.webp", "group_zh": "興趣組", "group_en": "Interest",
     "zh": "步操", "en": "Footdrill", "colour": "#b3261e",
     "what_zh": "步操口令與動作", "what_en": "Answer the drill commands smartly"},
    {"id": "archery", "art": "archery.webp", "group_zh": "興趣組", "group_en": "Interest",
     "zh": "射箭", "en": "Archery", "colour": "#1f4b8f",
     "what_zh": "安全射箭，射中靶心", "what_en": "Shoot safely and group your arrows"},
    {"id": "campcook", "art": "campcook.webp", "group_zh": "興趣組", "group_en": "Interest",
     "zh": "營地烹飪", "en": "Camp Cook", "colour": "#14402a",
     "what_zh": "用營火煮一餐", "what_en": "Cook a meal over the fire"},
    {"id": "athlete", "art": "athlete.webp", "group_zh": "興趣組", "group_en": "Interest",
     "zh": "運動", "en": "Athlete", "colour": "#1f4b8f",
     "what_zh": "練好體能，參加比賽", "what_en": "Train your body and take part in a sport"},
    {"id": "canoeist", "art": "canoeist.webp", "group_zh": "興趣組", "group_en": "Interest",
     "zh": "獨木舟", "en": "Canoeist", "colour": "#1f4b8f",
     "what_zh": "划獨木舟，懂水上安全", "what_en": "Paddle a canoe and keep safe on the water"},
    {"id": "angler", "art": "angler.webp", "group_zh": "興趣組", "group_en": "Interest",
     "zh": "釣魚", "en": "Angler", "colour": "#14402a",
     "what_zh": "釣魚，認識魚類", "what_en": "Fish, and know what you catch"},
    {"id": "worldfriendshipambassador", "art": "worldfriendshipambassador.webp",
     "group_zh": "服務組", "group_en": "Service",
     "zh": "國際友誼", "en": "World Friendship Ambassador", "colour": "#b3261e",
     "what_zh": "與外地童軍交流", "what_en": "Make friends with Scouts abroad"},
]

#: the badge art lives here, beside the other platform images
BADGE_ART = "img/badges"

N, E, S, W = 1, 2, 4, 8
STEPS = {N: (-1, 0), E: (0, 1), S: (1, 0), W: (0, -1)}
OPPOSITE = {N: S, E: W, S: N, W: E}


def hk_now() -> datetime:
    return datetime.now(HK)


def today_key(day: date | None = None) -> str:
    """The day a puzzle belongs to, in Hong Kong time — YYYY-MM-DD."""
    return (day or hk_now().date()).isoformat()


def _seed(day: str) -> int:
    # a stable, well-spread seed: the digits themselves are enough for these
    # four games, and they keep consecutive days visibly different
    return int(day.replace("-", ""))


# ── the four boards ─────────────────────────────────────────────────────────

def _pipes(rng: random.Random) -> dict:
    """A spanning tree of pipes, then every piece turned a random amount."""
    size = 6
    ports = {}                                   # (r, c) -> set of directions
    seen = {(0, 0)}
    stack = [(0, 0)]
    while stack:
        r, c = stack[-1]
        options = []
        for d, (dr, dc) in STEPS.items():
            nr, nc = r + dr, c + dc
            if 0 <= nr < size and 0 <= nc < size and (nr, nc) not in seen:
                options.append((d, nr, nc))
        if not options:
            stack.pop()
            continue
        d, nr, nc = rng.choice(options)
        ports.setdefault((r, c), set()).add(d)
        ports.setdefault((nr, nc), set()).add(OPPOSITE[d])
        seen.add((nr, nc))
        stack.append((nr, nc))

    mask_of = {cell: sum(dirs) for cell, dirs in ports.items()}
    cells = []
    turns = []
    for r in range(size):
        for c in range(size):
            mask = mask_of.get((r, c), 0)
            turn = rng.randrange(4)
            if turn == 0:                        # never hand back a solved board
                turn = rng.randrange(1, 4)
            cells.append({"m": mask, "t": turn})
            turns.append((4 - turn) % 4)         # taps needed to line it up
    return {"size": size, "cells": cells}, turns


def _fifteen(rng: random.Random) -> dict:
    """Solved, then a long walk away — always solvable."""
    board = list(range(1, 16)) + [0]
    gap = 15
    history = []
    for _ in range(160):
        r, c = divmod(gap, 4)
        moves = []
        if r > 0: moves.append(gap - 4)
        if r < 3: moves.append(gap + 4)
        if c > 0: moves.append(gap - 1)
        if c < 3: moves.append(gap + 1)
        step = rng.choice(moves)
        board[gap], board[step] = board[step], board[gap]
        gap = step
        history.append(step)
    return {"size": 4, "board": board}, history


#: 起營前草地上最常見的三種危險物，每一格地雷用其中一種畫出來。
HAZARDS = ("nail", "glass", "ember")


def _mines(rng: random.Random) -> dict:
    """Ten hazards in the grass, each drawn as a nail, a shard or a live ember."""
    size, count = 8, 10
    spots = sorted(rng.sample(range(size * size), count))
    kinds = [HAZARDS[i % len(HAZARDS)] for i in range(count)]
    rng.shuffle(kinds)
    return {"size": size, "mines": spots, "count": count,
            "hazards": {str(spot): kind for spot, kind in zip(spots, kinds)}}, None


def _memory(rng: random.Random) -> dict:
    """Eight 專科徽章 out of the pool, twice each, shuffled."""
    chosen = rng.sample(MEMORY_BADGES, 8)
    deck = [i for i in range(len(chosen)) for _ in range(2)]
    rng.shuffle(deck)
    return {"cards": deck, "badges": chosen, "art": BADGE_ART}, None


BUILDERS = {"pipes": _pipes, "fifteen": _fifteen, "mines": _mines, "memory": _memory}


def puzzle(day: date | None = None) -> dict:
    """Today's game and board — the same answer for every caller.

    `solution` is what the browser must never see: the taps that finish the
    board. It exists so the checks can play a real game in a real browser on
    whatever day they run (`scout/routes/daily_routes.py` sends `board` only).
    """
    key = today_key(day)
    rng = random.Random(_seed(key))
    kind = ORDER[rng.randrange(len(ORDER))]
    board, solution = BUILDERS[kind](rng)
    return {"date": key, "kind": kind, "board": board, "meta": GAMES[kind],
            "solution": solution}


def points_for(elapsed_ms: int) -> int:
    return POINTS_FAST if elapsed_ms <= FAST_MS else POINTS_DONE


def ref_id(day: str) -> str:
    """The ledger key that makes a day's points payable once and only once."""
    return f"daily:{day}"
