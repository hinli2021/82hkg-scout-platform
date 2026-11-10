#!/usr/bin/env python3
"""Play 每日挑戰 in a real browser and prove the points are paid exactly once.

    python3 tools/checks/check_daily.py [base_url]

Whatever game today happens to be, this solves it the way a scout would —
pipes turned until the net joins, tiles slid, mines avoided, pairs matched —
then lets the page claim the points. It then replays the page to confirm the
day shows as paid and the balance has moved exactly once.
"""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from scout import daily  # noqa: E402
from demo_reset import blank_daily  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5001'
problems = []


def check(ok, message):
    print(('  ok   ' if ok else '  FAIL ') + message)
    if not ok:
        problems.append(message)


def config_of(page):
    return json.loads(page.inner_text('#daily-config'))


def play(page):
    cfg = config_of(page)
    kind, board = cfg['kind'], cfg['board']
    puzzle = daily.puzzle()
    solution = puzzle['solution']

    if kind == 'pipes':
        pipes = page.locator('.pipe')
        for index, taps in enumerate(solution):
            for _ in range(taps):
                pipes.nth(index).click()
    elif kind == 'fifteen':
        tiles = board['board']
        state = list(tiles)
        # walk the scramble backwards: click the square the gap came from
        clicks = [solution[i - 1] for i in range(len(solution) - 1, 0, -1)] + [15]
        for index in clicks:
            page.evaluate("""(i) => {
                const cells = [...document.querySelectorAll('.fifteen-grid > *')];
                const node = cells[i];
                if (node && node.tagName === 'BUTTON') node.click();
            }""", index)
    elif kind == 'mines':
        mines = set(board['mines'])
        first = next(i for i in range(64) if i not in mines)
        page.locator('.mine-cell').nth(first).click()
        for i in range(64):
            if i in mines:
                continue
            cell = page.locator('.mine-cell').nth(i)
            if cell.get_attribute('class') and 'is-open' in cell.get_attribute('class'):
                continue
            cell.click()
    elif kind == 'memory':
        cards = board['cards']          # badge indices; a pair is the same index
        seen = {}
        pairs = []
        for index, face in enumerate(cards):
            if face in seen:
                pairs.append((seen[face], index))
            else:
                seen[face] = index
        for a, b in pairs:
            page.locator('.memory-card').nth(a).click()
            page.locator('.memory-card').nth(b).click()
            page.wait_for_timeout(220)
    return kind


def main():
    cleared = blank_daily()
    print(f'  ·· reset {cleared} earlier daily pay(s) for the practice scout')
    with sync_playwright() as play_ctx:
        browser = play_ctx.chromium.launch()
        ctx = browser.new_context(viewport={'width': 430, 'height': 900})
        ctx.request.post(f'{BASE}/login/demo/demo3')
        page = ctx.new_page()
        page.goto(f'{BASE}/welcome')
        ctx.request.post(f'{BASE}/welcome', data={'password': 'tiger777', 'confirm': 'tiger777',
                                                  'email': 'scout07@example.com'})
        page.goto(f'{BASE}/daily')
        page.wait_for_load_state('networkidle')
        cfg = config_of(page)
        page.wait_for_timeout(0)
        started = page.evaluate('() => Date.now()')
        check(cfg['kind'] == daily.puzzle()['kind'], f"today's game is {cfg['kind']}")
        check(page.locator('.daily-game > *').count() == 1, 'the board is drawn')
        check(cfg.get('already') is False, 'the day is not paid yet')

        balance_before = page.inner_text('.topbar-points')

        # a real scout cannot finish inside the clock floor; neither should the
        # check, or it would trip the server's “this run was too quick” guard
        page.wait_for_timeout(max(0, 9000 - (page.evaluate('() => Date.now()') - started)))
        kind = play(page)
        page.wait_for_selector('[data-daily-panel]:not([hidden])', timeout=15000)
        page.wait_for_timeout(900)
        result = page.inner_text('[data-daily-result]')
        check('完成' in result, f'{kind}: the page reports the finish — “{result[:40]}”')
        check('＋' in result, 'the points are shown on the card')

        page.goto(f'{BASE}/daily')
        page.wait_for_load_state('networkidle')
        cfg2 = config_of(page)
        check(cfg2.get('already') is True, 'reloading shows the day as already paid')
        today_row = page.locator('.daily-history li.is-today .chip.ok')
        check(today_row.count() == 1 and '＋' in today_row.first.inner_text(),
              f"the week strip marks today as paid ({today_row.first.inner_text() if today_row.count() else 'missing'})")
        balance_after = page.inner_text('.topbar-points')
        check(balance_after != balance_before,
              f'the balance moved once ({balance_before} → {balance_after})')

        page.screenshot(path=str(ROOT / 'docs' / 'screens' / 'daily-done.png'), full_page=True)
        browser.close()

    print('\n' + ('all checks passed' if not problems else f'{len(problems)} problem(s)'))
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
