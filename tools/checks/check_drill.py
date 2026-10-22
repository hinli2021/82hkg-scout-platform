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
pool is cumulative within section 2 (3, then 10, then 14 calls). Wrong or
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
    """Read the visible prompt: a statue's sign in section 1, a command in 2."""
    return page.evaluate("""() => {
        var root = document.querySelector('[data-drill]');
        var cfg = JSON.parse(root.getAttribute('data-drill-config'));
        var moves = [];
        cfg.sections.forEach(function (s) { (s.moves || []).forEach(function (m) { moves.push(m); }); });
        if (root.getAttribute('data-drill-section') === '2') {
            var commandNode = root.querySelector('[data-drill-command]');
            var command = commandNode ? commandNode.textContent.trim() : '';
            var called = moves.find(function (m) { return (m.command || '') === command; });
            return called ? called.id : 'NOT FOUND COMMAND: ' + command;
        }
        var art = root.querySelector('.cave-picture .cave-art');
        var framed = art ? (art.getAttribute('data-drill-art') || '') : '';
        var target = moves.find(function (m) { return (m.figure && m.figure === framed) || (m.img && m.img === framed); });
        return target ? target.id : 'NOT FOUND: ' + framed;
    }""")


def answer_current(page):
    """Press the formation or movement the visible prompt is calling for."""
    page.wait_for_selector('[data-drill-beat]')
    page.wait_for_timeout(150)
    target_id = current_move_id(page)
    if target_id.startswith('NOT FOUND'):
        return target_id
    btn = page.locator(f'[data-drill-form="{target_id}"]')
    if btn.count() != 1:
        return f'NO BUTTON for {target_id}'
    btn.first.click()
    return target_id


def clear_stage(page):
    """Answer every sign the stage calls, until the scene moves on.

    Returns (final scene, prompts answered, reviews met, movement ids).
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
        seen.append(answer_current(page))
        prompts += 1
        page.wait_for_timeout(1300)      # the ✓ flash, then the next sign


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
        for index, fresh_ids in enumerate(MOVE_STAGES):
            if index:
                click(page, '[data-drill-go="next-stage"]')
                page.wait_for_selector('[data-drill-scene="flip"]')
            check(page.get_attribute('[data-drill]', 'data-drill-section') == '2',
                  f'section 2 stage {index + 1} opens on the parade ground')
            cards = page.query_selector_all('[data-drill-flip]')
            check(len(cards) == expected_units[index],
                  f'section 2 stage {index + 1} shows {expected_units[index]} study card(s)')
            flip_text = page.inner_text('[data-drill-card]')
            check(f'第 {index + 1} 階段' in flip_text and '口令' in flip_text,
                  f'section 2 stage {index + 1} teaches commands before the mechanism')
            check(page.locator('[data-drill-flip] .drill-move-front-command').count() == expected_units[index],
                  f'section 2 stage {index + 1} puts a command banner on every card front')
            check(page.locator('[data-drill-flip] .drill-flip-back.is-move .drill-move-art').count() == 0,
                  f'section 2 stage {index + 1} card backs lead with the command, not a movement icon')
            if index:
                check('已學過的動作' in flip_text,
                      f'section 2 stage {index + 1} lists movements already learned')
            if index == 0:
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
                alert.click(); page.wait_for_timeout(600)
                back = alert.inner_text()
                check('口令' in back and 'Alert!' in back and '動作要點' in back and '30 度' in back,
                      'the Alert card back teaches its command and key points')
                check('起步為稍息' in back and '提起左腳' in back and '左腳踏下並靠攏右腳' in back,
                      'the Alert card teaches stand-at-ease → lift/close → Alert in order')
                check(page.locator('[data-drill-flip] .drill-flip-back.is-move .drill-move-command').count() == 3,
                      'every stage 1 movement card back leads with its command')
                shoot(page, 'drill-move-flip-stage1.png')
                alert.click(); page.wait_for_timeout(400)
            if index == 1:
                pacing = page.locator('[data-drill-flip="pacing"]')
                check(pacing.count() == 1, 'the four paces share one study card')
                pace_front = pacing.locator('.drill-flip-front').inner_text()
                pace_front_commands = [MOVE_BY_ID[mid]['command'] for mid in fresh_ids[:4]]
                check(all(command in pace_front for command in pace_front_commands),
                      'the pacing card front puts all four directional commands first')
                pacing.click(); page.wait_for_timeout(600)
                back = pacing.inner_text()
                pace_commands = [MOVE_BY_ID[mid]['command'] for mid in fresh_ids[:4]]
                check(all(command in back for command in pace_commands),
                      'the pacing card teaches all four directional commands')
                check('300 毫米' in back and '領袖示範' in back,
                      'the pacing card gives the side-pace distance and leader-demo note')
                shoot(page, 'drill-move-flip-pacing.png')
                pacing.click(); page.wait_for_timeout(400)
            if index == 2:
                dress = page.locator('[data-drill-flip="right-dress"]')
                dress.click(); page.wait_for_timeout(600)
                back = dress.inner_text()
                check('Right—dress!' in back and '看齊' in back and '排成直線' in back,
                      'the dressing card teaches the command and what dressing means')
                shoot(page, 'drill-move-flip-stage3.png')
                dress.click(); page.wait_for_timeout(400)

            click(page, '[data-drill-go="start-stage"]')
            page.wait_for_selector('[data-drill-scene="drill"]')
            page.wait_for_timeout(250)
            check(page.locator('.drill.drill-command-full').count() == 1,
                  f'section 2 stage {index + 1} commands take the whole screen')
            command = page.inner_text('[data-drill-command]').strip()
            pool_ids = [mid for stage in MOVE_STAGES[:index + 1] for mid in stage]
            pool_commands = {MOVE_BY_ID[mid]['command'] for mid in pool_ids}
            check(command in pool_commands,
                  f'section 2 stage {index + 1} calls a learned command: {command}')
            buttons = page.query_selector_all('[data-drill-form]')
            check(len(buttons) == expected_pools[index],
                  f'section 2 stage {index + 1} answers from {expected_pools[index]} cumulative movement buttons')
            animated_ids = [mid for mid in pool_ids if MOVE_BY_ID[mid].get('animation')]
            check(page.locator('[data-drill-forms] [data-drill-move-visual="animation"]').count() == len(animated_ids)
                  and page.locator('[data-drill-form="alert"] [data-drill-animation="alert"] [data-drill-frame]').count() == 5,
                  f'section 2 stage {index + 1} uses the finalized Alert statue animation on its answer button')
            check(page.locator('[data-drill-forms] [data-drill-move-visual="icon"] .drill-move-art').count()
                  == expected_pools[index] - len(animated_ids),
                  f'section 2 stage {index + 1} keeps icons only for movements without a finalized animation')
            shoot(page, f'drill-move-prompt-stage{index + 1}.png')

            if index == 0:
                target_id = current_move_id(page)
                wrong_btn = next(b for b in buttons if b.get_attribute('data-drill-form') != target_id)
                wrong_btn.click()
                page.wait_for_selector('[data-drill-scene="review"]')
                review = page.inner_text('[data-drill-card]')
                target = MOVE_BY_ID[target_id]
                check('不是這個動作' in review and target['title_zh'] in review and target['command'] in review,
                      'a wrong movement press opens the command review')
                check(page.locator('[data-drill-card] .drill-move-art.is-detailed').count() == 1
                      or page.locator('[data-drill-card] [data-drill-animation]').count() == 1,
                      'the movement review shows its detailed diagram or animated statue')
                shoot(page, 'drill-move-review-stage1.png')
                click(page, '[data-drill-go="resume"]')
                page.wait_for_selector('[data-drill-scene="drill"]')
            if index == 2:
                for width, height, label in ((390, 700, 'phone'), (1000, 550, 'short')):
                    page.set_viewport_size({'width': width, 'height': height})
                    page.wait_for_timeout(250)
                    fit = page.evaluate("""() => {
                        const forms = document.querySelector('[data-drill-forms]');
                        const cmd = document.querySelector('[data-drill-command]');
                        const btns = [...forms.querySelectorAll('button')].map(b => b.getBoundingClientRect());
                        const c = cmd.getBoundingClientRect();
                        return {
                          commandVisible: c.top >= 0 && c.bottom <= innerHeight,
                          allButtonsVisible: btns.every(r => r.top >= 0 && r.bottom <= innerHeight)
                        };
                    }""")
                    check(fit['commandVisible'] and fit['allButtonsVisible'],
                          f'the 14-movement command board fits a {label} window')
                    page.screenshot(path=str(SHOTS / f'drill-move-prompt-stage3-{label}.png'))
                page.set_viewport_size({'width': 1180, 'height': 940})
                page.wait_for_timeout(250)

            where, prompts, reviews, seen = clear_stage(page)
            check(where == 'stage-done', f'section 2 stage {index + 1} ends on its drill card')
            check(prompts == expected_pools[index] and set(seen) == set(pool_ids),
                  f'section 2 stage {index + 1} calls every cumulative movement ({prompts})')
            check(reviews == 0, f'section 2 stage {index + 1} needed no extra reviews on this walk')
            done = page.inner_text('[data-drill-card]')
            check(f'第 {index + 1} 階段操練完成' in done,
                  f'section 2 stage {index + 1} completion is named on its card')

        # ── both sections clear: studying is filed, then the leader's code
        click(page, '[data-drill-go="finish"]')
        page.wait_for_selector('[data-drill-code-input]', timeout=10000)
        assess = page.inner_text('[data-drill-card]')
        check('找領袖考核' in assess and '四方向' not in assess and '前、後、左、右移一步' in assess,
              'finishing section 2 opens the leader assessment card')
        check('原地踏步' in assess and '停步' in assess and '向右看齊' in assess,
              'the assessment card names the stage 3 movements to perform')
        shoot(page, 'drill-assess.png')
        badge, task = progress(page)
        check(task['status'] == 'studied', 'both sections file the studying, not completion')
        check(badge['progress_done'] == before,
              'the game counter still waits for the leader code')
        page.fill('[data-drill-code-input]', '0000')
        page.click('[data-drill-code] button[type="submit"]')
        page.wait_for_timeout(700)
        check('代碼不對' in page.inner_text('[data-drill-card]'),
              'a wrong leader code is refused')
        expected_bad_code_errors = 1  # Chromium logs the deliberate 400 as a resource error
        page.fill('[data-drill-code-input]', '82DR')
        page.click('[data-drill-code] button[type="submit"]')
        page.wait_for_timeout(900)
        result = page.inner_text('[data-drill-card]')
        check('遊戲 3 通關' in result and '第 6 項完成' in result,
              'the right leader code clears game 3 and item 6')
        shoot(page, 'drill-result.png')
        badge, task = progress(page)
        check(task['status'] == 'completed', 'item 6 is completed after the leader code')
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
