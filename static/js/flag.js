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

  function slotHtml(item) {
    var q = item.q;
    var placed = placements[q.id];
    var inner;
    if (placed == null) {
      inner = artImg("socket", "pipe-socket-img")
        + '<span class="pipe-slot-hint">' + escapeHtml(t("空位", "Empty")) + '</span>';
    } else {
      inner = artImg(PIPE_KINDS[placed % PIPE_KINDS.length], "pipe-in-slot")
        + '<span class="pipe-slot-word">' + escapeHtml(optionsOf(q)[placed] || "") + '</span>';
    }
    return '<button type="button" class="pipe-slot' + (placed == null ? "" : " is-full")
      + (selected === q.id ? " is-asking" : "") + '" data-qid="' + q.id + '"'
      + ' aria-label="' + escapeHtml(t(item.q.prompt_zh, item.q.prompt_en)) + '">' + inner + '</button>';
  }

  function buildMachine(message) {
    clearScene();
    var board = scene();
    var s = stage();
    var filled = s.questions.filter(function (it) { return placements[it.q.id] != null; }).length;

    var html = '<div class="pipe-machine">'
      + '<div class="pipe-question" data-pipe-question hidden></div>'
      + '<button type="button" class="pipe-notebook" data-pipe-notebook>'
      + artImg("notebook", "pipe-notebook-img")
      + '<span>' + escapeHtml(t("上一隊的筆記", "The last patrol's notebook")) + '</span></button>'
      + '<div class="pipe-panel">'
      + artImg("panel", "pipe-panel-img")
      + '<div class="pipe-slots" data-pipe-slots>'
      + s.questions.map(slotHtml).join("")
      + '</div></div>'
      + '<div class="pipe-controls">'
      + artImg("light-off", "pipe-light")
      + '<button type="button" class="pipe-start" data-pipe-start>'
      + artImg("button-start", "pipe-start-img")
      + '<span>' + escapeHtml(t("開機", "Start")) + '</span></button>'
      + '<span class="pipe-count">' + filled + " / " + s.questions.length + '</span>'
      + '</div>'
      + '<div class="pipe-note" data-pipe-note hidden></div>'
      + '</div>';
    board.innerHTML = html;

    board.querySelectorAll(".pipe-slot").forEach(function (slot) {
      slot.addEventListener("click", function () {
        if (!machineLive) return;
        selectSlot(slot.getAttribute("data-qid"));
      });
      slot.addEventListener("dragover", function (ev) { ev.preventDefault(); });
      slot.addEventListener("drop", function (ev) {
        ev.preventDefault();
        if (!machineLive) return;
        var raw = ev.dataTransfer.getData("text/plain");
        if (!raw) return;
        var parts = raw.split(":");
        selectSlot(slot.getAttribute("data-qid"), true);
        placePipe(parts[0], parseInt(parts[1], 10));
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

  function selectSlot(qid, keepCard) {
    selected = qid;
    picture.querySelectorAll(".pipe-slot").forEach(function (slot) {
      slot.classList.toggle("is-asking", slot.getAttribute("data-qid") === qid);
    });
    if (!keepCard) renderCard();
    showQuestionTop();
  }

  function showQuestionTop() {
    var bar = picture.querySelector("[data-pipe-question]");
    if (!bar) return;
    var item = selected ? findItem(selected) : null;
    if (!item) { bar.hidden = true; bar.textContent = ""; return; }
    bar.textContent = t(item.q.prompt_zh, item.q.prompt_en);
    bar.hidden = false;
  }

  function placePipe(qid, optionIndex) {
    if (qid !== selected || isNaN(optionIndex)) return;
    placements[qid] = optionIndex;
    buildMachine();
    selectSlot(qid, true);
    renderCard();
  }

  function renderCard(message) {
    var s = stage();
    var item = selected ? findItem(selected) : null;
    var filled = s.questions.filter(function (it) { return placements[it.q.id] != null; }).length;

    if (!item) {
      card.innerHTML = cardHtml(
        stageName(),
        t("駁好這一組喉", "Connect this run of pipe"),
        message || t("控制板上有 " + s.questions.length + " 個空位。點一個空位，在上面讀題目，再把合適的喉拖入去。全部駁好之後，按右邊的開機掣。左邊的筆記有齊你要用的資料。",
                     "There are " + s.questions.length + " empty gaps on the control panel. Tap a gap, read the question at the top, and drag the right pipe into it. When every gap is filled, press the start button on the right. The notebook on the left holds everything you need."),
        '<div class="cave-actions"><span class="pipe-card-count">'
          + escapeHtml(t("已駁好", "Connected")) + " " + filled + " / " + s.questions.length + '</span></div>');
      showQuestionTop();
      return;
    }

    var q = item.q;
    var arts = contextArt(item);
    var placed = placements[q.id];
    var pipes = '<div class="pipe-tray">';
    optionsOf(q).forEach(function (label, i) {
      pipes += '<button type="button" class="pipe-piece' + (placed === i ? " is-placed" : "")
        + '" draggable="true" data-pipe-option="' + i + '">'
        + artImg(PIPE_KINDS[i % PIPE_KINDS.length], "pipe-piece-img")
        + '<span class="pipe-piece-word">' + escapeHtml(label) + '</span></button>';
    });
    pipes += '</div>';

    card.innerHTML = cardHtml(
      stageName() + "  ·  " + escapeHtml(t("題目在上面", "Question at the top")),
      t(q.prompt_zh, q.prompt_en),
      message || t("把寫著答案的喉拖入發光的空位；用手提裝置也可以先點喉，再點空位。",
                   "Drag the pipe carrying the answer into the glowing gap. On a touch screen you can tap the pipe, then tap the gap."),
      (arts.length ? '<div class="pipe-context">' + arts.map(function (a) { return cloth(a); }).join("") + '</div>' : '')
      + pipes
      + (placed != null
        ? '<div class="cave-actions"><button type="button" class="btn ghost" data-pipe-remove>'
          + escapeHtml(t("拆走這段喉", "Take this pipe out")) + '</button></div>' : ''));

    card.querySelectorAll("[data-pipe-option]").forEach(function (btn) {
      var idx = parseInt(btn.getAttribute("data-pipe-option"), 10);
      btn.addEventListener("dragstart", function (ev) {
        ev.dataTransfer.setData("text/plain", q.id + ":" + idx);
      });
      btn.addEventListener("click", function () { placePipe(q.id, idx); });
    });
    var remove = card.querySelector("[data-pipe-remove]");
    if (remove) remove.addEventListener("click", function () {
      delete placements[q.id];
      buildMachine();
      selectSlot(q.id, true);
      renderCard();
    });
    showQuestionTop();
  }

  /* ── start button: red light, green light, flag up a quarter ───────── */

  function pressStart() {
    if (!machineLive) return;
    var s = stage();
    var missing = s.questions.filter(function (it) { return placements[it.q.id] == null; });
    var light = picture.querySelector(".pipe-light");
    if (missing.length) {
      selected = missing[0].q.id;
      buildMachine(t("仲有 " + missing.length + " 個空位未駁喉。先駁好全部，才可以開機。",
                     missing.length + " gap(s) still empty. Connect every pipe before you press start."));
      selectSlot(selected, true);
      renderCard(t("仲有 " + missing.length + " 個空位未駁喉。先駁好全部，才可以開機。",
                   missing.length + " gap(s) still empty. Connect every pipe before you press start."));
      return;
    }
    var allRight = s.questions.every(function (it) { return placements[it.q.id] === it.q.answer; });
    if (!allRight) {
      /* the machine stays live: tap any gap, swap its pipe, press start again */
      if (light) light.src = sourceUrl("light-red");
      card.innerHTML = cardHtml(
        stageName(),
        t("紅燈亮起", "The red light glows"),
        t("機器咳了兩聲，停下來。這一組喉裡面，有駁錯的地方。打開左邊的筆記對一對，點開空位就可以換另一段喉。再按一次開機掣。",
          "The machine coughs twice and stops. Somewhere in this run a pipe is wrong. Check the notebook on the left, tap a gap to swap its pipe, then press start again."),
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
