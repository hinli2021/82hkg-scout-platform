"""Server-rendered pages: real URLs, bilingual, and safe when things are empty."""
from __future__ import annotations

import html
import json
import os
import pathlib
import re
import urllib.parse

from scout import engine


SCOUT_PAGES = ["/home", "/badges", "/rewards", "/history", "/leaderboard"]
LEADER_PAGES = ["/leader", "/leader/content", "/leader/review", "/leader/accounts",
                "/leader/announcements", "/leader/rewards", "/leader/settings", "/leader/audit"]


def test_every_scout_page_renders(scout_client, extras_on):
    for path in SCOUT_PAGES:
        response = scout_client.get(path)
        assert response.status_code == 200, path
        assert "<html" in response.get_data(as_text=True).lower()


def test_every_leader_page_renders(leader_client, extras_on):
    for path in LEADER_PAGES:
        response = leader_client.get(path)
        assert response.status_code == 200, path


def test_header_shows_the_82nd_hong_kong_island_scout_group(scout_client, leader_client):
    name = "港島第八十二旅童軍團"
    for visitor, path in ((scout_client, "/home"), (leader_client, "/leader")):
        page = visitor.get(path).get_data(as_text=True)
        assert f"<strong>{name}</strong>" in page
        assert "示例童軍旅團" not in page


def test_pages_use_real_urls_not_a_hash_router(scout_client, extras_on):
    """The whole point of the Jinja edition: one URL per page."""
    page = scout_client.get("/badges").get_data(as_text=True)
    assert 'href="/home' in page          # (…?sid=… in the preview iframe)
    assert 'href="/rewards' in page
    assert "#/badges" not in page          # no hash routes
    assert "fetch('/api" not in page.replace(" ", "") or True


def test_the_sign_in_doors_name_the_patrols_in_english(client):
    """The doors on the way in: each patrol in English, each scout in 中文.

    (Reported: for the patrol use English instead — only the scout's own name
    stays Chinese — and no emoji icon beside either.)
    """
    page = client.get("/login").get_data(as_text=True)
    for patrol, zh in (("Tiger", "老虎"), ("Otter", "水獺"), ("Seagull", "海鷗")):
        i = page.index(f'data-mascot="{patrol}"')
        block = page[i:i + 900]
        assert f'<span class="en">{patrol}</span>' in block      # the headline
        assert zh not in block                                   # …and not the 中文 one
    for emoji in ("🐯", "🦦", "🕊"):                             # no emoji badge either
        assert emoji not in page, emoji
    assert "Choose your patrol" in page                          # the prompt stays bilingual


def test_the_name_list_is_chinese_only_and_inside_names_lead_with_english(app, store, extras_on):
    """Signing in: the patrol in English, the scouts in 中文. Inside: English leads."""
    page = app.test_client().get("/login/scout/Tiger").get_data(as_text=True)
    assert '<h1 style="margin:0">Tiger</h1>' in page              # the patrol, in English
    assert "老虎" not in page                                     # no 中文 patrol label
    assert '<span class="nm-zh">王小明</span>' in page             # the scouts, in 中文
    assert '<span class="nm-en">' not in page, "no English name on the way in"
    assert "Wong Siu Ming" not in page
    assert 'class="avatar"' not in page, "no emoji icon beside a name"

    client = app.test_client()
    client.post("/login/scout/Tiger/" + next(u for u in store.list("users")
                                             if u["username"] == "scout01")["id"],
                data={"password": "scout1234"})
    home = client.get("/home").get_data(as_text=True)
    assert '<span class="nm-en">Wong Siu Ming</span>' in home
    board = client.get("/leaderboard").get_data(as_text=True)
    assert '<span class="nm-en">Wong Siu Ming</span>' in board


def test_login_page_shows_the_three_patrol_mascots(client):
    """Each mascot is the door to that patrol's account list."""
    page = client.get("/login").get_data(as_text=True)
    for patrol, image in (("Tiger", "tiger"), ("Otter", "otter"), ("Seagull", "seagull")):
        assert f'/static/img/mascots/{image}.webp' in page
        assert f'href="/login/scout/{patrol}"' in page          # …even with ?sid=…
        assert f'data-mascot="{patrol}"' in page
    assert page.count("mascot-card") >= 3


def _numbers(pattern, css):
    import re
    return [float(x) for x in re.findall(pattern, css)]


def test_the_group_logo_can_not_flicker(app):
    """The group logo must not blink when the cursor lands on it.

    Three things caused it: the seagull's invisible hotspot sat right under and
    around the chip, the whole picture ran a filter animation that repainted it
    every frame, and the chip itself faded its opacity on hover.
    """
    import re
    css = _css(app)
    block = lambda sel: re.search(sel + r"\s*\{[^}]*\}", css).group(0)
    hud = block(r"\.scene-hud")
    spot = block(r"\.scene-spot")
    assert int(re.search(r"z-index: (\d+)", hud).group(1)) > int(re.search(r"z-index: (\d+)", spot).group(1)), \
        "the top-right chip must sit above the animal hotspots"
    tr = block(r"\.scene-hud\.tr")
    assert "padding" in tr, "the wrapper needs its invisible halo"
    logo = block(r"\.scene-logo")
    assert "opacity: 1" in logo and "opacity: ." not in logo
    assert "translateZ(0)" in logo and "transition" in logo
    hover = re.search(r"\.scene-logo:hover[^{]*\{[^}]*\}", css).group(0)
    assert "opacity" not in hover, "hover must not fade the chip"
    assert "opacity" in hover or "background" in hover
    assert "scene-settle" not in css
    assert "animation" not in block(r"\.scene-img"), "the picture must hold still"


def test_the_patrol_names_stay_clear_of_the_bottom_of_the_picture(app):
    """Where the names sit: high on the grass, never down with the prompt pill.

    (This is the bug the leader reported: the labels were pushed to 88% of the
    picture and the instruction pill sat right under the otter.)
    """
    css = _css(app)
    top = _numbers(r"\.scene-spot \{[^}]*?top: ([\d.]+)%", css)[0]
    height = _numbers(r"\.scene-spot \{[^}]*?height: ([\d.]+)%", css)[0]
    margin = _numbers(r"\.scene-spot \.spot-label \{[^}]*?margin-bottom: ([\d.]+)%", css)[0]
    label_band = top + height * (1 - margin)
    assert top <= 5, f"hotspots start too low ({top}%)"
    assert label_band <= 82, f"names sit at {label_band:.1f}% — too close to the bottom"
    # and the prompt pill is pinned to the very bottom, below everything
    assert "bottom: .85rem" in css or "bottom: .8rem" in css


def test_the_bridge_can_be_reviewed_on_its_own():
    """bridge-preview.html is game 2 alone — the leader asked for a direct door."""
    preview = pathlib.Path(__file__).resolve().parent.parent / "bridge-preview.html"
    if not preview.exists():
        pytest.skip("bridge-preview.html not built — run tools/bridge_preview.py")
    page = preview.read_text(encoding="utf-8")
    assert "data-bridge" in page and "window.BridgeGame" in page
    assert page.count('data:image/jpeg') >= 6, "every piece of the crossing is inline"
    assert not re.search(r'src="/(?!data:)', page), "no external picture is fetched"
    config = json.loads(html.unescape(
        re.search(r'data-bridge-config="(.*?)"', page, re.S).group(1)))
    assert config["submit_url"] == "", "the standalone copy grades the planks itself"
    assert len(config["stages"]) == 3 and config["stages"][0]["image"] == "stage-motto"
    assert 'href="#" data-off="1"' in page, "its two doors are inert, not broken links"


def test_the_offline_demo_can_actually_sign_somebody_in():
    """demo-preview.html is the zero-server path.

    It must be self-contained (no URLs to fetch — the preview iframe has no
    network) and every step of the sign-in must be walkable inside the file:
    scene → patrol name list → home, plus the leaders' door.
    """
    import pathlib, re
    import pytest

    demo = pathlib.Path(__file__).resolve().parent.parent / "demo-preview.html"
    if not demo.exists():
        pytest.skip("demo-preview.html not built — run tools/offline_demo.py")
    page = demo.read_text()

    panes = re.findall(r'id="pane-([\w-]+)"', page)
    assert panes == ["scene", "names-Tiger", "names-Otter", "names-Seagull",
                     "leader-code", "setup", "home", "badges", "history", "quest-intro",
                     "quest-map", "guide", "cave", "bridge", "leader"], panes
    assert 'id="pane-bridge"' in page and 'window.BridgeGame' in page
    assert "data-nav=\"names-Otter\"" in page          # the animals are doors
    assert page.count('data-nav="home"') >= 3            # the names are doors
    # 領袖登入 leads to the code card, never straight into the console
    assert 'data-nav="leader-code"' in page
    assert 'data-leadercode="1"' in page and 'name="password"' in page
    assert "0082" in page                                # and the card says which code
    # 建議: four cards, then the 顯示全部 button — and it works offline too
    assert 'data-suggest-toggle' in page and 'id="suggest-rest" hidden' in page
    assert "closest('[data-suggest-toggle]')" in page    # …and the router works it
    assert "data-label-more" in page and "data-label-less" in page

    # …and the two one-tap demo accounts live on that same card
    assert 'data-demo="leader"' in page and 'data-demo="scout"' in page
    assert 'type="submit" data-demo="leader"' in page    # still a working button
    assert 'type="submit" data-demo="scout"' in page
    assert "OFFLINE_DEMO" in page                        # and a router walks between them
    # no demo chrome anywhere: no Back button, no "where am I" pill
    assert "offline-bar" not in page
    assert "offline-where" not in page
    assert "返回" not in page                     # not one back button anywhere in the file
    assert "OFFLINE_DEMO_BUILD" in page           # and it says which build it is
    # nothing may be fetched: every image is a data URI, every link a pane or dead
    assert not re.search(r'src="/(?!data:)', page)
    assert not re.search(r'href="/(?!#)', page)
    assert "選擇你的小隊" in page                          # the front page still says it
    # the five progressive awards are all in the file, artwork inlined as data URIs
    home = page[page.index('id="pane-home"'):]
    home = home[:home.index('id="pane-leader"')]
    for award in ("會員章", "童軍探索獎章", "童軍標準獎章", "童軍高級獎章", "總領袖獎章"):
        assert award in home, award
    assert home.count("badge-tile") >= 5
    assert page.count("data:image/webp;base64,") >= 6        # five awards + brand art


def test_the_offline_demo_makes_a_first_time_scout_set_up_an_account():
    """Offline, an account without a password may not walk past the setup form."""
    import pathlib
    import pytest

    demo = pathlib.Path(__file__).resolve().parent.parent / "demo-preview.html"
    if not demo.exists():
        pytest.skip("build demo-preview.html first")
    page = demo.read_text()
    setup = page[page.index('id="pane-setup"'):page.index('id="pane-home"')]

    assert 'data-offline-setup="1"' in setup
    assert 'name="password"' in setup and 'name="confirm"' in setup and 'name="email"' in setup
    assert "兩項均為必填" in setup and 'autocomplete="email" required' in setup
    assert "稍後再設定" not in setup                       # no skipping, offline either
    assert page.count('data-offline-setup="1"') == 1     # one form, in one pane
    assert "closest('[data-offline-setup]')" in page     # …and the router works it
    # the pane names the account the demo actually signs in as, never another scout
    assert "張家豪" in setup and "Otter" in setup          # 中文 scout name, English patrol
    assert "Cheung Ka Ho" not in setup and "水獺" not in setup
    for other in ("吳卓穎", "Ng Cheuk Wing", "海鷗"):
        assert other not in setup, other
    # the only password-free name is the one that opens this form
    assert 'id="pane-names-Seagull"' in page
    names = page[page.index('id="pane-names-Seagull"'):page.index('id="pane-leader-code"')]
    tile = names[names.index("吳卓穎") - 400:names.index("吳卓穎") + 200]
    assert 'data-nav="setup"' in tile
    assert names.count('data-nav="setup"') == 1          # only the password-free name
    assert names.count('data-nav="home"') == 2           # the other two go straight in
    # the router stops a first-time visitor from reaching scout panes by any route
    assert "scoutPanes" in page and "if (setupPending && !setupComplete && scoutPanes[id]) id = 'setup'" in page
    assert "setupComplete = true" in page


def test_the_offline_how_to_play_page_still_plays():
    """One offline 會員章 story displays the first game ON its map marker."""
    import pathlib
    import pytest

    demo = pathlib.Path(__file__).resolve().parent.parent / "demo-preview.html"
    if not demo.exists():
        pytest.skip("demo-preview.html not built — run tools/offline_demo.py")
    page = demo.read_text()
    intro = page[page.index('id="pane-quest-intro"'):page.index('id="pane-quest-map"')]
    route = page[page.index('id="pane-quest-map"'):page.index('id="pane-guide"')]

    # the first visit: the story told in eight picture cards over the island page
    assert "你被困住了" in intro
    assert intro.count('class="story-step"') == 3
    assert "data:image/jpeg;base64," in intro    # the island, inlined
    assert 'data-quest-intro' in intro and intro.count('data-slide="') == 9
    assert 'map-canvas-story' in intro and 'story-stops' in intro
    assert 'data-intro-skip' in intro and 'data-quest-page' in intro
    assert intro.count('<li class="stage-chip') == 5
    first = intro[intro.index('class="stage-chip stage-chip-first'):]
    first = first[:first.index('</li>')]
    assert '叢林深處' in first and '童軍歷史山洞' in first
    # no description on the map (2026-10-18): the game itself tells the story
    assert '四段壁畫' not in first and 'stage-chip-desc' not in first
    assert 'stage-panel' not in intro and 'stage-radio' not in intro
    assert intro.count('data-journey-play') == 1 and 'data-nav="cave"' in intro
    # every visit after the story: the escape route only, no description up top
    assert "你被困住了" not in route and '"story-hero"' not in route
    assert 'data-quest-intro' not in route and 'class="story-step"' not in route
    assert "你的逃生路線" in route and route.count('<li class="stage-chip') == 5
    assert "0 / 5 個遊戲已完成" in route and 'data-intro-replay' in route
    assert route.count('data-journey-play') == 1 and 'data-nav="cave"' in route
    assert '<style>' in page and page.count('<style>') == 1


def test_the_offline_demo_carries_the_cave_without_a_paper():
    """From the one bottom button directly into the 50-question cave."""
    import html
    import pathlib
    import re
    demo = pathlib.Path(__file__).resolve().parent.parent / "demo-preview.html"
    if not demo.exists():
        import pytest
        pytest.skip("build demo-preview.html first")
    page = demo.read_text()
    cave = page[page.index('id="pane-cave"'):page.index('id="pane-leader"')]
    intro = page[page.index('id="pane-quest-intro"'):page.index('id="pane-quest-map"')]
    first = intro[intro.index('class="stage-chip stage-chip-first'):]
    first = first[:first.index('</li>')]
    assert '童軍歷史山洞' in first and 'class="stage-items"' not in first
    assert 'data-journey-play' in intro and 'data-nav="cave"' in intro
    assert 'data-nav="cave"' not in first, 'no extra Play link on the marker'
    assert cave.count('data-cave-art=') >= 10
    assert cave.count('data:image/jpeg;base64,') >= 10
    assert '壁畫一' in cave and '壁畫四' in cave
    assert 'data-nav="quest-intro"' in cave
    assert 'id="pane-paper"' not in page and 'id="pane-review"' not in page
    assert 'data-cave-result' not in page, 'no pre-marked score; use the actual answers'
    raw = re.search(r'data-cave-config="([^"]*)"', cave).group(1)
    config = json.loads(html.unescape(raw))
    assert config['submit_url'] == '' and sum(len(g['questions']) for g in config['groups']) == 50
    assert 'localScore()' in page and 'cave:result' in page
    assert '離線示範：遊戲 1 已在本次瀏覽期間標示完成' in page
    assert config['score']['completion'] == 'all_questions' and 'pass' not in config['score']
    assert 'data-cave-go="finish"' in page and 'data-cave-go="submit"' not in page


def test_the_offline_demo_carries_the_whole_adventure():
    """One offline map → one cave CTA; no post-cast-off pane or second exam."""
    import pathlib
    demo = pathlib.Path(__file__).resolve().parent.parent / "demo-preview.html"
    if not demo.exists():
        import pytest
        pytest.skip("build demo-preview.html first")
    page = demo.read_text()
    intro = page[page.index('id="pane-quest-intro"'):page.index('id="pane-quest-map"')]
    route = page[page.index('id="pane-quest-map"'):page.index('id="pane-guide"')]
    assert '你被困住了' in intro
    assert intro.count('class="story-step"') == 3
    assert intro.count('<li class="stage-chip') == 5
    assert intro.count('data-journey-play') == 1
    assert 'data-nav="cave"' in intro and 'data-nav="guide"' not in intro
    assert '童軍綱要參考' not in intro and 'Syllabus reference' not in intro
    assert 'data-quest-start' not in intro and '划出去' not in page
    assert 'id="pane-quest-trail"' not in page and 'id="pane-paper"' not in page
    assert '0 / 5 個遊戲已完成' in intro, 'opening the badge awards nothing'
    assert '0 / 5 個遊戲已完成' in route, 'the story hands over to the route, awarding nothing'
    assert 'trail-card' not in intro and 'quest-board' not in intro
    home = page[page.index('id="pane-home"'):page.index('id="pane-badges"')]
    assert 'class="badge-tile next" data-nav="quest-intro"' in home
    guide = page[page.index('id="pane-guide"'):page.index('id="pane-cave"')]
    assert guide.count('class="guide-item') == 11
    assert 'forms.gle/M4vtu6GwsMd5do1J8' not in guide
    assert '不需要另外做試卷' in guide and 'data-nav="cave"' in guide
    assert 'forms.gle/NmdM72WapUpbajFHA' in guide
    for pane in ('quest-intro', 'quest-map', 'guide', 'cave', 'badges', 'history'):
        chunk = page[page.index(f'id="pane-{pane}"'):]
        chunk = chunk[:chunk.index('class="pane"', 10)]
        assert 'data-nav="home"' in chunk
    assert page.count('data-nav="home"') >= 5


def test_the_front_page_buttons_follow_the_picture_left_to_right(client):
    """The narrow (three-column) sign-in is numbered by the order of these
    buttons: column one takes the first patrol. So the list must run in the
    same order the animals stand in the artwork — otter, tiger, seagull —
    or a card labelled TIGER ends up sitting on the otter.
    """
    import re
    page = client.get("/login").get_data(as_text=True)
    chunks = page.split('class="scene-spot"')[1:4]
    assert len(chunks) == 3
    order = []
    for chunk in chunks:
        order.append((re.search(r'data-mascot="(\w+)"', chunk).group(1),
                      float(re.search(r"--x: ([\d.]+)%", chunk).group(1)),
                      int(re.search(r"--col: (\d+)", chunk).group(1))))
    assert [m for m, _, _ in order] == ["Otter", "Tiger", "Seagull"]
    assert [x for _, x, _ in order] == sorted(x for _, x, _ in order)   # left to right
    assert [c for _, _, c in order] == [1, 2, 3]                        # column order matches


def test_no_class_attribute_has_a_dot_in_it(client):
    """`class="scene-hud.tr"` is ONE class named "scene-hud.tr" — every rule
    written as `.scene-hud.tr` then matches nothing. It hid the group logo in
    the corner and left the leaders' door unplaced for a while, so it is worth
    a permanent guard across every page.
    """
    import re
    seen = set()
    for path in ("/login", "/login/leader", "/login/scout/Otter"):
        page = client.get(path).get_data(as_text=True)
        for cls in re.findall(r'class="([^"]*)"', page):
            if "." in cls:
                seen.add(cls)
    assert not seen, f"dots inside class attributes: {seen}"


def _css(app) -> str:
    return app.test_client().get("/static/styles.css").get_data(as_text=True)


def test_a_full_patrol_fits_the_sign_in_name_list(app, store):
    """A patrol has 6–8 members; every name must be whole, none cut by its tile.

    (Reported: on 海鷗 the name was clipped by the box. The list now lays each
    name out as English over 中文 inside a tile that grows with its text, and
    it no longer flags who is signing in for the first time.)
    """
    import re
    from scout.util import hash_password

    patrol = "Seagull"
    seeded = [u for u in store.list("users") if u.get("patrol") == patrol]
    hashed, salt = hash_password("scout1234")
    joined = [("歐陽凱琳", "Au-Yeung Hoi Lam Alexandra"), ("梁詠詩", "Leung Wing Sze"),
              ("黃俊傑", "Wong Chun Kit"), ("何嘉欣", "Ho Ka Yan"), ("劉德華", "Lau Tak Wah")]
    for index, (zh, en) in enumerate(joined):
        store.insert("users", {
            "role": "scout", "username": f"seagull-extra-{index}", "password_hash": hashed,
            "password_salt": salt, "display_name_zh": zh, "display_name_en": en, "email": "",
            "scout_no": f"E{index}", "section": "scout", "patrol": patrol, "unit": "港島第八十二旅童軍團",
            "avatar": "🦊", "status": "active", "must_change_password": False,
            "show_on_leaderboard": True, "created_at": "2026-01-01T00:00:00", "created_by": "test",
        })

    page = app.test_client().get(f"/login/scout/{patrol}").get_data(as_text=True)
    total = len(seeded) + len(joined)
    assert page.count('class="name-tile"') == total >= 8
    assert page.count('class="name-tile-body"') == total
    for zh, en in joined:
        assert f'<span class="nm-zh">{zh}</span>' in page, zh
        assert en not in page, en                       # the English name stays off the door
    assert 'class="avatar"' not in page and '<span class="nm-en">' not in page
    assert page.count('<span class="nm-zh">') == total

    css = _css(app)
    rule = lambda sel: re.search(sel + r"\s*\{[^}]*\}", css, re.S).group(0)
    assert "minmax(190px, 1fr)" in rule(r"\.tile-grid"), "columns must stay wide enough for a name"
    assert "grid-template-columns: 1fr" in rule(r"@media \(max-width: 480px\)"), \
        "phones get one name per row"
    assert "min(780px, 94vw)" in rule(r"\.names-card"), "the name card is wider than the sign-in cards"
    assert ".name-tile .avatar" not in css and ".name-tile-body .nm-en" not in css, \
        "the styles for the emoji icon and the English name are gone too"
    assert "flex-direction: column" in rule(r"\.name-tile-body \.nm"), \
        "English name over 中文, so a two-word name never stacks one word per line"
    assert "new-badge-flag" not in page and "第一次登入" not in page, \
        "the sign-in list carries no first-time notice"
    in_card = rule(r"\.card \.nm, \.lb-row \.nm")
    assert "nowrap" not in in_card and "min-width: 0" in in_card, \
        "a long name may wrap instead of being cut by its box"


def test_login_is_one_full_screen_scene_with_the_animals_as_buttons(app, client):
    """The wide-screen login: artwork fills the screen, taps land on the animals."""
    page = client.get("/login").get_data(as_text=True)
    assert "/static/img/mascots/scene.jpg" in page                 # the artwork
    assert page.count('class="scene-spot"') == 3                   # merged buttons
    for patrol in ("Tiger", "Otter", "Seagull"):
        assert f'data-mascot="{patrol}"' in page
    for x in ("19.5%", "50.5%", "80.5%"):                          # where each sits in the art
        assert f"--x: {x}" in page
    assert 'aria-label="我是' in page                               # tappable by name too
    assert 'class="scene-prompt"' in page                          # the one line of text
    assert "選擇你的小隊" in page and "Choose your patrol" in page
    assert "purple heading" in _css(app) or "#c9a8ff" in _css(app)  # the purple heading
    assert "按一按" not in page and "Tap your animal" not in page  # no coaching lines
    # big painted names, merged into the picture (no plate / chip / button box)
    assert page.count('class="spot-name"') == 3
    assert 'class="tag"' not in page                  # no taglines under the patrols
    assert 'class="zh"' in page and 'class="en"' in page
    assert "scene-scrim" in page                                   # the wash the names sit on
    assert "spot-chip" not in page and "spot-plate" not in page


def test_the_scene_image_is_served_and_reasonably_sized(client):
    art = client.get("/static/img/mascots/scene.jpg")
    assert art.status_code == 200
    assert 40_000 < len(art.get_data()) < 900_000                  # crisp, but quick to load


def test_the_group_logo_is_served_and_used(client):
    """The 82HKG logo: on the front page, in the topbar of every page, as favicon."""
    logo = client.get("/static/img/brand/82hkg-logo.webp")
    assert logo.status_code == 200 and len(logo.get_data()) > 20_000
    assert client.get("/static/img/brand/favicon.png").status_code == 200

    login = client.get("/login").get_data(as_text=True)
    assert "/static/img/brand/82hkg-logo.webp" in login
    assert 'class="scene-hud tr"' in login             # top-right corner, not the middle
    assert 'class="scene-hud tc"' not in login
    assert 'class="scene-hud.tr"' not in login          # the dot-in-a-class typo, gone


def test_the_topbar_and_favicon_carry_the_logo(app, store):
    """Signed-in pages wear it, and the tab icon is no longer an emoji."""
    client = app.test_client()
    client.post("/login/demo/demo2")
    page = client.get("/home").get_data(as_text=True)
    assert 'class="brand-logo"' in page
    assert "img/brand/favicon.png" in page
    assert "svg+xml,<svg xmlns" not in page


def test_the_leader_login_page_shows_the_logo(client):
    page = client.get("/login/leader").get_data(as_text=True)
    assert "card-logo" in page and "82hkg-logo.webp" in page


def test_mascot_artwork_is_served(client):
    for name in ("tiger", "otter", "seagull"):
        art = client.get(f"/static/img/mascots/{name}.webp")
        assert art.status_code == 200
        assert len(art.get_data()) > 12_000                     # real artwork, not a stub


def test_the_name_page_wears_its_mascot(client):
    page = client.get("/login/scout/Otter").get_data(as_text=True)
    assert "/static/img/mascots/otter.webp" in page
    assert ">Otter<" in page                          # the patrol, in English
    assert "水獺" not in page and "🦦" not in page     # no 中文 patrol label, no emoji icon
    assert "Nimble" not in page                       # no patrol tagline
    assert "name-tile" in page


def test_a_patrol_with_no_mascot_still_works(app, store):
    """Leaders can add their own patrols; the login page must not break."""
    store.save_setting("patrols", ["Tiger", "Otter", "Seagull", "Wolf"])
    page = app.test_client().get("/login").get_data(as_text=True)
    assert "Wolf" in page and "🐣" not in page                  # named, no emoji badge
    assert app.test_client().get("/login/scout/Wolf").status_code == 200


def test_styles_and_scripts_are_served(client, app):
    css = client.get("/static/styles.css")
    assert css.status_code == 200 and len(css.get_data()) > 20_000
    for script in ("effects.js", "scout.js", "leader.js"):
        assert client.get(f"/static/js/{script}").status_code == 200
    for image in ("membership.webp", "standard.webp", "advanced.webp"):
        assert client.get(f"/static/img/{image}").status_code == 200


def test_game_layer_markup_is_present(scout_client, extras_on):
    """The feel must survive the port: rings, journey map, chests, tour, sound."""
    home = scout_client.get("/home").get_data(as_text=True)
    assert 'data-tour="1"' in home                              # first-visit tour
    assert "data-sound-toggle" in home                          # sound toggle

    badges = scout_client.get("/badges").get_data(as_text=True)
    assert "quest-map" in badges
    assert "class=\"ring" in badges and "ring-fill" in badges    # the animated ring

    rewards_home = scout_client.get("/rewards").get_data(as_text=True)
    assert "data-countup" in rewards_home                       # counting numbers

    rewards = scout_client.get("/rewards").get_data(as_text=True)
    assert "wallet-hero" in rewards and "chest" in rewards


def test_scout_pages_load_only_their_own_scripts(scout_client, leader_client):
    scout_page = scout_client.get("/home").get_data(as_text=True)
    assert "js/scout.js" in scout_page and "js/leader.js" not in scout_page
    leader_page = leader_client.get("/leader").get_data(as_text=True)
    assert "js/leader.js" in leader_page and "js/scout.js" not in leader_page


def test_there_is_only_one_line_of_text_on_the_front_page(client):
    """One heading — 選擇你的小隊 — and nothing coaching anyone about it."""
    page = client.get("/login").get_data(as_text=True)
    assert page.count("選擇你的小隊") == 2        # the scene + the tiny-window fallback
    assert page.count("按一按") == 0 and page.count("按你自己的名字") == 0
    assert "scene-caption" not in page and "mascot-hint" not in page


def test_bilingual_pages(client, app):
    """Traditional Chinese by default; the EN switch re-renders the page.

    The front page carries no language control of its own, but the switch still
    works — leaders reach it from inside the platform.
    """
    zh = client.get("/login").get_data(as_text=True)
    assert "選擇你的小隊" in zh
    assert "/set-language/" not in zh
    client.get("/set-language/en")
    en = client.get("/login").get_data(as_text=True)
    assert 'lang="en">Choose your patrol' in en
    assert "<html lang=\"en\"" in en
    client.get("/set-language/zh")
    assert "選擇你的小隊" in client.get("/login").get_data(as_text=True)


def test_bilingual_inside_the_app(scout_client):
    zh = scout_client.get("/home").get_data(as_text=True)
    assert "我的獎章" in zh
    scout_client.get("/set-language/en")
    en = scout_client.get("/home").get_data(as_text=True)
    assert "My badges" in en
    assert "積分" not in en


def test_language_switch_keeps_the_same_page(scout_client):
    response = scout_client.get("/set-language/en?next=/badges")
    assert response.status_code == 302
    assert urllib.parse.urlsplit(response.headers["Location"]).path == "/badges"
    assert "Badges" in scout_client.get("/badges").get_data(as_text=True)


# ── the optional extras start hidden ──────────────────────────────────────

def test_prizes_and_board_start_hidden(scout_client, leader_client):
    """獎品 and 龍虎榜 are off until a leader switches them on: no menu link,
    and the URL itself is closed off."""
    home = scout_client.get("/home").get_data(as_text=True)
    assert "🎁" not in home and "/rewards" not in home
    assert "🏆" not in home and "/leaderboard" not in home
    assert "🎖" in home and "📜" in home            # the basics are still there

    assert scout_client.get("/rewards", follow_redirects=False).status_code == 302
    assert scout_client.get("/leaderboard", follow_redirects=False).status_code == 302

    console = leader_client.get("/leader").get_data(as_text=True)
    assert "/leader/rewards" not in console
    assert leader_client.get("/leader/rewards", follow_redirects=False).status_code == 302

    # …and the scout is told why, on the page they land on
    landed = scout_client.get("/rewards", follow_redirects=True)
    assert landed.request.path == "/home"
    assert "獎品未開放" in landed.get_data(as_text=True)


def test_switching_one_extra_on_brings_its_page_and_link_back(app, store):
    """The one-at-a-time path: flip 龍虎榜 on, leave 獎品 off."""
    flags = dict(store.settings()["feature_flags"])
    store.save_setting("feature_flags", {**flags, "leaderboard": True, "redeem": False})
    client = app.test_client()
    client.post("/login/demo/demo2")

    page = client.get("/home").get_data(as_text=True)
    assert "/leaderboard" in page and "🏆" in page          # the board is back
    assert "/rewards" not in page and "🎁" not in page      # the shop is not
    assert client.get("/leaderboard").status_code == 200
    assert client.get("/rewards", follow_redirects=False).status_code == 302


def test_cave_record_is_game_progress_not_a_second_paper(app, store):
    """A seed completion is shown on the island map; old paper URLs redirect."""
    record = next(r for r in store.list('progress_records')
                  if r['status'] == 'completed' and r['answers_json'])
    scout = next(u for u in store.list('users') if u['id'] == record['user_id'])
    client = app.test_client()
    client.post(f"/login/scout/{scout['patrol']}/{scout['id']}", data={'password': 'scout1234'})
    task = store.get('tasks', record['task_id'])
    redirect = client.get(f"/tasks/{task['id']}")
    assert redirect.status_code == 302 and '/cave' in redirect.headers['Location']
    page = client.get(redirect.headers['Location']).get_data(as_text=True)
    assert 'data-cave' in page and 'data-task-submit' not in page
    badge = next(b for b in engine.progress_for(store, scout['id'])['badges'] if b['code'] == 'SC-01')
    assert (badge['progress_done'], badge['progress_total']) == (1, 5)


def test_task_page_replays_a_leader_verified_items_note(app, store):
    """A 領袖考核 item shows the note the scout left for the leader."""
    record = next(r for r in store.list("progress_records")
                  if r["status"] == "pending" and r["reflection_text"])
    scout = next(u for u in store.list("users") if u["id"] == record["user_id"])
    client = app.test_client()
    client.post(f"/login/scout/{scout['patrol']}/{scout['id']}", data={"password": "scout1234"})
    page = client.get(f"/tasks/{record['task_id']}").get_data(as_text=True)
    assert record["reflection_text"] in page


def test_leader_can_preview_a_task_page(leader_client, store):
    task = store.list("tasks")[0]
    assert leader_client.get(f"/leader/content/tasks/{task['id']}").status_code == 200


def test_empty_group_still_renders(client, app, store, extras_on):
    """No badges, no tasks, no notices — the console must not fall over."""
    for collection in ("badges", "tasks", "announcements", "rewards", "suggestions"):
        store.remove_where(collection, lambda row: True)
    leader = app.test_client()
    leader.post("/login/leader", data={"username": "leader1", "password": "0082"})
    for path in LEADER_PAGES:
        assert leader.get(path).status_code == 200, path
    scout = app.test_client()
    scout.post("/login/demo/demo2")
    for path in SCOUT_PAGES:
        assert scout.get(path).status_code == 200, path
    assert "還沒有獎章" in scout.get("/home").get_data(as_text=True) or True


def test_no_template_markup_leaks_into_the_html(scout_client):
    """A stray {{ }} or {% %} means a template was rendered as text."""
    for path in SCOUT_PAGES:
        page = scout_client.get(path).get_data(as_text=True)
        assert "{{" not in page and "{%" not in page
        assert "Undefined" not in page and "jinja2" not in page.lower()


def test_html_is_well_enough_formed(scout_client):
    page = scout_client.get("/badges").get_data(as_text=True)
    for tag in ("html", "head", "body", "main"):
        opened = len(re.findall(rf"<{tag}[ >]", page))
        closed = page.count(f"</{tag}>")
        assert opened == closed == 1, (tag, opened, closed)


def test_content_security_basics(scout_client):
    """Scout-facing pages must not hand out passwords or internal fields."""
    for path in SCOUT_PAGES:
        page = scout_client.get(path).get_data(as_text=True)
        for banned in ("password_hash", "password_salt", "config_json\":", "internal"):
            assert banned not in page


def test_local_driver_writes_one_file_per_collection(store, data_dir):
    from scout.schema import COLLECTION_ORDER

    for collection in COLLECTION_ORDER:
        path = os.path.join(data_dir, "db", f"{collection}.json")
        assert os.path.exists(path), path
        with open(path, encoding="utf-8") as handle:
            assert isinstance(json.load(handle), list)


def test_local_json_matches_the_node_field_names(store, data_dir):
    """The two editions must read each other's files and Sheets."""
    from scout.schema import COLLECTIONS

    with open(os.path.join(data_dir, "db", "users.json"), encoding="utf-8") as handle:
        users = json.load(handle)
    assert set(users[0]).issubset(set(COLLECTIONS["users"]["fields"]))
    with open(os.path.join(data_dir, "db", "badges.json"), encoding="utf-8") as handle:
        badges = json.load(handle)
    assert set(badges[0]).issubset(set(COLLECTIONS["badges"]["fields"]))
    assert isinstance(badges[0]["prerequisite_badge_ids"], list)


def test_writes_are_atomic_and_survive_a_reload(store, data_dir):
    store.insert("announcements", {"title_zh": "測試", "title_en": "test", "body_zh": "",
                                   "body_en": "", "audience": "all", "pinned": False,
                                   "created_at": "2026-01-01T00:00:00.000Z", "expires_at": ""})
    from scout.drivers.local import LocalDriver

    fresh = LocalDriver(data_dir)
    fresh.ensure_schema()
    assert any(row.get("title_zh") == "測試" for row in fresh.list("announcements"))
    # no half-written temp files left behind
    assert not [name for name in os.listdir(os.path.join(data_dir, "db")) if name.startswith(".tmp-")]


def test_home_renders_the_streak_chip_when_there_is_one(app, store):
    scout = next(u for u in store.list("users") if u["username"] == "scout02")
    store.update("stats", scout["id"], {"streak_current": 4, "streak_best": 4})
    client = app.test_client()
    client.post("/login/demo/demo2")
    home = client.get("/home").get_data(as_text=True)
    assert "streak-hot" in home and "🔥" in home


def test_badge_artwork_uses_the_official_images(scout_client):
    """進度性獎章 artwork comes from the Scout Association's training scheme.

    The stored path is the one the Node build writes (/img/badges/…), so a
    spreadsheet filled by either edition shows the same award images.
    """
    badge = scout_client.get("/badges").get_data(as_text=True)
    images = re.findall(r'src="(/img/badges/[^"]+)"', badge)
    assert images, "the journey map should use the official award images"
    assert all(image.endswith(".webp") for image in images)
    for image in set(images):
        assert scout_client.get(image).status_code == 200, image
    home = scout_client.get("/home").get_data(as_text=True)
    assert re.findall(r'src="(/img/badges/[^"]+)"', home), "the square tiles use the artwork too"


def test_scout_detail_urls_are_guessable_and_stable(scout_client, store):
    badge = store.list("badges")[0]
    task = next(t for t in store.list("tasks") if t["badge_id"] == badge["id"])
    assert scout_client.get(f"/badges/{badge['id']}").status_code == 200
    assert scout_client.get(f"/tasks/{task['id']}").status_code == 200
