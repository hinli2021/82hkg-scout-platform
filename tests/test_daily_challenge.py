"""每日挑戰 — the daily puzzle: one board a day, a few points, paid once.

The board is built from the Hong Kong date, so everyone in the troop plays the
same thing. These tests pin down the parts that must never drift:
  · the same day always builds the same board, and the four games rotate
  · every board is fair (the pipes join up, the 15-puzzle is solvable, the mines
    are ten distinct squares, the memory deck is eight pairs)
  · the page never carries the solution
  · finishing pays once a day, only for the signed ticket, only for today
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta

import pytest

from scout import daily


def config_of(page) -> dict:
    text = page.get_data(as_text=True)
    raw = re.search(r'<script id="daily-config" type="application/json">(.*?)</script>',
                    text, re.S).group(1)
    return json.loads(raw)


def day_playing(monkeypatch, kind: str) -> str:
    """Freeze the daily puzzle on a real date that happens to play `kind`."""
    for offset in range(60):
        probe = date(2026, 1, 1) + timedelta(days=offset)
        if daily.puzzle(probe)["kind"] == kind:
            monkeypatch.setattr(daily, "today_key", lambda day=None, _d=probe: _d.isoformat())
            return probe.isoformat()
    raise AssertionError(f"no {kind} day in 60 days")


# ── the boards themselves ───────────────────────────────────────────────────

def test_the_same_day_builds_the_same_board_and_the_games_rotate():
    a, b = daily.puzzle(date(2026, 10, 13)), daily.puzzle(date(2026, 10, 13))
    assert a == b
    kinds = {daily.puzzle(date(2026, 10, 13) + timedelta(days=i))["kind"] for i in range(24)}
    assert kinds == set(daily.ORDER)


def test_every_board_is_fair_and_finishable():
    for offset in range(40):
        p = daily.puzzle(date(2026, 10, 13) + timedelta(days=offset))
        board = p["board"]
        if p["kind"] == "pipes":
            cells = board["cells"]
            assert len(cells) == 36 and all(c["m"] for c in cells)
            assert any(c["t"] for c in cells), "a pipes board must not start solved"
            assert len(p["solution"]) == 36
        elif p["kind"] == "fifteen":
            seq = [v for v in board["board"] if v]
            inversions = sum(1 for i in range(len(seq)) for j in range(i + 1, len(seq))
                             if seq[i] > seq[j])
            blank_row_from_bottom = 4 - (board["board"].index(0) // 4)
            assert (inversions + blank_row_from_bottom) % 2 == 1, "15-puzzle must be solvable"
            assert board["board"] != list(range(1, 16)) + [0]
            assert len(p["solution"]) == 160
        elif p["kind"] == "mines":
            assert len(board["mines"]) == 10 == len(set(board["mines"]))
            assert all(0 <= spot < 64 for spot in board["mines"])
        elif p["kind"] == "memory":
            assert len(board["cards"]) == 16
            assert sorted(board["cards"].count(i) for i in range(8)) == [2] * 8
            badges = board["badges"]
            assert len(badges) == 8 == len({b["id"] for b in badges})
            assert all(b["zh"] and b["what_zh"] and b["group_zh"] for b in badges)
            # the official badge artwork must actually be in the repo
            import pathlib
            root = pathlib.Path(__file__).resolve().parents[1]
            for badge in badges:
                art = root / "static" / "img" / "badges" / badge["art"]
                assert art.exists(), f"missing badge art {badge['art']}"
                assert art.stat().st_size > 1000


def test_the_matching_deck_is_proficiency_badges_and_changes_by_day():
    from scout import daily as d
    assert len(d.MEMORY_BADGES) >= 12
    names = {"露營", "烹飪", "急救", "地圖閱讀", "天象", "游泳", "單車", "運動"}
    assert names <= {b["zh"] for b in d.MEMORY_BADGES}
    groups = {b["group_zh"] for b in d.MEMORY_BADGES}
    assert {"興趣組", "技能組", "服務組"} <= groups, "badges should span the training scheme's groups"
    decks = []
    for offset in range(40):
        p = d.puzzle(date(2026, 10, 13) + timedelta(days=offset))
        if p["kind"] == "memory":
            decks.append(tuple(sorted(b["zh"] for b in p["board"]["badges"])))
    assert len(decks) >= 5 and len(set(decks)) >= 4, "the badge deck should vary from day to day"
    assert all(len(deck) == 8 for deck in decks)


def test_points_are_three_for_finishing_and_five_for_a_quick_run():
    assert daily.points_for(daily.FAST_MS - 1) == daily.POINTS_FAST
    assert daily.points_for(daily.FAST_MS + 1) == daily.POINTS_DONE
    assert daily.points_for(2 * 60 * 1000) == 5
    assert daily.points_for(9 * 60 * 1000) == 3


# ── the page ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("kind", ["pipes", "fifteen", "mines", "memory"])
def test_each_game_can_be_played_without_leaking_the_answer(app, store, scout_client, monkeypatch, kind):
    day_playing(monkeypatch, kind)
    response = scout_client.get("/daily")
    assert response.status_code == 200
    config = config_of(response)
    assert config["kind"] == kind
    assert config["board"].get("size") or config["board"].get("cards")
    assert "solution" not in config and "turns" not in config["board"]
    assert "moves" not in config["board"]
    assert config["ticket"] and config["submit_url"].endswith("/daily/finish")
    body = response.get_data(as_text=True)
    assert "每日挑戰" in body and "daily.js" in body


def test_finishing_pays_once_a_day(app, store, scout_client, monkeypatch):
    day_playing(monkeypatch, "memory")
    config = config_of(scout_client.get("/daily"))
    with scout_client.client.session_transaction() as _:   # noqa: F841  (keeps the client in one session)
        pass
    before = store.stats_for(scout_client.id)["points_balance"]

    first = scout_client.post("/daily/finish",
                              json={"ticket": config["ticket"], "elapsed_ms": 90_000})
    body = first.get_json()
    assert first.status_code == 200 and body["ok"] and body["points"] == 5
    assert body["balance"] == before + 5
    assert store.stats_for(scout_client.id)["points_balance"] == before + 5

    again = scout_client.post("/daily/finish",
                              json={"ticket": config["ticket"], "elapsed_ms": 95_000})
    assert again.status_code == 200
    assert again.get_json()["already"] is True and again.get_json()["points"] == 0
    assert store.stats_for(scout_client.id)["points_balance"] == before + 5

    # the ledger says what it was for, and only once
    rows = [r for r in store.list("points_ledger")
            if r.get("user_id") == scout_client.id and r.get("entry_type") == "daily"]
    assert len(rows) == 1 and rows[0]["ref_id"] == daily.ref_id(daily.today_key())
    assert rows[0]["points_delta"] == 5 and "每日挑戰" in rows[0]["reason_zh"]

    # a slow finish the next day is worth three
    tomorrow = (date.fromisoformat(daily.today_key()) + timedelta(days=1)).isoformat()
    monkeypatch.setattr(daily, "today_key", lambda day=None, _d=tomorrow: _d)
    config2 = config_of(scout_client.get("/daily"))
    slow = scout_client.post("/daily/finish",
                             json={"ticket": config2["ticket"], "elapsed_ms": 9 * 60 * 1000})
    assert slow.get_json()["points"] == 3


def test_a_ticket_from_another_day_or_account_is_refused(app, store, scout_client, monkeypatch):
    day_playing(monkeypatch, "memory")
    config = config_of(scout_client.get("/daily"))

    assert scout_client.post("/daily/finish", json={"ticket": "nonsense",
                                                    "elapsed_ms": 90_000}).status_code == 400
    assert scout_client.post("/daily/finish", json={"ticket": config["ticket"],
                                                    "elapsed_ms": 100}).status_code == 400
    assert scout_client.post("/daily/finish", json={"ticket": config["ticket"],
                                                    "elapsed_ms": 3 * 3600 * 1000}).status_code == 400

    # tomorrow, today's ticket is a stale ticket
    tomorrow = (date.fromisoformat(daily.today_key()) + timedelta(days=1)).isoformat()
    monkeypatch.setattr(daily, "today_key", lambda day=None, _d=tomorrow: _d)
    late = scout_client.post("/daily/finish", json={"ticket": config["ticket"],
                                                    "elapsed_ms": 90_000})
    assert late.status_code == 409
    # …and nothing was paid
    assert not [r for r in store.list("points_ledger")
                if r.get("user_id") == scout_client.id and r.get("entry_type") == "daily"]


def test_the_daily_is_for_scouts_and_appears_on_home(app, store, scout_client, leader_client, monkeypatch):
    day_playing(monkeypatch, "pipes")
    assert leader_client.get("/daily").status_code in (302, 403)
    assert app.test_client().get("/daily").status_code in (302, 401)

    home = scout_client.get("/home").get_data(as_text=True)
    # the daily challenge is a square button on home, shaped like a badge tile
    assert "badge-tiles feature-tiles" in home and "badge-tile feature-tile" in home
    assert "daily-teaser" not in home and "每日挑戰" in home
    assert "每日挑戰" in scout_client.get("/home").get_data(as_text=True)

    page = scout_client.get("/daily").get_data(as_text=True)
    assert "這一個星期" in page
    assert "連續" not in page or "streak" in page.lower()
