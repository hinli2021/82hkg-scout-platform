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
   then the statue mechanism shows one movement large and the right command
   must be pressed inside the count. Each stage mixes in every movement learned
   before it in section 2. From movement stage 2 on, each question shows four
   command choices — the shown movement and three random learned commands,
   shuffled so the answer's place changes. Only when both sections are cleared is the
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

    var MOVEMENT_CHOICE_LIMIT = 4;
    var state = {
      startedAt: 0,              /* 第一個動作關卡出現那一刻 — 榜上的完成時間由這裡計 */
      watchFrom: 0,              /* 石像播放中：這段不計入完成時間，倒數也未開始 */
      armPrompt: false,          /* 題目正在等石像播完，才放出口令按鈕 */
      scene: 'intro',            /* intro · flip · drill · review · stage-done ·
                                    section-done · studied · result · save-error */
      section: 1,                /* 1 = hand signs on the cliff; 2 = movements below */
      stage: 0,
      pool: [],                  /* every learned move in the current cumulative stage */
      queue: [],                 /* sign ids still to answer this stage run */
      forms: [],                 /* the answer buttons shown for the current call */
      current: null,
      busy: false,
      ticked: false,             /* the code has been accepted in this session */
      flipIndex: 0,              /* which study card is on the board */
      flipIds: [],               /* the stage's study cards, in carousel order */
      flipRead: {},              /* card id → the scout has turned it over */
      flipFace: {}               /* card id → 'back', so a revisit keeps the notes */
    };

    /* the beat timers: one tick for the bar, one for the auto-advance after a
       right answer. say() clears both, so no timer ever outlives its card */
    var beatTimer = null;
    var advanceTimer = null;
    var statueTimer = null;
    var armTimer = null;          /* the half-second pause before a question animation */
    var flipFinishTimer = null;   /* repaint after the last study card has turned */
    function clearTimers(opts) {
      if (beatTimer) { window.clearInterval(beatTimer); beatTimer = null; }
      if (advanceTimer) { window.clearTimeout(advanceTimer); advanceTimer = null; }
      /* answering keeps the statue looping; a new card still stops it */
      if (!(opts && opts.keepStatue) && statueTimer) {
        window.clearInterval(statueTimer);
        statueTimer = null;
      }
      if (armTimer) { window.clearTimeout(armTimer); armTimer = null; }
      if (flipFinishTimer) { window.clearTimeout(flipFinishTimer); flipFinishTimer = null; }
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
    function movementChoiceLimit() {
      /* stages 2 and 3 offer four answers only */
      return MOVEMENT_CHOICE_LIMIT;
    }

    function movementChoicesFor(m) {
      var pool = state.pool && state.pool.length ? state.pool : activePool(state.stage);
      var limit = movementChoiceLimit();
      if (state.section !== 2 || state.stage < 1 || pool.length <= limit) {
        return state.forms && state.forms.length ? state.forms : shuffled(pool);
      }
      var distractors = shuffled(pool.filter(function (candidate) {
        return candidate.id !== m.id;
      })).slice(0, limit - 1);
      /* a second shuffle gives the correct movement a random place
         instead of leaving it at the head of the choice list */
      return shuffled([m].concat(distractors));
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

    function say(html, emoji, opts) {
      endWatch();                                 /* a card change closes the untimed watch */
      clearTimers();                              /* a new card ends any running beat */
      /* the flip cards are the whole screen — no cliff above, no small panel */
      root.classList.toggle('drill-flip-full', state.scene === 'flip');
      root.classList.toggle('drill-command-full', state.section === 2 &&
        (state.scene === 'drill' || state.scene === 'review'));
      root.setAttribute('data-drill-section', String(state.section || 1));
      if (!card) return;
      card.innerHTML = html;
      if (panel && panel.scrollTop) panel.scrollTop = 0;
      /* study cards swap in place: the next-card press must not fade or slide */
      card.classList.remove('is-in');
      if (!(opts && opts.instant)) {
        void card.offsetWidth;
        card.classList.add('is-in');
      }
      if (emoji) burstOn(card.querySelector('.btn'), emoji);
      card.setAttribute('tabindex', '-1');
      syncMore();
      window.setTimeout(syncMore, 80);
      startStatueAnimations();
      fitFlipCard();
      window.setTimeout(fitFlipCard, 60);
      window.setTimeout(fitFlipCard, 240);
      window.setTimeout(fitFlipCard, 480);
    }

    function frameSteps(node) {
      return Array.prototype.slice.call(node.querySelectorAll('[data-drill-frame]'));
    }
    function frameHolds(steps) {
      return steps.map(function (step) {
        return Math.max(180, Number(step.getAttribute('data-hold-ms')) || 900);
      });
    }
    function frameAt(holds, at) {
      var active = 0;
      var cursor = 0;
      holds.forEach(function (hold, index) {
        if (at >= cursor) active = index;
        cursor += hold;
      });
      return active;
    }
    function paintFrame(node, steps, index) {
      var last = node._frameOn;
      var incoming = steps[index];
      var img = incoming && incoming.querySelector('img');
      var ready = !img || img.complete;
      /* hold the picture already on screen until the next one has decoded */
      var show = ready || last === undefined ? index : last;
      if (last === show) return show;
      steps.forEach(function (step, i) {
        step.classList.toggle('is-active', i === show);
        /* the pose that is leaving stays fully opaque under the one arriving */
        step.classList.toggle('is-under', last !== undefined && i === last && i !== show);
      });
      node._frameOn = show;
      return show;
    }

    function startStatueAnimations() {
      if (!card) return;
      var nodes = Array.prototype.slice.call(card.querySelectorAll('[data-drill-animation]'));
      if (!nodes.length) return;
      var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      /* decode every pose before the first change, so a frame is never swapped
         in while its picture is still blank */
      nodes.forEach(function (node) {
        Array.prototype.forEach.call(node.querySelectorAll('img'), function (img) {
          if (img.decode) img.decode().catch(function () {});
        });
      });
      /* a question holds the opening pose, plays once, then keeps looping
         while the scout answers. Teaching cards loop straight away. */
      var promptNode = null;
      if (state.armPrompt) {
        nodes.forEach(function (node) {
          if (node.classList.contains('is-prompt')) promptNode = node;
        });
      }
      var looping = nodes.filter(function (node) { return node !== promptNode; });
      if (looping.length) runStatueLoop(looping, reduce);
      if (promptNode) armPromptPlayback(promptNode, reduce);
      else state.armPrompt = false;
    }

    function runStatueLoop(nodes, reduce) {
      var startedAt = Date.now();
      function apply() {
        nodes.forEach(function (node) {
          var steps = frameSteps(node);
          if (!steps.length) return;
          if (reduce) {
            steps.forEach(function (step, index) {
              step.classList.toggle('is-active', index === steps.length - 1);
              step.classList.remove('is-under');
            });
            node._frameOn = steps.length - 1;
            return;
          }
          var holds = frameHolds(steps);
          var total = holds.reduce(function (sum, hold) { return sum + hold; }, 0);
          var at = (Date.now() - startedAt) % total;
          paintFrame(node, steps, frameAt(holds, at));
        });
      }
      apply();
      if (!reduce) statueTimer = window.setInterval(apply, 40);
    }

    function armPromptPlayback(node, reduce) {
      /* half a second on the opening pose, then the movement itself */
      armTimer = window.setTimeout(function () {
        armTimer = null;
        if (!state.armPrompt || state.scene !== 'drill') return;
        if (reduce) {
          var steps = frameSteps(node);
          if (steps.length) paintFrame(node, steps, steps.length - 1);
          openAnswers();
          return;
        }
        playPromptOnce(node, openAnswers);
      }, 500);
    }

    function playPromptOnce(node, onDone) {
      var steps = frameSteps(node);
      if (!steps.length) { onDone(); return; }
      var holds = frameHolds(steps);
      var total = holds.reduce(function (sum, hold) { return sum + hold; }, 0);
      var startedAt = Date.now();
      var finished = false;
      function apply() {
        if (finished) return;
        var at = Date.now() - startedAt;
        var index = at >= total ? steps.length - 1 : frameAt(holds, at);
        var shown = paintFrame(node, steps, index);
        /* a slow picture may hold the previous pose a moment past the last
           frame; never block the answers for more than a blink after that */
        if (at >= total && (shown === steps.length - 1 || at >= total + 800)) {
          finished = true;
          if (statueTimer) { window.clearInterval(statueTimer); statueTimer = null; }
          onDone();
          /* buttons and the count are already up — keep the statue moving,
             without another hold and without restarting the beat timer */
          if (state.scene === 'drill' && card && card.contains(node)) runStatueLoop([node], false);
        }
      }
      apply();
      statueTimer = window.setInterval(apply, 40);
    }

    /* the watch is not timed: neither the leaderboard clock nor the count
       runs while the statue is still playing */
    function endWatch() {
      if (state.watchFrom && state.startedAt) {
        state.startedAt += Date.now() - state.watchFrom;
      }
      state.watchFrom = 0;
    }

    function openAnswers() {
      if (!state.armPrompt || state.scene !== 'drill') return;
      state.armPrompt = false;
      endWatch();
      var side = card && card.querySelector('[data-drill-answers]');
      if (side) {
        side.classList.remove('is-waiting');
        side.removeAttribute('aria-busy');
        Array.prototype.forEach.call(side.querySelectorAll('button'), function (btn) {
          btn.disabled = false;
        });
      }
      var fillBar = card && card.querySelector('[data-drill-beat-fill]');
      if (fillBar) fillBar.style.width = '100%';
      startBeats();
    }
    function kicker(text, kind) {
      return '<span class="cave-kicker' + (kind ? ' cave-kicker-' + kind : '') + '">' + esc(text) + '</span>';
    }
    function chip(text, cls) {
      return '<span class="drill-chip' + (cls ? ' ' + cls : '') + '">' + esc(text) + '</span>';
    }

    function paintProgress() {
      if (!progress) return;
      /* on the assess card the counters would read as "not finished" even
         though both sections are done — say where the item really stands */
      if (state.scene === 'result') {
        var a = cfg.assess || {};
        progress.textContent = state.ticked
          ? pick((cfg.studied_card || {}).pass_zh, (cfg.studied_card || {}).pass_en) || ''
          : pick(a.waiting_zh, a.waiting_en) || '';
        return;
      }
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
      var brief = pick(m.brief_zh, m.brief_en);
      if (brief) return brief;
      var points = (isEn() ? (m.points_en || m.points_zh) : (m.points_zh || m.points_en)) || [];
      var text = String(points[0] || '');
      return text.replace(/^手號：/, '').replace(/^Sign:\s*/i, '');
    }

    function signFlipHtml() {
      var fresh = (signStages[state.stage] || []).map(moveById).filter(function (m) { return m; });
      var known = state.stage > 0 ? cumulativePool(state.stage - 1) : [];
      var cards = fresh.map(function (m) {
        var front = m.figure || m.img;             /* the drawn figure first, the page behind */
        var inner =
            '<div class="drill-flip-face drill-flip-front">' +
              '<img src="' + esc(artUrl(front)) + '" alt="' + esc(pick(m.title_zh, m.title_en)) + '">' +
              '<span class="drill-flip-hint">⟳ ' + esc(pick(L.flip_hint_zh, L.flip_hint_en)) + '</span>' +
            '</div>' +
            '<div class="drill-flip-face drill-flip-back">' +
              '<span class="drill-flip-label">' + esc(pick(L.flip_formation_zh, L.flip_formation_en)) + '</span>' +
              '<strong class="drill-flip-name">' + esc(pick(m.title_zh, m.title_en)) + '</strong>' +
              formationSvg(m.id, true) +
              (leaderText(m) ? '<span class="drill-flip-leader"><span class="drill-leader-tri" aria-hidden="true">▼</span> <b>' +
                esc(pick(L.flip_leader_zh, L.flip_leader_en)) + '</b>' + (isEn() ? ': ' : '：') + esc(leaderText(m)) + '</span>' : '') +
              '<span class="drill-flip-sign"><b>' + esc(pick(L.flip_sign_zh, L.flip_sign_en)) + '</b> ' +
                esc(signFaceText(m)) + '</span>' +
            '</div>';
        return { id: m.id, html: flipCardHtml(m.id, pick(m.title_zh, m.title_en), inner) };
      });
      var knownNote = known.length
        ? '<p class="cave-line small drill-flip-known">' + esc(pick(L.flip_known_zh, L.flip_known_en)) +
          ' ' + known.map(function (m) { return esc(pick(m.title_zh, m.title_en)); }).join(isEn() ? ', ' : '、') + '</p>'
        : '';
      return kicker(fill(pick(L.flip_kicker_zh, L.flip_kicker_en), { stage: state.stage + 1 })) +
        '<p class="cave-line small">' + esc(pick(L.flip_lead_zh, L.flip_lead_en)) + '</p>' +
        (pick(L.flip_leader_note_zh, L.flip_leader_note_en)
          ? '<p class="cave-line small drill-flip-leader-note"><span class="drill-leader-tri" aria-hidden="true">▼</span> ' +
            esc(pick(L.flip_leader_note_zh, L.flip_leader_note_en)) + '</p>' : '') +
        knownNote +
        flipCarouselHtml(cards, pick(L.flip_start_zh, L.flip_start_en), '🪨');
    }


    function pointsFor(m) {
      return (isEn() ? (m.points_en || m.points_zh) : (m.points_zh || m.points_en)) || [];
    }

    /* one direct line, not the step-by-step detail of the movement */
    function briefFor(m) {
      return pick(m.brief_zh, m.brief_en) ||
        pick((m.check || {}).why_zh, (m.check || {}).why_en) || '';
    }

    function countText(m) {
      var count = isEn() && m && m.count_en ? m.count_en : ((m && m.count) || '');
      return String(count).replace(/^打數：\s*/, '').replace(/^Count:\s*/i, '').trim();
    }

    function manualText(m) {
      if (!m || !m.manual) return '';
      return pick(m.manual, m.manual_en);
    }

    /* One study card per movement. The four paces used to share a single card,
       but four commands on one card cannot be read on a phone — the carousel
       now gives every movement its own turn on the board. */
    function studyUnitsFor(ids) {
      return (ids || []).map(moveById).filter(function (m) { return m; })
        .map(function (m) { return { id: m.id, moves: [m] }; });
    }

    function unitTitle(unit) {
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
      var isPrompt = variant === 'prompt';
      var ariaLabel = isPrompt
        ? pick(L.move_prompt_visual_zh || '石像示範的步操動作',
               L.move_prompt_visual_en || 'The drill movement shown by the statue')
        : pick(m.title_zh, m.title_en);
      /* a still plate can stay painted for the whole loop, so a frame change
         never opens a gap onto the dark card behind the pictures */
      var plate = m.plate && artUrl(m.plate)
        ? '<img class="drill-statue-plate" src="' + esc(artUrl(m.plate)) + '" alt="" decoding="sync">'
        : '';
      return '<span class="drill-statue-anim is-' + esc(variant || 'flip') +
             (plate ? ' has-plate' : '') + '"' +
             ' data-drill-animation="' + esc(m.id) + '" data-frame-count="' + frames.length + '"' +
             ' role="img" aria-label="' + esc(ariaLabel) + '">' +
        plate +
        frames.map(function (frame, index) {
          /* no caption under the statue: the animation itself is the teaching */
          return '<span class="drill-statue-step' + (index === 0 ? ' is-active' : '') + '"' +
                 ' data-drill-frame data-hold-ms="' + esc(frame.hold_ms || 900) + '">' +
            '<img src="' + esc(artUrl(frame.img)) + '" alt="" decoding="sync">' +
          '</span>';
        }).join('') +
      '</span>';
    }

    function commandActionLabel() {
      return pick(L.move_command_action_label_zh || '口令 → 動作',
                  L.move_command_action_label_en || 'Command → movement');
    }


    /* ── the study carousel: one card at a time, read them all to go on ───── */

    function flipCardHtml(id, label, inner) {
      var flipped = state.flipFace[id] === 'back' ? ' is-flipped' : '';
      return '<div class="drill-flip' + flipped + '" data-drill-flip="' + esc(id) + '" role="button" tabindex="0"' +
             ' aria-label="' + esc(label) + '">' +
        '<span class="drill-flip-corner is-tl" aria-hidden="true"></span>' +
        '<span class="drill-flip-corner is-tr" aria-hidden="true"></span>' +
        '<span class="drill-flip-corner is-bl" aria-hidden="true"></span>' +
        '<span class="drill-flip-corner is-br" aria-hidden="true"></span>' +
        '<div class="drill-flip-inner">' + inner + '</div>' +
      '</div>';
    }

    function flipReadCount() {
      return state.flipIds.filter(function (id) { return state.flipRead[id]; }).length;
    }

    function flipAllRead() {
      return state.flipIds.length > 0 && flipReadCount() === state.flipIds.length;
    }

    function flipGateText(allRead) {
      var total = state.flipIds.length;
      var left = total - flipReadCount();
      if (allRead) {
        return '✓ ' + esc(fill(pick(L.flip_gate_done_zh, L.flip_gate_done_en), { n: total }));
      }
      return esc(fill(pick(L.flip_gate_left_zh, L.flip_gate_left_en), { n: left, total: total }));
    }

    function flipCarouselHtml(cards, startLabel, cheer) {
      state.flipIds = cards.map(function (c) { return c.id; });
      if (state.flipIndex > cards.length - 1) state.flipIndex = cards.length - 1;
      if (state.flipIndex < 0) state.flipIndex = 0;
      var index = state.flipIndex;
      var allRead = flipAllRead();
      var dots = cards.map(function (c, i) {
        var cls = 'drill-flip-dot' + (i === index ? ' is-active' : '') +
                  (state.flipRead[c.id] ? ' is-read' : '');
        return '<button type="button" class="' + cls + '" data-drill-flip-go="jump"' +
               ' data-drill-flip-jump="' + esc(c.id) + '"' +
               ' aria-label="' + esc(fill(pick(L.flip_card_of_zh, L.flip_card_of_en), { i: i + 1, n: cards.length })) +
               '"></button>';
      }).join('');
      return '<div class="drill-flip-stage" data-drill-carousel="' + cards.length + '">' +
          '<div class="drill-flip-board" data-drill-flip-board>' + cards[index].html + '</div>' +
          '<div class="drill-flip-controls">' +
            '<div class="cave-actions drill-flip-start' + (allRead ? '' : ' is-locked') + '"><button class="btn primary big" type="button"' +
              ' data-drill-go="start-stage" data-cheer="' + esc(cheer) + '"' +
              (allRead ? '' : ' disabled aria-disabled="true"') + '>' + esc(startLabel) + '</button></div>' +
            '<div class="drill-flip-nav">' +
              '<button type="button" class="drill-flip-step' + (allRead ? '' : ' is-locked') + '" data-drill-flip-go="prev"' +
                (index === 0 ? ' disabled' : '') +
                ' aria-label="' + esc(pick(L.flip_prev_zh, L.flip_prev_en)) + '">‹</button>' +
              '<span class="drill-flip-count" data-drill-flip-count>' + (index + 1) + ' / ' + cards.length + '</span>' +
              '<button type="button" class="drill-flip-step' + (allRead ? '' : ' is-locked') + '" data-drill-flip-go="next"' +
                (index === cards.length - 1 ? ' disabled' : '') +
                ' aria-label="' + esc(pick(L.flip_next_zh, L.flip_next_en)) + '">›</button>' +
            '</div>' +
            (allRead ? '' :
              '<div class="drill-flip-walk"><button type="button" class="btn primary big"' +
                ' data-drill-flip-go="walk">' +
                esc(walkLabel()) +
                '</button></div>') +
            '<div class="drill-flip-dots' + (allRead ? '' : ' is-locked') + '" data-drill-flip-dots>' + dots + '</div>' +
          '</div>' +
        '</div>' +
        '<p class="drill-flip-gate' + (allRead ? ' is-done' : '') + '" data-drill-flip-gate>' +
          flipGateText(allRead) + '</p>' +
        '<div class="cave-actions drill-flip-start-below' + (allRead ? '' : ' is-locked') + '"><button class="btn primary big" type="button"' +
          ' data-drill-go="start-stage" data-cheer="' + esc(cheer) + '"' +
          (allRead ? '' : ' disabled aria-disabled="true"') + '>' + esc(startLabel) + '</button></div>';
    }

    /* turning a card over is what counts as reading it */
    function toggleFlipCard(node) {
      if (!node) return;
      node.classList.toggle('is-flipped');
      var id = node.getAttribute('data-drill-flip') || '';
      var back = node.classList.contains('is-flipped');
      if (id) {
        state.flipFace[id] = back ? 'back' : 'front';
        if (back) state.flipRead[id] = true;
      }
      paintFlipGate();
    }

    function paintFlipGate() {
      if (!card) return;
      var allRead = flipAllRead();
      var gate = card.querySelector('[data-drill-flip-gate]');
      if (gate) {
        gate.innerHTML = flipGateText(allRead);
        gate.classList.toggle('is-done', allRead);
      }
      Array.prototype.forEach.call(card.querySelectorAll('[data-drill-go="start-stage"]'), function (start) {
        if (allRead) {
          start.removeAttribute('disabled');
          start.removeAttribute('aria-disabled');
        } else {
          start.setAttribute('disabled', 'disabled');
          start.setAttribute('aria-disabled', 'true');
        }
      });
      /* the ‹ › arrows and the start arrow stay hidden until every card is open */
      Array.prototype.forEach.call(
        card.querySelectorAll('.drill-flip-start, .drill-flip-start-below, .drill-flip-step, .drill-flip-dots'),
        function (el) { el.classList.toggle('is-locked', !allRead); }
      );
      var walk = card.querySelector('.drill-flip-walk');
      if (walk) walk.classList.toggle('is-locked', allRead);
      var walkBtn = card.querySelector('[data-drill-flip-go="walk"]');
      if (walkBtn) walkBtn.textContent = walkLabel();
      Array.prototype.forEach.call(card.querySelectorAll('[data-drill-flip-go="jump"]'), function (dot) {
        dot.classList.toggle('is-read', !!state.flipRead[dot.getAttribute('data-drill-flip-jump')]);
      });
    }

    /* the last study card is finished by turning it over, never by "next" */
    function onLastFlipCard() {
      return state.flipIds.length > 0 && state.flipIndex === state.flipIds.length - 1;
    }

    function walkLabel() {
      var id = state.flipIds[state.flipIndex];
      if (id && state.flipRead[id] && !onLastFlipCard()) {
        return pick(L.flip_walk_next_zh, L.flip_walk_next_en);
      }
      return pick(L.flip_walk_zh, L.flip_walk_en);
    }

    /* let the turn be seen, then drop the walk button and show Start.
       A next press must not be what completes the lesson. */
    function finishFlipLesson() {
      var walk = card && card.querySelector('.drill-flip-walk');
      if (walk) walk.classList.add('is-locked');
      if (flipFinishTimer) window.clearTimeout(flipFinishTimer);
      flipFinishTimer = window.setTimeout(function () {
        flipFinishTimer = null;
        if (state.scene === 'flip' && flipAllRead()) say(flipHtml(), null, { instant: true });
      }, 520);
    }

    /* The guided first pass, one press = one clear action:
       press once and the current card turns over so the back can be read;
       press again and it moves on to the next card still to be read.
       The last card has no next: flipping it is what finishes the lesson. */
    function walkFlipCard() {
      if (!state.flipIds.length) return;
      var id = state.flipIds[state.flipIndex];
      var node = card && card.querySelector('[data-drill-flip]');
      if (!state.flipRead[id] && node) {
        var last = onLastFlipCard();
        toggleFlipCard(node);                     /* turn it over, stay here */
        if (last || flipAllRead()) finishFlipLesson();
        return;
      }
      var total = state.flipIds.length;
      var next = -1;
      for (var k = 1; k <= total; k += 1) {
        var j = (state.flipIndex + k) % total;
        if (!state.flipRead[state.flipIds[j]]) { next = j; break; }
      }
      /* arriving at the last card does not finish it — it still has to be flipped */
      if (next < 0 || next === state.flipIndex) return;
      state.flipIndex = next;
      say(flipHtml(), null, { instant: true });   /* move on, no entrance */
    }

    function goToFlipCard(index) {
      var total = state.flipIds.length;
      if (!total) return;
      var next = Math.max(0, Math.min(total - 1, index));
      if (next === state.flipIndex) return;
      state.flipIndex = next;
      say(flipHtml(), null, { instant: true });
    }

    /* the study statue is a 672×900 picture. Fit the card to that picture so
       an iPad uses the stage height instead of a short 3:4 box */
    function fitFlipCard() {
      if (!card) return;
      var board = card.querySelector('[data-drill-flip-board]');
      var flip = board && board.querySelector('[data-drill-flip]');
      if (!board || !flip) return;
      var w = board.clientWidth;
      var h = board.clientHeight;
      /* a short landscape window puts the controls beside the card, so the
         board is only as tall as the card. Use the height left on screen. */
      var stage = card.querySelector('.drill-flip-stage');
      if (stage && window.getComputedStyle(stage).flexDirection === 'row') {
        var controls = stage.querySelector('.drill-flip-controls');
        var reserve = controls ? controls.getBoundingClientRect().height + 16 : 150;
        var room = window.innerHeight - stage.getBoundingClientRect().top - reserve;
        if (room > 120) h = room;
      }
      if (!w || !h) return;
      var sample = flip.querySelector('.drill-flip-anim img, .drill-flip-front img');
      var ratio = (sample && sample.naturalWidth && sample.naturalHeight)
        ? sample.naturalWidth / sample.naturalHeight : 672 / 900;
      var height = Math.min(h, w / ratio);
      var width = height * ratio;
      flip.style.width = Math.round(width) + 'px';
      flip.style.height = Math.round(height) + 'px';
      /* a wide board leaves the card a column of empty space either side:
         on desktop the back may grow sideways to read its key points */
      var back = flip.querySelector('.drill-flip-back');
      if (back) {
        var wide = window.innerWidth >= 760;
        back.style.width = wide ? Math.round(Math.min(w, Math.max(width, 544))) + 'px' : '';
        back.style.left = '';
        back.style.right = '';
        if (wide) {
          var flapLeft = Math.round((Math.min(w, Math.max(width, 544)) - width) / 2);
          back.style.marginLeft = (-flapLeft) + 'px';
        } else {
          back.style.marginLeft = '';
        }
      }
    }


    function moveFrontCommandHtml(unit) {
      var m = unit.moves[0] || {};
      var command = m.command || '';
      var lengthClass = command.length > 32 ? ' is-very-long' : command.length > 20 ? ' is-long' : '';
      return '<span class="drill-move-front-command' + lengthClass + '">' +
        '<small>' + esc(pick(L.move_command_label_zh, L.move_command_label_en)) +
          ' · ' + esc(unitTitle(unit)) + '</small>' +
        '<strong>' + esc(command) + '</strong></span>';
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
          esc(pick(L.manual_label_zh, L.manual_label_en)) + ' — ' + esc(manualText(m)) + '</span>');
      } else if (m.leader_demo) {
        chips.push('<span class="drill-move-manual">' +
          esc(pick(L.move_leader_demo_zh, L.move_leader_demo_en)) + '</span>');
      }
      return chips.length ? '<span class="drill-move-meta">' + chips.join('') + '</span>' : '';
    }

    function moveCardFront(unit) {
      var m = unit.moves[0] || {};
      var frames = animationFrames(m);
      var image = m.figure || m.img || '';
      var body = frames.length
        ? movementAnimationHtml(m, 'flip')
        : image
        ? '<img src="' + esc(artUrl(image)) + '" alt="' + esc(unitTitle(unit)) + '">'
        : '<span class="drill-flip-command-front">' +
            '<strong>' + esc(unitTitle(unit)) + '</strong>' + moveMetaChips(m) +
          '</span>';
      return '<div class="drill-flip-face drill-flip-front is-move-front">' +
        moveFrontCommandHtml(unit) +
        '<span class="drill-move-front-visual">' + body + '</span>' +
        '<span class="drill-flip-hint">⟳ ' + esc(pick(L.flip_hint_zh, L.flip_hint_en)) + '</span></div>';
    }

    function moveCardBack(unit) {
      var m = unit.moves[0] || {};
      var brief = briefFor(m);
      var note = pick(m.note_zh, m.note_en);
      if (!note && m.study_group === 'pacing') note = pick(L.pace_card_note_zh, L.pace_card_note_en);
      return '<div class="drill-flip-face drill-flip-back is-move">' +
        '<span class="drill-flip-label">' + esc(commandActionLabel()) + '</span>' +
        '<strong class="drill-flip-name">' + esc(pick(m.title_zh, m.title_en)) + '</strong>' +
        '<span class="drill-move-command"><small>' +
          esc(pick(L.move_command_label_zh, L.move_command_label_en)) + '</small>' +
          '<strong>' + esc(m.command || '') + '</strong></span>' +
        moveMetaChips(m) +
        (brief ? '<span class="drill-flip-sign">' + esc(brief) + '</span>' : '') +
        (note ? '<span class="drill-flip-sign">' + esc(note) + '</span>' : '') +
      '</div>';
    }

    function moveFlipHtml() {
      var freshIds = movementStages[state.stage] || [];
      var fresh = studyUnitsFor(freshIds);
      var known = state.stage > 0 ? studyUnitsFor(cumulativeMovementPool(state.stage - 1).map(function (m) { return m.id; })) : [];
      var cards = fresh.map(function (unit) {
        return { id: unit.id, html: flipCardHtml(unit.id, unitTitle(unit), moveCardFront(unit) + moveCardBack(unit)) };
      });
      var knownNote = known.length
        ? '<p class="cave-line small drill-flip-known">' + esc(pick(L.move_flip_known_zh, L.move_flip_known_en)) +
          ' ' + known.map(function (unit) { return esc(unitTitle(unit)); }).join(isEn() ? ', ' : '、') + '</p>'
        : '';
      return kicker(fill(pick(L.move_flip_kicker_zh, L.move_flip_kicker_en), { stage: state.stage + 1 })) +
        '<p class="cave-line small">' + esc(pick(L.move_flip_lead_zh, L.move_flip_lead_en)) + '</p>' +
        knownNote +
        flipCarouselHtml(cards, pick(L.move_flip_start_zh, L.move_flip_start_en), '🥁');
    }

    function flipHtml() {
      return state.section === 2 ? moveFlipHtml() : signFlipHtml();
    }

    function showFlip(section, stageIndex) {
      state.section = movementStages.length && section === 2 ? 2 : 1;
      var lists = activeStageLists();
      state.stage = Math.max(0, Math.min(Math.max(0, lists.length - 1), stageIndex));
      state.scene = 'flip';
      state.flipIndex = 0;
      state.flipIds = [];
      state.flipRead = {};
      state.flipFace = {};
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

    function commandLengthClass(command) {
      var text = String(command || '');
      return text.length > 32 ? ' is-very-long' : text.length > 20 ? ' is-long' : '';
    }

    function commandBtn(m, locked) {
      var command = m.command || pick(m.title_zh, m.title_en);
      return '<button class="drill-command-btn' + commandLengthClass(command) +
             '" type="button" data-drill-form="' + esc(m.id) + '"' +
             ' data-drill-answer-kind="command"' + (locked ? ' disabled' : '') + '>' +
        '<span class="drill-command-answer">' + esc(command) + '</span>' +
      '</button>';
    }

    function movementPromptVisualHtml(m) {
      var frames = animationFrames(m);
      var kind = 'diagram';
      var visual = '';
      if (frames.length) {
        kind = 'animation';
        visual = movementAnimationHtml(m, 'prompt');
      } else if (m.figure && artUrl(m.figure)) {
        kind = 'figure';
        visual = '<img class="drill-move-prompt-figure" src="' + esc(artUrl(m.figure)) + '" alt=""' +
                 ' aria-label="' + esc(pick(L.move_prompt_visual_zh || '石像示範的步操動作',
                                             L.move_prompt_visual_en || 'The drill movement shown by the statue')) + '">';
      } else {
        visual = movementSvg(m.id, true);
      }
      return '<div class="drill-move-prompt-visual" data-drill-prompt-visual' +
             ' data-drill-prompt-move="' + esc(m.id) + '"' +
             ' data-drill-prompt-kind="' + kind + '">' + visual + '</div>';
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
      var waiting = animationFrames(m).length > 0;
      return kicker(fill(pick(L.move_prompt_kicker_zh, L.move_prompt_kicker_en),
                         { stage: state.stage + 1, stages: movementStages.length })) +
        '<p class="drill-command-say">' +
          esc(pick(L.move_prompt_watch_zh || '看石像動作',
                   L.move_prompt_watch_en || 'Watch the statue’s movement')) + '</p>' +
        '<div class="drill-move-prompt-layout">' +
          movementPromptVisualHtml(m) +
          '<div class="drill-move-prompt-side' + (waiting ? ' is-waiting' : '') + '" data-drill-answers' +
            (waiting ? ' aria-busy="true"' : '') + '>' +
            '<h3 class="cave-subtitle drill-move-question">' +
              esc(pick(L.move_prompt_q_zh, L.move_prompt_q_en)) + '</h3>' +
            '<p class="drill-watch-note">' +
              esc(pick(L.move_prompt_wait_zh || '看完動作才可作答，時間那時才開始',
                       L.move_prompt_wait_en || 'Answers and the count start when the movement finishes')) +
            '</p>' +
            '<div class="drill-beat" data-drill-beat aria-hidden="true">' +
              '<div class="drill-beat-fill" data-drill-beat-fill></div>' +
            '</div>' +
            '<p class="drill-beat-note"><span>' +
              esc(pick(L.move_prompt_beat_zh || '在打數之內選出口令',
                       L.move_prompt_beat_en || 'choose the command inside the count')) + '</span>' +
              '<span data-drill-beat-count>' +
                esc(fill(pick(L.beat_of_zh, L.beat_of_en), { i: 1, n: beats })) +
              '</span></p>' +
            '<div class="drill-form-row is-commands is-count-' + state.forms.length + '" data-drill-forms' +
              ' data-answer-kind="command" data-answer-count="' + state.forms.length + '"' +
              ' style="--answer-count:' + state.forms.length + '">' +
              state.forms.map(function (choice) { return commandBtn(choice, waiting); }).join('') +
            '</div>' +
          '</div>' +
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
      if (state.section === 2) state.forms = movementChoicesFor(m);
      state.busy = false;
      state.scene = 'drill';
      setArt(state.section === 2 ? ridgeArt() : (m.figure || m.img || ridgeArt()));
      /* section 1: the leader statue shows the sign in the picture frame.
         Section 2: the large movement prompt lives inside the full-screen card,
         with the commands below it (or beside it on a wide screen). */
      var waiting = state.section === 2 && animationFrames(m).length > 0;
      state.armPrompt = waiting;
      say(promptHtml(m));
      mark('drill');
      bringStageIntoView();
      paintProgress();
      /* the count, and the finish clock, wait until the movement has played */
      if (waiting) state.watchFrom = Date.now();
      else startBeats();
    }

    function beginStage(section, stageIndex) {
      state.section = movementStages.length && section === 2 ? 2 : 1;
      var lists = activeStageLists();
      state.stage = Math.max(0, Math.min(Math.max(0, lists.length - 1), stageIndex));
      var pool = activePool(state.stage);
      state.pool = pool;
      state.forms = shuffled(pool);      /* fixed in section 1 and movement stage 1;
                                            stages 2 and 3 rebuild four choices */
      state.queue = shuffled(pool.map(function (m) { return m.id; }));
      nextInStage();
    }

    function nextInStage() {
      if (!state.queue.length) { stageDone(); return; }
      var m = moveById(state.queue.shift());
      if (!m) { nextInStage(); return; }
      renderPrompt(m);
    }

    /* the answer keeps the statue that is already on top. The notes go under
       it — a second, smaller animation in the description only repeats it. */
    function moveAnswerCopyHtml(m, opts) {
      opts = opts || {};
      var brief = briefFor(m);
      var count = countText(m);
      var text = '<div class="drill-answer-text">' +
        (opts.heading ? '<h2 class="cave-subtitle">' + esc(opts.heading) + '</h2>' : '') +
        '<p class="drill-answer-name">' + esc(pick(m.title_zh, m.title_en)) + '</p>' +
        (m.command ? '<p class="drill-command drill-command-feedback">' + esc(m.command) + '</p>' : '') +
        (count ? '<p class="drill-answer-count"><b>' +
          esc(pick(L.move_count_label_zh, L.move_count_label_en)) + '</b> ' + esc(count) + '</p>' : '') +
        (brief ? '<p class="drill-answer-brief">' + esc(brief) + '</p>' : '') +
      '</div>' +
        (opts.action || '');
      return '<div class="drill-answer-copy">' + text + '</div>';
    }

    function moveAnswerFallbackHtml(m, title, kind, opts) {
      var visual = animationFrames(m).length
        ? movementAnimationHtml(m, 'prompt')
        : (m.figure && artUrl(m.figure)
          ? '<img class="drill-move-prompt-figure" src="' + esc(artUrl(m.figure)) + '" alt="">'
          : movementSvg(m.id, true));
      return kicker(title, kind) +
        '<div class="drill-move-prompt-layout drill-answer-layout">' +
          '<div class="drill-move-prompt-visual" data-drill-prompt-visual>' + visual + '</div>' +
          moveAnswerCopyHtml(m, opts) +
        '</div>';
    }

    function replayAnswerAnimation() {
      var node = card && card.querySelector('.drill-move-prompt-visual .drill-statue-anim');
      if (!node || statueTimer) return;
      runStatueLoop([node], false);
    }

    function revealMoveAnswer(m, title, kind, opts) {
      var layout = card && card.querySelector('.drill-move-prompt-layout');
      var visual = layout && layout.querySelector('[data-drill-prompt-visual]');
      if (!layout || !visual) return false;
      state.armPrompt = false;
      endWatch();
      if (beatTimer) { window.clearInterval(beatTimer); beatTimer = null; }
      if (advanceTimer) { window.clearTimeout(advanceTimer); advanceTimer = null; }
      if (armTimer) { window.clearTimeout(armTimer); armTimer = null; }
      var kickerEl = card.querySelector('.cave-kicker');
      if (kickerEl) kickerEl.hidden = true;
      var watch = card.querySelector('.drill-command-say');
      if (watch) watch.hidden = true;
      layout.classList.add('drill-answer-layout');
      var copyOpts = {};
      var key;
      for (key in (opts || {})) copyOpts[key] = opts[key];
      copyOpts.heading = title;
      var copy = moveAnswerCopyHtml(m, copyOpts);
      var side = layout.querySelector('.drill-move-prompt-side, .drill-answer-copy');
      if (side) side.outerHTML = copy;
      else layout.insertAdjacentHTML('beforeend', copy);
      replayAnswerAnimation();
      return true;
    }

    function answerPick(pickedId) {
      /* the commands are not a choice until the statue has finished */
      if (state.busy || state.armPrompt || state.scene !== 'drill' || !state.current) return;
      var m = state.current;
      if (pickedId === m.id) {
        state.busy = true;
        clearTimers({ keepStatue: true });
        answers[m.id] = (m.check || {}).answer;
        save();
        chime();
        var why = pick((m.check || {}).why_zh, (m.check || {}).why_en);
        var isMove = state.section === 2;
        var rightTitle = isMove ? pick(L.move_right_title_zh, L.move_right_title_en)
                                : pick(L.right_title_zh, L.right_title_en);
        if (!(isMove && revealMoveAnswer(m, rightTitle, 'good', { points: false }))) {
          say(kicker(rightTitle, 'good') +
              '<h2 class="cave-subtitle">' + esc(pick(m.title_zh, m.title_en)) + '</h2>' +
              (isMove && m.command ? '<p class="drill-command drill-command-feedback">' + esc(m.command) + '</p>' : '') +
              (why ? '<p class="drill-why drill-teach-why"><b>' + esc(pick(L.remember_zh, L.remember_en)) +
                    '</b> ' + esc(why) + '</p>' : ''));
        }
        burstOn(card.querySelector('.drill-answer-copy .cave-subtitle, .cave-kicker'), isMove ? ['✨', '🥁'] : ['✨', '🪨']);
        paintProgress();
        advanceTimer = window.setTimeout(nextInStage, 1000);
        return;
      }
      clearTimers({ keepStatue: true });
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
      if (isMoveReview && countText(m)) reviewChips.push(chip(pick(L.move_count_label_zh, L.move_count_label_en) + (isEn() ? ': ' : '：') + countText(m)));
      if (m.manual) reviewChips.push(chip('📖 ' + pick(L.manual_label_zh, L.manual_label_en) + ' — ' + manualText(m)));
      if (isMoveReview && m.leader_demo) reviewChips.push(chip(pick(L.move_leader_demo_zh, L.move_leader_demo_en), 'is-demo'));
      if (isMoveReview) {
        var again = '<div class="cave-actions"><button class="btn primary" type="button" data-drill-go="resume">' +
          esc(pick(L.review_again_zh, L.review_again_en)) + '</button></div>';
        var answerOpts = { points: true, action: again };
        if (!revealMoveAnswer(m, title, 'bad', answerOpts)) {
          say(moveAnswerFallbackHtml(m, title, 'bad', answerOpts));
        }
        mark('review');
        paintProgress();
        return;
      }
      var reviewVisual = ((m.figure ? '<img class="drill-review-fig" src="' + esc(artUrl(m.figure)) + '"' +
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
          (briefFor(m) ? '<p class="drill-answer-brief">' + esc(briefFor(m)) + '</p>' : '') +
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
      /* 讀完介紹、真正開始操練才計時；榜上的完成時間由這裡起 */
      if (!state.startedAt && scene !== 'intro') state.startedAt = Date.now();
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
      var elapsed = state.startedAt ? Date.now() - state.startedAt : 0;
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
      if (elapsed) body.append('elapsed_ms', String(elapsed));
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

    function demoApprove() {
      /* the offline demo file has no leader account behind it: one clearly
         labelled button stands in for the leader's approval. The live page
         never sets this flag. */
      return !!(cfg.assess && cfg.assess.demo_approve);
    }

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
        '<div class="drill-wait" data-drill-wait>' +
          '<span class="drill-wait-row">' +
            '<button class="btn" type="button" data-drill-go="check">🔄 ' +
              esc(pick(a.refresh_zh, a.refresh_en)) + '</button>' +
            (demoApprove() ? '<button class="btn primary" type="button" data-drill-go="demo-approve">🔓 ' +
              esc(pick(a.demo_approve_zh, a.demo_approve_en)) + '</button>' : '') +
          '</span>' +
          (demoApprove() ? '<p class="cave-line small drill-wait-demo">' +
            esc(pick(a.demo_note_zh, a.demo_note_en)) + '</p>' : '') +
          '<p class="drill-code-note" data-drill-wait-note hidden></p>' +
        '</div>' +
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
      startWaiting();
    }

    function waitNote(text, bad) {
      if (!card) return;
      var slot = card.querySelector('[data-drill-wait-note]');
      if (!slot) return;
      slot.textContent = text || '';
      slot.classList.toggle('is-bad', !!bad);
      slot.hidden = !text;
    }

    /* ── the wait: ask the server whether the leader has approved yet ─────── */

    function stopWaiting() {
      if (state.waitTimer) { window.clearInterval(state.waitTimer); state.waitTimer = 0; }
    }

    function checkStatus(manual) {
      var a = cfg.assess || {};
      var url = cfg.status_url;
      if (!url) {                       // offline demo: nothing to ask
        if (manual) waitNote(pick(a.refresh_waiting_zh, a.refresh_waiting_en));
        return;
      }
      if (state.busy) return;
      state.busy = true;
      if (manual) waitNote(pick(a.refresh_checking_zh, a.refresh_checking_en));
      fetch(url, { credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } })
        .then(function (response) {
          return response.json().catch(function () { return { ok: false }; });
        })
        .then(function (data) {
          state.busy = false;
          if (data && data.ok && data.status === 'completed') { stopWaiting(); result(); return; }
          if (manual) waitNote(pick(a.refresh_waiting_zh, a.refresh_waiting_en));
        })
        .catch(function () {
          state.busy = false;
          if (manual) waitNote(pick(a.refresh_error_zh, a.refresh_error_en), true);
        });
    }

    function startWaiting() {
      stopWaiting();
      if (!cfg.status_url) return;      // the offline demo approves by its button
      state.waitTimer = window.setInterval(function () {
        if (state.scene !== 'result') { stopWaiting(); return; }
        checkStatus(false);
      }, 20000);
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
      stopWaiting();
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
      stopWaiting();
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
    exitOverlay.className = 'cave-exit-overlay';
    exitOverlay.hidden = true;
    /* the same centred dialog the cave shows: one look for every game */
    exitOverlay.innerHTML =
      '<div class="cave-exit-dialog" role="alertdialog" aria-modal="true" ' +
        'aria-labelledby="drill-exit-title" aria-describedby="drill-exit-message">' +
        '<span class="cave-kicker">' + esc(pick(L.leave_kicker_zh, L.leave_kicker_en)) + '</span>' +
        '<h2 id="drill-exit-title">' + esc(pick(L.leave_title_zh, L.leave_title_en)) + '</h2>' +
        '<p id="drill-exit-message">' + esc(pick(L.leave_lead_zh, L.leave_lead_en)) + '</p>' +
        '<div class="cave-exit-actions">' +
          '<button type="button" class="btn primary" data-drill-stay>' + esc(pick(L.leave_stay_zh, L.leave_stay_en)) + '</button>' +
          '<button type="button" class="btn ghost" data-drill-leave>' + esc(pick(L.leave_go_zh, L.leave_go_en)) + '</button>' +
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
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); finishExit(false); return; }
      if (event.key !== 'Tab') return;
      /* keep the keyboard inside the dialog, like the cave does */
      var stay = exitOverlay.querySelector('[data-drill-stay]');
      var leave = exitOverlay.querySelector('[data-drill-leave]');
      if (event.shiftKey && document.activeElement === stay) {
        event.preventDefault(); leave.focus();
      } else if (!event.shiftKey && document.activeElement === leave) {
        event.preventDefault(); stay.focus();
      }
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
      var flipGo = event.target.closest('[data-drill-flip-go]');
      if (flipGo) {
        event.preventDefault();
        tap();
        var step = flipGo.getAttribute('data-drill-flip-go');
        if (step === 'prev' || step === 'jump') {
          if (!flipAllRead()) return;
          if (step === 'prev') goToFlipCard(state.flipIndex - 1);
          else goToFlipCard(state.flipIds.indexOf(flipGo.getAttribute('data-drill-flip-jump')));
        } else if (step === 'next') {
          /* an unread lesson has no skip arrow: next flips this card and stays */
          if (!flipAllRead()) walkFlipCard();
          else goToFlipCard(state.flipIndex + 1);
        } else if (step === 'walk') walkFlipCard();
        return;
      }
      var flipCard = event.target.closest('[data-drill-flip]');
      if (flipCard) {
        event.preventDefault();
        var unreadLast = onLastFlipCard() && !state.flipRead[flipCard.getAttribute('data-drill-flip')];
        toggleFlipCard(flipCard);
        tap();
        if (unreadLast && flipAllRead()) finishFlipLesson();
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
      if (where === 'start-stage') {
        if (!flipAllRead()) {
          /* the gate is real: the mechanism stays asleep until every card is read */
          var gate = card && card.querySelector('[data-drill-flip-gate]');
          if (gate) {
            gate.classList.add('is-warn');
            window.setTimeout(function () { gate.classList.remove('is-warn'); }, 900);
          }
          return;
        }
        tap();
        beginStage(state.section, state.stage);
        return;
      }
      if (where === 'next-stage') { tap(); showFlip(state.section, state.stage + 1); return; }
      if (where === 'section-done') { tap(); sectionDone(); return; }
      if (where === 'section2') { tap(); showFlip(2, firstOpenMovementStage()); return; }
      if (where === 'resume') { tap(); nextInStage(); return; }
      if (where === 'finish') { finish(); return; }
      if (where === 'restart') { stopWaiting(); restart(); return; }
      if (where === 'check') { tap(); checkStatus(true); return; }
      if (where === 'demo-approve') { chime(); stopWaiting(); result(); return; }
    });
    root.addEventListener('keydown', function (event) {
      if (state.scene === 'flip' && (event.key === 'ArrowLeft' || event.key === 'ArrowRight')) {
        event.preventDefault();
        if (!flipAllRead()) {
          if (event.key === 'ArrowRight') walkFlipCard();
          return;
        }
        goToFlipCard(state.flipIndex + (event.key === 'ArrowRight' ? 1 : -1));
        return;
      }
      if (event.key !== 'Enter' && event.key !== ' ') return;
      var flipCard = event.target.closest && event.target.closest('[data-drill-flip]');
      if (flipCard) {
        event.preventDefault();
        toggleFlipCard(flipCard);
        tap();
      }
    });
    window.addEventListener('resize', function () { fitFlipCard(); });

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
