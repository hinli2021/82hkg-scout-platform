#!/usr/bin/env python3
"""Play 迷霧渡口 (game 2) in a real browser and prove the whole crossing works.

    LD_LIBRARY_PATH=/tmp/syslibs python3 tools/checks/check_bridge.py [base_url]

Walks the scout through the three stages — 銘言, 誓詞, 規律: reads each teaching
card, lays one plank out of order first (the recap must come back, not the
answer), then builds the whole span. The crossing is only the first half of
game 2: the card that greets the scout sends them to the leader for the 考核
(recite, and explain how the Law is lived) and waits there — no code is typed
any more. The check proves the crossing alone ticks nothing, that the map moves
on to area 3 anyway, and that the leader pressing 批准 in the leader account
turns the waiting card into the tick — with the badge counter, the pill and the
map all following.
Screenshots land in docs/screens/.
"""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from demo_reset import blank_game    # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5001'
ROOT = pathlib.Path(__file__).resolve().parents[2]
SHOTS = ROOT / 'docs' / 'screens'
RIVER = json.loads((ROOT / 'content' / 'member-badge' / 'river.json').read_text(encoding='utf-8'))
problems = []


def id_of(code, name='tasks.json'):
    for row in json.loads((ROOT / 'data' / 'db' / name).read_text(encoding='utf-8')):
        if row.get('code') == code:
            return row['id']
    raise SystemExit(f'{code} not found')


BRIDGE_ID = id_of('M05')
BADGE_ID = id_of('SC-01', 'badges.json')
BRIDGE_URL = f'{BASE}/tasks/{BRIDGE_ID}/bridge'


PUNCTUATION = '，。；、！？「」（）——'


def core(text):
    """The words alone: the cards keep their punctuation, the boards do not."""
    return ''.join(ch for ch in str(text) if ch not in PUNCTUATION and not ch.isspace())


def check(condition, message):
    print(('  ok   ' if condition else '  FAIL ') + message)
    if not condition:
        problems.append(message)


def scene(page):
    return page.get_attribute('[data-bridge]', 'data-bridge-scene')


def wait_scene(page, name, timeout=8000):
    page.wait_for_selector(f'[data-bridge][data-bridge-scene="{name}"]', timeout=timeout)


def click(page, selector):
    page.wait_for_selector(selector)
    page.click(selector)


def shoot(page, name):
    """Let the card's entrance animation finish before the shutter."""
    page.wait_for_timeout(520)
    page.screenshot(path=str(SHOTS / name), full_page=True)


def play(page):
    page.goto(BRIDGE_URL)
    page.wait_for_load_state('networkidle')
    SHOTS.mkdir(parents=True, exist_ok=True)
    check(scene(page) == 'intro', 'the game opens on the river bank')
    body = page.inner_text('[data-bridge]')
    check('迷霧渡口' in body, 'the crossing names itself')
    shoot(page, 'bridge-intro.png')

    for index, stage in enumerate(RIVER['stages']):
        if index == 0:
            click(page, '[data-bridge-go="teach"]')
        wait_scene(page, 'teach')
        card = page.inner_text('[data-bridge-card]')
        check(stage['teach']['title_zh'] in card,
              f'stage {index + 1}: the teaching card comes before the planks')
        check('原文' in card or 'word for word' in card.lower(),
              f'stage {index + 1}: the card says it is the wording itself, not a summary')
        # the description gives the normal sentence, not a trail of pieces
        check(all(core(sentence) in core(card)
                  for sentence in stage['teach']['sentences_zh']),
              f'stage {index + 1}: the card reads out whole sentences '
              f'("{stage["teach"]["sentences_zh"][0]}")')
        # 「原文」：一行一句，字字與官方措辭相同（連標點），不是解釋
        said = page.evaluate("""() => [...document.querySelectorAll('[data-bridge-card] .bridge-said .bridge-goal-line')]
            .map(line => line.textContent.trim())""")
        check(said == stage['teach']['sentences_zh'],
              f'stage {index + 1}: the card lists the exact wording, '
              f'{len(stage["teach"]["sentences_zh"])} line(s) — {said[:1]}')
        notes = page.evaluate("""() => [...document.querySelectorAll('[data-bridge-card] .bridge-said-note')]
            .map(note => note.textContent.trim())""")
        check(notes == stage['teach']['details_zh'],
              f'stage {index + 1}: every sentence keeps its detail underneath '
              f'({len(notes)} note(s) — "{notes[0][:18]}…" )')
        check('points_zh' not in stage['teach'],
              f'stage {index + 1}: the card keeps one shape — wording, then detail')
        check('→' not in card,
              f'stage {index + 1}: nothing in the card is cut into arrows')
        if index == 0:
            shoot(page, 'bridge-teach.png')
        elif index == 2:
            shoot(page, 'bridge-teach-law.png')   # the longest wording: seven points

        click(page, '[data-bridge-go="build"]')
        wait_scene(page, 'build')
        slots = page.query_selector_all('.bridge-rail .bridge-slot')
        planks = page.query_selector_all('[data-bridge-plank]')
        check(len(slots) == len(stage['planks']),
              f'stage {index + 1}: {len(stage["planks"])} boards make the span')
        check(len(planks) == len(stage['planks']),
              f'stage {index + 1}: every board is on the bank to pick up')

        # the empty boxes stand in rows, one row to a sentence
        rows = page.evaluate("""() => [...document.querySelectorAll('.bridge-rail .bridge-line')]
            .map(row => ({
                label: (row.querySelector('.bridge-line-label') || {}).textContent || '',
                slots: row.querySelectorAll('.bridge-slot').length,
            }))""")
        wanted = []
        for plank in stage['planks']:
            if not wanted or wanted[-1]['line'] != plank['line']:
                wanted.append({'line': plank['line'], 'slots': 1})
            else:
                wanted[-1]['slots'] += 1
        check([row['slots'] for row in rows] == [row['slots'] for row in wanted],
              f'stage {index + 1}: the boxes stand in {len(wanted)} rows, one to a sentence '
              f'({", ".join(str(row["slots"]) for row in wanted)})')
        check([row['label'] for row in rows] == stage['rows_zh'],
              f'stage {index + 1}: each row is named ({", ".join(stage["rows_zh"])})')
        # 鋪木板不再重覆次序：次序要在教學牌學，這裡不可以再寫出來。
        # 判定標準是「有沒有把那句原文一行一句地列出來」（.bridge-goal-line），
        # 而不是文字本身 —— 河岸上的木板本來就是那一句的字（準、備、Be Prepared）。
        panel = page.inner_text('[data-bridge-card]')
        check(page.query_selector('.bridge-goal') is None,
              f'stage {index + 1}: the build screen shows no order box')
        lines_shown = page.evaluate("""() => document.querySelectorAll('[data-bridge-card] .bridge-goal-line').length""")
        check(lines_shown == 0,
              f'stage {index + 1}: the build screen lists no sentence of the wording '
              f'(found {lines_shown})')
        check('橋上的次序' not in panel and 'The order on the bridge' not in panel,
              f'stage {index + 1}: the order heading is gone')
        # 教學牌本身仍然要一行一句（學習的地方）
        page.click('[data-bridge-go="teach"]')
        wait_scene(page, 'teach')
        back = page.evaluate("""() => [...document.querySelectorAll('[data-bridge-card] .bridge-goal-line')]
            .map(line => line.textContent.trim())""")
        check(back == stage['teach']['sentences_zh'],
              f'stage {index + 1}: the teaching card still gives the wording, one line each')
        click(page, '[data-bridge-go="build"]')
        wait_scene(page, 'build')
        check(page.query_selector('[data-bridge-go="teach"]') is not None,
              f'stage {index + 1}: a way back to the teaching card is offered')

        # one board out of order: the recap, never the answer
        keys = [plank['key'] for plank in stage['planks']]
        wrong = next((key for key in keys[1:]), None)
        if index == 2:
            # the law's pieces all start with the same word: a 童軍 laid where a
            # 童軍 is not wanted must still be refused
            head = stage['planks'][0]['zh']
            tail_key = next(plank['key'] for plank in stage['planks'] if plank['zh'] != head)
            page.click(f'[data-bridge-plank="{tail_key}"]')
            wait_scene(page, 'wrong')
            check(head in page.inner_text('[data-bridge-card]'),
                  'the recap names the word the board is waiting for')
            click(page, '[data-bridge-go="retry"]')
            wait_scene(page, 'build')
        if wrong:
            page.click(f'[data-bridge-plank="{wrong}"]')
            wait_scene(page, 'wrong')
            text = page.inner_text('[data-bridge-card]')
            check(stage['teach']['title_zh'] in text,
                  f'stage {index + 1}: a board laid early sends the scout back to the card')
            check(core(stage['teach']['sentences_zh'][0]) in core(text),
                  f'stage {index + 1}: the recap repeats the sentence to hold in mind')
            if index == 0:
                shoot(page, 'bridge-wrong.png')
            click(page, '[data-bridge-go="retry"]')
            wait_scene(page, 'build')

        # Lay the span, taking whichever copy of the right word is on the bank.
        # A stage may hold planks that read the same (all seven law points begin
        # 童軍): the board must accept any copy, and the server must file the
        # crossing even though the keys then arrive in a different order.
        labels = [plank['zh'] for plank in stage['planks']]
        duplicates = len(set(labels)) < len(labels)
        # the bank before a board moves — the stage that repeats words is the shot
        # worth keeping, and each stage keeps its own file
        shoot(page, {1: 'bridge-bank.png',
                     2: 'bridge-promise-bank.png',
                     3: 'bridge-law-bank.png'}[index + 1])
        swapped = 0
        for expected in stage['planks']:
            copies = page.evaluate("""(want) => {
                return [...document.querySelectorAll('[data-bridge-plank]')]
                    .map(b => ({key: b.getAttribute('data-bridge-plank'),
                                text: b.textContent.trim()}))
                    .filter(row => row.text === want).map(row => row.key);
            }""", expected['zh'])
            check(bool(copies), f'stage {index + 1}: "{expected["zh"]}" is on the bank')
            other = [key for key in copies if key != expected['key']]
            take = other[0] if other else copies[0]
            if take != expected['key']:
                swapped += 1
            page.click(f'[data-bridge-plank="{take}"]')
        wait_scene(page, 'built')
        check(True, f'stage {index + 1}: the span is built in order')
        if duplicates:
            check(swapped > 0,
                  f'stage {index + 1}: {swapped} of {len(stage["planks"])} boards were a '
                  f'different copy of the same word — the span still holds')
        if index == 0:
            shoot(page, 'bridge-built.png')
        elif index == 1:
            shoot(page, 'bridge-promise-built.png')
        else:
            shoot(page, 'bridge-law.png')
        click(page, '[data-bridge-go="finish"]' if index + 1 == len(RIVER['stages'])
              else '[data-bridge-go="next"]')

    # the server files the crossing in a blink, so the walking-across scene is
    # brief; the assess card is what the scout is left holding
    wait_scene(page, 'result')
    card = page.inner_text('[data-bridge-card]')
    check('過了橋' in card or '對岸' in card,
          'the far bank is reached once all three spans hold')
    check('等領袖批准' in card, 'the far bank sends the scout to the leader')
    check('背誦' in card and '講解' in card,
          'the check is named: recite, and explain how the Law is lived')
    check(page.query_selector('[data-bridge-wait]') is not None
          and page.query_selector('[data-bridge-code-input]') is None,
          'the card waits for the approval — there is no code to type')
    check(page.query_selector('[data-bridge-go="check"]') is not None,
          'and it offers 「重新檢查」 while the leader decides')
    check(page.query_selector('[data-bridge-link="badge"]') is not None,
          'the assess card shows the way back to the badge')
    shoot(page, 'bridge-assess.png')


def crossed_state(page, before):
    """The crossing is on file, but item 5 is not done until the leader approves."""
    entry = progress(page)
    check(entry['progress_done'] == before['progress_done'],
          f"the crossing alone does not tick a game ({before['progress_done']}"
          f" → {entry['progress_done']} of {entry['progress_total']})")
    rows = [t for t in entry['tasks'] if t['code'] == 'M05']
    check(bool(rows) and rows[0]['status'] == 'crossed',
          'item 5 is recorded as crossed, waiting on the leader')

    page.goto(f'{BASE}/badges/{BADGE_ID}')
    page.wait_for_load_state('networkidle')
    area2 = page.inner_text('.stage-chip[data-stage="2"]')
    check('已提交 · 等領袖批准' in area2, 'the map reads the waiting state on area 2')
    check(page.locator('.stage-chip[data-stage="2"] .stage-chip-replay[data-code]').count() == 1,
          'the map still offers a door into area 2 while it waits')

    page.goto(f'{BASE}/badges/{BADGE_ID}/requirements')
    page.wait_for_load_state('networkidle')
    check('等領袖批准' in page.inner_text('body'),
          'the requirements page says the item waits on the leader')
    check(page.query_selector(f'form[action*="/tasks/{BRIDGE_ID}/bridge-code"]') is None,
          'and holds no code form any more')

    # a crossed scout who re-opens the game lands on the assess card, not the bank
    page.goto(BRIDGE_URL)
    page.wait_for_load_state('networkidle')
    check(scene(page) == 'result', 're-entry opens straight onto the assess card')
    check(page.query_selector('[data-bridge-wait]') is not None,
          'no planks need re-laying to reach the waiting card')


def leader_approves(page, browser):
    """The last step of game 2: the leader presses 批准 in the leader account.

    The scout waits on the assess card; the same record stands in the leader's
    review queue (marked 已完成遊戲 · 等考核); one press and 「重新檢查」 finds
    the tick. Nothing is typed anywhere.
    """
    lctx = browser.new_context(locale='zh-HK', viewport={'width': 1180, 'height': 940})
    lctx.request.post(f'{BASE}/login/leader', form={'password': '0082'})
    lp = lctx.new_page()
    lp.goto(f'{BASE}/leader/review')
    lp.wait_for_load_state('networkidle')
    card = lp.locator('.review-card', has_text='已完成遊戲 · 等考核').first
    check(card.count() == 1, 'the finished crossing stands in the leader queue')
    check('背誦' in card.inner_text() and '變成 ✓' in card.inner_text(),
          'the queue card says what to check and what the press does')
    shoot(lp, 'leader-queue-bridge.png')
    card.locator('button[value="approve"]').click()
    lp.wait_for_timeout(1200)
    check(lp.locator('.review-card', has_text='已完成遊戲 · 等考核').count() == 0,
          'the approval clears the card out of the queue')
    lctx.close()

    page.click('[data-bridge-go="check"]')
    page.wait_for_function(
        "() => { var c = document.querySelector('[data-bridge-card]');"
        "        return c && c.innerText.indexOf('第 5 項完成') >= 0; }")
    card_text = page.inner_text('[data-bridge-card]')
    check('領袖批准了' in card_text and '第 5 項完成' in card_text,
          'the waiting card turns into the tick once the leader approves')
    check(page.query_selector('[data-bridge-link="badge"]') is not None,
          'the win shows the way back to the badge')
    shoot(page, 'bridge-result.png')


def verify_english(page):
    """The same waiting card in English: both halves of the 考核, no code box."""
    page.goto(f'{BASE}/set-language/en?next=/tasks/{BRIDGE_ID}/bridge')
    page.wait_for_load_state('networkidle')
    card = page.inner_text('[data-bridge-card]')
    check('Sent' in card and 'waiting for your leader' in card,
          'the crossed game opens on the English waiting card')
    check('Recite' in card and 'Explain' in card,
          'the English card names both halves of the check')
    check(page.query_selector('[data-bridge-code-input]') is None,
          'and offers no code box in English either')
    shoot(page, 'bridge-assess-en.png')
    page.goto(f'{BASE}/set-language/zh?next=/tasks/{BRIDGE_ID}/bridge')
    page.wait_for_load_state('networkidle')
    check(scene(page) == 'result', 'back in Chinese, the waiting card is still there')


def progress(page):
    data = page.evaluate("""async () => {
        const r = await fetch('/api/me/progress', {credentials: 'same-origin'});
        return await r.json();
    }""")
    return next(b for b in data['badges'] if b['id'] == BADGE_ID)


def verify_records(page, before):
    entry = progress(page)
    check(entry['progress_done'] == before['progress_done'] + 1,
          f"the crossing adds exactly one finished game ({before['progress_done']}"
          f" → {entry['progress_done']} of {entry['progress_total']})")
    rows = [t for t in entry['tasks'] if t['code'] == 'M05']
    check(bool(rows) and rows[0]['status'] == 'completed',
          'item 5 is marked completed by the game itself')

    page.goto(f'{BASE}/badges/{BADGE_ID}')
    page.wait_for_load_state('networkidle')
    body = page.inner_text('main')
    check(f"{entry['progress_done']} / 5" in body,
          'the badge page counts the crossing too')
    area2 = page.inner_text('.stage-chip[data-stage="2"]')
    check('已完成' in area2, 'area 2 reads as cleared on the map')


def begin_again(page):
    """From wherever the game opens, stand on the first teaching card.

    An approved item opens on its tick, so 「再走一次渡口」 comes first; a
    fresh one opens on the river bank, so its own button does the same job.
    """
    page.goto(BRIDGE_URL)
    if page.query_selector('[data-bridge-go="restart"]') is not None:
        click(page, '[data-bridge-go="restart"]')     # the tick → stage 1's card
    else:
        click(page, '[data-bridge-go="teach"]')       # the bank → stage 1's card


def verify_leaving(page):
    """Leaving an unfinished crossing asks first and restarts at stage 1."""
    begin_again(page)
    click(page, '[data-bridge-go="build"]')
    wait_scene(page, 'build')
    page.click(f'.cave-hud-link[href$="/badges/{BADGE_ID}"]')
    page.wait_for_selector('[data-bridge-leave]', state='visible')
    check(True, 'leaving the unfinished crossing warns first')
    shoot(page, 'bridge-leave.png')
    page.click('[data-bridge-leave]')
    page.wait_for_load_state('networkidle')
    begin_again(page)
    wait_scene(page, 'teach')
    check(RIVER['stages'][0]['teach']['title_zh'] in page.inner_text('[data-bridge-card]'),
          're-entering starts again from the first stage')


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(locale='zh-HK', viewport={'width': 1180, 'height': 940})
        page = ctx.new_page()
        errors = []
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        ctx.request.post(f'{BASE}/login/demo/demo2')
        page.goto(f'{BASE}/home')          # any page of the platform can read the API
        # a crashed earlier run must not skew the "this crossing added one game" count
        blank_game('scout03', {'M05'})
        before = progress(page)
        play(page)                      # the crossing → the assess card
        crossed_state(page, before)     # nothing ticked; the map and form in place
        verify_english(page)            # the same two halves in English
        leader_approves(page, browser)  # the leader's press clears item 5
        verify_records(page, before)    # only now does the game count
        verify_leaving(page)
        # leave the demo account as we found it: this walker wrote a real result
        print(f'tidied: {blank_game("scout03", {"M05"})} record(s) removed from demo2')
        for text in errors:
            if 'status of 400 (BAD REQUEST)' in text:
                continue   # the wrong-code refusals are the point of this walk
            problems.append(f'console error: {text}')
        ctx.close()
        browser.close()

    print(f'\nproblems: {len(problems)}')
    for item in problems:
        print(' -', item)
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
