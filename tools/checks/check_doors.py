"""會員章 has ONE door whatever you tap — check it in a real browser.

    bash tools/bootstrap_browser.sh                 # once per sandbox
    LD_LIBRARY_PATH=/tmp/syslibs python3 tools/checks/check_doors.py [base_url]

Two ways in, from a scout who has never opened the badge:

  * 主頁 → the 會員章 tile on 我的獎章      (`a.badge-tile.next`)
  * 我的獎章 → the 會員章 tile              (`a.badge-tile[href*='/badges/']`)

Both must land on the same page — the 你被困住了！ page — never a second URL for
the badge. It also refreshes docs/screens/scout-new-from-badges.png and
scout-mid-from-badges.png, which used to show the deleted game page.
"""
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
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5001"


from demo_reset import blank_slate, complete_setup


def main():
    print(f"scout07 blank slate ({blank_slate()} record(s) removed)")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1180, "height": 900}, locale="zh-HK")
        ctx.request.post(f"{BASE}/login/demo/demo3")          # scout07: a blank slate
        complete_setup(BASE, ctx)                             # …and finish required setup
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        # the first-run tour sits over /home until it is dismissed
        page.goto(f"{BASE}/home")
        page.evaluate("window.localStorage.setItem('scout.tourDone', '1')")
        page.reload()
        page.wait_for_load_state("networkidle")

        # ── door 1: 主頁, the tile that says 繼續 (the next badge) ───────────
        page.click("a.badge-tile.next")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)
        first = page.url
        heading = page.locator("h1").first.inner_text().strip()
        launch = page.locator(".story-launch").count()
        print("door 1 · 主頁 tile →", first.replace(BASE, ""))
        print("        heading:", heading, "| launch pad:", launch,
              "| maps:", page.locator(".map-canvas").count(),
              "| description on the map (want 0):", page.locator(".stage-chip-desc").count())
        assert heading == "你被困住了！" and launch == 1
        assert page.locator(".stage-chip-desc").count() == 0, \
            "the map shows no game description — it is read inside the game"
        assert page.locator(".stage-chip-first [data-game-state]").is_visible()
        assert page.locator(".stage-chip").count() == 5
        assert page.locator(".stage-radio, .stage-panel, [data-quest-start]").count() == 0
        assert page.locator("[data-journey-play]").count() == 1
        assert page.locator("a[href*='/requirements']").count() == 0
        assert "童軍綱要參考" not in page.locator("body").inner_text()
        page.screenshot(path=str(SHOTS / "scout-new-from-badges.png"), full_page=True)

        # ── door 2: 我的獎章, the 會員章 card's 打開 button ────────────────
        page.goto(f"{BASE}/badges")
        page.wait_for_load_state("networkidle")
        badge_id = first.split("/badges/")[1].split("?")[0]
        card = page.locator(f".card[data-badge-id='{badge_id}']")
        print("        card on 我的獎章:", re.sub(r"\s+", " ",
              card.inner_text()).strip()[:34] if card.count() else "MISSING")
        card.locator("a.btn").first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)
        second = page.url
        print("door 2 · 獎章 tile →", second.replace(BASE, ""))
        print("        same page:", page.url.split("?")[0] == first.split("?")[0],
              "| heading:", page.locator("h1").first.inner_text().strip())
        page.screenshot(path=str(SHOTS / "scout-mid-from-badges.png"), full_page=True)

        # ── one bottom button → straight into game 1 (not another Play step) ──
        assert page.locator("[data-journey-play]").count() == 1
        assert "童軍歷史山洞" in page.locator(".stage-chip-first").inner_text()
        assert "划出去" not in page.locator("body").inner_text()
        page.locator("[data-journey-play]").click()
        page.wait_for_load_state("networkidle")
        print("one-button game entry →", page.url.replace(BASE, ""),
              "| cave:", page.locator("#cave-root").count())
        assert "/cave" in page.url and page.locator("#cave-root").count() == 1
        assert page.locator("#cave-root").is_visible()

        # one page, never two: every tile on 主頁 opens its own award, and only
        # 會員章's is a link into the story
        page.goto(f"{BASE}/home")
        page.wait_for_timeout(300)
        hrefs = page.eval_on_selector_all(
            "a.badge-tile", "els => els.map(e => e.getAttribute('href').split('?')[0])")
        print("tiles on 主頁:", len(hrefs), "| awards:", len(set(hrefs)),
              "| every tile is a link:", all(hrefs))
        print("console errors:", errors[:3] or "none")
        browser.close()

    print(f"scout07 blank slate ({blank_slate()} record(s) removed)")


if __name__ == "__main__":
    main()
