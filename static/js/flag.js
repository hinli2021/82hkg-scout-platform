/* 溪谷旗桿 — game 4 of 會員章 (items 7 to 10).
   The flagpole by the stream is worked by an old pipe machine. Four runs of
   pipe have to be connected before the flag will rise: pick a gap on the
   control panel, read the question at the top, drag the right pipe into the
   gap, then press the start button on the right. A red light means a pipe is
   wrong somewhere; a green light raises the flag another quarter. The last
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

  var stations = config.stations || [];
  var intro = config.intro || [];
  var ending = config.ending || [];
  var card = root.querySelector("[data-flag-card]");
  var progress = root.querySelector("[data-flag-progress]");
  var picture = root.querySelector(".cave-picture");
  var badgeLink = root.querySelector('[data-flag-link="badge"]');

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
      (st.learn || []).forEach(function (p) { pages.push(p); });
    });
    return { def: def, questions: qs, learn: pages };
  }).filter(function (s) { return s.questions.length; });

  var placements = {};       /* qid -> chosen option index, checked only at start-up */
  var holeOrder = [];        /* shuffled hole order for the stage being fitted */
  var kindMaps = {};         /* qid -> pipe kind per option, shuffled each stage */
  var trayOrders = {};       /* qid -> order the pipes are offered in, shuffled */
  var wrongIds = {};         /* qids the start button has proved wrong this run */
  var selected = null;        /* qid of the gap being fitted */
  var stageIndex = 0;
  var startedAt = 0;
  var filed = false;
  var machineLive = false;    /* false while a light is showing / the flag is rising */

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
    kindMaps = {}; trayOrders = {}; wrongIds = {};
    if (!s) { holeOrder = []; return; }
    holeOrder = shuffled(s.questions.map(function (it, i) { return i; }));
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
  function scene() {
    var el = document.createElement("div");
    el.className = "flag-scene";
    el.innerHTML = '<div class="flag-board" data-flag-board></div>';
    picture.appendChild(el);
    return el.querySelector("[data-flag-board]");
  }

  /* ── story pages (the walk in, and the way out) ─────────────────────── */

  function showStory(pages, index, kicker, onDone) {
    if (index >= pages.length) { onDone(); return; }
    var page = pages[index];
    clearScene();
    var board = scene();
    var prop = document.createElement("div");
    prop.className = "pipe-story-prop";
    prop.innerHTML = page.art ? cloth(page.art) : artImg("notebook", "pipe-story-book");
    board.appendChild(prop);
    var last = index === pages.length - 1;
    card.innerHTML = cardHtml(
      kicker + "  ·  " + (index + 1) + " / " + pages.length,
      t(page.title_zh, page.title_en),
      t(page.body_zh, page.body_en),
      (page.fact_zh ? '<p class="flag-fact">' + escapeHtml(t(page.fact_zh, page.fact_en)) + '</p>' : '')
      + '<div class="cave-actions"><button class="btn primary" type="button" data-flag-next>'
      + escapeHtml(last ? t("繼續", "Go on") : t("下一頁", "Next page")) + '</button></div>');
    card.querySelector("[data-flag-next]").addEventListener("click", function () {
      showStory(pages, index + 1, kicker, onDone);
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
    if (placed != null) {
      inner += '<span class="pipe-hole-word">' + escapeHtml(optionsOf(q)[placed] || "") + '</span>';
    }
    return '<button type="button" class="pipe-hole' + (placed == null ? "" : " is-full")
      + (wrongIds[q.id] ? " is-wrong" : "") + '"'
      + ' style="left:' + spot.x + "%;top:" + spot.y + "%;width:" + spot.width
      + '%;transform:translate(-50%,-50%)"'
      + ' data-qid="' + q.id + '"'
      + ' aria-label="' + escapeHtml(t("第", "Hole ") + (index + 1) + t("個窿", "")) + '">' + inner + '</button>';
  }

  function buildMachine(message) {
    clearScene();
    var board = scene();
    var s = stage();
    var filled = s.questions.filter(function (it) { return placements[it.q.id] != null; }).length;

    var html = '<div class="pipe-machine">'
      + '<button type="button" class="pipe-notebook" data-pipe-notebook>'
      + artImg("notebook", "pipe-notebook-img")
      + '<span>' + escapeHtml(t("上一隊的筆記", "The last patrol's notebook")) + '</span></button>'
      + '<div class="pipe-panel">'
      + artImg("panel", "pipe-panel-img")
      + '<div class="pipe-holes">'
      + (holeOrder.length === s.questions.length ? holeOrder : s.questions.map(function (it, i) { return i; }))
          .map(function (qi, pos) { return holeHtml(s.questions[qi], pos); }).join("")
      + '</div>'
      /* the start button and the signal light are part of the panel now:
         their paintings had their backgrounds removed, so they sit on the
         wood and brass like fittings, not like separate cards */
      + artImg("light-off", "pipe-light")
      + '<button type="button" class="pipe-start" data-pipe-start title="'
      + escapeHtml(t("開機", "Start")) + '">'
      + artImg("button-start", "pipe-start-img")
      + '<span>' + escapeHtml(t("開機", "Start")) + '</span></button>'
      + '<span class="pipe-count">' + filled + " / " + s.questions.length + '</span>'
      + '</div>'
      + '<div class="pipe-note" data-pipe-note hidden></div>'
      + '<div class="pipe-popup" data-pipe-popup hidden></div>'
      + '</div>';
    board.innerHTML = html;

    board.querySelectorAll(".pipe-hole").forEach(function (hole) {
      hole.addEventListener("click", function () {
        if (!machineLive) return;
        openPopup(hole.getAttribute("data-qid"));
      });
    });
    board.querySelector("[data-pipe-notebook]").addEventListener("click", toggleNote);
    board.querySelector("[data-pipe-start]").addEventListener("click", pressStart);
    machineLive = true;
    renderCard(message);
    setProgress((stageIndex + 1) + " / " + stages.length + "  " + stageName()
      + "  ·  " + t("旗", "Flag") + " " + stageIndex + "/4");
  }

  function toggleNote() {
    var note = picture.querySelector("[data-pipe-note]");
    if (!note) return;
    if (!note.hidden) { note.hidden = true; return; }
    var s = stage();
    var html = '<div class="pipe-note-head"><strong>'
      + escapeHtml(t("上一隊的筆記", "The last patrol's notebook")) + '</strong>'
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
      t("駁好這一組喉", "Connect this run of pipe"),
      message || t("控制板上的黑格有 " + s.questions.length + " 個窿，整齊排好，每個窿對應一題。點開一個窿，駁喉畫面就會彈出來；把喉拖入接口，畫面會自己返回控制板，你會看到那段喉駁在窿上。全部駁好之後，按控制板右邊的開機掣。左邊的筆記有齊你要用的資料。",
                   "There are " + s.questions.length + " holes arranged neatly on the black board of the control panel, one for each question. Tap a hole and the fitting screen pops up; drag a pipe into the socket and the screen returns to the panel, with your pipe on the hole. When every hole is filled, press the start button on the panel. The notebook on the left holds everything you need."),
      '<div class="cave-actions"><span class="pipe-card-count">'
        + escapeHtml(t("已駁好", "Connected")) + " " + filled + " / " + s.questions.length + '</span></div>');
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
        + '" draggable="true" data-pipe-option="' + i + '">'
        + artImg(PIPE_KINDS[kindIndexFor(q.id, i)], "pipe-piece-img")
        + '<span class="pipe-piece-word">' + escapeHtml(label) + '</span></button>';
    });
    pipes += '</div>';

    pop.innerHTML =
      '<div class="pipe-popup-head"><span class="pipe-popup-kicker">'
      + escapeHtml(stageName() + "  ·  " + t("第", "Hole ") + (holeIndex(qid) + 1) + t("個窿", ""))
      + '</span><button type="button" class="pipe-popup-close" data-popup-close aria-label="'
      + escapeHtml(t("返回控制板", "Back to the panel")) + '">✕</button></div>'
      + '<h2 class="pipe-popup-q">' + escapeHtml(t(q.prompt_zh, q.prompt_en)) + '</h2>'
      + (arts.length ? '<div class="pipe-context">' + arts.map(function (a) { return cloth(a); }).join("") + '</div>' : '')
      + '<div class="pipe-fit" data-pipe-fit>'
      + (placed != null
        ? artImg(FITTED_KINDS[kindIndexFor(q.id, placed)], "pipe-fit-img")
          + '<span class="pipe-fit-word">' + escapeHtml(optionsOf(q)[placed] || "") + '</span>'
        : artImg("hole", "pipe-fit-socket")
          + '<span class="pipe-fit-hint">' + escapeHtml(t("把喉拖來這裡", "Drag a pipe here")) + '</span>')
      + '</div>'
      + pipes
      + '<div class="cave-actions">'
      + (placed != null ? '<button type="button" class="btn ghost" data-pipe-remove>'
        + escapeHtml(t("拆走這段喉", "Take this pipe out")) + '</button>' : '')
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
    pop.querySelectorAll("[data-pipe-option]").forEach(function (btn) {
      var idx = parseInt(btn.getAttribute("data-pipe-option"), 10);
      btn.addEventListener("dragstart", function (ev) {
        ev.dataTransfer.setData("text/plain", q.id + ":" + idx);
      });
      btn.addEventListener("click", function () { fitPipe(q.id, idx); });
    });
    var remove = pop.querySelector("[data-pipe-remove]");
    if (remove) remove.addEventListener("click", function () {
      delete placements[q.id];
      delete wrongIds[q.id];
      buildMachine();
    });
  }

  function fitPipe(qid, optionIndex) {
    if (qid !== selected || isNaN(optionIndex)) return;
    placements[qid] = optionIndex;
    delete wrongIds[qid];
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

  /* ── start button: red light, green light, flag up a quarter ───────── */

  function pressStart() {
    if (!machineLive) return;
    var s = stage();
    var missing = s.questions.filter(function (it) { return placements[it.q.id] == null; });
    var light = picture.querySelector(".pipe-light");
    if (missing.length) {
      buildMachine(t("仲有 " + missing.length + " 個窿未駁喉。先駁好全部，才可以開機。",
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
      if (light) light.src = sourceUrl("light-red");
      card.innerHTML = cardHtml(
        stageName(),
        t("紅燈亮起", "The red light glows"),
        t("機器咳了兩聲，停下來。駁錯的喉已經用紅光圈住。打開左邊的筆記對一對，點開圈住的窿就可以換另一段喉。再按一次開機掣。",
          "The machine coughs twice and stops. The wrong pipes are ringed in red light. Check the notebook on the left, tap a ringed hole to swap its pipe, then press start again."),
        "");
      return;
    }
    machineLive = false;
    if (light) light.src = sourceUrl("light-green");
    card.innerHTML = cardHtml(
      stageName(),
      t("綠燈亮起", "The green light glows"),
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
      last ? t("四組喉都駁對了。旗在桿頂展開，谷口通向海邊。",
               "All four pipe runs are right. The flag is open at the top, and the valley mouth leads to the sea.")
           : t("旗在桿上又高了一截，離桿頂又近一步。下一組喉在等你。",
               "The flag sits higher on the pole, one step nearer the top. The next run of pipe is waiting."),
      '<div class="cave-actions"><button class="btn primary" type="button" data-flag-next>'
        + escapeHtml(last ? t("完成升旗禮", "Finish the ceremony") : t("駁下一組喉", "Fit the next pipe run"))
        + '</button></div>');
    card.querySelector("[data-flag-next]").addEventListener("click", function () {
      if (last) { showEnding(); return; }
      stageIndex += 1;
      prepareStage();
      selected = null;
      buildMachine();
    });
  }

  /* ── start, ending, submit ─────────────────────────────────────────── */

  function start() {
    startedAt = Date.now();
    placements = {};
    selected = null;
    stageIndex = 0;
    prepareStage();
    filed = false;
    setProgress(t("溪谷旗桿", "The valley flagpole"));
    showStory(intro, 0, t("遊戲 4", "Game 4"), function () { buildMachine(); });
  }

  function showEnding() {
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

  var go = root.querySelector("[data-flag-go]");
  if (go) go.addEventListener("click", start);
})();
