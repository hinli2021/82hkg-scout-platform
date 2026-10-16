"""Walk demo-preview.html in a real browser: the island story and the whole walk.

    bash tools/bootstrap_browser.sh              # once per sandbox
    LD_LIBRARY_PATH=/tmp/syslibs python3 tools/checks/check_offline.py

Asserts the full zero-network journey. It does not modify server data.
"""
import html as H
import json
import os
import pathlib
import subprocess
import sys

LIBS = subprocess.run("find /tmp/syslibs -name '*.so*' -printf '%h\\n' | sort -u | tr '\\n' ':'",
                      shell=True, capture_output=True, text=True).stdout
os.environ["LD_LIBRARY_PATH"] = LIBS + os.environ.get("LD_LIBRARY_PATH", "")
from playwright.sync_api import sync_playwright   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILE = "file://" + os.path.join(ROOT, "demo-preview.html")
SHOTS = os.path.join(ROOT, "docs", "screens")

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": 1180, "height": 1100})
    external, errors = [], []
    page.on("request", lambda r: external.append(r.url) if r.url.startswith("http") else None)
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))

    def shown():
        """The pane ids, without the `pane-` prefix — i.e. the router's own names."""
        return page.eval_on_selector_all(
            ".pane", "els => els.filter(e => !e.hidden).map(e => e.id.replace('pane-', ''))")

    page.goto(FILE)
    page.wait_for_load_state("load")
    print("panes:", page.locator(".pane").count(), "| build:", page.evaluate("window.OFFLINE_DEMO_BUILD"))
    print("opening pane:", shown())

    # ── the first-time name must finish setup, and cannot dodge it ────────────
    page.click("[data-nav='names-Seagull']"); page.wait_for_timeout(250)
    page.click("#pane-names-Seagull a[data-nav='setup']"); page.wait_for_timeout(250)
    assert shown() == ["setup"], shown()
    setup = page.locator("#pane-setup")
    print("first-time door: 吳卓穎 →", shown(),
          "| form fields:", setup.locator("input").count(),
          "| says:", setup.locator(".welcome-hero h1").inner_text().strip())
    assert "兩項均為必填" in setup.inner_text()
    assert "聯絡電郵（必填）" in setup.inner_text() and "新密碼" in setup.inner_text()
    assert setup.locator('input[name="email"][required]').count() == 1
    assert "稍後再設定" not in setup.inner_text() and "Do it later" not in setup.inner_text()
    # no route past the form: Home / the badge / the game all bounce back here
    for target in ("home", "badges", "quest-intro", "cave"):
        page.evaluate(f"window.OFFLINE_DEMO.go('{target}')"); page.wait_for_timeout(120)
        assert shown() == ["setup"], (target, shown())
    print("  bypass attempts (home · 獎章 · 會員章 · 山洞) all land back on the form")
    # the server's three rules, offline: short password, mismatch, missing email
    error = page.locator("#offline-setup-error")
    for password, confirm, email, expected in (
        ("abc", "abc", "scout@example.com", "最少需要 6 個字"),
        ("tiger777", "tiger778", "scout@example.com", "兩次輸入的密碼不同"),
        ("tiger777", "tiger777", "", "有效的聯絡電郵"),
        ("tiger777", "tiger777", "not-an-email", "有效的聯絡電郵"),
    ):
        setup.locator('input[name="password"]').fill(password)
        setup.locator('input[name="confirm"]').fill(confirm)
        setup.locator('input[name="email"]').fill(email)
        setup.locator('button[type="submit"]').click(); page.wait_for_timeout(120)
        assert error.is_visible() and expected in error.inner_text(), (password, email)
        assert shown() == ["setup"], "a bad form must not open the platform"
    print("  refusals: short password · mismatch · empty email · malformed email")
    page.screenshot(path=os.path.join(SHOTS, "offline-setup.png"))
    setup.locator('input[name="password"]').fill("tiger777")
    setup.locator('input[name="confirm"]').fill("tiger777")
    setup.locator('input[name="email"]').fill("scout@example.com")
    setup.locator('button[type="submit"]').click(); page.wait_for_timeout(250)
    assert shown() == ["home"], shown()
    assert page.locator('#pane-setup input[name="password"]').input_value() == "", \
        "the offline demo must not keep the typed password"
    print("  valid password + email → home; the typed values are not kept")

    # …and the account just set up is the one the rest of the walk uses: the
    # pane switches through the same door the live app offers.
    page.evaluate("window.OFFLINE_DEMO.go('scene')"); page.wait_for_timeout(150)
    assert shown() == ["scene"], shown()

    # in: the leaders' card → one tap on the scout demo account
    page.click("[data-nav='leader-code']"); page.wait_for_timeout(200)
    page.click("[data-demo='scout']"); page.wait_for_timeout(250)
    print("home:", shown(), "| award tiles:", page.locator("#pane-home .badge-tile").count())

    # 會員章 → the one page: 玩法, the island story with the treasure map
    page.click("#pane-home a[data-nav='quest-intro']"); page.wait_for_timeout(350)
    print("── the one page for 會員章 ──")
    print("  pane:", shown())
    print("  headline:", page.locator("#pane-quest-intro .story-title").inner_text())
    print("  island art:", page.locator("#pane-quest-intro .story-art").count(),
          "| beats:", page.locator("#pane-quest-intro .story-step").count(),
          "| icons animating:", page.eval_on_selector_all(
              "#pane-quest-intro .story-step-icon", """els => els.filter(e => {
                  const s = getComputedStyle(e); return s.animationName && s.animationName !== 'none'; }).length"""))
    print("  areas on the map:", page.locator("#pane-quest-intro .stage-chip").count(),
          "| map canvas:", page.locator("#pane-quest-intro .map-canvas").count(),
          "| raft:", page.locator("#pane-quest-intro .story-raft").count())

    # The first location itself explains the game: no selecting pins, cast-off
    # form, or extra Play button. The one bottom CTA goes straight into the cave.
    first = page.locator("#pane-quest-intro .stage-chip-first")
    print("  first location:", first.inner_text().replace("\n", " | ")[:130])
    assert first.is_visible() and "童軍歷史山洞" in first.inner_text()
    assert "四段壁畫" in first.inner_text() and "五十題" in first.inner_text()
    assert page.locator("#pane-quest-intro .stage-radio, #pane-quest-intro .stage-panel").count() == 0
    assert page.locator("#pane-quest-intro [data-journey-play]").count() == 1
    assert page.locator("#pane-quest-intro [data-quest-start]").count() == 0
    assert "划出去" not in page.locator("#pane-quest-intro").inner_text()
    page.screenshot(path=os.path.join(SHOTS, "offline-story.png"), full_page=False)

    # The syllabus has no entry on the game page, but its old reference
    # content remains available (the live server still supports direct URLs).
    assert page.locator("#pane-quest-intro a[data-nav='guide']").count() == 0
    assert "童軍綱要參考" not in page.locator("#pane-quest-intro").inner_text()
    page.evaluate("window.OFFLINE_DEMO.go('guide')"); page.wait_for_timeout(200)
    print("preserved reference:", page.locator("#pane-guide .guide-item").count(), "items")
    assert page.locator("#pane-guide .guide-item[data-guide-item='4'] a[data-nav='cave']").count() == 1
    assert page.locator("#pane-paper, #pane-review, #pane-quest-trail").count() == 0
    page.evaluate("window.OFFLINE_DEMO.go('quest-intro')"); page.wait_for_timeout(150)

    page.click("#pane-quest-intro [data-journey-play]"); page.wait_for_timeout(400)
    assert shown() == ['cave']
    config = json.loads(H.unescape(page.get_attribute("#pane-cave #cave-root", "data-cave-config")))
    total = sum(len(g["questions"]) for g in config["groups"])
    assert config['submit_url'] == '', "offline cave scores locally, not via a fake paper response"
    print("cave:", shown(), "|", len(config["groups"]), "stretches |", total, "questions",
          "| hud:", page.locator("#pane-cave [data-cave-progress]").inner_text())
    page.click("#pane-cave [data-cave-go='wall']"); page.wait_for_timeout(300)

    dead_done = False
    wrong_count = 0
    backs = 0
    setback = config["setbacks"]
    stories = setback["stories"]
    limit = int(setback["wrong_limit"])
    assert limit == 3 and len(stories) >= 5, "five or six stories are expected"
    print(f"  setback rule: {limit} wrong turns in one stretch → back to its wall"
          f" | {len(stories)} stories | art: {[st['image'] + '.jpg' for st in stories[:2]]}")
    for index, group in enumerate(config["groups"], start=1):
        if index == 1:
            # the box keeps its size; a long wall scrolls inside its own panel
            view = page.evaluate("""() => {
              const panel = document.querySelector('#pane-cave .cave-card-wrap');
              const cue = document.querySelector('#pane-cave [data-cave-more]');
              return {left: panel.scrollHeight - panel.scrollTop - panel.clientHeight,
                      hidden: cue.hidden, text: cue.innerText.trim()};
            }""")
            if view["left"] > 0:
                assert not view["hidden"] and view["text"] == "▾ 向下捲動", view
                print("  long wall scrolls inside the box:", view["left"], "px | chip:", view["text"])
                page.evaluate("document.querySelector('#pane-cave .cave-card-wrap').scrollTop = 99999")
                page.wait_for_timeout(250)
                end = page.evaluate("""() => {
                  const panel = document.querySelector('#pane-cave .cave-card-wrap');
                  const cue = document.querySelector('#pane-cave [data-cave-more]');
                  return {left: panel.scrollHeight - panel.scrollTop - panel.clientHeight,
                          hidden: cue.hidden};
                }""")
                assert end["left"] <= 8 and end["hidden"], end
                page.evaluate("document.querySelector('#pane-cave .cave-card-wrap').scrollTop = 0")
                page.wait_for_timeout(200)
            print("  wall:", page.locator("#pane-cave .cave-milestone").count(), "milestones |",
                  page.locator("#pane-cave .cave-when").first.inner_text(), "→",
                  page.locator("#pane-cave .cave-what").first.inner_text()[:26])
            page.screenshot(path=os.path.join(SHOTS, "offline-cave-wall.png"), full_page=False)
        page.click("#pane-cave [data-cave-go='question']"); page.wait_for_timeout(250)
        if index == 1:
            print("  question:", page.locator("#pane-cave .cave-option").count(), "options |",
                  page.locator("#pane-cave .cave-question").inner_text()[:22])
            page.screenshot(path=os.path.join(SHOTS, "offline-cave-question.png"), full_page=False)
        for qi, q in enumerate(group["questions"], start=1):
            good = [o for o in q["options"] if o["ok"]][0]
            bad = [o for o in q["options"] if not o["ok"]][0]
            if qi % 4 == 1:   # missed first tries still clear the cave below 80
                wrong_count += 1
                page.click(f"#pane-cave [data-cave-option='{bad['key']}']")
                if not dead_done:
                    dead_done = True
                    page.wait_for_timeout(300)
                    print("  dead end:", page.locator("#pane-cave .cave-kicker-bad").count(),
                          "| 壁畫提示:", page.locator("#pane-cave .cave-explain").count(),
                          "|", page.locator("#pane-cave [data-cave-card]").inner_text()[:16].replace("\n", " "))
                    assert page.locator('#pane-cave .cave-explain strong').inner_text() == '重溫壁畫的線索'
                    assert page.locator('#pane-cave .cave-picks, #pane-cave .cave-pick-good').count() == 0
                    page.screenshot(path=os.path.join(SHOTS, "offline-cave-deadend.png"), full_page=False)
                fails = page.evaluate("window.__caveState.fails")
                if fails >= limit:
                    # 一段錯三次：a story sends the scout back to this stretch's wall
                    page.wait_for_timeout(300)
                    assert page.evaluate("window.__caveState.scene") == "setback"
                    story = stories[backs % len(stories)]
                    assert page.evaluate("window.__caveState.back.id") == story["id"]
                    text = page.locator("#pane-cave [data-cave-card]").inner_text()
                    assert story["title_zh"] in text and "要回頭了" in text, text[:60]
                    assert page.get_attribute("#pane-cave [data-cave]", "data-cave-setback") == "1"
                    print(f"  stretch {index} lost → {story['id']}:", text[:40].replace("\n", " "))
                    if backs == 0:
                        page.screenshot(path=os.path.join(SHOTS, "offline-cave-setback.png"),
                                        full_page=False)
                    backs += 1
                    page.click("#pane-cave [data-cave-go='stage-start']"); page.wait_for_timeout(280)
                    assert page.evaluate("window.__caveState.scene") == "wall"
                    assert page.evaluate(
                        "[__caveState.qi, __caveState.fails, __caveState.stagePassed]") == [0, 0, 0]
                    # the wall is read again before the chamber opens
                    assert page.locator("#pane-cave .cave-milestone").count() >= 1
                    page.click("#pane-cave [data-cave-go='question']"); page.wait_for_timeout(200)
                    for q2 in group["questions"]:
                        ok2 = [o for o in q2["options"] if o["ok"]][0]
                        page.click(f"#pane-cave [data-cave-option='{ok2['key']}']")
                        page.wait_for_timeout(45)
                        page.click("#pane-cave [data-cave-go='next']")
                        page.wait_for_timeout(45)
                    break        # the stretch has been answered; next stretch
                else:
                    torch = page.locator("#pane-cave .cave-torch")
                    assert torch.count() == 1, "a wrong turn must show what the torch has left"
                    left = limit - fails
                    expected = (f"還有 {left} 次" if left > 1 else "最後一次")
                    assert expected in torch.inner_text(), torch.inner_text()
                    if wrong_count == 1:
                        print("  after one wrong turn:", torch.inner_text().strip())
                page.click("#pane-cave [data-cave-go='question']")
                if wrong_count == 1: page.wait_for_timeout(200)
            page.click(f"#pane-cave [data-cave-option='{good['key']}']"); page.wait_for_timeout(60)
            page.click("#pane-cave [data-cave-go='next']"); page.wait_for_timeout(60)
            if index == 1 and qi == 1:
                # Leaving from the HUD offers a choice; cancel keeps this answer.
                page.click("#pane-cave .cave-hud-link[data-nav='home']")
                assert "從頭開始" in page.locator("#cave-exit-message").inner_text()
                assert shown() == ['cave']
                page.screenshot(path=os.path.join(SHOTS, "offline-cave-exit-warning.png"), full_page=False)
                page.click("[data-cave-stay]")
                assert page.evaluate("window.__caveState.passed") == 1
                assert shown() == ['cave']
        page.click("#pane-cave [data-cave-go]"); page.wait_for_timeout(220)
        print(f"  stretch {index} done ({len(group['questions'])} questions)")
    page.locator("#pane-cave .cave-verdict.is-pass").wait_for()
    assert page.locator("#pane-cave [data-cave-go='submit']").count() == 0
    score = page.locator("#pane-cave .cave-score").inner_text()
    assert wrong_count >= 11 and f"{100 - 2 * wrong_count} / 100" in score and 100 - 2 * wrong_count < 80
    assert page.locator("#pane-cave .cave-review-row").count() == wrong_count
    print("  automatically cleared at exit:", score,
          "|", page.locator("#pane-cave .cave-verdict").inner_text(),
          "| review rows:", wrong_count)
    page.screenshot(path=os.path.join(SHOTS, "offline-cave-result.png"), full_page=False)
    assert "離線示範" in page.locator("#pane-cave [data-cave-card]").inner_text()
    # 走出洞口: the run is over, so the way on is not blocked by the exit warning
    onward = page.locator("#pane-cave [data-cave-card] a[data-nav='bridge']")
    assert onward.count() == 1, "the cave mouth offers the next game"
    print("  the cave mouth:", onward.inner_text().strip()[:40])
    onward.click(); page.wait_for_timeout(350)
    assert page.locator(".cave-exit-overlay").is_hidden(), \
        "a cleared cave leaves without the 'you will restart' warning"
    assert shown() == ["bridge"], shown()
    # leaving the crossing half-laid still asks first (the guard is only lifted
    # once the run is finished)
    page.click("#pane-bridge .cave-hud-link[data-nav='home']"); page.wait_for_timeout(250)
    assert page.locator("[data-bridge-leave]").is_visible(), \
        "mid-crossing exits must still warn"
    page.click("[data-bridge-leave]"); page.wait_for_timeout(300)
    assert shown() == ["home"], shown()
    page.evaluate("window.OFFLINE_DEMO.go('quest-intro')"); page.wait_for_timeout(250)
    print("  回到會員章 →", shown(), "|", page.locator("#pane-quest-intro .story-beacon-meter").inner_text().replace("\n", " "))
    assert shown() == ['quest-intro']
    assert "1 / 5 個遊戲已完成" in page.locator("#pane-quest-intro .story-beacon-meter").inner_text()
    assert page.locator("#pane-quest-intro .stage-chip-first.is-done").count() == 1
    assert page.locator("#pane-quest-intro .stage-chip.is-here[data-stage='2']").count() == 1
    # …and the one button now opens the crossing, not a waiting notice
    assert page.locator("#pane-quest-intro [data-journey-play]").count() == 1
    assert page.locator("#pane-quest-intro [data-journey-play]").get_attribute("data-nav") == "bridge"
    assert page.locator("#pane-quest-intro [data-journey-wait]").is_hidden()
    # …and location 1 keeps its own small door back into the cave
    replay = page.locator("#pane-quest-intro [data-stage='1'] .stage-chip-replay")
    assert replay.count() == 1 and replay.inner_text().strip().endswith("再玩一次")
    print("  location 1:", replay.inner_text().strip(), "→",
          replay.get_attribute("data-nav"))
    replay.click(); page.wait_for_timeout(300)
    assert shown() == ["cave"] and page.evaluate("window.__caveState.scene") == "intro"
    print("  location 1's door opens the cave again at its entrance")
    # a re-opened cave is a fresh run, so going back out still asks first
    page.evaluate("window.OFFLINE_DEMO.go('quest-intro')"); page.wait_for_timeout(300)
    assert page.locator(".cave-exit-overlay").is_visible(), \
        "leaving a fresh replay still warns"
    page.click("[data-cave-leave]"); page.wait_for_timeout(300)
    assert shown() == ["quest-intro"], shown()

    # ── game 2: 迷霧渡口, the same walk with planks instead of questions ─────
    bridge = json.loads((pathlib.Path(ROOT) / "content" / "member-badge"
                         / "river.json").read_text(encoding="utf-8"))
    page.click("#pane-quest-intro [data-journey-play]"); page.wait_for_timeout(400)
    assert shown() == ["bridge"], shown()
    bridge_cfg = json.loads(H.unescape(page.get_attribute("#pane-bridge [data-bridge]",
                                                           "data-bridge-config")))
    assert bridge_cfg["submit_url"] == "", "offline bridge checks the planks itself"
    print("bridge:", shown(), "|", len(bridge_cfg["stages"]), "stages | board total:",
          sum(len(st["planks"]) for st in bridge_cfg["stages"]),
          "| hud:", page.locator("#pane-bridge [data-bridge-progress]").inner_text())
    page.click("#pane-bridge [data-bridge-go='teach']"); page.wait_for_timeout(300)
    page.screenshot(path=os.path.join(SHOTS, "offline-bridge-teach.png"), full_page=False)
    for index, stage in enumerate(bridge_cfg["stages"], start=1):
        # the teaching card carries the wording itself and a detail under each line
        notes = page.evaluate("""() => [...document.querySelectorAll('#pane-bridge [data-bridge-card] .bridge-said-note')]
            .map(note => note.textContent.trim())""")
        assert notes == stage["teach"]["details_zh"], \
            f"stage {index}: every sentence needs its detail line, got {len(notes)}"
        page.click("#pane-bridge [data-bridge-go='build']"); page.wait_for_timeout(250)
        # the empty boxes stand in rows, one row to a sentence, and the order box
        # hands the scout the whole sentence — never a chopped-up trail
        rows = page.evaluate("""() => [...document.querySelectorAll('#pane-bridge .bridge-line')]
            .map(row => row.querySelectorAll('.bridge-slot').length)""")
        want = []
        for plank in stage["planks"]:
            if not want or want[-1][0] != plank["line"]:
                want.append([plank["line"], 1])
            else:
                want[-1][1] += 1
        assert rows == [row[1] for row in want], \
            f"stage {index}: boxes should stand in sentence rows, got {rows} want {want}"
        goal = page.locator("#pane-bridge .bridge-goal").inner_text()
        assert all(''.join(sentence.split()) in ''.join(goal.split())
                   for sentence in stage["teach"]["sentences_zh"]), \
            f"stage {index}: the order box must show the whole sentence"
        print(f"  stage {index}: {len(rows)} sentence rows | order box: {goal[:34]}…"
              if len(goal) > 36 else f"  stage {index}: {len(rows)} sentence rows | order box: {goal}")
        if index == 1:
            print("  stage 1:", page.locator("#pane-bridge .bridge-slot").count(), "slots |",
                  page.locator("#pane-bridge .bridge-plank").count(), "planks |",
                  page.locator("#pane-bridge .bridge-goal").inner_text())
            page.screenshot(path=os.path.join(SHOTS, "offline-bridge-build.png"), full_page=False)
        if index == 2:
            # a board out of order: the teaching card comes back, not the answer
            wrong_key = stage["planks"][1]["key"]
            page.click(f"#pane-bridge [data-bridge-plank='{wrong_key}']")
            page.wait_for_timeout(250)
            recap = page.locator("#pane-bridge [data-bridge-card]").inner_text()
            assert stage["teach"]["title_zh"] in recap and "教學牌" in recap
            assert not any(p["zh"] in recap for p in stage["planks"][1:2] if p["key"] != wrong_key), \
                "the recap must not hand over the order"
            page.screenshot(path=os.path.join(SHOTS, "offline-bridge-recap.png"), full_page=False)
            page.click("#pane-bridge [data-bridge-go='retry']"); page.wait_for_timeout(250)
        swapped = 0
        for plank in stage["planks"]:
            # any copy of the right word will do: duplicates are interchangeable
            key = page.evaluate("""([want, canonical]) => {
                const same = [...document.querySelectorAll('#pane-bridge [data-bridge-plank]')]
                    .filter(b => b.textContent.trim() === want)
                    .map(b => b.getAttribute('data-bridge-plank'));
                const other = same.filter(k => k !== canonical);
                return other.length ? other[0] : same[0];
            }""", [plank["zh"], plank["key"]])
            assert key, f"{plank['zh']} is not on the bank"
            if key != plank["key"]:
                swapped += 1
            page.click(f"#pane-bridge [data-bridge-plank='{key}']")
            page.wait_for_timeout(50)
        page.wait_for_timeout(120)
        if swapped:
            print(f"  stage {index}: {swapped} board(s) taken as a different copy of the same word")
        last = index == len(bridge_cfg["stages"])
        page.click(f"#pane-bridge [data-bridge-go='{'finish' if last else 'next'}']")
        page.wait_for_timeout(220)
        print(f"  stage {index} laid ({len(stage['planks'])} planks)")
    page.locator("#pane-bridge [data-bridge-scene='result']").wait_for()
    assert "第 5 項已完成" in page.locator("#pane-bridge [data-bridge-card]").inner_text()
    assert page.locator("#pane-bridge [data-bridge-link='badge']").count() >= 1
    back = page.locator("#pane-bridge [data-bridge-card] a[data-nav='quest-intro']")
    assert back.count() == 1, "the win offers the badge, and offline that is the map pane"
    page.screenshot(path=os.path.join(SHOTS, "offline-bridge-result.png"), full_page=False)
    back.click(); page.wait_for_timeout(300)
    # the crossing is laid: no 'you will restart' warning on the way out
    assert page.locator("[data-bridge-leave]").is_hidden(), \
        "a finished crossing leaves without a warning"
    assert shown() == ["quest-intro"], shown()
    meter = page.locator("#pane-quest-intro .story-beacon-meter").inner_text()
    assert "2 / 5 個遊戲已完成" in meter, meter
    assert page.locator("#pane-quest-intro .stage-chip[data-stage='2'].is-done").count() == 1
    assert page.locator("#pane-quest-intro .stage-chip.is-here[data-stage='3']").count() == 1
    assert page.locator("#pane-quest-intro [data-journey-play]").count() == 0
    assert "遊戲 3" in page.locator("#pane-quest-intro [data-journey-wait]").inner_text()
    print("  after the crossing:", meter.replace("\n", " "),
          "| next:", page.locator("#pane-quest-intro [data-journey-wait]").inner_text().strip())
    replay2 = page.locator("#pane-quest-intro [data-stage='2'] .stage-chip-replay")
    assert replay2.count() == 1, "a cleared crossing keeps its own door too"
    replay2.click(); page.wait_for_timeout(300)
    assert shown() == ["bridge"]
    assert page.get_attribute("#pane-bridge [data-bridge]", "data-bridge-scene") == "intro"
    print("  location 2's door re-opens the crossing from its first stage")
    page.evaluate("window.OFFLINE_DEMO.go('quest-intro')"); page.wait_for_timeout(300)
    assert page.locator("[data-bridge-leave]").is_visible(), \
        "a fresh replay of the crossing warns as well"
    page.click("[data-bridge-leave]"); page.wait_for_timeout(300)
    assert shown() == ["quest-intro"], shown()
    page.evaluate("window.OFFLINE_DEMO.go('home')"); page.wait_for_timeout(200)
    tile = page.locator("#pane-home [data-badge-meter]").first
    assert "2 / 5" in tile.inner_text()
    print("  home tile:", tile.inner_text().replace("\n", " "))

    for pane in ("quest-intro", "guide", "cave", "bridge", "badges", "history"):
        page.evaluate(f"window.OFFLINE_DEMO.go('{pane}')")
        page.wait_for_timeout(150)
        link = page.locator(f"#pane-{pane} a[data-nav='home']").first
        label = link.inner_text().strip().replace("\n", " ")[:16]
        link.click()
        if pane == 'cave':
            assert page.locator('.cave-exit-overlay').is_visible()
            page.click('[data-cave-leave]')
            assert page.evaluate('window.__caveState.scene') == 'intro'
        if pane == 'bridge':
            assert page.locator('[data-bridge-leave]').is_visible()
            page.click('[data-bridge-leave]')
            # leaving closes the crossing: the next visit opens on stage one again
            assert page.get_attribute('#pane-bridge [data-bridge]',
                                      'data-bridge-scene') in ('intro', 'teach')
            assert page.locator('#pane-bridge [data-bridge-progress]').inner_text().startswith('第 1 / 3 關')
        page.wait_for_timeout(150)
        landed = shown()
        print(f"  {pane:12s} → {label:16s} → {landed}")
        assert landed == ["home"]
    print("every screen still offers the way home")

    page.evaluate("window.OFFLINE_DEMO.go('scene')"); page.wait_for_timeout(150)
    page.click("[data-nav='leader-code']"); page.wait_for_timeout(150)
    page.fill("#pane-leader-code input[name='password']", "0082")
    page.click("#pane-leader-code button[type=submit]"); page.wait_for_timeout(250)
    print("leader console behind 0082:", shown())
    print("external requests:", external[:3], "| console errors:", errors[:3])
    browser.close()
