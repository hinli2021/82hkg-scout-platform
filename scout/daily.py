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
        "name_zh": "水管接駁", "name_en": "Pipework",
        "short_zh": "轉動每一段水管，把整條水路接成一個網絡。",
        "short_en": "Turn each pipe until the whole net joins up.",
        "how_zh": ["點一下水管，它會順時針轉 90 度。",
                   "當所有接口都與鄰居對上，而且全部連在一起，就完成。",
                   "沒有計步限制，慢慢想。"],
        "how_en": ["Tap a pipe to turn it a quarter turn clockwise.",
                   "The net is done when every opening meets a neighbour's and the whole lot is one piece.",
                   "No move limit — take your time."],
        "emoji": "🔧",
    },
    "fifteen": {
        "name_zh": "數字滑塊", "name_en": "Slide fifteen",
        "short_zh": "把 1 至 15 順序排好，右下角留空。",
        "short_en": "Slide 1 to 15 into order, leaving the bottom-right corner empty.",
        "how_zh": ["點空格旁邊的方塊，它就會滑進空格。",
                   "把 1 至 15 由左上角起順序排好，右下角留空即完成。"],
        "how_en": ["Tap a tile beside the gap and it slides in.",
                   "Finish with 1–15 in order from the top left and the gap in the bottom-right corner."],
        "emoji": "🔢",
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
        "name_zh": "記憶配對", "name_en": "Memory pairs",
        "short_zh": "翻開兩張一樣的童軍圖案，配成八對。",
        "short_en": "Turn up matching Scout pictures — eight pairs.",
        "how_zh": ["每次翻開兩張，圖案一樣就配成一對，留在桌上。",
                   "八對全部配好就完成；記住位置會快好多。"],
        "how_en": ["Turn two cards at a time; a matching pair stays face up.",
                   "Eight pairs finishes the game — remembering where things were is the whole trick."],
        "emoji": "🃏",
    },
}

ORDER = ["pipes", "fifteen", "mines", "memory"]

MEMORY_FACES = ["⚜️", "🏕️", "🔥", "🧭", "🪢", "⛺", "🌲", "🛶"]

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
    deck = [i for i in range(len(MEMORY_FACES)) for _ in range(2)]
    rng.shuffle(deck)
    return {"cards": deck, "faces": MEMORY_FACES}, None


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
