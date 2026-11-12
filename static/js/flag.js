/* 溪谷旗桿 — game 4 of 會員章 (items 7 to 10).
   One ceremony by the stream. The 30 questions and their answers come from the
   leader's paper (content/member-badge/ceremony-bank.json); this file only
   adds the actions: tap a picture, tap a glowing part, drag a flag onto its
   pole, fill a gap in the anthem, drag the flag up the pole. No question is
   invented here, and no answer is decided here — the server re-checks every
   one on submit. */
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
  var passMark = config.pass_mark || 24;
  var card = root.querySelector("[data-flag-card]");
  var progress = root.querySelector("[data-flag-progress]");
  var picture = root.querySelector(".cave-picture");
  var badgeLink = root.querySelector('[data-flag-link="badge"]');

  var answers = {};          // question id -> chosen index
  var stationIndex = -1;
  var asking = null;         // the question currently open
  var startedAt = 0;

  var ART = {
    "flag-national": "flag-national",
    "flag-regional": "flag-regional",
    "emblem-national": "emblem-national",
    "emblem-regional": "emblem-regional"
  };

  function sourceUrl(name) {
    var img = root.querySelector('[data-flag-source="' + name + '"]');
    return img ? img.getAttribute("src") : "";
  }

  function cloth(name, extra) {
    return '<img class="flag-cloth ' + (extra || "") + '" src="' + sourceUrl(name) + '" alt="">';
  }

  function setProgress(text) { if (progress) progress.textContent = text; }

  function cardHtml(kicker, title, body, extra) {
    return '<span class="cave-kicker">' + escapeHtml(kicker) + '</span>'
      + '<h1 class="cave-title">' + escapeHtml(title) + '</h1>'
      + (body ? '<p class="cave-line">' + escapeHtml(body) + '</p>' : '')
      + (extra || "");
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function optionsHtml(q) {
    var opts = lang === "en" ? q.options_en : q.options_zh;
    var html = '<div class="flag-options" data-flag-options>';
    (opts || []).forEach(function (label, i) {
      html += '<button type="button" class="flag-option" data-flag-option="' + i + '">'
        + escapeHtml(label) + '</button>';
    });
    html += '</div>';
    if (q.why_zh) {
      html += '<p class="flag-why" data-flag-why hidden>' + escapeHtml(t(q.why_zh, q.why_en)) + '</p>';
    }
    return html;
  }

  function ask(q, kicker, locked) {
    asking = q;
    var extra = locked
      ? '<p class="flag-why">' + escapeHtml(t("先把兩面旗都拖上旗桿。", "Drag both flags onto the poles first.")) + '</p>'
      : optionsHtml(q);
    card.innerHTML = cardHtml(
      kicker,
      t(q.prompt_zh, q.prompt_en),
      "",
      extra);
    card.querySelectorAll("[data-flag-option]").forEach(function (btn) {
      btn.addEventListener("click", function () { choose(q, parseInt(btn.getAttribute("data-flag-option"), 10), btn); });
    });
  }

  /* a poles question stays locked until both flags are actually hanging */
  function polesReady() {
    var slots = picture.querySelectorAll("[data-slot]");
    return slots.length === 2 && picture.querySelectorAll("[data-slot].is-full").length === 2;
  }

  function choose(q, index, btn) {
    if (answers[q.id] != null) return;          // one answer, then it locks
    answers[q.id] = index;
    var right = index === q.answer;
    btn.classList.add(right ? "is-right" : "is-wrong");
    card.querySelectorAll("[data-flag-option]").forEach(function (b) { b.disabled = true; });
    var why = card.querySelector("[data-flag-why]");
    if (why && !right) why.hidden = false;
    markAsked(q);
    window.setTimeout(advance, right ? 550 : 1100);
  }

  function markAsked(q) {
    var el = picture.querySelector('[data-qid="' + q.id + '"]');
    if (el) { el.classList.remove("is-asking"); el.classList.add("is-done"); }
  }

  /* ── stations ─────────────────────────────────────────────────────────── */

  function showIntro() {
    setProgress(t("溪谷旗桿", "The valley flagpole"));
  }

  function start() {
    startedAt = Date.now();
    stationIndex = 0;
    enterStation();
  }

  function enterStation() {
    if (stationIndex >= stations.length) { finish(); return; }
    var station = stations[stationIndex];
    clearScene();
    setProgress((stationIndex + 1) + " / " + stations.length + "  " + t(station.name_zh, station.name_en));
    card.innerHTML = cardHtml(
      t(station.name_zh, station.name_en),
      t(station.lead_zh, station.lead_en),
      "",
      '<div class="cave-actions"><button class="btn primary" type="button" data-flag-begin>'
        + escapeHtml(t("開始", "Begin")) + '</button></div>');
    card.querySelector("[data-flag-begin]").addEventListener("click", function () { runStation(station); });
  }

  function runStation(station) {
    buildScene(station);
    var pending = (station.questions || []).filter(function (q) { return answers[q.id] == null; });
    if (!pending.length) { nextStation(); return; }
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
      layPoles(station, q);
      ask(q, label, !polesReady());
      return;
    }
    if (station.kind === "raise" && !picture.querySelector(".flag-hoist.is-up")) {
      ask(q, label, false);
      card.querySelector("[data-flag-options]").hidden = true;
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

  /* ── scene building ───────────────────────────────────────────────────── */

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

  function buildScene(station) {
    var board = scene();
    if (station.kind === "tap" && station.id === "look") buildGallery(board, station);
    else if (station.kind === "parts") buildParts(board, station);
    else if (station.kind === "poles") buildPoles(board);
    else if (station.kind === "sing") buildScore(board, station);
    else if (station.kind === "raise") buildRaise(board, station);
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
    var art = station.id === "flower" ? "flag-regional" : "flag-national";
    wrap.innerHTML = cloth(art);
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

  function layPoles(station, q) {
    var tray = picture.querySelector("[data-flag-tray]");
    if (!tray) return;
    tray.innerHTML = "";
    ["left", "right"].forEach(function (side) {
      var slot = picture.querySelector('[data-slot="' + side + '"]');
      if (slot) { slot.innerHTML = ""; slot.classList.remove("is-full"); }
    });
    var flags = [
      { id: "national", art: "flag-national" },
      { id: "regional", art: "flag-regional" }
    ];
    flags.forEach(function (f) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "flag-drag";
      btn.setAttribute("draggable", "true");
      btn.setAttribute("data-flag-id", f.id);
      btn.innerHTML = cloth(f.art);
      btn.addEventListener("dragstart", function (ev) {
        ev.dataTransfer.setData("text/plain", f.id);
      });
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
        var held = tray.querySelector(".flag-drag.is-held");
        if (held) hang(slot, held.getAttribute("data-flag-id"));
      });
    });
  }

  function hang(slot, flagId) {
    if (!flagId || slot.classList.contains("is-full")) return;
    var art = flagId === "national" ? "flag-national" : "flag-regional";
    slot.innerHTML = cloth(art, "is-fly");
    slot.classList.add("is-full");
    var btn = picture.querySelector('[data-flag-id="' + flagId + '"]');
    if (btn) btn.classList.add("is-used");
    // both flags up: the statement can be answered now
    if (polesReady() && asking) ask(asking, t("兩支旗桿", "Two flagpoles"));
  }

  function buildScore(board, station) {
    var wrap = document.createElement("div");
    wrap.className = "flag-score";
    var lines = lang === "en" ? (station.lines_en || []) : (station.lines_zh || []);
    if (!lines.length) {
      // the anthem-history station has no lyric lines: one tappable note per question
      lines = station.questions.map(function (q) { return "♪ {" + q.id + "}"; });
    }
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

  function buildRaise(board, station) {
    board.innerHTML =
      '<div class="flag-rope" aria-hidden="true"></div>'
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
        if (station) openNext(station);     // the flag is up: the questions unlock
      }
    }
    hoist.addEventListener("pointerdown", function (ev) {
      hoist.setPointerCapture(ev.pointerId);
    });
    hoist.addEventListener("pointermove", function (ev) {
      if (hoist.hasPointerCapture && hoist.hasPointerCapture(ev.pointerId)) lift(ev.clientY);
    });
    board.addEventListener("click", function (ev) { lift(ev.clientY); });
  }

  /* ── the end ──────────────────────────────────────────────────────────── */

  function finish() {
    clearScene();
    var total = stations.reduce(function (n, s) { return n + (s.questions || []).length; }, 0);
    var score = stations.reduce(function (n, s) {
      return n + (s.questions || []).filter(function (q) { return answers[q.id] === q.answer; }).length;
    }, 0);
    var passed = score >= passMark;
    var elapsed = startedAt ? Math.max(0, Date.now() - startedAt) : 0;
    setProgress(score + " / " + total);
    card.innerHTML = cardHtml(
      t("升旗完畢", "Ceremony over"),
      passed
        ? t("旗已升到桿頂", "The flag is at the top")
        : t("旗升到一半", "The flag stopped halfway"),
      passed
        ? t("你答對 " + score + "／" + total + " 題，達到 " + passMark + " 分。第 7 至 10 項完成，去找領袖考核。",
            "You got " + score + " of " + total + ", past the " + passMark + " mark. Items 7 to 10 are done — see your leader.")
        : t("你答對 " + score + "／" + total + " 題，未到 " + passMark + " 分。再升一次旗。",
            "You got " + score + " of " + total + ", short of " + passMark + ". Raise the flag again."),
      '<div class="cave-actions">'
        + (passed ? "" : '<button class="btn primary" type="button" data-flag-again>' + escapeHtml(t("再升一次", "Raise it again")) + '</button>')
        + (badgeLink ? '<a class="btn" href="' + badgeLink.getAttribute("href") + '">' + escapeHtml(t("回到會員章", "Back to the badge")) + '</a>' : "")
        + '</div>'
        + '<p class="flag-note">' + escapeHtml(t(config.note_zh, config.note_en)) + '</p>');
    var again = card.querySelector("[data-flag-again]");
    if (again) again.addEventListener("click", function () { answers = {}; start(); });
    if (passed && config.submit_url) submit(score, elapsed);
  }

  function submit(score, elapsed) {
    var body = new URLSearchParams();
    Object.keys(answers).forEach(function (id) { body.append(id, String(answers[id])); });
    body.append("elapsed_ms", String(elapsed));
    body.append("score", String(score));
    fetch(config.submit_url, {
      method: "POST",
      headers: { "X-Requested-With": "fetch", "Accept": "application/json",
                 "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString()
    }).then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
      .then(function (res) {
      var data = res.data;
      if (data && !res.ok && card) {
        var note = document.createElement("p");
        note.className = "flag-why";
        note.textContent = t(data.message_zh, data.message_en);
        card.appendChild(note);
      }
    }).catch(function () { /* the score is on screen either way; the scout can retry */ });
  }

  /* ── boot ─────────────────────────────────────────────────────────────── */

  var go = root.querySelector("[data-flag-go]");
  if (go) go.addEventListener("click", start);
  else showIntro();
})();
