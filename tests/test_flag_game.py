"""遊戲 4 — 溪谷旗桿（第 7 至 10 項）.

The valley continues the island story: the last patrol's notebook teaches
the flags, then the scout performs the ceremony. Finishing it — every
question answered right, with the story to lean on — clears items 7 to 10.
A short or wrong post clears nothing, and a second pass does not award
points again.
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


def test_the_story_teaches_before_the_play():
    questions = [q for station in BANK["stations"] for q in station["questions"]]
    assert len(questions) == 30
    assert len(BANK["intro"]) >= 3 and len(BANK["ending"]) >= 2
    assert "木筏" in BANK["intro"][-1]["body_zh"]
    assert "raft" in BANK["intro"][-1]["body_en"]
    # the notebook is only shown once the story mentions it: the first
    # page of the walk has no book, the pages that speak of it do
    assert "prop" not in BANK["intro"][0]
    assert all(page.get("prop") == "notebook" for page in BANK["intro"][1:])
    assert all("prop" not in page and "art" not in page for page in BANK["ending"])
    for station in BANK["stations"]:
        assert station.get("learn"), station["id"]
        for question in station["questions"]:
            assert question.get("echo_zh") and question.get("echo_en")


def test_the_flagpole_page_is_the_game(scout_client, store):
    task = task_of(store)
    page = scout_client.get(f"/tasks/{task['id']}/flag").get_data(as_text=True)
    assert page.count("data-flag") >= 1
    assert "flag.js" in page
    assert "morning ceremony" in page
    # before the walk starts, the words are merged into the valley painting
    # itself — there is no description card below the picture until the
    # walk begins and flag.js drops the start-screen class
    assert "is-start-screen" in page and "flag-start-overlay" in page
    js_text = (pathlib.Path(__file__).resolve().parent.parent / "static" / "js"
               / "flag.js").read_text(encoding="utf-8")
    assert 'root.classList.remove("is-start-screen")' in js_text
    css_text = (pathlib.Path(__file__).resolve().parent.parent / "static"
                / "styles.css").read_text(encoding="utf-8")
    assert "#flag-root.is-start-screen .flag-start-overlay" in css_text
    assert "#flag-root.is-start-screen .cave-card-wrap" in css_text
    # the flag is not raised yet on that first painting: the pole stands
    # bare, with no red flag at its top (scaled to the painting's size)
    from PIL import Image
    valley = Image.open(pathlib.Path(__file__).resolve().parent.parent / "static"
                        / "img" / "quest" / "flag" / "valley.jpg").convert("RGB")
    w, h = valley.size
    crop = valley.crop((int(w * 0.53), int(h * 0.24), int(w * 0.64), int(h * 0.34)))
    red = sum(1 for r, g, b in crop.getdata() if r > 110 and r - g > 55 and r - b > 35)
    assert red == 0, f"the unraised flagpole still shows {red} red pixels"
    # …but at the ending the same painting is swapped for the raised one,
    # with the flag up high at the top of the pole, and nothing over it
    assert 'page.prop === "notebook"' in js_text
    assert 'swapSceneArt(sourceUrl("raise-4"))' in js_text
    assert 'root.classList.add("is-ending")' in js_text
    assert "#flag-root.is-ending .pipe-story-prop" in css_text
    raise4 = Image.open(pathlib.Path(__file__).resolve().parent.parent / "static"
                        / "img" / "quest" / "flag" / "pipe" / "raise-4.jpg").convert("RGB")
    rw, rh = raise4.size
    raised = raise4.crop((int(rw * 0.50), int(rh * 0.05), int(rw * 0.66), int(rh * 0.22)))
    red_up = sum(1 for r, g, b in raised.getdata() if r > 110 and r - g > 55 and r - b > 35)
    assert red_up > 500, f"the ending flag is not up high ({red_up} red pixels)"
    # the four flags and emblems are the official artwork, not the old diagrams
    flag_dir = pathlib.Path(__file__).resolve().parent.parent / "static" / "img" / "quest" / "flag"
    for name in ("flag-national", "flag-regional", "emblem-national", "emblem-regional"):
        assert f"img/quest/flag/{name}.png" in page
        assert (flag_dir / f"{name}.png").is_file()
        assert not (flag_dir / f"{name}.svg").exists()
    assert "官方" in BANK["note_zh"] or "標準版本" in BANK["note_zh"]
    assert "official" in BANK["note_en"].lower() or "standard versions" in BANK["note_en"]
    # the ceremony is worked by the pipe machine: panel, notebook, pipes,
    # start button (no signal light any more — the button itself signals)
    # and the four quarter-raise pictures are paintings
    pipe_dir = flag_dir / "pipe"
    for name in ("panel", "notebook", "button-start", "button-start-red",
                 "pipe-straight", "pipe-elbow", "pipe-zigzag", "pipe-wave"):
        assert f'data-flag-source="{name}"' in page, name
    for gone in ("light-off", "light-red", "light-green"):
        assert f'data-flag-source="{gone}"' not in page, gone
        assert not (pipe_dir / f"{gone}.jpg").exists(), gone
    for n in (1, 2, 3, 4):
        assert f'data-flag-source="raise-{n}"' in page
    for name in ("panel", "raise-1", "raise-2", "raise-3", "raise-4"):
        assert (pipe_dir / f"{name}.jpg").is_file(), name
    # the fittings that sit on the panel — notebook, start button, sockets and
    # the four pipes — have their backgrounds removed, so they are PNGs whose
    # corners must actually be transparent
    from PIL import Image
    for name in ("notebook", "button-start", "button-start-red", "hole", "pipe-straight",
                 "pipe-elbow", "pipe-zigzag", "pipe-wave",
                 "hole-pipe-straight", "hole-pipe-elbow",
                 "hole-pipe-zigzag", "hole-pipe-wave"):
        assert f'data-flag-source="{name}"' in page, name
        path = pipe_dir / f"{name}.png"
        assert path.is_file(), name
        with Image.open(path) as im:
            assert im.mode == "RGBA" and im.getpixel((0, 0))[3] == 0, name
            if name.startswith("hole-pipe"):
                # a fitted pipe is the whole hole picture, same size as the hole
                assert im.size == Image.open(pipe_dir / "hole.png").size, name
            if name == "button-start-red":
                # the red button swaps in without jumping: same size as the green
                assert im.size == Image.open(pipe_dir / "button-start.png").size, name
    # the old paper is a study link, not the game itself
    assert "forms.gle" not in page.split("data-flag-link")[0]


def test_holes_stay_inside_the_black_board_and_answers_are_dealt_at_random():
    js = (pathlib.Path(__file__).resolve().parent.parent / "static" / "js"
          / "flag.js").read_text(encoding="utf-8")
    # the black board is only about x 32–68% of the panel painting, so the
    # grid is centred on 50% with holes no wider than 11.5%
    assert "width = 10" in js and "width = 6.2" in js and "width = 17" not in js
    assert "var x = 50 +" in js
    # every stage is re-dealt: random hole numbers, random pipe kind and a
    # random tray order for every answer
    assert "function prepareStage()" in js and "kindIndexFor" in js
    assert "Math.random" in js
    # a wrong start rings the wrong pipes in red, and the popup's buttons
    # keep light words on their dark ground
    assert "is-wrong" in js and "wrongIds" in js
    css = (pathlib.Path(__file__).resolve().parent.parent / "static"
           / "styles.css").read_text(encoding="utf-8")
    assert ".pipe-hole.is-wrong::after" in css
    assert ".pipe-popup .btn.ghost" in css and "#fff3d6" in css
    # the notes are shown before the machine, at the start of every run
    assert "function showStageNotes()" in js
    assert 'showStory(intro, 0, t("遊戲 4", "Game 4"), function () { showStageNotes(); });' in js
    # … and read in an open notebook: picture on the left page, words on
    # the right, not as a background behind the story card
    assert "notebook-open" in js and "notebook-page-left" in js
    assert "notebook-page-right" in js and ".notebook-open" in css
    assert ".flag-board.is-notes" not in css
    assert (pathlib.Path(__file__).resolve().parent.parent / "static" / "img"
            / "quest" / "flag" / "pipe" / "notebook-bg.jpg").is_file()
    # how to play is a picture pop-up after the notes, not the old long
    # sentence under the panel; it can be reopened from the machine card
    assert "function showHowTo(step)" in js and "howToSteps" in js
    # no light bulb: the start button turns red when wrong, glows when right
    assert "pipe-light" not in js and "button-start-red" in js
    assert ".pipe-start.is-wrong" in css and ".pipe-start.is-right" in css
    assert "data-flag-howto" in js and ".howto-diagram" in css
    assert "howto-ring-pulse" in css and "howto-drop-move" in css
    assert "There are \" + s.questions.length + \" holes arranged neatly" not in js


def test_pipes_are_dragged_not_clicked_lyrics_stay_in_order_and_no_all_of_these():
    root = pathlib.Path(__file__).resolve().parent.parent
    js = (root / "static" / "js" / "flag.js").read_text(encoding="utf-8")
    css = (root / "static" / "styles.css").read_text(encoding="utf-8")
    # fitting a pipe takes a drag onto the socket: a click on a pipe fits
    # nothing, and the drag works by pointer so touch screens can do it
    assert 'addEventListener("click", function () { fitPipe' not in js
    assert "pointerdown" in js and "pipe-drag-ghost" in js
    assert ".pipe-drag-ghost" in css and "touch-action: none" in css
    # while the how-to pop-up is up, the card below the picture is hidden,
    # so its leftover words and next-page button do not repeat the pop-up;
    # returning to the panel brings the card back
    assert 'root.classList.add("is-howto-open")' in js
    assert 'root.classList.remove("is-howto-open")' in js
    assert "#flag-root.is-howto-open .cave-card-wrap" in css
    # phones get room to work: the start painting is tall enough for the
    # words merged into it, and the fitting and how-to pop-ups cover the
    # screen, with the socket pinned on screen while the tray scrolls
    assert "#flag-root.is-start-screen .cave-picture" in css
    assert "position: fixed; inset: 4.4rem .55rem .55rem" in css
    assert ".pipe-fit { min-height: 5.4rem; position: sticky; top: 0" in css
    # phone holes are enlarged instead of shrunk onto the small screen:
    # the panel sits at twice width in a sideways-scrolling frame that
    # opens centred on the black board, with a swipe hint
    assert "pipe-panel-inner" in js and ".pipe-panel-inner { width: 200%; }" in css
    assert "pipe-pan-hint" in js and "pipe-pan-hint" in css
    assert "panelFrame.scrollLeft" in js
    # the anthem run deals its general questions first, then the six lyric
    # gaps one after another in song order, not shuffled among the rest
    assert 'it.station.id === "sing"' in js and "lyricOrder" in js
    sing = next(s for s in BANK["stations"] if s["id"] == "sing")
    assert [q["id"] for q in sing["questions"]] == ["q23", "q24", "q25", "q26", "q27", "q28"]
    assert [q["options_zh"][q["answer"]] for q in sing["questions"]] == [
        "奴隸", "長城", "中華民族", "吼聲", "萬眾一心", "進"]
    # no "all of the above": the small-stars question asks which class is
    # not one of the four, so exactly one of its four options is right
    assert "以上皆是" not in json.dumps(BANK, ensure_ascii=False)
    q8 = next(q for s in BANK["stations"] for q in s["questions"] if q["id"] == "q8")
    assert len(q8["options_zh"]) == 4 and len(q8["options_en"]) == 4
    assert "不是" in q8["prompt_zh"] and "not one" in q8["prompt_en"]
    assert q8["options_zh"][q8["answer"]] == "地主階級"


def test_the_notebook_is_just_called_notebook():
    root = pathlib.Path(__file__).resolve().parent.parent
    text = json.dumps(BANK, ensure_ascii=False)
    text += (root / "static" / "js" / "flag.js").read_text(encoding="utf-8")
    text += (root / "templates" / "scout" / "flag.html").read_text(encoding="utf-8")
    text += (root / "content" / "member-badge" / "guide.json").read_text(encoding="utf-8")
    # it is simply the notebook — no "last patrol's" anywhere it is named
    assert "上一小隊" not in text and "上一隊" not in text
    assert "last patrol" not in text
    assert 't("筆記", "Notebook")' in text


def test_the_flag_game_speaks_written_chinese():
    """Every scout-facing Chinese line is simple 書面語 — no colloquial
    Cantonese (撳／揀／嗰／窿／掣／駁…), in the bank, the page and the script."""
    import re
    root = pathlib.Path(__file__).resolve().parent.parent
    text = json.dumps(BANK, ensure_ascii=False)
    text += (root / "static" / "js" / "flag.js").read_text(encoding="utf-8")
    text += (root / "templates" / "scout" / "flag.html").read_text(encoding="utf-8")
    for colloquial in ("嘅", "唔", "咗", "喺", "撳", "啲", "嗰", "冇", "哋",
                       "嚟", "揀", "掣", "佢", "係", "窿", "駁", "點玩", "仲有"):
        assert colloquial not in text, colloquial
    assert "喉管" in text and "啟動按鈕" in text


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
    assert body["error"] == "flag_unfinished"
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


def test_twenty_four_out_of_thirty_does_not_pass(scout_client, store):
    """Finishing the ceremony means every line, not the old paper's 24."""
    data = answers(True)
    flipped = 0
    for key, value in list(data.items()):
        if flipped >= 6:
            break
        data[key] = "0" if value != "0" else "1"
        flipped += 1
    result = scout_client.post(f"/tasks/{task_of(store)['id']}/flag-submit", data=data)
    assert result.status_code == 400
    assert result.get_json()["error"] == "flag_unfinished"


def test_a_notes_post_cannot_skip_the_ceremony(scout_client, store):
    task = task_of(store)
    result = scout_client.post(f"/tasks/{task['id']}/submit", data={"notes": "done"})
    assert result.status_code == 403
    assert result.get_json()["error"] == "play_the_flag"


def test_the_map_offers_the_flagpole(scout_client, store):
    badge = next(b for b in store.list("badges") if b.get("code") == "SC-01")
    page = scout_client.get(f"/badges/{badge['id']}").get_data(as_text=True)
    assert "溪谷旗桿" in page
    assert page.count("即將推出") == 1
