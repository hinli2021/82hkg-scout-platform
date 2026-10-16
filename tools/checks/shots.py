#!/usr/bin/env python3
"""Re-shoot the scout-facing screens straight from the live server.

    LD_LIBRARY_PATH=/tmp/syslibs python3 tools/checks/shots.py [base_url]

Writes docs/screens/written-*.png.  Nothing else is touched: it logs in with the
demo shortcuts, reads the pages, and closes the browser.
"""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5001'
OUT = pathlib.Path(__file__).resolve().parents[2] / 'docs' / 'screens'
OUT.mkdir(parents=True, exist_ok=True)
VIEW = {'width': 1280, 'height': 900}


def task_id(code):
    db = json.loads((pathlib.Path(__file__).resolve().parents[2] / 'data' / 'db' / 'tasks.json').read_text())
    for row in db:
        if row.get('code') == code:
            return row['id']
    raise SystemExit(f'task {code} not found')


def membership_badge_id():
    db = json.loads((pathlib.Path(__file__).resolve().parents[2] / 'data' / 'db' / 'badges.json').read_text())
    for row in db:
        if row.get('code') == 'SC-01' or row.get('title_en') == 'Membership Badge':
            return row['id']
    raise SystemExit('membership badge not found in data/db/badges.json')


def shoot(page, name, url, full=True, wait=900):
    page.goto(BASE + url)
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(wait)
    page.screenshot(path=str(OUT / name), full_page=full)
    print(f'  {name:34s} {url}')


def main():
    badge = membership_badge_id()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        errors = []

        # --- the scout (demo2 → scout03, the single 會員章 story and its map)
        ctx = browser.new_context(viewport=VIEW, locale='zh-HK')
        page = ctx.new_page()
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.on('pageerror', lambda e: errors.append(str(e)))
        ctx.request.post(f'{BASE}/login/demo/demo2')
        print('scout screens:')
        shoot(page, 'written-home.png', '/home')
        shoot(page, 'written-badges.png', '/badges')
        shoot(page, 'written-story.png', f'/badges/{badge}?intro=1')
        shoot(page, 'written-trail.png', f'/badges/{badge}')
        # Game 1's explanation is on location 1 itself; no radio selection.
        page.goto(f'{BASE}/badges/{badge}')
        page.wait_for_load_state('networkidle')
        row = page.locator('.stage-chip-first')
        row.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        row.screenshot(path=str(OUT / 'written-game-slot.png'))
        print(f'  {"written-game-slot.png":34s} the first map stop (叢林深處)')
        shoot(page, 'written-requirements.png', f'/badges/{badge}/requirements')
        shoot(page, 'written-history.png', '/history')
        # Item 4 opens the cave directly — there is no separate paper page.
        shoot(page, 'written-cave.png', f'/tasks/{task_id("M04")}/cave')
        # Item 5 is the crossing (game 2): the map stop and its opening card.
        page.goto(f'{BASE}/badges/{badge}')
        page.wait_for_load_state('networkidle')
        stop = page.locator('.stage-chip[data-stage="2"]')
        stop.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        stop.screenshot(path=str(OUT / 'written-bridge-slot.png'))
        print(f'  {"written-bridge-slot.png":34s} the second map stop (迷霧小徑)')
        shoot(page, 'written-bridge.png', f'/tasks/{task_id("M05")}/bridge')
        ctx.close()

        # --- a first-entry scout (demo3 → scout07, no password yet)
        ctx = browser.new_context(viewport=VIEW, locale='zh-HK')
        page = ctx.new_page()
        ctx.request.post(f'{BASE}/login/demo/demo3')
        print('first-entry screens:')
        shoot(page, 'written-welcome.png', '/welcome')
        shoot(page, 'written-firsthome.png', '/home')
        ctx.close()

        # --- the leader
        ctx = browser.new_context(viewport=VIEW, locale='zh-HK')
        page = ctx.new_page()
        ctx.request.post(f'{BASE}/login/demo/demo1')
        print('leader screens:')
        shoot(page, 'written-leader.png', '/leader')
        ctx.close()

        browser.close()
        print('console errors:', errors or 'none')


if __name__ == '__main__':
    main()
