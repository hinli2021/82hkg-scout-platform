/* 每日挑戰 — one small game a day.
   ---------------------------------------------------------------------------
   The page hands over a board (built on the server from the Hong Kong date, so
   every scout in the troop gets the same puzzle) and a signed ticket. This file
   draws the board, judges it, and — when it is solved — posts the ticket and the
   clock so the points can be paid once for the day.

   Four games, one function each:
     pipes    旋轉水管   turn every piece until the net joins up
     fifteen  數字滑塊   the 15-puzzle
     mines    掃雷       8×8, ten mines
     memory   記憶配對   eight pairs
   Everything is drawn from scratch: no images, no libraries, no network beyond
   the one POST that claims the points.
*/
(function () {
  'use strict';

  var host = document.getElementById('daily-game');
  var configEl = document.getElementById('daily-config');
  if (!host || !configEl) return;

  var cfg;
  try { cfg = JSON.parse(configEl.textContent); } catch (e) { return; }
  if (!cfg || !cfg.kind) return;
  window.DAILY_ART = (cfg.board && cfg.board.art) || 'img/badges';

  /* 語言：整頁由 /set-language 設定，遊戲自己畫的字也跟着轉。
     T('中文', 'English') —— 英文版永遠不會掉出中文。 */
  var EN = (document.documentElement.lang || '').slice(0, 2) === 'en' || cfg.language === 'en';
  function T(zh, en) { return EN ? (en || zh) : zh; }

  var clockEl = document.querySelector('[data-daily-clock]');
  var panel = document.querySelector('[data-daily-panel]');
  var resultEl = document.querySelector('[data-daily-result]');

  var startedAt = Date.now();
  var finished = false;
  var timer = window.setInterval(tick, 500);

  function mmss(ms) {
    var s = Math.max(0, Math.floor(ms / 1000));
    return Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2);
  }
  function tick() {
    if (clockEl && !finished) clockEl.textContent = mmss(Date.now() - startedAt);
  }
  function elapsed() { return Date.now() - startedAt; }

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  /* ── the clock, the finish line and the points ────────────────────────── */

  function finish(won) {
    if (finished) return;
    finished = true;
    window.clearInterval(timer);
    if (clockEl) clockEl.textContent = mmss(elapsed());
    var used = elapsed();

    if (!won) {
      show(won, 0, used, '');
      return;
    }
    if (cfg.already) {
      show(won, 0, used, 'already');
      return;
    }
    fetch(cfg.submit_url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'fetch' },
      body: JSON.stringify({ ticket: cfg.ticket, elapsed_ms: used })
    }).then(function (r) { return r.json().catch(function () { return { ok: false }; }); })
      .then(function (data) {
        if (data && data.ok) show(true, data.points || 0, used, data.already ? 'already' : 'paid', '', data.pack);
        else show(true, 0, used, 'refused',
                  (data && (EN ? (data.message_en || data.message_zh) : data.message_zh)) || '');
      })
      .catch(function () { show(true, 0, used, 'refused', ''); });
  }

  function show(won, points, used, note, message, pack) {
    if (!panel) return;
    panel.hidden = false;
    host.classList.add('is-done');
    var line;
    if (!won) {
      line = T('未完成 — 再試一次（不計分）。', 'Not finished — try again (no points this time).');
    } else if (note === 'paid') {
      line = T('完成！＋' + points + ' 分，用時 ' + mmss(used) + '。',
              'Done! +' + points + ' points in ' + mmss(used) + '.');
      if (pack) line += T(' 並得到一個卡包。', ' A card pack is waiting.');
    } else if (note === 'already') {
      line = T('完成！今天的分數已入帳，這次是練習。',
              'Done! Today\'s points are already in — this one was a practice run.');
    } else if (note === 'refused') {
      /* the server said no — its sentence explains why (clock, old ticket, …) */
      line = message || T('完成了，但分數未能記下，請重新整理再試。',
                'Finished, but the points were not saved — reload and try again.');
    } else {
      line = T('完成！用時 ' + mmss(used) + '。', 'Done in ' + mmss(used) + '.');
    }
    resultEl.textContent = line;
    resultEl.classList.toggle('is-good', note === 'paid' || note === 'already');
  }

  /* 再玩一次：重新排一個棋盤，純練習，不會再交分。 */
  function again() {
    finished = false;
    startedAt = Date.now();
    if (panel) panel.hidden = true;
    host.classList.remove('is-done');
    window.clearInterval(timer);
    timer = window.setInterval(tick, 500);
    mount(shuffleBoard(cfg.kind, cfg.board));
  }

  function shuffleBoard(kind, board) {
    function rnd(n) { return Math.floor(Math.random() * n); }
    if (kind === 'memory') {
      var deck = board.cards.slice();
      for (var i = deck.length - 1; i > 0; i--) {
        var j = rnd(i + 1); var t = deck[i]; deck[i] = deck[j]; deck[j] = t;
      }
      return Object.assign({}, board, { cards: deck });
    }
    if (kind === 'fifteen') {
      var b = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 0];
      var gap = 15;
      for (var k = 0; k < 200; k++) {
        var r = Math.floor(gap / 4), c = gap % 4, moves = [];
        if (r > 0) moves.push(gap - 4);
        if (r < 3) moves.push(gap + 4);
        if (c > 0) moves.push(gap - 1);
        if (c < 3) moves.push(gap + 1);
        var step = moves[rnd(moves.length)];
        b[gap] = b[step]; b[step] = 0; gap = step;
      }
      return Object.assign({}, board, { board: b });
    }
    if (kind === 'mines') {
      var spots = [], want = board.mines.length;
      while (spots.length < want) {
        var s = rnd(board.size * board.size);
        if (spots.indexOf(s) < 0) spots.push(s);
      }
      return Object.assign({}, board, { mines: spots.sort(function (a, b2) { return a - b2; }) });
    }
    if (kind === 'pipes') {
      return Object.assign({}, board, {
        cells: board.cells.map(function (cell) {
          return { m: cell.m, t: Math.floor(Math.random() * 4) };
        })
      });
    }
    return board;
  }

  /* ── 旋轉水管 ───────────────────────────────────────────────────────────── */

  var N = 1, E = 2, S = 4, W = 8;
  var DIRS = [[N, 50, 0], [E, 100, 50], [S, 50, 100], [W, 0, 50]];

  function rot(mask, turns) {
    var t = ((turns % 4) + 4) % 4;
    return ((mask << t) | (mask >> (4 - t))) & 15;
  }

  function pipes(board) {
    var size = board.size;
    var cells = board.cells.map(function (c) { return { m: c.m, t: c.t }; });
    var grid = el('div', 'pipes-grid');
    grid.style.setProperty('--n', size);
    var buttons = [];

    function open(row, col, dir) {
      if (row < 0 || col < 0 || row >= size || col >= size) return false;
      return (rot(cells[row * size + col].m, cells[row * size + col].t) & dir) !== 0;
    }

    function solved() {
      for (var r = 0; r < size; r++) {
        for (var c = 0; c < size; c++) {
          var mask = rot(cells[r * size + c].m, cells[r * size + c].t);
          if (mask & N && !open(r - 1, c, S)) return false;
          if (mask & E && !open(r, c + 1, W)) return false;
          if (mask & S && !open(r + 1, c, N)) return false;
          if (mask & W && !open(r, c - 1, E)) return false;
        }
      }
      // …and it must be one piece, not two separate nets
      var seen = {}, stack = [[0, 0]];
      seen['0,0'] = true;
      while (stack.length) {
        var here = stack.pop(), row = here[0], col = here[1];
        var mask = rot(cells[row * size + col].m, cells[row * size + col].t);
        [[N, -1, 0], [E, 0, 1], [S, 1, 0], [W, 0, -1]].forEach(function (step) {
          if (!(mask & step[0])) return;
          var nr = row + step[1], nc = col + step[2];
          if (nr < 0 || nc < 0 || nr >= size || nc >= size) return;
          var key = nr + ',' + nc;
          if (!seen[key]) { seen[key] = true; stack.push([nr, nc]); }
        });
      }
      return Object.keys(seen).length === size * size;
    }

    function paint() {
      cells.forEach(function (cell, i) {
        var mask = rot(cell.m, cell.t);
        var svg = buttons[i].firstChild;
        while (svg.firstChild) svg.removeChild(svg.firstChild);
        var ns = 'http://www.w3.org/2000/svg';
        DIRS.forEach(function (d) {
          if (!(mask & d[0])) return;
          ['pipe-arm', 'pipe-core', 'pipe-water'].forEach(function (cls) {
            var line = document.createElementNS(ns, 'line');
            line.setAttribute('x1', 50); line.setAttribute('y1', 50);
            line.setAttribute('x2', d[1]); line.setAttribute('y2', d[2]);
            line.setAttribute('class', cls);
            svg.appendChild(line);
          });
        });
        var joint = document.createElementNS(ns, 'circle');
        joint.setAttribute('cx', 50); joint.setAttribute('cy', 50);
        joint.setAttribute('r', mask === N || mask === E || mask === S || mask === W ? 20 : 13);
        joint.setAttribute('class', 'pipe-joint');
        svg.appendChild(joint);
      });
      var done = solved();
      grid.classList.toggle('is-solved', done);
      if (done) finish(true);
    }

    cells.forEach(function (cell, i) {
      var button = el('button', 'pipe');
      button.type = 'button';
      button.setAttribute('aria-label', 'pipe ' + (i + 1));
      button.appendChild(document.createElementNS('http://www.w3.org/2000/svg', 'svg'));
      button.firstChild.setAttribute('viewBox', '0 0 100 100');
      button.firstChild.setAttribute('class', 'pipe-svg');
      button.addEventListener('click', function () {
        if (finished) return;
        cells[i].t = (cells[i].t + 1) % 4;
        paint();
        if (window.FX && FX.sfx) { try { FX.sfx('tap'); } catch (e) {} }
      });
      buttons.push(button);
      grid.appendChild(button);
    });
    paint();
    return grid;
  }

  /* ── 數字滑塊 ───────────────────────────────────────────────────────────── */

  /* ── 營地滑塊拼圖 ───────────────────────────────────────────────────────
     15 格滑塊，但拼的不是數字，而是一幅營地圖畫：太陽、旗、營帳、營火、
     樹林。每一格是圖畫的一塊（用同一張 SVG 做背景，按位置裁剪），角落
     留一個很小的號碼，方便小朋友記位置。旁邊放一張完成圖作對照。 */

  function campScene() {
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400">' +
      // sky
      '<rect width="400" height="400" fill="#0e2a1e"/>' +
      '<rect y="0" width="400" height="210" fill="#123726"/>' +
      // sun + rays
      '<circle cx="86" cy="78" r="40" fill="#f6d68a"/>' +
      '<circle cx="86" cy="78" r="54" fill="#f6d68a" opacity=".18"/>' +
      '<g stroke="#f6d68a" stroke-width="4" stroke-linecap="round" opacity=".85">' +
        '<path d="M86 10 v-16 M86 146 v16 M18 78 h-16 M154 78 h16"/>' +
        '<path d="M40 32 l-11 -11 M132 32 l11 -11 M40 124 l-11 11 M132 124 l11 11"/>' +
      '</g>' +
      // birds
      '<g stroke="#cfe8d8" stroke-width="3.5" fill="none" stroke-linecap="round" opacity=".8">' +
        '<path d="M186 62 q10 -9 20 0 q10 -9 20 0"/>' +
        '<path d="M236 92 q8 -7 16 0 q8 -7 16 0"/>' +
      '</g>' +
      // far hills
      '<path d="M0 210 q60 -46 128 -16 q52 24 104 6 q76 -28 168 8 v46 H0 z" fill="#17452c"/>' +
      // trees on the ridge
      '<g fill="#0b2317">' +
        '<path d="M28 196 l13 -30 l13 30 z"/><path d="M62 200 l10 -24 l10 24 z"/>' +
        '<path d="M188 186 l12 -28 l12 28 z"/><path d="M214 190 l9 -22 l9 22 z"/>' +
        '<path d="M352 198 l13 -30 l13 30 z"/>' +
      '</g>' +
      // near ground
      '<path d="M0 256 q120 -22 232 -4 q92 14 168 -6 v154 H0 z" fill="#1f5c3a"/>' +
      '<path d="M0 300 q140 -16 250 2 q84 12 150 -4 v102 H0 z" fill="#14402a"/>' +
      // flag pole + banner
      '<rect x="316" y="74" width="7" height="132" rx="3" fill="#d9a441"/>' +
      '<path d="M323 84 h66 v54 h-66 z" fill="#9e2b25"/>' +
      '<path d="M323 84 h66 v54 h-66 z" fill="none" stroke="#7a1f1a" stroke-width="3"/>' +
      // fleur-de-lis on the banner
      '<g fill="#f6d68a" transform="translate(356,111)">' +
        '<path d="M0 -19 c7 0 10 6 8 12 c-2 5 -6 7 -8 7 c-2 0 -6 -2 -8 -7 c-2 -6 1 -12 8 -12 z"/>' +
        '<path d="M-15 -6 c6 -2 10 2 9 8 c-1 4 -4 6 -7 6 c-4 -1 -6 -5 -4 -9 z" transform="rotate(-18)"/>' +
        '<path d="M15 -6 c6 -2 10 2 9 8 c-1 4 -4 6 -7 6 c-4 -1 -6 -5 -4 -9 z" transform="rotate(18)"/>' +
        '<rect x="-3" y="6" width="6" height="15" rx="3"/>' +
      '</g>' +
      // tent — kept clear of the bottom-right corner, which the gap hides
      '<path d="M138 336 l52 -80 l52 80 z" fill="#e0b268"/>' +
      '<path d="M138 336 l52 -80 l52 80 z" fill="none" stroke="#8a6134" stroke-width="4"/>' +
      '<path d="M190 336 l0 -44 l-16 44 z" fill="#6f4e28"/>' +
      '<path d="M170 256 l-8 -18 M210 256 l8 -18" stroke="#d9a441" stroke-width="4" stroke-linecap="round"/>' +
      // campfire
      '<g transform="translate(66,342)">' +
        '<path d="M-30 18 l60 -14 M-30 4 l60 14" stroke="#6f4e28" stroke-width="9" stroke-linecap="round"/>' +
        '<path d="M0 -30 c14 12 20 22 20 30 c0 11 -9 18 -20 18 c-11 0 -20 -7 -20 -18 c0 -8 6 -18 20 -30 z" fill="#f0a83c"/>' +
        '<path d="M0 -8 c7 7 10 12 10 17 c0 7 -4 11 -10 11 c-6 0 -10 -4 -10 -11 c0 -5 3 -10 10 -17 z" fill="#f6d68a"/>' +
      '</g>' +
      // ground detail: stones, grass, and a small copse in the far corner
      '<g fill="#0f3423">' +
        '<circle cx="128" cy="360" r="7"/><circle cx="146" cy="366" r="5"/>' +
        '<path d="M112 330 q6 -14 12 0 z"/><path d="M238 322 q6 -14 12 0 z"/>' +
      '</g>' +
      '<g fill="#0b2317" opacity=".9">' +
        '<path d="M330 372 l16 -34 l16 34 z"/><path d="M362 380 l12 -26 l12 26 z"/>' +
        '<path d="M306 384 l11 -24 l11 24 z"/>' +
      '</g>' +
      '</svg>';
  }

  var SCENE_URI = 'url("data:image/svg+xml,' + encodeURIComponent(campScene()) + '")';

  function fifteen(board) {
    var size = board.size;
    var tiles = board.board.slice();
    var outer = el('div', 'fifteen-wrap');
    var wrap = el('div', 'fifteen-grid');
    wrap.style.setProperty('--n', size);

    // the finished picture, small, so the scout knows what to build
    var ref = el('figure', 'fifteen-ref');
    var refPic = el('span', 'fifteen-ref-pic');
    refPic.style.backgroundImage = SCENE_URI;
    ref.appendChild(refPic);
    ref.appendChild(el('figcaption', 'fifteen-ref-cap', T('營地 · 完成圖', 'Camp · finished')));

    function solved() {
      for (var i = 0; i < tiles.length - 1; i++) if (tiles[i] !== i + 1) return false;
      return tiles[tiles.length - 1] === 0;
    }
    function paint() {
      wrap.innerHTML = '';
      tiles.forEach(function (value, index) {
        if (!value) {
          var gap = el('span', 'fifteen-gap');
          gap.innerHTML = '<span class="fifteen-gap-mark">⚜</span>';
          wrap.appendChild(gap);
          return;
        }
        var tile = el('button', 'fifteen-tile');
        tile.type = 'button';
        var slot = value - 1;                       // where this piece belongs
        var row = Math.floor(slot / size), col = slot % size;
        tile.style.backgroundImage = SCENE_URI;
        tile.style.backgroundSize = (size * 100) + '% ' + (size * 100) + '%';
        tile.style.backgroundPosition =
          (col / (size - 1) * 100).toFixed(4) + '% ' + (row / (size - 1) * 100).toFixed(4) + '%';
        tile.appendChild(el('span', 'fifteen-num', String(value)));
        tile.setAttribute('aria-label', T('第 ' + value + ' 塊', 'Piece ' + value));
        tile.addEventListener('click', function () { move(index); });
        wrap.appendChild(tile);
      });
    }
    function move(index) {
      if (finished) return;
      var gap = tiles.indexOf(0);
      var r = Math.floor(index / size), c = index % size;
      var gr = Math.floor(gap / size), gc = gap % size;
      if (Math.abs(r - gr) + Math.abs(c - gc) !== 1) return;
      tiles[gap] = tiles[index]; tiles[index] = 0;
      paint();
      if (window.FX && FX.sfx) { try { FX.sfx('tap'); } catch (e) {} }
      if (solved()) finish(true);
    }
    paint();
    outer.appendChild(wrap);
    outer.appendChild(ref);
    return outer;
  }

  /* ── 掃雷 ───────────────────────────────────────────────────────────────── */

  /* ── 營地排險 ───────────────────────────────────────────────────────────
     規則同掃雷一樣，但畫的是童軍起營前要做的第一件事：清場。草地下面
     藏了鐵釘、玻璃碎和未熄的炭火；撥開草、數一數旁邊有幾件，插旗標出
     有危險的格。踩中就要重新清一次。 */

  var HAZARD_ART = {
    nail: '<g stroke="#4a3a2a" stroke-width="2.8" stroke-linecap="round" fill="none">' +
          '<path d="M5 7h14"/><path d="M12 7v12"/>' +
          '<path d="M12 19l-2.4-3M12 19l2.4-3"/></g>',
    glass: '<g fill="#cfeaf2" stroke="#6f9fae" stroke-width="1.4" stroke-linejoin="round">' +
           '<path d="M4 19l6-14 4 8-4 6z"/><path d="M14 19l4-7 2 7z"/></g>' +
           '<path d="M9 9.5l1.6 3" stroke="#fff" stroke-width="1.2" opacity=".8"/>',
    ember: '<g><path d="M12 4c3.2 2.8 4.6 5.6 3 8.6-1 1.9-2.6 3-4.6 3-2.6 0-4.4-1.9-4.4-4.3 0-2 1.1-3.4 2.4-4.4.3 1 .9 1.8 1.8 2.2.3-2.1 1-3.6 1.8-5.1z" fill="#e2743a"/>' +
           '<path d="M12 11c1.1 1.2 1.4 2.4.5 3.4-.7.8-2 .8-2.7 0-.8-1-.3-2.2.6-3.2.4.4.8.6 1.2.6z" fill="#f7c948"/></g>'
  };

  function hazardSvg(kind) {
    return '<svg class="mine-art" viewBox="0 0 24 24" aria-hidden="true">' +
           (HAZARD_ART[kind] || HAZARD_ART.nail) + '</svg>';
  }

  function pennantSvg() {
    return '<svg class="mine-pennant" viewBox="0 0 24 24" aria-hidden="true">' +
           '<path d="M7 3.5v17" stroke="#7a5a2c" stroke-width="2.2" stroke-linecap="round"/>' +
           '<path d="M7 4.6l10 3.6-10 3.6z" fill="#b3261e"/>' +
           '<path d="M4 20.6h6" stroke="#7a5a2c" stroke-width="2" stroke-linecap="round"/></svg>';
  }

  function mines(board) {
    var size = board.size;
    var total = size * size;
    var kinds = board.hazards || {};
    var mineAt = {};
    board.mines.forEach(function (i) { mineAt[i] = true; });
    var open = {}, flagged = {}, starts = true, dead = false;
    var wrap = el('div', 'mines-wrap');
    var bar = el('div', 'mines-bar');
    var flagButton = el('button', 'btn ghost small', T('🚩 標記危險', '🚩 Mark a hazard'));
    flagButton.type = 'button';
    var count = el('span', 'chip', '⚠️ 0 / ' + board.count);
    bar.appendChild(flagButton); bar.appendChild(count);
    var note = el('p', 'mines-note',
      T('起營前先清場：撥開草，插旗標出草地上的危險物。',
        'Clear the ground before the tents go up: part the grass, plant a pennant on anything dangerous.'));
    var grid = el('div', 'mines-grid');
    grid.style.setProperty('--n', size);
    wrap.appendChild(bar); wrap.appendChild(grid); wrap.appendChild(note);

    var flagging = false;
    flagButton.addEventListener('click', function () {
      flagging = !flagging;
      flagButton.classList.toggle('is-on', flagging);
      flagButton.textContent = flagging ? T('🚩 標記中…', '🚩 Marking…') : T('🚩 標記危險', '🚩 Mark a hazard');
    });

    function neighbours(i) {
      var r = Math.floor(i / size), c = i % size, out = [];
      for (var dr = -1; dr <= 1; dr++) {
        for (var dc = -1; dc <= 1; dc++) {
          if (!dr && !dc) continue;
          var nr = r + dr, nc = c + dc;
          if (nr >= 0 && nc >= 0 && nr < size && nc < size) out.push(nr * size + nc);
        }
      }
      return out;
    }
    function mineCount(i) {
      return neighbours(i).filter(function (n) { return mineAt[n]; }).length;
    }
    function flaggedCount() {
      return Object.keys(flagged).filter(function (k) { return flagged[k]; }).length;
    }
    function firstClickSafe(index) {
      // the first tap is always safe: move a hazard out of the way if need be
      if (!mineAt[index]) return;
      delete mineAt[index];
      for (var i = 0; i < total; i++) {
        if (i !== index && !open[i] && !mineAt[i]) { mineAt[i] = true; return; }
      }
    }
    function reveal(index) {
      if (open[index] || flagged[index]) return;
      var stack = [index];
      while (stack.length) {
        var here = stack.pop();
        if (open[here] || flagged[here]) continue;
        open[here] = true;
        if (mineCount(here) === 0) neighbours(here).forEach(function (n) { stack.push(n); });
      }
    }
    function paint() {
      grid.innerHTML = '';
      for (var i = 0; i < total; i++) {
        var cell = el('button', 'mine-cell');
        cell.type = 'button';
        var isMine = !!mineAt[i];
        if (open[i] || (dead && isMine)) {
          cell.classList.add('is-open');
          if (isMine) {
            cell.classList.add('is-hazard');
            cell.innerHTML = hazardSvg(kinds[String(i)]);
            cell.setAttribute('aria-label', T('危險物', 'Hazard'));
          } else {
            var n = mineCount(i);
            if (n) { cell.textContent = String(n); cell.classList.add('n' + n); }
          }
        } else if (flagged[i]) {
          cell.classList.add('is-flag');
          cell.innerHTML = pennantSvg();
          cell.setAttribute('aria-label', T('已標記', 'Marked'));
        } else {
          cell.innerHTML = '<span class="mine-grass"></span>';
        }
        cell.addEventListener('click', onCell(i));
        grid.appendChild(cell);
      }
      var opened = Object.keys(open).length;
      count.textContent = '⚠️ ' + flaggedCount() + ' / ' + board.count +
                          '　🌿 ' + opened + '/' + (total - board.count);
    }
    function onCell(index) {
      return function () {
        if (finished || dead) return;
        if (flagging) {
          if (!open[index]) flagged[index] = !flagged[index];
          paint(); return;
        }
        if (open[index] || flagged[index]) return;
        if (starts) { starts = false; firstClickSafe(index); }
        if (mineAt[index]) {
          dead = true;
          open[index] = true;
          paint();
          grid.classList.add('is-dead');
          note.textContent = T('踩中危險物！場地未清好，營帳不能落地 —— 再清一次。',
            'You stood on a hazard! The ground is not clear, so no tent — clear it again.');
          if (window.FX && FX.sfx) { try { FX.sfx('wrong'); } catch (e) {} }
          finish(false);
          return;
        }
        reveal(index);
        paint();
        if (window.FX && FX.sfx) { try { FX.sfx('tap'); } catch (e) {} }
        if (Object.keys(open).length === total - board.count) {
          note.textContent = T('場地清好了 —— 可以落營。', 'Ground clear — the tents can go up.');
          finish(true);
        }
      };
    }
    paint();
    return wrap;
  }

  /* ── 專科徽章配對 ───────────────────────────────────────────────────────
     八枚專科徽章，每枚兩張。圖是香港童軍總會《童軍訓練綱要》的官方徽章
     圖樣（static/img/badges/），服務器每天抽八枚。配成一對之後，桌上的
     徽章簿會寫出這一枚屬於哪一組、要考甚麼。 */

  function badgeName(badge) {
    return EN ? (badge.en || badge.zh) : badge.zh;
  }

  function badgeImg(badge, faceDown) {
    if (faceDown) return '<span class="memory-back">⚜</span>';
    var src = (badge.art || '') ? ('/static/' + (window.DAILY_ART || 'img/badges') + '/' + badge.art) : '';
    if (!src) return '<span class="memory-back">⚜</span>';
    return '<img class="badge-img" src="' + src + '" alt="' + badgeName(badge) + '" ' +
           'width="133" height="133" loading="lazy" draggable="false">';
  }

  function memory(board) {
    var cards = board.cards.slice();
    var badges = board.badges;
    var up = {}, matched = {}, first = null, lock = false;
    var wrap = el('div', 'memory-wrap');
    var grid = el('div', 'memory-grid');
    var book = el('div', 'badge-book');
    wrap.appendChild(grid);
    wrap.appendChild(book);

    function paintBook() {
      var got = Object.keys(matched).map(function (i) { return cards[i]; })
        .filter(function (v, i, all) { return all.indexOf(v) === i; });
      if (!got.length) {
        book.innerHTML = '<p class="muted small" style="margin:.4rem 0 0">' +
          T('配對後，這裡會寫出每枚專科徽章要考甚麼。',
            'Match the pairs and this book says what each badge asks for.') + '</p>';
        return;
      }
      book.innerHTML = '<p class="badge-book-title">🎖️ ' + T('徽章簿', 'Badge book') + ' · ' + got.length + ' / 8</p>' +
        '<ul class="badge-book-list">' + got.map(function (b) {
          var badge = badges[b];
          return '<li><img class="badge-book-art" src="/static/' + (window.DAILY_ART || 'img/badges') +
                 '/' + badge.art + '" alt="" width="133" height="133">' +
                 '<span><strong>' + badgeName(badge) + '</strong> ' +
                 '<span class="badge-group">' + (EN ? (badge.group_en || badge.group_zh || '') : (badge.group_zh || '')) + '</span> ' +
                 '<span class="muted small">' + (EN ? (badge.what_en || badge.what_zh) : badge.what_zh) + '</span></span></li>';
        }).join('') + '</ul>';
    }

    function paint() {
      grid.innerHTML = '';
      cards.forEach(function (badgeIndex, i) {
        var card = el('button', 'memory-card');
        card.type = 'button';
        var faceUp = up[i] || matched[i];
        card.innerHTML = badgeImg(badges[badgeIndex], !faceUp);
        if (faceUp) card.classList.add('is-up');
        if (matched[i]) card.classList.add('is-matched');
        card.setAttribute('aria-label', faceUp ? badgeName(badges[badgeIndex]) : T('未翻開', 'Face down'));
        card.addEventListener('click', function () { flip(i); });
        grid.appendChild(card);
      });
      paintBook();
    }
    function flip(i) {
      if (finished || lock || up[i] || matched[i]) return;
      up[i] = true;
      paint();
      if (first === null) { first = i; return; }
      var a = first, b = i;
      first = null;
      if (cards[a] === cards[b]) {
        matched[a] = matched[b] = true;
        up[a] = up[b] = false;
        paint();
        if (window.FX && FX.sfx) { try { FX.sfx('correct'); } catch (e) {} }
        if (Object.keys(matched).length === cards.length) finish(true);
        return;
      }
      lock = true;
      window.setTimeout(function () {
        up[a] = up[b] = false;
        lock = false;
        paint();
      }, 760);
    }
    paint();
    return wrap;
  }

  /* ── go ─────────────────────────────────────────────────────────────────── */

  var BUILD = { pipes: pipes, fifteen: fifteen, mines: mines, memory: memory };

  function mount(board) {
    var build = BUILD[cfg.kind];
    if (!build) return;
    host.innerHTML = '';
    host.appendChild(build(board));
  }

  var againButton = document.querySelector('[data-daily-again]');
  if (againButton) againButton.addEventListener('click', again);

  mount(cfg.board);
  tick();
})();
