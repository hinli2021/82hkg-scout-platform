"""Leaders can rewrite a wall painting's teaching text, not just its questions.

Game 1's story (the four walls, their timelines and the closing note) is authored
in `cave.json`. A leader who corrects a question's facts needs to correct the
wall the scout reads before answering it, so the saved wording lives in the
task's config next to the question bank and is laid over the story at play time.
"""
from __future__ import annotations

import html
import json
import re

from scout import engine
from scout.content import cave_adventure


def cave(store):
    return next(t for t in store.list("tasks") if t.get("code") == "M04")


def scene(page):
    text = page.get_data(as_text=True)
    return json.loads(html.unescape(re.search(r'data-cave-config="([^"]*)"', text).group(1)))


def wall_form(wall, **changes):
    """The four textareas as a leader would see them, already filled in."""
    form = {
        "title_zh": wall["title_zh"],
        "title_en": wall["title_en"],
        "lead_zh": "\n".join(wall["lead_zh"]),
        "lead_en": "\n".join(wall["lead_en"]),
        "timeline_zh": "\n".join(f"{row['when_zh']} ｜ {row['text_zh']}" for row in wall["timeline"]),
        "timeline_en": "\n".join(f"{row['when_en']} | {row['text_en']}" for row in wall["timeline"]),
        "facts_zh": "\n".join(f"{row['label_zh']} ｜ {row['value_zh']}" for row in wall["facts"]),
        "facts_en": "\n".join(f"{row['label_en']} | {row['value_en']}" for row in wall["facts"]),
        "note_zh": wall["note_zh"],
        "note_en": wall["note_en"],
    }
    form.update(changes)
    return form


def test_a_saved_wall_changes_what_the_scout_reads(app, store, leader_client, scout_client):
    task = cave(store)
    url = f"/leader/content/tasks/{task['id']}/cave-walls"
    page = leader_client.get(url)
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert "編輯山洞壁畫" in body
    assert 'name="timeline_zh"' in body and 'name="note_zh"' in body
    # all four walls are reachable from the editor
    for n in (1, 2, 3, 4):
        assert f"wall={n}" in body

    original = cave_adventure()["groups"][0]["wall"]
    form = wall_form(original, title_zh="壁畫一：修正後的標題",
                     title_en="Wall one — corrected title",
                     note_zh="新的筆記。", note_en="A new note.")
    response = leader_client.post(f"{url}/1", data=form)
    assert response.status_code in (200, 302)

    config = engine.as_json(store.get("tasks", task["id"])["config_json"], {})
    assert config["walls"]["1"]["title_zh"] == "壁畫一：修正後的標題"
    assert config["walls"]["1"]["note_zh"] == "新的筆記。"
    # the questions themselves are untouched by a wall edit
    assert len(config["questions"]) == 50

    played = scene(scout_client.get(f"/tasks/{task['id']}/cave"))
    wall = played["groups"][0]["wall"]
    assert wall["title_zh"] == "壁畫一：修正後的標題"
    assert wall["note_zh"] == "新的筆記。"
    assert len(wall["timeline"]) == len(original["timeline"])
    assert len(played["groups"][0]["questions"]) == 15
    # walls the leader did not touch keep the story's own words
    assert played["groups"][1]["wall"]["title_zh"] == cave_adventure()["groups"][1]["wall"]["title_zh"]


def test_a_wall_can_be_reset_to_the_original_story(app, store, leader_client, scout_client):
    task = cave(store)
    url = f"/leader/content/tasks/{task['id']}/cave-walls"
    original = cave_adventure()["groups"][1]["wall"]
    leader_client.post(f"{url}/2", data=wall_form(original, title_zh="臨時標題"))
    assert engine.as_json(store.get("tasks", task["id"])["config_json"], {})["walls"]["2"]
    leader_client.post(f"{url}/2", data={"action": "reset"})
    config = engine.as_json(store.get("tasks", task["id"])["config_json"], {})
    assert "2" not in config.get("walls", {})
    played = scene(scout_client.get(f"/tasks/{task['id']}/cave"))
    assert played["groups"][1]["wall"]["title_zh"] == original["title_zh"]


def test_malformed_wall_text_is_refused(app, store, leader_client, scout_client):
    task = cave(store)
    url = f"/leader/content/tasks/{task['id']}/cave-walls"
    original = cave_adventure()["groups"][0]["wall"]
    # mismatched Chinese / English row counts would unpick the timeline pairing
    bad = wall_form(original, timeline_en="22 February 1857 | only one row")
    response = leader_client.post(f"{url}/1", data=bad,
                                  headers={"Accept": "application/json"})
    assert response.status_code == 400
    config = engine.as_json(store.get("tasks", task["id"])["config_json"], {})
    assert "1" not in (config.get("walls") or {})
    # a blank title is refused too
    response = leader_client.post(f"{url}/1", data=wall_form(original, title_zh=""),
                                  headers={"Accept": "application/json"})
    assert response.status_code == 400


def test_every_wall_can_be_saved(app, store, leader_client):
    """The troop's own history wall carries eight key facts and the promise
    wall seven — a cap tighter than the real content made those walls
    impossible to save at all."""
    task = cave(store)
    for group in cave_adventure()["groups"]:
        response = leader_client.post(
            f"/leader/content/tasks/{task['id']}/cave-walls/{group['n']}",
            data=wall_form(group["wall"]))
        assert response.status_code in (200, 302), group["name_zh"]
    config = engine.as_json(store.get("tasks", task["id"])["config_json"], {})
    assert sorted(config["walls"]) == ["1", "2", "3", "4"]
    # the widest wall keeps every fact, in order
    assert len(config["walls"]["3"]["facts"]) == len(cave_adventure()["groups"][2]["wall"]["facts"])


def test_a_bad_wall_post_returns_the_page_not_json(app, store, leader_client):
    """A leader posting the plain HTML form must see a sentence, not an API error."""
    task = cave(store)
    group = cave_adventure()["groups"][2]
    form = wall_form(group["wall"], timeline_en="only one row")
    response = leader_client.client.post(
        f"/leader/content/tasks/{task['id']}/cave-walls/3", data=form)
    body = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "<html" in body[:400]
    assert "中文與英文的行數要相同" in body
    assert "only one row" in body          # nothing the leader typed is thrown away


def test_only_leaders_reach_the_wall_editor(app, store, leader_client, scout_client):
    task = cave(store)
    url = f"/leader/content/tasks/{task['id']}/cave-walls"
    guest = app.test_client()
    assert guest.get(url).status_code in (302, 401)
    assert scout_client.get(url).status_code in (302, 403)
    other_quiz = next(t for t in store.list("tasks") if t.get("code") == "T-11")
    assert leader_client.get(f"/leader/content/tasks/{other_quiz['id']}/cave-walls").status_code == 404
    assert leader_client.get(url + "?wall=9").status_code == 404
    assert leader_client.get(url + "?wall=zero").status_code == 404
    # the entry point is offered from the task editor and the question editor
    assert "cave-walls" in leader_client.get(f"/leader/content/tasks/{task['id']}").get_data(as_text=True)
    assert "cave-walls" in leader_client.get(f"/leader/content/tasks/{task['id']}/cave-questions").get_data(as_text=True)
