"""Play 第 4 項's cave end to end in a real browser, and shoot every scene.

    bash tools/bootstrap_browser.sh                 # once per sandbox
    LD_LIBRARY_PATH=/tmp/syslibs python3 tools/checks/check_cave.py [base_url] [--fast]

It walks entrance → four walls (reading each timeline) → the fifty questions,
taking enough wrong first turns for a score below 80 — including one stretch
lost to 一段錯三次, which must send the scout back to that wall with a story and
clear the stretch's own progress. It then automatically records game 1 on
reaching the exit and reads the score and review. Writes docs/screens/cave-*.png.

`--fast` skips screenshots for a quick smoke test.
The completed run is recorded for demo3 → scout07; its records, points and start flag
are cleared afterwards so repeat checks leave the demo account blank.
"""
import html as H
import json
import os
import pathlib
import re
import subprocess
import sys

LIBS = subprocess.run("find /tmp/syslibs -name '*.so*' -printf '%h\\n' | sort -u | tr '\\n' ':'",
                      shell=True, capture_output=True, text=True).stdout
os.environ["LD_LIBRARY_PATH"] = LIBS + os.environ.get("LD_LIBRARY_PATH", "")
from playwright.sync_api import sync_playwright   # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHOTS = ROOT / "docs" / "screens"
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
BASE = ARGS[0] if ARGS else "http://127.0.0.1:5001"
FAST = "--fast" in sys.argv


from demo_reset import blank_slate, complete_setup


def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    blank_slate()
    backs = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1180, "height": 900}, locale="zh-HK")
        ctx.request.post(f"{BASE}/login/demo/demo3")
        complete_setup(BASE, ctx)          # 第一次登入：必填密碼 + 電郵
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        mid = json.loads((ROOT / "data" / "db" / "tasks.json").read_text())
        mid = next(r["id"] for r in mid if r.get("code") == "M04")
        page.goto(f"{BASE}/tasks/{mid}/cave")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(400)

        cfg = json.loads(H.unescape(page.get_attribute("#cave-root", "data-cave-config")))
        total = sum(len(g["questions"]) for g in cfg["groups"])
        # 一段錯三次：the stories and the limit come from cave.json → setbacks
        setback = cfg["setbacks"]
        stories = setback["stories"]
        limit = int(setback["wrong_limit"])
        assert limit == 3 and len(stories) >= 5, "five or six stories are expected"
        print(f"  setback rule: {limit} wrong turns in one stretch → back to its wall"
              f" | {len(stories)} stories")

        def art():
            return (page.get_attribute(".cave-art", "src") or "").rsplit("/", 1)[-1]

        def card():
            return re.sub(r"\s+", " ", page.inner_text("[data-cave-card]")).strip()

        def shot(name):
            if not FAST:
                page.screenshot(path=str(SHOTS / name))

        def words_below_the_picture(where):
            """the leader's rule: no message may lie on top of the cave painting"""
            box = page.evaluate("""() => {
              const p = document.querySelector('.cave-picture').getBoundingClientRect();
              const w = document.querySelector('.cave-card-wrap').getBoundingClientRect();
              const a = document.querySelector('.cave-art').getBoundingClientRect();
              return {overlap: Math.round(Math.max(0, p.bottom - w.top)),
                      artInside: a.top >= p.top - 1 && a.bottom <= p.bottom + 1};
            }""")
            assert box["artInside"], f"the picture is cut off at the {where}"
            assert box["overlap"] == 0, f"the words cover the picture at the {where} ({box['overlap']}px)"

        words_below_the_picture('entrance')
        print(f"cave — {len(cfg['groups'])} stretches, {total} questions, "
              f"chambers {cfg['chambers']}, dead ends {cfg['deadends']}")
        print("entrance:", card()[:46], "| art:", art())
        shot("cave-intro.png")
        page.click("[data-cave-go='wall']")
        page.wait_for_timeout(400)

        wrong_total = 0
        for index, group in enumerate(cfg["groups"], start=1):
            rows = page.locator(".cave-milestone").count()
            print(f"stretch {index}: {group['icon']} {group['name_zh']} — wall:",
                  rows, "milestones | art:", art())
            print("   first milestone:", page.locator(".cave-when").first.inner_text(),
                  "·", page.locator(".cave-what").first.inner_text()[:30])
            if index == 1:
                shot("cave-wall.png")
                # The box keeps its size; a long wall scrolls inside the panel
                # below the picture, and 向下捲動 says so until the last line.
                view = page.evaluate("""() => {
                  const stage = document.querySelector('.cave-stage').getBoundingClientRect();
                  const panel = document.querySelector('.cave-card-wrap');
                  const cue = document.querySelector('[data-cave-more]');
                  const r = cue.getBoundingClientRect();
                  return {fits: stage.bottom <= window.innerHeight + 1,
                          innerScroller: panel.scrollHeight > panel.clientHeight + 2,
                          left: panel.scrollHeight - panel.scrollTop - panel.clientHeight,
                          chip: !cue.hidden && r.bottom <= window.innerHeight + 1 && r.top > 0,
                          text: cue.innerText.trim()};
                }""")
                assert view["fits"], "the game box runs past the bottom of the screen"
                assert view["innerScroller"] and view["left"] > 0, view
                assert view["chip"] and view["text"] == "▾ 向下捲動", view
                print("   long wall: box at full height |", view["left"], "px scrolled inside | chip:", view["text"])
                page.evaluate("document.querySelector('.cave-card-wrap').scrollTop = 99999")
                page.wait_for_timeout(300)
                end_view = page.evaluate("""() => {
                  const panel = document.querySelector('.cave-card-wrap');
                  const cue = document.querySelector('[data-cave-more]');
                  const card = document.querySelector('[data-cave-card]');
                  const last = [...card.querySelectorAll('p, li, button, a')].pop();
                  const r = last.getBoundingClientRect();
                  return {left: panel.scrollHeight - panel.scrollTop - panel.clientHeight,
                          hidden: cue.hidden, text: last.innerText.trim(),
                          inside: r.bottom <= panel.getBoundingClientRect().bottom + 1};
                }""")
                assert end_view["left"] <= 8 and end_view["hidden"], end_view
                assert end_view["inside"], end_view
                print("   scrolled to the last line:", end_view["text"][:16], "— chip gone, line reads in full")
                page.evaluate("document.querySelector('.cave-card-wrap').scrollTop = 0")
                page.wait_for_timeout(200)
            page.click("[data-cave-go='question']")
            page.wait_for_timeout(350)

            right = [q for q in group["questions"] if any(o["ok"] for o in q["options"])]
            # stretches 1–3 lose this many questions to wrong turns before the
            # scout is sent back; the walked stretch is then answered cleanly
            miss = [0, 5, 9] if index <= 3 else [0, 5]
            if index == 4:
                miss = [0, 5]
            if index == 1:
                miss = [0, 5, 9]
            if index == 2:
                miss = [0, 5, 9]
            if index == 3:
                miss = [0, 5, 8]
            for qi, question in enumerate(group["questions"]):
                options = page.locator(".cave-option")
                if options.count() not in (3, 4):
                    raise SystemExit(f"question {question['id']} offered {options.count()} options")
                good = [o for o in question["options"] if o["ok"]][0]
                bad = [o for o in question["options"] if not o["ok"]][0]
                if qi in miss:  # enough missed first tries for <80; still retry each
                    page.click(f"[data-cave-option='{bad['key']}']")
                    wrong_total += 1
                    fails = page.evaluate('window.__caveState.fails')
                    if wrong_total == 1:
                        page.wait_for_timeout(300)
                        print("   dead end at", question["id"], "| art:", art(), "|",
                              card()[:40])
                        words_below_the_picture('dead end')
                        assert page.locator('.cave-explain strong').inner_text() == '重溫壁畫的線索'
                        assert page.locator('.cave-picks, .cave-pick-good').count() == 0
                        shot("cave-deadend.png")
                    if fails >= limit:
                        # the third wrong turn: a story sends the scout back
                        page.wait_for_timeout(320)
                        scene = page.evaluate('window.__caveState.scene')
                        assert scene == 'setback', scene
                        story = stories[backs % len(stories)]
                        assert page.evaluate('window.__caveState.back.id') == story["id"]
                        text = card()
                        assert story["title_zh"] in text and "要回頭了" in text
                        assert art() == story["image"] + ".jpg", art()
                        words_below_the_picture('setback story')
                        print(f"   stretch {index} lost → {story['id']}:",
                              text[:44].replace(chr(10), ' '))
                        if backs == 0:
                            shot("cave-setback.png")
                        backs += 1
                        page.click("[data-cave-go='stage-start']")
                        page.wait_for_timeout(320)
                        assert page.evaluate('window.__caveState.scene') == 'wall'
                        assert page.evaluate(
                            '[__caveState.qi, __caveState.fails, __caveState.stagePassed]') == [0, 0, 0]
                        print("   back at the wall: this stretch starts again")
                        # the wall is read again before the chamber opens
                        assert page.locator('.cave-timeline .cave-milestone').count() >= 1
                        page.click("[data-cave-go='question']")
                        page.wait_for_timeout(200)
                        for q2 in group["questions"]:
                            ok2 = [o for o in q2["options"] if o["ok"]][0]
                            page.click(f"[data-cave-option='{ok2['key']}']")
                            page.wait_for_timeout(150)
                            page.click("[data-cave-go='next']")
                            page.wait_for_timeout(110)
                        break          # this stretch is answered; on to the next wall
                    # the dead-end card carries the torch count down with it
                    torch = page.locator('.cave-torch')
                    assert torch.count() == 1, 'a wrong turn must show what the torch has left'
                    left = limit - fails
                    expected = (f"還有 {left} 次" if left > 1 else "最後一次")
                    assert expected in torch.inner_text(), torch.inner_text()
                    if wrong_total == 1:
                        print("   after one wrong turn:", torch.inner_text().strip())
                    page.click("[data-cave-go='question']")
                    if wrong_total == 1: page.wait_for_timeout(250)
                page.click(f"[data-cave-option='{good['key']}']")
                page.wait_for_timeout(180)
                page.click("[data-cave-go='next']")
                page.wait_for_timeout(120)
                if index == 1 and qi == 0:
                    # The top-home exit warns; staying must preserve question 1.
                    page.locator('.cave-hud-link').first.click()
                    assert "從頭開始" in page.locator('#cave-exit-message').inner_text()
                    shot('cave-exit-warning.png')
                    page.click('[data-cave-stay]')
                    assert page.evaluate('window.__caveState.passed') == 1
            words_below_the_picture(f'stretch {index} questions')
            print(f"   {len(group['questions'])} questions answered | group card:", card()[:34])
            if index == 1:
                shot("cave-groupdone.png")
            page.click("[data-cave-go]")                      # next wall / automatic finish
            page.wait_for_timeout(350)
            if index == 1:
                shot("cave-wall2.png")

        page.locator(".cave-verdict.is-pass").wait_for()
        assert page.locator("[data-cave-go='submit']").count() == 0
        assert wrong_total >= 11 and page.locator(".cave-review-row").count() == wrong_total
        expected = 100 - 2 * wrong_total
        score = page.locator(".cave-score").inner_text()
        # 成績改為百分比：第一次作答答對的比率，加上全程作答的準確率
        assert f"{expected}%" in score and expected < 80, score
        attempts = page.locator(".cave-attempts").inner_text()
        assert "答錯" in attempts and "次" in attempts, attempts
        counted = int(attempts.split("其中")[1].split("次答錯")[0].strip())
        assert counted >= wrong_total, attempts      # 每一次錯摸（含重試）都數得到
        assert "第一次作答" in attempts, attempts
        print("exit and automatic result:", card()[:90], "| art:", art())
        shot("cave-exit.png")
        print("  percentage shown:", score, "|", attempts)
        words_below_the_picture('result')
        print("  verdict:", page.locator(".cave-verdict").inner_text(),
              "| review rows:", wrong_total)
        shot("cave-result.png")
        # 走出洞口 → the journey carries straight on: the first action is game 2
        onward = page.locator("[data-cave-card] a.btn").first
        print("  at the cave mouth:", onward.inner_text().strip()[:46], "→",
              onward.get_attribute("href").split("?")[0])
        assert '/bridge' in onward.get_attribute('href'), 'the way on is game 2'
        # It must open game 2 without the exit warning: the guard is for a
        # half-finished cave, and a cleared run has nothing left to lose.
        onward.click()
        page.wait_for_load_state("networkidle")
        assert '/bridge' in page.url and page.get_attribute('[data-bridge]',
                                                            'data-bridge-scene') == 'intro'
        assert not page.locator('.cave-exit-overlay').is_visible(), \
            'the way on is not blocked by the "you will restart" warning'
        print("  the continue button opened the crossing (game 2)")
        # …and the map now offers game 2 while keeping location 1's own door
        badge_rows = json.loads((ROOT / "data" / "db" / "badges.json").read_text())
        badge_id = next(row["id"] for row in badge_rows if row.get("code") == "SC-01")
        page.goto(f'{BASE}/badges/{badge_id}')
        page.wait_for_load_state("networkidle")
        assert "1 / 5 個遊戲已完成" in page.locator("body").inner_text()
        assert page.locator(".stage-chip-first.is-done").count() == 1
        assert page.locator(".stage-chip[data-stage='2'].is-here").count() == 1
        # game 2 is built now, so the one button hands over to the crossing
        bridge_id = next(row["id"] for row in
                         json.loads((ROOT / "data" / "db" / "tasks.json").read_text())
                         if row.get("code") == "M05")
        play = page.locator("[data-journey-play]")
        assert play.count() == 1 and f"/tasks/{bridge_id}" in play.get_attribute("href")
        assert "進入遊戲 2" in play.inner_text()
        replay = page.locator('[data-replay="stage-1"]')
        assert replay.count() == 1 and '/cave' in replay.get_attribute('href'), \
            'location 1 keeps its own door back into the cave'
        replay.click()
        page.wait_for_load_state('networkidle')
        assert '/cave' in page.url and page.evaluate('window.__caveState.scene') == 'intro'
        print('  location 1 replays: the cave opens again at its entrance')
        page.go_back()
        page.wait_for_load_state("networkidle")
        print("map after game one: 1 / 5 games cleared | next:", play.inner_text().strip(),
              "| other games:",
              page.locator(".stage-chip-game", has_text="即將推出").count(), "unavailable")
        assert page.locator(".stage-chip-game", has_text="即將推出").count() == 3
        assert not errors, f"browser errors: {errors[:3]}"
        print("console errors: none")
        browser.close()
    print("scout07 blank slate:", blank_slate(), "record(s) removed")


if __name__ == "__main__":
    main()
