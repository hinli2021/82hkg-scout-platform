/**
 * Game layer — sound, motion, progress rings, particles, the first-visit tour.
 * (Python edition: plain script, no imports; every page is server-rendered, so
 *   this only decorates what the page already contains.)
 *
 * Rules it follows:
 *  • No XP, no levels. Everything decorates the badge ladder that already
 *    exists — points stay on the 獎品 page.
 *  • No network, no assets: sounds are synthesised with the Web Audio API and
 *    the art is SVG/CSS, so the platform works offline and inside sandboxes.
 *  • Everything degrades quietly: no AudioContext, blocked storage, reduced
 *    motion, a sandboxed iframe — the site still runs, just calmer.
 */
(function () {
  'use strict';

  var PREF_KEY = 'scout.sound';
  var TOUR_KEY = 'scout.tourDone';

  /* ── storage that never throws (sandboxed iframes block it) ───────────── */
  function getItem(key) {
    try { return window.localStorage.getItem(key); } catch (e) { return null; }
  }
  function setItem(key, value) {
    try { window.localStorage.setItem(key, value); } catch (e) { /* ignore */ }
  }

  /* ── small DOM helpers ───────────────────────────────────────────────── */
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (name) {
      if (name === 'class') node.className = attrs[name];
      else if (name === 'style') node.setAttribute('style', attrs[name]);
      else if (name.slice(0, 2) === 'on' && typeof attrs[name] === 'function') node.addEventListener(name.slice(2), attrs[name]);
      else node.setAttribute(name, attrs[name]);
    });
    (children || []).forEach(function (child) {
      if (child === null || child === undefined) return;
      node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
    });
    return node;
  }
  function clear(node) {
    while (node && node.firstChild) node.removeChild(node.firstChild);
    return node;
  }
  function lang() {
    return (document.documentElement.getAttribute('lang') || 'zh').slice(0, 2) === 'en' ? 'en' : 'zh';
  }
  function L(zh, en) { return lang() === 'en' ? (en || zh) : (zh || en); }

  /* ── sound ───────────────────────────────────────────────────────────── */
  var ctx = null;
  var pref = (function () {
    var saved = getItem(PREF_KEY);
    return saved === 'off' ? false : saved === 'on' ? true : null; // null → follow the unit default
  })();

  function soundOn() {
    if (pref !== null) return pref;
    try { return window.__scoutSoundDefault !== false; } catch (e) { return true; }
  }
  function setSound(on) {
    pref = !!on;
    setItem(PREF_KEY, pref ? 'on' : 'off');
    if (!pref) pauseMusic();
    if (pref) {
      sfx('tap');
      if (pageWantsMusic()) startMusic();
    }
    paintSoundToggle();
    return pref;
  }
  function toggleSound() { return setSound(!soundOn()); }

  function audio() {
    if (ctx) return ctx;
    try {
      var Ctor = window.AudioContext || window.webkitAudioContext;
      if (!Ctor) return null;
      ctx = new Ctor();
    } catch (e) { ctx = null; }
    return ctx;
  }

  function tone(freq, dur, opts) {
    opts = opts || {};
    var ac = audio();
    if (!ac) return;
    try {
      if (ac.state === 'suspended') ac.resume();
      var t0 = ac.currentTime + (opts.delay || 0);
      var osc = ac.createOscillator();
      var vol = ac.createGain();
      osc.type = opts.type || 'sine';
      osc.frequency.setValueAtTime(freq, t0);
      if (opts.sweep) osc.frequency.exponentialRampToValueAtTime(Math.max(60, opts.sweep), t0 + dur);
      vol.gain.setValueAtTime(0.0001, t0);
      vol.gain.exponentialRampToValueAtTime(opts.gain || 0.05, t0 + 0.012);
      vol.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
      osc.connect(vol).connect(ac.destination);
      osc.start(t0);
      osc.stop(t0 + dur + 0.02);
    } catch (e) { /* a sound is a bonus — never break an interaction */ }
  }

  var RECIPES = {
    tap: function () { tone(620, 0.07, { type: 'triangle', gain: 0.035 }); },
    type: function () { tone(440, 0.03, { type: 'square', gain: 0.012 }); },
    correct: function () { tone(784, 0.1, { gain: 0.05 }); tone(1175, 0.16, { gain: 0.045, delay: 0.09 }); },
    wrong: function () { tone(300, 0.22, { type: 'sawtooth', gain: 0.035, sweep: 150 }); },
    tick: function () { tone(880, 0.05, { type: 'triangle', gain: 0.03 }); },
    submit: function () { tone(523, 0.1, { gain: 0.04 }); tone(659, 0.14, { gain: 0.04, delay: 0.08 }); },
    unlock: function () { tone(320, 0.5, { type: 'triangle', gain: 0.05, sweep: 1180 }); },
    badge: function () { [523, 659, 784, 1046].forEach(function (f, i) { tone(f, 0.28, { gain: 0.05, delay: i * 0.11 }); }); },
    pop: function () { tone(420, 0.09, { type: 'triangle', gain: 0.04, sweep: 760 }); },
    place: function () { tone(330, 0.08, { type: 'triangle', gain: 0.045 }); tone(660, 0.12, { type: 'triangle', gain: 0.04, delay: 0.055 }); },
    flip: function () { tone(520, 0.06, { type: 'triangle', gain: 0.03, sweep: 980 }); tone(880, 0.08, { type: 'triangle', gain: 0.025, delay: 0.05 }); },
    sparkle: function () { [1320, 1760, 2210].forEach(function (f, i) { tone(f, 0.12, { type: 'sine', gain: 0.022, delay: i * 0.055 }); }); },
    win: function () { [523, 659, 784, 1046, 1318].forEach(function (f, i) { tone(f, 0.24, { type: 'triangle', gain: 0.045, delay: i * 0.09 }); }); },
    fanfare: function () {
      [392, 523, 659, 784].forEach(function (f, i) { tone(f, 0.22, { type: 'triangle', gain: 0.05, delay: i * 0.1 }); });
      [1046, 1318].forEach(function (f, i) { tone(f, 0.38, { type: 'triangle', gain: 0.045, delay: 0.42 + i * 0.1 }); });
    }
  };

  function sfx(name) {
    if (!soundOn()) return;
    var recipe = RECIPES[name];
    if (recipe) recipe();
  }

  /* ── background music ──────────────────────────────────────────────────
     A short cheerful tune, synthesised note by note — no music file, so it
     works offline. It only plays on game pages (the four member-badge games
     carry `is-game`; the daily challenge and the cards page ask for it with
     `data-music`). Browsers will not let a page make sound before the scout
     touches it, so the tune waits for the first tap or key press, then
     loops quietly underneath the sound effects. The 🔊 button in the top
     bar switches music and effects off together. */
  var MUSIC_STEP = 0.24;               // eighth notes at about 125 bpm
  var MUSIC_CHORDS = [                 // C – G – Am – F, sixteen steps each
    { bass: 130.81, fifth: 196.00 },
    { bass: 98.00, fifth: 146.83 },
    { bass: 110.00, fifth: 164.81 },
    { bass: 87.31, fifth: 130.81 }
  ];
  var MUSIC_MELODY = [
    659, 784, 1046, 784, 880, 784, 659, 784, 1046, 784, 659, 587, 659, 0, 784, 0,
    587, 784, 988, 784, 880, 784, 587, 784, 988, 784, 587, 659, 784, 0, 587, 0,
    659, 880, 1046, 880, 784, 659, 523, 659, 880, 1046, 1318, 1046, 880, 0, 784, 659,
    698, 880, 1046, 880, 784, 659, 587, 659, 523, 659, 784, 659, 587, 0, 0, 0
  ];
  var musicTimer = null;
  var musicStep = 0;
  var musicNextAt = 0;
  var musicWanted = false;

  function musicPlaying() { return musicTimer !== null; }

  function scheduleMusic() {
    var ac = audio();
    if (!ac || ac.state !== 'running') return;
    /* the clock stood still while the browser held the sound back — do not
       try to play every missed note at once */
    if (musicNextAt < ac.currentTime - 0.1) musicNextAt = ac.currentTime + 0.05;
    while (musicNextAt < ac.currentTime + 0.45) {
      var delay = Math.max(0, musicNextAt - ac.currentTime);
      var step = musicStep % MUSIC_MELODY.length;
      var chord = MUSIC_CHORDS[Math.floor(step / 16) % MUSIC_CHORDS.length];
      var note = MUSIC_MELODY[step];
      if (note) tone(note, 0.19, { type: 'triangle', gain: 0.02, delay: delay });
      if (step % 8 === 0) tone(chord.bass, 0.34, { type: 'sine', gain: 0.032, delay: delay });
      if (step % 8 === 4) tone(chord.fifth, 0.3, { type: 'sine', gain: 0.026, delay: delay });
      if (step % 4 === 2) tone(1900, 0.03, { type: 'triangle', gain: 0.005, delay: delay });
      musicStep += 1;
      musicNextAt += MUSIC_STEP;
    }
  }

  function startMusic() {
    musicWanted = true;
    if (!soundOn() || musicTimer !== null) return;
    var ac = audio();
    if (!ac) return;
    musicStep = 0;
    musicNextAt = ac.currentTime + 0.06;
    musicTimer = window.setInterval(scheduleMusic, 120);
    scheduleMusic();
  }

  function pauseMusic() {
    if (musicTimer !== null) { window.clearInterval(musicTimer); musicTimer = null; }
  }

  function stopMusic() {
    musicWanted = false;
    pauseMusic();
  }

  function pageWantsMusic() {
    return !!(document.body && (document.body.classList.contains('is-game')
      || document.body.getAttribute('data-music') === 'game'));
  }

  /* ── motion ──────────────────────────────────────────────────────────── */
  function reducedMotion() {
    try { return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); }
    catch (e) { return false; }
  }

  function enter(node, index) {
    if (!node || reducedMotion()) return node;
    if (index) node.style.setProperty('--i', String(Math.min(index, 12)));
    node.classList.add('enter');
    return node;
  }

  /** Numbers that count up (overall %, points balance). */
  function countUp(node, to, opts) {
    if (!node) return;
    opts = opts || {};
    var ms = opts.ms || 700;
    var suffix = opts.suffix || '';
    var target = Number(to) || 0;
    if (reducedMotion() || typeof requestAnimationFrame !== 'function') {
      node.textContent = target + suffix;
      return;
    }
    // Read the clock ourselves — some environments use a different epoch for
    // the rAF timestamp, which used to freeze these numbers at 0.
    var clock = function () { return (typeof performance !== 'undefined' ? performance.now() : Date.now()); };
    var t0 = clock();
    var step = function () {
      var p = Math.max(0, Math.min(1, (clock() - t0) / ms));
      var eased = Math.max(0, 1 - Math.pow(1 - p, 3));
      node.textContent = Math.round(target * eased) + suffix;
      if (p < 1) requestAnimationFrame(step);
      else node.textContent = target + suffix;
    };
    requestAnimationFrame(step);
  }

  /** Circular progress ring (SVG). */
  function ring(percent, opts) {
    opts = opts || {};
    var size = opts.size || 96;
    var stroke = opts.stroke || 9;
    var toneName = opts.tone || 'green';
    var p = Math.max(0, Math.min(100, Math.round(Number(percent) || 0)));
    var r = (size - stroke) / 2;
    var c = 2 * Math.PI * r;
    var NS = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', '0 0 ' + size + ' ' + size);
    svg.setAttribute('width', String(size));
    svg.setAttribute('height', String(size));
    svg.setAttribute('class', 'ring tone-' + toneName);
    function mk(cls) {
      var circle = document.createElementNS(NS, 'circle');
      circle.setAttribute('cx', String(size / 2));
      circle.setAttribute('cy', String(size / 2));
      circle.setAttribute('r', String(r));
      circle.setAttribute('fill', 'none');
      circle.setAttribute('stroke-width', String(stroke));
      circle.setAttribute('class', cls);
      return circle;
    }
    var fill = mk('ring-fill');
    fill.setAttribute('stroke-dasharray', String(c));
    fill.setAttribute('stroke-dashoffset', String(c));
    fill.setAttribute('stroke-linecap', 'round');
    fill.setAttribute('transform', 'rotate(-90 ' + size / 2 + ' ' + size / 2 + ')');
    svg.appendChild(mk('ring-track'));
    svg.appendChild(fill);

    var centre = opts.centre ? el('strong', {}, [opts.centre]) : el('strong', {}, [p + '%']);
    var wrap = el('div', { class: 'ring-wrap' + (toneName === 'brass' ? ' is-brass' : '') }, [
      svg,
      el('div', { class: 'ring-centre' }, [centre, opts.sub ? el('span', { class: 'ring-sub' }, [opts.sub]) : null])
    ]);
    var paint = function () { fill.setAttribute('stroke-dashoffset', String(c * (1 - p / 100))); };
    if (typeof requestAnimationFrame === 'function' && !reducedMotion()) {
      requestAnimationFrame(function () { requestAnimationFrame(paint); });
    } else { paint(); }
    return wrap;
  }

  /** Fills every <span data-ring="56"> placeholder a template leaves behind. */
  function hydrateRings(root) {
    (root || document).querySelectorAll('[data-ring]').forEach(function (node) {
      var percent = node.getAttribute('data-ring');
      var size = Number(node.getAttribute('data-ring-size')) || 96;
      var toneName = node.getAttribute('data-ring-tone') || 'green';
      var sub = node.getAttribute('data-ring-sub') || null;
      node.appendChild(ring(percent, { size: size, tone: toneName, sub: sub }));
      node.classList.add('ring-slot');
    });
  }

  function hydrateCounters(root) {
    (root || document).querySelectorAll('[data-countup]').forEach(function (node) {
      countUp(node, node.getAttribute('data-countup'), { suffix: node.getAttribute('data-countup-suffix') || '' });
    });
  }

  /** A short particle burst around an element (task complete, badge unlock). */
  function burst(anchor, count, emojis) {
    if (!anchor || !anchor.getBoundingClientRect || reducedMotion()) return;
    var rect = anchor.getBoundingClientRect();
    if (!rect.width && !rect.height) return; // hidden element
    count = count || 14;
    emojis = emojis || ['✨', '⭐', '🎉'];
    var root = document.getElementById('fx-root') || document.body;
    for (var i = 0; i < count; i++) {
      (function (i) {
        var node = el('span', {
          class: 'fx-bit',
          style: 'left:' + (rect.left + rect.width / 2) + 'px;' +
                 'top:' + (rect.top + rect.height / 2) + 'px;' +
                 '--dx:' + ((Math.random() - 0.5) * 220) + 'px;' +
                 '--dy:' + (-40 - Math.random() * 140) + 'px;' +
                 '--rot:' + ((Math.random() - 0.5) * 240) + 'deg;' +
                 'animation-delay:' + (Math.random() * 0.12) + 's'
        }, [emojis[i % emojis.length]]);
        root.appendChild(node);
        setTimeout(function () { node.remove(); }, 1100);
      })(i);
    }
  }

  /** Ripple + press feedback for anything tappable. */
  function pressable(node, opts) {
    if (!node || node.dataset.pressable === '1') return node;
    opts = opts || {};
    node.dataset.pressable = '1';
    node.classList.add('pressable');
    node.addEventListener('pointerdown', function (ev) {
      node.classList.add('pressed');
      if (opts.sound !== false) sfx(opts.sound || 'tap');
      if (reducedMotion() || !node.getBoundingClientRect) return;
      var rect = node.getBoundingClientRect();
      if (!rect.width) return;
      var dot = el('span', {
        class: 'ripple',
        style: 'left:' + ((ev.clientX || rect.left + rect.width / 2) - rect.left) + 'px;' +
               'top:' + ((ev.clientY || rect.top + rect.height / 2) - rect.top) + 'px;'
      });
      node.appendChild(dot);
      setTimeout(function () { dot.remove(); }, 560);
    });
    ['pointerup', 'pointercancel', 'pointerleave'].forEach(function (name) {
      node.addEventListener(name, function () { node.classList.remove('pressed'); });
    });
    return node;
  }

  /* ── first-visit tour (once per device, scout pages only) ────────────── */
  var TOUR_STEPS = [
    {
      emoji: '🎖',
      zh: ['這是你的獎章旅程', '每格是一個獎章。點一下打開，完成裡面的任務就可以考獲。'],
      en: ['This is your badge journey', 'Each tile is an award. Tap one to open it — finish the tasks inside to earn it.'],
      href: function (urls) { return urls.badges; }
    },
    {
      emoji: '🗺️',
      zh: ['「獎章」頁是一條路線', '看得到自己走到哪裡、下一個獎章還差多少。順序完成就自動考獲。'],
      en: ['The Badges page is the trail', 'See where you are and how far the next award is. Finish in order and it is awarded automatically.'],
      href: function (urls) { return urls.home; }
    },
    {
      emoji: '🔥',
      zh: ['每天完成一件事', '連續活躍會累積火苗，龍虎榜按考獲獎章排名 — 看看你的小隊在哪裡！'],
      en: ['Do one thing a day', 'Consecutive days build a streak. The leaderboard ranks earned badges — see where your patrol is!'],
      needs: 'leaderboard',                       // skipped while the board is hidden
      href: function (urls) { return urls.leaderboard; }
    }
  ];

  // Steps whose feature is switched off simply do not appear in the tour.
  function tourSteps(urls) {
    return TOUR_STEPS.filter(function (step) { return !step.needs || !!urls[step.needs]; });
  }

  function maybeShowTour(urls) {
    if (getItem(TOUR_KEY) === '1') return false;
    if (!urls || !urls.home) return false;
    if (document.getElementById('tour-root')) return false; // never stack two tours

    var steps = tourSteps(urls);
    var i = 0;
    var root = el('div', { class: 'tour-backdrop', id: 'tour-root' });
    var card = el('div', { class: 'tour-card' });
    root.appendChild(card);

    function finish() {
      setItem(TOUR_KEY, '1');
      root.remove();
      document.removeEventListener('keydown', onKey);
    }
    function onKey(ev) { if (ev.key === 'Escape') finish(); }

    function paint() {
      var step = steps[i];
      clear(card).appendChild(el('div', {}, [
        el('div', { class: 'tour-emoji' }, [step.emoji]),
        el('h2', {}, [L(step.zh[0], step.en[0])]),
        el('p', { class: 'muted' }, [L(step.zh[1], step.en[1])]),
        el('div', { class: 'tour-dots' }, steps.map(function (_, k) {
          return el('span', { class: 'tour-dot' + (k === i ? ' on' : '') });
        })),
        el('div', { class: 'row' }, [
          el('button', { class: 'btn ghost', type: 'button', onclick: finish }, [L('略過', 'Skip')]),
          el('button', {
            class: 'btn primary grow', type: 'button',
            onclick: function () {
              sfx('tap');
              if (i === steps.length - 1) { finish(); return; }
              var target = step.href(urls);
              i += 1;
              if (target) { window.location.href = target; return; } // real page, real URL
              paint();
            }
          }, [L('下一步', 'Next')])
        ])
      ]));
    }

    paint();
    document.body.appendChild(root);
    document.addEventListener('keydown', onKey);
    return true;
  }

  function resetTour() { setItem(TOUR_KEY, '0'); }

  /* ── HUD sound toggle ────────────────────────────────────────────────── */
  function paintSoundToggle() {
    document.querySelectorAll('[data-sound-toggle]').forEach(function (button) {
      var on = soundOn();
      button.textContent = on ? '🔊' : '🔇';
      button.classList.toggle('off', !on);
      button.setAttribute('aria-pressed', on ? 'true' : 'false');
      button.title = on ? L('遊戲音樂與音效：開', 'Game music and sound: on') : L('遊戲音樂與音效：關', 'Game music and sound: off');
    });
  }

  /* ── boot: decorate whatever this page rendered ──────────────────────── */
  function init() {
    document.querySelectorAll('.card, .stat, .badge-tile, .quest-node, .chest, .lb-row').forEach(function (node, i) {
      enter(node, i);
    });
    hydrateRings();
    hydrateCounters();
    document.querySelectorAll('.btn, .badge-tile, .quest-node, .chest, .pill, .name-tile').forEach(function (node) {
      pressable(node);
    });
    document.querySelectorAll('[data-sound-toggle]').forEach(function (button) {
      button.addEventListener('click', function () { toggleSound(); });
    });
    /* 窄畫面的漢堡選單：按一下開合，按連結、按外面或按 Esc 都會收起 */
    document.querySelectorAll('[data-nav-toggle]').forEach(function (button) {
      var menu = document.getElementById(button.getAttribute('aria-controls') || '');
      if (!menu) return;
      function setOpen(open) {
        menu.classList.toggle('open', open);
        button.setAttribute('aria-expanded', open ? 'true' : 'false');
        button.textContent = open ? '✕' : '☰';
      }
      button.addEventListener('click', function (ev) {
        ev.stopPropagation();
        setOpen(!menu.classList.contains('open'));
      });
      menu.addEventListener('click', function (ev) {
        if (ev.target.closest && ev.target.closest('a')) setOpen(false);
      });
      document.addEventListener('click', function (ev) {
        if (menu.classList.contains('open') && !menu.contains(ev.target)) setOpen(false);
      });
      document.addEventListener('keydown', function (ev) {
        if (ev.key === 'Escape') setOpen(false);
      });
    });
    paintSoundToggle();
    /* game pages get the background tune: it starts on the scout's first
       tap or key press (the browser insists on one), pauses while the tab
       is hidden, and stops for good when the sound button is switched off */
    if (pageWantsMusic()) {
      musicWanted = true;
      var kickMusic = function () { if (musicWanted && soundOn()) startMusic(); };
      document.addEventListener('pointerdown', kickMusic);
      document.addEventListener('keydown', kickMusic);
      document.addEventListener('visibilitychange', function () {
        if (document.hidden) pauseMusic();
        else if (musicWanted && soundOn()) startMusic();
      });
      startMusic();
    }
    initStageBoard();
    if (document.body.dataset.tour === '1') {
      maybeShowTour({
        home: document.body.dataset.urlHome,
        badges: document.body.dataset.urlBadges,
        leaderboard: document.body.dataset.urlLeaderboard
      });
    }
  }

  /* ── the adventure's stage board: pick a stage, its card opens ──────────
     The board is plain radios inside labels, so picking one — and the card
     under it swapping over — works with CSS alone, offline included. This only
     adds the polish the sign-in page has: a spark off the chip you tapped, and
     the card sliding up into view. Bound once per board, because the offline
     file re-runs init() every time a pane is shown. */
  function initStageBoard() {
    document.querySelectorAll('[data-stage-picker]').forEach(function (board) {
      if (board.dataset.stageBound === '1') return;
      board.dataset.stageBound = '1';
      board.addEventListener('change', function (ev) {
        var radio = ev.target;
        if (!radio || radio.name !== 'stage-preview') return;
        var label = board.querySelector('label[for="' + radio.id + '"]');
        if (label) burst(label, 12, ['⭐', '✨', '🧭']);
        sfx('tap');
        var panel = board.querySelector('.stage-panel[data-stage-panel="' + radio.value + '"]');
        if (panel && panel.scrollIntoView) {
          try {
            panel.scrollIntoView({ block: 'nearest', behavior: reducedMotion() ? 'auto' : 'smooth' });
          } catch (e) { /* an old browser just stays where it is */ }
        }
      });
    });
  }

  /* ── anything that says [data-cheer] throws a little party when tapped ──
     The adventure's how-to-play cards and its stage board use this: tap a card
     or a stage and a few sparks fly off it, the same way the sign-in animals
     cheer when a scout picks one. Emojis come from the attribute, so a page can
     choose its own (data-cheer="⭐,🎒"). It is pure decoration — with JavaScript
     off (or reduced motion on) the tap still does its real job. */
  function cheer(node) {
    if (!node) return;
    var emojis = (node.getAttribute('data-cheer') || '✨,⭐,🎉').split(',').filter(Boolean);
    burst(node, 12, emojis);
    sfx('tap');
  }

  document.addEventListener('click', function (ev) {
    var node = ev.target.closest ? ev.target.closest('[data-cheer]') : null;
    if (node) cheer(node);
  });

  window.FX = {
    sfx: sfx, soundOn: soundOn, setSound: setSound, toggleSound: toggleSound,
    music: { start: startMusic, stop: stopMusic, playing: musicPlaying },
    reducedMotion: reducedMotion, enter: enter, countUp: countUp, ring: ring,
    burst: burst, pressable: pressable, maybeShowTour: maybeShowTour, resetTour: resetTour,
    hydrateRings: hydrateRings, hydrateCounters: hydrateCounters, L: L, lang: lang
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
