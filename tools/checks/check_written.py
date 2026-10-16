#!/usr/bin/env python3
"""Walk every page in a real browser and prove the visible Chinese is 書面語.

    LD_LIBRARY_PATH=/tmp/syslibs python3 tools/checks/check_written.py [base_url]

Logs in with the demo shortcuts (scout / first-entry scout / leader), reads the
rendered text of every page, and prints any line that still carries Cantonese
markers.  Read-only: it never submits a form.
"""
import json
import pathlib
import re
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5001'
ROOT = pathlib.Path(__file__).resolve().parents[2]
MARK = re.compile(r'(嘅|唔|咗|喺|撳|啲|嗰|冇|哋|㗎|嘛|嚟|揀|掣|睇|佢|哩|囉|喇|咁|咩|咪|攞|俾|啱|傾|嘢|呀|啦|呢|添|邊個|邊度|幾時|點樣|點解|乜|咋|而家|依家|返(?!回)|入去|遲些)')


def scout_id(username):
    rows = json.loads((ROOT / 'data' / 'db' / 'users.json').read_text())
    for row in rows:
        if row.get('username') == username:
            return row['id'], row.get('patrol') or ''
    raise SystemExit(f'{username} not found')


def id_of(name, code):
    rows = json.loads((ROOT / 'data' / 'db' / name).read_text())
    for row in rows:
        if row.get('code') == code:
            return row['id']
    raise SystemExit(f'{code} not found')


BADGE, TASK = id_of('badges.json', 'SC-01'), id_of('tasks.json', 'M04')
BRIDGE = id_of('tasks.json', 'M05')


def walk(ctx, urls, label, bad):
    page = ctx.new_page()
    for url in urls:
        page.goto(BASE + url)
        page.wait_for_load_state('networkidle')
        for line in page.inner_text('body').splitlines():
            line = line.strip()
            if line and MARK.search(line):
                bad.append((label, url, line))
    page.close()


def main():
    bad = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        print('scout (demo2 → scout03):')
        ctx = browser.new_context(locale='zh-HK')
        ctx.request.post(f'{BASE}/login/demo/demo2')
        walk(ctx, ['/home', '/badges', f'/badges/{BADGE}?intro=1', f'/badges/{BADGE}',
                   f'/badges/{BADGE}/requirements', '/history', f'/tasks/{TASK}',
                   f'/tasks/{BRIDGE}/bridge'], 'scout', bad)
        ctx.close()

        print('first entry (demo3 → scout07):')
        ctx = browser.new_context(locale='zh-HK')
        ctx.request.post(f'{BASE}/login/demo/demo3')
        walk(ctx, ['/welcome', '/home'], 'first-entry', bad)
        ctx.close()

        print('leader (demo1):')
        ctx = browser.new_context(locale='zh-HK')
        ctx.request.post(f'{BASE}/login/demo/demo1')
        walk(ctx, ['/leader', '/leader/content', '/leader/review', '/leader/accounts',
                   '/leader/announcements', '/leader/settings', '/leader/audit',
                   '/leader/rewards'], 'leader', bad)
        ctx.close()

        print('names pages:')
        tiger_id, tiger_patrol = scout_id('scout01')
        ctx = browser.new_context(locale='zh-HK')
        walk(ctx, ['/login', '/login/scout/tiger', '/login/leader', '/forgot',
                   f'/login/scout/{tiger_patrol}/{tiger_id}',
                   f'/forgot/scout/{tiger_patrol}/{tiger_id}',
                   f'/forgot/scout/{tiger_patrol}/{tiger_id}/sent'], 'sign-in', bad)
        ctx.close()
        browser.close()

    print(f'\ncolloquial lines found: {len(bad)}')
    for label, url, line in bad:
        print(f'  [{label}] {url}: {line[:110]}')


if __name__ == '__main__':
    main()
