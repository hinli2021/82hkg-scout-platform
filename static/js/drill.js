/* ── 步操訓練場 — 第 6 項的第三個遊戲 ────────────────────────────────────────
   Section 1 · the fall-in hand signs, played on the cliff face. The way
   down collapsed long ago; what is left is a row of ancient mechanisms,
   carved with a scout making the hand signs of the leader's 《步操手冊》.

   Each stage opens on the flip cards — the stage's new signs shown big and
   clear, tap one to turn it over and see the formation it calls for. When
   the scout is ready the mechanism wakes: the rock shows a sign, a beat bar
   drains the movement's count (打數), and the formation must be pressed
   from the square buttons below — inside the count, with everything on the
   screen and nothing to scroll. A wrong press or a late one is never told
   the answer: the card opens again as the review and the sign rejoins the
   back of the queue. Two stages — 3 new signs first, then 4, with the
   second stage's mechanism mixing all 7 — and both flights of steps are
   out: section 1 is done.

   Down the steps is section 2, the drill movements on the parade ground:
   three stages of movement cards first (command, count and key points),
   then the command mechanism calls a command and the right movement must
   be pressed inside the count. Each stage mixes in every movement learned
   before it in section 2. Only when both sections are cleared is the
   studying filed; then the leader assesses the scout in person and the
   leader's code (82DR) finishes game 3. A scout who has already studied
   or finished re-opens straight onto the assess card.

   The same shape as cave.js and bridge.js on purpose: one browser-side
   state machine, the route hands over every word and picture, so the
   identical game plays inside the offline demo file, with the same exit
   warning.
*/
(function () {
  'use strict';

  function isEn() { return document.documentElement.lang === 'en'; }
  function pick(zh, en) { return isEn() && en ? en : (zh || ''); }
  function esc(text) {
    return String(text == null ? '' : text)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function fill(text, values) {
    return String(text == null ? '' : text).replace(/\{(\w+)\}/g, function (all, key) {
      return values[key] === undefined ? all : values[key];
    });
  }
  function tap() { if (window.FX && FX.sfx) { try { FX.sfx('tap'); } catch (e) {} } }
  function chime() { if (window.FX && FX.sfx) { try { FX.sfx('unlock'); } catch (e) {} } }
  function thud() { if (window.FX && FX.sfx) { try { FX.sfx('wrong'); } catch (e) {} } }
  function burstOn(node, emojis) {
    if (node && window.FX && FX.burst) { try { FX.burst(node, 16, emojis); } catch (e) {} }
  }
  function shuffled(list) {
    var out = list.slice();
    for (var i = out.length - 1; i > 0; i -= 1) {
      var j = Math.floor(Math.random() * (i + 1));
      var swap = out[i]; out[i] = out[j]; out[j] = swap;
    }
    return out;
  }

  /* The formation diagrams — seven dots-and-spaces pictures, one to a sign,
     drawn inline so no asset is fetched. The detailed version (the flip-card
     backs and the review) adds the manual's green ▼ for where the leader /
     commander stands: front-and-centre for most formations, and directly in
     front of the tallest scout for the height-ordered line. */
  function formationSvg(id, detailed) {
    var dot = function (x, y, r) {
      return '<circle cx="' + x + '" cy="' + y + '" r="' + (r || 3.1) + '"/>';
    };
    var row = function (y, xs, r) { return xs.map(function (x) { return dot(x, y, r); }).join(''); };
    var arts = {
      'sign-line': function () { return row(18, [6, 12, 18, 24, 30]); },
      'sign-line-tall': function () {
        /* smallest to tallest, as in the manual's diagram — the leader faces
           the tallest scout at the right-hand end */
        return dot(6, 18, 1.9) + dot(12, 18, 2.5) + dot(18, 18, 3.1) + dot(24, 18, 3.8) + dot(30, 18, 4.4);
      },
      'sign-columns': function () {
        return row(8, [14, 22]) + row(18, [14, 22]) + row(28, [14, 22]);
      },
      'sign-open-order': function () { return row(9, [6, 12, 18, 24, 30]) + row(27, [6, 12, 18, 24, 30]); },
      'sign-close-order': function () { return row(13, [6, 12, 18, 24, 30]) + row(23, [6, 12, 18, 24, 30]); },
      'sign-horseshoe': function () {
        return dot(10, 6) + dot(10, 15) + dot(12, 25) + dot(18, 29) + dot(24, 25) + dot(26, 15) + dot(26, 6);
      },
      'sign-open-square': function () {
        return dot(8, 7) + dot(8, 16) + dot(8, 25) + dot(15, 25) + dot(22, 25) + dot(29, 25) + dot(29, 16) + dot(29, 7);
      }
    };
    var body = (arts[id] || arts['sign-line'])();
    if (!detailed) {
      return '<svg class="drill-form-art" viewBox="0 0 36 36" aria-hidden="true" focusable="false">' +
             body + '</svg>';
    }
    /* in the 36-unit drawing the leader stands above the formation: centre
       (x=18) for most signs, above the tallest scout (x=30) for line-tall */
    var leaderX = (id === 'sign-line-tall' ? 30 : 18) + 6;
    var leader = '<polygon class="drill-form-leader" points="' +
      (leaderX - 4.2) + ',0.8 ' + (leaderX + 4.2) + ',0.8 ' + leaderX + ',7.2"/>';
    return '<svg class="drill-form-art is-detailed" viewBox="0 0 48 48" aria-hidden="true" focusable="false">' +
           leader + '<g transform="translate(6 9)">' + body + '</g></svg>';
  }

  /* Section 2's little movement diagrams: gold footprints, green direction
     arrows and one clear cue per movement. They are deliberately schematic —
     the manual page and the leader's demonstration carry the exact footwork. */
  function movementSvg(id, detailed) {
    var foot = function (x, y, rotate, cls) {
      return '<ellipse class="' + (cls || 'move-foot') + '" cx="' + x + '" cy="' + y +
             '" rx="3.1" ry="5.2" transform="rotate(' + (rotate || 0) + ' ' + x + ' ' + y + ')"/>';
    };
    var arrow = function (points) {
      return '<polygon class="move-arrow" points="' + points + '"/>';
    };
    var line = function (points, cls) {
      return '<polyline class="' + (cls || 'move-line') + '" points="' + points + '"/>';
    };
    var path = function (d, cls) {
      return '<path class="' + (cls || 'move-line') + '" d="' + d + '"/>';
    };
    var centreFeet = foot(20, 28, -18) + foot(28, 28, 18);
    var arts = {
      'alert': function () {
        return '<line class="move-guide" x1="24" y1="5" x2="24" y2="42"/>' +
               '<circle class="move-dot" cx="24" cy="9" r="3.4"/>' +
               line('24,13 24,24') + foot(20, 34, -30) + foot(28, 34, 30);
      },
      'stand-at-ease': function () {
        return foot(13, 33, -12) + foot(35, 33, 12) +
               '<line class="move-guide" x1="13" y1="42" x2="35" y2="42"/>' +
               arrow('13,39.5 18,42 13,44.5') + arrow('35,39.5 30,42 35,44.5') +
               '<circle class="move-dot" cx="24" cy="9" r="3.4"/>' + line('24,13 24,25');
      },
      'salute-front': function () {
        return '<circle class="move-dot" cx="22" cy="10" r="4"/>' +
               line('22,15 22,34') + line('22,34 17,43') + line('22,34 27,43') +
               line('22,19 34,19 29,8') + '<circle class="move-green-dot" cx="27" cy="8" r="2"/>';
      },
      'pace-forward': function () { return centreFeet + arrow('24,3 31,13 27,13 27,21 21,21 21,13 17,13'); },
      'pace-backward': function () { return centreFeet + arrow('24,45 17,35 21,35 21,27 27,27 27,35 31,35'); },
      'pace-left': function () { return centreFeet + arrow('3,24 13,17 13,21 21,21 21,27 13,27 13,31'); },
      'pace-right': function () { return centreFeet + arrow('45,24 35,31 35,27 27,27 27,21 35,21 35,17'); },
      'pacing': function () {
        return centreFeet +
               arrow('24,2 29,9 26,9 26,15 22,15 22,9 19,9') +
               arrow('24,46 19,39 22,39 22,33 26,33 26,39 29,39') +
               arrow('2,24 9,19 9,22 15,22 15,26 9,26 9,29') +
               arrow('46,24 39,29 39,26 33,26 33,22 39,22 39,19');
      },
      'right-turn': function () {
        return '<circle class="move-dot" cx="24" cy="24" r="3"/>' +
               path('M14 31 A12 12 0 0 1 35 20') + arrow('35,14 40,23 30,24');
      },
      'left-turn': function () {
        return '<circle class="move-dot" cx="24" cy="24" r="3"/>' +
               path('M34 31 A12 12 0 0 0 13 20') + arrow('13,14 8,23 18,24');
      },
      'about-turn': function () {
        return '<circle class="move-dot" cx="24" cy="24" r="3"/>' +
               path('M13 27 A11 11 0 1 1 35 27') + arrow('35,20 41,29 31,31');
      },
      'mark-time': function () {
        return '<line class="move-guide" x1="7" y1="40" x2="41" y2="40"/>' +
               foot(16, 34, -8) + foot(32, 22, 8) +
               arrow('32,5 37,13 34,13 34,18 30,18 30,13 27,13');
      },
      'quick-march': function () {
        return foot(12, 38, -28) + foot(21, 29, 24) + foot(29, 20, -22) + foot(36, 12, 20) +
               arrow('42,3 45,12 38,9 36,15 33,11 39,9');
      },
      'halt': function () {
        return '<polygon class="move-stop" points="18,4 30,4 38,12 38,24 30,32 18,32 10,24 10,12"/>' +
               '<line class="move-stop-line" x1="16" y1="18" x2="32" y2="18"/>' +
               foot(20, 41, -18) + foot(28, 41, 18);
      },
      'right-dress': function () {
        return '<line class="move-guide" x1="7" y1="34" x2="39" y2="34"/>' +
               '<circle class="move-dot" cx="10" cy="28" r="3.2"/>' +
               '<circle class="move-dot" cx="19" cy="28" r="3.2"/>' +
               '<circle class="move-dot" cx="28" cy="28" r="3.2"/>' +
               '<circle class="move-green-dot" cx="37" cy="28" r="3.6"/>' +
               arrow('45,12 36,17 36,14 18,14 18,20 36,20 36,17') +
               '<line class="move-green-line" x1="41" y1="8" x2="41" y2="38"/>';
      }
    };
    var body = (arts[id] || arts.alert)();
    return '<svg class="drill-move-art' + (detailed ? ' is-detailed' : '') +
           '" viewBox="0 0 48 48" aria-hidden="true" focusable="false">' + body + '</svg>';
  }

  function mountOne(root) {
    if (!root || root.getAttribute('data-drill-bound') === '1') return;
    var cfg = null;
    try { cfg = JSON.parse(root.getAttribute('data-drill-config') || '{}'); } catch (e) { cfg = null; }
    if (!cfg || !cfg.sections || !cfg.sections.length) return;
    root.setAttribute('data-drill-bound', '1');

    var L = cfg.labels || {};
    var art = root.querySelector('.cave-art');
    var backdrop = root.querySelector('.cave-art-backdrop');
    var card = root.querySelector('[data-drill-card]');
    var moreCue = root.querySelector('[data-drill-more]');
    var panel = card ? card.parentElement : null;
    var progress = root.querySelector('[data-drill-progress]');
    var sections = cfg.sections;
    var totalMoves = 0;
    sections.forEach(function (s) { totalMoves += (s.moves || []).length; });

    /* the play itself: section 1's sign stages, then section 2's three
       movement stages. Each list names only that stage's new prompts; the
       mechanism pool is cumulative inside its own section. */
    var game = cfg.game || {};
    var signStages = (game.sign_stages || []).filter(function (row) { return row && row.length; });
    if (!signStages.length) {
      signStages = [allMoves().filter(function (m) { return !m.command; }).map(function (m) { return m.id; })];
    }
    var movementStages = (game.movement_stages || []).filter(function (row) { return row && row.length; });
    var allSigns = cumulativePool(signStages.length - 1);
    var allMovements = cumulativeMovementPool(movementStages.length - 1);
    var requiredMoves = allSigns.concat(allMovements.filter(function (m) {
      return !allSigns.some(function (sign) { return sign.id === m.id; });
    }));

    /* every page of the manual waits in the hidden block, keyed by name; the
       ridge painting stands behind the cards that carry no page of their own */
    var urls = {};
    var firstArt = root.querySelector('.cave-picture .cave-art');
    if (firstArt) urls[firstArt.getAttribute('data-drill-art') || 'ridge'] = firstArt.getAttribute('src');
    Array.prototype.forEach.call(root.querySelectorAll('.cave-sources [data-drill-art]'),
      function (node) { urls[node.getAttribute('data-drill-art')] = node.getAttribute('src'); });
    function artUrl(name) { return urls[name] || ''; }
    function ridgeArt() { return (cfg.intro || {}).image || 'ridge'; }

    var storeKey = 'drill-manual-' + (cfg.task_id || 'demo');
    var answers = {};            /* move id → its check's answer, once passed in time */
    try {
      var saved = JSON.parse(window.localStorage.getItem(storeKey) || '{}');
      if (saved && typeof saved === 'object') answers = saved;
    } catch (e) { answers = {}; }
    function sanitize() {
      /* a leader may have rewritten the checks since this browser last
         visited: any stored answer that no longer matches is dropped, so the
         scout re-drills the changed sign */
      sections.forEach(function (s) {
        (s.moves || []).forEach(function (m) {
          var check = m.check || {};
          if (answers[m.id] !== undefined && answers[m.id] !== check.answer) delete answers[m.id];
        });
      });
      save();
    }
    function save() {
      try { window.localStorage.setItem(storeKey, JSON.stringify(answers)); } catch (e) {}
    }
    sanitize();

    var state = {
      scene: 'intro',            /* intro · flip · drill · review · stage-done ·
                                    section-done · studied · result · save-error */
      section: 1,                /* 1 = hand signs on the cliff; 2 = movements below */
      stage: 0,
      queue: [],                 /* sign ids still to answer this stage run */
      forms: [],                 /* the square formation buttons, this stage */
      current: null,
      busy: false,
      ticked: false              /* the code has been accepted in this session */
    };

    /* the beat timers: one tick for the bar, one for the auto-advance after a
       right answer. say() clears both, so no timer ever outlives its card */
    var beatTimer = null;
    var advanceTimer = null;
    var statueTimer = null;
    function clearTimers() {
      if (beatTimer) { window.clearInterval(beatTimer); beatTimer = null; }
      if (advanceTimer) { window.clearTimeout(advanceTimer); advanceTimer = null; }
      if (statueTimer) { window.clearInterval(statueTimer); statueTimer = null; }
    }

    function movesOfSection(i) { return sections[i].moves || []; }
    function allMoves() {
      var list = [];
      sections.forEach(function (s) { (s.moves || []).forEach(function (m) { list.push(m); }); });
      return list;
    }
    function moveById(id) {
      var found = null;
      allMoves().forEach(function (m) { if (m.id === id) found = m; });
      return found;
    }
    function cumulativeFrom(stageLists, stageIndex) {
      var ids = [];
      for (var i = 0; i <= stageIndex && i < stageLists.length; i += 1) {
        (stageLists[i] || []).forEach(function (id) { if (ids.indexOf(id) < 0) ids.push(id); });
      }
      return ids.map(moveById).filter(function (m) { return m; });
    }
    function cumulativePool(stageIndex) { return cumulativeFrom(signStages, stageIndex); }
    function cumulativeMovementPool(stageIndex) { return cumulativeFrom(movementStages, stageIndex); }
    function activeStageLists() { return state.section === 2 ? movementStages : signStages; }
    function activePool(stageIndex) {
      return state.section === 2 ? cumulativeMovementPool(stageIndex) : cumulativePool(stageIndex);
    }
    function movePassed(m) { return answers[m.id] !== undefined; }
    function signsDone() { return allSigns.filter(movePassed).length; }
    function movementsDone() { return allMovements.filter(movePassed).length; }
    function section1Passed() { return allSigns.length > 0 && allSigns.every(movePassed); }
    function section2Passed() { return allMovements.length > 0 && allMovements.every(movePassed); }
    function allGamePassed() { return requiredMoves.length > 0 && requiredMoves.every(movePassed); }
    function firstOpenFrom(stageLists, poolFor) {
      for (var i = 0; i < stageLists.length; i += 1) {
        if (poolFor(i).some(function (m) { return !movePassed(m); })) return i;
      }
      return Math.max(0, stageLists.length - 1);
    }
    function firstOpenStage() { return firstOpenFrom(signStages, cumulativePool); }
    function firstOpenMovementStage() { return firstOpenFrom(movementStages, cumulativeMovementPool); }

    function setArt(name) {
      if (art && name && artUrl(name) && art.getAttribute('src') !== artUrl(name)) {
        art.setAttribute('data-drill-art', name);
        art.setAttribute('src', artUrl(name));
        if (backdrop) backdrop.setAttribute('src', artUrl(name));
      }
    }
    /* 向下捲動: nothing may be cut off without the scout being told */
    function syncMore() {
      if (!moreCue || !panel) return;
      moreCue.hidden = (panel.scrollHeight - panel.scrollTop - panel.clientHeight) <= 8;
    }
    if (panel) {
      panel.addEventListener('scroll', syncMore, { passive: true });
      window.addEventListener('resize', syncMore);
    }
    function bringStageIntoView() {
      /* a tap below the fold must not leave the next statue half off-screen */
      if (root && root.scrollIntoView) root.scrollIntoView({ block: 'start', behavior: 'auto' });
    }

    function say(html, emoji) {
      clearTimers();                              /* a new card ends any running beat */
      /* the flip cards are the whole screen — no cliff above, no small panel */
      root.classList.toggle('drill-flip-full', state.scene === 'flip');
      root.classList.toggle('drill-command-full', state.section === 2 && state.scene === 'drill');
      root.setAttribute('data-drill-section', String(state.section || 1));
      if (!card) return;
      card.innerHTML = html;
      if (panel && panel.scrollTop) panel.scrollTop = 0;
      card.classList.remove('is-in');
      void card.offsetWidth;
      card.classList.add('is-in');
      if (emoji) burstOn(card.querySelector('.btn'), emoji);
      card.setAttribute('tabindex', '-1');
      syncMore();
      window.setTimeout(syncMore, 80);
      startStatueAnimations();
    }

    function startStatueAnimations() {
      if (!card) return;
      var nodes = Array.prototype.slice.call(card.querySelectorAll('[data-drill-animation]'));
      if (!nodes.length) return;
      var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      var startedAt = Date.now();
      function apply() {
        nodes.forEach(function (node) {
          var steps = Array.prototype.slice.call(node.querySelectorAll('[data-drill-frame]'));
          if (!steps.length) return;
          if (reduce) {
            steps.forEach(function (step, index) {
              step.classList.toggle('is-active', index === steps.length - 1);
            });
            return;
          }
          var holds = steps.map(function (step) {
            return Math.max(250, Number(step.getAttribute('data-hold-ms')) || 900);
          });
          var total = holds.reduce(function (sum, hold) { return sum + hold; }, 0);
          var at = (Date.now() - startedAt) % total;
          var active = 0;
          var cursor = 0;
          holds.forEach(function (hold, index) {
            if (at >= cursor) active = index;
            cursor += hold;
          });
          steps.forEach(function (step, index) {
            step.classList.toggle('is-active', index === active);
          });
        });
      }
      apply();
      if (!reduce) statueTimer = window.setInterval(apply, 80);
    }
    function kicker(text, kind) {
      return '<span class="cave-kicker' + (kind ? ' cave-kicker-' + kind : '') + '">' + esc(text) + '</span>';
    }
    function chip(text, cls) {
      return '<span class="drill-chip' + (cls ? ' ' + cls : '') + '">' + esc(text) + '</span>';
    }

    function paintProgress() {
      if (!progress) return;
      if (state.section === 2 && movementStages.length) {
        progress.textContent = fill(pick(L.move_progress_zh, L.move_progress_en) || '', {
          done: movementsDone(), total: allMovements.length,
          stage: state.stage + 1, stages: movementStages.length
        }) || pick(L.hud_zh, L.hud_en) || '';
        return;
      }
      progress.textContent = fill(pick(L.progress_zh, L.progress_en) || '', {
        done: signsDone(), total: allSigns.length,
        stage: state.stage + 1, stages: signStages.length
      }) || pick(L.hud_zh, L.hud_en) || '';
    }

    /* ── the flip cards: this stage's new signs, big and clear ────────────── */

    function leaderText(m) {
      return pick(m.leader_zh, m.leader_en);
    }

    function signFaceText(m) {
      /* the first point names the sign itself: 手號：兩手握拳… → the card */
      var points = (isEn() ? (m.points_en || m.points_zh) : (m.points_zh || m.points_en)) || [];
      var text = String(points[0] || '');
      return text.replace(/^手號：/, '').replace(/^Sign:\s*/i, '');
    }

    function signFlipHtml() {
      var fresh = (signStages[state.stage] || []).map(moveById).filter(function (m) { return m; });
      var known = state.stage > 0 ? cumulativePool(state.stage - 1) : [];
      var cards = fresh.map(function (m) {
        var front = m.figure || m.img;             /* the drawn figure first, the page behind */
        return '<div class="drill-flip" data-drill-flip="' + esc(m.id) + '" role="button" tabindex="0"' +
               ' aria-label="' + esc(pick(m.title_zh, m.title_en)) + '">' +
          '<span class="drill-flip-corner is-tl" aria-hidden="true"></span>' +
          '<span class="drill-flip-corner is-tr" aria-hidden="true"></span>' +
          '<span class="drill-flip-corner is-bl" aria-hidden="true"></span>' +
          '<span class="drill-flip-corner is-br" aria-hidden="true"></span>' +
          '<div class="drill-flip-inner">' +
            '<div class="drill-flip-face drill-flip-front">' +
              '<img src="' + esc(artUrl(front)) + '" alt="' + esc(pick(m.title_zh, m.title_en)) + '">' +
              '<span class="drill-flip-hint">⟳ ' + esc(pick(L.flip_hint_zh, L.flip_hint_en)) + '</span>' +
            '</div>' +
            '<div class="drill-flip-face drill-flip-back">' +
              '<span class="drill-flip-label">' + esc(pick(L.flip_formation_zh, L.flip_formation_en)) + '</span>' +
              '<strong class="drill-flip-name">' + esc(pick(m.title_zh, m.title_en)) + '</strong>' +
              formationSvg(m.id, true) +
              (leaderText(m) ? '<span class="drill-flip-leader"><span class="drill-leader-tri" aria-hidden="true">▼</span> <b>' +
                esc(pick(L.flip_leader_zh, L.flip_leader_en)) + '</b>：' + esc(leaderText(m)) + '</span>' : '') +
              '<span class="drill-flip-sign"><b>' + esc(pick(L.flip_sign_zh, L.flip_sign_en)) + '</b> ' +
                esc(signFaceText(m)) + '</span>' +
            '</div>' +
          '</div>' +
        '</div>';
      }).join('');
      var knownNote = known.length
        ? '<p class="cave-line small drill-flip-known">' + esc(pick(L.flip_known_zh, L.flip_known_en)) +
          ' ' + known.map(function (m) { return esc(pick(m.title_zh, m.title_en)); }).join('、') + '</p>'
        : '';
      return kicker(fill(pick(L.flip_kicker_zh, L.flip_kicker_en), { stage: state.stage + 1 })) +
        '<p class="cave-line small">' + esc(pick(L.flip_lead_zh, L.flip_lead_en)) + '</p>' +
        (pick(L.flip_leader_note_zh, L.flip_leader_note_en)
          ? '<p class="cave-line small drill-flip-leader-note"><span class="drill-leader-tri" aria-hidden="true">▼</span> ' +
            esc(pick(L.flip_leader_note_zh, L.flip_leader_note_en)) + '</p>' : '') +
        '<div class="drill-flip-grid">' + cards + '</div>' +
        knownNote +
        '<div class="cave-actions"><button class="btn primary big" type="button" data-drill-go="start-stage" data-cheer="🪨">' +
          esc(pick(L.flip_start_zh, L.flip_start_en)) + '</button></div>';
    }


    function pointsFor(m) {
      return (isEn() ? (m.points_en || m.points_zh) : (m.points_zh || m.points_en)) || [];
    }

    function countText(m) {
      return String((m && m.count) || '').replace(/^打數：\s*/, '').trim();
    }

    function studyUnitsFor(ids) {
      var units = [];
      var paceUnit = null;
      (ids || []).map(moveById).filter(function (m) { return m; }).forEach(function (m) {
        if (m.study_group === 'pacing') {
          if (!paceUnit) {
            paceUnit = { id: 'pacing', moves: [] };
            units.push(paceUnit);
          }
          paceUnit.moves.push(m);
        } else {
          units.push({ id: m.id, moves: [m] });
        }
      });
      return units;
    }

    function unitTitle(unit) {
      if (unit.id === 'pacing') return pick(L.pace_card_title_zh, L.pace_card_title_en);
      var m = unit.moves[0] || {};
      return pick(m.title_zh, m.title_en);
    }


    function animationFrames(m) {
      return ((m && m.animation) || []).map(function (frame) {
        return typeof frame === 'string' ? { img: frame } : frame;
      }).filter(function (frame) { return frame && frame.img && artUrl(frame.img); });
    }

    function movementArt(m) {
      var frames = animationFrames(m || {});
      return (m && m.figure) || (frames.length ? frames[frames.length - 1].img : '') ||
             (m && m.img) || ridgeArt();
    }

    function movementAnimationHtml(m, variant) {
      var frames = animationFrames(m);
      if (!frames.length) return '';
      return '<span class="drill-statue-anim is-' + esc(variant || 'flip') + '"' +
             ' data-drill-animation="' + esc(m.id) + '" data-frame-count="' + frames.length + '"' +
             ' role="img" aria-label="' + esc(pick(m.title_zh, m.title_en)) + '">' +
        frames.map(function (frame, index) {
          var label = pick(frame.label_zh, frame.label_en);
          return '<span class="drill-statue-step' + (index === 0 ? ' is-active' : '') + '"' +
                 ' data-drill-frame data-hold-ms="' + esc(frame.hold_ms || 900) + '">' +
            '<img src="' + esc(artUrl(frame.img)) + '" alt="">' +
            (label ? '<span class="drill-statue-caption">' + esc(label) + '</span>' : '') +
          '</span>';
        }).join('') +
      '</span>';
    }

    function moveCardFront(unit) {
      var m = unit.moves[0] || {};
      var frames = unit.id === 'pacing' ? [] : animationFrames(m);
      var image = unit.id === 'pacing' ? '' : (m.figure || m.img || '');
      var body = frames.length
        ? movementAnimationHtml(m, 'flip')
        : image
        ? '<img src="' + esc(artUrl(image)) + '" alt="' + esc(unitTitle(unit)) + '">'
        : '<span class="drill-flip-icon-front">' + movementSvg(unit.id, true) +
            '<strong>' + esc(unitTitle(unit)) + '</strong>' +
            (unit.id === 'pacing'
              ? '<small>' + unit.moves.map(function (pace) {
                  return esc(pick(pace.title_zh, pace.title_en));
                }).join(isEn() ? ' · ' : '、') + '</small>'
              : '<small>' + esc(m.command || '') + '</small>') +
          '</span>';
      return '<div class="drill-flip-face drill-flip-front">' + body +
        '<span class="drill-flip-hint">⟳ ' + esc(pick(L.flip_hint_zh, L.flip_hint_en)) + '</span></div>';
    }

    function moveMetaChips(m) {
      var chips = [];
      if (countText(m)) {
        chips.push('<span class="drill-move-count"><b>' +
          esc(pick(L.move_count_label_zh, L.move_count_label_en)) + '</b> ' +
          esc(countText(m)) + '</span>');
      }
      if (m.manual) {
        chips.push('<span class="drill-move-manual">📖 ' +
          esc(pick(L.manual_label_zh, L.manual_label_en)) + ' — ' + esc(m.manual) + '</span>');
      } else if (m.leader_demo) {
        chips.push('<span class="drill-move-manual">' +
          esc(pick(L.move_leader_demo_zh, L.move_leader_demo_en)) + '</span>');
      }
      return chips.length ? '<span class="drill-move-meta">' + chips.join('') + '</span>' : '';
    }

    function moveCardBack(unit) {
      if (unit.id === 'pacing') {
        var directions = unit.moves.map(function (m) {
          var firstPoint = pointsFor(m)[0] || '';
          return '<span class="drill-pace-direction">' + movementSvg(m.id) +
            '<b>' + esc(pick(m.title_zh, m.title_en)) + '</b>' +
            '<small>' + esc(m.command || '') + '</small>' +
            '<span>' + esc(firstPoint) + '</span></span>';
        }).join('');
        return '<div class="drill-flip-face drill-flip-back is-move">' +
          '<span class="drill-flip-label">' + esc(pick(L.move_flip_label_zh, L.move_flip_label_en)) + '</span>' +
          '<strong class="drill-flip-name">' + esc(unitTitle(unit)) + '</strong>' +
          movementSvg('pacing', true) +
          '<span class="drill-pace-directions">' + directions + '</span>' +
          '<span class="drill-flip-sign">' + esc(pick(L.pace_card_note_zh, L.pace_card_note_en)) + '</span>' +
        '</div>';
      }
      var m = unit.moves[0] || {};
      var points = pointsFor(m);
      var note = pick(m.note_zh, m.note_en);
      return '<div class="drill-flip-face drill-flip-back is-move">' +
        '<span class="drill-flip-label">' + esc(pick(L.move_flip_label_zh, L.move_flip_label_en)) + '</span>' +
        '<strong class="drill-flip-name">' + esc(pick(m.title_zh, m.title_en)) + '</strong>' +
        movementSvg(m.id, true) +
        '<span class="drill-move-command"><b>' +
          esc(pick(L.move_command_label_zh, L.move_command_label_en)) + '</b> ' +
          esc(m.command || '') + '</span>' +
        moveMetaChips(m) +
        (points.length
          ? '<span class="drill-move-points-label">' +
              esc(pick(L.move_points_label_zh, L.move_points_label_en)) + '</span>' +
            '<ol class="drill-flip-points">' + points.map(function (text) {
              return '<li>' + esc(text) + '</li>';
            }).join('') + '</ol>'
          : '') +
        (note ? '<span class="drill-flip-sign">' + esc(note) + '</span>' : '') +
      '</div>';
    }

    function moveFlipHtml() {
      var freshIds = movementStages[state.stage] || [];
      var fresh = studyUnitsFor(freshIds);
      var known = state.stage > 0 ? studyUnitsFor(cumulativeMovementPool(state.stage - 1).map(function (m) { return m.id; })) : [];
      var cards = fresh.map(function (unit) {
        return '<div class="drill-flip" data-drill-flip="' + esc(unit.id) + '" role="button" tabindex="0"' +
               ' aria-label="' + esc(unitTitle(unit)) + '">' +
          '<span class="drill-flip-corner is-tl" aria-hidden="true"></span>' +
          '<span class="drill-flip-corner is-tr" aria-hidden="true"></span>' +
          '<span class="drill-flip-corner is-bl" aria-hidden="true"></span>' +
          '<span class="drill-flip-corner is-br" aria-hidden="true"></span>' +
          '<div class="drill-flip-inner">' + moveCardFront(unit) + moveCardBack(unit) + '</div>' +
        '</div>';
      }).join('');
      var knownNote = known.length
        ? '<p class="cave-line small drill-flip-known">' + esc(pick(L.move_flip_known_zh, L.move_flip_known_en)) +
          ' ' + known.map(function (unit) { return esc(unitTitle(unit)); }).join(isEn() ? ', ' : '、') + '</p>'
        : '';
      return kicker(fill(pick(L.move_flip_kicker_zh, L.move_flip_kicker_en), { stage: state.stage + 1 })) +
        '<p class="cave-line small">' + esc(pick(L.move_flip_lead_zh, L.move_flip_lead_en)) + '</p>' +
        '<div class="drill-flip-grid">' + cards + '</div>' +
        knownNote +
        '<div class="cave-actions"><button class="btn primary big" type="button" data-drill-go="start-stage" data-cheer="🥁">' +
          esc(pick(L.move_flip_start_zh, L.move_flip_start_en)) + '</button></div>';
    }

    function flipHtml() {
      return state.section === 2 ? moveFlipHtml() : signFlipHtml();
    }

    function showFlip(section, stageIndex) {
      state.section = movementStages.length && section === 2 ? 2 : 1;
      var lists = activeStageLists();
      state.stage = Math.max(0, Math.min(Math.max(0, lists.length - 1), stageIndex));
      state.scene = 'flip';
      setArt(ridgeArt());
      say(flipHtml());
      mark('flip');
      bringStageIntoView();
      paintProgress();
    }

    /* ── the live mechanism: a sign on the rock, the count running ────────── */

    function beatCountFor(m) {
      if (state.section !== 2) return 3;      /* three beats to every hand sign */
      var count = countText(m);
      if (!count) return 3;
      var parts = count.split(/[—–-]+/).map(function (part) { return part.trim(); })
                       .filter(function (part) { return part; });
      return Math.max(2, Math.min(6, parts.length || 3));
    }
    function beatTotalFor(m) {
      var beats = beatCountFor(m);
      /* Section 2 gives the scout time to read the command and find the right
         movement among a cumulative bank; the bar still runs to the movement's
         own number of beats, only more slowly than parade tempo. */
      return state.section === 2 ? Math.max(8000, beats * 1700) : Math.max(4000, beats * 1500);
    }

    function formationBtn(m) {
      return '<button class="drill-form-btn" type="button" data-drill-form="' + esc(m.id) + '"' +
             ' aria-label="' + esc(pick(m.title_zh, m.title_en)) + '">' +
        '<span class="drill-form-name">' + esc(pick(m.title_zh, m.title_en)) + '</span>' +
        formationSvg(m.id) +
      '</button>';
    }

    function movementBtn(m) {
      return '<button class="drill-form-btn drill-move-btn" type="button" data-drill-form="' + esc(m.id) + '"' +
             ' aria-label="' + esc(pick(m.title_zh, m.title_en)) + '">' +
        '<span class="drill-form-name">' + esc(pick(m.title_zh, m.title_en)) + '</span>' +
        movementSvg(m.id) +
      '</button>';
    }

    function signPromptHtml(m) {
      var beats = beatCountFor(m);
      return kicker(pick(L.prompt_kicker_zh, L.prompt_kicker_en) ||
                    fill(pick('第 1 節 · 集隊手號 · 第 {stage} / {stages} 階段',
                              'Section 1 · hand signs · stage {stage} / {stages}'),
                         { stage: state.stage + 1, stages: signStages.length })) +
        '<h2 class="cave-subtitle">' + esc(pick(L.prompt_q_zh, L.prompt_q_en)) + '</h2>' +
        '<div class="drill-beat" data-drill-beat aria-hidden="true">' +
          '<div class="drill-beat-fill" data-drill-beat-fill></div>' +
        '</div>' +
        '<p class="drill-beat-note"><span>' + esc(pick('三拍之內', 'three beats')) + '</span>' +
          '<span data-drill-beat-count>' +
            esc(fill(pick(L.beat_of_zh, L.beat_of_en), { i: 1, n: beats })) +
          '</span></p>' +
        '<div class="drill-form-row" data-drill-forms>' +
          state.forms.map(formationBtn).join('') +
        '</div>';
    }


    function movePromptHtml(m) {
      var beats = beatCountFor(m);
      var chips = [];
      if (countText(m)) chips.push(chip(pick(L.move_count_label_zh, L.move_count_label_en) + '：' + countText(m), 'is-command'));
      if (m.manual) chips.push(chip('📖 ' + pick(L.manual_label_zh, L.manual_label_en) + ' — ' + m.manual));
      if (m.leader_demo) chips.push(chip(pick(L.move_leader_demo_zh, L.move_leader_demo_en), 'is-demo'));
      return kicker(fill(pick(L.move_prompt_kicker_zh, L.move_prompt_kicker_en),
                         { stage: state.stage + 1, stages: movementStages.length })) +
        '<p class="drill-command-say">' + esc(pick(L.move_prompt_say_zh, L.move_prompt_say_en)) + '</p>' +
        '<h2 class="drill-command" data-drill-command>' + esc(m.command || '') + '</h2>' +
        (chips.length ? '<div class="drill-chips">' + chips.join('') + '</div>' : '') +
        '<h3 class="cave-subtitle drill-move-question">' + esc(pick(L.move_prompt_q_zh, L.move_prompt_q_en)) + '</h3>' +
        '<div class="drill-beat" data-drill-beat aria-hidden="true">' +
          '<div class="drill-beat-fill" data-drill-beat-fill></div>' +
        '</div>' +
        '<p class="drill-beat-note"><span>' + esc(pick('在打數之內按出動作', 'press the movement inside the count')) + '</span>' +
          '<span data-drill-beat-count>' +
            esc(fill(pick(L.beat_of_zh, L.beat_of_en), { i: 1, n: beats })) +
          '</span></p>' +
        '<div class="drill-form-row is-movements" data-drill-forms>' +
          state.forms.map(movementBtn).join('') +
        '</div>';
    }

    function promptHtml(m) {
      return state.section === 2 ? movePromptHtml(m) : signPromptHtml(m);
    }

    function startBeats() {
      var beats = beatCountFor(state.current);
      var total = beatTotalFor(state.current);
      var beatMs = total / beats;
      var fillBar = card && card.querySelector('[data-drill-beat-fill]');
      var countNote = card && card.querySelector('[data-drill-beat-count]');
      var bar = card && card.querySelector('[data-drill-beat]');
      var startedAt = null;
      beatTimer = window.setInterval(function () {
        if (!startedAt) startedAt = Date.now();
        var elapsed = Date.now() - startedAt;
        var left = Math.max(0, total - elapsed);
        if (fillBar) fillBar.style.width = (left / total * 100) + '%';
        if (bar) bar.classList.toggle('is-low', left < total * 0.34);
        if (countNote) {
          var beat = Math.min(beats, Math.floor(elapsed / beatMs) + 1);
          countNote.textContent = fill(pick(L.beat_of_zh, L.beat_of_en), { i: beat, n: beats });
        }
        if (left <= 0) {
          clearTimers();
          onLate();
        }
      }, 80);
    }

    function renderPrompt(m) {
      state.current = m;
      state.busy = false;
      state.scene = 'drill';
      setArt(state.section === 2 ? ridgeArt() : (m.figure || m.img || ridgeArt()));
      /* section 1: the leader statue shows the sign. Section 2: the full-screen
         command board needs no picture — the called command is the prompt. */
      say(promptHtml(m));
      mark('drill');
      bringStageIntoView();
      paintProgress();
      startBeats();
    }

    function beginStage(section, stageIndex) {
      state.section = movementStages.length && section === 2 ? 2 : 1;
      var lists = activeStageLists();
      state.stage = Math.max(0, Math.min(Math.max(0, lists.length - 1), stageIndex));
      var pool = activePool(state.stage);
      state.forms = shuffled(pool);      /* the buttons hold still for the stage */
      state.queue = shuffled(pool.map(function (m) { return m.id; }));
      nextInStage();
    }

    function nextInStage() {
      if (!state.queue.length) { stageDone(); return; }
      var m = moveById(state.queue.shift());
      if (!m) { nextInStage(); return; }
      renderPrompt(m);
    }

    function answerPick(pickedId) {
      if (state.busy || state.scene !== 'drill' || !state.current) return;
      var m = state.current;
      if (pickedId === m.id) {
        state.busy = true;
        clearTimers();
        answers[m.id] = (m.check || {}).answer;
        save();
        chime();
        var why = pick((m.check || {}).why_zh, (m.check || {}).why_en);
        var isMove = state.section === 2;
        say(kicker(isMove ? pick(L.move_right_title_zh, L.move_right_title_en)
                          : pick(L.right_title_zh, L.right_title_en), 'good') +
            '<h2 class="cave-subtitle">' + esc(pick(m.title_zh, m.title_en)) + '</h2>' +
            (isMove && m.command ? '<p class="drill-command drill-command-feedback">' + esc(m.command) + '</p>' : '') +
            (why ? '<p class="drill-why drill-teach-why"><b>' + esc(pick(L.remember_zh, L.remember_en)) +
                  '</b> ' + esc(why) + '</p>' : ''));
        burstOn(card.querySelector('.cave-kicker'), isMove ? ['✨', '🥁'] : ['✨', '🪨']);
        paintProgress();
        advanceTimer = window.setTimeout(nextInStage, 1000);
        return;
      }
      clearTimers();
      thud();
      reviewCard(m, state.section === 2 ? pick(L.move_wrong_title_zh, L.move_wrong_title_en)
                                        : pick(L.wrong_title_zh, L.wrong_title_en));
    }

    function onLate() {
      if (!state.current) return;
      thud();
      reviewCard(state.current, pick(L.late_title_zh, L.late_title_en));
    }

    function reviewCard(m, title) {
      /* never the answer outright — the card opens again as the review, and
         the sign rejoins the back of the queue */
      state.queue.push(m.id);
      state.scene = 'review';
      state.busy = false;
      var isMoveReview = state.section === 2;
      setArt(isMoveReview ? movementArt(m) : (m.figure || m.img || ridgeArt()));
      var points = pointsFor(m);
      var why = pick((m.check || {}).why_zh, (m.check || {}).why_en);
      var reviewChips = [];
      if (isMoveReview && m.command) reviewChips.push(chip(m.command, 'is-command'));
      if (isMoveReview && countText(m)) reviewChips.push(chip(pick(L.move_count_label_zh, L.move_count_label_en) + '：' + countText(m)));
      if (m.manual) reviewChips.push(chip('📖 ' + pick(L.manual_label_zh, L.manual_label_en) + ' — ' + m.manual));
      if (isMoveReview && m.leader_demo) reviewChips.push(chip(pick(L.move_leader_demo_zh, L.move_leader_demo_en), 'is-demo'));
      var reviewVisual = isMoveReview
        ? (animationFrames(m).length ? movementAnimationHtml(m, 'review') : movementSvg(m.id, true))
        : ((m.figure ? '<img class="drill-review-fig" src="' + esc(artUrl(m.figure)) + '"' +
                       ' alt="' + esc(pick(m.title_zh, m.title_en)) + '">' : '') + formationSvg(m.id, true));
      say(kicker(title, 'bad') +
          '<h2 class="cave-subtitle">' + esc(fill(isMoveReview
                                                  ? pick(L.move_review_lead_zh, L.move_review_lead_en)
                                                  : pick(L.review_lead_zh, L.review_lead_en),
                                                  { name: pick(m.title_zh, m.title_en) })) + '</h2>' +
          (reviewChips.length ? '<div class="drill-chips">' + reviewChips.join('') + '</div>' : '') +
          '<div class="drill-review-form">' +
            reviewVisual +
            '<span class="drill-form-name">' + esc(pick(m.title_zh, m.title_en)) + '</span>' +
          '</div>' +
          '<ol class="drill-points">' + points.map(function (text) {
            return '<li>' + esc(text) + '</li>';
          }).join('') + '</ol>' +
          (why ? '<p class="drill-why drill-teach-why"><b>' + esc(pick(L.remember_zh, L.remember_en)) +
                '</b> ' + esc(why) + '</p>' : '') +
          '<div class="cave-actions"><button class="btn primary" type="button" data-drill-go="resume">' +
            esc(pick(L.review_again_zh, L.review_again_en)) + '</button></div>');
      mark('review');
      paintProgress();
    }

    /* ── between stages: a flight of steps appears ────────────────────────── */

    function stageDoneHtml() {
      if (state.section === 2) {
        var lastMoveStage = state.stage + 1 >= movementStages.length;
        var moveDoneTitle = fill(pick(L.move_stage_done_zh, L.move_stage_done_en), { n: state.stage + 1 });
        return kicker(moveDoneTitle, 'good') +
          '<h2 class="cave-subtitle">' + esc(moveDoneTitle) + '</h2>' +
          '<p class="cave-line small">' + esc(pick(L.move_stage_done_note_zh, L.move_stage_done_note_en)) + '</p>' +
          '<div class="cave-actions cave-actions-split">' +
            (lastMoveStage
              ? '<button class="btn primary" type="button" data-drill-go="finish" data-cheer="🎖,🥁">' +
                esc(pick(L.move_finish_zh, L.move_finish_en)) + '</button>'
              : '<button class="btn primary" type="button" data-drill-go="next-stage" data-cheer="🥁">' +
                esc(pick(L.move_next_stage_zh, L.move_next_stage_en)) + '</button>') +
          '</div>';
      }
      var last = state.stage + 1 >= signStages.length;
      return kicker(fill(pick(L.stage_done_zh, L.stage_done_en), { n: state.stage + 1 }), 'good') +
        '<h2 class="cave-subtitle">' +
          esc(fill(pick(L.stage_done_zh, L.stage_done_en), { n: state.stage + 1 })) + '</h2>' +
        '<p class="cave-line small">' + esc(pick(L.stage_done_note_zh, L.stage_done_note_en)) + '</p>' +
        '<div class="cave-actions cave-actions-split">' +
          (last
            ? '<button class="btn primary" type="button" data-drill-go="section-done" data-cheer="🎖,🪨">' +
              esc(pick(L.section_done_title_zh, L.section_done_title_en)) + '</button>'
            : '<button class="btn primary" type="button" data-drill-go="next-stage" data-cheer="🪨">' +
              esc(pick(L.next_stage_zh, L.next_stage_en)) + '</button>') +
        '</div>';
    }

    function stageDone() {
      state.busy = false;         /* the last answer's flash must not block the way on */
      state.scene = 'stage-done';
      setArt(ridgeArt());
      say(stageDoneHtml());
      mark('stage-done');
      paintProgress();
    }

    function sectionDoneHtml() {
      var badgeLink = root.querySelector('[data-drill-link="badge"]');
      return kicker(pick(L.section_done_title_zh, L.section_done_title_en), 'good') +
        '<h1 class="cave-title">' + esc(pick(L.section_done_title_zh, L.section_done_title_en)) + '</h1>' +
        '<p class="cave-line small">' + esc(pick(L.section_done_note_zh, L.section_done_note_en)) + '</p>' +
        '<div class="cave-actions cave-actions-split">' +
          '<button class="btn primary" type="button" data-drill-go="section2" data-cheer="🥁">' +
            esc(pick(L.section2_start_zh, L.section2_start_en)) + '</button>' +
          '<button class="btn ghost" type="button" data-drill-go="restart">' +
            esc(pick(L.restart_zh, L.restart_en)) + '</button>' +
          (badgeLink ? badgeLink.outerHTML : '') +
        '</div>';
    }

    function sectionDone() {
      state.scene = 'section-done';
      setArt(ridgeArt());
      say(sectionDoneHtml());
      mark('section-done');
      paintProgress();
    }

    function mark(name) {
      root.setAttribute('data-drill-scene', name);
      root.setAttribute('data-drill-section', String(state.section || 1));
    }

    function show(scene) {
      state.scene = scene;
      mark(scene);
      if (scene === 'intro') {
        state.section = section1Passed() && movementStages.length ? 2 : 1;
        state.stage = state.section === 2 ? firstOpenMovementStage() : firstOpenStage();
        setArt(ridgeArt());
        var paras = (isEn() ? ((cfg.intro || {}).paras_en || (cfg.intro || {}).paras_zh)
                            : ((cfg.intro || {}).paras_zh || (cfg.intro || {}).paras_en)) || [];
        say(kicker(pick((cfg.intro || {}).kicker_zh, (cfg.intro || {}).kicker_en)) +
            '<h1 class="cave-title">' + esc(pick((cfg.intro || {}).title_zh, (cfg.intro || {}).title_en)) + '</h1>' +
            (paras.length ? '<p class="cave-line">' + paras.map(esc).join('</p><p class="cave-line">') + '</p>' : '') +
            '<p class="cave-line small">' + esc(pick((cfg.intro || {}).hint_zh, (cfg.intro || {}).hint_en)) + '</p>' +
            '<div class="cave-actions"><button class="btn primary big" type="button" data-drill-go="start">' +
            esc(pick((cfg.intro || {}).action_zh, (cfg.intro || {}).action_en)) + '</button></div>');
        paintProgress();
      } else if (scene === 'studied') {
        var studied = cfg.studied_card || {};
        setArt(ridgeArt());
        say(kicker(pick(studied.kicker_zh, studied.kicker_en), 'good') +
            '<h1 class="cave-title">' + esc(pick(studied.title_zh, studied.title_en)) + '</h1>' +
            '<p class="cave-line small drill-submitting">' + esc(pick(studied.submitting_zh, studied.submitting_en)) + '</p>');
        paintProgress();
      } else if (scene === 'result') {
        setArt(ridgeArt());
      }
    }

    /* ── finishing (both sections): the manual is studied, the leader next ── */

    function finish() {
      if (state.busy) return;
      state.busy = true;
      show('studied');
      var url = cfg.submit_url;
      if (!url) {                      // self-contained offline preview: it
        window.setTimeout(function () { // already knows every check was right
          state.busy = false;
          if (state.ticked) { result(); return; }
          assess();
          return;
        }, 500);
        return;
      }
      var body = new FormData();
      requiredMoves.forEach(function (m) {
        body.append('check_' + m.id, String(answers[m.id] !== undefined ? answers[m.id] : (m.check || {}).answer));
      });
      fetch(url, { method: 'POST', body: body, credentials: 'same-origin' })
        .then(function (response) {
          return response.json().catch(function () { return { ok: false }; })
            .then(function (data) { return { status: response.status, data: data }; });
        })
        .then(function (answer_) {
          state.busy = false;
          if (answer_.data && answer_.data.ok) {
            if (answer_.data.status === 'completed') { result(); return; }
            assess();
            return;
          }
          saveProblem(answer_.data ? pick(answer_.data.message_zh, answer_.data.message_en) : '');
        })
        .catch(function () { state.busy = false; saveProblem(''); });
    }

    /* ── the assess card: the manual is learned, the leader's word is next ── */

    function assessHtml() {
      var a = cfg.assess || {};
      var points = (isEn() ? (a.points_en || a.points_zh) : a.points_zh || []) || [];
      var pointsHtml = points.map(function (text) {
        return '<p class="cave-line small drill-assess-point">🏅 ' + esc(text) + '</p>';
      }).join('');
      var next = cfg.next_game;
      var nextBtn = '';
      if (next && next.url) {
        nextBtn = '<a class="btn ghost" href="' + esc(next.url) + '">' +
          esc(fill(pick(a.go_next_zh, a.go_next_en) || '', {})) + '</a>';
      }
      return kicker(pick(a.kicker_zh, a.kicker_en), 'good') +
        '<h1 class="cave-title">' + esc(pick(a.title_zh, a.title_en)) + '</h1>' +
        '<p class="cave-line small">' + esc(pick(a.lead_zh, a.lead_en)) + '</p>' +
        pointsHtml +
        '<p class="cave-line small">' + esc(pick(a.after_zh, a.after_en)) + '</p>' +
        '<form class="drill-code" data-drill-code action="" method="post" autocomplete="off">' +
          '<label class="drill-code-label" for="drill-code-input">' + esc(pick(a.code_label_zh, a.code_label_en)) + '</label>' +
          '<span class="drill-code-row">' +
            '<input id="drill-code-input" data-drill-code-input type="text" inputmode="latin" maxlength="24" ' +
                   'placeholder="' + esc(pick(a.code_placeholder_zh, a.code_placeholder_en)) + '">' +
            '<button class="btn primary" type="submit">' + esc(pick(a.code_button_zh, a.code_button_en)) + '</button>' +
          '</span>' +
          '<p class="drill-code-note" data-drill-code-note hidden></p>' +
        '</form>' +
        '<div class="cave-actions cave-actions-split">' +
          '<button class="btn ghost" type="button" data-drill-go="restart">' +
            esc(pick((cfg.studied_card || {}).again_zh, (cfg.studied_card || {}).again_en)) + '</button>' +
          nextBtn +
        '</div>';
    }

    function assess() {
      /* the studying is saved; from here the game may be left any time */
      document.dispatchEvent(new CustomEvent('drill:studied', { detail: { cleared: false } }));
      setArt(ridgeArt());
      var badgeLink = root.querySelector('[data-drill-link="badge"]');
      var refs = Array.prototype.map.call(root.querySelectorAll('[data-drill-link="ref"]'),
                                          function (node) { return node.outerHTML; }).join('');
      say(assessHtml() + (refs ? '<div class="row wrap" style="gap:.4rem; margin:.15rem 0 .35rem">' + refs + '</div>' : '') +
          (badgeLink ? '<div class="cave-actions">' + badgeLink.outerHTML + '</div>' : ''));
      state.scene = 'result';
      mark('result');
      paintProgress();
    }

    function codeNote(text, bad) {
      if (!card) return;
      var slot = card.querySelector('[data-drill-code-note]');
      if (!slot) return;
      slot.textContent = text || '';
      slot.classList.toggle('is-bad', !!bad);
      slot.hidden = !text;
    }

    function submitCode(form) {
      if (state.busy) return;
      var input = form.querySelector('[data-drill-code-input]');
      var given = (input && input.value || '').trim();
      if (!given) { codeNote(pick('請輸入領袖給你的代碼。', 'Type the code your leader gave you.'), true); return; }
      var a = cfg.assess || {};
      state.busy = true;
      codeNote(pick(a.code_checking_zh, a.code_checking_en), false);
      var normalise = function (value) {
        return String(value == null ? '' : value).normalize('NFKC').replace(/\s+/g, '').toUpperCase();
      };
      var url = cfg.code_url;
      if (!url) {
        /* the offline demo file has no server: it carries the code itself and
           checks it here, so the demo teaches the same two halves as the live
           game (the live page never ships the code to the browser) */
        window.setTimeout(function () {
          state.busy = false;
          if (normalise(given) === normalise((a || {}).code)) { result(); return; }
          codeNote(pick(a.code_wrong_zh, a.code_wrong_en), true);
        }, 300);
        return;
      }
      var body = new FormData();
      body.append('code', given);
      fetch(url, { method: 'POST', body: body, credentials: 'same-origin',
                   headers: { 'X-Requested-With': 'fetch' } })
        .then(function (response) {
          return response.json().catch(function () { return { ok: false }; })
            .then(function (data) { return { status: response.status, data: data }; });
        })
        .then(function (reply) {
          state.busy = false;
          if (reply.data && reply.data.ok) { result(); return; }
          codeNote(pick((reply.data && reply.data.message_zh) || a.code_wrong_zh,
                        (reply.data && reply.data.message_en) || a.code_wrong_en), true);
        })
        .catch(function () {
          state.busy = false;
          codeNote(pick('核對不到代碼，請再試一次。', 'Could not check the code — please try again.'), true);
        });
    }

    function saveProblem(message) {
      var studied = cfg.studied_card || {};
      mark('save-error');
      say(kicker(pick(studied.kicker_zh, studied.kicker_en), 'bad') +
          '<h2 class="cave-subtitle">' + esc(pick(studied.save_error_zh, studied.save_error_en)) + '</h2>' +
          (message ? '<p class="cave-line small">' + esc(message) + '</p>' : '') +
          '<p class="cave-line small">' + esc(pick(studied.save_retry_zh, studied.save_retry_en)) + '</p>' +
          '<div class="cave-actions"><button class="btn primary big" type="button" data-drill-go="finish">' +
          esc(pick(studied.retry_zh, studied.retry_en)) + '</button></div>');
    }

    function result() {
      var studied = cfg.studied_card || {};
      state.ticked = true;
      document.dispatchEvent(new CustomEvent('drill:result', { detail: { cleared: true } }));
      var badgeLink = root.querySelector('[data-drill-link="badge"]');
      var refs = Array.prototype.map.call(root.querySelectorAll('[data-drill-link="ref"]'),
                                          function (node) { return node.outerHTML; }).join('');
      say(kicker(pick(studied.pass_zh, studied.pass_en), 'good') +
          '<h1 class="cave-title">' + esc(pick(studied.pass_title_zh, studied.pass_title_en)) + '</h1>' +
          '<p class="cave-line small">' + esc(pick(studied.pass_note_zh, studied.pass_note_en)) + '</p>' +
          (refs ? '<div class="row wrap" style="gap:.4rem; margin:.15rem 0 .35rem">' + refs + '</div>' : '') +
          '<div class="cave-actions cave-actions-split">' +
            '<button class="btn ghost" type="button" data-drill-go="restart">' +
              esc(pick(studied.again_zh, studied.again_en)) + '</button>' +
            (badgeLink ? badgeLink.outerHTML : '') +
          '</div>');
      state.scene = 'result';
      mark('result');
      paintProgress();
    }

    function reset() {
      state.section = 1;
      state.stage = 0;
      state.queue = [];
      state.forms = [];
      state.current = null;
      state.busy = false;
    }
    function restart() {
      reset();
      try { window.localStorage.removeItem(storeKey); } catch (e) {}
      answers = {};
      show('intro');
    }

    /* ── the warning before leaving ────────────────────────────────────────── */

    var exitOverlay = document.createElement('div');
    exitOverlay.className = 'cave-exit';
    exitOverlay.hidden = true;
    exitOverlay.setAttribute('role', 'dialog');
    exitOverlay.setAttribute('aria-modal', 'true');
    exitOverlay.innerHTML =
      '<div class="cave-exit-box">' +
        '<span class="cave-kicker cave-kicker-bad">' + esc(pick(L.leave_kicker_zh, L.leave_kicker_en)) + '</span>' +
        '<h2 class="cave-subtitle">' + esc(pick(L.leave_title_zh, L.leave_title_en)) + '</h2>' +
        '<p class="cave-line small">' + esc(pick(L.leave_lead_zh, L.leave_lead_en)) + '</p>' +
        '<div class="cave-actions cave-actions-split">' +
          '<button class="btn primary" type="button" data-drill-stay>' + esc(pick(L.leave_stay_zh, L.leave_stay_en)) + '</button>' +
          '<button class="btn ghost" type="button" data-drill-leave>' + esc(pick(L.leave_go_zh, L.leave_go_en)) + '</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(exitOverlay);
    var pendingExit = null;
    var lastFocus = null;
    var approvedExit = false;
    function drillIsVisible() {
      var pane = root.closest('.pane');
      return !pane || !pane.hidden;
    }
    function finishExit(leave) {
      if (exitOverlay.hidden) return;
      var callback = pendingExit;
      pendingExit = null;
      if (exitOverlay.contains(document.activeElement)) document.activeElement.blur();
      exitOverlay.hidden = true;
      document.body.classList.remove('cave-exit-open');
      if (leave) {
        approvedExit = true;
        clearTimers();
        reset();
        show('intro');
        if (callback) callback();
      } else if (lastFocus && lastFocus.isConnected && lastFocus !== document.body) {
        startStatueAnimations();
        lastFocus.focus();
      }
      lastFocus = null;
    }
    exitOverlay.addEventListener('click', function (event) {
      if (event.target.closest('[data-drill-stay]') || event.target === exitOverlay) finishExit(false);
      else if (event.target.closest('[data-drill-leave]')) finishExit(true);
    });
    exitOverlay.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); finishExit(false); }
    });
    function requestExit(callback) {
      // the assessed result and the finished section card have nothing to
      // lose: no warning on the way out. Everything else — the intro, the
      // flip cards, a live round — asks first, like the cave does.
      if (state.scene === 'result' || state.scene === 'section-done' || !drillIsVisible()) {
        if (callback) callback();
        return;
      }
      if (!exitOverlay.hidden) return;
      clearTimers();                       /* the count waits while you decide */
      pendingExit = callback;
      lastFocus = document.activeElement;
      exitOverlay.hidden = false;
      document.body.classList.add('cave-exit-open');
      exitOverlay.querySelector('[data-drill-stay]').focus();
    }
    root.__requestDrillExit = requestExit;
    root.__restartDrill = restart;
    /* the offline demo's router: a manual already studied re-opens here, not
       on the title page, so the code can be typed at any time afterwards */
    root.__drillAssess = function () { assess(); };

    if (!window.OFFLINE_DEMO) {
      document.addEventListener('click', function (event) {
        if (state.scene === 'result' || !drillIsVisible() || event.defaultPrevented || event.button !== 0 ||
            event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        var anchor = event.target.closest('a[href]');
        if (!anchor || anchor.target === '_blank' || anchor.hasAttribute('download')) return;
        var href = anchor.getAttribute('href');
        if (!href || href.charAt(0) === '#') return;
        event.preventDefault();
        event.stopImmediatePropagation();
        requestExit(function () { window.location.assign(anchor.href); });
      }, true);
      window.addEventListener('beforeunload', function (event) {
        if (approvedExit || state.scene === 'intro' || state.scene === 'result') return;
        event.preventDefault();
        event.returnValue = '';
      });
      window.addEventListener('pageshow', function (event) {
        if (event.persisted) approvedExit = false;
      });
    }

    /* ── the controls ─────────────────────────────────────────────────────── */

    root.addEventListener('click', function (event) {
      var flipCard = event.target.closest('[data-drill-flip]');
      if (flipCard) {
        event.preventDefault();
        flipCard.classList.toggle('is-flipped');
        tap();
        return;
      }
      var tile = event.target.closest('[data-drill-form]');
      if (tile) {
        event.preventDefault();
        answerPick(tile.getAttribute('data-drill-form'));
        return;
      }
      var go = event.target.closest('[data-drill-go]');
      if (!go) return;
      event.preventDefault();
      var where = go.getAttribute('data-drill-go');
      if (where === 'start') {
        tap();
        if (allGamePassed()) { finish(); return; }
        if (!section1Passed()) showFlip(1, firstOpenStage());
        else if (movementStages.length && !section2Passed()) sectionDone();
        else sectionDone();
        return;
      }
      if (where === 'start-stage') { tap(); beginStage(state.section, state.stage); return; }
      if (where === 'next-stage') { tap(); showFlip(state.section, state.stage + 1); return; }
      if (where === 'section-done') { tap(); sectionDone(); return; }
      if (where === 'section2') { tap(); showFlip(2, firstOpenMovementStage()); return; }
      if (where === 'resume') { tap(); nextInStage(); return; }
      if (where === 'finish') { finish(); return; }
      if (where === 'restart') { restart(); return; }
    });
    root.addEventListener('keydown', function (event) {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      var flipCard = event.target.closest && event.target.closest('[data-drill-flip]');
      if (flipCard) {
        event.preventDefault();
        flipCard.classList.toggle('is-flipped');
        tap();
      }
    });

    /* the leader's 考核 code: the last order of game 3 */
    root.addEventListener('submit', function (event) {
      var form = event.target.closest('[data-drill-code]');
      if (!form) return;
      event.preventDefault();
      submitCode(form);
    });

    /* a manual that is already studied opens on the assess card, so the code
       can be typed without re-reading the chapters */
    if (cfg.studied_now && !cfg.completed_now) {
      state.ticked = false;
      /* answers may be absent on a fresh browser: the studying is on file, so
         treat every movement as answered for the walk's sake */
      requiredMoves.forEach(function (m) {
        if (answers[m.id] === undefined) answers[m.id] = (m.check || {}).answer;
      });
      assess();
    } else if (cfg.completed_now) {
      requiredMoves.forEach(function (m) {
        if (answers[m.id] === undefined) answers[m.id] = (m.check || {}).answer;
      });
      state.ticked = true;
      result();
    } else {
      show('intro');
    }
  }

  function mountAll(scope) {
    var nodes = (scope || document).querySelectorAll('[data-drill]');
    Array.prototype.forEach.call(nodes, mountOne);
  }

  window.DrillGame = {
    mount: mountOne,
    mountAll: mountAll,
    assess: function () {
      var root = document.querySelector('[data-drill]');
      if (root && root.__drillAssess) root.__drillAssess();
    },
    requestExit: function (callback) {
      var root = document.querySelector('[data-drill]');
      if (root && root.__requestDrillExit) root.__requestDrillExit(callback);
      else if (callback) callback();
    },
    restart: function () {
      var root = document.querySelector('[data-drill]');
      if (root && root.__restartDrill) root.__restartDrill();
    },
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { mountAll(); });
  } else {
    mountAll();
  }
})();
