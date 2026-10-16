/*
 * The patrol mascots on the login page.
 *
 * Two shapes of the same door:
 *   • wide screens — one full-screen camp scene, the three animals themselves
 *     are the buttons (`.scene-spot`, positioned over the artwork);
 *   • phones and tall windows — three cards (`.mascot-card`).
 *
 * Pointing at an animal lights a glow on it, dims the rest and zooms the
 * picture gently towards it; tapping it makes it cheer ("is-chosen") and then
 * the browser moves on to that patrol's name list. All of it is decoration:
 * every door is an ordinary link, so with JavaScript off (or reduced motion
 * on) a tap simply goes to the same page.
 */
(function () {
  'use strict';

  var spots = Array.prototype.slice.call(document.querySelectorAll('[data-mascot]'));
  if (!spots.length) return;

  var scene = document.getElementById('scene-login');
  var prompt = document.getElementById('scene-prompt');
  var leaving = false;

  function fx() { return window.FX || null; }
  function L(zh, en) { var api = fx(); return api && api.L ? api.L(zh, en) : zh; }
  function reduced() { var api = fx(); return !!(api && api.reducedMotion && api.reducedMotion()); }
  function label(spot) { return spot.getAttribute('data-patrol-label') || spot.getAttribute('data-mascot') || ''; }

  /* ── pointing at an animal ───────────────────────────────────────────── */

  function preview(spot) {
    if (leaving) return;
    if (scene) {
      var x = spot.style.getPropertyValue('--x') || '50%';
      scene.style.setProperty('--x', x);
      scene.style.setProperty('--zoom-o', x + ' 58%');
      scene.setAttribute('data-active', '');
    }
    if (prompt) prompt.classList.add('is-live');   // the heading leans forward a little
    var api = fx();
    if (api && api.sfx) api.sfx('tap');
  }

  function reset() {
    if (leaving) return;
    if (scene) scene.removeAttribute('data-active');
    if (prompt) prompt.classList.remove('is-live');
    spots.forEach(function (spot) { spot.classList.remove('is-chosen', 'is-dimmed'); });
  }

  /* ── choosing one ────────────────────────────────────────────────────── */
  function choose(spot) {
    if (leaving) return;
    var href = spot.getAttribute('href');
    if (!href || href === '#') return;
    leaving = true;

    var api = fx();
    if (api) {
      if (api.sfx) api.sfx('unlock');
      if (api.burst) api.burst(spot, 18, ['✨', '⭐', '🎉']);
    }

    spots.forEach(function (other) {
      other.classList.toggle('is-chosen', other === spot);
      other.classList.toggle('is-dimmed', other !== spot);
    });
    spot.setAttribute('aria-current', 'true');
    if (scene) {
      var x = spot.style.getPropertyValue('--x') || '50%';
      scene.style.setProperty('--x', x);
      scene.style.setProperty('--zoom-o', x + ' 58%');
      scene.setAttribute('data-active', '');
      scene.setAttribute('data-chosen', '');
    }
    if (prompt) prompt.classList.add('is-live');

    // let the cheer land before the page turns
    window.setTimeout(function () { window.location.href = href; }, reduced() ? 60 : 560);
  }

  /* ── wiring ──────────────────────────────────────────────────────────── */
  spots.forEach(function (spot) {
    spot.addEventListener('mouseenter', function () { preview(spot); });
    spot.addEventListener('focus', function () { preview(spot); });
    spot.addEventListener('mouseleave', reset);
    spot.addEventListener('blur', reset);

    spot.addEventListener('click', function (event) {
      // ⌘/Ctrl/Shift-click and middle-click keep working the normal way
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button) return;
      event.preventDefault();
      choose(spot);
    });

    spot.addEventListener('keydown', function (event) {
      if (event.key === ' ' || event.key === 'Spacebar') {   // Space chooses too
        event.preventDefault();
        choose(spot);
      }
    });
  });

  // touch screens: the first tap lights the animal up, the second walks in
  if (window.matchMedia && window.matchMedia('(hover: none)').matches) {
    spots.forEach(function (spot) {
      spot.addEventListener('touchstart', function () {
        if (!spot.classList.contains('is-chosen')) preview(spot);
      }, { passive: true });
    });
  }

  // coming back with the browser's Back button: put everything back
  window.addEventListener('pageshow', function () {
    leaving = false;
    if (scene) scene.removeAttribute('data-chosen');
    reset();
  });
})();
