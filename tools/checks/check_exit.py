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

        # Changing language also navigates; the warning itself must translate.
        page.locator('.lang-switch a').last.click()
        assert page.locator('.cave-exit-overlay').is_visible()
        page.click('[data-cave-leave]')
        page.wait_for_load_state('networkidle')
        assert page.locator('html').get_attribute('lang') == 'en'
        page.locator('.cave-hud-link').first.click()
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
        live.close()
        print('live: English warning and recap-only retry confirmed')

        offline = browser.new_context(viewport={'width': 390, 'height': 844})
        file_page = offline.new_page()
        file_page.on('pageerror', lambda error: errors.append(str(error)))
        file_page.goto((ROOT / 'demo-preview.html').as_uri())
        file_page.click('[data-nav="leader-code"]')
        file_page.click('[data-demo="scout"]')
        file_page.click('#pane-home [data-nav="quest-intro"]')
        file_page.click('#pane-quest-intro [data-journey-play]')
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
        assert file_page.locator('.cave-exit-overlay').is_visible()
        file_page.keyboard.press('Escape')
        assert not file_page.locator('.cave-exit-overlay').is_visible()
        assert file_page.evaluate('window.__caveState.scene') == 'question'
        file_page.click('#pane-cave .cave-hud-link[data-nav="quest-intro"]')
        file_page.click('[data-cave-leave]')
        assert file_page.locator('#pane-quest-intro').is_visible()
        file_page.evaluate("window.OFFLINE_DEMO.go('cave')")
        assert file_page.evaluate('window.__caveState.scene') == 'intro'
        file_page.keyboard.press('Escape')
        assert file_page.locator('.cave-exit-overlay').is_visible()
        file_page.click('[data-cave-stay]')
        assert file_page.locator('#pane-cave').is_visible()
        file_page.keyboard.press('Escape')
        file_page.click('[data-cave-leave]')
        assert file_page.locator('#pane-quest-intro').is_visible()
        print('offline: mobile home, membership and Escape; cancel/re-entry confirmed')

        assert not errors, f'Browser errors: {errors}'
        browser.close()
        print('console errors: none')


if __name__ == '__main__':
    main()
