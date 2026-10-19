#!/usr/bin/env python3
"""Play section 1 of 步操訓練場 (game 3) in a real browser — the cliff face.

    DATA_DIR=<server data> LD_LIBRARY_PATH=/tmp/syslibs python3 tools/checks/check_drill.py [base_url]

Game 3 is played in two sections; this check walks section 1, the fall-in
hand signs on the cliff. The story opens the game: the way down collapsed,
and the rock face carries a row of ancient mechanisms carved with a scout
making the hand signs. Each stage opens on the flip cards — the stage's new
signs big and clear, tap one to turn it over and see the formation it calls
for — then the mechanism wakes: the rock shows a sign, a beat bar drains the
count (打數), and the formation must be pressed from the square buttons
below, inside the count, everything on the screen. A wrong press or a late
one opens the card again as the review (never the answer outright) and the
sign rejoins the queue. Two stages — 3 new signs first, then 4, with the
second stage's mechanism mixing all 7 — and both flights of steps are out:
section 1 is done, and nothing is filed
on the server yet (section 2, the drill commands, is coming; the studying
and the leader's code only enter once both sections are cleared).
Screenshots land in docs/screens/.
"""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from demo_reset import blank_slate, complete_setup      # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5001'
ROOT = pathlib.Path(__file__).resolve().parents[2]
SHOTS = ROOT / 'docs' / 'screens'
MANUAL = json.loads((ROOT / 'content' / 'member-badge' / 'drill.json').read_text(encoding='utf-8'))
STAGES = MANUAL['game']['sign_stages']
problems = []


def check(condition, message):
    print(('  ok   ' if condition else '  FAIL ') + message)
    if not condition:
        problems.append(message)


def scene(page):
    return page.get_attribute('[data-drill]', 'data-drill-scene')


def click(page, selector):
    page.wait_for_selector(selector)
    page.click(selector)


def shoot(page, name):
    page.wait_for_timeout(520)
    page.screenshot(path=str(SHOTS / name), full_page=True)


def progress(page):
    data = page.evaluate("""async () => {
        const r = await fetch('/api/me/progress', {credentials: 'same-origin'});
        return await r.json();
    }""")
    badge = next(b for b in data['badges'] if b.get('code') == 'SC-01')
    task = next(t for t in badge['tasks'] if t['code'] == 'M06')
    return badge, task


def answer_current(page):
    """Press the formation the carved sign on the rock is calling for.

    Reads only what the player can see — the framed leader statue — and matches
    it against the game's own config. Returns the sign's movement id.
    """
    page.wait_for_selector('[data-drill-beat]')
    page.wait_for_timeout(150)
    return page.evaluate("""() => {
        var root = document.querySelector('[data-drill]');
        var cfg = JSON.parse(root.getAttribute('data-drill-config'));
        var art = root.querySelector('.cave-picture .cave-art');
        var framed = art ? (art.getAttribute('data-drill-art') || '') : '';
        var moves = [];
        cfg.sections.forEach(function (s) { (s.moves || []).forEach(function (m) { moves.push(m); }); });
        var target = moves.find(function (m) { return (m.figure && m.figure === framed) || (m.img && m.img === framed); });
        if (!target) return 'NOT FOUND: ' + framed;
        var btn = root.querySelector('[data-drill-form="' + target.id + '"]');
        if (!btn) return 'NO BUTTON for ' + target.id;
        btn.click();
        return target.id;
    }""")


def clear_stage(page):
    """Answer every sign the stage calls, until the scene moves on.

    Returns (final scene, prompts answered, reviews met along the way).
    """
    prompts = reviews = 0
    guard = 0
    while True:
        guard += 1
        if guard > 40:
            raise SystemExit('the stage never ended — a sign is stuck in the queue')
        where = scene(page)
        if where == 'review':
            reviews += 1
            click(page, '[data-drill-go="resume"]')
            page.wait_for_timeout(250)
            continue
        if where != 'drill':
            return where, prompts, reviews
        answer_current(page)
        prompts += 1
        page.wait_for_timeout(1300)      # the ✓ flash, then the next sign


def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(locale='zh-HK', viewport={'width': 1180, 'height': 940})
        page = ctx.new_page()
        errors = []
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        ctx.request.post(f'{BASE}/login/demo/demo3')          # scout07: a blank slate
        complete_setup(BASE, ctx)                             # …and finish required setup
        page.goto(f'{BASE}/home')
        blank_slate()
        badge, task = progress(page)
        drill_url = f"{BASE}/tasks/{task['id']}/drill"
        before = badge['progress_done']
        total = badge['progress_total']

        # ── the story: the cliff, the mechanisms, the stairs
        page.goto(drill_url)
        page.wait_for_selector('[data-drill][data-drill-scene="intro"]')
        body = page.inner_text('[data-drill-card]')
        check('步操訓練場' in body, 'the drill ground names itself')
        check('斷崖' in body and '機關' in body,
              'the story tells of the cliff and its mechanisms')
        check('手號' in body and '隊形' in body,
              'the story says what section 1 is: hand signs and formations')
        check('翻開手號卡' in body, 'the way in is the flip cards')
        shoot(page, 'drill-intro.png')

        # ── stage 1: three flip cards, big and clear, tap to turn
        click(page, '[data-drill-go="start"]')
        page.wait_for_selector('[data-drill-scene="flip"]')
        cards = page.query_selector_all('[data-drill-flip]')
        check(len(cards) == len(STAGES[0]),
              f'stage 1 shows its {len(STAGES[0])} new signs as flip cards ({len(cards)})')
        check(page.locator('.drill.drill-flip-full').count() == 1,
              'the flip cards take the whole screen — no cliff above them')
        check(not page.locator('.cave-picture .cave-art').first.is_visible(),
              'the cliff painting steps aside on the flip page')
        check(page.locator('.cave-hud-link').first.is_visible(),
              'the 主頁 / 會員章 pills still float on top of the full screen')
        front_src = page.locator('[data-drill-flip] img').first.get_attribute('src')
        check('/signs/' in str(front_src),
              'the card front shows the drawn figure of the sign')
        first = page.locator('[data-drill-flip]').first
        first.click()
        page.wait_for_timeout(600)
        check('is-flipped' in (first.get_attribute('class') or ''),
              'tapping a card turns it over')
        back = first.inner_text()
        check('隊形' in back and '手號' in back,
              'the back names the formation and describes the sign')
        check('領袖位置' in back and '正前方中央' in back,
              'the back tells the scout where the leader stands')
        check(page.locator('[data-drill-flip] .drill-form-art.is-detailed').count() == len(STAGES[0]),
              'every card back carries the detailed formation diagram')
        check(page.locator('[data-drill-flip] .drill-form-leader').count() == len(STAGES[0]),
              'every detailed diagram marks the leader with the green triangle')
        icon_box = first.locator('.drill-form-art.is-detailed').bounding_box()
        check(bool(icon_box) and icon_box['width'] >= 100,
              f"the card-back formation icon is large ({round(icon_box['width']) if icon_box else 0}px wide)")
        check('綠色 ▼' in page.inner_text('[data-drill-card]'),
              'the flip page explains the green leader marker')
        shoot(page, 'drill-flip.png')
        for width, height, minimum in ((390, 700, 55), (1000, 550, 65)):
            page.set_viewport_size({'width': width, 'height': height})
            page.wait_for_timeout(300)
            compact = page.evaluate("""() => {
              const svg = document.querySelector('[data-drill-flip].is-flipped .drill-form-art.is-detailed');
              if (!svg) return null;
              const r = svg.getBoundingClientRect();
              return {width: r.width, height: r.height};
            }""")
            check(bool(compact and compact['width'] >= minimum
                       and abs(compact['width'] - compact['height']) <= 2),
                  f'the card-back diagram stays square in a {width}×{height} window')
        page.set_viewport_size({'width': 1180, 'height': 940})
        page.wait_for_timeout(300)
        first.click()                                        # …and back again
        page.wait_for_timeout(600)
        check('is-flipped' not in (first.get_attribute('class') or ''),
              'a second tap turns the card back to the sign')

        # ── the mechanism: a sign on the rock, the count running, the buttons
        click(page, '[data-drill-go="start-stage"]')
        page.wait_for_selector('[data-drill-scene="drill"]')
        prompt = page.inner_text('[data-drill-card]')
        check('隊形' in prompt, 'the mechanism asks for the formation')
        check('/signs/' in (page.get_attribute('.cave-picture .cave-art', 'data-drill-art') or ''),
              'the mechanism itself shows the leader statue making the sign')
        check(page.query_selector('[data-drill-beat]') is not None,
              'the count (打數) is running as a beat bar')
        buttons = page.query_selector_all('[data-drill-form]')
        check(len(buttons) == len(STAGES[0]),
              f'the formations stand as square buttons in a row ({len(buttons)})')
        check(page.locator('.drill-form-art').count() == len(STAGES[0]),
              'every button carries its little formation diagram')
        shoot(page, 'drill-prompt.png')

        # a short landscape window must still frame the WHOLE statue and the
        # answers — the portrait statue is not stretched to the full width
        page.set_viewport_size({'width': 1000, 'height': 550})
        page.wait_for_timeout(180)
        fit = page.evaluate("""() => {
            var art = document.querySelector('.cave-picture .cave-art');
            var forms = document.querySelector('[data-drill-forms]');
            var a = art.getBoundingClientRect(), f = forms.getBoundingClientRect();
            return {top: a.top, bottom: a.bottom, formsBottom: f.bottom, vh: innerHeight};
        }""")
        check(fit['top'] >= 0 and fit['bottom'] <= fit['vh'] and fit['formsBottom'] <= fit['vh'],
              'in a short window the whole statue and its buttons stay on screen')
        page.screenshot(path=str(SHOTS / 'drill-prompt-short.png'))
        page.set_viewport_size({'width': 1180, 'height': 940})
        page.wait_for_timeout(120)

        # the bar really drains
        page.wait_for_timeout(900)
        width = page.evaluate("() => document.querySelector('[data-drill-beat-fill]').style.width")
        check(width and width != '100%', f'the beat bar drains as the count runs ({width})')

        # ── a wrong press is reviewed, never answered — and re-queued
        framed = page.get_attribute('.cave-picture .cave-art', 'data-drill-art')
        right_id = next(m['id'] for s in MANUAL['sections'] for m in s['moves']
                        if m.get('figure') == framed or m.get('img') == framed)
        wrong_btn = next(b for b in buttons if b.get_attribute('data-drill-form') != right_id)
        wrong_btn.click()
        page.wait_for_selector('[data-drill-scene="review"]')
        review = page.inner_text('[data-drill-card]')
        check('不是這個隊形' in review, 'a wrong press is told it is wrong, in so many words')
        right_name = next(m['title_zh'] for s in MANUAL['sections'] for m in s['moves']
                          if m['id'] == right_id)
        check(right_name in review,
              f'the review re-teaches the pairing: this sign calls for「{right_name}」')
        check(page.locator('[data-drill-card] .drill-review-fig').count() == 1,
              'the review shows the sign figure beside the formation')
        shoot(page, 'drill-review.png')
        click(page, '[data-drill-go="resume"]')
        page.wait_for_selector('[data-drill-scene="drill"]')

        # ── a late press meets the same review
        page.wait_for_timeout(6500)
        if scene(page) == 'review':
            late = page.inner_text('[data-drill-card]')
            check('打數完了' in late, 'letting the count run out opens the review as well')
            click(page, '[data-drill-go="resume"]')
            page.wait_for_selector('[data-drill-scene="drill"]')
        else:
            check(False, 'the count ran out but no review opened')

        # ── stage 1 clears only when every sign is answered in time
        where, prompts, reviews = clear_stage(page)
        check(where == 'stage-done', 'stage 1 ends on its stairs card')
        done = page.inner_text('[data-drill-card]')
        check('第 1 段石階出現了' in done, 'the card says the first flight of steps is out')
        check(prompts >= len(STAGES[0]),
              f'every sign of the pool was called ({prompts} prompts, {reviews} reviews met)')

        # ── stage 2: four new cards, and the mechanism mixes all seven
        expected_pool = [len(STAGES[0])]
        for index in range(1, len(STAGES)):
            click(page, '[data-drill-go="next-stage"]')
            page.wait_for_selector('[data-drill-scene="flip"]')
            cards = page.query_selector_all('[data-drill-flip]')
            check(len(cards) == len(STAGES[index]),
                  f'stage {index + 1} shows its {len(STAGES[index])} new sign(s) ({len(cards)})')
            known = page.inner_text('[data-drill-card]')
            check('已學過' in known, f'stage {index + 1} lists the signs already learned')
            click(page, '[data-drill-go="start-stage"]')
            page.wait_for_selector('[data-drill-scene="drill"]')
            expected_pool.append(expected_pool[-1] + len(STAGES[index]))
            buttons = page.query_selector_all('[data-drill-form]')
            check(len(buttons) == expected_pool[-1],
                  f'stage {index + 1} answers from {expected_pool[-1]} formation buttons')
            where, prompts, reviews = clear_stage(page)
            check(where == 'stage-done', f'stage {index + 1} ends on its stairs card')
            check(prompts == expected_pool[-1],
                  f'stage {index + 1} calls every sign of the pool ({prompts} prompts)')
            check(reviews == 0, f'stage {index + 1} needed no reviews on this walk')

        # ── section 1 done: the steps are out, section 2 is named — nothing filed
        click(page, '[data-drill-go="section-done"]')
        page.wait_for_selector('[data-drill-scene="section-done"]')
        card = page.inner_text('[data-drill-card]')
        check('石階齊了' in card and '第 1 節完成' in card,
              'the section-done card says the steps are complete')
        check('第 2 節' in card and '即將開放' in card,
              'the card names section 2, the drill commands, as coming soon')
        check(page.query_selector('[data-drill-code-input]') is None,
              'no code box yet: the leader’s code only enters once both sections are cleared')
        check(page.query_selector('a[data-drill-link="badge"]') is not None,
              'the card shows the way back to the badge')
        shoot(page, 'drill-section-done.png')

        badge, task = progress(page)
        check(task['status'] == 'todo',
              'section 1 alone files nothing — item 6 still waits')
        check(badge['progress_done'] == before,
              f'the game counter has not moved ({before} → {badge["progress_done"]} of {total})')

        page.goto(f'{BASE}/badges/{badge["id"]}')
        page.wait_for_load_state('networkidle')
        area3 = page.inner_text('.stage-chip[data-stage="3"]')
        check('等你開始' in area3, 'area 3 on the map still reads as ready to play')

        # ── a finished scout re-opens on the section card, not the flip cards
        page.goto(drill_url)
        page.wait_for_selector('[data-drill][data-drill-scene="intro"]')
        click(page, '[data-drill-go="start"]')
        page.wait_for_selector('[data-drill-scene="section-done"]')
        check('石階齊了' in page.inner_text('[data-drill-card]'),
              're-entry lands straight back on the section-done card')

        for text in errors:
            problems.append(f'console error: {text}')
        ctx.close()
        browser.close()

    print(f'tidied: {blank_slate()} record(s) removed from demo3')
    print(f'\nproblems: {len(problems)}')
    for item in problems:
        print(' -', item)
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
