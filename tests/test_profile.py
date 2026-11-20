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
        "position": "小隊長",
        "interests": "露營、繩結、音樂",
        "experience": "我參加了童軍兩年，去過一次大露營。",
        "share": "我喜歡畫畫，也喜歡教新成員綁繩結。", "strength": "畫畫",
    })
    assert reply.status_code == 200
    row = store.get("profiles", new_scout.id)
    assert row["position"] == "小隊長" and row["interests"] == "露營、繩結、音樂"
    assert row["visible"] in (True, "true", 1)

    page = new_scout.get("/profile").get_data(as_text=True)
    assert "露營、繩結、音樂" in page and "小隊長" in page  # the card shows the position
    assert "請先完成個人檔案" not in page  # complete: the pop-up is gone
    # the front follows a monster trading card: name and HP, picture window,
    # info strip (number, patrol, position), then the moves
    front = page[page.index("data-char-front"):page.index("data-char-back")]
    assert "poke-head" in front and "HP" in front and "poke-info" in front
    assert "poke-moves" in front and "童軍經驗" in front
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
    # the four patrol ranks are not picked here any more
    for word in ("隊員", "副小隊長", "小隊長", "高級小隊長"):
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
    # the edit form offers every pick back, Other words in their boxes
    assert 'value="聯絡" data-desc-zh="負責出席記錄，聯絡和通知大家。" data-desc-en="Keeps the attendance record, and contacts and reminds everyone." selected' in page
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
    assert 'data-desc-zh="負責出席記錄，聯絡和通知大家。"' in other_page


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
    assert "小隊長" in page
    # the owner's edit form offers the title back as ordinary text
    assert 'value="小隊長"' in new_scout.get("/profile").get_data(as_text=True)


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
        "position": "副小隊長", "interests": "露營", "experience": "參加了童軍兩年。", "share": "喜歡幫忙。", "strength": "繩結",
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
        "position": "小隊長", "interests": "露營、繩結",
        "experience": "我參加了童軍兩年。", "share": "我喜歡教新成員綁繩結。", "strength": "繩結",
    })


def test_my_profile_links_to_the_card_maker(store, new_scout):
    _complete(new_scout)
    page = new_scout.get("/profile").get_data(as_text=True)
    assert 'href="/card-maker' in page and "生成我的卡圖" in page

    maker = new_scout.get("/card-maker")
    assert maker.status_code == 200
    body = maker.get_data(as_text=True)
    assert "card-generator.html" in body and "上載卡圖" in body
    # the original Google link is one tap away (Google forbids embedding it,
    # so it opens in a new window where its key is provided automatically)
    assert "https://gemini.google.com/share/026550477ded" in body
    assert 'target="_blank"' in body

    # the embedded generator is locked to the Pokémon system
    generator = new_scout.client.get("/static/card-generator.html").get_data(as_text=True)
    assert "scout-pokemon-lock" in generator and 'data-sys="pokemon"' in generator


def test_an_uploaded_card_picture_lands_on_my_card(store, new_scout):
    import io
    reply = new_scout.post("/profile/card-upload",
                            data={"card_image": (io.BytesIO(b"\x89PNG fake"), "card.png")})
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "profile_incomplete"

    _complete(new_scout)
    reply = new_scout.post("/profile/card-upload",
                            data={"card_image": (io.BytesIO(b"notes"), "notes.txt")})
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "card_file"

    reply = new_scout.post("/profile/card-upload",
                            data={"card_image": (io.BytesIO(b"\x89PNG fake"), "card.png")})
    assert reply.status_code == 200
    row = store.get("profiles", new_scout.id)
    assert row["card_image_url"].startswith("/uploads/")
    page = new_scout.get("/profile").get_data(as_text=True)
    assert "char-generated-img" in page and row["card_image_url"] in page


def test_an_uploaded_card_picture_is_stored_as_avif_or_webp(store, new_scout):
    import io
    import pathlib

    from PIL import Image
    _complete(new_scout)
    buffer = io.BytesIO()
    Image.new("RGB", (240, 360), (30, 90, 60)).save(buffer, format="PNG")
    reply = new_scout.post("/profile/card-upload",
                           data={"card_image": (io.BytesIO(buffer.getvalue()), "card.png")})
    assert reply.status_code == 200
    row = store.get("profiles", new_scout.id)
    assert row["card_image_url"].endswith((".avif", ".webp"))
    # the stored file really is that format, not just renamed
    name = row["card_image_url"].rsplit("/", 1)[-1]
    raw = (pathlib.Path(store.driver.uploads_dir) / name).read_bytes()
    assert len(raw) < len(buffer.getvalue())
    with Image.open(io.BytesIO(raw)) as stored:
        assert stored.format in ("AVIF", "WEBP") and stored.size == (240, 360)


# ── the in-page generator borrows the platform key through the proxy ─────

_PROXY_BODY = {"contents": [{"role": "user", "parts": [{"text": "畫一張 Pokémon 卡"}]}],
               "generationConfig": {"imageConfig": {"aspectRatio": "2:3"}}}


class _FakeUpstream:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        import json as _json
        self.content = _json.dumps(payload if payload is not None else {
            "candidates": [{"content": {"parts": [
                {"inlineData": {"mimeType": "image/png", "data": "aGVsbG8="}}]}}],
        }).encode()


def test_the_card_proxy_needs_a_complete_profile_and_a_platform_key(store, new_scout, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    reply = new_scout.post("/profile/card-image-proxy", json=_PROXY_BODY)
    assert reply.status_code == 400
    assert "完成個人檔案" in reply.get_json()["error"]["message"]

    _complete(new_scout)
    reply = new_scout.post("/profile/card-image-proxy", json=_PROXY_BODY)
    assert reply.status_code == 400
    assert "平台尚未設定出圖金鑰" in reply.get_json()["error"]["message"]

    reply = new_scout.post("/profile/card-image-proxy", json={"contents": []})
    assert reply.status_code == 400
    assert "不完整" in reply.get_json()["error"]["message"]


def test_the_card_proxy_forwards_with_the_platform_key(store, new_scout, app, monkeypatch):
    import requests as requests_module
    from scout.routes import profile_routes
    app.config["GEMINI_API_KEY"] = "platform-key"
    seen = {}

    def fake_post(url, params=None, timeout=None, json=None):
        seen.update(url=url, params=params, json=json)
        return _FakeUpstream()

    monkeypatch.setattr(requests_module, "post", fake_post)
    _complete(new_scout)
    reply = new_scout.post("/profile/card-image-proxy", json=_PROXY_BODY)
    assert reply.status_code == 200
    assert reply.get_json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"] == "aGVsbG8="
    # the platform key goes upstream; it is never part of the answer
    assert seen["params"] == {"key": "platform-key"}
    assert "gemini-2.5-flash-image" in seen["url"]
    assert seen["json"]["contents"] == _PROXY_BODY["contents"]
    assert b"platform-key" not in reply.data
    rows = [r for r in store.list("audit_log") if r.get("action") == "profile_card_proxy"]
    assert len(rows) == 1

    # half a minute between generations
    reply = new_scout.post("/profile/card-image-proxy", json=_PROXY_BODY)
    assert reply.status_code == 429
    assert "等半分鐘" in reply.get_json()["error"]["message"]


def test_the_card_proxy_has_a_daily_limit(store, new_scout, app, monkeypatch):
    import requests as requests_module
    app.config["GEMINI_API_KEY"] = "platform-key"
    monkeypatch.setattr(requests_module, "post", lambda *a, **kw: _FakeUpstream())
    _complete(new_scout)
    from scout.util import now_iso
    for _ in range(25):
        store.insert("audit_log", {
            "actor_id": new_scout.id, "actor_role": "scout", "action": "profile_card_proxy",
            "entity": "profiles", "entity_id": new_scout.id, "detail_json": "{}",
            "created_at": now_iso(),
        })
    # jump the last entry back so only the daily cap can refuse this call
    rows = [r for r in store.list("audit_log") if r.get("action") == "profile_card_proxy"]
    store.update("audit_log", rows[-1]["id"], {"created_at": "2020-01-01T00:00:00.000Z"})
    reply = new_scout.post("/profile/card-image-proxy", json=_PROXY_BODY)
    assert reply.status_code == 429
    assert "今日的出圖次數已用完" in reply.get_json()["error"]["message"]


def test_the_embedded_generator_uses_the_proxy_not_a_pasted_key(new_scout):
    generator = new_scout.client.get("/static/card-generator.html").get_data(as_text=True)
    assert "/profile/card-image-proxy" in generator
    assert ".gear { display: none" in generator


def test_the_profiles_tab_exists_in_the_schema():
    from scout.schema import COLLECTIONS, key_field
    assert COLLECTIONS["profiles"]["fields"] == [
        "user_id", "position", "interests", "experience", "camping_days", "hiking_times",
        "share", "share_visible", "strength", "visible", "updated_at",
        "card_image_url", "card_image_id", "card_generated_at"]
    assert key_field("profiles") == "user_id"
