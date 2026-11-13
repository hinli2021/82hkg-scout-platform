"""我的個人檔案 — progress overview, personal words, patrol member visits."""
from __future__ import annotations


def find(store, username):
    return next(u for u in store.list("users") if u["username"] == username)


def test_my_profile_shows_a_progress_overview(store, new_scout):
    page = new_scout.get("/profile").get_data(as_text=True)
    assert "我的個人檔案" in page and "進度總覽" in page
    assert "獎章" in page and "任務" in page and "積分" in page
    assert "興趣" in page and "童軍經驗" in page and "想和大家分享的事" in page
    assert "讓其他童軍看我的個人檔案" in page


def test_the_old_history_address_lands_on_my_profile(store, new_scout):
    response = new_scout.get("/history")
    assert response.status_code == 302
    assert "/profile" in response.headers["Location"]
    home = new_scout.get("/home").get_data(as_text=True)
    assert "我的紀錄" not in home and 'href="/profile' in home


def test_a_scout_can_save_personal_words_and_choose_to_share(store, new_scout):
    reply = new_scout.post("/profile", data={
        "interests": "露營、繩結、音樂",
        "experience": "我參加了童軍兩年，去過一次大露營。",
        "share": "我喜歡畫畫，也喜歡教新成員綁繩結。",
        "visible": "1",
    })
    assert reply.status_code == 200
    row = store.get("profiles", new_scout.id)
    assert row["interests"] == "露營、繩結、音樂"
    assert row["visible"] in (True, "true", 1)

    page = new_scout.get("/profile").get_data(as_text=True)
    assert "露營、繩結、音樂" in page and "checked" in page


def test_profiles_are_private_until_the_scout_shares(store, new_scout, scout_client):
    new_scout.post("/profile", data={
        "interests": "天文", "experience": "參加了童軍三年。", "share": "想分享星星的故事。",
    })
    # scout03 visits scout07 before anything is shared
    locked = scout_client.get(f"/profile/{new_scout.id}").get_data(as_text=True)
    assert "尚未公開個人檔案" in locked
    assert "天文" not in locked and "星星的故事" not in locked

    new_scout.post("/profile", data={
        "interests": "天文", "experience": "參加了童軍三年。", "share": "想分享星星的故事。",
        "visible": "1",
    })
    open_page = scout_client.get(f"/profile/{new_scout.id}").get_data(as_text=True)
    assert "天文" in open_page and "參加了童軍三年" in open_page
    assert "想分享星星的故事" in open_page and "進度總覽" in open_page


def test_the_patrol_list_groups_scouts_and_marks_who_is_open(store, new_scout, scout_client):
    other = find(store, "scout04")
    store.insert("profiles", {
        "user_id": other["id"], "interests": "足球", "experience": "", "share": "",
        "visible": True, "updated_at": "2026-01-01",
    })
    page = new_scout.get("/profile").get_data(as_text=True)
    assert "各小隊成員" in page
    members = page[page.index("各小隊成員"):]
    assert "老虎" in members and "水獺" in members and "海鷗" in members
    assert f'href="/profile/{other["id"]}' in page
    assert "未公開" in page  # somebody on the list has not shared yet


def test_long_entries_are_refused(store, new_scout):
    reply = new_scout.post("/profile", data={"experience": "長" * 1001})
    assert reply.status_code == 400
    assert store.get("profiles", new_scout.id) is None


def test_leaders_and_unknown_scouts_stay_out(store, new_scout, leader_client):
    assert leader_client.get("/profile").status_code in (302, 403)
    assert new_scout.get("/profile/no-such-scout").status_code == 404
    leader = find(store, "leader1")
    assert new_scout.get(f"/profile/{leader['id']}").status_code == 404


def test_english_profile_carries_no_chinese_headings(store, new_scout):
    new_scout.get("/set-language/en")
    page = new_scout.get("/profile").get_data(as_text=True)
    assert "My profile" in page and "Progress overview" in page
    assert "Scouts by patrol" in page
    assert "我的個人檔案" not in page and "進度總覽" not in page


def test_the_profiles_tab_exists_in_the_schema():
    from scout.schema import COLLECTIONS, key_field
    assert COLLECTIONS["profiles"]["fields"] == [
        "user_id", "interests", "experience", "share", "visible", "updated_at"]
    assert key_field("profiles") == "user_id"
