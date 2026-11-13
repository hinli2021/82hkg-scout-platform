/* 溪谷旗桿 — game 4 of 會員章 (items 7 to 10).
   The flagpole by the stream is worked by an old pipe machine. Four runs of
   pipe have to be connected before the flag will rise: pick a gap on the
   control panel, read the question at the top, drag the right pipe into the
   gap, then press the start button on the right. A red light means a pipe is
   wrong somewhere; a green glow raises the flag another quarter. The last
   patrol's notebook sits on the left of the panel and holds everything the
   scout needs. The 30 answers still come from the leader's paper; the server
   re-checks every answer on submit. */
(function () {
  "use strict";

  var root = document.querySelector("[data-flag]");
  if (!root) return;
  var config = {};
  try { config = JSON.parse(root.getAttribute("data-flag-config") || "{}"); }
  catch (e) { config = {}; }

  var lang = document.documentElement.lang === "en" ? "en" : "zh";
  function t(zh, en) { return lang === "en" ? (en || zh || "") : (zh || en || ""); }
  function sfx(name) { if (window.FX && FX.sfx) { try { FX.sfx(name); } catch (e) { /* sound is a bonus */ } } }

  var stations = config.stations || [];
  var intro = config.intro || [];
  var ending = config.ending || [];
  var card = root.querySelector("[data-flag-card]");
  var progress = root.querySelector("[data-flag-progress]");
  var picture = root.querySelector(".cave-picture");
  var badgeLink = root.querySelector('[data-flag-link="badge"]');
  /* the painting behind every scene: the bare-pole valley before the
     walk, and the same valley with the flag at the top for the ending.
     Both are remembered here so start() can put the bare pole back. */
  var sceneArt = picture ? picture.querySelector("[data-flag-art]") : null;
  var sceneBackdrop = picture ? picture.querySelector(".cave-art-backdrop") : null;
  var startArtUrl = sceneArt ? sceneArt.getAttribute("src") : "";
  function swapSceneArt(url) {
    if (!url) return;
    if (sceneArt) sceneArt.setAttribute("src", url);
    if (sceneBackdrop) sceneBackdrop.setAttribute("src", url);
  }

  /* the seven notebook chapters become four runs of pipe */
  var STAGE_DEFS = [
    { ids: ["look", "stars"], zh: "第一組喉管：旗和徽", en: "Pipe run 1: flags and emblems" },
    { ids: ["flower", "poles"], zh: "第二組喉管：兩面旗的位置", en: "Pipe run 2: where the two flags go" },
    { ids: ["anthem", "sing"], zh: "第三組喉管：國歌", en: "Pipe run 3: the anthem" },
    { ids: ["raise"], zh: "最後一組喉管：升到桿頂", en: "Final pipe run: up to the top" }
  ];
  var PIPE_KINDS = ["pipe-straight", "pipe-elbow", "pipe-zigzag", "pipe-wave"];
  /* the same four pipes already fitted into the hole — one painting each,
     exactly the size of the empty hole, so selecting a pipe swaps the
     whole hole picture instead of laying a pipe over it */
  var FITTED_KINDS = ["hole-pipe-straight", "hole-pipe-elbow", "hole-pipe-zigzag", "hole-pipe-wave"];

  /* Holes sit in a neat grid, always inside the panel's black board. The
     dark board itself spans only about x 32–68%, y 31–76% of the panel
     painting (the brass frame and the wheels sit outside it), so the holes
     are kept small and centred on x 50% with a margin inside the black.
     Centres are in percent of the panel. */
  function holeSpot(index, count) {
    var cols, width, rowYs, spacing;
    if (count <= 2) { cols = count; width = 11.5; rowYs = [53]; spacing = 13.5; }
    else if (count <= 9) { cols = 3; width = 10; rowYs = [39.5, 53, 66.5]; spacing = 11; }
    else { cols = 5; width = 6.2; rowYs = [45, 61]; spacing = 6.9; }
    var row = Math.floor(index / cols);
    var inRow = Math.min(cols, count - row * cols);
    var col = index - row * cols;
    var x = 50 + (col - (inRow - 1) / 2) * spacing;
    var y = rowYs[Math.min(row, rowYs.length - 1)];
    return { x: x, y: y, width: width };
  }

  function shuffled(list) {
    var a = list.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = a[i]; a[i] = a[j]; a[j] = tmp;
    }
    return a;
  }

  function stationById(id) {
    return stations.filter(function (s) { return s.id === id; })[0] || null;
  }
  var stages = STAGE_DEFS.map(function (def) {
    var qs = [], pages = [];
    def.ids.forEach(function (id) {
      var st = stationById(id);
      if (!st) return;
      (st.questions || []).forEach(function (q) { qs.push({ q: q, station: st }); });
      (st.learn || []).forEach(function (p) { pages.push(Object.assign({}, p, { _station: st.id })); });
    });
    return { def: def, questions: qs, learn: pages };
  }).filter(function (s) { return s.questions.length; });

  var placements = {};       /* qid -> chosen option index, checked only at start-up */
  var holeOrder = [];        /* shuffled hole order for the stage being fitted */
  var kindMaps = {};         /* qid -> pipe kind per option, shuffled each stage */
  var trayOrders = {};       /* qid -> order the pipes are offered in, shuffled */
  var wrongIds = {};         /* qids the start button has proved wrong this run */
  var startState = "";       /* "", "wrong" (red button) or "right" (green glow) */
  var howtoShown = false;    /* the how-to-play pop-up shows once, after the first notes */
  var selected = null;        /* qid of the gap being fitted */
  var stageIndex = 0;
  var startedAt = 0;
  var filed = false;
  var machineLive = false;    /* false while the button is showing a result / the flag is rising */

  function sourceUrl(name) {
    var img = root.querySelector('[data-flag-source="' + name + '"]');
    return img ? img.getAttribute("src") : "";
  }
  function cloth(name, extra) {
    return '<img class="flag-cloth ' + (extra || "") + '" src="' + sourceUrl(name) + '" alt="">';
  }
  function artImg(name, cls) {
    return '<img class="' + cls + '" src="' + sourceUrl(name) + '" alt="">';
  }
  function setProgress(text) { if (progress) progress.textContent = text; }
  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function cardHtml(kicker, title, body, extra) {
    return '<span class="cave-kicker">' + escapeHtml(kicker) + '</span>'
      + '<h1 class="cave-title">' + escapeHtml(title) + '</h1>'
      + (body ? '<p class="cave-line">' + escapeHtml(body) + '</p>' : '')
      + (extra || "");
  }
  function stage() { return stages[stageIndex]; }
  function stageName() { var s = stage(); return s ? t(s.def.zh, s.def.en) : ""; }
  function findItem(qid) {
    var found = null;
    stages.forEach(function (s) {
      s.questions.forEach(function (it) { if (it.q.id === qid) found = it; });
    });
    return found;
  }
  function optionsOf(q) { return (lang === "en" ? q.options_en : q.options_zh) || []; }

  /* Each stage is dealt afresh: the questions land on random holes (so the
     hole numbers change every run) and every answer is offered as a random
     pipe kind in a random tray order — the pipe a scout picks is still the
     original option index, so grading is unchanged. */
  function prepareStage() {
    var s = stage();
    kindMaps = {}; trayOrders = {}; wrongIds = {}; startState = "";
    if (!s) { holeOrder = []; return; }
    /* The anthem run keeps its lyric gaps together, in the order they are
       sung: the general anthem questions are dealt first, then the six
       words of the song follow one after another (q23 to q28), so the
       scout fills the song in as it flows instead of hunting for the
       next word among shuffled holes. Every other run is fully shuffled. */
    var lyricOrder = [], otherOrder = [];
    s.questions.forEach(function (it, i) {
      if (it.station && it.station.id === "sing") lyricOrder.push(i);
      else otherOrder.push(i);
    });
    holeOrder = lyricOrder.length
      ? shuffled(otherOrder).concat(lyricOrder)
      : shuffled(s.questions.map(function (it, i) { return i; }));
    s.questions.forEach(function (it) {
      var n = Math.max(1, optionsOf(it.q).length);
      var kinds = shuffled(PIPE_KINDS.map(function (k, i) { return i; }));
      var map = [], order = [];
      for (var i = 0; i < n; i++) { map[i] = kinds[i % kinds.length]; order.push(i); }
      kindMaps[it.q.id] = map;
      trayOrders[it.q.id] = shuffled(order);
    });
  }
  function kindIndexFor(qid, optionIndex) {
    var map = kindMaps[qid];
    return (map && map[optionIndex] != null) ? map[optionIndex]
                                             : optionIndex % PIPE_KINDS.length;
  }

  /* ── scene scaffolding ──────────────────────────────────────────────── */

  function clearScene() {
    var old = picture.querySelector(".flag-scene");
    if (old) old.remove();
  }
  function scene(boardClass) {
    var el = document.createElement("div");
    el.className = "flag-scene";
    el.innerHTML = '<div class="flag-board' + (boardClass ? " " + boardClass : "")
      + '" data-flag-board></div>';
    picture.appendChild(el);
    return el.querySelector("[data-flag-board]");
  }

  /* ── story pages (the walk in, and the way out) ─────────────────────── */

  function showStory(pages, index, kicker, onDone, boardClass) {
    if (index >= pages.length) { onDone(); return; }
    var page = pages[index];
    clearScene();
    var board = scene(boardClass);
    /* a story page only shows a prop when its own words call for one:
       the notebook appears on the page that first mentions it (tucked
       under the pack strap), not from the very first page of the walk */
    if (page.art || page.prop === "notebook") {
      var prop = document.createElement("div");
      prop.className = "pipe-story-prop";
      prop.innerHTML = page.art ? cloth(page.art) : artImg("notebook", "pipe-story-book");
      board.appendChild(prop);
    }
    var last = index === pages.length - 1;
    card.innerHTML = cardHtml(
      kicker + "  ·  " + (index + 1) + " / " + pages.length,
      t(page.title_zh, page.title_en),
      t(page.body_zh, page.body_en),
      (page.fact_zh ? '<p class="flag-fact">' + escapeHtml(t(page.fact_zh, page.fact_en)) + '</p>' : '')
      + '<div class="cave-actions"><button class="btn primary" type="button" data-flag-next>'
      + escapeHtml(last ? t("繼續", "Go on") : t("下一頁", "Next page")) + '</button></div>');
    card.querySelector("[data-flag-next]").addEventListener("click", function () {
      sfx("tap");
      showStory(pages, index + 1, kicker, onDone, boardClass);
    });
  }

  /* ── the pipe machine ──────────────────────────────────────────────── */

  function contextArt(item) {
    var q = item.q, st = item.station;
    if (q.art) return [q.art];
    if (st.id === "stars" || st.id === "raise") return ["flag-national"];
    if (st.id === "flower") return ["flag-regional"];
    if (st.id === "poles") return ["flag-national", "flag-regional"];
    return [];
  }

  function holeHtml(item, index) {
    var q = item.q;
    var placed = placements[q.id];
    var spot = holeSpot(index, stage().questions.length);
    var inner = artImg(placed != null ? FITTED_KINDS[kindIndexFor(q.id, placed)] : "hole",
                       "pipe-hole-img")
      + '<span class="pipe-hole-no">' + (index + 1) + '</span>';
    return '<button type="button" class="pipe-hole' + (placed == null ? "" : " is-full")
      + (wrongIds[q.id] ? " is-wrong" : "") + '"'
      + ' style="left:' + spot.x + "%;top:" + spot.y + "%;width:" + spot.width
      + '%;transform:translate(-50%,-50%)"'
      + ' data-qid="' + q.id + '"'
      + ' aria-label="' + escapeHtml(t("第", "Hole ") + (index + 1) + t("個孔", "")) + '">' + inner + '</button>';
  }

  function buildMachine(message) {
    root.classList.remove("is-howto-open");
    clearScene();
    var board = scene();
    var s = stage();
    var filled = s.questions.filter(function (it) { return placements[it.q.id] != null; }).length;

    var html = '<div class="pipe-machine">'
      + '<button type="button" class="pipe-notebook" data-pipe-notebook>'
      + artImg("notebook", "pipe-notebook-img")
      + '<span>' + escapeHtml(t("筆記", "Notebook")) + '</span></button>'
      + '<div class="pipe-panel"><div class="pipe-panel-inner">'
      + artImg("panel", "pipe-panel-img")
      + '<div class="pipe-holes">'
      + (holeOrder.length === s.questions.length ? holeOrder : s.questions.map(function (it, i) { return i; }))
          .map(function (qi, pos) { return holeHtml(s.questions[qi], pos); }).join("")
      + '</div>'
      /* the start button is a fitting on the panel itself, and it is the
         machine's only signal now: it turns into the red button when a
         pipe is wrong, and glows green when the run is right */
      + '<button type="button" class="pipe-start'
      + (startState ? " is-" + startState : "") + '" data-pipe-start title="'
      + escapeHtml(t("啟動", "Start")) + '">'
      + artImg(startState === "wrong" ? "button-start-red" : "button-start", "pipe-start-img")
      + '<span>' + escapeHtml(t("啟動", "Start")) + '</span></button>'
      + '<span class="pipe-count">' + filled + " / " + s.questions.length + '</span>'
      + '</div></div>'
      + '<span class="pipe-pan-hint">' + escapeHtml(t("左右滑動，可以看整塊控制板", "Swipe sideways to see the whole panel")) + '</span>'
      + '<div class="pipe-note" data-pipe-note hidden></div>'
      + '<div class="pipe-popup" data-pipe-popup hidden></div>'
      + '</div>';
    board.innerHTML = html;

    /* on a phone the panel is enlarged inside its sideways-scrolling
       frame (see styles.css): start with the black board centred, so the
       holes are in view before any swiping */
    var panelFrame = board.querySelector(".pipe-panel");
    if (panelFrame && panelFrame.scrollWidth > panelFrame.clientWidth) {
      panelFrame.scrollLeft = (panelFrame.scrollWidth - panelFrame.clientWidth) / 2;
    }

    board.querySelectorAll(".pipe-hole").forEach(function (hole) {
      hole.addEventListener("click", function () {
        if (!machineLive) return;
        sfx("tap");
        openPopup(hole.getAttribute("data-qid"));
      });
    });
    board.querySelector("[data-pipe-notebook]").addEventListener("click", toggleNote);
    board.querySelector("[data-pipe-start]").addEventListener("click", pressStart);
    machineLive = true;
    renderCard(message);
    /* the how-to button lives in the card renderCard() has just written,
       so it can only be bound now, not before the card exists */
    var howtoBtn = card.querySelector("[data-flag-howto]");
    if (howtoBtn) howtoBtn.addEventListener("click", function () { showHowTo(0); });
    setProgress((stageIndex + 1) + " / " + stages.length + "  " + stageName()
      + "  ·  " + t("旗", "Flag") + " " + stageIndex + "/4");
  }

  function toggleNote() {
    var note = picture.querySelector("[data-pipe-note]");
    if (!note) return;
    if (!note.hidden) { note.hidden = true; return; }
    var s = stage();
    var html = '<div class="pipe-note-head"><strong>'
      + escapeHtml(t("筆記", "Notebook")) + '</strong>'
      + '<button type="button" class="pipe-note-close" data-note-close aria-label="'
      + escapeHtml(t("合上筆記", "Close the notebook")) + '">✕</button></div>';
    s.learn.forEach(function (p) {
      html += '<div class="pipe-note-page">'
        + (p.art ? cloth(p.art, "is-small pipe-note-art") : "")
        + '<h3>' + escapeHtml(t(p.title_zh, p.title_en)) + '</h3>'
        + '<p>' + escapeHtml(t(p.body_zh, p.body_en)) + '</p>'
        + (p.fact_zh ? '<p class="pipe-note-fact">' + escapeHtml(t(p.fact_zh, p.fact_en)) + '</p>' : '')
        + '</div>';
    });
    html += '<p class="pipe-note-foot">' + escapeHtml(t(config.note_zh, config.note_en)) + '</p>';
    note.innerHTML = html;
    note.hidden = false;
    note.querySelector("[data-note-close]").addEventListener("click", function () { note.hidden = true; });
  }

  function renderCard(message) {
    var s = stage();
    var filled = s.questions.filter(function (it) { return placements[it.q.id] != null; }).length;
    card.innerHTML = cardHtml(
      stageName(),
      t("接好這一組喉管", "Connect this run of pipe"),
      message || t("按一個孔打開問題，然後把正確的喉管拖到孔口；全部孔都接好後，按啟動按鈕。",
                   "Tap a hole to open its question, then drag the right pipe onto the socket; fill every hole, then press the start button."),
      '<div class="cave-actions"><span class="pipe-card-count">'
        + escapeHtml(t("已接好", "Connected")) + " " + filled + " / " + s.questions.length + '</span>'
        + '<button type="button" class="btn ghost" data-flag-howto>'
        + escapeHtml(t("遊玩方法", "How to play")) + '</button></div>');
  }

  /* ── the fitting screen that pops up from a hole ───────────────────── */

  var popupTimer = null;

  function holeIndex(qid) {
    var s = stage(), idx = -1;
    var order = holeOrder.length === s.questions.length
      ? holeOrder : s.questions.map(function (it, i) { return i; });
    order.forEach(function (qi, pos) { if (s.questions[qi].q.id === qid) idx = pos; });
    return idx;
  }

  function closePopup() {
    if (popupTimer) { window.clearTimeout(popupTimer); popupTimer = null; }
    var pop = picture.querySelector("[data-pipe-popup]");
    if (pop) { pop.hidden = true; pop.innerHTML = ""; }
    selected = null;
  }

  function openPopup(qid) {
    var pop = picture.querySelector("[data-pipe-popup]");
    var item = findItem(qid);
    if (!pop || !item) return;
    selected = qid;
    var q = item.q;
    var arts = contextArt(item);
    var placed = placements[q.id];

    var pipes = '<div class="pipe-tray">';
    var tray = trayOrders[q.id] && trayOrders[q.id].length === optionsOf(q).length
      ? trayOrders[q.id] : optionsOf(q).map(function (label, i) { return i; });
    tray.forEach(function (i) {
      var label = optionsOf(q)[i];
      pipes += '<button type="button" class="pipe-piece' + (placed === i ? " is-placed" : "")
        + '" data-pipe-option="' + i + '">'
        + artImg(PIPE_KINDS[kindIndexFor(q.id, i)], "pipe-piece-img")
        + '<span class="pipe-piece-word">' + escapeHtml(label) + '</span></button>';
    });
    pipes += '</div>';

    pop.innerHTML =
      '<div class="pipe-popup-head"><span class="pipe-popup-kicker">'
      + escapeHtml(stageName() + "  ·  " + t("第", "Hole ") + (holeIndex(qid) + 1) + t("個孔", ""))
      + '</span><button type="button" class="pipe-popup-close" data-popup-close aria-label="'
      + escapeHtml(t("返回控制板", "Back to the panel")) + '">✕</button></div>'
      + '<h2 class="pipe-popup-q">' + escapeHtml(t(q.prompt_zh, q.prompt_en)) + '</h2>'
      + (arts.length ? '<div class="pipe-context">' + arts.map(function (a) { return cloth(a); }).join("") + '</div>' : '')
      + '<div class="pipe-fit" data-pipe-fit>'
      + (placed != null
        ? artImg(FITTED_KINDS[kindIndexFor(q.id, placed)], "pipe-fit-img")
          + '<span class="pipe-fit-word">' + escapeHtml(optionsOf(q)[placed] || "") + '</span>'
        : artImg("hole", "pipe-fit-socket")
          + '<span class="pipe-fit-hint">' + escapeHtml(t("把喉管拖到這裡", "Drag a pipe here")) + '</span>')
      + '</div>'
      + pipes
      + '<div class="cave-actions">'
      + (placed != null ? '<button type="button" class="btn ghost" data-pipe-remove>'
        + escapeHtml(t("取下這條喉管", "Take this pipe out")) + '</button>' : '')
      + '<button type="button" class="btn ghost" data-popup-close>'
      + escapeHtml(t("返回控制板", "Back to the panel")) + '</button></div>';
    pop.hidden = false;

    pop.querySelectorAll("[data-popup-close]").forEach(function (btn) {
      btn.addEventListener("click", function () { closePopup(); buildMachine(); });
    });
    var fit = pop.querySelector("[data-pipe-fit]");
    fit.addEventListener("dragover", function (ev) { ev.preventDefault(); fit.classList.add("is-over"); });
    fit.addEventListener("dragleave", function () { fit.classList.remove("is-over"); });
    fit.addEventListener("drop", function (ev) {
      ev.preventDefault();
      var raw = ev.dataTransfer.getData("text/plain");
      if (!raw) return;
      var parts = raw.split(":");
      fitPipe(parts[0], parseInt(parts[1], 10));
    });
    /* Pipes are fitted by dragging only. A tap or click on a pipe does
       nothing: the scout has to pick the pipe up, carry it to the socket
       at the top and let go there. The drag is built on pointer events,
       so the same gesture works with a mouse and on a touch screen. */
    pop.querySelectorAll("[data-pipe-option]").forEach(function (btn) {
      var idx = parseInt(btn.getAttribute("data-pipe-option"), 10);
      btn.addEventListener("pointerdown", function (ev) {
        ev.preventDefault();
        var startX = ev.clientX, startY = ev.clientY;
        var ghost = null, dragging = false;
        try { btn.setPointerCapture(ev.pointerId); } catch (e) { /* mouse still reports moves */ }
        function moveGhost(x, y) {
          if (ghost) { ghost.style.left = x + "px"; ghost.style.top = y + "px"; }
          var r = fit.getBoundingClientRect();
          fit.classList.toggle("is-over", x >= r.left && x <= r.right && y >= r.top && y <= r.bottom);
        }
        function onMove(moveEv) {
          if (!dragging) {
            if (Math.abs(moveEv.clientX - startX) + Math.abs(moveEv.clientY - startY) < 8) return;
            dragging = true;
            ghost = btn.cloneNode(true);
            ghost.classList.add("pipe-drag-ghost");
            ghost.style.width = btn.offsetWidth + "px";
            document.body.appendChild(ghost);
            btn.classList.add("is-dragging");
          }
          moveGhost(moveEv.clientX, moveEv.clientY);
        }
        function onUp(upEv) {
          btn.removeEventListener("pointermove", onMove);
          btn.removeEventListener("pointerup", onUp);
          btn.removeEventListener("pointercancel", onUp);
          btn.classList.remove("is-dragging");
          if (ghost) ghost.remove();
          var r = fit.getBoundingClientRect();
          var dropped = dragging && upEv.clientX >= r.left && upEv.clientX <= r.right
            && upEv.clientY >= r.top && upEv.clientY <= r.bottom;
          fit.classList.remove("is-over");
          if (dropped) fitPipe(q.id, idx);
        }
        btn.addEventListener("pointermove", onMove);
        btn.addEventListener("pointerup", onUp);
        btn.addEventListener("pointercancel", onUp);
      });
    });
    var remove = pop.querySelector("[data-pipe-remove]");
    if (remove) remove.addEventListener("click", function () {
      sfx("pop");
      delete placements[q.id];
      delete wrongIds[q.id];
      startState = "";
      buildMachine();
    });
  }

  function fitPipe(qid, optionIndex) {
    if (qid !== selected || isNaN(optionIndex)) return;
    sfx("place");
    placements[qid] = optionIndex;
    delete wrongIds[qid];
    startState = "";
    var pop = picture.querySelector("[data-pipe-popup]");
    var fit = pop ? pop.querySelector("[data-pipe-fit]") : null;
    if (fit) {
      var item = findItem(qid);
      fit.innerHTML = artImg(FITTED_KINDS[kindIndexFor(qid, optionIndex)], "pipe-fit-img")
        + '<span class="pipe-fit-word">' + escapeHtml(optionsOf(item.q)[optionIndex] || "") + '</span>';
      fit.classList.add("is-fitted");
    }
    if (popupTimer) window.clearTimeout(popupTimer);
    /* a short look at the fitted pipe, then back to the panel */
    popupTimer = window.setTimeout(function () { popupTimer = null; buildMachine(); }, 600);
  }

  /* ── start button: red button, green glow, flag up a quarter ───────── */

  function pressStart() {
    if (!machineLive) return;
    var s = stage();
    var missing = s.questions.filter(function (it) { return placements[it.q.id] == null; });
    var startBtn = picture.querySelector(".pipe-start");
    var startImg = picture.querySelector(".pipe-start-img");
    if (missing.length) {
      sfx("tick");
      buildMachine(t("還有 " + missing.length + " 個孔尚未接上喉管。先接好全部喉管，才可以啟動。",
                     missing.length + " hole(s) still empty. Connect every pipe before you press start."));
      openPopup(missing[0].q.id);
      return;
    }
    var allRight = s.questions.every(function (it) { return placements[it.q.id] === it.q.answer; });
    if (!allRight) {
      /* the machine stays live: the wrong pipes are ringed in red on the
         board; tap one, swap its pipe, press start again */
      wrongIds = {};
      s.questions.forEach(function (it) {
        if (placements[it.q.id] !== it.q.answer) wrongIds[it.q.id] = true;
      });
      picture.querySelectorAll(".pipe-hole").forEach(function (hole) {
        hole.classList.toggle("is-wrong", !!wrongIds[hole.getAttribute("data-qid")]);
      });
      startState = "wrong";
      sfx("wrong");
      if (startImg) startImg.src = sourceUrl("button-start-red");
      if (startBtn) startBtn.classList.add("is-wrong");
      card.innerHTML = cardHtml(
        stageName(),
        t("啟動按鈕變成紅色", "The start button turns red"),
        t("機器咳了兩聲便停下來。接錯的喉管已被紅色光圈標示。請打開左邊的筆記核對，再按被圈著的孔打開，把另一條喉管拖到孔口，然後再按啟動按鈕。",
          "The machine coughs twice and stops, and the start button turns red. The wrong pipes are ringed in red light. Check the notebook on the left, tap a ringed hole to open it, drag another pipe onto the socket, then press start again."),
        "");
      return;
    }
    machineLive = false;
    startState = "right";
    sfx("win");
    if (startBtn) startBtn.classList.add("is-right");
    card.innerHTML = cardHtml(
      stageName(),
      t("啟動按鈕發出綠光", "The start button glows green"),
      t("水開始流，繩子開始動。旗要升起來了。", "Water starts to flow and the rope begins to move. The flag is going up."),
      "");
    window.setTimeout(showRaise, 1300);
  }

  function showRaise() {
    clearScene();
    var board = scene();
    var n = stageIndex + 1;
    var wrap = document.createElement("div");
    wrap.className = "pipe-raise";
    wrap.innerHTML = artImg("raise-" + n, "pipe-raise-img")
      + '<span class="pipe-raise-badge">'
      + escapeHtml(t("旗升了", "Flag up")) + " " + n + " / 4</span>";
    board.appendChild(wrap);
    var last = stageIndex >= stages.length - 1;
    setProgress(t("旗", "Flag") + " " + n + "/4");
    card.innerHTML = cardHtml(
      stageName(),
      last ? t("旗升到桿頂", "The flag is at the top")
           : t("旗升了四分之一", "The flag is a quarter higher"),
      last ? t("四組喉管都接對了。旗幟在桿頂展開，谷口通向海邊。",
               "All four pipe runs are right. The flag is open at the top, and the valley mouth leads to the sea.")
           : t("旗幟在桿上又升高了一些，距離桿頂更近。接著要接下一組喉管。",
               "The flag sits higher on the pole, one step nearer the top. The next run of pipe is waiting."),
      '<div class="cave-actions"><button class="btn primary" type="button" data-flag-next>'
        + escapeHtml(last ? t("完成升旗禮", "Finish the ceremony") : t("接下一組喉管", "Fit the next pipe run"))
        + '</button></div>');
    card.querySelector("[data-flag-next]").addEventListener("click", function () {
      sfx(last ? "fanfare" : "unlock");
      if (last) { showEnding(); return; }
      stageIndex += 1;
      prepareStage();
      selected = null;
      showStageNotes();
    });
  }

  /* ── start, ending, submit ─────────────────────────────────────────── */

  function start() {
    /* the walk has begun: the words come off the painting and the card
       below the picture takes over from here; the pole is bare again */
    root.classList.remove("is-start-screen");
    root.classList.remove("is-ending");
    swapSceneArt(startArtUrl);
    startedAt = Date.now();
    placements = {};
    selected = null;
    stageIndex = 0;
    prepareStage();
    howtoShown = false;
    filed = false;
    setProgress(t("溪谷旗桿", "The valley flagpole"));
    showStory(intro, 0, t("遊戲 4", "Game 4"), function () { showStageNotes(); });
  }

  /* the notes come first: read this run's pages from the
     notebook, then the control panel appears and the fitting starts.
     The notebook stays on the panel afterwards for checking. Each page
     is an open spread: the picture on the left page, the words on the
     right. */
  function noteArts(page) {
    if (page.art) return [page.art];
    if (page._station === "poles") return ["flag-national", "flag-regional"];
    if (page._station === "raise") return ["raise-1"];
    return ["flag-national"];
  }

  function showNotesPage(pages, index) {
    if (index >= pages.length) {
      if (stageIndex === 0 && !howtoShown) { howtoShown = true; showHowTo(0); }
      else buildMachine();
      return;
    }
    var page = pages[index];
    clearScene();
    var board = scene();
    var spread = document.createElement("div");
    spread.className = "notebook-open";
    spread.innerHTML =
      '<div class="notebook-page-left">'
      + noteArts(page).map(function (a) {
          return a.indexOf("raise") === 0 ? artImg(a, "notebook-page-img")
                                          : cloth(a, "notebook-page-img");
        }).join("")
      + '</div>'
      + '<div class="notebook-page-right">'
      + '<h3>' + escapeHtml(t(page.title_zh, page.title_en)) + '</h3>'
      + '<p>' + escapeHtml(t(page.body_zh, page.body_en)) + '</p>'
      + (page.fact_zh ? '<p class="notebook-page-fact">' + escapeHtml(t(page.fact_zh, page.fact_en)) + '</p>' : '')
      + '</div>';
    board.appendChild(spread);
    var last = index === pages.length - 1;
    setProgress((stageIndex + 1) + " / " + stages.length + "  " + stageName()
      + "  ·  " + t("旗", "Flag") + " " + stageIndex + "/4");
    card.innerHTML = cardHtml(
      stageName() + "  ·  " + t("筆記", "Notebook")
        + "  ·  " + (index + 1) + " / " + pages.length,
      t("筆記", "Notebook"),
      "",
      '<div class="cave-actions"><button class="btn primary" type="button" data-flag-next>'
      + escapeHtml(last ? t("繼續", "Go on") : t("下一頁", "Next page")) + '</button></div>');
    card.querySelector("[data-flag-next]").addEventListener("click", function () {
      showNotesPage(pages, index + 1);
    });
  }

  /* ── how to play: a step-by-step pop-up, mostly pictures ──────────────
     Shown once, right after the first run's notes (and again whenever the
     scout taps “How to play”). Each step is a little diagram built from
     the game's own paintings, with a short line of words under it. */
  function howToSteps() {
    var panelShot = function (extra) {
      return '<div class="howto-shot">' + artImg("panel", "howto-panel") + extra + '</div>';
    };
    var ring = function (left, top, width) {
      return '<span class="howto-ring" style="left:' + left + '%;top:' + top
        + '%;width:' + width + '%"></span>';
    };
    return [
      { title: t("第 1 步：按一個孔", "Step 1: Tap a hole"),
        body: t("控制板的黑格上，每個孔都是一道問題。按其中一個孔把它打開。",
                "Every hole on the black board is one question. Tap a hole to open it."),
        diagram: panelShot(
          '<span class="howto-hole" style="left:50%;top:53%;width:23%">' + artImg("hole", "howto-hole-img") + '</span>'
          + ring(50, 53, 26)) },
      { title: t("第 2 步：把正確的喉管拖到孔口", "Step 2: Drag the right pipe to the socket"),
        body: t("看清楚問題，想一想筆記中的答案，然後把那個答案的喉管拖到上方的孔口，再放手。只按喉管是不會把它裝上的。每道問題有幾個答案，每個答案都是一條不同的喉管。",
                "Read the question, think of the answer from the notes, then drag that answer's pipe to the socket above and let go. Tapping a pipe on its own will not fit it. Each answer is a different pipe."),
        diagram: '<div class="howto-tray">'
          + ["pipe-straight", "pipe-elbow", "pipe-zigzag", "pipe-wave"].map(function (k, i) {
              return '<span class="howto-piece' + (i === 1 ? " is-picked" : "") + '">'
                + artImg(k, "howto-piece-img") + '<span>' + escapeHtml(t("答案", "Answer")) + " " + "ABCD"[i] + '</span></span>';
            }).join("")
          + '</div><div class="howto-drop">'
          + '<span class="howto-drop-pipe">' + artImg("pipe-elbow", "howto-drop-img") + '</span>'
          + '<span class="howto-drop-hole">' + artImg("hole", "howto-hole-img") + '</span></div>' },
      { title: t("第 3 步：喉管會裝進孔內", "Step 3: The pipe fits into the hole"),
        body: t("拖好之後，整個孔會變成裝好喉管的樣子。按任何一個孔打開它，都可以隨時把另一條喉管拖進去，換走原本那一條。",
                "Once the pipe is dragged in, the whole hole picture changes to the fitted pipe. Tap any hole to open it and drag a different pipe in to swap it."),
        diagram: '<div class="howto-swap">'
          + artImg("hole", "howto-swap-a") + artImg("hole-pipe-wave", "howto-swap-b") + '</div>' },
      { title: t("第 4 步：全部接好後，按啟動按鈕", "Step 4: Fill every hole, then press Start"),
        body: t("所有孔都接好喉管後，按控制板右邊的啟動按鈕。若在未接好時按下，機器會提醒你還有多少個孔未接。",
                "When every hole has a pipe, press the start button on the right of the panel. If a hole is still empty, the machine will tell you."),
        diagram: panelShot(
          '<span class="howto-start">' + artImg("button-start", "howto-start-img") + '</span>'
          + ring(90, 57, 15)
          + '<span class="howto-count">9 / 9</span>') },
      { title: t("第 5 步：留意啟動按鈕", "Step 5: Watch the start button"),
        body: t("啟動按鈕變紅，表示有喉管接錯：接錯的孔會被紅光圈著，按開它，再把另一條喉管拖到孔口，然後再按啟動按鈕。啟動按鈕發出綠光，表示全部正確，旗會升起四分之一。四組喉管都接對，旗便升到桿頂。",
                "If the start button turns red, a pipe is wrong: the wrong holes are ringed in red — tap one to open it, drag another pipe onto the socket, then press start again. If it glows green, all is correct and the flag rises a quarter. Finish all four runs to raise it to the top."),
        diagram: '<div class="howto-lights">'
          + '<span class="howto-light-case">' + artImg("button-start-red", "howto-button-img")
          + '<span class="howto-wrong">' + artImg("hole-pipe-elbow", "howto-hole-img") + '</span></span>'
          + '<span class="howto-arrow">→</span>'
          + '<span class="howto-light-case">' + artImg("button-start", "howto-button-img is-glowing")
          + '<span class="howto-raise">' + artImg("raise-1", "howto-raise-img") + '</span></span></div>' }
    ];
  }

  function showHowTo(step) {
    var steps = howToSteps();
    step = Math.max(0, Math.min(step, steps.length - 1));
    var item = steps[step];
    /* while the how-to pop-up is up, the card below the picture is hidden
       altogether: its leftover words and its own next-page button would
       only repeat what the pop-up already says and does. buildMachine()
       takes the class away again when the scout returns to the panel. */
    root.classList.add("is-howto-open");
    clearScene();
    var board = scene();
    var last = step === steps.length - 1;
    var dots = steps.map(function (_, i) {
      return '<span class="howto-dot' + (i === step ? " is-on" : "") + '"></span>';
    }).join("");
    var wrap = document.createElement("div");
    wrap.className = "howto";
    wrap.innerHTML =
      '<div class="howto-head"><span class="howto-kicker">'
      + escapeHtml(t("遊玩方法", "How to play")) + "  ·  " + (step + 1) + " / " + steps.length
      + '</span><button type="button" class="howto-skip" data-howto-skip>'
      + escapeHtml(t("跳過", "Skip")) + '</button></div>'
      + '<div class="howto-diagram">' + item.diagram + '</div>'
      + '<h2 class="howto-title">' + escapeHtml(item.title) + '</h2>'
      + '<p class="howto-body">' + escapeHtml(item.body) + '</p>'
      + '<div class="howto-dots">' + dots + '</div>'
      + '<div class="cave-actions howto-actions">'
      + (step > 0 ? '<button type="button" class="btn ghost" data-howto-back>'
          + escapeHtml(t("上一步", "Back")) + '</button>' : "")
      + '<button type="button" class="btn primary" data-howto-next>'
      + escapeHtml(last ? t("開始接喉管", "Start fitting pipes") : t("下一步", "Next step"))
      + '</button></div>';
    board.appendChild(wrap);
    setProgress(t("遊玩方法", "How to play") + "  ·  " + (step + 1) + " / " + steps.length);
    wrap.querySelector("[data-howto-skip]").addEventListener("click", function () { buildMachine(); });
    wrap.querySelector("[data-howto-next]").addEventListener("click", function () {
      if (last) buildMachine(); else showHowTo(step + 1);
    });
    var back = wrap.querySelector("[data-howto-back]");
    if (back) back.addEventListener("click", function () { showHowTo(step - 1); });
  }

  function showStageNotes() {
    var s = stage();
    var pages = s ? s.learn : [];
    if (!pages.length) { buildMachine(); return; }
    showNotesPage(pages, 0);
  }

  function showEnding() {
    /* the ceremony is done, so the painting itself changes: the flag is
       up at the top of the pole now (the fourth raise picture), and it
       stays up behind every ending page */
    root.classList.add("is-ending");
    swapSceneArt(sourceUrl("raise-4"));
    clearScene();
    setProgress(t("升旗完畢", "Ceremony over"));
    showStory(ending, 0, t("溪谷旗桿", "The valley flagpole"), function () {
      var next = config.next_game;
      card.innerHTML = cardHtml(
        t("通向海邊", "Toward the sea"),
        t("旗已升到桿頂", "The flag is at the top"),
        t("第 7 至 10 項完成。臨海山崗還在前面，木筏在沙灘上等你。",
          "Items 7 to 10 are done. The seaward bluff is still ahead, and the raft is waiting on the beach."),
        '<div class="cave-actions">'
          + (next ? '<a class="btn primary" href="' + escapeHtml(next.url) + '">'
            + escapeHtml(t("去下一關：", "On to the next game: ") + t(next.name_zh, next.name_en)) + '</a>' : "")
          + (badgeLink ? '<a class="btn' + (next ? " ghost" : " primary") + '" href="' + badgeLink.getAttribute("href") + '">'
            + escapeHtml(t("回到會員章", "Back to the badge")) + '</a>' : "")
          + '</div>'
          + '<p class="flag-note">' + escapeHtml(t(config.note_zh, config.note_en)) + '</p>');
      submit();
    });
  }

  function submit() {
    if (filed || !config.submit_url) return;
    filed = true;
    var body = new URLSearchParams();
    Object.keys(placements).forEach(function (id) { body.append(id, String(placements[id])); });
    body.append("elapsed_ms", String(startedAt ? Math.max(0, Date.now() - startedAt) : 0));
    fetch(config.submit_url, {
      method: "POST",
      headers: { "X-Requested-With": "fetch", "Accept": "application/json",
                 "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString()
    }).then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
      .then(function (res) {
        if (res.ok || !card) return;
        var note = document.createElement("p");
        note.className = "flag-why";
        note.textContent = t(res.data.message_zh, res.data.message_en);
        card.appendChild(note);
        filed = false;
      }).catch(function () { filed = false; });
  }

  /* the start button exists twice before the walk — on the painting and
     in the (hidden) card below — so bind them all */
  root.querySelectorAll("[data-flag-go]").forEach(function (go) {
    go.addEventListener("click", start);
  });
})();
