"""Leaders can revise one cave question/answer without breaking its four walls."""
from __future__ import annotations

import html
import json
import os
import pathlib
import re
import subprocess
import sys

from scout import engine

ROOT = pathlib.Path(__file__).resolve().parents[1]


def cave(store):
    return next(t for t in store.list("tasks") if t.get("code") == "M04")


def bank(store):
    return engine.as_json(store.get("tasks", cave(store)["id"])["config_json"], {})


def form_for(q):
    form = {
        "question_id": q["id"], "q_zh": q["q_zh"], "q_en": q["q_en"],
        "explain_zh": q.get("explain_zh") or "", "explain_en": q.get("explain_en") or "",
        "answer": str(q["answer"]),
    }
    for i in range(4):
        option = q["options"][i] if i < len(q["options"]) else ""
        form[f"option_{i}_zh"] = option.get("zh", "") if isinstance(option, dict) else option
        form[f"option_{i}_en"] = option.get("en", "") if isinstance(option, dict) else option
    return form


def cave_scene(page):
    text = page.get_data(as_text=True)
    return json.loads(html.unescape(re.search(r'data-cave-config="([^"]*)"', text).group(1)))


def test_only_leaders_can_open_and_change_the_cave_bank(app, store, leader_client, scout_client):
    task = cave(store)
    url = f"/leader/content/tasks/{task['id']}/cave-questions"
    page = leader_client.get(url).get_data(as_text=True)
    assert "編輯山洞題目" in page and 'name="answer"' in page
    assert page.count('class="cave-editor-link ') == 50
    assert task["config_json"]["questions"][0]["id"] in page
    assert f"href=\"{url}" in leader_client.get("/leader/content").get_data(as_text=True)
    from scout.content import cave_adventure
    groups = cave_adventure()["groups"]
    last_id = groups[-1]["questions"][-1]  # last in wall order, not in bank order
    last_index = next(i for i, q in enumerate(bank(store)["questions"]) if q["id"] == last_id)
    last = leader_client.get(url + f"?q={last_index}").get_data(as_text=True)
    assert '50 / 50' in last and 'name="question_id" value="' + last_id + '"' in last
    # The bank interleaves wall 3 and 4. Previous/next must follow the wall,
    # never skip ahead to another painting just because its bank index is next.
    third_id = groups[2]["questions"][-1]
    fourth_id = groups[3]["questions"][0]
    third_index = next(i for i, q in enumerate(bank(store)["questions"]) if q["id"] == third_id)
    fourth_index = next(i for i, q in enumerate(bank(store)["questions"]) if q["id"] == fourth_id)
    third = leader_client.get(url + f"?q={third_index}").get_data(as_text=True)
    fourth = leader_client.get(url + f"?q={fourth_index}").get_data(as_text=True)
    assert f'q={fourth_index}' in re.search(r'<a class="btn ghost" href="([^"]+)">下一題', third).group(1)
    assert f'q={third_index}' in re.search(r'<a class="btn ghost" href="([^"]+)">← 上一題', fourth).group(1)
    assert leader_client.get(url + "?q=50").status_code == 404
    assert leader_client.get(url + "?q=garbage").status_code == 404

    form = form_for(bank(store)["questions"][0])
    guest = app.test_client()
    for visitor, status in ((guest, 401), (scout_client, 403)):
        for method, path, kwargs in (("get", url, {}), ("post", url + "/0", {"data": form})):
            response = getattr(visitor, method)(path, headers={"Accept": "application/json"}, **kwargs)
            assert response.status_code == status
    other_quiz = next(t for t in store.list("tasks") if t.get("code") == "T-11")
    assert leader_client.get(f"/leader/content/tasks/{other_quiz['id']}/cave-questions").status_code == 404
    assert bank(store)["questions"][0]["q_zh"] == form["q_zh"]


def test_one_edit_preserves_question_ids_groups_and_previous_progress(
        store, leader_client, new_scout):
    task = cave(store)
    before = bank(store)
    original = before["questions"][0]
    completed = next(r for r in store.list("progress_records") if r.get("task_id") == task["id"])
    stats = store.stats_for(completed["user_id"])
    counts = (len(store.list("progress_records")), len(store.list("points_ledger")))

    form = form_for(original)
    form.update(q_zh="新的歷史問題是甚麼？", q_en="Which event changed Scouting?",
                answer=str((original["answer"] + 1) % 4),
                explain_zh="重溫壁畫的年份，再作選擇。",
                explain_en="Read the wall's dates, then choose again.",
                option_0_zh="年代甲", option_0_en="Year A",
                option_1_zh="年代乙", option_1_en="Year B")
    path = f"/leader/content/tasks/{task['id']}/cave-questions/0"
    result = leader_client.post(path, data=form)
    assert result.status_code == 200 and result.get_json()["ok"]
    updated = bank(store)
    assert len(updated["questions"]) == 50
    assert updated["questions"][1:] == before["questions"][1:]
    assert [q["id"] for q in updated["questions"]] == [q["id"] for q in before["questions"]]
    assert updated["questions"][0]["part"] == original["part"]
    assert updated["questions"][0].get("review_note") == original.get("review_note")
    assert updated["questions"][0]["answer"] == int(form["answer"])
    assert updated["questions"][0]["options"][0] == {"zh": "年代甲", "en": "Year A"}
    assert store.get("progress_records", completed["id"]) == completed
    assert store.stats_for(completed["user_id"]) == stats
    assert counts == (len(store.list("progress_records")), len(store.list("points_ledger")))
    assert any(a.get("action") == "edit_cave_question" and a.get("entity_id") == task["id"]
               for a in store.list("audit_log"))

    scene = cave_scene(new_scout.get(f"/tasks/{task['id']}/cave"))
    first = scene["groups"][0]["questions"][0]
    assert first["id"] == original["id"] and first["bank"] == 0
    assert first["q_zh"] == form["q_zh"] and first["q_en"] == form["q_en"]
    assert first["explain_en"] == form["explain_en"]
    assert len(first["options"]) == 4
    assert next(o for o in first["options"] if o["idx"] == 0)["label_en"] == "Year A"
    assert next(o for o in first["options"] if o["ok"])["idx"] == int(form["answer"])

    answers = {f"q{i}": str(q["answer"]) for i, q in enumerate(updated["questions"])}
    answers["q0"] = str(original["answer"])
    missed = new_scout.post(f"/tasks/{task['id']}/cave-submit", data=answers).get_json()
    assert missed["passed"] and missed["score"] == 98
    answers["q0"] = form["answer"]
    replay = new_scout.post(f"/tasks/{task['id']}/cave-submit", data=answers).get_json()
    assert replay["passed"] and replay["score"] == 100 and replay["already_done"]


def test_invalid_changes_do_not_replace_or_truncate_the_bank(store, leader_client):
    task = cave(store)
    old = bank(store)
    question = old["questions"][0]
    valid = form_for(question)
    path = f"/leader/content/tasks/{task['id']}/cave-questions/0"
    invalid = (
        ({**valid, "question_id": "甲999"}, 409),
        ({**valid, "q_zh": ""}, 400),
        ({**valid, "explain_zh": ""}, 400),
        ({**valid, "option_1_zh": ""}, 400),
        ({**valid, "answer": "9"}, 400),
        ({**valid, "option_3_zh": "", "answer": "3"}, 400),
        ({**valid, "option_1_zh": valid["option_0_zh"]}, 400),
        ({**valid, "option_1_en": valid["option_0_en"]}, 400),
    )
    for form, code in invalid:
        assert leader_client.post(path, data=form).status_code == code
        assert bank(store) == old
    # The ordinary quiz editor cannot wipe 50 IDs even with a forged POST.
    assert leader_client.post(f"/leader/content/tasks/{task['id']}",
                              data={"quiz_zh": "1 + 1? | 2 | 1 | 2 | 3"}).status_code == 400
    assert leader_client.post(f"/leader/content/tasks/{task['id']}",
                              data={"config_json": json.dumps({"questions": []})}).status_code == 400
    assert bank(store) == old


def test_fourth_choice_can_be_removed_but_not_a_required_choice(store, leader_client, new_scout):
    task = cave(store)
    original = bank(store)["questions"][0]
    form = form_for(original)
    form["option_3_zh"] = form["option_3_en"] = ""
    form["answer"] = "2"
    resp = leader_client.post(f"/leader/content/tasks/{task['id']}/cave-questions/0", data=form)
    assert resp.status_code == 200
    assert len(bank(store)["questions"][0]["options"]) == 3
    scene = cave_scene(new_scout.get(f"/tasks/{task['id']}/cave"))
    assert len(scene["groups"][0]["questions"][0]["options"]) == 3


def test_in_progress_run_keeps_the_bank_shown_at_entry(
        store, leader_client, new_scout, scout_client):
    """Editing a live question must not mark a scout's correct old answer wrong."""
    task = cave(store)
    original = bank(store)
    opened = cave_scene(new_scout.get(f"/tasks/{task['id']}/cave"))
    old_key = opened["run_key"]
    assert old_key and opened["groups"][0]["questions"][0]["id"] == original["questions"][0]["id"]
    old_answers = {f"q{i}": str(q["answer"]) for i, q in enumerate(original["questions"])}
    old_answers["run_key"] = old_key
    path = f"/tasks/{task['id']}/cave-submit"

    # This snapshot belongs only to the scout who opened the page. A modified
    # token cannot be used to change the grade, and neither can a token from a
    # different scout's account.
    bad = new_scout.post(path, data={**old_answers, "run_key": "!" + old_key})
    assert bad.status_code == 400
    assert scout_client.post(path, data=old_answers).status_code == 400

    form = form_for(original["questions"][0])
    form["answer"] = "2"
    form["option_3_zh"] = form["option_3_en"] = ""  # fourth choice now removed
    assert leader_client.post(f"/leader/content/tasks/{task['id']}/cave-questions/0",
                              data=form).get_json()["ok"]
    assert len(bank(store)["questions"][0]["options"]) == 3

    # The old tab still grades against its own four-choice key, including the
    # original correct answer. It wins on completion and leaves no duplicate
    # progress or points if the player opens a new tab and submits again.
    result = new_scout.post(path, data=old_answers).get_json()
    assert result["passed"] and result["score"] == 100 and not result["already_done"]
    record = next(r for r in store.list("progress_records")
                  if r["user_id"] == new_scout.id and r["task_id"] == task["id"])
    assert record["score"] == 100
    fresh = cave_scene(new_scout.get(f"/tasks/{task['id']}/cave"))
    assert fresh["run_key"] != old_key
    assert len(fresh["groups"][0]["questions"][0]["options"]) == 3
    latest_answers = {f"q{i}": str(q["answer"]) for i, q in enumerate(bank(store)["questions"])}
    latest_answers["run_key"] = fresh["run_key"]
    assert new_scout.post(path, data=latest_answers).get_json()["already_done"]


def test_rebuilding_offline_copy_includes_local_leader_edits(store, data_dir, leader_client):
    task = cave(store)
    form = form_for(bank(store)["questions"][0])
    form["q_zh"] = "離線新題目測試？"
    form["q_en"] = "Offline edited question?"
    form["answer"] = str((int(form["answer"]) + 1) % 4)
    assert leader_client.post(f"/leader/content/tasks/{task['id']}/cave-questions/0",
                              data=form).get_json()["ok"]
    output = pathlib.Path(data_dir) / "local-edits-preview.html"
    env = {**os.environ, "OFFLINE_SOURCE_DATA_DIR": data_dir,
           "OFFLINE_OUTPUT_PATH": str(output)}
    result = subprocess.run([sys.executable, str(ROOT / "tools/offline_demo.py")],
                            cwd=ROOT, env=env, capture_output=True, text=True, check=True)
    assert "offline cave questions: copied from local leader content" in result.stdout
    raw = output.read_text()
    payload = json.loads(html.unescape(re.search(r'data-cave-config="([^"]*)"', raw).group(1)))
    assert payload["submit_url"] == "" and "run_key" not in payload and len(payload["groups"]) == 4
    assert payload["groups"][0]["questions"][0]["q_zh"] == form["q_zh"]
    assert payload["groups"][0]["questions"][0]["q_en"] == form["q_en"]
    assert next(o for o in payload["groups"][0]["questions"][0]["options"] if o["ok"])["idx"] == int(form["answer"])
