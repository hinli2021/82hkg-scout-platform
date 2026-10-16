/* ── 童軍歷史山洞 — 第 4 項的第一個遊戲 ─────────────────────────────────────
   Four stretches, four wall paintings, and fifty questions. Each wall carries a
   timeline of what the questions of that group ask about; after reading it the
   scout answers the group inside the chamber, question by question. A wrong
   answer drops them into a dead end — the wall's facts are told again and they
   choose once more — and a right one moves on. Three wrong turns inside one
   stretch, though, and the stretch is lost: a story sends the scout back to
   that stretch's wall to read it again and answer the chamber afresh (the
   stories and the number of chances live in cave.json → setbacks). At the end
   the 50 answers are handed in and the score comes back, with a review of what
   was missed.

   The whole game is a browser-side state machine: the route hands over the
   walls, the questions (options in a shuffled order) and the words, so the same
   game plays inside the offline demo file. Scoring is re-checked on the server
   when the answers are submitted; the local verdicts are only what the scout
   sees along the way.
*/
(function () {
  'use strict';

  function isEn() { return document.documentElement.lang === 'en'; }
  function pick(zh, en) { return isEn() && en ? en : (zh || ''); }
  /* a label that must never come out empty, whatever the payload carries */
  function label(zh, en, fallbackZh, fallbackEn) {
    return (isEn() ? (en || fallbackEn) : (zh || fallbackZh)) || '';
  }
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
  function burstOn(node, emojis) {
    if (node && window.FX && FX.burst) { try { FX.burst(node, 16, emojis); } catch (e) {} }
  }
  function tap() { if (window.FX && FX.sfx) { try { FX.sfx('tap'); } catch (e) {} } }
  function chime() { if (window.FX && FX.sfx) { try { FX.sfx('unlock'); } catch (e) {} } }
  function shuffled(list, keepFirst) {
    var out = list.slice();
    for (var i = out.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = out[i]; out[i] = out[j]; out[j] = t;
    }
    return out;
  }

  function mountOne(root) {
    if (!root || root.getAttribute('data-cave-bound') === '1') return;
    var cfg = null;
    try { cfg = JSON.parse(root.getAttribute('data-cave-config') || '{}'); } catch (e) { cfg = null; }
    if (!cfg || !cfg.groups || !cfg.groups.length) return;
    root.setAttribute('data-cave-bound', '1');

    var L = cfg.labels || {};
    var art = root.querySelector('.cave-art');
    var backdrop = root.querySelector('.cave-art-backdrop');
    var card = root.querySelector('[data-cave-card]');
    /* the cue, and the panel that scrolls (the card's parent): looked up after
       the card, or the cue would have no panel to watch */
    var moreCue = root.querySelector('[data-cave-more]');
    var panel = card ? card.parentElement : null;
    var progress = root.querySelector('[data-cave-progress]');
    var totalQuestions = cfg.groups.reduce(function (n, g) { return n + g.questions.length; }, 0);

    /* every painting waits in the hidden block; the one on screen is remembered
       here before the first swap, or coming back to the entrance loses it */
    var urls = {};
    urls[cfg.intro.image] = art ? art.getAttribute('src') : '';
    Array.prototype.forEach.call(root.querySelectorAll('.cave-sources [data-cave-art]'),
      function (node) { urls[node.getAttribute('data-cave-art')] = node.getAttribute('src'); });
    function artUrl(name) {
      if (urls[name]) return urls[name];
      var node = root.querySelector('.cave-sources [data-cave-art="' + name + '"]');
      return node ? node.getAttribute('src') : '';
    }

    /* 一段路錯三次 → 退回這一幅壁畫（cave.json → setbacks）*/
    var setback = cfg.setbacks || {};
    var stories = (setback.stories || []).filter(function (story) { return story && story.image; });
    var wrongLimit = Math.max(1, parseInt(setback.wrong_limit, 10) || 3);

    var state = null;
    function reset() {
      /* a run: which chamber stands behind each question, in what order the
         dead ends are met, and what the scout has answered so far */
      var spread = [];
      (cfg.chambers || ['fork']).forEach(function (name) { spread.push(name); });
      if (!spread.length) spread = ['fork'];
      state = {
        scene: 'intro', group: 0, qi: 0, first: {}, passed: 0,
        chambers: shuffled(spread), deadends: shuffled(cfg.deadends || ['deadend']),
        deadsSeen: 0, pending: null, result: null, finishing: false,
        // this stretch only: wrong turns taken, and questions of it answered
        fails: 0, stagePassed: 0, back: null, backs: 0,
      };
      window.__caveState = state;                     // for the browser checks
    }
    reset();

    function current() { return cfg.groups[state.group]; }
    function question() {
      var group = current();
      return group.questions[state.qi] || null;
    }
    function chamberFor(asked) {
      return state.chambers[asked % state.chambers.length];
    }
    function deadendFor() {
      var pool = state.deadends && state.deadends.length ? state.deadends : ['deadend'];
      var name = pool[state.deadsSeen % pool.length];
      state.deadsSeen += 1;
      return name;
    }


    function welcomeHtml() {
      return '<span class="cave-kicker">' + esc(pick(cfg.intro.kicker_zh, cfg.intro.kicker_en)) + '</span>' +
        '<h1 class="cave-title">' + esc(pick(cfg.intro.title_zh, cfg.intro.title_en)) + '</h1>' +
        (isEn() ? cfg.intro.paras_en : cfg.intro.paras_zh).map(function (line) {
          return '<p class="cave-line">' + esc(line) + '</p>';
        }).join('') +
        '<div class="cave-actions">' +
          '<button class="btn primary big" type="button" data-cave-go="wall" data-cheer="🔥,✨">' +
            esc(pick(cfg.intro.action_zh, cfg.intro.action_en)) + '</button>' +
        '</div>';
    }

    function timelineHtml(wall) {
      var html = '<h3 class="cave-subtitle">🕰 ' + esc(pick(L.timeline_title_zh, L.timeline_title_en)) + '</h3>' +
        '<ol class="cave-timeline">';
      (wall.timeline || []).forEach(function (row) {
        html += '<li class="cave-milestone"><span class="cave-when">' + esc(row.when) + '</span>' +
                '<p class="cave-what">' + esc(row.text) + '</p></li>';
      });
      html += '</ol>';
      var facts = wall.facts || [];
      if (facts && facts.length) {
        html += '<div class="cave-facts">' + facts.map(function (fact) {
          return '<span class="cave-fact"><b>' + esc(fact.label) + '</b> ' + esc(fact.value) + '</span>';
        }).join('') + '</div>';
      }
      if (wall.note) html += '<p class="cave-note-line">🖊 ' + esc(wall.note) + '</p>';
      return html;
    }

    function locWall() {
      /* the route ships the wall in both languages; the scene picks one and
         lines the timeline up as {when, text} rows */
      var wall = current().wall;
      return {
        image: wall.image,
        title_zh: wall.title_zh, title_en: wall.title_en,
        lead: isEn() ? wall.lead_en : wall.lead_zh,
        timeline: (wall.timeline || []).map(function (row) {
          return { when: pick(row.when_zh, row.when_en), text: pick(row.text_zh, row.text_en) };
        }),
        facts: (wall.facts || []).map(function (fact) {
          return { label: pick(fact.label_zh, fact.label_en), value: pick(fact.value_zh, fact.value_en) };
        }),
        note: pick(wall.note_zh, wall.note_en),
      };
    }

    function wallHtml(openButton) {
      var group = current(), wall = locWall();
      return '<span class="cave-kicker">' +
          esc(fill(pick(L.group_kicker_zh, L.group_kicker_en), { n: group.n })) + ' · ' +
          esc(pick(group.name_zh, group.name_en)) + '</span>' +
        '<h2 class="cave-title">' + esc(group.icon || '') + ' ' +
          esc(pick(wall.title_zh, wall.title_en)) + '</h2>' +
        wall.lead.map(function (line) { return '<p class="cave-line">' + esc(line) + '</p>'; }).join('') +
        timelineHtml(wall) +
        '<div class="cave-actions">' +
          '<button class="btn primary big" type="button" data-cave-go="question" data-cheer="🔥,🧭">' +
            esc(pick(L.wall_button_zh, L.wall_button_en)) + '</button>' +
        '</div>';
    }

    function questionHtml() {
      var group = current(), q = question();
      var head = '<span class="cave-kicker">' +
          esc(fill(pick(L.question_kicker_zh, L.question_kicker_en),
                   { n: group.n, i: state.qi + 1, total: group.questions.length })) + '</span>' +
        '<h2 class="cave-question">' + esc(pick(q.q_zh, q.q_en)) + '</h2>';
      var options = '<div class="cave-options">' + q.options.map(function (option) {
        var text = pick(option.label_zh || option.label, option.label_en || option.label);
        return '<button class="cave-option" type="button" data-cave-option="' + esc(option.key) + '">' +
          '<span class="cave-option-mark">' + esc(text.slice(0, 1)) + '</span>' +
          '<span class="cave-option-text">' + esc(text) + '</span></button>';
      }).join('') + '</div>';
      var foot = '<div class="cave-actions cave-actions-split">' +
          '<button class="btn ghost small" type="button" data-cave-go="wall">' +
            esc('📜 ' + pick(L.wall_open_zh, L.wall_open_en)) + '</button>' +
          '<button class="btn ghost small" type="button" data-cave-go="wall">' +
            esc('↩ ' + label(L.back_wall_zh, L.back_wall_en, '回去看壁畫', 'Back to the wall')) + '</button>' +
        '</div>';
      return head + options + foot;
    }

    function verdictHtml(ok, q) {
      var group = current();
      var explain = pick(q.explain_zh, q.explain_en);
      var head = ok
        ? '<span class="cave-kicker cave-kicker-good">' + esc(pick(L.right_kicker_zh, L.right_kicker_en)) + '</span>' +
          '<h2 class="cave-title">' + esc(pick(L.right_title_zh, L.right_title_en)) + '</h2>'
        : '<span class="cave-kicker cave-kicker-bad">' + esc(pick(L.wrong_kicker_zh, L.wrong_kicker_en)) + '</span>' +
          '<h2 class="cave-title">' + esc(pick(L.wrong_title_zh, L.wrong_title_en)) + '</h2>' +
          '<p class="cave-line">' + esc(pick(group.deadend_zh, group.deadend_en)) + '</p>';
      // A wrong turn offers only the historical recap, never an answer strip.
      // The player must read the clue and try the same question again.
      var recapHeading = ok ? pick(L.why_zh, L.why_en) : pick(L.recap_zh, L.recap_en);
      var body = '<div class="cave-explain"><strong>' + esc(recapHeading) + '</strong>' +
        '<p>' + esc(explain || '') + '</p></div>';
      var last = state.qi + 1 >= group.questions.length;
      var foot = ok
        ? '<div class="cave-actions"><button class="btn primary big" type="button" data-cave-go="next" data-cheer="⭐,🔥">' +
          esc(last ? label(L.to_group_end_zh, L.to_group_end_en, '✅ 這一組答完了', 'Group complete')
                   : label(L.next_question_zh, L.next_question_en, '下一題 →', 'Next question →')) +
          '</button></div>'
        : '<div class="cave-actions"><button class="btn primary" type="button" data-cave-go="question" data-cheer="🔥,🪨">' +
          esc(pick(L.try_again_zh, L.try_again_en)) + '</button></div>';
      if (!ok) body += torchHtml();     // 火把的光還剩幾次
      return head + body + foot;
    }

    /* 回頭的故事：一段錯三次，用一個理由把人送回這一幅壁畫前 */
    function setbackStory() {
      if (!stories.length) return null;
      return stories[state.backs % stories.length];
    }

    function setbackHtml() {
      var group = current();
      var story = state.back || {};
      var paras = (isEn() ? story.paras_en : story.paras_zh) || [];
      var note = pick(setback.note_zh, setback.note_en);
      return '<span class="cave-kicker cave-kicker-bad">' +
          esc(fill(label(setback.kicker_zh, setback.kicker_en,
                         '第 {n} 段 · 要回頭了', 'Stretch {n} · you have to turn back'),
                   { n: group.n })) + '</span>' +
        '<h2 class="cave-title">' + esc(pick(story.title_zh, story.title_en)) + '</h2>' +
        paras.map(function (line) { return '<p class="cave-line">' + esc(line) + '</p>'; }).join('') +
        '<div class="cave-exit-box">' + esc(pick(group.name_zh, group.name_en)) + ' · ' +
          esc(fill(pick(L.progress_zh, L.progress_en),
                   { n: group.n, groups: cfg.groups.length, done: state.passed, total: totalQuestions })) +
        '</div>' +
        (note ? '<p class="cave-line small">' + esc(note) + '</p>' : '') +
        '<div class="cave-actions"><button class="btn primary big" type="button" ' +
          'data-cave-go="stage-start" data-cheer="🔥,🧭">' +
          esc(label(setback.back_zh, setback.back_en,
                    '回到壁畫前，重走這一段', 'Back to the wall — walk this stretch again')) +
        '</button></div>';
    }

    /* 火把：還剩幾次 —— 錯的當下就貼在死路卡上，不用猜 */
    function torchHtml() {
      var left = Math.max(0, wrongLimit - state.fails);
      var text = left <= 1
        ? label(setback.torch_last_zh, setback.torch_last_en,
                '🔥 最後一次 —— 再錯就要退回這一段的入口。',
                '🔥 One chance left — the next wrong turn sends you back.')
        : fill(pick(setback.torch_zh, setback.torch_en), { left: left });
      return '<p class="cave-torch' + (left <= 1 ? ' is-low' : '') + '">' + esc(text) + '</p>';
    }

    function groupDoneHtml() {
      var group = current();
      var last = state.group + 1 >= cfg.groups.length;
      return '<span class="cave-kicker cave-kicker-good">' +
          esc(pick(L.group_done_kicker_zh, L.group_done_kicker_en)) + '</span>' +
        '<h2 class="cave-title">' + esc(pick(L.group_done_title_zh, L.group_done_title_en)) + '</h2>' +
        '<p class="cave-line">' + esc(pick(group.name_zh, group.name_en)) + ' · ' +
          group.questions.length + ' ' + esc(isEn() ? 'questions answered' : '題已完成') + '</p>' +
        '<div class="cave-actions"><button class="btn primary big" type="button" ' +
          (last ? 'data-cave-go="finish"' : 'data-cave-go="wall" data-cave-next-group="1"') +
          ' data-cheer="⭐,✨">' +
          esc(last ? pick(L.leave_zh, L.leave_en) : pick(L.next_wall_zh, L.next_wall_en)) + '</button></div>';
    }

    function exitNarrativeHtml() {
      return '<span class="cave-kicker">🏅 ' + esc(pick(L.result_kicker_zh, L.result_kicker_en)) + '</span>' +
        '<h1 class="cave-title">' + esc(pick(cfg.exit.title_zh, cfg.exit.title_en)) + '</h1>' +
        (isEn() ? cfg.exit.paras_en : cfg.exit.paras_zh).map(function (line) {
          return '<p class="cave-line">' + esc(line) + '</p>';
        }).join('');
    }

    function resultHtml() {
      var r = state.result || {};
      var score = r.score == null ? localScore().score : r.score;
      var wrong = localReview();
      var html = exitNarrativeHtml() +
        '<h2 class="cave-score">' + esc(fill(pick(L.result_score_zh, L.result_score_en), { score: score })) + '</h2>' +
        '<p class="cave-verdict is-pass">' + esc(pick(L.pass_zh, L.pass_en)) + '</p>' +
        '<p class="cave-line">' + esc(pick(L.pass_note_zh, L.pass_note_en)) + '</p>';
      if (r.offline) html += '<p class="cave-line small">' + esc(isEn()
        ? 'Offline preview: game 1 is marked complete for this visit. Your score is for review; play online to save it to your account.'
        : '離線示範：遊戲 1 已在本次瀏覽期間標示完成，成績只供回顧；連線遊玩才會正式記錄在帳戶。') + '</p>';
      var detail = (r.review && r.review.length) ? r.review : wrong;
      html += '<h3 class="cave-subtitle">' + esc(pick(L.review_title_zh, L.review_title_en)) + '</h3>';
      if (!detail.length) {
        html += '<p class="cave-line">🎉 ' + esc(pick(L.review_none_zh, L.review_none_en)) + '</p>';
      } else {
        if (!r.review) html += '<p class="cave-line small">' + esc(pick(L.review_lead_zh, L.review_lead_en)) + '</p>';
        html += '<ol class="cave-review">' + detail.map(function (row) {
          return '<li class="cave-review-row">' +
            '<div class="cave-review-q">' + esc(fill(pick(L.mark_zh, L.mark_en), { n: row.n })) + ' · ' +
              esc(pick(row.q_zh, row.q_en)) + '</div>' +
            '<div class="cave-review-picks"><span class="cave-pick-bad">✗ ' +
              esc(pick(L.your_answer_zh, L.your_answer_en)) + '：' + esc(row.given_label || '—') + '</span>' +
              '<span class="cave-pick-good">✓ ' + esc(row.answer_label || '') + '</span></div>' +
            (row.explain ? '<p class="cave-review-why">' + esc(row.explain) + '</p>' : '') +
            '</li>';
        }).join('') + '</ol>';
      }
      var onward = onwardLink();
      html += '<div class="cave-actions' + (onward ? ' cave-actions-split' : '') + '">' +
          (onward || '<button class="btn primary" type="button" data-cave-go="restart" data-cheer="🔥,✨">' +
            esc('↺ ' + pick(L.again_zh, L.again_en)) + '</button>') +
          (onward ? '<button class="btn ghost" type="button" data-cave-go="restart">' +
            esc(pick('↺ ' + (L.again_zh || ''), '↺ ' + (L.again_en || ''))) + '</button>' : '') +
          badgeButton() +
        '</div>';
      return html;
    }

    function badgeLink(kind) {
      var kit = root.querySelector('[data-cave-link="badge"]');
      if (!kit) return '';
      var a = kit.cloneNode(true);
      a.removeAttribute('data-cave-link');
      a.removeAttribute('hidden');
      a.setAttribute('class', 'btn ' + kind);
      return a.outerHTML;
    }
    function badgeButton() {
      return badgeLink('ghost') || '';
    }
    /* 走出洞口: the way on, straight into the next game on the map */
    function onwardLink() {
      var kit = root.querySelector('[data-cave-link="next"]');
      if (!kit) return '';
      var a = kit.cloneNode(true);
      a.removeAttribute('data-cave-link');
      a.setAttribute('class', 'btn primary big');
      return a.outerHTML;
    }
    /* a cleared run has nothing left to lose: the exit guard only protects a
       half-finished cave */
    function finished() { return state.scene === 'result'; }

    function localScore() {
      var right = localReview(true);
      return { score: Math.round(right / totalQuestions * 100), right: right };
    }

    /* the missed questions, in the order they were asked: the first attempt is
       the one that counts, even though every question is finally passed */
    function localReview(rightOnly) {
      var rows = [];
      cfg.groups.forEach(function (group) {
        group.questions.forEach(function (q) {
          var attempt = state.first[q.id];
          if (!attempt) return;
          if (rightOnly) { if (attempt.ok) rows.push(attempt); return; }
          if (attempt.ok) return;
          rows.push({
            n: q.bank + 1, qid: q.id, q_zh: q.q_zh, q_en: q.q_en,
            given_label: attempt.label, answer_label: attempt.answer_label,
            explain: attempt.explain,
          });
        });
      });
      return rightOnly ? rows.length : rows;
    }

    function paintArt(name) {
      var url = artUrl(name);
      if (!url || !art || art.getAttribute('src') === url) return;
      if (backdrop) backdrop.setAttribute('src', url);   // the matte behind the picture
      art.classList.add('is-fading');
      window.setTimeout(function () {
        art.setAttribute('src', url);
        art.classList.remove('is-fading');
      }, 170);
    }

    function caption(scene, q) {
      if (scene === 'intro') return pick(cfg.intro.title_zh, cfg.intro.title_en);
      if (scene === 'submitting' || scene === 'save-error' || scene === 'result')
        return pick(cfg.exit.title_zh, cfg.exit.title_en);
      if (scene === 'question' || scene === 'verdict') return q ? pick(q.q_zh, q.q_en) : '';
      if (scene === 'setback')
        return (state.back && pick(state.back.title_zh, state.back.title_en)) || '';
      return pick(current().wall.title_zh, current().wall.title_en);
    }

    /* 向下捲動: is any of this message still below the panel's edge? */
    function syncMore() {
      if (!moreCue || !panel) return;
      moreCue.hidden = (panel.scrollHeight - panel.scrollTop - panel.clientHeight) <= 8;
    }
    if (panel) {
      panel.addEventListener('scroll', syncMore, { passive: true });
      window.addEventListener('resize', syncMore);
    }

    function updateProgress() {
      if (!progress) return;
      var label = fill(pick(L.progress_zh, L.progress_en),
        { n: state.group + 1, groups: cfg.groups.length, done: state.passed, total: totalQuestions });
      progress.textContent = label;
    }

    function show(scene) {
      var group = current();
      var q = question();
      state.scene = scene;
      var name = cfg.intro.image, html = '';
      if (scene === 'intro') { html = welcomeHtml(); }
      else if (scene === 'wall') { name = group.wall.image; html = wallHtml(); }
      else if (scene === 'question' || scene === 'verdict') {
        // a dead end is its own painting; a question stands in a chamber
        name = (scene === 'verdict' && state.pending && !state.pending.ok)
          ? deadendFor() : chamberFor(state.passed);
        html = scene === 'question'
          ? questionHtml()
          : verdictHtml(state.pending ? state.pending.ok : false, q);
      } else if (scene === 'setback') {
        name = (state.back && state.back.image) || cfg.intro.image;
        html = setbackHtml();
      } else if (scene === 'groupdone') { name = chamberFor(state.passed); html = groupDoneHtml(); }
      else if (scene === 'submitting') {
        name = cfg.exit.image;
        html = '<span class="cave-kicker">' + esc(pick(L.result_kicker_zh, L.result_kicker_en)) + '</span>' +
               '<h2 class="cave-title">' + esc(pick(L.submitting_zh, L.submitting_en)) + '</h2>' +
               '<div class="cave-spinner" aria-hidden="true">🔥</div>';
      } else if (scene === 'save-error') {
        name = cfg.exit.image;
        html = '<h2 class="cave-title">' +
          esc(label(L.save_error_zh, L.save_error_en, '未能記錄通關', 'Could not record your completion')) +
          '</h2><p class="cave-line">' +
          esc(label(L.save_retry_zh, L.save_retry_en,
            '你的作答仍在這個畫面，請再試一次。未成功儲存前不要離開。',
            'Your answers are still here. Please retry before leaving; the game has not been saved.')) +
          '</p><div class="cave-actions"><button class="btn primary big" type="button" data-cave-go="finish">' +
          esc(label(L.retry_zh, L.retry_en, '再次記錄通關', 'Try saving again')) + '</button></div>';
      } else if (scene === 'result') { name = cfg.exit.image; html = resultHtml(); }
      /* the routers and the checks read this while a story is on screen */
      if (scene === 'setback') root.setAttribute('data-cave-setback', '1');
      else root.removeAttribute('data-cave-setback');

      paintArt(name);
      /* the routers (live and offline) read this to see a run is over */
      root.setAttribute('data-cave-finished', finished() ? '1' : '0');
      if (art) art.setAttribute('alt', caption(scene === 'verdict' ? 'verdict' : scene, q) || '');
      card.innerHTML = html;
      // A wall or a review scrolls inside the panel under the picture. A new
      // scene starts at its heading, not halfway down the last one.
      card.scrollTop = 0;
      if (panel && panel.scrollTop) panel.scrollTop = 0;
      card.classList.remove('is-in');
      void card.offsetWidth;
      card.classList.add('is-in');
      root.classList.toggle('is-question', scene === 'question' || scene === 'verdict');
      updateProgress();
      syncMore();
      window.setTimeout(syncMore, 80);   // fonts and pictures settle a moment later
      if (scene === 'groupdone' || scene === 'result') {
        burstOn(card.querySelector('.cave-actions .btn'), ['⭐', '✨', '🔥']);
        chime();
      }
      if (scene === 'verdict' && state.pending && !state.pending.ok) tap();
      if (scene === 'setback') tap();
    }

    function choose(key) {
      var q = question();
      var option = q.options.filter(function (o) { return o.key === key; })[0];
      if (!option) return;
      var first = !state.first[q.id];
      if (first) {
        var key_option = q.options.filter(function (o) { return o.ok; })[0] || {};
        state.first[q.id] = {
          n: q.bank + 1, qid: q.id, ok: !!option.ok, idx: option.idx,
          label: pick(option.label_zh || option.label, option.label_en || option.label),
          answer_label: pick(key_option.label_zh || key_option.label,
                             key_option.label_en || key_option.label),
          explain: pick(q.explain_zh, q.explain_en),
        };
      }
      state.pending = { ok: !!option.ok, first: first };
      if (!option.ok) {
        state.fails += 1;
        if (state.fails >= wrongLimit && stories.length) {
          state.back = setbackStory();
          state.backs += 1;
          show('setback');
          return;
        }
      }
      show('verdict');
    }

    function advance() {
      // only a right answer moves on; a dead end sends the scout back
      if (!state.pending || !state.pending.ok) return;
      state.passed += 1;
      state.stagePassed += 1;
      state.qi += 1;
      if (state.qi >= current().questions.length) { show('groupdone'); return; }
      show('question');
    }

    /* 回到這一幅壁畫：這一組之前錯過的仍然計分，但題目要由第一題重新答 */
    function restartStage() {
      state.passed = Math.max(0, state.passed - state.stagePassed);
      state.stagePassed = 0;
      state.fails = 0;
      state.qi = 0;
      state.pending = null;
      state.marks = [];
      show('wall');
    }

    function nextGroup() {
      if (state.group + 1 < cfg.groups.length) {
        state.group += 1;
        state.qi = 0;
        state.marks = [];
        state.fails = 0;          // a new stretch: the torch is lit again
        state.stagePassed = 0;
        show('wall');
      } else {
        finish();
      }
    }

    function finish() {
      // Walking past the last chamber automatically saves the completion;
      // there is no extra hand-in step or minimum score for this game.
      if (state.finishing || state.passed !== totalQuestions ||
          Object.keys(state.first).length !== totalQuestions) return;
      state.finishing = true;
      var run = state;
      show('submitting');
      var body = new URLSearchParams();
      if (cfg.run_key) body.append('run_key', cfg.run_key);
      cfg.groups.forEach(function (group) {
        group.questions.forEach(function (q) {
          body.append('q' + q.bank, String(run.first[q.id].idx));
        });
      });
      var done = function (payload) {
        if (state !== run) return;  // the player left or began a new run
        state.result = {
          score: payload ? payload.score : localScore().score,
          passed: true,
          review: [],
          offline: !payload,
        };
        show('result');
        root.dispatchEvent(new CustomEvent('cave:result', { bubbles: true, detail: {
          score: state.result.score, passed: true, offline: state.result.offline,
        }}));
      };
      var failed = function () {
        if (state !== run) return;
        state.finishing = false;
        show('save-error'); // never claim a live win if the server did not save it
      };
      var url = cfg.submit_url;
      if (!url) { done(null); return; } // self-contained offline preview
      if (!window.fetch) { failed(); return; }
      try {
        fetch(url, {
          method: 'POST',
          headers: { 'X-Requested-With': 'fetch', 'Accept': 'application/json',
                     'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
          body: body.toString(),
        }).then(function (response) {
          if (!response.ok) throw new Error('Cave completion not saved');
          return response.json();
        }).then(function (payload) {
          if (!payload || !payload.ok || payload.passed !== true) throw new Error('Incomplete cave run');
          done(payload);
        }).catch(failed);
      } catch (error) { failed(); }
    }

    /* Leaving an unfinished cave discards this browser's in-memory answers.
       Use an in-page dialog, not window.confirm: the offline viewer runs in a
       sandboxed iframe where native confirm dialogs are blocked. */
    var exitOverlay = document.createElement('div');
    exitOverlay.className = 'cave-exit-overlay';
    exitOverlay.hidden = true;
    exitOverlay.innerHTML =
      '<div class="cave-exit-dialog" role="alertdialog" aria-modal="true" ' +
        'aria-labelledby="cave-exit-title" aria-describedby="cave-exit-message">' +
        '<span class="cave-kicker">' + esc(pick('離開遊戲', 'Leaving the game')) + '</span>' +
        '<h2 id="cave-exit-title">' + esc(pick('要離開山洞嗎？', 'Leave the cave?')) + '</h2>' +
        '<p id="cave-exit-message">' +
          esc(pick('離開後，再次進入遊戲需要從頭開始。尚未提交的作答不會保留。',
                   'If you leave, you will have to start the game again when you return. Unsubmitted answers will not be saved.')) +
        '</p>' +
        '<div class="cave-exit-actions">' +
          '<button type="button" class="btn primary" data-cave-stay>' +
            esc(pick('繼續遊戲', 'Keep playing')) + '</button>' +
          '<button type="button" class="btn ghost" data-cave-leave>' +
            esc(pick('離開遊戲', 'Leave game')) + '</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(exitOverlay);
    var pendingExit = null;
    var lastFocus = null;
    var approvedExit = false;
    function caveIsVisible() {
      var pane = root.closest('.pane');
      return !pane || !pane.hidden;
    }
    function finishExit(leave) {
      if (exitOverlay.hidden) return;
      var callback = pendingExit;
      pendingExit = null;
      // Do not leave keyboard focus on a hidden dialog button after either
      // choice. In particular, Escape must work again in the offline router.
      if (exitOverlay.contains(document.activeElement)) document.activeElement.blur();
      exitOverlay.hidden = true;
      document.body.classList.remove('cave-exit-open');
      if (leave) {
        approvedExit = true;
        reset();
        show('intro');
        if (callback) callback();
      } else if (lastFocus && lastFocus.isConnected && lastFocus !== document.body) {
        lastFocus.focus();
      }
      lastFocus = null;
    }
    exitOverlay.addEventListener('click', function (event) {
      if (event.target.closest('[data-cave-stay]') || event.target === exitOverlay) {
        finishExit(false);
      } else if (event.target.closest('[data-cave-leave]')) {
        finishExit(true);
      }
    });
    exitOverlay.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); finishExit(false); }
      if (event.key !== 'Tab') return;
      var stay = exitOverlay.querySelector('[data-cave-stay]');
      var leave = exitOverlay.querySelector('[data-cave-leave]');
      if (event.shiftKey && document.activeElement === stay) {
        event.preventDefault(); leave.focus();
      } else if (!event.shiftKey && document.activeElement === leave) {
        event.preventDefault(); stay.focus();
      }
    });
    function requestExit(callback) {
      if (finished() || !caveIsVisible()) { if (callback) callback(); return; }
      if (!exitOverlay.hidden) return;
      pendingExit = callback;
      lastFocus = document.activeElement;
      exitOverlay.hidden = false;
      document.body.classList.add('cave-exit-open');
      exitOverlay.querySelector('[data-cave-stay]').focus();
    }
    root.__requestCaveExit = requestExit;
    /* the live page starts over on every reload; the offline file reuses this
       instance, so its replay doors ask for the same fresh entrance */
    root.__restartCave = function () { reset(); show('intro'); };

    /* Normal links (the cave HUD, breadcrumbs, the site header, language and
       result links) all pass through the same warning on the live site. */
    if (!window.OFFLINE_DEMO) {
      document.addEventListener('click', function (event) {
        if (finished()) return;      // a cleared run may leave without a warning
        if (!caveIsVisible() || event.defaultPrevented || event.button !== 0 ||
            event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        var anchor = event.target.closest('a[href]');
        if (!anchor || anchor.target === '_blank' || anchor.hasAttribute('download')) return;
        var href = anchor.getAttribute('href');
        if (!href || href.charAt(0) === '#') return;
        event.preventDefault();
        event.stopImmediatePropagation();
        requestExit(function () { window.location.assign(anchor.href); });
      }, true);
      document.addEventListener('submit', function (event) {
        if (!caveIsVisible()) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        var form = event.target;
        requestExit(function () { form.submit(); });
      }, true);
      // Browsers only allow their generic warning for Back/Reload/close-tab;
      // the links above always show our bilingual, explicit restart message.
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
      var option = event.target.closest('[data-cave-option]');
      if (option) { event.preventDefault(); tap(); choose(option.getAttribute('data-cave-option')); return; }
      var go = event.target.closest('[data-cave-go]');
      if (!go) return;
      event.preventDefault();
      var where = go.getAttribute('data-cave-go');
      if (where === 'next') { tap(); advance(); return; }
      if (where === 'restart') {
        reset();
        show('intro');
        return;
      }
      if (where === 'stage-start') { tap(); restartStage(); return; }
      if (where === 'finish') { tap(); finish(); return; }
      if (where === 'wall' && go.getAttribute('data-cave-next-group')) { nextGroup(); return; }
      tap();
      show(where);
    });

    show('intro');
  }

  function mountAll(scope) {
    var nodes = (scope || document).querySelectorAll('[data-cave]');
    Array.prototype.forEach.call(nodes, mountOne);
  }

  window.CaveGame = {
    mount: mountOne,
    mountAll: mountAll,
    requestExit: function (callback) {
      var root = document.querySelector('[data-cave]');
      if (root && root.__requestCaveExit) root.__requestCaveExit(callback);
      else if (callback) callback();
    },
    restart: function () {
      var root = document.querySelector('[data-cave]');
      if (root && root.__restartCave) root.__restartCave();
    },
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { mountAll(); });
  } else {
    mountAll();
  }
})();
