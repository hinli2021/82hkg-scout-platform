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
    var stack = reveal.querySelector('.reveal-stack') || reveal;
    showCard(stack, 0);
    function seen(card) {
      card.classList.add('is-up', 'is-seen');
    }
    if (reduced()) {
      cards.forEach(seen);
      return;
    }
    cards.forEach(function (card) { card.classList.remove('is-up'); });
    function flip() {
      if (at >= cards.length) {
        reveal.classList.add('is-done');
        return;
      }
      var card = cards[at];
      var rarity = card.getAttribute('data-rarity') || '';
      var rare = !!SR[rarity];
      card.classList.add('is-deal');
      showCard(stack, at);
      reveal._timer = setTimeout(function () {
        card.classList.add('is-up');
        sfx(rare ? 'sparkle' : 'flip');
        if (rare && window.FX && FX.burst) {
          FX.burst(card, rarity === 'LR' || rarity === 'UR' ? 20 : 12, ['✦', '★', '✧']);
        }
        if (rare) {
          stage.classList.add('is-hit');
          setTimeout(function () { stage.classList.remove('is-hit'); }, 720);
        }
        at += 1;
        reveal._timer = setTimeout(function () {
          card.classList.add('is-seen');
          flip();
        }, rare ? 980 : 620);
      }, 280);
    }
    reveal._timer = setTimeout(flip, 180);
    reveal.querySelectorAll('[data-card-prev], [data-card-next]').forEach(function (button) {
      button.addEventListener('click', function () {
        if (reveal._timer) clearTimeout(reveal._timer);
        cards.forEach(seen);
        var current = parseInt(stack.getAttribute('data-at') || '0', 10);
        var next = button.hasAttribute('data-card-prev') ? current - 1 : current + 1;
        if (next < 0) next = 0;
        if (next > cards.length - 1) next = cards.length - 1;
        showCard(stack, next);
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
        sfx('pop');
        var started = Date.now();
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
          var wait = reduced() ? 0 : Math.max(0, 1080 - (Date.now() - started));
          setTimeout(function () {
            stage.classList.remove('is-hit');
            stage.innerHTML = data.html;
            var count = document.querySelector('[data-pack-count]');
            if (count && data.packs != null) count.textContent = String(data.packs);
            var owned = document.querySelector('[data-owned-count]');
            if (owned && data.owned != null) owned.textContent = String(data.owned);
            bind(stage);
            play(stage);
          }, wait);
        }).catch(function () { form.submit(); });
      });
    });
  }

  // Two filters, one result: the category chips and the rarity chips both
  // narrow the album in place, and a card shows only when it passes both.
  var categoryWant = 'all';
  var rarityWant = 'all';

  function rarityMatches(card) {
    var rarity = card.getAttribute('data-rarity') || '';
    var owned = card.getAttribute('data-owned') === '1';
    return rarityWant === 'all'
      || (rarityWant === 'owned' && owned)
      || (rarityWant === 'SR' && owned && (rarity === 'SR' || rarity === 'SSR' || rarity === 'UR' || rarity === 'LR'))
      || rarity === rarityWant;
  }

  function applyAlbumFilters() {
    document.querySelectorAll('[data-album-section]').forEach(function (section) {
      var inCategory = categoryWant === 'all'
        || section.getAttribute('data-category') === categoryWant;
      var any = false;
      section.querySelectorAll('.mini-card').forEach(function (card) {
        var show = inCategory && rarityMatches(card);
        card.hidden = !show;
        if (show) any = true;
      });
      section.hidden = !inCategory;
      var empty = section.querySelector('[data-album-none]');
      if (empty) empty.hidden = !(inCategory && !any);
    });
  }

  document.querySelectorAll('[data-categories] [data-category-filter]').forEach(function (button) {
    if (button.classList.contains('brass')) {
      categoryWant = button.getAttribute('data-category-filter');
    }
    button.addEventListener('click', function () {
      categoryWant = button.getAttribute('data-category-filter');
      document.querySelectorAll('[data-categories] [data-category-filter]').forEach(function (other) {
        var on = other === button;
        other.classList.toggle('brass', on);
        other.classList.toggle('light', !on);
        other.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      applyAlbumFilters();
    });
  });

  document.querySelectorAll('[data-filters] [data-filter]').forEach(function (button) {
    if (button.classList.contains('brass')) {
      rarityWant = button.getAttribute('data-filter');
    }
    button.addEventListener('click', function () {
      rarityWant = button.getAttribute('data-filter');
      document.querySelectorAll('[data-filters] [data-filter]').forEach(function (other) {
        other.classList.toggle('brass', other === button);
      });
      applyAlbumFilters();
    });
  });

  applyAlbumFilters();

  bind(stage);
  play(stage);
})();
