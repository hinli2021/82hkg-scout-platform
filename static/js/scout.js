/**
 * Scout pages — the interactive layer on top of server-rendered forms.
 *
 * Every form here works with JavaScript switched off (it posts and the server
 * redirects). When JS *is* running we take over: submit by fetch, keep the
 * scout on the task, play the feedback sound, fire the confetti and offer the
 * next task. Progressive enhancement, never a requirement.
 */
(function () {
  'use strict';
  var FX = window.FX;

  /* ── feedback: a result the server just handed back ───────────────────── */
  function showFeedback(kind, zh, en, events) {
    var box = document.getElementById('task-feedback');
    if (!box) return;
    var lang = FX.lang();
    box.className = 'card ' + (kind === 'success' ? 'feedback-ok' : kind === 'warn' ? 'feedback-warn' : '');
    box.innerHTML = '';
    var title = document.createElement('div');
    title.className = 'feedback-title';
    title.textContent = (lang === 'en' ? en : zh) || zh || en;
    box.appendChild(title);
    if (kind === 'success') {
      var trophy = document.createElement('div');
      trophy.className = 'feedback-emoji';
      trophy.textContent = '🎉';
      box.insertBefore(trophy, title);
      FX.burst(box, 18);
      FX.sfx('correct');
    } else if (kind === 'warn') {
      FX.sfx('wrong');
    }
    (events || []).forEach(function (ev) {
      if (ev.type === 'badge') {
        var line = document.createElement('div');
        line.className = 'feedback-badge';
        line.textContent = '🎖 ' + (lang === 'en' ? 'Badge earned! ' : '考獲獎章！') +
          (ev.badge ? (lang === 'en' ? ev.badge.title_en : ev.badge.title_zh) : '');
        box.appendChild(line);
        FX.sfx('badge');
        FX.burst(box, 26, ['🎖', '✨', '⭐']);
      } else if (ev.type === 'points' && ev.points) {
        var pts = document.createElement('div');
        pts.className = 'muted small';
        pts.textContent = (lang === 'en' ? 'Points earned: ' : '獲得積分：') + ev.points;
        box.appendChild(pts);
      }
    });
    box.classList.remove('hidden');
    box.scrollIntoView({ behavior: FX.reducedMotion() ? 'auto' : 'smooth', block: 'center' });
  }

  /* ── the task player ─────────────────────────────────────────────────── */
  function initTask() {
    var form = document.querySelector('form[data-task-submit]');
    if (!form) return;

    // Quiz: light up answered questions, block a silent submission.
    form.querySelectorAll('.quiz-question').forEach(function (question) {
      question.querySelectorAll('.radio-row input').forEach(function (radio) {
        radio.addEventListener('change', function () {
          question.classList.add('answered');
          question.querySelectorAll('.radio-row').forEach(function (row) { row.classList.remove('picked'); });
          var picked = radio.closest('.radio-row');
          if (picked) picked.classList.add('picked');
          FX.sfx('tick');
          paintDots();
        });
      });
    });
    var dots = document.getElementById('quiz-dots');
    function paintDots() {
      if (!dots) return;
      var questions = form.querySelectorAll('.quiz-question');
      var answered = form.querySelectorAll('.quiz-question.answered').length;
      dots.querySelectorAll('.q-dot').forEach(function (dot, i) {
        dot.classList.toggle('on', i < answered);
      });
      var label = dots.querySelector('.quiz-dots-label');
      if (label) label.textContent = answered + ' / ' + questions.length;
    }
    paintDots();

    // Checklist: count ticks and enable submission when everything is ticked.
    var checklist = form.querySelector('[data-checklist]');
    if (checklist) {
      checklist.querySelectorAll('input[type=checkbox]').forEach(function (box) {
        box.addEventListener('change', function () {
          FX.sfx(box.checked ? 'tick' : 'tap');
          paintChecklist();
        });
      });
      paintChecklist();
    }
    function paintChecklist() {
      if (!checklist) return;
      var boxes = checklist.querySelectorAll('input[type=checkbox]');
      var done = checklist.querySelectorAll('input[type=checkbox]:checked').length;
      var meter = checklist.querySelector('[data-checklist-count]');
      if (meter) meter.textContent = done + ' / ' + boxes.length;
    }

    // Evidence: choose a photo → upload → keep the link in the hidden field.
    var file = form.querySelector('input[type=file][data-upload]');
    if (file) {
      file.addEventListener('change', function () {
        var chosen = file.files && file.files[0];
        if (!chosen) return;
        var status = document.getElementById('upload-status');
        if (status) status.textContent = FX.L('上載中…', 'Uploading…');
        var reader = new FileReader();
        reader.onload = function () {
          fetch(withSid('/upload'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'fetch' },
            body: JSON.stringify({
              filename: chosen.name, mimeType: chosen.type || 'image/jpeg', dataUrl: reader.result
            })
          }).then(function (res) { return res.json(); }).then(function (data) {
            if (data.ok) {
              var hidden = form.querySelector('input[name=evidence_url]');
              if (hidden) hidden.value = data.url;
              if (status) status.innerHTML = '';
              if (status) {
                var link = document.createElement('a');
                link.href = data.url; link.target = '_blank'; link.rel = 'noopener';
                link.textContent = FX.L('已上載 ✓ 查看相片', 'Uploaded ✓ view photo');
                status.appendChild(link);
              }
              FX.sfx('unlock');
            } else if (status) {
              status.textContent = FX.lang() === 'en' ? (data.message_en || 'Upload failed') : (data.message_zh || '上載失敗');
              FX.sfx('wrong');
            }
          }).catch(function () {
            if (status) status.textContent = FX.L('上載失敗，請再試一次', 'Upload failed — please try again');
          });
        };
        reader.readAsDataURL(chosen);
      });
    }

    // Submit by fetch so the scout stays on the page and sees the result.
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var button = form.querySelector('button[type=submit]');
      if (button) { button.disabled = true; button.classList.add('busy'); }
      FX.sfx('submit');

      if (form.dataset.quiz === '1' && form.dataset.requireAll === '1') {
        var total = form.querySelectorAll('.quiz-question').length;
        var answered = form.querySelectorAll('.quiz-question.answered').length;
        if (answered < total) {
          FX.sfx('wrong');
          showFeedback('warn', '還有題目未回答（' + answered + ' / ' + total + '）', 'Answer every question first (' + answered + ' / ' + total + ')');
          if (button) { button.disabled = false; button.classList.remove('busy'); }
          return;
        }
      }

      fetch(form.action, {
        method: 'POST',
        headers: { 'X-Requested-With': 'fetch', 'Accept': 'application/json' },
        body: new FormData(form)
      }).then(function (res) { return res.json().then(function (data) { return { status: res.status, data: data }; }); })
        .then(function (result) {
          var data = result.data || {};
          if (result.status >= 400) {
            showFeedback('warn', data.message_zh || '未能提交', data.message_en || 'Could not submit');
            return;
          }
          showFeedback(data.passed ? 'success' : (data.status === 'pending' ? 'info' : 'warn'),
            data.feedback_zh, data.feedback_en, data.events);
          if (data.passed) {
            // Progress moved — refresh the rings and let the scout pick what to do next.
            paintBadgeChip(data.progress);
            addNextAction(data);
          } else if (data.record_id) {
            // A redo: re-enable the form so they can try again right away.
            window.setTimeout(function () { window.location.reload(); }, 2200);
          }
        })
        .catch(function () {
          showFeedback('warn', '網絡問題，請再試一次', 'Network hiccup — please try again');
        })
        .then(function () {
          if (button) { button.disabled = false; button.classList.remove('busy'); }
        });
    });
  }

  function paintBadgeChip(progress) {
    if (!progress || !progress.badges) return;
    progress.badges.forEach(function (badge) {
      var meter = document.querySelector('[data-badge-meter="' + badge.id + '"]');
      if (meter) meter.textContent = badge.tasks_done + ' / ' + badge.tasks_total;
      var bar = document.querySelector('[data-badge-bar="' + badge.id + '"]');
      if (bar) bar.style.width = badge.percent + '%';
    });
    var overall = document.querySelector('[data-overall-percent]');
    if (overall && progress.overall) overall.textContent = progress.overall.percent + '%';
  }

  function addNextAction(data) {
    var panel = document.getElementById('next-action');
    if (!panel) return;
    panel.innerHTML = '';
    panel.classList.remove('hidden');
    var next = data.progress && data.progress.overall && data.progress.overall.next_task;
    var row = document.createElement('div');
    row.className = 'row wrap';
    var back = document.createElement('a');
    back.className = 'btn';
    back.href = '/badges';
    back.textContent = FX.L('回到獎章路線', 'Back to the trail');
    row.appendChild(back);
    if (next && next.task) {
      var go = document.createElement('a');
      go.className = 'btn primary';
      go.href = '/tasks/' + next.task.id;
      go.textContent = FX.L('下一個任務：', 'Next task: ') + (FX.lang() === 'en' ? next.task.title_en : next.task.title_zh);
      FX.pressable(go);
      row.appendChild(go);
    }
    panel.appendChild(row);
  }

  /* ── a result flashed by the server after a plain (no-JS) post ────────── */
  /* Inside the preview iframe cookies are refused, so the sign-in token also
     travels in the address bar — keep it on URLs the page builds itself. */
  function withSid(url) {
    var hit = location.search.match(/[?&]sid=([^&]+)/);
    if (!hit || /[?&]sid=/.test(url)) return url;
    return url + (url.indexOf('?') > -1 ? '&' : '?') + 'sid=' + hit[1];
  }

  /* ── the adventure's first tap: 開始冒險 (POST /badges/<id>/start) ─────── */
  /* Without JS the form is already fine (it 302s to ?started=1, which is where
     第 1 關 is credited and lit). This only makes the tap feel like a game: the
     button locks, a few stars pop, then the trail opens with the first star on.
     Any failure falls back to the plain post, so the scout never gets stuck. */
  function initQuestStart() {
    var form = document.querySelector('form[data-quest-start]');
    if (!form) return;
    form.addEventListener('submit', function (ev) {
      if (form.getAttribute('data-busy') === '1') { ev.preventDefault(); return; }
      var button = form.querySelector('button[type=submit]');
      var trail = form.getAttribute('data-quest-trail') || '';
      var action = form.getAttribute('action') || '';
      var xhr = new XMLHttpRequest();
      ev.preventDefault();
      form.setAttribute('data-busy', '1');
      if (button) { button.setAttribute('disabled', 'disabled'); button.classList.add('is-busy'); }
      function giveUp() {
        form.removeAttribute('data-busy');
        if (button) { button.removeAttribute('disabled'); button.classList.remove('is-busy'); }
        form.submit();
      }
      xhr.open('POST', action, true);
      xhr.setRequestHeader('X-Requested-With', 'fetch');
      xhr.setRequestHeader('Accept', 'application/json');
      xhr.onload = function () {
        if (xhr.status < 200 || xhr.status >= 400) { giveUp(); return; }
        var data = {};
        try { data = JSON.parse(xhr.responseText || '{}'); } catch (e) { data = {}; }
        if (!data.ok) { giveUp(); return; }
        var where = data.trail || trail;
        if (window.FX && button) FX.burst(button, 22, ['⭐', '🎒', '✨']);
        window.setTimeout(function () { window.location.href = withSid(where); },
                          window.FX ? 460 : 60);
      };
      xhr.onerror = giveUp;
      xhr.send(new FormData(form));
    });
  }

  /* ── a page that arrived with good news (e.g. a password just set) ───── */
  function initCelebration() {
    var node = document.querySelector('[data-celebrate]');
    if (!node) return;
    FX.sfx('unlock');
    FX.burst(node, 26, ['🎉', '✨', '🔐']);
  }

  function initServerFeedback() {
    var node = document.getElementById('server-feedback');
    if (!node) return;
    try {
      var data = JSON.parse(node.getAttribute('data-feedback') || '{}');
      if (!data.zh && !data.en) return;
      showFeedback(data.kind === 'success' ? 'success' : 'warn', data.zh, data.en, data.events);
    } catch (e) { /* nothing to do */ }
  }

  /* ── rewards page: chest cost meters ─────────────────────────────────── */
  function initRewards() {
    document.querySelectorAll('[data-chest]').forEach(function (chest) {
      chest.addEventListener('click', function () {
        if (chest.classList.contains('locked')) {
          FX.sfx('wrong');
          var note = chest.querySelector('.chest-note');
          if (note) { note.classList.add('shake'); setTimeout(function () { note.classList.remove('shake'); }, 500); }
        } else {
          FX.sfx('unlock');
          FX.burst(chest, 12);
        }
      });
    });
  }

  /* ── leaderboard: highlight me ───────────────────────────────────────── */
  function initBoard() {
    var me = document.querySelector('.lb-row.is-me');
    if (me) { FX.enter(me); if (FX.soundOn()) FX.sfx('tap'); }
  }

  /* ── 建議: 顯示全部 / 收起 ────────────────────────────────────────────── */
  function initSuggestions() {
    var toggle = document.querySelector('[data-suggest-toggle]');
    var rest = document.getElementById('suggest-rest');
    if (!toggle || !rest) return;
    toggle.addEventListener('click', function () {
      var opening = rest.hidden;
      rest.hidden = !opening;
      toggle.setAttribute('aria-expanded', opening ? 'true' : 'false');
      toggle.textContent = opening ? toggle.dataset.labelLess : toggle.dataset.labelMore;
      if (opening) {
        if (FX && FX.sfx) FX.sfx('tap');
        if (FX && FX.enter) {
          Array.prototype.forEach.call(rest.querySelectorAll('.suggest-card'), function (card, i) {
            FX.enter(card, i);
          });
        }
      } else {
        // collapsing shortens the page — keep the first four cards in view
        var first = document.querySelector('[data-suggest-shown]');
        if (first && first.scrollIntoView) first.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    });
  }

  function boot() {
    initSuggestions();
    initTask();
    initQuestStart();
    initCelebration();
    initServerFeedback();
    initRewards();
    initBoard();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
