"""Browser check: leaving the cave warns, cancel keeps answers, re-entry restarts.

    LD_LIBRARY_PATH=/tmp/syslibs python3 tools/checks/check_exit.py [base_url]

Tests the live bilingual site and the self-contained offline file. Does not
submit answers or modify a scout's progress.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

LIBS = subprocess.run("find /tmp/syslibs -name '*.so*' -printf '%h\\n' | sort -u | tr '\\n' ':'",
                      shell=True, capture_output=True, text=True).stdout
os.environ['LD_LIBRARY_PATH'] = LIBS + os.environ.get('LD_LIBRARY_PATH', '')
from playwright.sync_api import sync_playwright   # noqa: E402

from demo_reset import complete_setup                       # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5001'
CAVE_ID = next(row['id'] for row in json.loads((ROOT / 'data/db/tasks.json').read_text())
               if row.get('code') == 'M04')
BADGE_ID = next(row['id'] for row in json.loads((ROOT / 'data/db/badges.json').read_text())
                if row.get('code') == 'SC-01')


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        errors = []
        live = browser.new_context(viewport={'width': 1180, 'height': 880}, locale='zh-HK')
        live.request.post(f'{BASE}/login/demo/demo3')
        complete_setup(BASE, live)          # first-time scouts must set password + email
        page = live.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(f'{BASE}/tasks/{CAVE_ID}/cave')
        page.click('[data-cave-go="wall"]')
        page.click('[data-cave-go="question"]')
        config = json.loads(page.locator('#cave-root').get_attribute('data-cave-config'))
        first = config['groups'][0]['questions'][0]
        bad = next(option['key'] for option in first['options'] if not option['ok'])
        good = next(option['key'] for option in first['options'] if option['ok'])
        page.click(f'[data-cave-option="{bad}"]')
        assert page.locator('.cave-explain strong').inner_text() == '重溫壁畫的線索'
        assert page.locator('.cave-explain p').inner_text().strip(), 'the recap is readable'
        assert page.locator('.cave-picks, .cave-review-picks, .cave-pick-good').count() == 0
        assert page.evaluate('window.__caveState.passed') == 0
        page.click('[data-cave-go="question"]')
        assert page.locator('.cave-question').inner_text() == first['q_zh']
        page.click(f'[data-cave-option="{good}"]')
        page.click('[data-cave-go="next"]')
        assert page.evaluate('window.__caveState.passed') == 1
        assert not page.evaluate('(qid) => window.__caveState.first[qid].ok', first['id'])
        print('live: wrong turn → recap only → same question to retry')

        exits = (
            ('.cave-hud-link', 'cave HUD home'),
            ('.cave-hud-link >> nth=1', 'cave HUD membership'),
            ('.crumbs a', 'breadcrumb home'),
            ('.crumbs a >> nth=1', 'breadcrumb membership'),
            ('.tabbar a', 'site header home'),
        )
        for selector, name in exits:
            page.locator(selector).first.click()
            assert page.locator('.cave-exit-overlay').is_visible(), name
            assert '從頭開始' in page.locator('#cave-exit-message').inner_text()
            page.click('[data-cave-stay]')
            assert page.evaluate('window.__caveState.passed') == 1, name
            assert '/cave' in page.url, name
            print('live:', name, '→ cancel keeps question 1')

        page.locator('.cave-hud-link').last.click()
        page.click('[data-cave-leave]')
        page.wait_for_url(f'**/badges/{BADGE_ID}*')
        page.goto(f'{BASE}/tasks/{CAVE_ID}/cave')
        assert page.evaluate('window.__caveState.scene') == 'intro'
        assert page.evaluate('window.__caveState.passed') == 0
        print('live: confirmed membership exit → cave starts at entrance again')

        # 平台以中文為主，語言切換按鈕已移除：改用網址轉成英文。
        # 離開的警告本身仍然要翻譯（English text in the same dialog）。
        page.goto(f'{BASE}/set-language/en?next=/tasks/{CAVE_ID}/cave')
        page.wait_for_load_state('networkidle')
        assert page.locator('html').get_attribute('lang') == 'en'
        page.locator('.cave-hud-link').first.click()
        assert page.locator('.cave-exit-overlay').is_visible()
        assert 'start the game again' in page.locator('#cave-exit-message').inner_text()
        page.click('[data-cave-stay]')
        page.click('[data-cave-go="wall"]')
        page.click('[data-cave-go="question"]')
        english = json.loads(page.locator('#cave-root').get_attribute('data-cave-config'))
        en_question = english['groups'][0]['questions'][0]
        en_bad = next(option['key'] for option in en_question['options'] if not option['ok'])
        page.click(f'[data-cave-option="{en_bad}"]')
        assert page.locator('.cave-explain strong').inner_text() == 'Recap the clues from the wall'
        assert page.locator('.cave-explain p').inner_text().strip()
        assert page.locator('.cave-picks, .cave-review-picks, .cave-pick-good').count() == 0
        page.click('[data-cave-go="question"]')
        assert page.locator('.cave-question').inner_text() == en_question['q_en']
        # every game warns with the same centred dialog as the cave — no
        # game-specific strip of buttons pinned to the bottom of the page
        for code, route, stay in (('M04', 'cave', 'cave-stay'),
                                  ('M05', 'bridge', 'bridge-stay'),
                                  ('M06', 'drill', 'drill-stay')):
            game_id = next(row['id'] for row in
                           json.loads((ROOT / 'data/db/tasks.json').read_text())
                           if row.get('code') == code)
            game = live.new_page()
            game.on('pageerror', lambda error: errors.append(str(error)))
            game.goto(f'{BASE}/tasks/{game_id}/{route}')
            # the three games open on different first buttons; `.first` on a
            # combined selector would grab a hidden one from another game
            for selector in ('[data-cave-go="wall"]', '[data-bridge-go="teach"]',
                             '[data-drill-go="start"]'):
                start = game.locator(selector)
                if start.count() and start.first.is_visible():
                    start.first.click()
                    break
            game.wait_for_timeout(600)
            game.locator('.cave-hud-link, a[href="/home"]').first.click()
            game.wait_for_timeout(500)
            box = game.evaluate("""() => {
              const overlay = document.querySelector('.cave-exit-overlay');
              const dialog = overlay && overlay.querySelector('.cave-exit-dialog');
              if (!dialog) return null;
              const r = dialog.getBoundingClientRect();
              const style = getComputedStyle(overlay);
              return {position: style.position, zIndex: Number(style.zIndex),
                      cx: r.x + r.width / 2, cy: r.y + r.height / 2,
                      vw: innerWidth, vh: innerHeight,
                      actions: dialog.querySelectorAll('.cave-exit-actions button').length,
                      role: dialog.getAttribute('role'),
                      title: dialog.querySelector('h2').textContent.trim()};
            }""")
            assert box, f'{route}: the leave warning is not the shared centred dialog'
            assert box['position'] == 'fixed' and box['zIndex'] >= 1000, (route, box)
            assert abs(box['cx'] - box['vw'] / 2) <= 2 and abs(box['cy'] - box['vh'] / 2) <= 2, \
                f'{route}: the dialog is not centred ({box["cx"]:.0f},{box["cy"]:.0f} of {box["vw"]}x{box["vh"]})'
            assert box['actions'] == 2 and box['role'] == 'alertdialog', (route, box)
            assert box['title'], f'{route}: the dialog has no title'
            with_escape = game.locator('.cave-exit-overlay').is_visible()
            game.keyboard.press('Escape')
            game.wait_for_timeout(300)
            assert with_escape and game.locator('.cave-exit-overlay').is_hidden(), \
                f'{route}: Escape does not close the warning'
            assert f'/{route}' in game.url, f'{route}: cancelling should keep the scout in the game'
            game.locator('.cave-hud-link, a[href="/home"]').first.click()
            game.wait_for_timeout(400)
            game.click(f'[data-{stay}]')
            game.wait_for_timeout(400)
            game.close()
            print(f'live: {route} warns with the same centred dialog as the cave')

        live.close()
        print('live: English warning and recap-only retry confirmed')

        offline = browser.new_context(viewport={'width': 390, 'height': 844})
        file_page = offline.new_page()
        file_page.on('pageerror', lambda error: errors.append(str(error)))
        file_page.goto((ROOT / 'demo-preview.html').as_uri())
        file_page.click('[data-nav="leader-code"]')
        file_page.click('[data-demo="scout"]')
        file_page.click('#pane-home [data-nav="quest-intro"]')
        # the story replays first; leave it to reach the route's play button
        if file_page.locator('#pane-quest-intro [data-intro-skip]').count():
            file_page.click('#pane-quest-intro [data-intro-skip]')
            file_page.wait_for_timeout(400)
        file_page.click('#pane-quest-map [data-journey-play]')
        file_page.wait_for_timeout(400)
        file_page.click('#pane-cave [data-cave-go="wall"]')
        file_page.click('#pane-cave [data-cave-go="question"]')
        offline_config = json.loads(file_page.locator('#pane-cave #cave-root').get_attribute('data-cave-config'))
        offline_first = offline_config['groups'][0]['questions'][0]
        offline_bad = next(option['key'] for option in offline_first['options'] if not option['ok'])
        file_page.click(f'#pane-cave [data-cave-option="{offline_bad}"]')
        assert file_page.locator('#pane-cave .cave-explain strong').inner_text() == '重溫壁畫的線索'
        assert file_page.locator('#pane-cave .cave-explain p').inner_text().strip()
        assert file_page.locator('#pane-cave .cave-picks, #pane-cave .cave-pick-good').count() == 0
        file_page.click('#pane-cave [data-cave-go="question"]')
        assert file_page.locator('#pane-cave .cave-question').inner_text() == offline_first['q_zh']
        file_page.click('#pane-cave .cave-hud-link[data-nav="home"]')
        assert file_page.locator('.cave-exit-overlay:not([hidden])').count() == 1
        file_page.keyboard.press('Escape')
        assert file_page.locator('.cave-exit-overlay:not([hidden])').count() == 0
        assert file_page.evaluate('window.__caveState.scene') == 'question'
        file_page.click('#pane-cave .cave-hud-link[data-nav="quest-intro"]')
        file_page.click('[data-cave-leave]')
        assert file_page.locator('#pane-quest-map').is_visible(), \
            'a door after the replayed story opens on the route'
        file_page.evaluate("window.OFFLINE_DEMO.go('cave')")
        assert file_page.evaluate('window.__caveState.scene') == 'intro'
        file_page.keyboard.press('Escape')
        assert file_page.locator('.cave-exit-overlay:not([hidden])').count() == 1
        file_page.click('[data-cave-stay]')
        assert file_page.locator('#pane-cave').is_visible()
        file_page.keyboard.press('Escape')
        file_page.click('[data-cave-leave]')
        assert file_page.locator('#pane-quest-map').is_visible(), \
            'a door after the replayed story opens on the route'
        print('offline: mobile home, membership and Escape; cancel/re-entry confirmed')

        assert not errors, f'Browser errors: {errors}'
        browser.close()
        print('console errors: none')


if __name__ == '__main__':
    main()
