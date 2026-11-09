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
        if (data && data.ok) show(true, data.points || 0, used, data.already ? 'already' : 'paid');
        else show(true, 0, used, 'refused', (data && data.message_zh) || '');
      })
      .catch(function () { show(true, 0, used, 'refused', ''); });
  }

  function show(won, points, used, note, message) {
    if (!panel) return;
    panel.hidden = false;
    host.classList.add('is-done');
    var line;
    if (!won) {
      line = '未完成 — 再試一次（不計分）。';
    } else if (note === 'paid') {
      line = '完成！＋' + points + ' 分，用時 ' + mmss(used) + '。';
    } else if (note === 'already') {
      line = '完成！今天的分數已入帳，這次是練習。';
    } else if (note === 'refused') {
      /* the server said no — its sentence explains why (clock, old ticket, …) */
      line = message || '完成了，但分數未能記下，請重新整理再試。';
    } else {
      line = '完成！用時 ' + mmss(used) + '。';
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
          var line = document.createElementNS(ns, 'line');
          line.setAttribute('x1', 50); line.setAttribute('y1', 50);
          line.setAttribute('x2', d[1]); line.setAttribute('y2', d[2]);
          line.setAttribute('class', 'pipe-arm');
          svg.appendChild(line);
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

  function fifteen(board) {
    var size = board.size;
    var tiles = board.board.slice();
    var wrap = el('div', 'fifteen-grid');
    wrap.style.setProperty('--n', size);

    function solved() {
      for (var i = 0; i < tiles.length - 1; i++) if (tiles[i] !== i + 1) return false;
      return tiles[tiles.length - 1] === 0;
    }
    function paint() {
      wrap.innerHTML = '';
      tiles.forEach(function (value, index) {
        if (!value) { wrap.appendChild(el('span', 'fifteen-gap')); return; }
        var tile = el('button', 'fifteen-tile', String(value));
        tile.type = 'button';
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
    return wrap;
  }

  /* ── 掃雷 ───────────────────────────────────────────────────────────────── */

  function mines(board) {
    var size = board.size;
    var total = size * size;
    var mineAt = {};
    board.mines.forEach(function (i) { mineAt[i] = true; });
    var open = {}, flagged = {}, starts = true;
    var wrap = el('div', 'mines-wrap');
    var bar = el('div', 'mines-bar');
    var flagButton = el('button', 'btn ghost small', '🚩 插旗');
    flagButton.type = 'button';
    var count = el('span', 'chip', '💣 ' + board.count);
    bar.appendChild(flagButton); bar.appendChild(count);
    var grid = el('div', 'mines-grid');
    grid.style.setProperty('--n', size);
    wrap.appendChild(bar); wrap.appendChild(grid);

    var flagging = false;
    flagButton.addEventListener('click', function () {
      flagging = !flagging;
      flagButton.classList.toggle('is-on', flagging);
      flagButton.textContent = flagging ? '🚩 插旗中' : '🚩 插旗';
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
    function firstClickSafe(index) {
      // the first tap is always safe: move a mine out of the way if need be
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
        if (open[i]) {
          cell.classList.add('is-open');
          var n = mineCount(i);
          if (n) { cell.textContent = String(n); cell.classList.add('n' + n); }
        } else if (flagged[i]) {
          cell.classList.add('is-flag');
          cell.textContent = '🚩';
        }
        cell.addEventListener('click', onCell(i));
        grid.appendChild(cell);
      }
      var opened = Object.keys(open).length;
      count.textContent = '💣 ' + board.count + ' · ' + opened + '/' + (total - board.count);
    }
    function onCell(index) {
      return function () {
        if (finished) return;
        if (flagging) {
          if (!open[index]) flagged[index] = !flagged[index];
          paint(); return;
        }
        if (open[index] || flagged[index]) return;
        if (starts) { starts = false; firstClickSafe(index); }
        if (mineAt[index]) {
          open[index] = true;
          paint();
          grid.classList.add('is-dead');
          if (window.FX && FX.sfx) { try { FX.sfx('wrong'); } catch (e) {} }
          finish(false);
          return;
        }
        reveal(index);
        paint();
        if (window.FX && FX.sfx) { try { FX.sfx('tap'); } catch (e) {} }
        if (Object.keys(open).length === total - board.count) finish(true);
      };
    }
    paint();
    return wrap;
  }

  /* ── 記憶配對 ───────────────────────────────────────────────────────────── */

  function memory(board) {
    var cards = board.cards.slice();
    var faces = board.faces;
    var up = {}, matched = {}, first = null, lock = false;
    var grid = el('div', 'memory-grid');

    function paint() {
      grid.innerHTML = '';
      cards.forEach(function (face, i) {
        var card = el('button', 'memory-card');
        card.type = 'button';
        if (up[i] || matched[i]) {
          card.classList.add('is-up');
          card.textContent = faces[face];
        } else {
          card.textContent = '⚜';
        }
        if (matched[i]) card.classList.add('is-matched');
        card.addEventListener('click', function () { flip(i); });
        grid.appendChild(card);
      });
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
      }, 680);
    }
    paint();
    return grid;
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
