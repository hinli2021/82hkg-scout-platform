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

   Section 2 (the 步操 commands, down on the parade ground) is coming soon;
   the studying is filed and the leader's 考核 code (82DR) only enters the
   picture once both sections are cleared. A scout who has already studied
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

  /* the little formation diagrams on the square buttons — seven dots-and-
     spaces pictures, one to a sign, drawn inline so no asset is fetched */
  function formationSvg(id) {
    var dot = function (x, y, r) {
      return '<circle cx="' + x + '" cy="' + y + '" r="' + (r || 3.1) + '"/>';
    };
    var row = function (y, xs, r) { return xs.map(function (x) { return dot(x, y, r); }).join(''); };
    var arts = {
      'sign-line': function () { return row(18, [6, 12, 18, 24, 30]); },
      'sign-line-tall': function () {
        return dot(6, 18, 4.4) + dot(12, 18, 3.8) + dot(18, 18, 3.1) + dot(24, 18, 2.5) + dot(30, 18, 1.9);
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
    return '<svg class="drill-form-art" viewBox="0 0 36 36" aria-hidden="true" focusable="false">' +
           (arts[id] || arts['sign-line'])() + '</svg>';
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

    /* the play itself: section 1's stages, each a list of new sign ids */
    var game = cfg.game || {};
    var signStages = (game.sign_stages || []).filter(function (row) { return row && row.length; });
    if (!signStages.length) {
      signStages = [allMoves().filter(function (m) { return !m.command; }).map(function (m) { return m.id; })];
    }
    var allSigns = cumulativePool(signStages.length - 1);

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
    function clearTimers() {
      if (beatTimer) { window.clearInterval(beatTimer); beatTimer = null; }
      if (advanceTimer) { window.clearTimeout(advanceTimer); advanceTimer = null; }
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
    function cumulativePool(stageIndex) {
      var ids = [];
      for (var i = 0; i <= stageIndex && i < signStages.length; i += 1) {
        signStages[i].forEach(function (id) { if (ids.indexOf(id) < 0) ids.push(id); });
      }
      return ids.map(moveById).filter(function (m) { return m; });
    }
    function movePassed(m) { return answers[m.id] !== undefined; }
    function signsDone() { return allSigns.filter(movePassed).length; }
    function allStagesPassed() { return allSigns.every(movePassed); }
    function firstOpenStage() {
      for (var i = 0; i < signStages.length; i += 1) {
        if (cumulativePool(i).some(function (m) { return !movePassed(m); })) return i;
      }
      return signStages.length - 1;
    }

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
    }
    function kicker(text, kind) {
      return '<span class="cave-kicker' + (kind ? ' cave-kicker-' + kind : '') + '">' + esc(text) + '</span>';
    }
    function chip(text, cls) {
      return '<span class="drill-chip' + (cls ? ' ' + cls : '') + '">' + esc(text) + '</span>';
    }

    function paintProgress() {
      if (!progress) return;
      progress.textContent = fill(pick(L.progress_zh, L.progress_en) || '', {
        done: signsDone(), total: allSigns.length,
        stage: state.stage + 1, stages: signStages.length
      }) || pick(L.hud_zh, L.hud_en) || '';
    }

    /* ── the flip cards: this stage's new signs, big and clear ────────────── */

    function signFaceText(m) {
      /* the first point names the sign itself: 手號：兩手握拳… → the card */
      var points = (isEn() ? (m.points_en || m.points_zh) : (m.points_zh || m.points_en)) || [];
      var text = String(points[0] || '');
      return text.replace(/^手號：/, '').replace(/^Sign:\s*/i, '');
    }

    function flipHtml() {
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
              formationSvg(m.id) +
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
        '<div class="drill-flip-grid">' + cards + '</div>' +
        knownNote +
        '<div class="cave-actions"><button class="btn primary big" type="button" data-drill-go="start-stage" data-cheer="🪨">' +
          esc(pick(L.flip_start_zh, L.flip_start_en)) + '</button></div>';
    }

    function showFlip(stageIndex) {
      state.stage = Math.max(0, Math.min(signStages.length - 1, stageIndex));
      state.scene = 'flip';
      setArt(ridgeArt());
      say(flipHtml());
      mark('flip');
      bringStageIntoView();
      paintProgress();
    }

    /* ── the live mechanism: a sign on the rock, the count running ────────── */

    function beatMs() { return 1500; }
    function beatCount() { return 3; }      /* three beats to every sign */

    function formationBtn(m) {
      return '<button class="drill-form-btn" type="button" data-drill-form="' + esc(m.id) + '"' +
             ' aria-label="' + esc(pick(m.title_zh, m.title_en)) + '">' +
        '<span class="drill-form-name">' + esc(pick(m.title_zh, m.title_en)) + '</span>' +
        formationSvg(m.id) +
      '</button>';
    }

    function promptHtml(m) {
      var beats = beatCount();
      var total = Math.max(4000, beats * beatMs());
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

    function startBeats() {
      var beats = beatCount();
      var total = Math.max(4000, beats * beatMs());
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
          var beat = Math.min(beats, Math.floor(elapsed / beatMs()) + 1);
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
      setArt(m.figure || m.img || ridgeArt());   /* the leader statue shows the sign */
      say(promptHtml(m));
      mark('drill');
      bringStageIntoView();
      paintProgress();
      startBeats();
    }

    function beginStage(stageIndex) {
      state.stage = Math.max(0, Math.min(signStages.length - 1, stageIndex));
      var pool = cumulativePool(state.stage);
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
        say(kicker(pick(L.right_title_zh, L.right_title_en), 'good') +
            '<h2 class="cave-subtitle">' + esc(pick(m.title_zh, m.title_en)) + '</h2>' +
            (why ? '<p class="drill-why drill-teach-why"><b>' + esc(pick(L.remember_zh, L.remember_en)) +
                  '</b> ' + esc(why) + '</p>' : ''));
        burstOn(card.querySelector('.cave-kicker'), ['✨', '🪨']);
        paintProgress();
        advanceTimer = window.setTimeout(nextInStage, 1000);
        return;
      }
      clearTimers();
      thud();
      reviewCard(m, pick(L.wrong_title_zh, L.wrong_title_en));
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
      setArt(m.figure || m.img || ridgeArt());
      var points = (isEn() ? (m.points_en || m.points_zh) : (m.points_zh || m.points_en)) || [];
      var why = pick((m.check || {}).why_zh, (m.check || {}).why_en);
      say(kicker(title, 'bad') +
          '<h2 class="cave-subtitle">' + esc(fill(pick(L.review_lead_zh, L.review_lead_en),
                                                  { name: pick(m.title_zh, m.title_en) })) + '</h2>' +
          (m.manual ? '<div class="drill-chips">' + chip('📖 ' + pick(L.manual_label_zh, L.manual_label_en) +
                   ' — ' + m.manual, 'is-manual') + '</div>' : '') +
          '<div class="drill-review-form">' +
            (m.figure ? '<img class="drill-review-fig" src="' + esc(artUrl(m.figure)) + '"' +
                         ' alt="' + esc(pick(m.title_zh, m.title_en)) + '">' : '') +
            formationSvg(m.id) +
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
    }

    function show(scene) {
      state.scene = scene;
      mark(scene);
      if (scene === 'intro') {
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
      sections.forEach(function (s) {
        (s.moves || []).forEach(function (m) {
          body.append('check_' + m.id, String(answers[m.id] !== undefined ? answers[m.id] : (m.check || {}).answer));
        });
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
        if (allStagesPassed()) sectionDone();
        else showFlip(firstOpenStage());
        return;
      }
      if (where === 'start-stage') { tap(); beginStage(state.stage); return; }
      if (where === 'next-stage') { tap(); showFlip(state.stage + 1); return; }
      if (where === 'section-done') { tap(); sectionDone(); return; }
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
      sections.forEach(function (s) {
        (s.moves || []).forEach(function (m) {
          if (answers[m.id] === undefined) answers[m.id] = (m.check || {}).answer;
        });
      });
      assess();
    } else if (cfg.completed_now) {
      sections.forEach(function (s) {
        (s.moves || []).forEach(function (m) {
          if (answers[m.id] === undefined) answers[m.id] = (m.check || {}).answer;
        });
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
