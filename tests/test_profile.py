"""我的個人檔案 — progress overview, personal words, patrol member visits."""
from __future__ import annotations


def find(store, username):
    return next(u for u in store.list("users") if u["username"] == username)


def test_my_profile_shows_a_progress_overview(store, new_scout):
    page = new_scout.get("/profile").get_data(as_text=True)
    assert "我的個人檔案" in page and "狀態總覽" in page
    # the card shows points only: no badge count, task count or streak
    assert "積分" in page and "poke-bottom" not in page
    assert 'char-stat-k">獎章' not in page and 'char-stat-k">任務' not in page
    assert 'char-stat-k">連續天數' not in page
    assert "興趣" in page and "童軍經驗" in page and "想和大家分享的事" in page
    assert "個人檔案會公開給其他童軍看" in page
    assert "請先完成個人檔案" in page  # the blocking pop-up is already up
    # the profile is a character card now: portrait front, status back
    assert "data-char-card" in page and "data-char-front" in page and "data-char-back" in page
    assert "看背面" in page and "職位" in page


def test_experience_is_two_dropdowns_of_camping_days_and_hikes(store, new_scout):
    page = new_scout.get("/profile").get_data(as_text=True)
    # the written paragraph is gone from both forms: two lists take its place
    assert 'name="experience"' not in page
    assert '<select name="camping_days"' in page and '<select name="hiking_times"' in page
    assert "露營天數" in page and "行山次數" in page and "20以上" in page
    for name in ("camping_days", "hiking_times"):
        start = page.index(f'name="{name}"')
        options = page[start:page.index("</select>", start)]
        for n in range(21):
            assert f'value="{n}"' in options
        assert 'value="20+"' in options

    # picking only one of the two is not a finished experience
    reply = new_scout.post("/profile", data={
        "position": "隊員", "interests": "露營", "camping_days": "6",
        "share": "喜歡幫忙。", "strength": "繩結",
    })
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "profile_empty"
    assert store.get("profiles", new_scout.id) is None

    # 0 is a real pick, and 20+ is the top of the list
    reply = new_scout.post("/profile", data={
        "position": "隊員", "interests": "露營", "camping_days": "0",
        "hiking_times": "20+", "share": "喜歡幫忙。", "strength": "繩結",
    })
    assert reply.status_code == 200
    row = store.get("profiles", new_scout.id)
    assert row["camping_days"] == "0" and row["hiking_times"] == "20+"
    assert row["experience"] == ""  # the counts replace the paragraph

    page = new_scout.get("/profile").get_data(as_text=True)
    assert "露營天數" in page and "行山次數" in page and "20+" in page
    assert 'value="0" selected' in page and 'value="20+" selected' in page
    assert "請先完成個人檔案" not in page  # both zeros-and-all still complete


def test_the_experience_dropdowns_are_english_on_english_pages(store, new_scout):
    new_scout.get("/set-language/en")
    page = new_scout.get("/profile").get_data(as_text=True)
    assert "Camping days" in page and "Hikes" in page and "20 or more" in page
    assert '<select name="camping_days"' in page
    # the picked lists read in English too, values unchanged
    assert '<select name="position_choice"' in page and "Patrol contact" in page
    assert "My strength (other)" in page and "Other" in page


def test_the_old_history_address_lands_on_my_profile(store, new_scout):
    response = new_scout.get("/history")
    assert response.status_code == 302
    assert "/profile" in response.headers["Location"]
    home = new_scout.get("/home").get_data(as_text=True)
    assert "我的紀錄" not in home and 'href="/profile' in home


def test_a_scout_can_save_personal_words_and_the_profile_is_public(store, new_scout):
    reply = new_scout.post("/profile", data={
        "position": "聯絡",
        "interests": "露營、繩結、音樂",
        "experience": "我參加了童軍兩年，去過一次大露營。",
        "share": "我喜歡畫畫，也喜歡教新成員綁繩結。", "strength": "畫畫",
    })
    assert reply.status_code == 200
    row = store.get("profiles", new_scout.id)
    assert row["position"] == "聯絡" and row["interests"] == "露營、繩結、音樂"
    assert row["visible"] in (True, "true", 1)

    page = new_scout.get("/profile").get_data(as_text=True)
    assert "露營、繩結、音樂" in page and "聯絡" in page  # the card shows the position
    # once a leader appoints the scout patrol leader, the card wears it —
    # leaders appoint ranks; the scout never picks one (see below). A row
    # still carrying the old spelling 小隊長 reads as 隊長.
    store.update("profiles", new_scout.id, {"position": "小隊長"})
    page = new_scout.get("/profile").get_data(as_text=True)
    assert "隊長" in page and "小隊長" not in page
    assert "請先完成個人檔案" not in page  # complete: the pop-up is gone
    # the front follows a monster trading card: name, picture window,
    # info strip (number, patrol, position), then the moves — no HP
    front = page[page.index("data-char-front"):page.index("data-char-back")]
    assert "poke-head" in front and "HP" not in front and "poke-info" in front
    assert "poke-moves" in front and "童軍經驗" in front
    # strength sits on the front too, in the interests row, same format
    assert "我的強項" in front and "poke-abilities" in front
    # a 隊長 wears the two-band insignia, bands either side of the emblem
    assert "rank-bar rank-count-2" in front and front.count("rank-stripe") == 4
    assert "poke-rarity" not in front and "poke-bottom" not in front


def test_position_strength_and_interests_are_picked_from_lists(store, new_scout):
    page = new_scout.get("/profile").get_data(as_text=True)
    # all three are lists now, each with an Other that opens a text box
    assert '<select name="position_choice"' in page
    assert '<select name="strength_choice"' in page
    # 興趣 is a row of tap-to-pick checkboxes, so any number can be picked
    assert '<select name="interest_picks"' not in page
    assert page.count('type="checkbox" name="interest_picks"') >= 18
    assert "可多選" in page
    assert 'name="position"' not in page and 'name="strength"' not in page
    for word in ("聯絡", "康樂", "文書", "物資管理", "氣象員", "報時員", "情緒輔助"):
        assert f'value="{word}"' in page
    # the four patrol ranks are not picked here any more, under their
    # proper titles or the old spellings
    for word in ("隊員", "副隊長", "隊長", "團隊長",
                 "副小隊長", "小隊長", "高級小隊長"):
        assert f'<option value="{word}"' not in page
    assert 'value="__other__"' in page and ">其他<" in page
    for word in ("露營", "行山", "電子遊戲", "攝影", "繩結", "急救", "照顧他人"):
        assert f'value="{word}"' in page
    assert 'data-other-box="position_choice" hidden' in page
    assert 'data-other-box="strength_choice" hidden' in page
    assert 'data-other-box="interest_picks" hidden' in page

    def save(**overrides):
        data = {
            "position_choice": "聯絡",
            "interest_picks": ["露營", "__other__"],
            "interests_other": "觀鳥",
            "camping_days": "3", "hiking_times": "2",
            "share": "喜歡幫忙。",
            "strength_choice": "__other__", "strength_other": "守夜",
        }
        data.update(overrides)
        return new_scout.post("/profile", data=data)

    # Other picked but left blank is not a finished answer
    reply = save(position_choice="__other__")
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "profile_position"
    assert store.get("profiles", new_scout.id) is None

    reply = save()
    assert reply.status_code == 200
    row = store.get("profiles", new_scout.id)
    assert row["position"] == "聯絡"
    # Other is stored and shown as the words themselves, no 其他： in front
    assert row["interests"] == "露營、觀鳥"
    assert row["strength"] == "守夜"

    page = new_scout.get("/profile").get_data(as_text=True)
    assert "其他：觀鳥" not in page and "其他：守夜" not in page
    front = page[page.index("data-char-front"):page.index("data-char-back")]
    assert "觀鳥" in front and "露營" in front
    assert 'class="poke-position">🎖 聯絡' in front  # the position stands out
    # the edit form offers every pick back, Other words in their boxes
    assert 'value="聯絡" data-desc-zh="記錄出席，聯絡和通知大家。" data-desc-en="Records attendance, and contacts and reminds everyone." selected' in page
    assert 'value="守夜"' in page and 'value="觀鳥"' in page
    assert 'data-other-box="position_choice" hidden' in page  # 聯絡 is listed

    # interests stop at three picks, Other counting as one of them
    reply = save(interest_picks=["露營", "行山", "足球", "籃球"])
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "profile_interests"
    assert store.get("profiles", new_scout.id)["interests"] == "露營、觀鳥"

    # an Other position that runs too long is refused, like the other fields
    reply = save(position_choice="__other__", position_other="職" * 41,
                 position_desc="負責帶隊")
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "profile_long"
    assert store.get("profiles", new_scout.id)["position"] == "聯絡"


def test_an_other_prefix_from_the_first_list_version_is_not_shown(store, new_scout, scout_client):
    # for a few hours Other was stored as 「其他：…」; those rows read as
    # the words alone now, on the card and back in the edit form
    store.insert("profiles", {
        "user_id": new_scout.id, "position": "其他：營火主持人",
        "interests": "露營、其他：觀鳥", "experience": "參加了童軍兩年。",
        "share": "喜歡幫忙。", "strength": "其他：守夜",
        "visible": True, "updated_at": "2026-01-01",
    })
    page = scout_client.get(f"/profile/{new_scout.id}").get_data(as_text=True)
    card = page[page.index("data-char-card"):]
    assert "營火主持人" in card and "觀鳥" in card and "守夜" in card
    assert "其他：" not in card
    own = new_scout.get("/profile").get_data(as_text=True)
    assert 'value="營火主持人"' in own and 'value="守夜"' in own


def test_share_is_optional_and_only_shows_when_ticked(store, new_scout, scout_client):
    # no share at all: the profile still completes
    reply = new_scout.post("/profile", data={
        "position": "隊員", "interests": "露營", "camping_days": "1", "hiking_times": "2",
        "strength": "繩結",
    })
    assert reply.status_code == 200
    assert "請先完成個人檔案" not in new_scout.get("/home").get_data(as_text=True)

    # written but not ticked to show: it is kept, and nobody sees it
    new_scout.post("/profile", data={
        "position": "隊員", "interests": "露營", "camping_days": "1", "hiking_times": "2",
        "strength": "繩結", "share": "只想自己留着的分享",
        "share_visible_present": "1",
    })
    row = store.get("profiles", new_scout.id)
    assert row["share"] == "只想自己留着的分享" and row["share_visible"] in (False, "false", 0)
    # the tick sits beside the 想和大家分享的事 heading, above the text box
    own_page = new_scout.get("/profile").get_data(as_text=True)
    head = own_page[own_page.index("share-head"):own_page.index('name="share"', own_page.index("share-head"))]
    assert "想和大家分享的事" in head and 'name="share_visible"' in head
    visited = scout_client.get(f"/profile/{new_scout.id}").get_data(as_text=True)
    assert "只想自己留着的分享" not in visited
    own = new_scout.get("/profile").get_data(as_text=True)
    card = own[own.index("data-char-card"):own.index("編輯個人檔案")]
    assert "只想自己留着的分享" not in card  # not on the card, only in the form

    # ticked: it shows on the card for everyone
    new_scout.post("/profile", data={
        "position": "隊員", "interests": "露營", "camping_days": "1", "hiking_times": "2",
        "strength": "繩結", "share": "想和大家分享露營相",
        "share_visible_present": "1", "share_visible": "1",
    })
    visited = scout_client.get(f"/profile/{new_scout.id}").get_data(as_text=True)
    assert "想和大家分享露營相" in visited


def test_a_profile_completes_without_a_position_until_game_5(store, new_scout):
    # position waits for the game: everything else filled is a complete
    # profile, and the pop-up lets the scout through
    page = new_scout.get("/profile").get_data(as_text=True)
    assert "暫時留空" in page and "未完成遊戲 5 前可留空" in page
    reply = new_scout.post("/profile", data={
        "position_choice": "", "interest_picks": ["露營"],
        "camping_days": "1", "hiking_times": "2", "strength_choice": "繩結",
    })
    assert reply.status_code == 200
    assert store.get("profiles", new_scout.id)["position"] == ""
    assert "data-profile-setup" not in new_scout.get("/home").get_data(as_text=True)


def test_leader_ranks_are_appointed_never_picked(store, new_scout):
    # a scout cannot give themselves a rank — not from the list form…
    reply = new_scout.post("/profile", data={
        "position_choice": "__other__", "position_other": "隊長",
        "position_desc": "帶領小隊", "interest_picks": ["露營"],
        "camping_days": "1", "hiking_times": "2", "strength_choice": "繩結",
    })
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "profile_position_rank"
    assert store.get("profiles", new_scout.id) is None
    # …and not through the old plain fields either
    reply = new_scout.post("/profile", data={
        "position": "副隊長", "interests": "露營",
        "experience": "參加了童軍兩年。", "strength": "繩結",
    })
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "profile_position_rank"
    assert store.get("profiles", new_scout.id) is None

    # appointed by a leader, the rank rides along on the scout's own
    # edits — but swapping it or handing it back is refused. The stored
    # row still uses the old spelling 小隊長； keeping it under the
    # proper title 隊長 is the same appointment, stored back properly.
    store.insert("profiles", {
        "user_id": new_scout.id, "position": "小隊長", "interests": "露營",
        "camping_days": "1", "hiking_times": "2", "strength": "繩結",
        "visible": True, "updated_at": "2026-01-01",
    })
    keep = {
        "position_choice": "__other__", "position_other": "隊長",
        "interest_picks": ["露營", "行山"], "camping_days": "3",
        "hiking_times": "2", "strength_choice": "繩結",
    }
    assert new_scout.post("/profile", data=keep).status_code == 200
    assert store.get("profiles", new_scout.id)["position"] == "隊長"
    for swap in ({"position_other": "副隊長"}, {"position_choice": "康樂"}):
        reply = new_scout.post("/profile", data={**keep, **swap})
        assert reply.status_code == 400
        assert reply.get_json()["error"] == "profile_position_rank"
    assert store.get("profiles", new_scout.id)["position"] == "隊長"


def test_an_other_position_joins_the_selection_list(store, new_scout, scout_client):
    data = {
        "position_choice": "__other__", "position_other": "營火主持人",
        "interest_picks": ["露營"], "camping_days": "1", "hiking_times": "2",
        "strength_choice": "繩結",
    }
    # a brand-new role must say what it has to do before it can join
    reply = new_scout.post("/profile", data=data)
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "profile_position_desc"
    assert store.get("profiles", new_scout.id) is None

    reply = new_scout.post("/profile", data={**data, "position_desc": "帶大家唱營火歌"})
    assert reply.status_code == 200
    assert store.get("profiles", new_scout.id)["position"] == "營火主持人"
    assert "營火主持人" in (store.settings_cached().get("custom_positions") or [])

    # from now on it is picked straight from the list — by its owner…
    page = new_scout.get("/profile").get_data(as_text=True)
    assert 'value="營火主持人" data-desc-zh="帶大家唱營火歌" data-desc-en="帶大家唱營火歌" selected' in page
    # …and by every other scout, with the inventor's description attached
    other_page = scout_client.get("/profile").get_data(as_text=True)
    assert 'value="營火主持人"' in other_page
    assert 'data-desc-zh="帶大家唱營火歌"' in other_page
    # the written duties ride on the listed positions too
    assert 'data-desc-zh="記錄出席，聯絡和通知大家。"' in other_page


def test_a_position_written_before_the_lists_is_offered_back_as_other(store, new_scout):
    # a page left open from before the lists still saves its plain fields
    reply = new_scout.post("/profile", data={
        "position": "營火主持人",
        "interests": "唱歌", "experience": "參加了童軍兩年。", "share": "喜歡帶大家唱營火歌。", "strength": "唱歌",
    })
    assert reply.status_code == 200
    assert store.get("profiles", new_scout.id)["position"] == "營火主持人"
    page = new_scout.get("/profile").get_data(as_text=True)
    assert "營火主持人" in page
    # …and the list form offers those words back under Other, not lost
    assert 'value="營火主持人"' in page


def test_a_position_saved_as_an_old_code_still_reads_as_a_title(store, new_scout, scout_client):
    # profiles saved while the position was picked from a list hold a code
    store.insert("profiles", {
        "user_id": new_scout.id, "position": "pl", "interests": "足球",
        "experience": "參加了童軍一年。", "share": "喜歡在營地幫忙。", "strength": "生火",
        "visible": True, "updated_at": "2026-01-01",
    })
    page = scout_client.get(f"/profile/{new_scout.id}").get_data(as_text=True)
    assert "隊長" in page
    # the owner's edit form offers the title back as ordinary text
    assert 'value="隊長"' in new_scout.get("/profile").get_data(as_text=True)


def test_an_unfinished_profile_cannot_be_visited(store, new_scout, scout_client):
    # a row left over from before profiles had to be completed and public
    store.insert("profiles", {
        "user_id": new_scout.id, "interests": "觀星", "experience": "",
        "share": "", "visible": False, "updated_at": "2026-01-01",
    })
    locked = scout_client.get(f"/profile/{new_scout.id}").get_data(as_text=True)
    assert "尚未完成並公開個人檔案" in locked
    assert "觀星" not in locked

    new_scout.post("/profile", data={
        "position": "隊員", "interests": "天文", "experience": "參加了童軍三年。", "share": "想分享星星的故事。", "strength": "觀星",
    })
    open_page = scout_client.get(f"/profile/{new_scout.id}").get_data(as_text=True)
    assert "天文" in open_page and "參加了童軍三年" in open_page
    assert "想分享星星的故事" in open_page and "狀態總覽" in open_page


def test_the_patrol_list_groups_scouts_and_marks_who_is_open(store, new_scout, scout_client):
    other = find(store, "scout04")
    store.insert("profiles", {
        "user_id": other["id"], "position": "pl", "interests": "足球", "experience": "參加了童軍一年。",
        "share": "喜歡在營地幫忙煮食。", "strength": "煮食", "visible": True, "updated_at": "2026-01-01",
    })
    page = new_scout.get("/profile").get_data(as_text=True)
    assert "各小隊成員" in page
    members = page[page.index("各小隊成員"):]
    assert "老虎" in members and "水獺" in members and "海鷗" in members
    assert f'href="/profile/{other["id"]}' in page
    assert "尚未完成" in page  # somebody on the list has not finished yet


def test_the_pop_up_blocks_a_scout_until_the_profile_is_complete(store, new_scout, leader_client):
    for path in ("/home", "/daily", "/cards", "/feedback"):
        page = new_scout.get(path).get_data(as_text=True)
        assert "data-profile-setup" in page, path
        assert "請先完成個人檔案" in page, path
        assert "儲存並公開個人檔案" in page, path
    # leaders never see the scout pop-up
    assert "data-profile-setup" not in leader_client.get("/leader").get_data(as_text=True)

    # the other fields are still required — a half-filled profile is refused
    # (position alone may wait: it is decided inside game 5)
    reply = new_scout.post("/profile", data={"interests": "露營", "experience": "參加了童軍兩年。", "share": "喜歡幫忙。"})
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "profile_empty"
    reply = new_scout.post("/profile", data={"position": "隊員", "interests": "露營", "experience": "", "share": ""})
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "profile_empty"
    assert store.get("profiles", new_scout.id) is None

    new_scout.post("/profile", data={
        "position": "聯絡", "interests": "露營", "experience": "參加了童軍兩年。", "share": "喜歡幫忙。", "strength": "繩結",
    })
    assert "data-profile-setup" not in new_scout.get("/home").get_data(as_text=True)


def test_saving_from_the_pop_up_returns_to_the_page_in_use(store, new_scout):
    response = new_scout.client.post("/profile", data={
        "position": "隊員", "interests": "音樂", "experience": "參加了童軍一年。", "share": "想和大家組樂隊。", "strength": "唱歌",
        "return_to": "/daily",
    })
    assert response.status_code == 302
    assert "/daily" in response.headers["Location"]
    assert store.get("profiles", new_scout.id)["visible"] in (True, "true", 1)


def test_the_pop_up_is_english_on_english_pages(store, new_scout):
    new_scout.get("/set-language/en")
    page = new_scout.get("/home").get_data(as_text=True)
    assert "Complete your profile first" in page
    assert "Save and publish my profile" in page
    assert "請先完成個人檔案" not in page


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
    assert "My profile" in page and "Status overview" in page
    assert "Scouts by patrol" in page
    assert "我的個人檔案" not in page and "狀態總覽" not in page


def _complete(new_scout):
    new_scout.post("/profile", data={
        "position": "聯絡", "interests": "露營、繩結",
        "experience": "我參加了童軍兩年。", "share": "我喜歡教新成員綁繩結。", "strength": "繩結",
    })


def test_my_profile_offers_a_real_photo_upload_not_a_card_generator(store, new_scout):
    _complete(new_scout)
    page = new_scout.get("/profile").get_data(as_text=True)
    assert "生成我的卡圖" not in page and "/card-maker" not in page
    assert "data-card-photo" in page and "上載相片" in page
    # the rule is spelled out where the scout uploads: a real-life photo of
    # themselves, face clearly visible, leader-approved before it shows
    assert "真人相片" in page and "清楚見到你的樣子" in page
    assert "領袖批准" in page


def test_an_uploaded_photo_waits_for_a_leader_then_lands_on_my_card(store, new_scout, leader_client, app):
    import io
    reply = new_scout.post("/profile/card-photo",
                           data={"card_photo": (io.BytesIO(b"\x89PNG fake"), "card.png")})
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "profile_incomplete"

    _complete(new_scout)
    reply = new_scout.post("/profile/card-photo",
                           data={"card_photo": (io.BytesIO(b"notes"), "notes.txt")})
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "card_file"

    reply = new_scout.post("/profile/card-photo",
                           data={"card_photo": (io.BytesIO(b"\x89PNG fake"), "card.png")})
    assert reply.status_code == 200
    assert reply.get_json()["card_photo_status"] == "pending"
    row = store.get("profiles", new_scout.id)
    assert row["card_photo_status"] == "pending"
    assert row["card_photo_url"].startswith("/uploads/")

    # waiting: the card itself still wears the mascot, and another scout
    # visiting sees no photo at all — only the owner sees the waiting preview
    page = new_scout.get("/profile").get_data(as_text=True)
    assert "char-photo" not in page and "等領袖批准中" in page
    visitor = _login(app, next(u for u in store.list("users") if u["username"] == "scout05"))
    seen = visitor.get(f"/profile/{new_scout.id}").get_data(as_text=True)
    assert row["card_photo_url"] not in seen and "char-photo" not in seen

    # the leader finds it in the review queue and approves it there
    queue = leader_client.get("/leader/review").get_data(as_text=True)
    assert row["card_photo_url"] in queue and "個人卡相片待批准" in queue
    reply = leader_client.post(f"/leader/card-photos/{new_scout.id}", data={"action": "approve"})
    assert reply.status_code in (200, 302)
    assert store.get("profiles", new_scout.id)["card_photo_status"] == "approved"

    page = new_scout.get("/profile").get_data(as_text=True)
    assert "char-photo" in page and row["card_photo_url"] in page
    seen = visitor.get(f"/profile/{new_scout.id}").get_data(as_text=True)
    assert "char-photo" in seen and row["card_photo_url"] in seen

    # a replacement goes back to waiting, off the card, until approved again;
    # and a leader can send a photo back instead
    reply = new_scout.post("/profile/card-photo",
                           data={"card_photo": (io.BytesIO(b"\x89PNG fake2"), "card.png")})
    assert reply.status_code == 200
    page = new_scout.get("/profile").get_data(as_text=True)
    assert "char-photo" not in page
    reply = leader_client.post(f"/leader/card-photos/{new_scout.id}", data={"action": "reject"})
    assert reply.status_code in (200, 302)
    row = store.get("profiles", new_scout.id)
    assert row["card_photo_status"] == "rejected" and not row["card_photo_url"]
    page = new_scout.get("/profile").get_data(as_text=True)
    assert "未獲批准" in page

    # a scout may not approve their own photo
    reply = new_scout.post("/profile/card-photo",
                           data={"card_photo": (io.BytesIO(b"\x89PNG fake3"), "card.png")})
    assert reply.status_code == 200
    reply = new_scout.post(f"/leader/card-photos/{new_scout.id}", data={"action": "approve"})
    assert reply.status_code in (302, 403)
    assert store.get("profiles", new_scout.id)["card_photo_status"] == "pending"


def test_an_old_generated_card_picture_no_longer_covers_the_card(store, new_scout):
    """Generated card pictures are retired: even one already on file stays
    off the card — the designed card (or an approved photo) is what shows."""
    _complete(new_scout)
    store.update("profiles", new_scout.id, {"card_image_url": "/uploads/old-generated.webp"})
    page = new_scout.get("/profile").get_data(as_text=True)
    assert "char-generated-img" not in page and "/uploads/old-generated.webp" not in page


def test_an_uploaded_photo_is_stored_as_avif_or_webp(store, new_scout):
    import io
    import pathlib

    from PIL import Image
    _complete(new_scout)
    buffer = io.BytesIO()
    Image.new("RGB", (240, 360), (30, 90, 60)).save(buffer, format="PNG")
    reply = new_scout.post("/profile/card-photo",
                           data={"card_photo": (io.BytesIO(buffer.getvalue()), "card.png")})
    assert reply.status_code == 200
    row = store.get("profiles", new_scout.id)
    assert row["card_photo_url"].endswith((".avif", ".webp"))
    # the stored file really is that format, not just renamed
    name = row["card_photo_url"].rsplit("/", 1)[-1]
    raw = (pathlib.Path(store.driver.uploads_dir) / name).read_bytes()
    assert len(raw) < len(buffer.getvalue())
    with Image.open(io.BytesIO(raw)) as stored:
        assert stored.format in ("AVIF", "WEBP") and stored.size == (240, 360)


def test_the_card_generator_is_gone(store, new_scout):
    """No self-generated cards any more: the maker page, the key-lending
    proxy, the old upload door and the generator file itself are all gone."""
    _complete(new_scout)
    assert new_scout.get("/card-maker").status_code == 404
    assert new_scout.post("/profile/card-image-proxy", json={"contents": []}).status_code in (404, 405)
    assert new_scout.post("/profile/card-upload", data={}).status_code in (404, 405)
    assert new_scout.client.get("/static/card-generator.html").status_code == 404


def test_the_profiles_tab_exists_in_the_schema():
    from scout.schema import COLLECTIONS, key_field
    assert COLLECTIONS["profiles"]["fields"] == [
        "user_id", "position", "interests", "experience", "camping_days", "hiking_times",
        "share", "share_visible", "strength", "visible", "updated_at",
        "card_image_url", "card_image_id", "card_generated_at",
        "card_photo_url", "card_photo_id", "card_photo_status", "card_photo_uploaded_at"]
    assert key_field("profiles") == "user_id"


def test_the_test_account_is_not_in_the_patrol_groups(store, new_scout):
    """The leaders' test account (username `test`) never shows up as a Tiger
    member on the profile page — the same rule the patrol game already follows."""
    from scout.routes.profile_routes import patrol_groups
    from scout.util import hash_password

    hashed, salt = hash_password("scout1234")
    tester = store.insert("users", {
        "role": "scout", "username": "test", "password_hash": hashed,
        "password_salt": salt, "display_name_zh": "測試帳戶",
        "display_name_en": "Test Account", "section": "scout", "patrol": "Tiger",
        "status": "active",
    })
    groups = patrol_groups(store, new_scout.id)
    member_ids = {m["user"]["id"] for g in groups for m in g["members"]}
    assert tester["id"] not in member_ids
    assert new_scout.id in member_ids  # real Tiger members still listed
    page = new_scout.get("/profile").get_data(as_text=True)
    assert "測試帳戶" not in page


def _make_test_account(store):
    from scout.util import hash_password
    hashed, salt = hash_password("scout1234")
    return store.insert("users", {
        "role": "scout", "username": "test", "password_hash": hashed,
        "password_salt": salt, "display_name_zh": "測試帳戶",
        "display_name_en": "Test Account", "section": "scout", "patrol": "Tiger",
        "status": "active",
    })


def _login(app, user):
    client = app.test_client()
    reply = client.post(f"/login/scout/{user['patrol']}/{user['id']}",
                        data={"password": "scout1234"})
    assert reply.status_code in (200, 302)
    return client


def test_only_the_test_account_sees_and_can_use_the_reset(store, app, new_scout):
    """🧪 The reset button lives on the test account's profile page only;
    any other scout asking for the reset is refused."""
    tester = _make_test_account(store)

    page = new_scout.get("/profile").get_data(as_text=True)
    assert "data-test-reset" not in page
    assert "data-reset-open" not in page
    assert "/profile/test-reset" not in page
    assert "drill-manual-" not in page
    refused = new_scout.post("/profile/test-reset",
                             headers={"X-Requested-With": "fetch"})
    assert refused.status_code == 403

    client = _login(app, tester)
    page = client.get("/profile").get_data(as_text=True)
    assert "data-test-reset" in page and "重設遊戲進度" in page
    # The confirmation starts hidden, and the page carries the script that
    # reveals it when the first button is pressed (a missing listener was
    # previously reported as "nothing happens after I press the button").
    assert 'data-reset-endpoint="/profile/test-reset' in page
    assert 'id="test-reset-confirm"' in page
    assert "data-reset-confirm hidden" in page
    assert "data-reset-yes" in page and "確定重設" in page
    assert "confirmBox.hidden = false" in page
    assert "scrollIntoView" in page
    assert "fetch(endpoint" in page
    # Game 3 keeps its half-read manual in the browser, beyond the server
    # reset's reach: a successful reset wipes those keys too, so the replay
    # starts at stage 1 (it used to resume mid-manual after a reset).
    assert "drill-manual-" in page and "removeItem(key)" in page


def test_the_reset_reverts_games_points_badge_and_packs(store, app):
    """After a test-account reset, the five games, their points, the badge
    award and the game-granted packs are gone — and stats agree again."""
    from scout.gacha import grant_pack, load_state
    from scout.routes.profile_routes import _membership_game_tasks

    tester = _make_test_account(store)
    badge, task_ids = _membership_game_tasks(store)
    assert badge and len(task_ids) >= 5
    task_id = sorted(task_ids)[0]
    store.insert("progress_records", {
        "user_id": tester["id"], "badge_id": badge["id"], "task_id": task_id,
        "attempt_no": 1, "status": "completed", "score": 30,
        "points_awarded": 30,
    })
    store.insert("points_ledger", {
        "user_id": tester["id"], "entry_type": "task", "points_delta": 30,
        "reason_zh": "完成任務", "reason_en": "done", "ref_type": "task",
        "ref_id": task_id, "created_by": "auto",
    })
    store.insert("badge_awards", {"user_id": tester["id"], "badge_id": badge["id"],
                                  "awarded_by": "auto"})
    store.insert("points_ledger", {
        "user_id": tester["id"], "entry_type": "badge", "points_delta": 50,
        "reason_zh": "考獲", "reason_en": "earned", "ref_type": "badge",
        "ref_id": badge["id"], "created_by": "auto",
    })
    grant_pack(store, tester, key=f"task:{task_id}", kind="standard",
               source="task", ref_id=task_id, reason_zh="完成", reason_en="done")
    store.stats_for(tester["id"])
    store.rebuild_stats(tester["id"])
    assert store.stats_for(tester["id"])["points_balance"] == 80

    client = _login(app, tester)
    reply = client.post("/profile/test-reset", headers={"X-Requested-With": "fetch"})
    assert reply.status_code == 200 and reply.get_json()["ok"]

    uid = tester["id"]
    assert not [r for r in store.list("progress_records") if r["user_id"] == uid]
    assert not [r for r in store.list("badge_awards") if r["user_id"] == uid]
    assert not [r for r in store.list("points_ledger") if r["user_id"] == uid]
    assert load_state(store, uid)["packs_json"] == []
    assert load_state(store, uid)["grants_json"] == []
    stats = store.stats_for(uid)
    assert stats["points_balance"] == 0 and stats["tasks_done"] == 0
    # and the account can earn the same pack all over again
    assert grant_pack(store, tester, key=f"task:{task_id}", kind="standard",
                      source="task", ref_id=task_id,
                      reason_zh="完成", reason_en="done") is True
