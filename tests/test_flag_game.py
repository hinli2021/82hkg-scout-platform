"""遊戲 4 — 溪谷旗桿（第 7 至 10 項）.

The ceremony is the leader's 30-question paper turned into actions. Passing
24 of 30 clears items 7, 8, 9 and 10 together; falling short clears nothing,
and a second pass does not hand out a second pack of points.
"""
from __future__ import annotations

import json
import pathlib

from scout import engine

BANK = json.loads((pathlib.Path(__file__).resolve().parent.parent / "content"
                   / "member-badge" / "ceremony-bank.json").read_text(encoding="utf-8"))


def task_of(store, code="M07"):
    return next(t for t in store.list("tasks") if t.get("code") == code)


def answers(correct=True):
    """Every question, answered right — or every one answered wrong."""
    out = {}
    for station in BANK["stations"]:
        for question in station["questions"]:
            choice = question["answer"] if correct else (question["answer"] + 1) % len(question["options_zh"])
            out[question["id"]] = str(choice)
    return out


def test_the_paper_has_thirty_questions_and_a_pass_mark_of_24():
    questions = [q for station in BANK["stations"] for q in station["questions"]]
    assert len(questions) == 30
    assert BANK["pass_mark"] == 24
    assert len({q["id"] for q in questions}) == 30


def test_the_flagpole_page_is_the_game(scout_client, store):
    task = task_of(store)
    page = scout_client.get(f"/tasks/{task['id']}/flag").get_data(as_text=True)
    assert page.count("data-flag") >= 1
    assert "flag.js" in page
    # the old paper is a study link, not the game itself
    assert "forms.gle" not in page.split("data-flag-link")[0]


def test_the_task_page_redirects_into_the_game(scout_client, store):
    task = task_of(store)
    answer = scout_client.get(f"/tasks/{task['id']}")
    assert answer.status_code == 302
    assert f"/tasks/{task['id']}/flag" in answer.headers["Location"]


def test_passing_clears_items_seven_to_ten(scout_client, store):
    task = task_of(store)
    result = scout_client.post(f"/tasks/{task['id']}/flag-submit",
                               data={**answers(True), "elapsed_ms": "240000"})
    body = result.get_json()
    assert body["ok"] and body["passed"]
    assert body["detail"]["score"] == 30

    progress = engine.progress_for(store, scout_client.id)
    badge = next(b for b in progress["badges"] if b.get("code") == "SC-01")
    states = {t["code"]: t["status"] for t in badge["tasks"]}
    assert states["M07"] == "completed"
    assert states["M08"] == "completed"
    assert states["M09"] == "completed"
    assert states["M10"] == "completed"
    # item 11 is a different game and must stay untouched
    assert states["M11"] != "completed"


def test_falling_short_clears_nothing(scout_client, store):
    task = task_of(store)
    result = scout_client.post(f"/tasks/{task['id']}/flag-submit", data=answers(False))
    assert result.status_code == 400
    body = result.get_json()
    assert body["error"] == "flag_short"
    progress = engine.progress_for(store, scout_client.id)
    badge = next(b for b in progress["badges"] if b.get("code") == "SC-01")
    assert all(t["status"] != "completed" for t in badge["tasks"] if t["code"] in ("M07", "M08", "M09", "M10"))


def test_a_replay_does_not_award_points_twice(scout_client, store):
    task = task_of(store)
    scout_client.post(f"/tasks/{task['id']}/flag-submit", data=answers(True))
    first = engine.points_summary(store, scout_client.id)["balance"]
    again = scout_client.post(f"/tasks/{task['id']}/flag-submit", data=answers(True)).get_json()
    assert again["already_done"] is True
    second = engine.points_summary(store, scout_client.id)["balance"]
    assert second == first


def test_the_map_offers_the_flagpole(scout_client, store):
    badge = next(b for b in store.list("badges") if b.get("code") == "SC-01")
    page = scout_client.get(f"/badges/{badge['id']}").get_data(as_text=True)
    assert "溪谷旗桿" in page
    assert page.count("即將推出") == 1
