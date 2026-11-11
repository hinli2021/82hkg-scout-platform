#!/usr/bin/env python3
"""Play both sections of 步操訓練場 (game 3) in a real browser.

    DATA_DIR=<server data> LD_LIBRARY_PATH=/tmp/syslibs python3 tools/checks/check_drill.py [base_url]

Section 1 is the cliff of fall-in hand signs: two flip-card stages, then the
statue mechanism inside a three-beat count. Section 2 is the parade ground
below: three movement stages — Alert / Stand at ease / Salute; four-direction
pacing plus left/right/about turns; and Mark time / Quick march / Halt /
Right dress. Each stage first teaches with movement cards (manual page,
command, count and key points), then the full-screen command board calls a
command and the scout presses the movement inside its count. Every stage's
call pool is cumulative within section 2 (3, then 10, then 14 calls); stage
2 and 3 show four shuffled choices, always including the called
movement. Wrong or
late answers reopen the teaching review and re-queue the movement. Clearing
both sections files the studying only; the leader's 82DR code completes
item 6. Screenshots land in docs/screens/.
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
MOVE_STAGES = MANUAL['game']['movement_stages']
MOVE_BY_ID = {m['id']: m for sec in MANUAL['sections'] for m in sec['moves']}
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


def current_move_id(page):
    """Read the visible prompt: a statue's sign or shown movement."""
    return page.evaluate("""() => {
        var root = document.querySelector('[data-drill]');
        var cfg = JSON.parse(root.getAttribute('data-drill-config'));
        var moves = [];
        cfg.sections.forEach(function (s) { (s.moves || []).forEach(function (m) { moves.push(m); }); });
        if (root.getAttribute('data-drill-section') === '2') {
            var promptNode = root.querySelector('[data-drill-prompt-move]');
            var shownId = promptNode ? promptNode.getAttribute('data-drill-prompt-move') : '';
            var shown = moves.find(function (m) { return m.id === shownId; });
            return shown ? shown.id : 'NOT FOUND PROMPT: ' + shownId;
        }
        var art = root.querySelector('.cave-picture .cave-art');
        var framed = art ? (art.getAttribute('data-drill-art') || '') : '';
        var target = moves.find(function (m) { return (m.figure && m.figure === framed) || (m.img && m.img === framed); });
        return target ? target.id : 'NOT FOUND: ' + framed;
    }""")


def choice_snapshot(page):
    """The visible answer order plus where the called movement sits in it."""
    target_id = current_move_id(page)
    ids = page.evaluate("""() => [...document.querySelectorAll('[data-drill-form]')]
        .map(button => button.getAttribute('data-drill-form'))""")
    return {'target': target_id, 'ids': ids,
            'position': ids.index(target_id) if target_id in ids else -1}


def answer_current(page):
    """Press the formation or movement the visible prompt is calling for."""
    page.wait_for_selector('[data-drill-beat]')
    # The previous card's start button can leave the pointer exactly on a new
    # answer's lower edge, making its hover lift oscillate; park it first.
    page.mouse.move(5, 5)
    page.wait_for_timeout(200)
    target_id = current_move_id(page)
    if target_id.startswith('NOT FOUND'):
        return target_id
    btn = page.locator(f'[data-drill-form="{target_id}"]')
    if btn.count() != 1:
        return f'NO BUTTON for {target_id}'
    btn.first.click()
    return target_id


def study_cards(page, expect, section=1):
    """Turn every study card of the open flip stage, in carousel order.

    The cards come one at a time now: the board holds a single card, the
    arrows walk it, and the stage's start button stays disabled until every
    card has been turned over. Returns the list of card ids in order.
    """
    seen = []
    total_attr = page.get_attribute('[data-drill-carousel]', 'data-drill-carousel')
    check(total_attr is not None and int(total_attr) == expect,
          f'the {section == 2 and "movement" or "sign"} stage opens a carousel of {expect} card(s) ({total_attr})')
    check(page.locator('[data-drill-flip]').count() == 1,
          'the carousel shows one study card at a time, not the whole set at once')
    for index in range(expect):
        board = page.locator('[data-drill-flip]')
        seen.append(board.get_attribute('data-drill-flip'))
        board.click()
        page.wait_for_timeout(560)
        check('is-flipped' in (board.get_attribute('class') or ''),
              f'card {index + 1} of {expect} turns over to its notes')
        if index < expect - 1:
            page.click('[data-drill-flip-go="next"]')
            page.wait_for_timeout(520)
    counter = page.inner_text('[data-drill-flip-count]')
    check(counter.strip() == f'{expect} / {expect}',
          f'the carousel counter ends at the last card ({counter.strip()})')
    gate = page.inner_text('[data-drill-flip-gate]')
    check('看過' in gate, f'the gate says every card has been read ({gate[:24]})')
    check(page.locator('[data-drill-go="start-stage"][disabled]').count() == 0,
          'the start button unlocks once every card is read')
    return seen


def clear_stage(page, choice_audit=None):
    """Answer every sign the stage calls, until the scene moves on.

    Returns (final scene, prompts answered, reviews met, movement ids).
    When ``choice_audit`` is a list, each prompt's visible answer order and
    correct-answer position are appended before the answer is pressed.
    """
    prompts = reviews = 0
    seen = []
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
            return where, prompts, reviews, seen
        if choice_audit is not None:
            page.wait_for_selector('[data-drill-beat]')
            page.wait_for_timeout(150)
            choice_audit.append(choice_snapshot(page))
        seen.append(answer_current(page))
        prompts += 1
        page.wait_for_timeout(1300)      # the ✓ flash, then the next sign


def answer_grid_fit(page):
    return page.evaluate("""() => {
        const wrap = document.querySelector('.cave-card-wrap');
        const card = document.querySelector('[data-drill-card]');
        const forms = document.querySelector('[data-drill-forms]');
        const layout = document.querySelector('.drill-move-prompt-layout');
        const buttons = [...forms.querySelectorAll('button')].map(b => b.getBoundingClientRect());
        const visual = document.querySelector('[data-drill-prompt-visual]');
        const a = visual ? visual.getBoundingClientRect() : null;
        const c = card.getBoundingClientRect(), l = layout.getBoundingClientRect();
        return {
          count: buttons.length, taggedCount: Number(forms.dataset.answerCount || 0),
          wrapClient: wrap.clientHeight, wrapScroll: wrap.scrollHeight,
          cardClient: card.clientHeight, cardScroll: card.scrollHeight,
          allVisible: buttons.every(r => r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth)
                      && a.top >= 0 && a.bottom <= innerHeight && a.left >= 0 && a.right <= innerWidth,
          minButton: Math.min(...buttons.map(r => Math.min(r.width, r.height))),
          promptWidth: a ? a.width : 0, promptHeight: a ? a.height : 0,
          bottomGap: c.bottom - l.bottom
        };
    }""")


def check_answer_grid(page, expected, minimum, label):
    page.wait_for_timeout(250)
    fit = answer_grid_fit(page)
    check(fit['count'] == expected and fit['taggedCount'] == expected and fit['allVisible']
          and fit['wrapScroll'] <= fit['wrapClient'] + 1 and fit['cardScroll'] <= fit['cardClient'] + 1
          and fit['minButton'] >= 38 and fit['bottomGap'] <= 42
          and fit['promptWidth'] >= minimum[0] and fit['promptHeight'] >= minimum[1],
          f'the large movement prompt and {expected} command answers fill {label} without scrolling; '
          f"prompt visual {round(fit['promptWidth'])}×{round(fit['promptHeight'])}px")
    return fit


def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(locale='zh-HK', viewport={'width': 1180, 'height': 940})
        page = ctx.new_page()
        errors = []
        expected_bad_code_errors = 0
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
        check('手號' in body and '隊形' in body and '第 2 節' in body and '口令' in body,
              'the story names section 1 hand signs and section 2 commands')
        check('翻開手號卡' in body, 'the way in is the flip cards')
        shoot(page, 'drill-intro.png')

        # ── stage 1: the carousel, one sign at a time, all of them read
        click(page, '[data-drill-go="start"]')
        page.wait_for_selector('[data-drill-scene="flip"]')
        check(page.locator('.drill.drill-flip-full').count() == 1,
              'the study cards take the whole screen — no cliff above them')
        check(not page.locator('.cave-picture .cave-art').first.is_visible(),
              'the cliff painting steps aside on the flip page')
        check(page.locator('.cave-hud-link').first.is_visible(),
              'the 主頁 / 會員章 pills still float on top of the full screen')
        check(page.locator('[data-drill-go="start-stage"][disabled]').count() == 1,
              'the mechanism stays locked until the cards are read')
        check('未翻開' in page.inner_text('[data-drill-flip-gate]'),
              'the gate names how many cards are still unopened')
        front_src = page.locator('[data-drill-flip] img').first.get_attribute('src')
        check('/signs/' in str(front_src),
              'the card front shows the drawn figure of the sign')
        card_box = page.locator('[data-drill-flip]').bounding_box()
        check(bool(card_box) and card_box['width'] >= 300 and card_box['height'] >= 400,
              f"the single card is large on a desktop ({round(card_box['width'])}×{round(card_box['height'])}px)")

        first = page.locator('[data-drill-flip]')
        first.click()
        page.wait_for_timeout(620)
        check('is-flipped' in (first.get_attribute('class') or ''),
              'tapping the card turns it over')
        back = first.inner_text()
        check('隊形' in back and '手號' in back,
              'the back names the formation and describes the sign')
        check('領袖位置' in back and '正前方中央' in back,
              'the back tells the scout where the leader stands')
        check(page.locator('[data-drill-flip] .drill-form-art.is-detailed').count() == 1,
              'the card back carries the detailed formation diagram')
        check(page.locator('[data-drill-flip] .drill-form-leader').count() == 1,
              'the detailed diagram marks the leader with the green triangle')
        icon_box = first.locator('.drill-form-art.is-detailed').bounding_box()
        check(bool(icon_box) and icon_box['width'] >= 100,
              f"the card-back formation icon is large ({round(icon_box['width']) if icon_box else 0}px wide)")
        check('未翻開' in page.inner_text('[data-drill-flip-gate]')
              and page.locator('[data-drill-go="start-stage"][disabled]').count() == 1,
              'one card read is not enough — the gate and the lock still hold')
        check('綠色 ▼' in page.inner_text('[data-drill-card]')
              or page.locator('.drill-leader-tri').count() >= 1,
              'the flip page explains the green leader marker')
        shoot(page, 'drill-flip.png')
        for width, height, minimum in ((390, 700, 130), (1000, 550, 90)):
            page.set_viewport_size({'width': width, 'height': height})
            page.wait_for_timeout(420)
            compact = page.evaluate("""() => {
              const svg = document.querySelector('[data-drill-flip].is-flipped .drill-form-art.is-detailed');
              const card = document.querySelector('[data-drill-flip]');
              if (!svg) return null;
              const r = svg.getBoundingClientRect(), c = card.getBoundingClientRect();
              return {width: r.width, height: r.height, cardWidth: c.width, cardHeight: c.height,
                      scroll: document.documentElement.scrollHeight - innerHeight};
            }""")
            check(bool(compact and compact['width'] >= minimum
                       and abs(compact['width'] - compact['height']) <= 2),
                  f'the card-back diagram stays square and large in a {width}×{height} window '
                  f'({round(compact["width"]) if compact else 0}px)')
            check(bool(compact) and compact['scroll'] <= 0,
                  f'the {width}×{height} study card fits without scrolling')
            if width == 390:
                page.screenshot(path=str(SHOTS / 'drill-flip-phone-back.png'), full_page=True)
        page.set_viewport_size({'width': 1180, 'height': 940})
        page.wait_for_timeout(320)

        # walk the rest of the carousel; every card must be read to unlock
        for index in range(1, len(STAGES[0])):
            page.click('[data-drill-flip-go="next"]')
            page.wait_for_timeout(520)
            card = page.locator('[data-drill-flip]')
            card.click()
            page.wait_for_timeout(560)
        counter = page.inner_text('[data-drill-flip-count]').strip()
        check(counter == f'{len(STAGES[0])} / {len(STAGES[0])}',
              f'the carousel walks every sign card ({counter})')
        check('看過' in page.inner_text('[data-drill-flip-gate]'),
              'the gate confirms every card has been read')
        check(page.locator('[data-drill-go="start-stage"][disabled]').count() == 0,
              'the start button unlocks only after the whole carousel is read')
        shoot(page, 'drill-flip-read.png')

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
        where, prompts, reviews, seen = clear_stage(page)
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
            practice = page.locator('[data-drill-flip]').count()
            check(practice == 1,
                  f'stage {index + 1} shows one sign card at a time ({practice})')
            total_attr = page.get_attribute('[data-drill-carousel]', 'data-drill-carousel')
            check(int(total_attr) == len(STAGES[index]),
                  f'stage {index + 1} carousel holds its {len(STAGES[index])} new sign(s) ({total_attr})')
            known = page.inner_text('[data-drill-card]')
            check('已學過' in known, f'stage {index + 1} lists the signs already learned')
            study_cards(page, len(STAGES[index]))
            click(page, '[data-drill-go="start-stage"]')
            page.wait_for_selector('[data-drill-scene="drill"]')
            expected_pool.append(expected_pool[-1] + len(STAGES[index]))
            buttons = page.query_selector_all('[data-drill-form]')
            check(len(buttons) == expected_pool[-1],
                  f'stage {index + 1} answers from {expected_pool[-1]} formation buttons')
            where, prompts, reviews, seen = clear_stage(page)
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
        check('第 2 節' in card and '步操動作' in card and '即將開放' not in card,
              'the card opens section 2, the drill movements, below the cliff')
        check(page.query_selector('[data-drill-go="section2"]') is not None,
              'the section-done card leads down to the parade ground')
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

        # ── section 2 · the parade ground: three cumulative movement stages
        click(page, '[data-drill-go="section2"]')
        page.wait_for_selector('[data-drill-scene="flip"]')
        expected_units = [3, 4, 4]          # pacing is one card with four calls
        expected_pools = []
        running = 0
        for stage_ids in MOVE_STAGES:
            running += len(stage_ids)
            expected_pools.append(running)
        expected_button_counts = [expected_pools[0], 4, 4]
        for index, fresh_ids in enumerate(MOVE_STAGES):
            if index:
                click(page, '[data-drill-go="next-stage"]')
                page.wait_for_selector('[data-drill-scene="flip"]')
            check(page.get_attribute('[data-drill]', 'data-drill-section') == '2',
                  f'section 2 stage {index + 1} opens on the parade ground')
            check(page.locator('[data-drill-flip]').count() == 1,
                  f'section 2 stage {index + 1} shows one study card at a time')
            total = int(page.get_attribute('[data-drill-carousel]', 'data-drill-carousel'))
            check(total == len(fresh_ids),
                  f'section 2 stage {index + 1} has {len(fresh_ids)} card(s) in its carousel ({total})')
            flip_text = page.inner_text('[data-drill-card]')
            check(f'第 {index + 1} 階段' in flip_text and '口令' in flip_text,
                  f'section 2 stage {index + 1} teaches commands before the mechanism')
            if index:
                check(page.locator('[data-drill-go="start-stage"][disabled]').count() == 1,
                      f'section 2 stage {index + 1} keeps the mechanism locked until the cards are read')
            if index:
                check('已學過的動作' in flip_text,
                      f'section 2 stage {index + 1} lists movements already learned')
            if index == 0:
                # the alert card is the first of three, each on its own turn
                check(page.get_attribute('[data-drill-flip]', 'data-drill-flip') == 'alert',
                      'section 2 stage 1 opens on the Alert card')
                check(page.locator('[data-drill-flip] .drill-move-front-command').count() == 1,
                      'section 2 stage 1 puts a command banner on the card front')
                check(page.locator('[data-drill-flip] .drill-flip-back.is-move .drill-move-art').count() == 0,
                      'the movement card back leads with the command, not a movement icon')
                alert = page.locator('[data-drill-flip="alert"]')
                anim = alert.locator('[data-drill-animation="alert"]')
                check(anim.count() == 1 and anim.locator('[data-drill-frame]').count() == 5,
                      'the Alert card front is a five-frame statue animation')
                alert_front = alert.locator('.drill-flip-front')
                command_layout = alert_front.evaluate("""node => {
                    const banner = node.querySelector('.drill-move-front-command');
                    const animation = node.querySelector('[data-drill-animation]');
                    const b = banner.getBoundingClientRect(), a = animation.getBoundingClientRect();
                    return {text: banner.textContent, bannerBottom: b.bottom, animationTop: a.top,
                            fontSize: parseFloat(getComputedStyle(banner.querySelector('strong')).fontSize)};
                }""")
                check('Alert!' in command_layout['text'] and command_layout['bannerBottom'] <= command_layout['animationTop'] + 1
                      and command_layout['fontSize'] >= 16,
                      'the Alert card front leads with a large Alert! command above the statue animation')
                frame_srcs = anim.locator('img').evaluate_all(
                    "imgs => imgs.map(img => img.getAttribute('src') || '')")
                check(all('/movements/alert-' in src for src in frame_srcs)
                      and not any('/manual/' in src for src in frame_srcs),
                      'the Alert animation uses statue frames, not a PDF/manual page')
                active_at = lambda: anim.evaluate(
                    "node => [...node.querySelectorAll('[data-drill-frame]')].findIndex(step => step.classList.contains('is-active'))")
                first_active = active_at()
                page.wait_for_timeout(1150)
                check(active_at() != first_active, 'the Alert statue animation advances through its frames')
                page.click('[data-drill-flip-go="next"]'); page.wait_for_timeout(520)
                ease = page.locator('[data-drill-flip="stand-at-ease"]')
                check(ease.count() == 1, 'the next carousel card is Stand at ease')
                ease_anim = ease.locator('[data-drill-animation="stand-at-ease"]')
                check(ease_anim.count() == 1 and ease_anim.locator('[data-drill-frame]').count() == 7,
                      'the Stand at ease card front is a seven-frame statue animation')
                ease_srcs = ease_anim.locator('img').evaluate_all(
                    "imgs => imgs.map(img => img.getAttribute('src') || '')")
                expected_ease_frames = [
                    'alert-5-alert.jpg', 'alert-4-lower.jpg', 'alert-2-lift.jpg',
                    'alert-3-close.jpg', 'stand-at-ease-5-lower-out.jpg',
                    'stand-at-ease-6-land.jpg', 'alert-1-stand-at-ease.jpg',
                ]
                check(len(ease_srcs) == len(expected_ease_frames)
                      and all(name in src for name, src in zip(expected_ease_frames, ease_srcs))
                      and not any('/manual/' in src for src in ease_srcs),
                      'Stand at ease runs Alert → lift → thigh level → lower out → stand at ease')
                ease_active_at = lambda: ease_anim.evaluate(
                    "node => [...node.querySelectorAll('[data-drill-frame]')].findIndex(step => step.classList.contains('is-active'))")
                ease_first_active = ease_active_at()
                page.wait_for_timeout(750)
                check(ease_active_at() != ease_first_active,
                      'the Stand at ease statue animation advances through its frames')
                page.click('[data-drill-flip-go="next"]'); page.wait_for_timeout(520)
                salute = page.locator('[data-drill-flip="salute-front"]')
                check(salute.count() == 1, 'the last carousel card is Salute')
                salute_anim = salute.locator('[data-drill-animation="salute-front"]')
                check(salute_anim.count() == 1 and salute_anim.locator('[data-drill-frame]').count() == 8,
                      'the Salute card front is an eight-frame statue animation')
                salute_srcs = salute_anim.locator('img').evaluate_all(
                    "imgs => imgs.map(img => img.getAttribute('src') || '')")
                expected_salute_frames = [
                    'alert-5-alert.jpg', 'salute-2-side-rise.jpg',
                    'salute-3-shoulder-level.jpg', 'salute-4-forearm-rise.jpg',
                    'salute-5-salute.jpg', 'salute-6-lower.jpg',
                    'salute-7-almost-down.jpg', 'alert-5-alert.jpg',
                ]
                check(len(salute_srcs) == len(expected_salute_frames)
                      and all(name in src for name, src in zip(expected_salute_frames, salute_srcs))
                      and not any('/manual/' in src for src in salute_srcs),
                      'Salute runs Alert → side rise → shoulder → forearm up → hold → down by the front → Alert')
                salute_active_at = lambda: salute_anim.evaluate(
                    "node => [...node.querySelectorAll('[data-drill-frame]')].findIndex(step => step.classList.contains('is-active'))")
                salute_first_active = salute_active_at()
                for _ in range(24):
                    page.wait_for_timeout(100)
                    if salute_active_at() != salute_first_active:
                        break
                check(salute_active_at() != salute_first_active,
                      'the Salute statue animation advances through its frames')
                page.click('[data-drill-flip-go="prev"]'); page.wait_for_timeout(420)
                page.click('[data-drill-flip-go="prev"]'); page.wait_for_timeout(480)
                alert = page.locator('[data-drill-flip="alert"]')
                alert.click(); page.wait_for_timeout(600)
                back = alert.inner_text()
                check(page.locator('[data-drill-go="start-stage"][disabled]').count() == 1,
                      'two stage-1 cards are still unread — the mechanism stays locked')
                check('口令' in back and 'Alert!' in back and '動作要點' in back and '30 度' in back,
                      'the Alert card back teaches its command and key points')
                check('起步為稍息' in back and '提起左腳' in back and '左腳踏下並靠攏右腳' in back,
                      'the Alert card teaches stand-at-ease → lift/close → Alert in order')
                shoot(page, 'drill-move-flip-stage1.png')
                alert.click(); page.wait_for_timeout(400)
            if index == 1:
                # every pace now gets its own card, so each one is readable on a phone
                pace_ids = []
                for step in range(4):
                    card = page.locator('[data-drill-flip]')
                    pace_ids.append(card.get_attribute('data-drill-flip'))
                    card.click()
                    page.wait_for_timeout(520)
                    if step < 3:
                        page.click('[data-drill-flip-go="next"]')
                        page.wait_for_timeout(480)
                check(pace_ids == fresh_ids[:4],
                      f'the four paces each get their own card, in order ({pace_ids})')
                back = page.locator('[data-drill-flip]').inner_text()
                check(MOVE_BY_ID['pace-right']['command'] in back and '右' in back,
                      'the last pacing card teaches its own command, not a shared card')
                shoot(page, 'drill-move-flip-pacing.png')
                for step in range(3):          # back to the first card
                    page.click('[data-drill-flip-go="prev"]')
                    page.wait_for_timeout(360)
                page.wait_for_timeout(200)
            if index == 2:
                for step in range(3):
                    page.click('[data-drill-flip-go="next"]')
                    page.wait_for_timeout(420)
                dress = page.locator('[data-drill-flip="right-dress"]')
                check(dress.count() == 1, 'the dressing card is the last of the four')
                dress.click(); page.wait_for_timeout(600)
                back = dress.inner_text()
                check('Right—dress!' in back and '看齊' in back and '排成直線' in back,
                      'the dressing card teaches the command and what dressing means')
                shoot(page, 'drill-move-flip-stage3.png')
                dress.click(); page.wait_for_timeout(300)
                for step in range(3):
                    page.click('[data-drill-flip-go="prev"]')
                    page.wait_for_timeout(320)

            # read every card of this stage before the mechanism may wake
            for step in range(len(fresh_ids)):
                card = page.locator('[data-drill-flip]')
                if 'is-flipped' not in (card.get_attribute('class') or ''):
                    card.click()
                    page.wait_for_timeout(420)
                if step < len(fresh_ids) - 1:
                    page.click('[data-drill-flip-go="next"]')
                    page.wait_for_timeout(400)
            check(page.locator('[data-drill-go="start-stage"][disabled]').count() == 0,
                  f'section 2 stage {index + 1} unlocks the mechanism after every card is read')

            page.click('[data-drill-go="start-stage"]')
            page.wait_for_selector('[data-drill-scene="drill"]')
            # the statue holds, plays once, then the commands and the count appear
            page.wait_for_selector('[data-drill-answers]:not(.is-waiting)', timeout=12000)
            check(page.locator('.drill.drill-command-full').count() == 1,
                  f'section 2 stage {index + 1} movement questions take the whole screen')
            pool_ids = [mid for stage in MOVE_STAGES[:index + 1] for mid in stage]
            first_target_id = current_move_id(page)
            prompt_kind = page.get_attribute('[data-drill-prompt-visual]',
                                             'data-drill-prompt-kind')
            prompt_text = page.inner_text('[data-drill-card]')
            check(first_target_id in pool_ids and '這個動作的口令是甚麼？' in prompt_text,
                  f'section 2 stage {index + 1} shows a learned movement and asks for its command: '
                  f'{first_target_id}')
            buttons = page.query_selector_all('[data-drill-form]')
            button_ids = [button.get_attribute('data-drill-form') for button in buttons]
            button_commands = [' '.join(button.inner_text().split()) for button in buttons]
            expected_buttons = expected_button_counts[index]
            first_position = button_ids.index(first_target_id) if first_target_id in button_ids else -1
            check(len(buttons) == expected_buttons and len(set(button_ids)) == expected_buttons
                  and set(button_ids) <= set(pool_ids) and first_position >= 0
                  and set(button_commands) == {MOVE_BY_ID[mid]['command'] for mid in button_ids}
                  and page.locator('[data-drill-forms][data-answer-kind="command"] '
                                   '.drill-command-btn[data-drill-answer-kind="command"]').count()
                      == expected_buttons,
                  f'section 2 stage {index + 1} answers with {expected_buttons} unique command buttons '
                  f'from its {expected_pools[index]}-movement cumulative pool, including the shown movement')
            if index:
                check(0 <= first_position < expected_buttons,
                      f'section 2 stage {index + 1} places the correct command among the {expected_buttons} choices '
                      f'(position {first_position + 1} on this question)')
            target_move = MOVE_BY_ID.get(first_target_id, {})
            if target_move.get('animation'):
                prompt_frames = page.locator(
                    f'[data-drill-prompt-visual] [data-drill-animation="{first_target_id}"] '
                    '[data-drill-frame]'
                ).count()
                check(prompt_kind == 'animation'
                      and prompt_frames == len(target_move['animation'])
                      and page.locator('[data-drill-prompt-visual] .drill-statue-caption').count() == 0,
                      f'section 2 stage {index + 1} puts the finalized statue animation in the large '
                      'question area without answer-revealing captions')
            else:
                check(prompt_kind == 'diagram'
                      and page.locator('[data-drill-prompt-visual] .drill-move-art.is-detailed').count() == 1,
                      f'section 2 stage {index + 1} puts a large movement diagram in the question '
                      'area until that statue animation is finalized')
            check(page.locator('[data-drill-forms] [data-drill-animation]').count() == 0
                  and page.locator('[data-drill-forms] .drill-move-art').count() == 0,
                  f'section 2 stage {index + 1} no longer shrinks movement visuals into answer buttons')
            check_answer_grid(page, expected_buttons,
                              ((300, 450), (180, 220), (180, 220))[index],
                              f'the desktop stage {index + 1} screen')
            shoot(page, f'drill-move-prompt-stage{index + 1}.png')

            if index == 0:
                target_id = current_move_id(page)
                wrong_btn = next(b for b in buttons if b.get_attribute('data-drill-form') != target_id)
                page.mouse.move(5, 5)
                page.wait_for_timeout(200)
                wrong_btn.click()
                page.wait_for_selector('[data-drill-scene="review"]')
                review = page.inner_text('[data-drill-card]')
                target = MOVE_BY_ID[target_id]
                check('不是這個口令' in review and target['title_zh'] in review and target['command'] in review,
                      'a wrong command press opens the movement review')
                check(page.locator('[data-drill-card] .drill-move-art.is-detailed').count() == 1
                      or page.locator('[data-drill-card] [data-drill-animation]').count() == 1,
                      'the movement review shows its detailed diagram or animated statue')
                shoot(page, 'drill-move-review-stage1.png')
                click(page, '[data-drill-go="resume"]')
                page.wait_for_selector('[data-drill-scene="drill"]')
            if index == 2:
                for width, height, label in ((390, 700, 'phone'), (1000, 550, 'short'), (700, 420, 'tiny-short')):
                    page.set_viewport_size({'width': width, 'height': height})
                    page.wait_for_timeout(250)
                    prompt_visible = page.evaluate("""() => {
                        const c = document.querySelector('[data-drill-prompt-visual]').getBoundingClientRect();
                        return c.top >= 0 && c.bottom <= innerHeight && c.width > 0 && c.height > 0;
                    }""")
                    check(prompt_visible,
                          f'the stage 3 movement prompt stays visible in a {label} window')
                    check_answer_grid(page, expected_buttons, (70, 90) if width <= 430 else (90, 90),
                                      f'a {label} window')
                    page.screenshot(path=str(SHOTS / f'drill-move-prompt-stage3-{label}.png'))
                page.set_viewport_size({'width': 1180, 'height': 940})
                page.wait_for_timeout(250)

            choice_audit = []
            where, prompts, reviews, seen = clear_stage(page, choice_audit)
            check(where == 'stage-done', f'section 2 stage {index + 1} ends on its drill card')
            check(prompts == expected_pools[index] and set(seen) == set(pool_ids),
                  f'section 2 stage {index + 1} shows every cumulative movement ({prompts})')
            if index:
                positions = [entry['position'] for entry in choice_audit]
                check(len(choice_audit) == prompts
                      and all(len(entry['ids']) == expected_buttons
                              and len(set(entry['ids'])) == expected_buttons
                              and set(entry['ids']) <= set(pool_ids)
                              and entry['target'] in entry['ids']
                              and entry['ids'][entry['position']] == entry['target']
                              for entry in choice_audit),
                      f'section 2 stage {index + 1} shows {expected_buttons} unique learned command choices on every question')
                check(len(set(positions)) >= 2,
                      f'section 2 stage {index + 1} varies the correct-answer position '
                      f'({[position + 1 for position in positions]})')
            check(reviews == 0, f'section 2 stage {index + 1} needed no extra reviews on this walk')
            done = page.inner_text('[data-drill-card]')
            check(f'第 {index + 1} 階段操練完成' in done,
                  f'section 2 stage {index + 1} completion is named on its card')

        # ── both sections clear: studying is filed, then the leader approves
        click(page, '[data-drill-go="finish"]')
        page.wait_for_selector('[data-drill-wait]', timeout=10000)
        assess = page.inner_text('[data-drill-card]')
        check('等領袖批准' in assess and '四方向' not in assess and '前、後、左、右移一步' in assess,
              'finishing section 2 opens the leader assessment card')
        check('原地踏步' in assess and '停步' in assess and '向右看齊' in assess,
              'the assessment card names the stage 3 movements to perform')
        check(page.query_selector('[data-drill-code-input]') is None,
              'there is no leader code to type any more')
        shoot(page, 'drill-assess.png')
        badge, task = progress(page)
        check(task['status'] == 'studied', 'both sections file the studying, not completion')
        check(badge['progress_done'] == before,
              'the game counter still waits for the leader')
        expected_bad_code_errors = 0

        # the leader presses 批准 in the leader account
        lctx = browser.new_context(locale='zh-HK', viewport={'width': 1180, 'height': 940})
        lctx.request.post(f'{BASE}/login/leader', form={'password': '0082'})
        lp = lctx.new_page()
        lp.goto(f'{BASE}/leader/review')
        lp.wait_for_load_state('networkidle')
        lcard = lp.locator('.review-card', has_text='已完成遊戲 · 等考核').first
        check(lcard.count() == 1, 'the finished drill ground stands in the leader queue')
        check('看他親身做出各個動作' in lcard.inner_text(),
              'the queue card says what to watch for')
        lcard.locator('button[value="approve"]').click()
        lp.wait_for_timeout(1200)
        check(lp.locator('.review-card', has_text='已完成遊戲 · 等考核').count() == 0,
              'the approval clears the card out of the queue')
        lctx.close()

        click(page, '[data-drill-go="check"]')
        page.wait_for_function(
            "() => { var c = document.querySelector('[data-drill-card]');"
            "        return c && c.innerText.indexOf('第 6 項完成') >= 0; }")
        result = page.inner_text('[data-drill-card]')
        check('領袖批准了' in result and '第 6 項完成' in result,
              'the waiting card turns into the tick once the leader approves')
        shoot(page, 'drill-result.png')
        badge, task = progress(page)
        check(task['status'] == 'completed', 'item 6 is completed after the leader approves')
        check(badge['progress_done'] == before + 1,
              f'the game counter moves once ({before} → {badge["progress_done"]} of {total})')
        page.goto(drill_url)
        page.wait_for_selector('[data-drill][data-drill-scene="result"]')
        check('遊戲 3 通關' in page.inner_text('[data-drill-card]'),
              'a completed scout re-opens on the game 3 result card')

        for text in errors:
            if expected_bad_code_errors and 'status of 400' in text:
                expected_bad_code_errors -= 1
                continue
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
