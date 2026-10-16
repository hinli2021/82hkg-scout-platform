/**
 * Leader console — small conveniences, never a requirement.
 * (Everything in the console works as plain forms with JavaScript switched off.)
 */
(function () {
  'use strict';
  var FX = window.FX;

  /* ── approve / reject / send back without leaving the queue ───────────── */
  function initReview() {
    document.querySelectorAll('[data-review]').forEach(function (form) {
      form.addEventListener('submit', function (ev) {
        ev.preventDefault();
        var button = form.querySelector('button[type=submit]');
        if (button) button.disabled = true;
        fetch(form.action, {
          method: 'POST',
          headers: { 'X-Requested-With': 'fetch', 'Accept': 'application/json' },
          body: new FormData(form)
        }).then(function (res) { return res.json(); })
          .then(function (data) {
            var card = form.closest('.review-card');
            if (data.ok) {
              FX.sfx('correct');
              if (card) {
                card.classList.add('review-done');
                FX.burst(card, 12, ['✅', '✨']);
                window.setTimeout(function () { card.remove(); emptyQueueNote(); }, 700);
              }
            } else {
              FX.sfx('wrong');
              alert(FX.lang() === 'en' ? (data.message_en || 'Failed') : (data.message_zh || '失敗'));
              if (button) button.disabled = false;
            }
          })
          .catch(function () { if (button) button.disabled = false; });
      });
    });
  }

  function emptyQueueNote() {
    var queue = document.getElementById('review-queue');
    if (queue && !queue.querySelector('.review-card')) {
      queue.innerHTML = '<div class="card center muted">' +
        (FX.lang() === 'en' ? 'Nothing waiting — all caught up ✓' : '沒有待審批的提交 ✓') + '</div>';
    }
  }

  /* ── inline edit forms (content, accounts, rewards) ──────────────────── */
  function initInlineForms() {
    document.querySelectorAll('form[data-inline]').forEach(function (form) {
      form.addEventListener('submit', function (ev) {
        ev.preventDefault();
        var note = form.querySelector('[data-inline-note]');
        var button = form.querySelector('button[type=submit]');
        if (button) button.disabled = true;
        fetch(form.action, {
          method: 'POST',
          headers: { 'X-Requested-With': 'fetch', 'Accept': 'application/json' },
          body: new FormData(form)
        }).then(function (res) { return res.json(); })
          .then(function (data) {
            if (button) button.disabled = false;
            if (data.ok) {
              FX.sfx('tick');
              if (note) {
                note.textContent = FX.lang() === 'en' ? 'Saved ✓' : '已儲存 ✓';
                note.classList.add('saved');
                window.setTimeout(function () { note.classList.remove('saved'); }, 1600);
              }
              if (form.dataset.reload === '1') window.location.reload();
            } else if (note) {
              note.textContent = FX.lang() === 'en' ? (data.message_en || 'Failed') : (data.message_zh || '失敗');
            }
          })
          .catch(function () { if (button) button.disabled = false; });
      });
    });
  }

  /* ── tabs inside a page (content / accounts panels) ─────────────────── */
  function initTabs() {
    document.querySelectorAll('[data-tabs]').forEach(function (group) {
      var buttons = group.querySelectorAll('[data-tab]');
      buttons.forEach(function (button) {
        button.addEventListener('click', function () {
          var name = button.getAttribute('data-tab');
          buttons.forEach(function (other) { other.classList.toggle('on', other === button); });
          document.querySelectorAll('[data-tab-panel]').forEach(function (panel) {
            if (panel.getAttribute('data-group') && panel.getAttribute('data-group') !== group.dataset.tabs) return;
            panel.classList.toggle('hidden', panel.getAttribute('data-tab-panel') !== name);
          });
          FX.sfx('tap');
        });
      });
    });
  }

  /* ── confirm destructive actions, and show the temp password clearly ─── */
  function initConfirmations() {
    document.querySelectorAll('form[data-confirm]').forEach(function (form) {
      form.addEventListener('submit', function (ev) {
        var message = form.getAttribute('data-confirm');
        if (!window.confirm(message)) ev.preventDefault();
      });
    });
  }

  /* ── settings: patrol list as chips ──────────────────────────────────── */
  function initSettings() {
    document.querySelectorAll('[data-patrol-input]').forEach(function (input) {
      input.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter') {
          ev.preventDefault();
          var value = input.value.trim();
          if (!value) return;
          var list = document.querySelector(input.getAttribute('data-patrol-input'));
          if (!list) return;
          var chip = document.createElement('label');
          chip.className = 'chip';
          chip.innerHTML = '<input type="checkbox" name="patrols" value="' + value.replace(/"/g, '&quot;') + '" checked> ' + value;
          list.appendChild(chip);
          FX.pressable(chip);
          input.value = '';
          FX.sfx('tick');
        }
      });
    });
  }

  function boot() {
    initReview();
    initInlineForms();
    initTabs();
    initConfirmations();
    initSettings();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
