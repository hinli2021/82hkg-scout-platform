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
    return '<span class="pat-dots">' + (step === "cards"
        ? '<i class="on"></i><i></i>' : '<i></i><i class="on"></i>') + "</span>";
  }

  function renderProgress(step) {
    $("[data-pat-progress]").innerHTML = (step === "cards"
      ? (lang === "en" ? "Step 1 of 2: member cards" : "第 1 步，共 2 步：翻開成員卡")
      : (lang === "en" ? "Step 2 of 2: seat the raft" : "第 2 步，共 2 步：安排木筏崗位"))
      + progress(step);
  }

  function cardBack(member) {
    if (!member.complete) {
      return '<div class="pat-front-back">'
        + '<p class="pat-muted">'
        + esc(lang === "en" ? "This member has not finished their profile yet."
                            : "這位成員尚未填寫個人檔案。")
        + "</p></div>";
    }
    return '<ul class="pat-facts">'
      + "<li><b>" + esc(lang === "en" ? "Interests" : "興趣") + "</b><span>" + esc(member.interests) + "</span></li>"
      + "<li><b>" + esc(lang === "en" ? "Strength" : "強項") + "</b><span>" + esc(member.strength) + "</span></li>"
      + "<li><b>" + esc(lang === "en" ? "Scout experience" : "童軍經驗") + "</b><span>" + esc(member.experience) + "</span></li>"
      + "<li><b>" + esc(lang === "en" ? "Something to share" : "想和大家分享的事") + "</b><span>" + esc(member.share) + "</span></li>"
      + "</ul>";
  }

  function memberCard(member) {
    var name = lang === "en" ? member.name_en : member.name_zh;
    var position = (lang === "en" ? member.position_en : member.position_zh)
      || (lang === "en" ? "No position yet" : "暫時沒有職位");
    var contact = member.is_contact
      ? '<span class="pat-badge">📨 ' + esc(lang === "en" ? "Patrol contact" : "小隊聯絡") + "</span>" : "";
    var contactHow = "";
    if (member.is_contact) {
      contactHow = '<p class="pat-contact">'
        + esc(lang === "en"
            ? (member.contact_email
                ? "How to reach them: send an email to " + member.contact_email
                : "How to reach them: this member has no email yet — ask your leader.")
            : (member.contact_email
                ? "聯絡方法：發電郵至 " + member.contact_email
                : "聯絡方法：這位成員尚未登記電郵，請向領袖查詢。"))
        + "</p>";
    }
    return '<button type="button" class="pat-card" data-member="' + esc(member.id) + '">'
      + '<span class="pat-card-inner">'
      + '<span class="pat-face pat-front">'
        + '<span class="pat-avatar">' + esc(member.avatar || "🦊") + "</span>"
        + '<strong>' + esc(name) + "</strong>"
        + '<span class="pat-pos">' + esc(position) + "</span>"
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
    if (data.playable && state.flipped.size >= members.length) {
      start.hidden = false;
      hint.textContent = lang === "en"
        ? "You have flipped every card. Time to seat the raft."
        : "所有成員卡都已翻開。可以去安排木筏崗位。";
    } else if (data.playable) {
      start.hidden = true;
      hint.textContent = (lang === "en" ? "Flipped: " : "已翻開：")
        + state.flipped.size + " / " + members.length;
    }
    if (!data.playable) {
      hint.textContent = lang === "en"
        ? "Your patrol has very few members, so the raft cannot be seated yet. Ask your leader to add your patrol mates first."
        : "小隊的成員太少，暫時未能安排木筏崗位。請先向領袖查詢，請領袖把隊員加入平台。";
    }
  }

  function startQuiz() {
    $("[data-pat-cards]").hidden = true;
    $("[data-pat-intro]").hidden = true;
    $("[data-pat-quiz]").hidden = false;
    renderProgress("quiz");
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
          renderProgress("cards");
          state.reloadToRetry = true;
          $("[data-pat-start]").textContent = lang === "en"
            ? "🚣 Look at the cards again, then seat the raft once more"
            : "🚣 再看一次成員卡，重新安排木筏";
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
    $("[data-pat-start]").addEventListener("click", startQuiz);
    $("[data-pat-form]").addEventListener("submit", submit);
  })();
})();
