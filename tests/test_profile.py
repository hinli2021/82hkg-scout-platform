"""我的個人檔案 — progress overview, personal words, patrol member visits."""
from __future__ import annotations


def find(store, username):
    return next(u for u in store.list("users") if u["username"] == username)


def test_my_profile_shows_a_progress_overview(store, new_scout):
    page = new_scout.get("/profile").get_data(as_text=True)
    assert "我的個人檔案" in page and "狀態總覽" in page
    assert "獎章" in page and "任務" in page and "積分" in page
    assert "興趣" in page and "童軍經驗" in page and "想和大家分享的事" in page
    assert "個人檔案會公開給其他童軍看" in page
    assert "請先完成個人檔案" in page  # the blocking pop-up is already up
    # the profile is a character card now: portrait front, status back
    assert "data-char-card" in page and "data-char-front" in page and "data-char-back" in page
    assert "看背面" in page and "職位" in page


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
        "share": "我喜歡畫畫，也喜歡教新成員綁繩結。",
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
    assert "poke-moves" in front and "童軍經驗" in front and "poke-rarity" in front


def test_a_scout_can_write_any_position_in_their_own_words(store, new_scout):
    # the position is a text field, not a list to pick from
    page = new_scout.get("/profile").get_data(as_text=True)
    assert 'name="position"' in page and '<select name="position"' not in page
    assert "例如：小隊長、副小隊長、隊員" in page

    reply = new_scout.post("/profile", data={
        "position": "營火主持人",
        "interests": "唱歌", "experience": "參加了童軍兩年。", "share": "喜歡帶大家唱營火歌。",
    })
    assert reply.status_code == 200
    assert store.get("profiles", new_scout.id)["position"] == "營火主持人"
    assert "營火主持人" in new_scout.get("/profile").get_data(as_text=True)

    # a position that is far too long is refused, like the other fields
    reply = new_scout.post("/profile", data={
        "position": "職" * 41,
        "interests": "唱歌", "experience": "參加了童軍兩年。", "share": "喜歡帶大家唱營火歌。",
    })
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "profile_long"
    assert store.get("profiles", new_scout.id)["position"] == "營火主持人"


def test_a_position_saved_as_an_old_code_still_reads_as_a_title(store, new_scout, scout_client):
    # profiles saved while the position was picked from a list hold a code
    store.insert("profiles", {
        "user_id": new_scout.id, "position": "pl", "interests": "足球",
        "experience": "參加了童軍一年。", "share": "喜歡在營地幫忙。",
        "visible": True, "updated_at": "2026-01-01",
    })
    page = scout_client.get(f"/profile/{new_scout.id}").get_data(as_text=True)
    assert "小隊長" in page
    # the owner's edit form offers the title back as ordinary text
    assert 'value="小隊長"' in new_scout.get("/profile").get_data(as_text=True)


def test_an_unfinished_profile_cannot_be_visited(store, new_scout, scout_client):
    # a row left over from before profiles had to be completed and public
    store.insert("profiles", {
        "user_id": new_scout.id, "interests": "天文", "experience": "",
        "share": "", "visible": False, "updated_at": "2026-01-01",
    })
    locked = scout_client.get(f"/profile/{new_scout.id}").get_data(as_text=True)
    assert "尚未完成並公開個人檔案" in locked
    assert "天文" not in locked

    new_scout.post("/profile", data={
        "position": "隊員", "interests": "天文", "experience": "參加了童軍三年。", "share": "想分享星星的故事。",
    })
    open_page = scout_client.get(f"/profile/{new_scout.id}").get_data(as_text=True)
    assert "天文" in open_page and "參加了童軍三年" in open_page
    assert "想分享星星的故事" in open_page and "狀態總覽" in open_page


def test_the_patrol_list_groups_scouts_and_marks_who_is_open(store, new_scout, scout_client):
    other = find(store, "scout04")
    store.insert("profiles", {
        "user_id": other["id"], "position": "pl", "interests": "足球", "experience": "參加了童軍一年。",
        "share": "喜歡在營地幫忙煮食。", "visible": True, "updated_at": "2026-01-01",
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

    # every field is required — no position, or a half-filled profile, is refused
    reply = new_scout.post("/profile", data={"interests": "露營", "experience": "參加了童軍兩年。", "share": "喜歡幫忙。"})
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "profile_position"
    reply = new_scout.post("/profile", data={"position": "隊員", "interests": "露營", "experience": "", "share": ""})
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "profile_empty"
    assert store.get("profiles", new_scout.id) is None

    new_scout.post("/profile", data={
        "position": "副小隊長", "interests": "露營", "experience": "參加了童軍兩年。", "share": "喜歡幫忙。",
    })
    assert "data-profile-setup" not in new_scout.get("/home").get_data(as_text=True)


def test_saving_from_the_pop_up_returns_to_the_page_in_use(store, new_scout):
    response = new_scout.client.post("/profile", data={
        "position": "隊員", "interests": "音樂", "experience": "參加了童軍一年。", "share": "想和大家組樂隊。",
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
        "experience": "我參加了童軍兩年。", "share": "我喜歡教新成員綁繩結。",
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


def test_a_generated_card_picture_is_stored_as_avif_or_webp(store, new_scout, app, monkeypatch):
    import io

    from PIL import Image

    from scout.routes import profile_routes
    app.config["GEMINI_API_KEY"] = "test-key"
    buffer = io.BytesIO()
    Image.new("RGB", (240, 360), (90, 30, 60)).save(buffer, format="PNG")
    monkeypatch.setattr(profile_routes, "_call_gemini",
                        lambda api_key, model, prompt: (buffer.getvalue(), "image/png"))
    _complete(new_scout)
    reply = new_scout.post("/profile/card-image", json={"prompt": "畫一張 Pokémon 卡"})
    assert reply.status_code == 200
    row = store.get("profiles", new_scout.id)
    assert row["card_image_url"].endswith((".avif", ".webp"))


def test_a_card_picture_needs_a_complete_profile_first(store, new_scout):
    reply = new_scout.post("/profile/card-image", json={"prompt": "畫一張卡"})
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "profile_incomplete"


def test_a_card_picture_needs_the_leaders_key(store, new_scout, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    _complete(new_scout)
    reply = new_scout.post("/profile/card-image", json={"prompt": "畫一張卡"})
    assert reply.status_code == 503
    assert reply.get_json()["error"] == "card_no_key"
    reply = new_scout.post("/profile/card-image", json={"prompt": " "})
    assert reply.status_code == 400
    assert reply.get_json()["error"] == "card_prompt"


def test_a_card_picture_is_made_and_kept_on_the_card(store, new_scout, app, monkeypatch):
    from scout.routes import profile_routes
    app.config["GEMINI_API_KEY"] = "test-key"
    seen = {}
    def fake_gemini(api_key, model, prompt):
        seen.update(api_key=api_key, model=model, prompt=prompt)
        return b"\x89PNG fake picture", "image/png"
    monkeypatch.setattr(profile_routes, "_call_gemini", fake_gemini)
    _complete(new_scout)

    reply = new_scout.post("/profile/card-image", json={"prompt": "畫一張 Pokémon 卡"})
    assert reply.status_code == 200
    assert seen == {"api_key": "test-key", "model": "gemini-2.5-flash-image",
                    "prompt": "畫一張 Pokémon 卡"}
    row = store.get("profiles", new_scout.id)
    assert row["card_image_url"].startswith("/uploads/") and row["card_generated_at"]
    page = new_scout.get("/profile").get_data(as_text=True)
    assert "char-generated-img" in page and row["card_image_url"] in page

    # one at a time: an instant second try is asked to wait
    reply = new_scout.post("/profile/card-image", json={"prompt": "再畫一張"})
    assert reply.status_code == 429
    assert reply.get_json()["error"] == "card_wait"


def test_a_failed_card_picture_keeps_the_old_state(store, new_scout, app, monkeypatch):
    from scout.routes import profile_routes
    app.config["GEMINI_API_KEY"] = "test-key"
    def broken(api_key, model, prompt):
        raise RuntimeError("upstream is busy")
    monkeypatch.setattr(profile_routes, "_call_gemini", broken)
    _complete(new_scout)
    reply = new_scout.post("/profile/card-image", json={"prompt": "畫一張卡"})
    assert reply.status_code == 502
    assert reply.get_json()["error"] == "card_failed"
    assert not store.get("profiles", new_scout.id).get("card_image_url")


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


# ── card pictures live in Cloudflare R2 when the leader sets it up ──────

_R2_CONFIG = {
    "CLOUDFLARE_ACCOUNT_ID": "acc-123",
    "R2_ACCESS_KEY_ID": "test-access",
    "R2_SECRET_ACCESS_KEY": "test-secret",
    "R2_BUCKET": "scout-cards",
    "R2_PUBLIC_BASE_URL": "https://pub.example.test",
}


def _png_bytes():
    import io

    from PIL import Image
    buffer = io.BytesIO()
    Image.new("RGB", (240, 360), (30, 90, 60)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_a_card_picture_goes_to_r2_when_it_is_set_up(store, new_scout, app, monkeypatch):
    import io

    import requests as requests_module
    app.config.update(_R2_CONFIG)
    seen = {}

    class _Ok:
        status_code = 200

    def fake_put(url, data=None, headers=None, timeout=None):
        seen.update(url=url, data=data, headers=headers)
        return _Ok()

    monkeypatch.setattr(requests_module, "put", fake_put)
    _complete(new_scout)
    reply = new_scout.post("/profile/card-upload",
                           data={"card_image": (io.BytesIO(_png_bytes()), "card.png")})
    assert reply.status_code == 200
    row = store.get("profiles", new_scout.id)
    assert row["card_image_url"].startswith("https://pub.example.test/cards/card-")
    assert row["card_image_url"].endswith(".avif")
    assert "acc-123.r2.cloudflarestorage.com/scout-cards/cards/card-" in seen["url"]
    assert seen["headers"]["Content-Type"] == "image/avif"
    auth = seen["headers"]["Authorization"]
    assert auth.startswith("AWS4-HMAC-SHA256 Credential=test-access/")
    assert "SignedHeaders=host;x-amz-content-sha256;x-amz-date" in auth
    assert seen["headers"]["x-amz-content-sha256"]


def test_a_card_picture_falls_back_to_the_drive_when_r2_fails(store, new_scout, app, monkeypatch):
    import io

    import requests as requests_module
    app.config.update(_R2_CONFIG)

    def broken_put(url, data=None, headers=None, timeout=None):
        raise RuntimeError("R2 is down")

    monkeypatch.setattr(requests_module, "put", broken_put)
    _complete(new_scout)
    reply = new_scout.post("/profile/card-upload",
                           data={"card_image": (io.BytesIO(_png_bytes()), "card.png")})
    assert reply.status_code == 200
    row = store.get("profiles", new_scout.id)
    assert row["card_image_url"].startswith("/uploads/")


def test_the_profiles_tab_exists_in_the_schema():
    from scout.schema import COLLECTIONS, key_field
    assert COLLECTIONS["profiles"]["fields"] == [
        "user_id", "position", "interests", "experience", "share", "visible", "updated_at",
        "card_image_url", "card_image_id", "card_generated_at"]
    assert key_field("profiles") == "user_id"
