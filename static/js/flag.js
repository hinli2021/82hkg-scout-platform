/* 溪谷旗桿 — game 4 of 會員章 (items 7 to 10).
   The island story continues here: down from the ridge, a notebook by the
   stream teaches the flags, then the scout performs the ceremony. Finishing
   the ceremony passes. The 30 answers still come from the leader's paper;
   this file only tells the story and plays the actions. The server re-checks
   every answer on submit. */
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

  var answers = {};
  var stationIndex = -1;
  var asking = null;
  var startedAt = 0;
  var filed = false;

  function sourceUrl(name) {
    var img = root.querySelector('[data-flag-source="' + name + '"]');
    return img ? img.getAttribute("src") : "";
  }

  function cloth(name, extra) {
    return '<img class="flag-cloth ' + (extra || "") + '" src="' + sourceUrl(name) + '" alt="">';
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

  function bookButton(station) {
    if (!station || !(station.learn || []).length) return "";
    return '<button type="button" class="flag-book" data-flag-book>'
      + escapeHtml(t("翻開筆記", "Open the notebook")) + '</button>';
  }

  function bindBook(station) {
    var btn = card.querySelector("[data-flag-book]");
    if (!btn) return;
    btn.addEventListener("click", function () { showLearn(station, 0, true); });
  }

  /* ── story pages ──────────────────────────────────────────────────────── */

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

  function notebook(board) {
    var book = document.createElement("div");
    book.className = "flag-notebook";
    book.setAttribute("aria-hidden", "true");
    board.appendChild(book);
  }

  function paintPage(board, page) {
    if (page.scene === "poles") {
      buildPoles(board);
      var tray = board.querySelector("[data-flag-tray]");
      if (tray) tray.remove();
      ["left", "right"].forEach(function (side, i) {
        var slot = board.querySelector('[data-slot="' + side + '"]');
        if (!slot) return;
        slot.innerHTML = cloth(i === 0 ? "flag-national" : "flag-regional", "is-fly");
        slot.classList.add("is-full");
      });
    } else if (page.scene === "raise") {
      board.innerHTML = '<div class="flag-rope" aria-hidden="true"></div>'
        + '<div class="flag-hoist">' + cloth("flag-national", "is-fly") + '</div>';
    } else if (page.scene === "score") {
      var score = document.createElement("div");
      score.className = "flag-score";
      score.innerHTML = "<p>&#9834; &#9834; &#9834;</p>";
      board.appendChild(score);
    } else if (page.art) {
      var wrap = document.createElement("div");
      wrap.className = "flag-big";
      wrap.innerHTML = cloth(page.art);
      if (page.part) {
        var hot = document.createElement("span");
        hot.className = "flag-hot is-asking";
        hot.setAttribute("data-part", page.part);
        wrap.appendChild(hot);
      }
      board.appendChild(wrap);
    }
    notebook(board);
  }

  function showStory(pages, index, kicker, onDone) {
    if (index >= pages.length) { onDone(); return; }
    var page = pages[index];
    clearScene();
    var board = scene();
    paintPage(board, page);
    var revealed = !page.fact_zh;
    function render() {
      var last = index === pages.length - 1;
      card.innerHTML = cardHtml(
        kicker + "  ·  " + (index + 1) + " / " + pages.length,
        t(page.title_zh, page.title_en),
        t(page.body_zh, page.body_en),
        (revealed && page.fact_zh
          ? '<p class="flag-fact">' + escapeHtml(t(page.fact_zh, page.fact_en)) + '</p>' : '')
        + '<div class="cave-actions">'
        + (revealed
          ? '<button class="btn primary" type="button" data-flag-next>'
            + escapeHtml(last ? t("繼續", "Go on") : t("下一頁", "Next page")) + '</button>'
          : '<p class="flag-why">' + escapeHtml(t("點一點溪谷，筆記會把這一行讀出來。",
              "Tap the valley. The notebook will read this line.")) + '</p>')
        + '</div>');
      var next = card.querySelector("[data-flag-next]");
      if (next) next.addEventListener("click", function () { showStory(pages, index + 1, kicker, onDone); });
    }
    render();
    if (!revealed) board.addEventListener("click", function () {
      if (revealed) return;
      revealed = true;
      render();
    });
  }

  function showLearn(station, index, review) {
    var pages = station.learn || [];
    if (!pages.length || index >= pages.length) {
      runStation(station);
      return;
    }
    var page = pages[index];
    clearScene();
    var board = scene();
    paintPage(board, page);
    var revealed = !page.fact_zh;
    var last = index === pages.length - 1;
    function render() {
      var label = review
        ? t("回到升旗禮", "Back to the ceremony")
        : t("現在換我做", "Now I do it");
      card.innerHTML = cardHtml(
        t("筆記", "The notebook") + "  ·  " + (index + 1) + " / " + pages.length,
        t(page.title_zh, page.title_en),
        t(page.body_zh, page.body_en),
        (revealed && page.fact_zh
          ? '<p class="flag-fact">' + escapeHtml(t(page.fact_zh, page.fact_en)) + '</p>' : '')
        + '<div class="cave-actions">'
        + (revealed
          ? '<button class="btn primary" type="button" data-flag-next>'
            + escapeHtml(last ? label : t("下一頁", "Next page")) + '</button>'
          : '<p class="flag-why">' + escapeHtml(page.part
            ? t("點一點上面發光的地方，筆記會把這一行讀出來。", "Tap the glowing part above. The notebook will read this line.")
            : t("點一點溪谷，筆記會把這一行讀出來。", "Tap the valley. The notebook will read this line.")) + '</p>')
        + '</div>');
      var next = card.querySelector("[data-flag-next]");
      if (next) next.addEventListener("click", function () { showLearn(station, index + 1, review); });
    }
    render();
    if (!revealed) board.addEventListener("click", function () {
      if (revealed) return;
      revealed = true;
      render();
    });
    setProgress((stationIndex + 1) + " / " + stations.length + "  " + t(station.name_zh, station.name_en));
  }

  /* ── play ─────────────────────────────────────────────────────────────── */

  function optionsHtml(q) {
    var opts = lang === "en" ? q.options_en : q.options_zh;
    var html = '<div class="flag-options" data-flag-options>';
    (opts || []).forEach(function (label, i) {
      html += '<button type="button" class="flag-option" data-flag-option="' + i + '">'
        + escapeHtml(label) + '</button>';
    });
    return html + '</div>';
  }

  function ask(q, kicker, locked) {
    asking = q;
    var station = stations[stationIndex];
    var extra = locked
      ? '<p class="flag-why">' + escapeHtml(t("先把兩面旗都拖上旗桿。", "Drag both flags onto the poles first.")) + '</p>'
      : optionsHtml(q);
    card.innerHTML = cardHtml(kicker, t(q.prompt_zh, q.prompt_en), "", extra + bookButton(station));
    card.querySelectorAll("[data-flag-option]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        choose(q, parseInt(btn.getAttribute("data-flag-option"), 10), btn);
      });
    });
    bindBook(station);
  }

  function polesReady() {
    var slots = picture.querySelectorAll("[data-slot]");
    return slots.length === 2 && picture.querySelectorAll("[data-slot].is-full").length === 2;
  }

  function choose(q, index, btn) {
    if (answers[q.id] != null) return;
    if (index !== q.answer) {
      btn.classList.add("is-wrong");
      btn.disabled = true;
      var echo = card.querySelector("[data-flag-echo]");
      if (!echo) {
        echo = document.createElement("p");
        echo.className = "flag-why";
        echo.setAttribute("data-flag-echo", "");
        card.appendChild(echo);
      }
      echo.textContent = t(q.echo_zh, q.echo_en) || t("筆記不是這樣寫的。再看一次。",
        "That is not what the notebook says. Look again.");
      return;
    }
    answers[q.id] = index;
    btn.classList.add("is-right");
    card.querySelectorAll("[data-flag-option]").forEach(function (b) { b.disabled = true; });
    markAsked(q);
    window.setTimeout(advance, 450);
  }

  function markAsked(q) {
    var el = picture.querySelector('[data-qid="' + q.id + '"]');
    if (!el) return;
    el.classList.remove("is-asking");
    el.classList.add("is-done");
    if (el.classList.contains("flag-gap")) {
      var word = (lang === "en" ? q.options_en : q.options_zh)[q.answer];
      el.textContent = word;
    }
    var tick = el.querySelector(".flag-tick");
    if (tick) tick.textContent = "✔";
  }

  function start() {
    startedAt = Date.now();
    answers = {};
    filed = false;
    stations.forEach(function (s) { s._bridged = false; });
    setProgress(t("溪谷旗桿", "The valley flagpole"));
    showStory(intro, 0, t("遊戲 4", "Game 4"), function () {
      stationIndex = 0;
      enterStation();
    });
  }

  function enterStation() {
    if (stationIndex >= stations.length) { showEnding(); return; }
    var station = stations[stationIndex];
    station._bridged = false;
    setProgress((stationIndex + 1) + " / " + stations.length + "  " + t(station.name_zh, station.name_en));
    showLearn(station, 0, false);
  }

  function runStation(station) {
    clearScene();
    buildScene(station);
    if (!station._bridged) {
      station._bridged = true;
      card.innerHTML = cardHtml(
        t(station.name_zh, station.name_en),
        t(station.lead_zh, station.lead_en),
        "",
        '<div class="cave-actions"><button class="btn primary" type="button" data-flag-play>'
          + escapeHtml(t("我來做", "I'll do it")) + '</button></div>'
          + bookButton(station));
      card.querySelector("[data-flag-play]").addEventListener("click", function () { openNext(station); });
      bindBook(station);
      return;
    }
    openNext(station);
  }

  function openNext(station) {
    var pending = (station.questions || []).filter(function (q) { return answers[q.id] == null; });
    if (!pending.length) { nextStation(); return; }
    var q = pending[0];
    picture.querySelectorAll(".is-asking").forEach(function (el) { el.classList.remove("is-asking"); });
    var el = picture.querySelector('[data-qid="' + q.id + '"]');
    if (el) el.classList.add("is-asking");
    var label = t(station.name_zh, station.name_en) + "  ·  "
      + ((station.questions.length - pending.length) + 1) + "/" + station.questions.length;
    if (station.kind === "poles") {
      if (!picture.querySelector("[data-flag-tray]")) layPoles();
      ask(q, label, !polesReady());
      return;
    }
    if (station.kind === "raise" && !picture.querySelector(".flag-hoist.is-up")) {
      ask(q, label, false);
      var options = card.querySelector("[data-flag-options]");
      if (options) options.hidden = true;
      var note = document.createElement("p");
      note.className = "flag-why";
      note.textContent = t("按住國旗，把它拉到旗桿頂。", "Hold the flag and drag it to the top of the pole.");
      card.appendChild(note);
      return;
    }
    ask(q, label);
  }

  function advance() {
    var station = stations[stationIndex];
    if (!station) return;
    openNext(station);
  }

  function nextStation() {
    stationIndex += 1;
    enterStation();
  }

  function showEnding() {
    clearScene();
    setProgress(t("升旗完畢", "Ceremony over"));
    showStory(ending, 0, t("溪谷旗桿", "The valley flagpole"), function () {
      card.innerHTML = cardHtml(
        t("通向海邊", "Toward the sea"),
        t("旗已升到桿頂", "The flag is at the top"),
        t("第 7 至 10 項完成。臨海山崗還在前面，木筏在沙灘上等你。",
          "Items 7 to 10 are done. The seaward bluff is still ahead, and the raft is waiting on the beach."),
        '<div class="cave-actions">'
          + (badgeLink ? '<a class="btn primary" href="' + badgeLink.getAttribute("href") + '">'
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
    Object.keys(answers).forEach(function (id) { body.append(id, String(answers[id])); });
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

  /* ── scenes ───────────────────────────────────────────────────────────── */

  function buildScene(station) {
    var board = scene();
    if (station.kind === "tap" && station.id === "look") buildGallery(board, station);
    else if (station.kind === "parts") buildParts(board, station);
    else if (station.kind === "poles") buildPoles(board);
    else if (station.kind === "sing") buildScore(board, station);
    else if (station.kind === "raise") buildRaise(board);
    else if (station.kind === "tap") buildScore(board, station);
  }

  function buildGallery(board, station) {
    var wrap = document.createElement("div");
    wrap.className = "flag-gallery";
    station.questions.forEach(function (q) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "flag-tile" + (answers[q.id] != null ? " is-done" : "");
      btn.setAttribute("data-qid", q.id);
      btn.innerHTML = cloth(q.art) + '<span class="flag-tick">' + (answers[q.id] != null ? "✔" : "") + '</span>';
      btn.addEventListener("click", function () {
        if (answers[q.id] != null) return;
        picture.querySelectorAll(".is-asking").forEach(function (el) { el.classList.remove("is-asking"); });
        btn.classList.add("is-asking");
        ask(q, t(station.name_zh, station.name_en));
      });
      wrap.appendChild(btn);
    });
    board.appendChild(wrap);
  }

  function buildParts(board, station) {
    var wrap = document.createElement("div");
    wrap.className = "flag-big";
    wrap.innerHTML = cloth(station.id === "flower" ? "flag-regional" : "flag-national");
    station.questions.forEach(function (q) {
      var hot = document.createElement("button");
      hot.type = "button";
      hot.className = "flag-hot" + (answers[q.id] != null ? " is-done" : "");
      hot.setAttribute("data-part", q.part);
      hot.setAttribute("data-qid", q.id);
      hot.addEventListener("click", function () {
        if (answers[q.id] != null) return;
        picture.querySelectorAll(".is-asking").forEach(function (el) { el.classList.remove("is-asking"); });
        hot.classList.add("is-asking");
        ask(q, t(station.name_zh, station.name_en));
      });
      wrap.appendChild(hot);
    });
    board.appendChild(wrap);
  }

  function buildPoles(board) {
    var wrap = document.createElement("div");
    wrap.className = "flag-poles";
    wrap.innerHTML =
      '<div class="flag-pole" data-pole="left"><span class="flag-knob"></span><span class="flag-base"></span><span class="flag-slot" data-slot="left"></span></div>'
      + '<div class="flag-pole" data-pole="right"><span class="flag-knob"></span><span class="flag-base"></span><span class="flag-slot" data-slot="right"></span></div>'
      + '<div class="flag-tray" data-flag-tray></div>';
    board.appendChild(wrap);
  }

  function layPoles() {
    var tray = picture.querySelector("[data-flag-tray]");
    if (!tray || tray.childElementCount) return;
    ["left", "right"].forEach(function (side) {
      var slot = picture.querySelector('[data-slot="' + side + '"]');
      if (slot && !slot.classList.contains("is-full")) slot.innerHTML = "";
    });
    [{ id: "national", art: "flag-national" }, { id: "regional", art: "flag-regional" }].forEach(function (f) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "flag-drag";
      btn.setAttribute("draggable", "true");
      btn.setAttribute("data-flag-id", f.id);
      btn.innerHTML = cloth(f.art);
      btn.addEventListener("dragstart", function (ev) { ev.dataTransfer.setData("text/plain", f.id); });
      btn.addEventListener("click", function () { btn.classList.toggle("is-held"); });
      tray.appendChild(btn);
    });
    picture.querySelectorAll("[data-slot]").forEach(function (slot) {
      slot.addEventListener("dragover", function (ev) { ev.preventDefault(); });
      slot.addEventListener("drop", function (ev) {
        ev.preventDefault();
        hang(slot, ev.dataTransfer.getData("text/plain"));
      });
      slot.addEventListener("click", function () {
        var held = picture.querySelector(".flag-drag.is-held");
        if (held) hang(slot, held.getAttribute("data-flag-id"));
      });
    });
  }

  function hang(slot, flagId) {
    if (!flagId || slot.classList.contains("is-full")) return;
    slot.innerHTML = cloth(flagId === "national" ? "flag-national" : "flag-regional", "is-fly");
    slot.classList.add("is-full");
    var btn = picture.querySelector('[data-flag-id="' + flagId + '"]');
    if (btn) btn.classList.add("is-used");
    if (polesReady() && asking) ask(asking, t("兩支旗桿", "Two flagpoles"));
  }

  function buildScore(board, station) {
    var wrap = document.createElement("div");
    wrap.className = "flag-score";
    var lines = lang === "en" ? (station.lines_en || []) : (station.lines_zh || []);
    if (!lines.length) lines = station.questions.map(function (q) { return "♪ {" + q.id + "}"; });
    lines.forEach(function (line) {
      var p = document.createElement("p");
      p.innerHTML = escapeHtml(line).replace(/\{(q\d+)\}/g, function (_, id) {
        var q = (station.questions || []).filter(function (qq) { return qq.id === id; })[0];
        if (!q) return "";
        var filled = answers[id] != null;
        var word = filled ? (lang === "en" ? q.options_en : q.options_zh)[q.answer] : "____";
        return '<button type="button" class="flag-gap' + (filled ? " is-done" : "") + '" data-qid="' + id + '">'
          + escapeHtml(filled ? word : "____") + '</button>';
      });
      wrap.appendChild(p);
    });
    wrap.querySelectorAll(".flag-gap").forEach(function (gap) {
      gap.addEventListener("click", function () {
        var id = gap.getAttribute("data-qid");
        var q = (station.questions || []).filter(function (qq) { return qq.id === id; })[0];
        if (!q || answers[q.id] != null) return;
        picture.querySelectorAll(".is-asking").forEach(function (el) { el.classList.remove("is-asking"); });
        gap.classList.add("is-asking");
        ask(q, t(station.name_zh, station.name_en));
      });
    });
    board.appendChild(wrap);
  }

  function buildRaise(board) {
    board.innerHTML = '<div class="flag-rope" aria-hidden="true"></div>'
      + '<button type="button" class="flag-hoist" data-flag-hoist>' + cloth("flag-national", "is-fly") + '</button>';
    var hoist = board.querySelector("[data-flag-hoist]");
    function lift(clientY) {
      var rect = board.getBoundingClientRect();
      var ratio = 1 - (clientY - rect.top) / rect.height;
      ratio = Math.max(0.05, Math.min(0.9, ratio));
      hoist.style.bottom = (ratio * 100) + "%";
      if (ratio > 0.78 && !hoist.classList.contains("is-up")) {
        hoist.classList.add("is-up");
        hoist.style.bottom = "84%";
        var station = stations[stationIndex];
        if (station) openNext(station);
      }
    }
    hoist.addEventListener("pointerdown", function (ev) { hoist.setPointerCapture(ev.pointerId); });
    hoist.addEventListener("pointermove", function (ev) {
      if (hoist.hasPointerCapture && hoist.hasPointerCapture(ev.pointerId)) lift(ev.clientY);
    });
    board.addEventListener("click", function (ev) { lift(ev.clientY); });
  }

  var go = root.querySelector("[data-flag-go]");
  if (go) go.addEventListener("click", start);
})();
