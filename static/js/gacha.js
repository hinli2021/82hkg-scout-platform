/* 抽卡 — tap the pack, flip five cards. No-JS still posts the form. */
(function () {
  var stage = document.getElementById('gacha-stage');
  if (!stage) return;
  var SR = { SR: 1, SSR: 1, UR: 1, LR: 1 };

  function reduced() {
    return window.FX && FX.reducedMotion && FX.reducedMotion();
  }

  function sfx(name) {
    if (window.FX && FX.sfx) FX.sfx(name);
  }

  function showCard(stack, index) {
    var cards = stack.querySelectorAll('[data-card]');
    var n = stack.parentNode.querySelector('[data-card-n]');
    cards.forEach(function (card, i) {
      card.classList.toggle('is-current', i === index);
      card.classList.toggle('is-behind', i === index - 1);
    });
    if (n) n.textContent = (index + 1) + '/' + cards.length;
    stack.setAttribute('data-at', String(index));
  }

  function play(root) {
    var reveal = root.querySelector('[data-reveal]');
    if (!reveal || reveal.getAttribute('data-played') === '1') return;
    reveal.setAttribute('data-played', '1');
    reveal.classList.add('is-live');
    var cards = [].slice.call(reveal.querySelectorAll('[data-card]'));
    if (!cards.length) return;
    var at = 0;
    showCard(reveal.querySelector('.reveal-stack') || reveal, 0);
    if (reduced()) {
      cards.forEach(function (card) { card.classList.add('is-up'); });
      return;
    }
    cards.forEach(function (card) { card.classList.remove('is-up'); });
    function flip() {
      if (at >= cards.length) return;
      var card = cards[at];
      card.classList.add('is-up');
      showCard(reveal.querySelector('.reveal-stack') || reveal, at);
      var rarity = card.getAttribute('data-rarity') || '';
      sfx(SR[rarity] ? 'badge' : 'correct');
      at += 1;
      if (at < cards.length) {
        reveal._timer = setTimeout(flip, SR[rarity] ? 1100 : 680);
      }
    }
    reveal._timer = setTimeout(flip, 280);
    reveal.querySelectorAll('[data-card-prev], [data-card-next]').forEach(function (button) {
      button.addEventListener('click', function () {
        if (reveal._timer) clearTimeout(reveal._timer);
        cards.forEach(function (card) { card.classList.add('is-up'); });
        var current = parseInt(reveal.querySelector('.reveal-stack').getAttribute('data-at') || '0', 10);
        var next = button.hasAttribute('data-card-prev') ? current - 1 : current + 1;
        if (next < 0) next = 0;
        if (next > cards.length - 1) next = cards.length - 1;
        showCard(reveal.querySelector('.reveal-stack'), next);
      });
    });
  }

  function bind(root) {
    root.querySelectorAll('[data-pack-form]').forEach(function (form) {
      if (form.getAttribute('data-bound') === '1') return;
      form.setAttribute('data-bound', '1');
      form.addEventListener('submit', function (ev) {
        if (!window.fetch) return;
        ev.preventDefault();
        var foil = form.querySelector('.foil');
        var button = form.querySelector('button');
        if (button) button.disabled = true;
        if (foil) foil.classList.add('is-opening');
        sfx('tap');
        fetch(form.action, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'X-Requested-With': 'fetch', 'Accept': 'application/json' },
          body: new FormData(form)
        }).then(function (response) {
          return response.json().catch(function () { return { ok: false }; });
        }).then(function (data) {
          if (!data || !data.ok || !data.html) {
            form.submit();
            return;
          }
          stage.innerHTML = data.html;
          var count = document.querySelector('[data-pack-count]');
          if (count && data.packs != null) count.textContent = String(data.packs);
          var owned = document.querySelector('[data-owned-count]');
          if (owned && data.owned != null) owned.textContent = String(data.owned);
          bind(stage);
          play(stage);
        }).catch(function () { form.submit(); });
      });
    });
  }

  document.querySelectorAll('[data-filters] [data-filter]').forEach(function (button) {
    button.addEventListener('click', function () {
      var want = button.getAttribute('data-filter');
      document.querySelectorAll('[data-filters] [data-filter]').forEach(function (other) {
        other.classList.toggle('brass', other === button);
      });
      document.querySelectorAll('.mini-card').forEach(function (card) {
        var rarity = card.getAttribute('data-rarity') || '';
        var owned = card.getAttribute('data-owned') === '1';
        var show = want === 'all'
          || (want === 'owned' && owned)
          || (want === 'SR' && owned && (rarity === 'SR' || rarity === 'SSR' || rarity === 'UR' || rarity === 'LR'))
          || rarity === want;
        card.hidden = !show;
      });
    });
  });

  bind(stage);
  play(stage);
})();
