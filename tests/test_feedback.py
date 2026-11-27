"""意見箱 — scouts report bugs and ideas; leaders reward the good ones once."""
from __future__ import annotations


def submit(scout, **over):
    body = {"kind": "bug", "title": "抽卡頁面有問題", "body": "在手機上看不到打開卡包的按鈕。"}
    body.update(over)
    return scout.post("/feedback", data=body)


def only_row(store):
    rows = store.list("feedback")
    assert len(rows) == 1
    return rows[0]


def test_a_scout_can_report_a_bug_and_see_it_waiting(store, new_scout):
    page = new_scout.get("/feedback").get_data(as_text=True)
    assert "意見箱" in page and "問題報告" in page and "建議" in page

    response = submit(new_scout)
    assert response.status_code == 200
    row = only_row(store)
    assert row["user_id"] == new_scout.id and row["kind"] == "bug"
    assert row["status"] == "new" and row["points_awarded"] in (0, "0", "")

    mine = new_scout.get("/feedback").get_data(as_text=True)
    assert "抽卡頁面有問題" in mine and "等領袖查看" in mine


def test_an_idea_is_kept_apart_from_a_bug(store, new_scout):
    submit(new_scout, kind="idea", title="想加夜行遊戲", body="希望每日挑戰多一款夜行遊戲。")
    row = only_row(store)
    assert row["kind"] == "idea"


def test_empty_or_unknown_entries_are_refused(store, new_scout):
    assert submit(new_scout, title="").status_code == 400
    assert submit(new_scout, body=" ").status_code == 400
    assert submit(new_scout, kind="praise").status_code == 400
    assert store.list("feedback") == []


def test_home_shows_the_feedback_tile_next_to_cards(store, new_scout):
    home = new_scout.get("/home").get_data(as_text=True)
    assert "意見箱" in home and 'href="/feedback' in home
    assert home.index("抽卡") < home.index("意見箱")


def test_a_leader_rewards_once_and_the_points_land(store, new_scout, leader_client):
    submit(new_scout, kind="idea", title="想加夜行遊戲", body="希望每日挑戰多一款夜行遊戲。")
    row = only_row(store)
    before = store.stats_for(new_scout.id)["points_balance"]

    queue = leader_client.get("/leader/feedback").get_data(as_text=True)
    assert "想加夜行遊戲" in queue and "給積分獎勵" in queue

    reply = leader_client.post(f"/leader/feedback/{row['id']}",
                               data={"action": "reward", "points": "8", "comment": "好主意，謝謝你。"})
    assert reply.status_code == 200
    row = store.get("feedback", row["id"])
    assert row["status"] == "rewarded" and int(row["points_awarded"]) == 8
    assert store.stats_for(new_scout.id)["points_balance"] == int(before) + 8
    ledger = [r for r in store.list("points_ledger")
              if r.get("entry_type") == "feedback" and r.get("ref_id") == row["id"]]
    assert len(ledger) == 1 and int(ledger[0]["points_delta"]) == 8

    # the scout sees the reward and the reply
    mine = new_scout.get("/feedback").get_data(as_text=True)
    assert "+8" in mine and "好主意，謝謝你。" in mine

    # a second reward is refused — points are never paid twice
    again = leader_client.post(f"/leader/feedback/{row['id']}",
                               data={"action": "reward", "points": "8"})
    assert again.status_code == 409
    assert store.stats_for(new_scout.id)["points_balance"] == int(before) + 8


def test_reward_points_must_be_in_range(store, new_scout, leader_client):
    submit(new_scout)
    row = only_row(store)
    for bad in ("0", "51", "abc"):
        reply = leader_client.post(f"/leader/feedback/{row['id']}",
                                   data={"action": "reward", "points": bad})
        assert reply.status_code == 400, bad
    assert store.get("feedback", row["id"])["status"] == "new"


def test_a_leader_can_close_and_reopen(store, new_scout, leader_client):
    submit(new_scout)
    row = only_row(store)
    closed = leader_client.post(f"/leader/feedback/{row['id']}",
                                data={"action": "close", "comment": "已經知道了。"})
    assert closed.status_code == 200
    assert store.get("feedback", row["id"])["status"] == "closed"
    assert "已處理" in new_scout.get("/feedback").get_data(as_text=True)

    handled = leader_client.get("/leader/feedback?status=handled").get_data(as_text=True)
    assert "抽卡頁面有問題" in handled
    back = leader_client.post(f"/leader/feedback/{row['id']}", data={"action": "reopen"})
    assert back.status_code == 200
    assert store.get("feedback", row["id"])["status"] == "new"


def test_each_side_only_sees_its_own_pages(store, new_scout, leader_client):
    assert new_scout.get("/leader/feedback").status_code in (302, 403)
    assert leader_client.get("/feedback").status_code in (302, 403)
    assert leader_client.post("/feedback", data={"kind": "bug", "title": "x", "body": "y"}).status_code == 403


def test_english_pages_carry_no_chinese(store, new_scout, leader_client):
    submit(new_scout, kind="idea", title="Night walk game", body="Please add a night walk game.")
    new_scout.get("/set-language/en")
    page = new_scout.get("/feedback").get_data(as_text=True)
    assert "Feedback" in page and "Bug report" in page and "Night walk game" in page
    assert "意見箱" not in page and "等領袖查看" not in page

    leader_client.get("/set-language/en")
    queue = leader_client.get("/leader/feedback").get_data(as_text=True)
    assert "Feedback" in queue and "Give points" in queue and "意見箱" not in queue


def test_the_feedback_tab_exists_in_the_schema():
    from scout.schema import COLLECTIONS
    fields = COLLECTIONS["feedback"]["fields"]
    for needed in ("user_id", "kind", "title", "body", "status", "points_awarded"):
        assert needed in fields
