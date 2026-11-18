/* 遊戲 5：小隊名冊卡 — flip the patrol's member cards, then seat everyone
   on the raft: each station states its requirement, worked out from the
   cards. The browser never holds the seating plan: it sends the choices
   back, and the server re-grades them. */
(function () {
  "use strict";
  /* the scene rides on the root element, the same way the cave, the drill
     ground and the flagpole carry theirs */
  var root = document.querySelector("[data-patrol-root]");
  var data = {};
  try { data = JSON.parse(root.getAttribute("data-patrol-config") || "{}"); } catch (e) { data = {}; }
  var lang = document.documentElement.lang === "en" ? "en" : "zh";
  var $ = function (sel) { return document.querySelector(sel); };
  var esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  var state = { scene: 0, flipped: new Set(), flippedAll: false };

  function progress(step) {
    var at = step === "cards" ? 0 : step === "stage1" ? 1 : 2;
    var dots = "";
    for (var i = 0; i < 3; i++) dots += '<i' + (i === at ? ' class="on"' : "") + "></i>";
    return '<span class="pat-dots">' + dots + "</span>";
  }

  function renderProgress(step) {
    $("[data-pat-progress]").innerHTML = (step === "cards"
      ? (lang === "en" ? "Know your patrol" : "認識小隊成員")
      : step === "stage1"
        ? (lang === "en" ? "Stage 1: find your patrol" : "第一階段：找出小隊成員")
        : (lang === "en" ? "Stage 2: seat the raft" : "第二階段：安排木筏崗位"))
      + progress(step);
  }

  function factRow(label, text, fallback) {
    return "<li><b>" + esc(label) + "</b><span>"
      + esc(text || fallback) + "</span></li>";
  }

  function cardBack(member) {
    var rows = '<ul class="pat-facts">'
      + factRow(lang === "en" ? "Interests" : "興趣", member.interests,
                lang === "en" ? "Not written yet" : "尚未填寫")
      + factRow(lang === "en" ? "Strength" : "強項", member.strength,
                lang === "en" ? "Not written yet" : "尚未填寫")
      + factRow(lang === "en" ? "Scout experience" : "童軍經驗", member.experience,
                lang === "en" ? "Not written yet" : "尚未填寫")
      + factRow(lang === "en" ? "Something to share" : "想和大家分享的事", member.share,
                lang === "en" ? "Not written yet" : "尚未填寫")
      + factRow(lang === "en" ? "Scout number" : "童軍編號", member.scout_no,
                lang === "en" ? "Not set yet" : "尚未編配")
      + "</ul>";
    if (!member.complete) {
      rows += '<p class="pat-muted">'
        + esc(lang === "en"
            ? "This member has not finished their profile yet — know them by their name, avatar, scout number and position."
            : "這位成員尚未填寫全部資料——可以靠姓名、頭像、童軍編號和職位辨認他。")
        + "</p>";
    }
    return rows;
  }

  function memberCard(member) {
    var name = lang === "en" ? member.name_en : member.name_zh;
    var position = (lang === "en" ? member.position_en : member.position_zh)
      || (lang === "en" ? "No position yet" : "暫時沒有職位");
    var patrol = lang === "en" ? data.patrol_en : data.patrol_zh;
    var contact = member.is_contact
      ? '<span class="pat-badge">📨 ' + esc(lang === "en" ? "Patrol contact" : "小隊聯絡") + "</span>" : "";
    var contactHow = "";
    if (member.is_contact) {
      contactHow = '<p class="pat-contact">'
        + esc(lang === "en"
            ? "How to reach them: find them in person at a meeting, or ask your leader to pass a message on."
            : "聯絡方法：在集會時親自找他，或請領袖幫忙聯絡。")
        + "</p>";
    }
    /* the same profile card the member sees on their own page: portrait,
       the NO. / patrol / position strip, and their own words below. It is
       drawn from the live profile, so an edit updates it at once. */
    var portrait = member.card_image_url
      ? '<img class="pat-pimg" src="' + esc(member.card_image_url) + '" alt="">'
      : '<span class="pat-portrait"><span class="pat-avatar">'
        + esc(member.avatar || "🦊") + "</span></span>";
    return '<button type="button" class="pat-card" data-member="' + esc(member.id) + '">'
      + '<span class="pat-card-inner">'
      + '<span class="pat-face pat-front">'
        + '<span class="pat-phead"><strong>' + esc(name) + '</strong>'
        + '<span class="pat-ppos">' + esc(position) + "</span></span>"
        + portrait
        + '<span class="pat-pinfo"><span>NO. ' + esc(member.scout_no || "—") + "</span>"
        + "<span>" + esc(patrol || "") + "</span><span>" + esc(position) + "</span></span>"
        + '<span class="pat-pmove"><b>' + esc(lang === "en" ? "Interests" : "興趣") + "</b>"
        + esc(member.interests || (lang === "en" ? "Not written yet" : "尚未填寫")) + "</span>"
        + contact
        + '<span class="pat-fliphint">' + esc(lang === "en" ? "Tap to flip" : "按一下翻卡") + "</span>"
      + "</span>"
      + '<span class="pat-face pat-back">' + cardBack(member) + contactHow + "</span>"
      + "</span></button>";
  }

  function showCard(index) {
    var deck = $("[data-pat-deck]");
    var member = (data.members || [])[index];
    if (!member) return;
    state.scene = index;
    deck.innerHTML = '<div class="pat-scene-wrap">'
      + memberCard(member)
      + '<p class="pat-count">' + (index + 1) + " / " + (data.members || []).length + "</p>"
      + "</div>";
    var card = deck.querySelector(".pat-card");
    card.addEventListener("click", function () {
      card.classList.toggle("is-flipped");
      if (!state.flipped.has(member.id)) {
        state.flipped.add(member.id);
        if (state.flipped.size === (data.members || []).length) state.flippedAll = true;
        sync();
      }
    });
    sync();
  }

  function sync() {
    var members = data.members || [];
    $("[data-pat-prev]").disabled = state.scene <= 0;
    $("[data-pat-next]").disabled = state.scene >= members.length - 1;
    var start = $("[data-pat-start]");
    var hint = $("[data-pat-hint]");
    if (!data.playable) {
      start.disabled = true;
      hint.textContent = lang === "en"
        ? "Your patrol has very few members, so the game cannot start yet. Ask your leader to add your patrol mates first."
        : "小隊的成員太少，暫時未能開始遊戲。請先向領袖查詢，請領袖把隊員加入平台。";
      return;
    }
    if (state.flipped.size >= members.length && members.length) {
      hint.textContent = lang === "en"
        ? "You have flipped every card. Stage 1 will be much easier now."
        : "所有成員卡都已翻開。第一階段會容易得多。";
    } else {
      hint.textContent = (lang === "en" ? "Flipped: " : "已翻開：")
        + state.flipped.size + " / " + members.length
        + (lang === "en" ? ". Flip every card first and stage 1 will be much easier."
                          : "。先翻開每一張卡，第一階段會容易得多。");
    }
  }

  var picked = {};   // stage 1: scout id -> true

  function renderBoard() {
    var board = $("[data-pat-board]");
    board.innerHTML = (data.roster_board || []).map(function (s) {
      return '<button type="button" class="pat-name' + (picked[s.id] ? " is-picked" : "")
        + '" data-name="' + esc(s.id) + '">'
        + (picked[s.id] ? "✓ " : "") + esc(lang === "en" ? s.name_en : s.name_zh) + "</button>";
    }).join("");
    board.querySelectorAll("[data-name]").forEach(function (node) {
      node.addEventListener("click", function () {
        var id = node.getAttribute("data-name");
        if (picked[id]) { delete picked[id]; } else { picked[id] = true; }
        renderBoard();
      });
    });
    var count = Object.keys(picked).length;
    $("[data-pat-boardhint]").textContent = (lang === "en" ? "Picked: " : "已選：")
      + count + (lang === "en" ? ". Your patrol has " : " 人。你的小隊共有 ")
      + (data.roster_size || 0) + (lang === "en" ? " members, including you." : " 位成員（包括你自己）。");
  }

  function startStage1() {
    /* the story picture belongs to the opening only: once the game is
       under way the words panel takes the whole window */
    root.classList.add("is-playing");
    $("[data-pat-cards]").hidden = true;
    $("[data-pat-intro]").hidden = true;
    $("[data-pat-stage1]").hidden = false;
    renderProgress("stage1");
    var wrap = $(".cave-card-wrap");
    if (wrap) wrap.scrollTop = 0;
    renderBoard();
  }

  function checkStage1() {
    var result = $("[data-pat-stage1result]");
    result.textContent = lang === "en" ? "Checking…" : "正在核實……";
    var fd = new FormData();
    fd.set("run_key", data.run_key || "");
    Object.keys(picked).forEach(function (id) { fd.append("members", id); });
    fetch(data.stage1_url, {
      method: "POST",
      headers: { "X-Requested-With": "fetch" },
      body: fd
    }).then(function (r) { return r.json().then(function (j) { return { r: r, j: j }; }); })
      .then(function (out) {
        var j = out.j;
        if (j.ok && j.passed) {
          result.className = "pat-result pat-ok";
          result.textContent = "🎉 " + (lang === "en" ? j.message_en : j.message_zh);
          startStage2();
        } else {
          result.className = "pat-result pat-bad";
          result.textContent = "❌ " + (lang === "en" ? j.message_en : j.message_zh);
        }
      }).catch(function () {
        result.className = "pat-result pat-bad";
        result.textContent = lang === "en"
          ? "The connection failed. Please try again."
          : "連線失敗。請再試一次。";
      });
  }

  function startStage2() {
    $("[data-pat-cards]").hidden = true;
    $("[data-pat-intro]").hidden = true;
    $("[data-pat-stage1]").hidden = true;
    $("[data-pat-quiz]").hidden = false;
    renderProgress("stage2");
    $("[data-pat-start]").hidden = true;
    /* the words panel scrolls inside the stage, like the other games */
    var wrap = $(".cave-card-wrap");
    if (wrap) wrap.scrollTop = 0;
    renderRaft();
  }

  /* ── the raft: tap a member on the shore, then a station ──────────────
     Each station states its requirement; the seating is worked out from
     the member cards. The browser holds no plan — the choices are sent
     back and the server re-grades them. */
  var assign = {};       // seat id -> member id
  var selected = null;   // member id waiting on the shore

  function memberName(m) { return lang === "en" ? m.name_en : m.name_zh; }

  function memberById(id) {
    var found = null;
    (data.members || []).forEach(function (m) { if (m.id === id) found = m; });
    return found;
  }

  function crewMembers() {
    var crew = (data.crew && data.crew.length) ? data.crew
      : (data.members || []).map(function (m) { return m.id; });
    return (data.members || []).filter(function (m) { return crew.indexOf(m.id) >= 0; });
  }

  function renderRaft() {
    var raftBox = $("[data-pat-raft]");
    var pool = $("[data-pat-pool]");
    raftBox.innerHTML = (data.raft || []).map(function (seat) {
      var occ = assign[seat.id] ? memberById(assign[seat.id]) : null;
      return '<div class="pat-seat' + (occ ? " is-filled" : "") + '" data-seat="'
        + esc(seat.id) + '" role="button" tabindex="0">'
        + '<b class="pat-role">' + esc(lang === "en" ? seat.role_en : seat.role_zh) + "</b>"
        + '<span class="pat-duty">' + esc(lang === "en" ? seat.duty_en : seat.duty_zh) + "</span>"
        + '<p class="pat-criterion">' + esc(lang === "en" ? seat.criterion_en : seat.criterion_zh) + "</p>"
        + '<span class="pat-occupant">' + (occ
            ? esc(occ.avatar || "🦊") + " " + esc(memberName(occ))
            : esc(lang === "en" ? "— empty —" : "— 尚未安排 —")) + "</span></div>";
    }).join("");
    pool.innerHTML = crewMembers().map(function (m) {
      var placed = Object.keys(assign).some(function (k) { return assign[k] === m.id; });
      return '<button type="button" class="pat-chip' + (selected === m.id ? " is-selected" : "")
        + (placed ? " is-placed" : "") + '" data-member="' + esc(m.id) + '">'
        + '<span aria-hidden="true">' + esc(m.avatar || "🦊") + "</span> "
        + esc(memberName(m)) + "</button>";
    }).join("");
    var hint = $("[data-pat-poolhint]");
    var placedCount = Object.keys(assign).length;
    var total = (data.raft || []).length;
    if (selected) {
      var sm = memberById(selected);
      hint.textContent = lang === "en"
        ? "Seating " + memberName(sm) + ": tap a station on the raft."
        : "正在安排 " + memberName(sm) + "：點木筏上的崗位。";
    } else if (total && placedCount >= total) {
      hint.textContent = lang === "en"
        ? "Everyone is seated and the raft is ready. Press “Board the raft”."
        : "全部成員已安排好，木筏準備好了。按「登上木筏」出發。";
    } else {
      hint.textContent = (lang === "en" ? "Seated: " : "已安排：") + placedCount + " / " + total
        + (lang === "en" ? ". Tap a member on the shore, then a station on the raft."
                          : "。先點岸邊的一位成員，再點木筏上的崗位。");
    }
    raftBox.querySelectorAll("[data-seat]").forEach(function (node) {
      node.addEventListener("click", function () { seatTap(node.getAttribute("data-seat")); });
      node.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); seatTap(node.getAttribute("data-seat")); }
      });
    });
    pool.querySelectorAll("[data-member]").forEach(function (node) {
      node.addEventListener("click", function () {
        var id = node.getAttribute("data-member");
        selected = (selected === id) ? null : id;
        renderRaft();
      });
    });
  }

  function seatTap(seatId) {
    if (selected) {
      Object.keys(assign).forEach(function (k) { if (assign[k] === selected) delete assign[k]; });
      assign[seatId] = selected;
      selected = null;
    } else if (assign[seatId]) {
      delete assign[seatId];
    }
    renderRaft();
  }

  function submit(e) {
    e.preventDefault();
    var form = $("[data-pat-form]");
    var result = $("[data-pat-result]");
    var startTime = performance.now();
    result.textContent = lang === "en" ? "Marking…" : "正在核實……";
    var fd = new FormData(form);
    fd.set("run_key", data.run_key || "");
    fd.set("elapsed_ms", Math.max(0, Math.round(performance.now() - startTime)).toString());
    (data.raft || []).forEach(function (seat) {
      fd.set(seat.id, assign[seat.id] || "");
    });
    fetch(data.submit_url, {
      method: "POST",
      headers: { "X-Requested-With": "fetch" },
      body: fd
    }).then(function (r) { return r.json().then(function (j) { return { r: r, j: j }; }); })
      .then(function (out) {
        var j = out.j;
        if (j.ok && j.passed) {
          state.flippedAll = true;
          result.className = "pat-result pat-ok";
          result.textContent = (lang === "en" ? "🎉 " + j.message_en : "🎉 " + j.message_zh);
          var done = $("[data-pat-done]");
          if (done) done.hidden = false;
          var submitBtn = $("[data-pat-submit]");
          if (submitBtn) submitBtn.hidden = true;
        } else {
          result.className = "pat-result pat-bad";
          result.textContent = "❌ " + (lang === "en" ? j.message_en : j.message_zh);
          $("[data-pat-quiz]").hidden = true;
          $("[data-pat-cards]").hidden = false;
          root.classList.remove("is-playing");
          assign = {}; picked = {};
          $("[data-pat-start]").hidden = false;
          renderProgress("cards");
          state.reloadToRetry = true;
          $("[data-pat-start]").textContent = lang === "en"
            ? "🪵 Look at the cards again, then start over"
            : "🪵 再看一次成員卡，重新出發";
        }
      }).catch(function () {
        result.className = "pat-result pat-bad";
        result.textContent = lang === "en"
          ? "The connection failed. Please try again."
          : "連線失敗。請再試一次。";
      });
  }

  (function () {
    if (!data.playable || !(data.members || []).length) {
      $("[data-pat-deck]").innerHTML = '<p class="pat-muted">'
        + esc(lang === "en"
            ? "This patrol does not have enough members yet."
            : "這個小隊暫時未有足夠成員。")
        + "</p>";
      sync();
      renderProgress("cards");
      return;
    }
    renderProgress("cards");
    showCard(0);
    $("[data-pat-prev]").addEventListener("click", function () { showCard(state.scene - 1); });
    $("[data-pat-next]").addEventListener("click", function () { showCard(state.scene + 1); });
    $("[data-pat-start]").addEventListener("click", startStage1);
    $("[data-pat-stage1-check]").addEventListener("click", checkStage1);
    $("[data-pat-back-cards]").addEventListener("click", function () {
      $("[data-pat-stage1]").hidden = true;
      $("[data-pat-cards]").hidden = false;
      root.classList.remove("is-playing");
      renderProgress("cards");
      var wrap = $(".cave-card-wrap");
      if (wrap) wrap.scrollTop = 0;
    });
    $("[data-pat-form]").addEventListener("submit", submit);
  })();
})();
