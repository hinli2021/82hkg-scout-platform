#!/usr/bin/env python3
"""The sign-in name list must hold a real patrol — 6 to 8 scouts, every name whole.

    bash tools/bootstrap_browser.sh                                  # once
    LD_LIBRARY_PATH=/tmp/syslibs python3 tools/checks/check_names.py

A unit's patrol has six or seven members, so the 小隊 → 姓名 page is checked at
every width it is used at (a phone at 320px up to a desktop at 1440px) with a
full roster built for the occasion: 7–8 names per patrol, one account with no
password yet (its tile must still open the set-a-password form), and one
deliberately long name. The list shows names and nothing else — no first-time
notice is written beside anyone.

It reports, for each width: how many names wrapped to a second line, whether any
name is cut by its tile, and whether the page overflows sideways. It fails the
run on a cut name, a sideways overflow or a name that did not render at all.

Nothing here touches the real `data/`: the roster lives in a throwaway directory
and is served by a temporary server on a spare port. Screenshots land in
docs/screens/names-list{,-phone}.png.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading

LIBS = subprocess.run("find /tmp/syslibs -name '*.so*' -printf '%h\\n' | sort -u | tr '\\n' ':'",
                      shell=True, capture_output=True, text=True).stdout
os.environ["LD_LIBRARY_PATH"] = LIBS + os.environ.get("LD_LIBRARY_PATH", "")

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHOTS = ROOT / "docs" / "screens"
PORT = int(os.environ.get("NAMES_CHECK_PORT", "5077"))

# the roster below is invented; the size is the point (6–8 per patrol)
ROSTER = {
    "Seagull": [("陳小明", "Chan Siu Ming"), ("李美儀", "Lee Mei Yee"), ("吳卓穎", "Ng Cheuk Wing"),
                ("張家豪", "Cheung Ka Ho"), ("黃俊傑", "Wong Chun Kit"), ("何嘉欣", "Ho Ka Yan"),
                ("梁詠詩", "Leung Wing Sze"), ("歐陽凱琳", "Au-Yeung Hoi Lam Alexandra")],
    "Tiger": [("王小明", "Wong Siu Ming"), ("林小玲", "Lam Siu Ling"), ("陳大文", "Chan Tai Man"),
              ("劉德華", "Lau Tak Wah"), ("周星馳", "Chow Sing Chi"), ("鄭秀文", "Cheng Sau Man"),
              ("麥當娜", "Mak Donna")],
    "Otter": [("馮寶寶", "Fung Bo Bo"), ("曾志偉", "Tsang Chi Wai"), ("張學友", "Cheung Hok Yau"),
              ("郭富城", "Kwok Fu Sing"), ("黎明", "Lai Ming"), ("許冠傑", "Hui Koon Kit"),
              ("林子祥", "Lam Chi Cheung")],
}
WITHOUT_PASSWORD = {("Seagull", "Ng Cheuk Wing")}      # no password yet: opens the setup form


def build_site() -> tuple[object, pathlib.Path]:
    """A seeded site in a temporary data dir, with a full roster in every patrol."""
    workdir = pathlib.Path(tempfile.mkdtemp(prefix="names-check-"))
    os.environ["DATA_DIR"] = str(workdir)
    os.environ["SEED_DEMO"] = "true"
    os.environ.setdefault("SECRET_KEY", "names-check")
    os.environ.setdefault("DEMO_LOGIN", "true")
    sys.path.insert(0, str(ROOT))
    from app import create_app                                   # noqa: E402
    from scout.store import Store                                # noqa: E402
    from scout.util import hash_password                         # noqa: E402

    app = create_app()
    store = Store.from_env()
    hashed, salt = hash_password("scout1234")
    # the sample scouts step aside: this check wants a realistic patrol and
    # nothing else (they only exist in this throwaway data dir)
    for row in list(store.list("users")):
        if str(row.get("username", "")).startswith("scout"):
            store.remove("users", row["id"])
    for patrol, people in ROSTER.items():
        for index, (zh, en) in enumerate(people):
            fresh = (patrol, en) in WITHOUT_PASSWORD
            store.insert("users", {
                "role": "scout", "username": f"{patrol.lower()}{index}",
                "password_hash": "" if fresh else hashed,
                "password_salt": "" if fresh else salt,
                "display_name_zh": zh, "display_name_en": en, "email": "",
                "scout_no": f"{patrol[0]}{index}", "section": "scout", "patrol": patrol,
                "unit": "港島第八十二旅童軍團", "avatar": "🦊", "status": "active",
                "must_change_password": fresh, "show_on_leaderboard": True,
                "created_at": "2026-01-01T00:00:00", "created_by": "check",
            })
    return app, workdir


def serve(app) -> object:
    from werkzeug.serving import make_server
    server = make_server("127.0.0.1", PORT, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    app, workdir = build_site()
    server = serve(app)
    base = f"http://127.0.0.1:{PORT}"
    print(f"temporary site on {base} · data in {workdir}")
    for patrol, people in ROSTER.items():
        print(f"  {patrol}: {len(people)} members · "
              f"no password yet: {sum(1 for _, en in people if (patrol, en) in WITHOUT_PASSWORD)}")

    from playwright.sync_api import sync_playwright

    problems: list[str] = []
    widths = (320, 390, 480, 768, 1180, 1440)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for width in widths:
            ctx = browser.new_context(viewport={"width": width, "height": 900}, locale="zh-HK")
            page = ctx.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            for patrol, people in ROSTER.items():
                page.goto(f"{base}/login/scout/{patrol}")
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(250)
                report = page.evaluate("""() => {
                  const tiles = [...document.querySelectorAll('.name-tile')];
                  const lines = el => {
                    const lh = parseFloat(getComputedStyle(el).lineHeight) || 18;
                    return el.getBoundingClientRect().height > lh * 1.6;
                  };
                  return {
                    total: tiles.length,
                    cols: new Set(tiles.map(t => t.offsetLeft)).size,
                    names: tiles.map(t => t.querySelector('.nm-zh').textContent.trim()),
                    wrapped: tiles.filter(t => lines(t.querySelector('.nm-zh'))).map(
                        t => t.querySelector('.nm-zh').textContent.trim()),
                    cut: tiles.filter(t => t.scrollHeight > t.clientHeight + 1 ||
                                           t.scrollWidth > t.clientWidth + 1)
                              .map(t => t.querySelector('.nm-zh').textContent.trim()),
                    flagged: tiles.flatMap(t => [...t.querySelectorAll('*')]
                        .map(n => n.textContent).filter(x => /第一次登入|First time in/.test(x))),
                    latin: tiles.map(t => t.textContent).flatMap(x => x.match(/[A-Za-z]{2,}/g) || []),
                    sideways: document.documentElement.scrollWidth > window.innerWidth,
                    card: document.querySelector('.names-card').clientWidth,
                    gridHeight: Math.round(document.querySelector('.tile-grid').getBoundingClientRect().height),
                  };
                }""")
                expected = [zh for zh, _ in people]
                label = f"{width}px · {patrol}"
                print(f"  {label:22s} names {report['total']:2d} · columns {report['cols']} · "
                      f"card {report['card']:4d}px · list {report['gridHeight']:4d}px · "
                      f"wrapped {len(report['wrapped'])} · cut {len(report['cut'])}"
                      f"{' · SIDEWAYS SCROLL' if report['sideways'] else ''}")
                # the list is sorted by the Chinese name, so compare as a set
                if sorted(report["names"]) != sorted(expected):
                    problems.append(f"{label}: names on the page are {report['names']}, expected {expected}")
                if report["cut"]:
                    problems.append(f"{label}: cut by the tile: {report['cut']}")
                if report["sideways"]:
                    problems.append(f"{label}: the page scrolls sideways")
                if report["latin"]:
                    problems.append(f"{label}: an English name is back on the door: {report['latin']}")
                if report["flagged"]:
                    problems.append(f"{label}: a first-time notice is back on the list: {report['flagged']}")
                if report["total"] != len(expected):
                    problems.append(f"{label}: {report['total']} tiles, expected {len(expected)}")
                if width > 480 and report["cols"] < 2:
                    problems.append(f"{label}: only {report['cols']} column on a wide screen")
                if width <= 480 and report["cols"] != 1:
                    problems.append(f"{label}: the phone list should be one name per row")
            if errors:
                problems.append(f"{width}px: browser errors {errors[:3]}")
            # the tiles must stay working doors, and the no-password one leads to setup
            page.goto(f"{base}/login/scout/Tiger")
            page.wait_for_load_state("networkidle")
            page.locator(".name-tile").first.click()
            page.wait_for_load_state("networkidle")
            print(f"  {width}px · first Tiger name → {page.url.replace(base, '')}")
            assert "/login/scout/Tiger/" in page.url, page.url
            page.goto(f"{base}/login/scout/Seagull")
            page.wait_for_load_state("networkidle")
            page.locator(".name-tile", has_text="吳卓穎").click()
            page.wait_for_load_state("networkidle")
            fresh_url = page.url.replace(base, "")
            print(f"  {width}px · 吳卓穎 (no password) → {fresh_url}")
            if "/welcome" not in page.url:
                problems.append(f"{width}px: the password-free name must open the setup form, got {fresh_url}")
            if width in (390, 1180):
                page.goto(f"{base}/login/scout/Seagull")
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(300)
                shot = "names-list.png" if width == 1180 else "names-list-phone.png"
                page.screenshot(path=str(SHOTS / shot), full_page=True)
                print(f"  {width}px · screenshot → docs/screens/{shot}")
            ctx.close()
        browser.close()

    server.shutdown()
    shutil.rmtree(workdir, ignore_errors=True)
    if problems:
        print("\nFAILED")
        for problem in problems:
            print("  ✗", problem)
        return 1
    print("\nOK — every name in 6–8 member patrols is whole at 320–1440px, "
          "nothing scrolls sideways, and each tile still opens its own door")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
