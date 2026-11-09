#!/usr/bin/env python3
"""Prove a wrong board costs only its line — and that the boards are big enough.

    python3 tools/checks/check_bridge_row.py [base_url]

Game 2 (迷霧渡口) used to send the scout back to the start of the whole stage on
one wrong board. Now the rows already pinned stay on the bridge and only the
line being laid comes up again. This walks stage 1: lays its first line, puts a
board from a later line down out of turn, then checks that
  · the recap explains only this line is taken up,
  · the first line is still on the bridge afterwards,
  · the bank holds exactly the boards that are still to be laid,
  · every board on the bank is a comfortable tapping size.
"""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5001'
RIVER = json.loads((ROOT / 'content' / 'member-badge' / 'river.json').read_text(encoding='utf-8'))
TASKS = json.loads((ROOT / 'data' / 'db' / 'tasks.json').read_text(encoding='utf-8'))
BRIDGE_ID = next(row['id'] for row in TASKS if row.get('code') == 'M05')
URL = f'{BASE}/tasks/{BRIDGE_ID}/bridge'

problems = []


def check(ok, message):
    print(('  ok   ' if ok else '  FAIL ') + message)
    if not ok:
        problems.append(message)


def scene(page):
    return page.get_attribute('[data-bridge]', 'data-bridge-scene')


def main():
    # stage 1 (銘言) is only three boards, so walk through it and test on stage 2
    # (誓詞) — four lines, which is where a row-scoped reset actually shows.
    opener = RIVER['stages'][0]
    stage = RIVER['stages'][1]
    planks = stage['planks']
    first_line = planks[0]['line']
    line_one = [p for p in planks if p['line'] == first_line]

    with sync_playwright() as play:
        browser = play.chromium.launch()
        ctx = browser.new_context(viewport={'width': 430, 'height': 900})
        ctx.request.post(f'{BASE}/login/demo/demo3')
        page = ctx.new_page()
        page.goto(f'{BASE}/welcome')
        ctx.request.post(f'{BASE}/welcome', data={'password': 'tiger777',
                                                  'confirm': 'tiger777',
                                                  'email': 'scout07@example.com'})
        page.goto(URL)
        page.wait_for_load_state('networkidle')
        check(scene(page) == 'intro', 'the game opens on the river bank')

        page.click('[data-bridge-go="teach"]')
        page.wait_for_selector('[data-bridge][data-bridge-scene="teach"]')
        page.click('[data-bridge-go="build"]')
        page.wait_for_selector('[data-bridge][data-bridge-scene="build"]')
        for plank in opener['planks']:                 # clear stage 1
            page.click(f'[data-bridge-plank="{plank["key"]}"]')
        page.wait_for_selector('[data-bridge][data-bridge-scene="built"]')
        page.click('[data-bridge-go="next"]')
        page.wait_for_selector('[data-bridge][data-bridge-scene="teach"]')
        page.click('[data-bridge-go="build"]')
        page.wait_for_selector('[data-bridge][data-bridge-scene="build"]')

        # boards on the bank must be easy to hit
        boxes = page.evaluate("""() => [...document.querySelectorAll('[data-bridge-plank]')]
            .map(b => { const r = b.getBoundingClientRect();
                        return {h: Math.round(r.height), w: Math.round(r.width)}; })""")
        smallest = min(min(b['h'], b['w']) for b in boxes)
        check(smallest >= 44, f'every board is at least 44 px in both directions '
                              f'(smallest side {smallest} px, {len(boxes)} boards)')

        # lay the first line exactly as the stage wants it
        for plank in line_one:
            page.click(f'[data-bridge-plank="{plank["key"]}"]')
        laid = page.evaluate("() => document.querySelectorAll('.bridge-slot.is-laid').length")
        check(laid == len(line_one), f'the first line is on the bridge ({laid} boards)')

        # now a board that is not the one the bridge is waiting for
        wanted = planks[len(line_one)]
        wrong = next(p for p in planks
                     if p['line'] != first_line and p['zh'] != wanted['zh'])
        page.click(f'[data-bridge-plank="{wrong["key"]}"]')
        page.wait_for_selector('[data-bridge][data-bridge-scene="wrong"]', timeout=6000)
        text = page.inner_text('[data-bridge-card]')
        check('這一行要重排' in text, 'the recap says only this line comes up again')
        check(f'{len(line_one)}' in text, 'the recap counts the boards left on the bridge')

        page.click('[data-bridge-go="retry"]')
        page.wait_for_selector('[data-bridge][data-bridge-scene="build"]')
        kept = page.evaluate("""() => [...document.querySelectorAll('.bridge-slot.is-laid')]
            .map(s => s.querySelector('.bridge-board').textContent.trim())""")
        check(kept == [p['zh'] for p in line_one],
              f'the finished line stayed put ({len(kept)} boards, {kept})')
        bank = page.evaluate("""() => [...document.querySelectorAll('[data-bridge-plank]')]
            .map(b => b.getAttribute('data-bridge-plank'))""")
        check(len(bank) == len(planks) - len(line_one),
              f'the bank holds only the boards still to be laid ({len(bank)})')
        check(wrong['key'] in bank, 'the mislaid board is back on the bank')

        page.screenshot(path=str(ROOT / 'docs' / 'screens' / 'bridge-row-reset.png'),
                        full_page=True)
        browser.close()

    print('\n' + ('all checks passed' if not problems else f'{len(problems)} problem(s)'))
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
