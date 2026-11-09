"""每日挑戰 — one small puzzle a day, the same for everyone in the troop.

The shape is borrowed from puzzle sites: a daily game that takes a few minutes,
rotates between a handful of simple puzzles, and pays a few points. Everything
is deterministic from the Hong Kong date, so every scout in the troop opens the
same puzzle and the day's result is comparable.

Four games, each one pure data — the browser draws and judges it:

  pipes    旋轉水管   a net of pipes turned out of place; turn every piece
                      until the whole net joins up (6×6)
  fifteen  數字滑塊   the 15-puzzle, 4×4
  mines    掃雷       8×8 with ten mines
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
        "name_zh": "掃雷", "name_en": "Mines",
        "short_zh": "翻開所有安全格，避開十個地雷。",
        "short_en": "Open every safe square without hitting one of the ten mines.",
        "how_zh": ["點一格翻開；數字表示四周有幾個地雷。",
                   "長按（或先按 🚩 再點）可以插旗。",
                   "第一次點的一定安全。"],
        "how_en": ["Tap a square to open it; the number counts the mines around it.",
                   "Press and hold (or tap 🚩 first) to flag a square.",
                   "Your first tap is always safe."],
        "emoji": "💣",
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

#: 專科徽章 — the proficiency badges the matching game is played with. The day
#: draws eight of them, so the deck changes from day to day.
#: Each entry: id (drawn by the browser), the name, the badge's colour, and one
#: line saying what a scout actually does to earn it.
MEMORY_BADGES = [
    {"id": "camping", "zh": "露營", "en": "Camping", "colour": "#2c7d4f",
     "what_zh": "在野外紮營，過一晚", "what_en": "Pitch a tent and spend the night out"},
    {"id": "cooking", "zh": "烹飪", "en": "Cooking", "colour": "#b6822a",
     "what_zh": "用營火煮一餐", "what_en": "Cook a meal over a fire"},
    {"id": "firstaid", "zh": "急救", "en": "First Aid", "colour": "#b3261e",
     "what_zh": "包紮傷口，處理意外", "what_en": "Dress a wound and handle an accident"},
    {"id": "mapreading", "zh": "地圖閱讀", "en": "Map Reading", "colour": "#23527c",
     "what_zh": "讀地圖，找方向", "what_en": "Read a map and find your way"},
    {"id": "knotting", "zh": "繩結", "en": "Knotting", "colour": "#6f4e28",
     "what_zh": "打結、綁紮營架", "what_en": "Tie knots and build a lashing"},
    {"id": "astronomy", "zh": "天文", "en": "Astronomy", "colour": "#4b3f8f",
     "what_zh": "認星，看月相", "what_en": "Find the stars and the phases of the moon"},
    {"id": "swimming", "zh": "游泳", "en": "Swimming", "colour": "#1f7a8a",
     "what_zh": "游一段距離，懂救生", "what_en": "Swim a set distance and know water safety"},
    {"id": "cycling", "zh": "單車", "en": "Cycling", "colour": "#8a4a00",
     "what_zh": "安全騎行，保養單車", "what_en": "Ride safely and look after your bike"},
    {"id": "birdwatching", "zh": "觀鳥", "en": "Bird Watching", "colour": "#1f5c3a",
     "what_zh": "辨認常見雀鳥", "what_en": "Recognise the birds around you"},
    {"id": "photography", "zh": "攝影", "en": "Photography", "colour": "#4a5a53",
     "what_zh": "用照片記錄旅程", "what_en": "Tell the trip in photographs"},
    {"id": "gardening", "zh": "園藝", "en": "Gardening", "colour": "#5c7a1f",
     "what_zh": "種植，照顧植物", "what_en": "Plant something and keep it alive"},
    {"id": "weather", "zh": "氣象", "en": "Weather", "colour": "#3f6f8f",
     "what_zh": "看雲識天氣，記錄氣象", "what_en": "Read the clouds and keep a weather log"},
]

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


def _mines(rng: random.Random) -> dict:
    size, count = 8, 10
    spots = rng.sample(range(size * size), count)
    return {"size": size, "mines": sorted(spots), "count": count}, None


def _memory(rng: random.Random) -> dict:
    """Eight 專科徽章 out of the pool, twice each, shuffled."""
    chosen = rng.sample(MEMORY_BADGES, 8)
    deck = [i for i in range(len(chosen)) for _ in range(2)]
    rng.shuffle(deck)
    return {"cards": deck, "badges": chosen}, None


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
