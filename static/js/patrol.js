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
    var at = step === "story" ? 0 : step === "cards" ? 1 : step === "stage1" ? 2 : 3;
    var dots = "";
    for (var i = 0; i < 4; i++) dots += '<i' + (i === at ? ' class="on"' : "") + "></i>";
    return '<span class="pat-dots">' + dots + "</span>";
  }

  function renderProgress(step) {
    $("[data-pat-progress]").innerHTML = (step === "story"
      ? (lang === "en" ? "The story" : "故事")
      : step === "cards"
        ? (lang === "en" ? "Know your patrol" : "認識小隊成員")
        : step === "stage1"
          ? (lang === "en" ? "Stage 1: find your patrol" : "第一階段：找出小隊成員")
          : (lang === "en" ? "Stage 2: seat the raft" : "第二階段：安排木筏崗位"))
      + progress(step);
  }

  function factRow(label, text, fallback) {
    return '<div class="char-row"><span class="char-row-k">' + esc(label)
      + '</span><span class="char-row-v">' + esc(text || fallback) + "</span></div>";
  }

  /* the profile card prints a member's name this way: English first with
     the Chinese after it — and the patrol's name the same */
  function displayName(member) {
    if (lang === "en") return member.name_en || member.name_zh || "";
    if (member.name_en && member.name_zh && member.name_en !== member.name_zh) {
      return member.name_en + " " + member.name_zh;
    }
    return member.name_zh || member.name_en || "";
  }

  function displayPatrol() {
    if (lang === "en") return data.patrol_en || data.patrol_zh || "";
    if (data.patrol_en && data.patrol_zh && data.patrol_en !== data.patrol_zh) {
      return data.patrol_en + " " + data.patrol_zh;
    }
    return data.patrol_zh || data.patrol_en || "";
  }

  function cardBack(member) {
    /* the profile card's back: the status numbers, the badges earned,
       then the member's details in their own words */
    var earned = (member.earned_badges || []).map(function (badge) {
      return '<span class="chip brass">' + esc(badge.emoji || "🎖") + " "
        + esc(lang === "en" ? badge.title_en : badge.title_zh) + "</span>";
    }).join("");
    var rows = '<div class="char-back-head"><span class="char-back-name">'
      + esc(displayName(member)) + "</span>"
      + '<span class="char-back-sub">' + esc(lang === "en" ? "Status overview" : "狀態總覽") + "</span></div>"
      + '<div class="char-stats">'
      + '<div class="char-stat"><span class="char-stat-k">' + esc(lang === "en" ? "Badges" : "獎章")
      + '</span><span class="char-stat-v">' + esc(member.badges_done || 0) + "/" + esc(member.badges_total || 0) + "</span></div>"
      + '<div class="char-stat"><span class="char-stat-k">' + esc(lang === "en" ? "Tasks" : "任務")
      + '</span><span class="char-stat-v">' + esc(member.tasks_done || 0) + "/" + esc(member.tasks_total || 0) + "</span></div>"
      + '<div class="char-stat"><span class="char-stat-k">' + esc(lang === "en" ? "Points" : "積分")
      + '</span><span class="char-stat-v">' + esc(member.points_balance || 0) + "</span></div>"
      + '<div class="char-stat"><span class="char-stat-k">' + esc(lang === "en" ? "Day streak" : "連續天數")
      + '</span><span class="char-stat-v">' + esc(member.streak_current || 0) + "</span></div>"
      + "</div>"
      + '<div class="char-badges"><span class="char-row-k">'
      + esc(lang === "en" ? "Badges earned" : "已考獲的獎章") + "</span>"
      + (earned ? '<span class="row wrap" style="gap:.35rem">' + earned + "</span>"
                 : '<span class="char-row-v">' + esc(lang === "en" ? "No badges earned yet." : "尚未考獲獎章。") + "</span>")
      + "</div>"
      + '<div class="char-details">'
      + factRow(lang === "en" ? "Position" : "職位",
                lang === "en" ? member.position_en : member.position_zh,
                lang === "en" ? "Not written yet" : "尚未填寫")
      + factRow(lang === "en" ? "Patrol" : "小隊", displayPatrol(), "")
      + factRow(lang === "en" ? "Interests" : "興趣", member.interests,
                lang === "en" ? "Not written yet." : "尚未填寫。")
      + factRow(lang === "en" ? "Scout experience" : "童軍經驗", member.experience,
                lang === "en" ? "Not written yet." : "尚未填寫。")
      + factRow(lang === "en" ? "Something to share" : "想和大家分享的事", member.share,
                lang === "en" ? "Not written yet." : "尚未填寫。")
      + factRow(lang === "en" ? "My strength" : "我的強項", member.strength,
                lang === "en" ? "Not written yet." : "尚未填寫。")
      + "</div>";
    if (!member.complete) {
      rows += '<p class="pat-muted">'
        + esc(lang === "en"
            ? "This member has not finished their profile yet — know them by their name, avatar, scout number and position."
            : "這位成員尚未完成個人檔案——可以靠姓名、頭像、童軍編號和職位辨認他。")
        + "</p>";
    }
    if (member.is_contact) {
      rows += '<p class="pat-contact">'
        + esc(lang === "en"
            ? "📨 Patrol contact — how to reach them: find them in person at a meeting, or ask your leader to pass a message on."
            : "📨 小隊聯絡——聯絡方法：在集會時親自找他，或請領袖幫忙聯絡。")
        + "</p>";
    }
    return rows;
  }

  function memberCard(member) {
    var name = displayName(member);
    var position = (lang === "en" ? member.position_en : member.position_zh)
      || (lang === "en" ? "No position yet" : "尚未填寫職位");
    var patrol = displayPatrol();
    var mascot = member.mascot || {};
    var notYet = lang === "en" ? "Not written yet" : "尚未填寫";
    /* the very card the member sees on their own profile page — the same
       classes, the same layout, drawn from the same live profile */
    var front;
    if (member.card_image_url) {
      front = '<img class="char-generated-img" src="' + esc(member.card_image_url)
        + '" alt="' + esc(lang === "en" ? "AI card picture" : "AI 生成的個人卡圖") + '">';
    } else {
      var stars = "";
      var done = member.badges_done || 0, total = member.badges_total || 0;
      for (var i = 0; i < done; i++) stars += "★";
      for (var j = done; j < total; j++) stars += "☆";
      front = '<span class="poke-head"><span class="poke-name">' + esc(name) + "</span>"
        + '<span class="poke-hp"><small>HP</small> ' + esc(member.points_balance || 0)
        + '<span class="poke-type">' + esc(mascot.emoji || "🐣") + "</span></span></span>"
        + '<span class="char-portrait poke-art">'
        + (mascot.img ? '<img src="' + esc(mascot.img) + '" alt="">'
                      : '<span class="char-portrait-emoji" aria-hidden="true">' + esc(mascot.emoji || "🐣") + "</span>")
        + '<span class="char-avatar" aria-hidden="true">' + esc(member.avatar || "🦊") + "</span></span>"
        + '<span class="poke-info"><span>NO. ' + esc(member.scout_no || "—") + "</span>"
        + "<span>" + esc(patrol || "") + "</span><span>" + esc(position) + "</span></span>"
        + (member.is_contact
            ? '<span class="pat-badge">📨 ' + esc(lang === "en" ? "Patrol contact" : "小隊聯絡") + "</span>" : "")
        + '<span class="poke-moves">'
        + '<span class="poke-ability"><span class="poke-ability-label">'
        + esc(lang === "en" ? "Interests" : "興趣") + '</span><span class="poke-ability-text">'
        + esc(member.interests || notYet) + "</span></span>"
        + '<span class="poke-move"><span class="poke-move-head"><span class="poke-cost">'
        + esc(mascot.emoji || "🐣") + '</span><span class="poke-move-name">'
        + esc(lang === "en" ? "Scout experience" : "童軍經驗") + '</span></span>'
        + '<span class="poke-move-text">' + esc(member.experience
            || (lang === "en" ? "No Scout experience written yet." : "尚未填寫童軍經驗。")) + "</span></span>"
        + '<span class="poke-move"><span class="poke-move-head"><span class="poke-cost">⭐</span>'
        + '<span class="poke-move-name">' + esc(lang === "en" ? "Something to share" : "想和大家分享的事")
        + '</span></span><span class="poke-move-text poke-clamp-2">' + esc(member.share || notYet + (lang === "en" ? "" : "。")) + "</span></span>"
        + "</span>"
        + '<span class="poke-bottom">'
        + "<span><small>" + esc(lang === "en" ? "Badges" : "獎章") + "</small>" + esc(done) + "/" + esc(total) + "</span>"
        + "<span><small>" + esc(lang === "en" ? "Tasks" : "任務") + "</small>" + esc(member.tasks_done || 0) + "/" + esc(member.tasks_total || 0) + "</span>"
        + "<span><small>" + esc(lang === "en" ? "Day streak" : "連續天數") + "</small>" + esc(member.streak_current || 0) + "</span>"
        + "</span>"
        + '<span class="poke-foot"><span>' + esc(lang === "en" ? "82nd Hong Kong Island Scout Group" : "港島第八十二旅童軍團")
        + '</span><span class="poke-rarity">' + stars + "</span></span>";
    }
    return '<button type="button" class="pat-card char-card" data-member="' + esc(member.id) + '"'
      + ' style="--char-tint: ' + esc(mascot.tint || "#2f8f5b")
      + "; --char-tint-dark: " + esc(mascot.tint_dark || "#1f6b43")
      + "; --char-soft: " + esc(mascot.soft || "rgba(47, 143, 91, .14)") + '">'
      + '<span class="char-face char-front">' + front + "</span>"
      + '<span class="char-face char-back">' + cardBack(member) + "</span>"
      + "</button>";
  }

  function showCard(index) {
    var deck = $("[data-pat-deck]");
    var member = (data.members || [])[index];
    if (!member) return;
    state.scene = index;
    deck.innerHTML = '<div class="pat-scene-wrap">'
      + memberCard(member)
      + '<p class="pat-count">' + (index + 1) + " / " + (data.members || []).length
      + '<span class="pat-fliphint">' + esc(lang === "en" ? "Tap the card to flip it" : "按一下卡片翻面") + "</span></p>"
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

  /* ── the opening story, told page by page ─────────────────────────── */
  var storyAt = 0;

  function storyPages() {
    return Array.prototype.slice.call(document.querySelectorAll("[data-pat-page]"));
  }

  function showStoryPage() {
    var pages = storyPages();
    pages.forEach(function (page, i) { page.hidden = i !== storyAt; });
    var count = $("[data-pat-story-count]");
    if (count) count.textContent = pages.length > 1 ? (storyAt + 1) + " / " + pages.length : "";
    var next = $("[data-pat-story-next]");
    var last = storyAt >= pages.length - 1;
    if (next) next.textContent = last
      ? (lang === "en" ? "👥 Meet your patrol" : "👥 去認識你的小隊")
      : (lang === "en" ? "Continue →" : "繼續 →");
    renderProgress("story");
  }

  function storyNext() {
    var pages = storyPages();
    if (storyAt < pages.length - 1) {
      storyAt += 1;
      showStoryPage();
      var wrap = $(".cave-card-wrap");
      if (wrap) wrap.scrollTop = 0;
      return;
    }
    /* the story is told — now, know your patrol */
    enterCards();
    var wrap2 = $(".cave-card-wrap");
    if (wrap2) wrap2.scrollTop = 0;
  }

  function enterCards() {
    $("[data-pat-story]").hidden = true;
    $("[data-pat-cards]").hidden = false;
    renderProgress("cards");
  }

  function startStage1() {
    /* the story picture belongs to the opening only: once the game is
       under way the words panel takes the whole window */
    root.classList.add("is-playing");
    $("[data-pat-cards]").hidden = true;
    $("[data-pat-story]").hidden = true;
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
    $("[data-pat-story]").hidden = true;
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
          runPassed = true;
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

  /* ── the warning before leaving ──────────────────────────────────────
     Leaving before the raft sets off discards this visit's flipped
     cards and placements. An in-page dialog, not window.confirm: the
     offline viewer runs in a sandboxed iframe where native confirm
     dialogs are blocked. The same dialog every other game shows. While
     the story is still being told nothing is lost yet, so the warning
     starts once the member cards are on the table. */
  var runPassed = false;
  var exitOverlay = document.createElement("div");
  exitOverlay.className = "cave-exit-overlay";
  exitOverlay.hidden = true;
  exitOverlay.innerHTML =
    '<div class="cave-exit-dialog" role="alertdialog" aria-modal="true" ' +
      'aria-labelledby="patrol-exit-title" aria-describedby="patrol-exit-message">' +
      '<span class="cave-kicker">' + esc(lang === "en" ? "Leaving the game" : "離開遊戲") + "</span>" +
      '<h2 id="patrol-exit-title">' + esc(lang === "en" ? "Leave the seaside?" : "要離開海邊嗎？") + "</h2>" +
      '<p id="patrol-exit-message">' +
        esc(lang === "en"
          ? "If you leave, you will have to start the game again when you return. Unsubmitted answers will not be saved."
          : "離開後，再次進入遊戲需要從頭開始。尚未提交的作答不會保留。") +
      "</p>" +
      '<div class="cave-exit-actions">' +
        '<button type="button" class="btn primary" data-pat-stay>' +
          esc(lang === "en" ? "Keep playing" : "繼續遊戲") + "</button>" +
        '<button type="button" class="btn ghost" data-pat-leave>' +
          esc(lang === "en" ? "Leave game" : "離開遊戲") + "</button>" +
      "</div>" +
    "</div>";
  document.body.appendChild(exitOverlay);
  var pendingExit = null;
  var lastFocus = null;
  var approvedExit = false;
  function patInProgress() {
    if (runPassed) return false;
    var story = $("[data-pat-story]");
    return !!story && story.hidden;
  }
  function finishExit(leave) {
    if (exitOverlay.hidden) return;
    var callback = pendingExit;
    pendingExit = null;
    if (exitOverlay.contains(document.activeElement)) document.activeElement.blur();
    exitOverlay.hidden = true;
    document.body.classList.remove("cave-exit-open");
    if (leave) {
      approvedExit = true;
      if (callback) callback();
    } else if (lastFocus && lastFocus.isConnected && lastFocus !== document.body) {
      lastFocus.focus();
    }
    lastFocus = null;
  }
  exitOverlay.addEventListener("click", function (event) {
    if (event.target.closest("[data-pat-stay]") || event.target === exitOverlay) finishExit(false);
    else if (event.target.closest("[data-pat-leave]")) finishExit(true);
  });
  exitOverlay.addEventListener("keydown", function (event) {
    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); finishExit(false); return; }
    if (event.key !== "Tab") return;
    var stay = exitOverlay.querySelector("[data-pat-stay]");
    var leave = exitOverlay.querySelector("[data-pat-leave]");
    if (event.shiftKey && document.activeElement === stay) {
      event.preventDefault(); leave.focus();
    } else if (!event.shiftKey && document.activeElement === leave) {
      event.preventDefault(); stay.focus();
    }
  });
  function requestExit(callback) {
    if (!patInProgress()) { if (callback) callback(); return; }
    if (!exitOverlay.hidden) return;
    pendingExit = callback;
    lastFocus = document.activeElement;
    exitOverlay.hidden = false;
    document.body.classList.add("cave-exit-open");
    exitOverlay.querySelector("[data-pat-stay]").focus();
  }
  if (!window.OFFLINE_DEMO) {
    document.addEventListener("click", function (event) {
      if (!patInProgress() || event.defaultPrevented || event.button !== 0 ||
          event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      var anchor = event.target.closest("a[href]");
      if (!anchor || anchor.target === "_blank" || anchor.hasAttribute("download")) return;
      var href = anchor.getAttribute("href");
      if (!href || href.charAt(0) === "#") return;
      event.preventDefault();
      event.stopImmediatePropagation();
      requestExit(function () { window.location.assign(anchor.href); });
    }, true);
    document.addEventListener("submit", function (event) {
      if (!patInProgress()) return;
      if (event.target.closest("[data-pat-form]")) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      var form = event.target;
      requestExit(function () { form.submit(); });
    }, true);
    window.addEventListener("beforeunload", function (event) {
      if (approvedExit || !patInProgress()) return;
      event.preventDefault();
      event.returnValue = "";
    });
    window.addEventListener("pageshow", function (event) {
      if (event.persisted) approvedExit = false;
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
      renderProgress("story");
      showStoryPage();
      $("[data-pat-story-next]").addEventListener("click", storyNext);
      return;
    }
    /* every visit starts from the beginning, story first — a replay
       hears the seaside story again before knowing the patrol */
    renderProgress("story");
    showStoryPage();
    showCard(0);
    $("[data-pat-prev]").addEventListener("click", function () { showCard(state.scene - 1); });
    $("[data-pat-next]").addEventListener("click", function () { showCard(state.scene + 1); });
    $("[data-pat-story-next]").addEventListener("click", storyNext);
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
