/* ── 迷霧渡口 — 第 5 項的第二個遊戲 ─────────────────────────────────────────
   Three stages across a river: 銘言 (two characters), 誓詞 (four lines), 規律
   (seven points). Each stage opens with a teaching card; closing it hands the
   scout a pile of planks to lay in order. A board laid too early slips into the
   river, the teaching card is shown again and that plank is laid once more. All
   three stages laid and the crossing holds — which is what clears the item.

   The same shape as cave.js on purpose: one browser-side state machine, the
   route hands over every word and picture, so the identical game plays inside
   the offline demo file, with the same exit warning on the way out.
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

  function mountOne(root) {
    if (!root || root.getAttribute('data-bridge-bound') === '1') return;
    var cfg = null;
    try { cfg = JSON.parse(root.getAttribute('data-bridge-config') || '{}'); } catch (e) { cfg = null; }
    if (!cfg || !cfg.stages || !cfg.stages.length) return;
    root.setAttribute('data-bridge-bound', '1');

    var L = cfg.labels || {};
    var art = root.querySelector('.cave-art');
    var backdrop = root.querySelector('.cave-art-backdrop');
    var card = root.querySelector('[data-bridge-card]');
    var moreCue = root.querySelector('[data-bridge-more]');
    var panel = card ? card.parentElement : null;
    /* the cue and the scrolling panel (the card's parent) are looked up after
       the card itself: naming the parent first left the cue永远 hidden */
    var moreCue = root.querySelector('[data-bridge-more]');
    var panel = card ? card.parentElement : null;
    var progress = root.querySelector('[data-bridge-progress]');
    var total = cfg.stages.length;

    /* every painting waits in the hidden block; remember the one on screen first */
    var urls = {};
    urls[(cfg.intro || {}).image || 'bank'] = art ? art.getAttribute('src') : '';
    Array.prototype.forEach.call(root.querySelectorAll('.cave-sources [data-bridge-art]'),
      function (node) { urls[node.getAttribute('data-bridge-art')] = node.getAttribute('src'); });
    function artUrl(name) {
      if (urls[name]) return urls[name];
      var node = root.querySelector('.cave-sources [data-bridge-art="' + name + '"]');
      return node ? node.getAttribute('src') : '';
    }

    var state = {
      scene: 'intro',          /* intro · teach · build · built · crossed · result */
      stage: 0,
      laid: [],                // planks already on the bridge, this stage
      pool: [],                // planks still lying on the bank
      wrongKey: '',
      busy: false
    };

    var shuffled = function (list) {
      var out = list.slice();
      for (var i = out.length - 1; i > 0; i--) {
        var j = Math.floor(Math.random() * (i + 1));
        var swap = out[i]; out[i] = out[j]; out[j] = swap;
      }
      return out;
    };
    function stage() { return cfg.stages[state.stage] || cfg.stages[0]; }
    /* What a plank says. The board is judged on this, never on the key: several
       planks may read the same (every law point begins with 童軍), and then any
       copy of the right word is the right word. */
    function plankLabel(plank) {
      if (!plank) return '';
      return String(isEn() ? (plank.en || plank.zh) : (plank.zh || plank.en)) || '';
    }
    /* each stage may carry its own painting; the shared one is the fallback */
    function stageArt() { return stage().image || (cfg.planks || {}).image || 'bank'; }
    function laidCount() { return state.laid.length; }
    function plankTotal() { return (stage().planks || []).length; }
    /* 誓詞、規律、銘言以正常句子示人：一句一句讀，不切割、不畫箭嘴 */
    function sentencesOf(target) {
      var teach = target.teach || target || {};
      var list = isEn() ? (teach.sentences_en || teach.sentences_zh)
                        : (teach.sentences_zh || teach.sentences_en);
      if (list && list.length) return toLines(list);
      var text = pick(target.chain_zh || teach.chain_zh || '', target.chain_en || teach.chain_en || '');
      if (text) return [text];
      return [(target.planks || []).map(function (p) { return pick(p.zh, p.en); }).join('、')];
    }
    function chainOf(target) { return sentencesOf(target).join(pick('　', ' ')); }

    function setArt(name) {
      if (art && name && artUrl(name) && art.getAttribute('src') !== artUrl(name)) {
        art.setAttribute('data-bridge-art', name);
        art.setAttribute('src', artUrl(name));
        if (backdrop) backdrop.setAttribute('src', artUrl(name));   // the matte
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

    function say(html, emoji) {
      if (!card) return;
      card.innerHTML = html;
      // the panel scrolls under the picture: a new scene starts at its heading
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
    function toLines(value) {
      /* one sentence is allowed to stand for a list of one */
      if (value == null) return [];
      return Object.prototype.toString.call(value) === '[object Array]' ? value : [value];
    }
    function lines(list, cls) {
      return toLines(list).map(function (text) {
        return '<p class="cave-line' + (cls ? ' ' + cls : '') + '">' + esc(text) + '</p>';
      }).join('');
    }
    /* 教學牌先給原文，再逐句給說明：一行原文、一行細節，兩者都不缺。
       opts.details 為 false 時只列原文（河岸的次序框用這個，保持一眼看完）。 */
    function wordingBox(target, opts) {
      opts = opts || {};
      var teach = target || {};
      var name = pick((cfg.planks || {}).label_zh, (cfg.planks || {}).label_en) || '';
      var notes = opts.details === false ? []
                : toLines(isEn() ? (teach.details_en || teach.details_zh) : teach.details_zh);
      var body = sentencesOf(teach).map(function (text, i) {
        return '<span class="bridge-said-item">' +
                 '<span class="bridge-goal-line">' + esc(text) + '</span>' +
                 (notes[i] ? '<span class="bridge-said-note">' + esc(notes[i]) + '</span>' : '') +
               '</span>';
      }).join('');
      return (opts.label === false ? '' : '<p class="bridge-goal-label">' + esc(name) + '</p>') +
        '<div class="bridge-goal bridge-said">' + body + '</div>';
    }

    /* ── the bridge itself ─────────────────────────────────────────────────── */

    function slotHtml(index) {
      var plank = state.laid[index];
      var number = fill(pick(L.slot_zh, L.slot_en) || '第 {i} 塊', { i: index + 1 });
      if (!plank) {
        return '<span class="bridge-slot is-empty"><b>' + esc(number) + '</b>' +
               '<i>' + esc(pick(L.empty_zh, L.empty_en) || '') + '</i></span>';
      }
      var text = pick(plank.zh, plank.en);
      return '<span class="bridge-slot is-laid' + (text.length > 10 ? ' has-long' : '') + '"><b>' +
             esc(number) + '</b><span class="bridge-board">' + esc(text) + '</span></span>';
    }

    /* 同一句的木板排成一行：先按木板上的 line 分組，再把每行的空格畫出來 */
    function plankRows(st) {
      var planks = (st && st.planks) || [];
      var lined = planks.some(function (row) { return Number(row.line) > 0; });
      var rows = [];
      planks.forEach(function (plank) {
        var no = lined ? (Number(plank.line) || 0) : 1;
        var last = rows[rows.length - 1];
        if (!last || last.no !== no) { last = { no: no, planks: [] }; rows.push(last); }
        last.planks.push(plank);
      });
      var names = (st && st.rows_zh) || [], namesEn = (st && st.rows_en) || [];
      rows.forEach(function (row, i) {
        row.label = pick(names[i], namesEn[i]) || '';
      });
      return rows;
    }

    function bridgeHtml() {
      var index = 0;
      var rail = plankRows(stage()).map(function (row) {
        var slots = row.planks.map(function () {
          var html = slotHtml(index);
          index += 1;
          return html;
        }).join('');
        return '<div class="bridge-line">' +
                 (row.label ? '<span class="bridge-line-label">' + esc(row.label) + '</span>' : '') +
                 '<div class="bridge-slots" role="list">' + slots + '</div>' +
               '</div>';
      }).join('');
      var pool = state.pool.map(function (plank) {
        var wrong = state.wrongKey === plank.key;
        return '<button class="bridge-plank' + (wrong ? ' is-wrong' : '') + '" type="button" ' +
               'data-bridge-plank="' + esc(plank.key) + '">' + esc(pick(plank.zh, plank.en)) + '</button>';
      }).join('') || '<span class="cave-line small">' +
         esc(pick('木板都用完了。', 'Every plank is on the bridge.')) + '</span>';
      return '<div class="bridge-bench">' +
               '<div class="bridge-rail">' + rail + '</div>' +
             '</div>' +
             '<p class="cave-line small">' + esc(pick(L.pool_zh, L.pool_en) || '') + '</p>' +
             '<div class="bridge-planks" role="group">' + pool + '</div>';
    }

    function teachHtml(again) {
      var teach = stage().teach || {};
      var hint = again
        ? '<p class="cave-line small">' + esc(pick('次序要記牢：', 'Hold the order in mind: ') ) +
          esc(pick(teach.chain_zh, teach.chain_en)) + '</p>' : '';
      return kicker(fill(pick(L.card_kicker_zh, L.card_kicker_en) || '第 {n} 關', { n: stage().n })) +
        '<h2 class="cave-subtitle">' + esc(pick(teach.title_zh, teach.title_en)) + '</h2>' +
        lines(isEn() ? (teach.lead_en || teach.lead_zh) : teach.lead_zh, 'small') +
        /* 教學牌的正文：原文一行、說明一行 */
        wordingBox(teach, { details: true }) +
        lines(isEn() ? (teach.note_en || teach.note_zh) : teach.note_zh, 'small') + hint +
        '<div class="cave-actions">' +
          '<button class="btn primary big" type="button" data-bridge-go="build">' +
            esc(pick(L.card_button_zh, L.card_button_en) || '') + '</button>' +
        '</div>';
    }

    function mark(name) {
      // a plain hook for the walkthrough checks (and for anyone styling per scene)
      root.setAttribute('data-bridge-scene', name);
    }

    function show(scene) {
      state.scene = scene;
      mark(scene);
      var st = stage();
      if (scene === 'intro') {
        setArt((cfg.intro || {}).image || 'bank');
        say(kicker(pick((cfg.intro || {}).kicker_zh, (cfg.intro || {}).kicker_en)) +
            '<h1 class="cave-title">' + esc(pick((cfg.intro || {}).title_zh, (cfg.intro || {}).title_en)) + '</h1>' +
            lines(isEn() ? (cfg.intro || {}).paras_en : (cfg.intro || {}).paras_zh, '') +
            '<p class="cave-line small">' + esc(pick((cfg.intro || {}).hint_zh, (cfg.intro || {}).hint_en)) + '</p>' +
            '<div class="cave-actions"><button class="btn primary big" type="button" data-bridge-go="teach">' +
            esc(pick((cfg.intro || {}).action_zh, (cfg.intro || {}).action_en)) + '</button></div>');
      } else if (scene === 'teach') {
        setArt(stageArt());
        say(teachHtml(false));
      } else if (scene === 'build') {
        setArt(stageArt());
        /* 鋪木板不重覆次序：次序要記在腦裡。想再看，按下面的「再看一次教學牌」。 */
        say(kicker(fill(pick((cfg.planks || {}).kicker_zh, (cfg.planks || {}).kicker_en), { n: st.n })) +
            '<h2 class="cave-subtitle">' + esc(pick(st.teach.title_zh, st.teach.title_en)) + '</h2>' +
            '<p class="cave-line small">' + esc(pick((cfg.planks || {}).tip_zh, (cfg.planks || {}).tip_en)) + '</p>' +
            bridgeHtml() +
            '<div class="cave-actions"><button class="btn ghost" type="button" data-bridge-go="teach">' +
            esc(pick(L.card_reopen_zh, L.card_reopen_en) || '') + '</button></div>');
      } else if (scene === 'wrong') {
        var wrong = cfg.wrong || {};
        setArt(wrong.image || 'slip');
        say(kicker(pick(wrong.kicker_zh, wrong.kicker_en), 'bad') +
            '<h2 class="cave-subtitle">' + esc(pick(wrong.title_zh, wrong.title_en)) + '</h2>' +
            lines(isEn() ? toLines(wrong.lead_en || wrong.lead_zh) : toLines(wrong.lead_zh), 'small') +
            '<h3 class="cave-subtitle bridge-recap-title">' + esc(pick(wrong.recap_title_zh, wrong.recap_title_en)) + '</h3>' +
            '<h4 class="bridge-recap-head">' + esc(pick((stage().teach || {}).title_zh, (stage().teach || {}).title_en)) + '</h4>' +
            wordingBox(stage().teach, { details: true, label: false }) +
            '<p class="cave-line small">' + esc(fill(pick(wrong.note_zh, wrong.note_en), { chain: chainOf(stage().teach) })) + '</p>' +
            '<div class="cave-actions"><button class="btn primary big" type="button" data-bridge-go="retry">' +
            esc(pick(wrong.retry_zh, wrong.retry_en)) + '</button></div>');
      } else if (scene === 'built') {
        var built = cfg.built || {};
        var last = state.stage + 1 >= total;
        // the last span laid: show the finished crossing itself
        setArt(last ? ((cfg.crossed || {}).image || 'crossed') : stageArt());
        say(kicker(fill(pick(built.kicker_zh, built.kicker_en), { n: st.n }), 'good') +
            '<h2 class="cave-subtitle">' + esc(pick(built.title_zh, built.title_en)) + '</h2>' +
            '<p class="cave-line">' + esc(fill(pick(built.chain_zh, built.chain_en), { chain: chainOf(st.teach) })) + '</p>' +
            '<p class="cave-line small">' + esc(pick(built.note_zh, built.note_en)) + '</p>' +
            '<div class="cave-actions"><button class="btn primary big" type="button" data-bridge-go="' +
            (last ? 'finish' : 'next') + '">' +
            esc(last ? pick((cfg.crossed || {}).action_zh, (cfg.crossed || {}).action_en)
                     : pick(built.next_zh, built.next_en)) + '</button></div>');
      } else if (scene === 'crossed') {
        var crossed = cfg.crossed || {};
        setArt(crossed.image || 'crossed');
        say(kicker(pick(crossed.kicker_zh, crossed.kicker_en), 'good') +
            '<h1 class="cave-title">' + esc(pick(crossed.title_zh, crossed.title_en)) + '</h1>' +
            lines(isEn() ? crossed.paras_en : crossed.paras_zh, ''));
      } else if (scene === 'result') {
        setArt((cfg.crossed || {}).image || 'crossed');
      }
      paintProgress();
    }

    function paintProgress() {
      if (!progress) return;
      var planks = (cfg.planks || {});
      var text = fill(pick(planks.progress_zh, planks.progress_en) || '', {
        n: state.stage + 1, total: total, done: laidCount(), planks: plankTotal()
      });
      progress.textContent = text || pick(L.hud_zh, L.hud_en) || '';
    }

    /* ── playing ───────────────────────────────────────────────────────────── */

    function startStage(index) {
      state.stage = Math.max(0, Math.min(total - 1, index));
      state.laid = [];
      state.pool = shuffled(stage().planks || []);
      state.wrongKey = '';
      show('teach');
    }

    function place(key) {
      if (state.busy) return;
      var wanted = (stage().planks || [])[state.laid.length];
      var plank = (stage().planks || []).filter(function (row) { return row.key === key; })[0];
      if (!plank || !wanted) return;
      /* 同樣文字的木板可以互換：次序對了就扣得住，用哪一塊都可以 */
      if (plankLabel(plank) !== plankLabel(wanted)) {
        /* the board tips off the wet rock into the water */
        state.wrongKey = key;
        state.laid = [];
        state.pool = shuffled(stage().planks || []);
        thud();
        show('wrong');
        return;
      }
      state.wrongKey = '';
      /* take exactly the board that was lifted — never every board that happens
         to carry the same key */
      for (var i = 0; i < state.pool.length; i += 1) {
        if (state.pool[i].key === key) { state.pool.splice(i, 1); break; }
      }
      state.laid.push(plank);
      tap();
      if (state.laid.length === plankTotal()) {
        chime();
        show('built');
        return;
      }
      show('build');
    }

    function retry() {
      state.laid = [];
      state.pool = shuffled(stage().planks || []);
      state.wrongKey = '';
      show('build');
    }

    function finish() {
      if (state.busy) return;
      state.busy = true;
      var submitting = (cfg.crossed || {}).submitting_zh;
      show('crossed');
      note(pick(submitting, (cfg.crossed || {}).submitting_en));

      var url = cfg.submit_url;
      if (!url) {                      // self-contained offline preview: it already
        window.setTimeout(result, 260); // knows every plank was right — no server
        return;
      }
      var body = new FormData();
      cfg.stages.forEach(function (stage_) {
        var wanted = (stage_.planks || []).map(function (p) { return p.key; });
        wanted.forEach(function (key) { body.append('stage' + stage_.n, key); });
      });
      fetch(url, { method: 'POST', body: body, credentials: 'same-origin' })
        .then(function (response) {
          return response.json().catch(function () { return { ok: false }; })
            .then(function (data) { return { status: response.status, data: data }; });
        })
        .then(function (answer) {
          state.busy = false;
          if (answer.data && answer.data.ok) { result(); return; }
          saveProblem((answer.data && (answer.data.message_zh || answer.data.message_en)) || '');
        })
        .catch(function () { state.busy = false; saveProblem(''); });
    }

    function note(text) {
      var live = card && card.querySelector('.bridge-submitting');
      if (live) live.textContent = text;
    }

    function saveProblem(message) {
      var crossed = cfg.crossed || {};
      mark('save-error');
      say(kicker(pick(crossed.kicker_zh, crossed.kicker_en), 'bad') +
          '<h2 class="cave-subtitle">' + esc(pick(crossed.save_error_zh, crossed.save_error_en)) + '</h2>' +
          (message ? '<p class="cave-line small">' + esc(message) + '</p>' : '') +
          '<p class="cave-line small">' + esc(pick(crossed.save_retry_zh, crossed.save_retry_en)) + '</p>' +
          '<div class="cave-actions"><button class="btn primary big" type="button" data-bridge-go="finish">' +
          esc(pick(crossed.retry_zh, crossed.retry_en)) + '</button></div>');
    }

    function result() {
      var crossed = cfg.crossed || {};
      document.dispatchEvent(new CustomEvent('bridge:result', { detail: { cleared: true } }));
      var badgeLink = root.querySelector('[data-bridge-link="badge"]');
      /* the task's own revision links, offered while the words are still fresh */
      var refs = Array.prototype.map.call(root.querySelectorAll('[data-bridge-link="ref"]'),
                                          function (node) { return node.outerHTML; }).join('');
      // the confirmation gets its own headline: the walking-across scene before it
      // has just used the crossing's own words
      say(kicker(pick(crossed.pass_zh, crossed.pass_en), 'good') +
          '<h1 class="cave-title">' +
          esc(pick(crossed.pass_title_zh || crossed.title_zh,
                   crossed.pass_title_en || crossed.title_en)) + '</h1>' +
          '<p class="cave-line small">' + esc(pick(crossed.pass_note_zh, crossed.pass_note_en)) + '</p>' +
          (refs ? '<div class="row wrap" style="gap:.4rem; margin:.15rem 0 .35rem">' + refs + '</div>' : '') +
          '<div class="cave-actions cave-actions-split">' +
            '<button class="btn ghost" type="button" data-bridge-go="restart">' +
              esc(pick(crossed.again_zh, crossed.again_en)) + '</button>' +
            (badgeLink ? badgeLink.outerHTML : '') +
          '</div>');
      state.scene = 'result';
      mark('result');
      paintProgress();
    }

    function reset() {
      state.stage = 0;
      state.laid = [];
      state.pool = [];
      state.wrongKey = '';
      state.busy = false;
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
          '<button class="btn primary" type="button" data-bridge-stay>' + esc(pick(L.leave_stay_zh, L.leave_stay_en)) + '</button>' +
          '<button class="btn ghost" type="button" data-bridge-leave>' + esc(pick(L.leave_go_zh, L.leave_go_en)) + '</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(exitOverlay);
    var pendingExit = null;
    var lastFocus = null;
    var approvedExit = false;
    function bridgeIsVisible() {
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
        reset();
        startStage(0);
        if (callback) callback();
      } else if (lastFocus && lastFocus.isConnected && lastFocus !== document.body) {
        lastFocus.focus();
      }
      lastFocus = null;
    }
    exitOverlay.addEventListener('click', function (event) {
      if (event.target.closest('[data-bridge-stay]') || event.target === exitOverlay) finishExit(false);
      else if (event.target.closest('[data-bridge-leave]')) finishExit(true);
    });
    exitOverlay.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); finishExit(false); }
    });
    function requestExit(callback) {
      // a finished crossing has nothing to lose: no warning on the way out
      if (state.scene === 'result' || !bridgeIsVisible()) { if (callback) callback(); return; }
      if (!exitOverlay.hidden) return;
      pendingExit = callback;
      lastFocus = document.activeElement;
      exitOverlay.hidden = false;
      document.body.classList.add('cave-exit-open');
      exitOverlay.querySelector('[data-bridge-stay]').focus();
    }
    root.__requestBridgeExit = requestExit;
    root.__restartBridge = function () {
      reset();
      state.pool = shuffled((cfg.stages[0].planks) || []);
      show('intro');
    };

    if (!window.OFFLINE_DEMO) {
      document.addEventListener('click', function (event) {
        if (state.scene === 'result' || !bridgeIsVisible() || event.defaultPrevented || event.button !== 0 ||
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

    root.addEventListener('click', function (event) {
      var plank = event.target.closest('[data-bridge-plank]');
      if (plank) { event.preventDefault(); place(plank.getAttribute('data-bridge-plank')); return; }
      var go = event.target.closest('[data-bridge-go]');
      if (!go) return;
      event.preventDefault();
      var where = go.getAttribute('data-bridge-go');
      if (where === 'build') { tap(); show('build'); return; }
      if (where === 'teach') { tap(); show('teach'); return; }
      if (where === 'retry') { tap(); retry(); return; }
      if (where === 'next') { tap(); startStage(state.stage + 1); return; }
      if (where === 'finish') { finish(); return; }
      if (where === 'restart') { reset(); startStage(0); return; }
    });

    state.pool = shuffled((cfg.stages[0].planks) || []);
    show('intro');
  }

  function mountAll(scope) {
    var nodes = (scope || document).querySelectorAll('[data-bridge]');
    Array.prototype.forEach.call(nodes, mountOne);
  }

  window.BridgeGame = {
    mount: mountOne,
    mountAll: mountAll,
    requestExit: function (callback) {
      var root = document.querySelector('[data-bridge]');
      if (root && root.__requestBridgeExit) root.__requestBridgeExit(callback);
      else if (callback) callback();
    },
    restart: function () {
      var root = document.querySelector('[data-bridge]');
      if (root && root.__restartBridge) root.__restartBridge();
    },
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { mountAll(); });
  } else {
    mountAll();
  }
})();
