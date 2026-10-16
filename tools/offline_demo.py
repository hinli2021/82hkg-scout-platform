"""Builds demo-preview.html — the whole sign-in walk as ONE offline file.

Why this exists: the preview panel runs the page inside an iframe, so the
browser drops the session cookie, and the sandbox itself sleeps between
sessions (taking the server down with it). This file needs neither: every screen
is rendered here, inlined, and stitched together with a tiny router.

Run it after any template/style change:

    cd scout-platform-py && python3 tools/offline_demo.py

It writes demo-preview.html in the project root (self-contained, with inlined images):
    scene  →  patrol name list  →  first-time setup (password + email) → home
    scene  →  patrol name list  →  existing scout home
    scene  →  領袖登入          →  code card (0082) →  leader home
Anything that would need the server (handing in a task, signing out, …) is
disabled and says so instead of failing silently.
"""
from __future__ import annotations

import base64
import html
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import tempfile

# Only the cave's question content may be copied from an existing local site;
# the demo itself still uses disposable accounts and progress in a temp store.
LOCAL_CONTENT_DIR = pathlib.Path(os.environ.get("OFFLINE_SOURCE_DATA_DIR") or ROOT / "data")
os.environ.setdefault("SECRET_KEY", "offline-demo")
# the demo gets its own throw-away data dir: the build must never touch the
# real one, and a fresh seed is what makes the screens below reproducible
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="offline-demo-")
os.environ["SEED_DEMO"] = "true"
os.environ.setdefault("DEMO_LOGIN", "true")

from app import create_app                                  # noqa: E402

BUILD = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")
MASCOTS = ("tiger", "otter", "seagull")
PATROLS = ("Tiger", "Otter", "Seagull")

app = create_app()
client = app.test_client()


def data_uri(path: pathlib.Path) -> str:
    kind = {"webp": "webp", "jpg": "jpeg", "jpeg": "jpeg", "png": "png"}[path.suffix.lstrip(".").lower()]
    return f"data:image/{kind};base64," + base64.b64encode(path.read_bytes()).decode()


PAGE_CSS: list[str] = []          # <style> blocks found in any page's <head>


def body_of(html: str) -> str:
    """Everything inside <body>…</body>, i.e. one screen ready to be a pane.

    The breadcrumb "‹ 返回" is dropped here: offline it is a dead link, and the
    leader asked for no back buttons anywhere in this file.
    """
    for block in re.findall(r"<style>(.*?)</style>", html, re.S):
        # A page may carry a few rules of its own; pull them up into the
        # offline file's single stylesheet so it needs no network.
        PAGE_CSS.append(block)
    html = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S)
    body = m.group(1) if m else html
    return re.sub(r'<div class="crumbs">.*?</div>', "", body, flags=re.S)


def fetch(path: str) -> str:
    return client.get(path).get_data(as_text=True)


def session_html(start: str) -> str:
    """The page behind a sign-in, fetched the cookie-less way (?sid=…)."""
    return fetch(session_token(start)[1])


def session_token(start: str) -> tuple[str, str]:
    """(sid, the page behind the sign-in) — the token keeps the session alive."""
    response = client.post(start, follow_redirects=False)
    location = response.headers["Location"]
    return location.split("sid=", 1)[1], fetch(location)


# ── the screens ────────────────────────────────────────────────────────────
panes: list[tuple[str, str, str]] = []          # (id, title, body)

panes.append(("scene", "Sign in", body_of(fetch("/login"))))
for patrol in PATROLS:
    panes.append((f"names-{patrol}", f"{patrol} · who are you?", body_of(fetch(f"/login/scout/{patrol}"))))
# ── 會員章, told as one story with one scout (demo2 = 張家豪) ────────────────
#   first-time scout07 must finish setup; existing demo2 goes straight home →
#   badge → first location's information → one button → cave.
#   No extra task or paper is created; the score is calculated from what the
#   scout actually chooses. The temp data dir is separate from the live demo.
from scout.store import Store                                     # noqa: E402
from scout.mascots import mascot_for                            # noqa: E402
from scout.schema import patrol_label                           # noqa: E402

store = Store.from_env()
membership = sorted(store.list("badges"), key=lambda b: int(b["order_index"]))[0]
me = next(u for u in store.list("users") if u["username"] == "scout03")
first_scout = next(u for u in store.list("users") if u["username"] == "scout07")

own = [r for r in store.list("progress_records")
       if r["user_id"] == me["id"] and r["badge_id"] == membership["id"]]
for record in own:
    store.remove("progress_records", record["id"])
store.rebuild_stats(me["id"])

sid, _ = session_token("/login/demo/demo2")

cave_task = next(t for t in store.list("tasks")
                 if t["badge_id"] == membership["id"] and t.get("code") == "M04")

# A leader's edits live in the site's task record, not the shipped seed files.
# Copy just those 50 questions into this throw-away demo so rebuilding the
# offline HTML reflects local changes; never copy scout accounts or scores.
local_tasks = LOCAL_CONTENT_DIR / "db" / "tasks.json"
if local_tasks.is_file():
    try:
        rows = json.loads(local_tasks.read_text(encoding="utf-8"))
        local = next((row for row in rows if row.get("code") == "M04"), None)
        if not local:
            raise ValueError("M04 is not in this local database")
        source_config = json.loads(local["config_json"]) if isinstance(local.get("config_json"), str) else local["config_json"]
        questions = source_config.get("questions") or []
        seed_config = cave_task["config_json"]
        seed_config = json.loads(seed_config) if isinstance(seed_config, str) else seed_config
        if (len(questions) == 50 and
                [q.get("id") for q in questions] == [q.get("id") for q in seed_config["questions"]]):
            store.update("tasks", cave_task["id"], {"config_json": {**seed_config, "questions": questions}})
            print("offline cave questions: copied from local leader content")
        else:
            print("offline cave questions: local IDs do not match the walls; using shipped seed")
    except (ValueError, KeyError, TypeError, AttributeError):
        print("offline cave questions: local content unreadable; using shipped seed")

panes.append(("home", "Home", body_of(fetch(f"/home?sid={sid}"))))
panes.append(("badges", "我的獎章 · the journey", body_of(fetch(f"/badges?sid={sid}"))))
panes.append(("history", "我的紀錄 · history", body_of(fetch(f"/history?sid={sid}"))))
panes.append(("quest-intro", "會員章 · 玩法（你被困住了！）",
              body_of(fetch(f"/badges/{membership['id']}?sid={sid}"))))

panes.append(("guide", "會員章 · 綱要參考",
              body_of(fetch(f"/badges/{membership['id']}/requirements?sid={sid}"))))

# Remove the network submission URL from this *offline copy only*. cave.js
# already knows how to score the first attempt of every answer locally when
# there is no endpoint; the real platform still marks and records it server-side.
# There is just one cave game, not a cave + another fifty-question form.
cave_page = fetch(f"/tasks/{cave_task['id']}/cave?sid={sid}")
def clear_offline_submit(match: re.Match) -> str:
    config = json.loads(html.unescape(match.group(2)))
    config["submit_url"] = ""
    config.pop("run_key", None)  # server-only snapshot; the offline cave grades locally
    return match.group(1) + html.escape(json.dumps(config, ensure_ascii=False), quote=True) + match.group(3)

cave_page = re.sub(r'(data-cave-config=")(.*?)(")', clear_offline_submit, cave_page, count=1, flags=re.S)
panes.append(("cave", "遊戲 1 · 童軍歷史山洞", body_of(cave_page)))

# ── game 2: 迷霧渡口 — the bridge the scout builds plank by plank ──────────
# Same treatment as the cave: no endpoint in the offline copy, so the game
# checks the planks itself and reports a win to the router below.
bridge_task = next((t for t in store.list("tasks")
                    if t["badge_id"] == membership["id"] and t.get("code") == "M05"), None)
if bridge_task is None:
    print("offline bridge: M05 is missing from this database; the demo skips game 2")

def clear_bridge_submit(match: re.Match) -> str:
    config = json.loads(html.unescape(match.group(2)))
    config["submit_url"] = ""
    config.pop("run_key", None)
    return match.group(1) + html.escape(json.dumps(config, ensure_ascii=False), quote=True) + match.group(3)

if bridge_task is not None:
    bridge_page = fetch(f"/tasks/{bridge_task['id']}/bridge?sid={sid}")
    bridge_page = re.sub(r'(data-bridge-config=")(.*?)(")', clear_bridge_submit,
                         bridge_page, count=1, flags=re.S)
    panes.append(("bridge", "遊戲 2 · 迷霧渡口", body_of(bridge_page)))

panes.append(("leader", "Leader", body_of(session_html("/login/demo/demo1"))))

# the leaders' door is NOT free: the offline copy of the card asks for the code
# (0082) exactly like the live one, so the demo does not teach the wrong thing
# (a *clean* client: the signed-in one would render the "already signed in" card,
#  which has no code box at all)
bare = app.test_client()
code_page = body_of(bare.get("/login/leader").get_data(as_text=True))
code_page = re.sub(r'(<div class="crumbs"><a href=")/(login)"', r'\1#\2 data-nav="scene"',
                   code_page)                                                          # ‹ 返回 → the scene
code_page = code_page.replace(
    '<form method="post" action="/login/leader">',
    '<form data-leadercode="1" method="post" action="#">',
)
code_page = code_page.replace(
    '<form data-leadercode="1"',
    '<div class="alert error" id="offline-code-error" hidden>'
    '領袖代碼不對，請再試 · Wrong leader code</div>\n    <form data-leadercode="1"',
)
panes.insert(4, ("leader-code", "Leader sign-in", code_page))


def as_demo_scout(markup: str) -> str:
    """Rewrite a first-time page so it belongs to the account the demo walks in as.

    The welcome form is rendered for scout07 (吳卓穎 · 海鷗), but the offline file
    signs in as the scout demo (demo2 = 張家豪 · 水獺). Names, patrol words and the
    patrol artwork/colours are swapped so the pane matches who the visitor meets
    on the home screen — one scout, one demo, one story.
    """
    here, there = first_scout, me
    swaps = [
        (here["display_name_zh"], there["display_name_zh"]),
        (here["display_name_en"], there["display_name_en"]),
        (here["avatar"], there["avatar"]),
        (patrol_label(here["patrol"])["zh"], patrol_label(there["patrol"])["zh"]),
        (here["patrol"], there["patrol"]),                       # Seagull → Otter
        (f"/static/img/mascots/{here['patrol'].lower()}.webp",
         f"/static/img/mascots/{there['patrol'].lower()}.webp"),
    ]
    for key in ("tint", "tint_dark", "soft", "glow"):
        swaps.append((mascot_for(here["patrol"])[key], mascot_for(there["patrol"])[key]))
    for old, new in swaps:
        if old:
            markup = markup.replace(str(old), str(new))
    return markup


# A first-time name must NOT jump to Home, even in the zero-network demo. Use
# the same welcome form as the live app and validate it locally; no password or
# email is stored in the HTML, localStorage, or the throw-away demo account.
first_sid, _ = session_token("/login/demo/demo3")
setup_page = as_demo_scout(body_of(fetch(f"/welcome?sid={first_sid}")))
setup_page = re.sub(r'(<form\b[^>]*?)action="[^"]+"', r'\1action="#"', setup_page, count=1)
setup_page = setup_page.replace('class="setup-form"',
                                'class="setup-form" data-offline-setup="1" novalidate', 1)
setup_page = setup_page.replace('<form ',
    '<div class="alert info small">離線示範只模擬必填步驟；密碼及電郵不會儲存。'
    ' Offline preview only: your password and email are not saved.</div>\n'
    '<div class="alert warn" id="offline-setup-error" role="alert" hidden></div>\n<form ', 1)
panes.insert(5, ("setup", "First-time account setup", setup_page))

# ── stitch ─────────────────────────────────────────────────────────────────
css = (ROOT / "static/styles.css").read_text()
fx = (ROOT / "static/js/effects.js").read_text()
login_js = (ROOT / "static/js/login.js").read_text()
cave_js = (ROOT / "static/js/cave.js").read_text()        # 第 4 項: the cave walks itself
bridge_js = (ROOT / "static/js/bridge.js").read_text()    # 第 5 項: the planks of 迷霧渡口

# the login script: instead of leaving the page, it switches pane
login_js = login_js.replace(
    "var href = spot.getAttribute('href');\n    if (!href || href === '#') return;",
    "var href = spot.getAttribute('data-nav') || spot.getAttribute('href');\n    if (!href || href === '#') return;",
)
login_js = login_js.replace(
    "window.setTimeout(function () { window.location.href = href; }, reduced() ? 60 : 560);",
    "window.setTimeout(function () { window.OFFLINE_DEMO.go(href); }, reduced() ? 60 : 560);",
)

router = """
/* ── the offline router ──────────────────────────────────────────────────
   One file, one cave, five areas. Its score is local in this demo; the live
   game writes its result on the server. Other forms needing a server are off. */
(function () {
  'use strict';
  var panes = Array.prototype.slice.call(document.querySelectorAll('.pane'));
  var shown = 'scene';
  var trail = [];
  var game1Cleared = false;
  var game2Cleared = false;
  var setupPending = false;
  var setupComplete = false;
  var scoutPanes = { home: 1, badges: 1, history: 1, 'quest-intro': 1, guide: 1,
                     cave: 1, bridge: 1 };

  /* A cleared location keeps a small door of its own: the live map does the same,
     so the offline file must not be the only place without a way back in. */
  function replayDoor(chip, pane, label) {
    if (!chip || chip.querySelector('.stage-chip-replay')) return;
    var card = chip.querySelector('.stage-chip-card') || chip;
    var door = document.createElement('a');
    door.className = 'stage-chip-replay';
    door.setAttribute('data-nav', pane);
    door.textContent = '🎮 ' + label;
    card.appendChild(door);
  }

  function go(id, exitApproved) {
    if (id === 'scene' || id === 'leader-code' || id.indexOf('names-') === 0) {
      setupPending = false; // changing accounts is allowed; skipping setup is not
    }
    if (id === 'setup') {
      if (setupComplete) id = 'home';
      else setupPending = true;
    }
    if (setupPending && !setupComplete && scoutPanes[id]) id = 'setup';
    var target = document.getElementById('pane-' + id);
    if (!target) return;
    var game = leavingGame(id) && !exitApproved ? shownGame() : null;
    if (game) {
      game.requestExit(function () { go(id, true); });
      return;
    }
    if (id !== shown) trail.push(shown);
    /* This one file reuses each game instance, so a replay door has to send the
       game back to its entrance — the live pages do it by loading the URL again. */
    if (id !== shown && id === 'cave') window.CaveGame.restart();
    if (id !== shown && id === 'bridge') window.BridgeGame.restart();
    panes.forEach(function (p) { p.hidden = p !== target; });
    target.querySelectorAll('.pane-inner').forEach(function (n) { n.hidden = false; });
    shown = id;
    window.scrollTo(0, 0);
    document.body.className = target.getAttribute('data-body') || '';
    if (window.FX && FX.init) { try { FX.init(); } catch (e) {} }
  }

  // Leaving a game still asks first — whichever game is on the screen.
  function shownGame() {
    return shown === 'cave' ? window.CaveGame : window.BridgeGame;
  }
  function leavingGame(id) {
    return (shown === 'cave' && id !== 'cave') || (shown === 'bridge' && id !== 'bridge');
  }

  function back() {
    var previous = trail[trail.length - 1];
    if (!previous) return;
    var arrive = function () { trail.pop(); go(previous, true); };
    var game = leavingGame(null) ? shownGame() : null;
    if (game) game.requestExit(arrive);
    else arrive();
  }

  // The offline file cannot persist a server record. During this visit, show
  // the first area and the 1 / 5 counter as cleared when the actual cave game
  // completes, whatever the score; a reload starts from the clean slate.
  document.addEventListener('cave:result', function (event) {
    if (!event.detail || !event.detail.passed || game1Cleared) return;
    game1Cleared = true;
    var pane = document.getElementById('pane-quest-intro');
    if (pane) {
      var first = pane.querySelector('.stage-chip[data-stage="1"]');
      var second = pane.querySelector('.stage-chip[data-stage="2"]');
      if (first) {
        first.classList.add('is-done');
        first.classList.remove('is-here');
        var state = first.querySelector('[data-game-state]');
        if (state) state.textContent = '✔ 已完成';
        var me = first.querySelector('.stage-chip-me');
        if (me && second) second.querySelector('.stage-chip-card').appendChild(me);
      }
      if (second) {
        second.classList.add('is-here');
        var card = second.querySelector('.stage-chip-card');
        if (card) card.setAttribute('aria-current', 'step');
      }
      var beacon = pane.querySelector('.story-beacon-meter .small');
      if (beacon) beacon.textContent = beacon.textContent.replace(/0\\s*\\/\\s*5/g, '1 / 5');
      var bar = pane.querySelector('.story-beacon-bar span');
      if (bar) bar.style.width = '20%';
      var raft = pane.querySelector('.story-raft-meter');
      if (raft) raft.textContent = '1 / 5';
      replayDoor(first, 'cave', '再玩一次');
      var play = pane.querySelector('[data-journey-play]');
      if (play) {
        // the next game is the crossing, so the one button now points at it
        play.setAttribute('data-nav', 'bridge');
        play.removeAttribute('href');
        play.textContent = '🎮 繼續歷險 · 進入遊戲 2';
      }
      var lead = pane.querySelector('[data-journey-launch] .story-launch-note:not([data-journey-wait])');
      if (lead) lead.textContent = '直接進入「迷霧渡口」。';
      var wait = pane.querySelector('[data-journey-wait]');
      if (wait) wait.hidden = true;      // game 2 is ready; no waiting notice yet
    }
    var tile = document.querySelector('#pane-home [data-badge-meter]');
    if (tile) tile.textContent = '1 / 5 個遊戲';
  });

  // The bridge is the second game: clear area 2, stand the scout on area 3,
  // and move both counters one step on. Game 3 waits for its leader, as ever.
  document.addEventListener('bridge:result', function (event) {
    if (!event.detail || !event.detail.cleared || game2Cleared) return;
    game2Cleared = true;
    var pane = document.getElementById('pane-quest-intro');
    if (pane) {
      var second = pane.querySelector('.stage-chip[data-stage="2"]');
      var third = pane.querySelector('.stage-chip[data-stage="3"]');
      if (second) {
        second.classList.add('is-done');
        second.classList.remove('is-here');
        var state = second.querySelector('[data-game-state]');
        if (state) state.textContent = '✔ 已完成';
        var me = second.querySelector('.stage-chip-me');
        if (me && third) third.querySelector('.stage-chip-card').appendChild(me);
      }
      if (third) {
        third.classList.add('is-here');
        var card = third.querySelector('.stage-chip-card');
        if (card) card.setAttribute('aria-current', 'step');
      }
      var beacon = pane.querySelector('.story-beacon-meter .small');
      if (beacon) beacon.textContent = beacon.textContent.replace(/1\\s*\\/\\s*5/g, '2 / 5');
      var bar = pane.querySelector('.story-beacon-bar span');
      if (bar) bar.style.width = '40%';
      var raft = pane.querySelector('.story-raft-meter');
      if (raft) raft.textContent = '2 / 5';
      replayDoor(second, 'bridge', '再玩一次');
      var play = pane.querySelector('[data-journey-play]');
      if (play) play.remove();          // games 3–5 are not built yet: nothing to press
      var launch = pane.querySelector('[data-journey-launch] .story-launch-note:not([data-journey-wait])');
      if (launch) launch.remove();
      var wait = pane.querySelector('[data-journey-wait]');
      if (wait) {
        wait.hidden = false;
        wait.textContent = wait.textContent.replace('遊戲 2', '遊戲 3');
      }
    }
    var tile = document.querySelector('#pane-home [data-badge-meter]');
    if (tile) tile.textContent = '2 / 5 個遊戲';
  });

  // the two demo accounts on the leaders' card: one tap each
  document.addEventListener('submit', function (event) {
    var form = event.target;
    var demo = form.querySelector ? form.querySelector('[data-demo]') : null;
    if (!demo) return;
    event.preventDefault();
    setupPending = false; // demo2 is an existing account, not first-time scout07
    go(demo.getAttribute('data-demo') === 'leader' ? 'leader' : 'home');
  });

  // Offline form: behave like the server's required onboarding gate, without
  // persisting a minor's password/email in this downloadable demo file.
  document.addEventListener('submit', function (event) {
    var form = event.target.closest('[data-offline-setup]');
    if (!form) return;
    event.preventDefault();
    var password = form.querySelector('[name="password"]').value.trim();
    var confirm = form.querySelector('[name="confirm"]').value.trim();
    var email = form.querySelector('[name="email"]').value.trim();
    var error = document.getElementById('offline-setup-error');
    var problem = password.length < 6 ? '密碼最少需要 6 個字。 Password must have at least 6 characters.'
      : password !== confirm ? '兩次輸入的密碼不同。 Passwords do not match.'
      : !/^[^\\s@]+@[^\\s@]+\\.[^\\s@]{2,}$/.test(email)
        ? '請填寫有效的聯絡電郵。 Enter a valid contact email.' : '';
    if (problem) {
      if (error) { error.textContent = problem; error.hidden = false; }
      return;
    }
    if (error) error.hidden = true;
    form.reset(); // never keep the values, including when returning to the pane
    setupPending = false;
    setupComplete = true;
    go('home');
  });

  // the leaders' card: 0082 opens the console, anything else is refused
  document.addEventListener('submit', function (event) {
    var form = event.target.closest('[data-leadercode]');
    if (!form) return;                       // other active forms have their own handlers
    event.preventDefault();
    var input = form.querySelector('input[name="password"]');
    var error = document.getElementById('offline-code-error');
    var code = (input && input.value || '').trim();
    if (code === '0082') {
      if (error) error.hidden = true;
      if (input) input.value = '';
      go('leader');
    } else {
      if (error) error.hidden = false;
      if (input) { input.value = ''; input.focus(); }
    }
  });

  document.addEventListener('click', function (event) {
    /* 建議: 顯示全部 / 收起 — the offline twin of static/js/scout.js */
    var sugg = event.target.closest('[data-suggest-toggle]');
    if (sugg) {
      var rest = document.getElementById('suggest-rest');
      if (rest) {
        var opening = rest.hidden;
        rest.hidden = !opening;
        sugg.setAttribute('aria-expanded', opening ? 'true' : 'false');
        sugg.textContent = opening ? sugg.getAttribute('data-label-less')
                                   : sugg.getAttribute('data-label-more');
      }
      return;
    }
    var nav = event.target.closest('[data-nav]');
    if (nav) {
      event.preventDefault();
      go(nav.getAttribute('data-nav'));
      return;
    }
    var dead = event.target.closest('[data-dead]');
    if (dead) {
      event.preventDefault();
      var note = document.getElementById('offline-note');
      if (note) {
        note.classList.add('is-on');
        window.clearTimeout(note._t);
        note._t = window.setTimeout(function () { note.classList.remove('is-on'); }, 2600);
      }
      return;
    }
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') back();
  });

  window.OFFLINE_DEMO = { go: go, back: back };
  go('scene');
})();
"""

images: dict[str, str] = {}
for path in sorted((ROOT / "static").rglob("*")):
    if path.suffix.lower() in (".webp", ".jpg", ".jpeg", ".png"):
        images["/static/" + path.relative_to(ROOT / "static").as_posix()] = data_uri(path)
for name in ("membership", "pathfinder", "standard", "advanced", "chief-scout"):
    art = ROOT / "static/img" / f"{name}.webp"
    if art.exists():
        images[f"/img/badges/{name}.webp"] = data_uri(art)

# Inline styles from server-rendered pages share the one offline stylesheet.
seen_css = []
for block in PAGE_CSS:
    if block not in seen_css:
        seen_css.append(block)
page_css_text = "\n".join(seen_css)          # one string, ready for the <style> block

parts: list[str] = []
parts.append(f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>童軍進度平台 · 離線示範 Scout Progress Platform · offline demo</title>
<!-- build: no-back-button · {{BUILD}} -->
<script>window.OFFLINE_DEMO_BUILD = "{{BUILD}}";</script>
<style>
{css}
/* ── per-page rules (moved out of the panes) ── */
{page_css_text}
/* ── the offline shell ── */
.pane[hidden] {{ display: none !important; }}
.pane-inner[hidden] {{ display: none !important; }}
/* the "this step needs the server" note: off the screen until a step really
   does need it, then it floats in for a moment and goes again */
.offline-note {{
  position: fixed; left: 50%; bottom: 1rem; transform: translate(-50%, 1.2rem);
  background: #1c2a24; color: #f3f7f3; border-radius: 999px; padding: .5rem .95rem;
  font-size: .86rem; box-shadow: 0 14px 30px rgba(0, 0, 0, .35);
  opacity: 0; pointer-events: none; transition: opacity .25s ease, transform .25s ease;
  z-index: 90;
}}
.offline-note.is-on {{ opacity: 1; transform: translate(-50%, 0); }}
</style>
<script>
{fx}
</script>
</head>
<body>
""")

for pid, title, body in panes:
    body_class = "scene-body" if pid == "scene" else ""
    parts.append(f'<div class="pane" id="pane-{pid}" data-title="{title}" data-body="{body_class}"'
                 '>\n'
                 f'<div class="pane-inner">\n{body}\n</div>\n</div>\n')

parts.append("""
<div class="offline-note" id="offline-note">離線示範：這一步需要連接伺服器 · this step needs the server</div>
<script>
""")
parts.append(router)
parts.append("</script>\n<script>\n")
parts.append(login_js)
parts.append("\n</script>\n<script>\n")
parts.append(cave_js)
parts.append("\n</script>\n<script>\n")
parts.append(bridge_js)
parts.append("\n</script>\n</body>\n</html>\n")

html = "".join(parts).replace("{BUILD}", BUILD)

# ── links: cross-pane ones become data-nav, everything else is switched off ─
def link(match: re.Match) -> str:
    tag = match.group(0)
    href = match.group(1)
    if "data-nav" in tag or 'href="#"' in tag:
        return tag
    if re.fullmatch(r"/login/scout/(Tiger|Otter|Seagull)", href):
        return tag.replace(f'href="{href}"', f'data-nav="names-{href.rsplit("/", 1)[1]}"')
    if re.fullmatch(r"/login/scout/(Tiger|Otter|Seagull)/[0-9a-f]{16}", href):
        # The one password-free name cannot open the existing scout's Home.
        destination = "setup" if href.rsplit("/", 1)[1] == first_scout["id"] else "home"
        return tag.replace(f'href="{href}"', f'data-nav="{destination}"')
    if href.startswith("/logout"):
        return tag.replace(f'href="{href}"', 'data-nav="scene"')  # wrong name? start over
    if href == "/login/leader":
        return tag.replace(f'href="{href}"', 'data-nav="leader-code"')   # the card, which asks for 0082
    if href == "/leader":
        return tag.replace(f'href="{href}"', 'data-nav="leader"')
    if href.startswith("http"):
        return tag                                    # the papers and folders are real links
    if href.startswith("#"):                              # anchors inside one pane still scroll
        return tag
    if href == "/" or href.startswith("/home"):
        return tag.replace(f'href="{href}"', 'data-nav="home"')     # 🏠 主頁, from anywhere
    if href.startswith("/history"):
        return tag.replace(f'href="{href}"', 'data-nav="history"')
    if href == "/badges" or href.startswith("/badges?"):
        return tag.replace(f'href="{href}"', 'data-nav="badges"')
    if href.startswith(f"/badges/{membership['id']}/requirements"):
        return tag.replace(f'href="{href}"', 'data-nav="guide"')         # the 11 items in full
    if href.startswith(f"/badges/{membership['id']}?intro=1"):
        return tag.replace(f'href="{href}"', 'data-nav="quest-intro"')   # the old 玩法 alias
    if href.startswith(f"/badges/{membership['id']}/start"):
        return tag.replace(f'href="{href}"', 'data-nav="cave"')   # legacy shortcut, no intermediate screen
    if href.startswith(f"/badges/{membership['id']}"):
        return tag.replace(f'href="{href}"', 'data-nav="quest-intro"')   # 會員章 → 玩法
    if href.startswith(f"/tasks/{cave_task['id']}"):
        return tag.replace(f'href="{href}"', 'data-nav="cave"')     # ✨ game 1
    if bridge_task is not None and href.startswith(f"/tasks/{bridge_task['id']}"):
        return tag.replace(f'href="{href}"', 'data-nav="bridge"')   # ✨ game 2
    return tag.replace(f'href="{href}"', 'href="#" data-dead="1"')


def switch_off_forms(markup: str) -> str:
    """Neuter server-backed forms; keep leader sign-in and local setup usable.

    The leader card's code (0082), its two demo buttons, and the first-time
    account form work without a server. All other forms (submissions, leader
    editors) stay switched off and explain why instead of failing silently.
    """

    def handle(match: re.Match) -> str:
        block = match.group(0)
        if any(key in block for key in ("data-leadercode", "data-demo", "data-offline-setup")):
            # keep it, and make sure its submit buttons still submit
            block = re.sub(r'(<button\b[^>]*?)\s+type="button"\s+data-dead="1"',
                           lambda m: m.group(1) + ' type="submit"', block)
            block = block.replace(' data-dead="1"', '') if "data-demo" in block else block
            return block
        block = re.sub(r"<form\b[^>]*>", '<form data-dead="1" onsubmit="return false">', block, count=1)
        block = re.sub(r'(<button\b[^>]*?)\s+type="submit"',
                       lambda m: m.group(1) + ' type="button" data-dead="1"', block)
        return block

    return re.sub(r"<form\b.*?</form>", handle, markup, flags=re.S)


html = re.sub(r'<a\b[^>]*href="([^"]+)"[^>]*>', link, html)
html = switch_off_forms(html)

# This file is meant to be shared, so no session token may travel in it: the
# ?sid=… the build used to render its pages is stripped. Nothing offline needs
# one — the cave grades locally and server-backed controls are switched off.
html = re.sub(r'([?&])sid=[^"&\s]+', lambda m: "" if m.group(1) == "?" else "", html)
assert "sid=" not in html, "a session token survived into the offline demo"
# the leader's rule for THIS file: no 返回 button anywhere (the live pages keep
# 「返回會員章」 on the cave's own bar — offline it reads 回到會員章, and the config
# the game reads carries the same words)
html = html.replace("返回會員章", "回到會員章")
assert "返回" not in html, "a back button slipped into the offline demo"

# ── images ────────────────────────────────────────────────────────────────
for src, uri in images.items():
    html = html.replace(f'src="{src}"', f'src="{uri}"')
html = re.sub(r'src="/(?!data:)[^"]+"', 'src=""', html)         # nothing left to fetch

out = pathlib.Path(os.environ.get("OFFLINE_OUTPUT_PATH") or ROOT / "demo-preview.html")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(html)
size = out.stat().st_size / 1024
left = len(re.findall(r'src="/(?!data:)', html))
print(f"{out.name} written — {size:,.0f} KB, {len(panes)} screens, "
      f"images inlined: {len(images)}, external fetches left: {left}")
