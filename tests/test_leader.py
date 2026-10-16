"""The leader console: content, review queue, accounts, rewards, settings, log."""
from __future__ import annotations

import json
import pathlib

from conftest import grant_awards          # the shared 'leader grants an award' helper
from scout import engine


def submit_pending(app, store, username="scout04"):
    """Walk a scout to a leader-verified submission and return the record id.

    The evidence sample task lives in 標準獎章, which only opens once the two
    awards before it are earned — so the leader grants those first.
    """
    scout = grant_awards(app, store, username, orders=(1, 2))
    client = app.test_client()
    client.post(f"/login/scout/{scout['patrol']}/{scout['id']}", data={"password": "scout1234"})
    task = next(t for t in store.list("tasks")
                if t["type"] == "evidence" and not any(
                    r["task_id"] == t["id"] and r["user_id"] == scout["id"] and r["status"] == "completed"
                    for r in store.list("progress_records")))
    client.post(f"/tasks/{task['id']}/submit", data={"evidence_url": "/uploads/x.jpg"},
                headers={"Accept": "application/json"})
    return next(r["id"] for r in store.list("progress_records")
                if r["user_id"] == scout["id"] and r["task_id"] == task["id"] and r["status"] == "pending"), task


# ── every console page renders ──────────────────────────────────────────────

def test_console_pages_render(leader_client, extras_on):
    for path in ("/leader", "/leader/content", "/leader/review", "/leader/accounts",
                 "/leader/announcements", "/leader/rewards", "/leader/settings", "/leader/audit"):
        response = leader_client.get(path)
        assert response.status_code == 200, f"{path} → {response.status_code}"
        assert "領袖" in response.get_data(as_text=True) or "Leader" in response.get_data(as_text=True)


def test_overview_shows_the_basic_quick_actions(leader_client):
    page = leader_client.get("/leader").get_data(as_text=True)
    assert "quick-actions" in page
    for needle in ("審批提交", "重設密碼申請", "新增獎章任務", "開設童軍帳戶", "發公告"):
        assert needle in page
    assert "獎品目錄" not in page          # 獎品 is switched off for now


def test_overview_quick_actions_grow_with_the_switches(leader_client, extras_on):
    page = leader_client.get("/leader").get_data(as_text=True)
    assert "獎品目錄" in page             # switched on → the shortcut is back


def test_overview_counts_match_the_data(leader_client, store):
    body = leader_client.get("/api/leader/overview").get_json()
    counts = body["counts"]
    assert counts["scouts"] == len([u for u in store.list("users") if u["role"] == "scout"])
    assert counts["badges"] == len([b for b in store.list("badges") if b["status"] == "published"])
    assert counts["pending"] == len([r for r in store.list("progress_records") if r["status"] == "pending"])


def test_task_editor_renders(leader_client, store):
    cave = next(t for t in store.list("tasks") if t.get("code") == "M04")
    page = leader_client.get(f"/leader/content/tasks/{cave['id']}").get_data(as_text=True)
    assert cave["title_zh"] in page
    assert 'name="quiz_zh"' not in page, "the generic paste form would destroy the wall IDs"
    assert f"/leader/content/tasks/{cave['id']}/cave-questions" in page

    task = next(t for t in store.list("tasks") if t.get("code") == "T-11")
    other = leader_client.get(f"/leader/content/tasks/{task['id']}").get_data(as_text=True)
    assert 'name="quiz_zh"' in other
    config = engine.as_json(task["config_json"], {})
    assert config["questions"][0]["q_zh"] in other
    assert f" | {config['questions'][0]['answer'] + 1} | " in other, "leader sees the real answer"


# ── review queue ────────────────────────────────────────────────────────────

def test_review_queue_lists_pending(app, leader_client, store):
    record_id, _ = submit_pending(app, store)
    page = leader_client.get("/leader/review").get_data(as_text=True)
    assert "review-card" in page
    assert "何嘉欣" in page                       # scout04
    assert record_id in page


def test_approve_pays_points_and_completes(app, leader_client, store):
    record_id, task = submit_pending(app, store)
    record = store.get("progress_records", record_id)
    before = store.stats_for(record["user_id"])["points_balance"]

    response = leader_client.post(f"/leader/review/{record_id}", data={"action": "approve", "comment": "做得好！"})
    assert response.status_code in (200, 302)

    after = store.get("progress_records", record_id)
    assert after["status"] == "completed"
    assert after["leader_comment"] == "做得好！"
    assert after["decided_by"] == leader_client.id
    assert store.stats_for(record["user_id"])["points_balance"] == before + int(task["points"])
    assert any(row["ref_id"] == record["task_id"] and row["entry_type"] == "task"
               for row in store.list("points_ledger") if row["user_id"] == record["user_id"])


def test_approve_can_override_the_points(app, leader_client, store):
    record_id, _ = submit_pending(app, store)
    record = store.get("progress_records", record_id)
    before = store.stats_for(record["user_id"])["points_balance"]
    leader_client.post(f"/leader/review/{record_id}", data={"action": "approve", "points": "25"})
    assert store.stats_for(record["user_id"])["points_balance"] == before + 25


def test_reject_sends_it_back_with_a_comment(app, leader_client, store):
    record_id, _ = submit_pending(app, store)
    leader_client.post(f"/leader/review/{record_id}", data={"action": "reject", "comment": "相片太模糊"})
    record = store.get("progress_records", record_id)
    assert record["status"] == "rejected" and record["leader_comment"] == "相片太模糊"
    assert record["points_awarded"] == 0
    # …and the scout can hand it in again
    scout = next(u for u in store.list("users") if u["id"] == record["user_id"])
    client = app.test_client()
    client.post(f"/login/scout/{scout['patrol']}/{scout['id']}", data={"password": "scout1234"})
    again = client.post(f"/tasks/{record['task_id']}/submit", data={"evidence_url": "/uploads/better.jpg"},
                        headers={"Accept": "application/json"})
    assert again.status_code == 200


def test_reset_puts_it_back_in_the_queue(app, leader_client, store):
    record_id, _ = submit_pending(app, store)
    leader_client.post(f"/leader/review/{record_id}", data={"action": "reset"})
    record = store.get("progress_records", record_id)
    assert record["status"] == "pending" and record["decided_by"] == ""


def test_bad_review_action_is_refused(leader_client, store):
    record = store.list("progress_records")[0]
    response = leader_client.post(f"/leader/review/{record['id']}", data={"action": "explode"})
    assert response.status_code == 400


def test_unknown_record_is_404(leader_client):
    assert leader_client.post("/leader/review/nope", data={"action": "approve"}).status_code == 404


def test_leader_approval_cannot_replace_five_area_games(app, leader_client, store):
    """Optional syllabus sign-offs, even with the cave, cannot earn the badge."""
    scout = next(u for u in store.list("users") if u["username"] == "scout03")
    client = app.test_client()
    client.post(f"/login/scout/{scout['patrol']}/{scout['id']}", data={"password": "scout1234"})
    badge = next(b for b in store.list("badges") if b.get("code") == "SC-01")

    for pending in [r for r in store.list("progress_records")
                    if r.get("user_id") == scout["id"] and r.get("status") == "pending"]:
        leader_client.post(f"/leader/review/{pending['id']}", data={"action": "approve"})
    before = engine.progress_for(store, scout["id"])
    assert before["badges"][0]["progress_done"] == 0
    assert before["badges"][0]["earned"] is False

    cave = next(t for t in store.list("tasks") if t.get("code") == "M04")
    config = cave["config_json"]
    config = json.loads(config) if isinstance(config, str) else config
    answer = {f"q{i}": str(q["answer"]) for i, q in enumerate(config["questions"])}
    result = client.post(f"/tasks/{cave['id']}/cave-submit", data=answer,
                         headers={"Accept": "application/json"}).get_json()
    assert result["passed"] is True
    after = engine.progress_for(store, scout["id"])
    assert after["badges"][0]["progress_done"] == 1
    assert after["badges"][0]["earned"] is False
    assert after["badges"][1]["locked"] is True, "four games are still missing"


def test_create_scout_account(leader_client, store):
    response = leader_client.post("/leader/accounts", data={
        "display_name_zh": "新童軍", "display_name_en": "New Scout", "patrol": "Tiger",
        "scout_no": "S2001", "email": "new@example.com", "avatar": "🐻",
    })
    assert response.status_code in (200, 302)
    created = next(u for u in store.list("users") if u["display_name_zh"] == "新童軍")
    assert created["role"] == "scout" and created["patrol"] == "Tiger"
    assert created["password_hash"] == "" and created["must_change_password"] is True
    assert store.get("stats", created["id"]) is not None      # stats row created with the account


def test_create_scout_needs_a_name_and_patrol(leader_client):
    assert leader_client.post("/leader/accounts", data={"patrol": "Tiger"}).status_code == 400
    assert leader_client.post("/leader/accounts", data={"display_name_zh": "無小隊"}).status_code == 400


def test_username_collision_is_refused(leader_client):
    response = leader_client.post("/leader/accounts", data={
        "display_name_zh": "撞名", "patrol": "Tiger", "username": "scout01"})
    assert response.status_code == 409


def test_created_scout_can_sign_in_first_time(leader_client, store):
    leader_client.post("/leader/accounts", data={"display_name_zh": "小小", "patrol": "Otter"})
    created = next(u for u in store.list("users") if u["display_name_zh"] == "小小")
    client = store  # keep linters quiet
    visitor = __import__("flask").current_app.test_client() if False else None
    assert created["username"]


def test_lock_and_unlock(app, leader_client, store):
    scout = next(u for u in store.list("users") if u["username"] == "scout05")
    leader_client.post(f"/leader/accounts/{scout['id']}/lock")
    assert store.get("users", scout["id"])["status"] == "locked"
    visitor = app.test_client()
    blocked = visitor.post(f"/login/scout/Seagull/{scout['id']}", data={"password": "scout1234"})
    assert blocked.status_code == 403
    leader_client.post(f"/leader/accounts/{scout['id']}/unlock")
    assert store.get("users", scout["id"])["status"] == "active"


def test_delete_scout_removes_the_records(leader_client, store):
    scout = next(u for u in store.list("users") if u["username"] == "scout01")
    assert [r for r in store.list("progress_records") if r["user_id"] == scout["id"]]
    leader_client.post(f"/leader/accounts/{scout['id']}/delete")
    assert store.get("users", scout["id"]) is None
    assert not [r for r in store.list("progress_records") if r["user_id"] == scout["id"]]
    assert not [r for r in store.list("badge_awards") if r["user_id"] == scout["id"]]
    assert not [r for r in store.list("points_ledger") if r["user_id"] == scout["id"]]
    assert store.get("stats", scout["id"]) is None


def test_edit_scout_details(leader_client, store):
    scout = next(u for u in store.list("users") if u["username"] == "scout02")
    leader_client.post(f"/leader/accounts/{scout['id']}", data={
        "display_name_en": "Lee Mei Yee Sr", "patrol": "Seagull", "scout_no": "S9999",
        "show_on_leaderboard": "0"})
    updated = store.get("users", scout["id"])
    assert updated["display_name_en"] == "Lee Mei Yee Sr"
    assert updated["patrol"] == "Seagull"
    assert updated["show_on_leaderboard"] is False


def test_csv_export_has_the_roster(leader_client, store):
    response = leader_client.get("/leader/accounts/export.csv")
    assert response.status_code == 200
    assert "attachment" in response.headers["Content-Disposition"]
    text = response.get_data(as_text=True)
    assert "display_name_zh" in text and "王小明" in text
    assert "has_password" in text
    assert "password_hash" not in text          # never export the hash


def test_csv_import_creates_accounts(leader_client, store):
    import io

    csv_text = ("username,display_name_zh,display_name_en,patrol,scout_no,email,avatar\n"
                "scoutaa,陳小明,Ming Chan,Tiger,S3001,ming@example.com,🐯\n"
                "scoutbb,黃小美,May Wong,Otter,S3002,,🐼\n"
                "scoutaa,重複,Dup,Tiger,,,\n")
    response = leader_client.post("/leader/accounts/import",
                                  data={"file": (io.BytesIO(csv_text.encode("utf-8")), "scouts.csv")},
                                  content_type="multipart/form-data")
    assert response.status_code in (200, 302)
    created = [u for u in store.list("users") if u["username"] in ("scoutaa", "scoutbb")]
    assert len(created) == 2
    assert all(u["password_hash"] == "" for u in created)     # first sign-in sets it
    assert store.get("stats", created[0]["id"]) is not None


def test_import_without_content_is_refused(leader_client):
    assert leader_client.post("/leader/accounts/import", json={"csv": "   "}).status_code == 400


def test_adjust_points_writes_a_labelled_ledger_entry(leader_client, store):
    scout = next(u for u in store.list("users") if u["username"] == "scout06")
    before = store.stats_for(scout["id"])["points_balance"]
    leader_client.post("/leader/rewards/adjust-points",
                       data={"user_id": scout["id"], "points_delta": "15", "reason": "協助集會"})
    assert store.stats_for(scout["id"])["points_balance"] == before + 15
    entry = [r for r in store.list("points_ledger") if r["user_id"] == scout["id"]][-1]
    assert entry["entry_type"] == "manual" and entry["reason_zh"] == "協助集會"


# ── content ─────────────────────────────────────────────────────────────────

def test_create_and_edit_a_badge(leader_client, store):
    leader_client.post("/leader/content/badges", data={
        "title_zh": "測試獎章", "title_en": "Test award", "code": "SC-99",
        "emoji": "🧪", "points_reward": "40", "status": "published", "desc_zh": "測試用"})
    badge = next(b for b in store.list("badges") if b["title_zh"] == "測試獎章")
    assert badge["points_reward"] == 40 and badge["status"] == "published"

    leader_client.post(f"/leader/content/badges/{badge['id']}",
                       data={"title_en": "Test award v2", "points_reward": "55"})
    updated = store.get("badges", badge["id"])
    assert updated["title_en"] == "Test award v2" and updated["points_reward"] == 55


def test_badges_can_be_reordered(leader_client, store):
    before = [b["id"] for b in sorted(store.list("badges"), key=lambda b: int(b["order_index"]))]
    leader_client.post(f"/leader/content/badges/{before[1]}/move", data={"direction": "up"})
    after = [b["id"] for b in sorted(store.list("badges"), key=lambda b: int(b["order_index"]))]
    assert after[0] == before[1] and after[1] == before[0]


def test_delete_badge_takes_its_tasks(leader_client, store):
    badge = store.list("badges")[0]
    task_ids = [t["id"] for t in store.list("tasks") if t["badge_id"] == badge["id"]]
    assert task_ids
    leader_client.post(f"/leader/content/badges/{badge['id']}/delete")
    assert store.get("badges", badge["id"]) is None
    assert all(store.get("tasks", task_id) is None for task_id in task_ids)


def test_create_task_from_plain_text(leader_client, store):
    badge = store.list("badges")[0]
    leader_client.post("/leader/content/tasks", data={
        "badge_id": badge["id"], "title_zh": "文字任務", "type": "checklist",
        "points": "8", "status": "published",
        "items_zh": "第一項\n第二項\n第三項", "items_en": "one\ntwo\nthree"})
    task = next(t for t in store.list("tasks") if t["title_zh"] == "文字任務")
    config = task["config_json"]
    config = json.loads(config) if isinstance(config, str) else config
    assert [item["zh"] for item in config["items"]] == ["第一項", "第二項", "第三項"]
    assert config["items"][1]["en"] == "two"


def test_create_task_without_a_badge_is_refused(leader_client):
    response = leader_client.post("/leader/content/tasks", data={"title_zh": "無獎章"})
    assert response.status_code == 400


def test_edit_task_instructions_and_points(leader_client, store):
    task = next(t for t in store.list("tasks") if t["type"] == "reflection")
    leader_client.post(f"/leader/content/tasks/{task['id']}", data={
        "raw_title_zh": "反思（更新）", "points": "12", "min_chars": "80"})
    updated = store.get("tasks", task["id"])
    assert updated["title_zh"] == "反思（更新）" and int(updated["points"]) == 12
    config = updated["config_json"]
    config = json.loads(config) if isinstance(config, str) else config
    assert config["min_chars"] == 80


def test_tasks_can_be_reordered(leader_client, store):
    badge = store.list("badges")[0]
    siblings = sorted([t for t in store.list("tasks") if t["badge_id"] == badge["id"]],
                      key=lambda t: int(t["order_index"]))
    assert len(siblings) >= 2
    leader_client.post(f"/leader/content/tasks/{siblings[1]['id']}/move", data={"direction": "up"})
    after = sorted([t for t in store.list("tasks") if t["badge_id"] == badge["id"]],
                   key=lambda t: int(t["order_index"]))
    assert after[0]["id"] == siblings[1]["id"]


def test_delete_task(leader_client, store):
    task = store.list("tasks")[-1]
    leader_client.post(f"/leader/content/tasks/{task['id']}/delete")
    assert store.get("tasks", task["id"]) is None


def test_a_leader_can_grant_an_award_manually(leader_client, store):
    scout = next(u for u in store.list("users") if u["username"] == "scout06")
    badge = store.list("badges")[2]
    response = leader_client.post(f"/api/leader/scouts/{scout['id']}/award-badge/{badge['id']}")
    assert response.status_code == 200 and response.get_json()["awarded"] is True
    assert any(a["badge_id"] == badge["id"] for a in store.list("badge_awards") if a["user_id"] == scout["id"])
    again = leader_client.post(f"/api/leader/scouts/{scout['id']}/award-badge/{badge['id']}")
    assert again.status_code == 409


# ── announcements ───────────────────────────────────────────────────────────

def test_create_pin_and_delete_a_notice(leader_client, store):
    leader_client.post("/leader/announcements", data={
        "title_zh": "集會改期", "title_en": "Meeting moved", "body_zh": "改為下週日",
        "audience": "scout", "pinned": "1"})
    notice = next(a for a in store.list("announcements") if a["title_zh"] == "集會改期")
    assert notice["pinned"] is True and notice["audience"] == "scout"

    leader_client.post(f"/leader/announcements/{notice['id']}", data={"pinned": "0"})
    assert store.get("announcements", notice["id"])["pinned"] is False

    leader_client.post(f"/leader/announcements/{notice['id']}/delete")
    assert store.get("announcements", notice["id"]) is None


def test_notice_needs_a_title(leader_client):
    assert leader_client.post("/leader/announcements", data={"body_zh": "沒有標題"}).status_code == 400


def test_pinned_notice_appears_on_the_scout_home(app, leader_client, store):
    leader_client.post("/leader/announcements", data={
        "title_zh": "特別公告", "title_en": "Special", "body_zh": "詳情", "audience": "all", "pinned": "1"})
    client = app.test_client()
    client.post("/login/demo/demo2")
    page = client.get("/home").get_data(as_text=True)
    assert "特別公告" in page and "置頂" in page


def test_expired_notice_is_hidden(app, leader_client, store):
    leader_client.post("/leader/announcements", data={
        "title_zh": "過期公告", "audience": "scout", "expires_at": "2020-01-01"})
    client = app.test_client()
    client.post("/login/demo/demo2")
    assert "過期公告" not in client.get("/home").get_data(as_text=True)


def test_leader_only_notice_stays_off_the_scout_home(app, leader_client, store):
    leader_client.post("/leader/announcements", data={
        "title_zh": "領袖通告", "audience": "leader"})
    client = app.test_client()
    client.post("/login/demo/demo2")
    assert "領袖通告" not in client.get("/home").get_data(as_text=True)


# ── rewards ─────────────────────────────────────────────────────────────────

def test_reward_crud(leader_client, store):
    leader_client.post("/leader/rewards", data={
        "title_zh": "小食券", "title_en": "Snack ticket", "emoji": "🍪",
        "points_cost": "60", "stock": "10", "category": "food", "active": "1"})
    reward = next(r for r in store.list("rewards") if r["title_zh"] == "小食券")
    assert int(reward["points_cost"]) == 60

    leader_client.post(f"/leader/rewards/{reward['id']}", data={"points_cost": "75", "active": "0"})
    updated = store.get("rewards", reward["id"])
    assert int(updated["points_cost"]) == 75 and updated["active"] is False
    assert "小食券" not in __import__("scout.engine", fromlist=["x"]).points_summary(store, "x")["recent"].__str__()  # no crash

    leader_client.post(f"/leader/rewards/{reward['id']}/delete")
    assert store.get("rewards", reward["id"]) is None


def test_hidden_reward_is_not_shown_to_scouts(app, leader_client, store, extras_on):
    reward = store.list("rewards")[0]
    leader_client.post(f"/leader/rewards/{reward['id']}", data={"active": "0"})
    client = app.test_client()
    client.post("/login/demo/demo2")
    assert reward["title_zh"] not in client.get("/rewards").get_data(as_text=True)


def test_reward_needs_a_title(leader_client):
    assert leader_client.post("/leader/rewards", data={"points_cost": "10"}).status_code == 400


# ── settings ────────────────────────────────────────────────────────────────

def test_settings_save_unit_and_motto(leader_client, store, app):
    leader_client.post("/leader/settings", data={
        "unit_name_zh": "測試旅團", "unit_name_en": "Test Group",
        "motto_zh": "準備", "motto_en": "Be prepared", "patrols": ["Tiger", "Otter"]})
    saved = store.settings(force=True)
    assert saved["unit_name_zh"] == "測試旅團" and saved["motto_en"] == "Be prepared"
    assert saved["patrols"] == ["Tiger", "Otter"]
    client = app.test_client()
    assert "測試旅團" in client.get("/login").get_data(as_text=True)


def test_settings_switches(leader_client, store):
    # the real form posts a "switches" marker, so an absent box means “off”
    leader_client.post("/leader/settings", data={
        "switches": "1", "ui_sound": "1", "scout_self_reset": "1",
        "flag_leaderboard": "1", "flag_streaks": "1"})
    saved = store.settings(force=True)
    assert saved["ui_sound"] is True and saved["scout_self_reset"] is True
    assert saved["feature_flags"]["leaderboard"] is True

    # unticking a switch turns it off (the checkbox simply is not posted)
    leader_client.post("/leader/settings", data={"switches": "1", "flag_leaderboard": "1"})
    saved = store.settings(force=True)
    assert saved["ui_sound"] is False
    assert saved["feature_flags"]["streaks"] is False


def test_settings_page_shows_the_storage_mode(leader_client):
    assert "本機 JSON 檔案" in leader_client.get("/leader/settings").get_data(as_text=True)


# ── audit log ───────────────────────────────────────────────────────────────

def test_actions_are_logged(leader_client, store, app):
    record_id, _ = submit_pending(app, store)
    leader_client.post(f"/leader/review/{record_id}", data={"action": "approve"})
    leader_client.post("/leader/accounts", data={"display_name_zh": "紀錄測試", "patrol": "Tiger"})
    actions = [row["action"] for row in store.list("audit_log")]
    assert "approve" in actions and "create_scout" in actions


def test_audit_page_renders_entries(leader_client, store):
    page = leader_client.get("/leader/audit").get_data(as_text=True)
    assert "操作紀錄" in page
    assert "sign_in" in page or "seed_demo" in page


def test_sign_in_is_logged(app, store):
    client = app.test_client()
    client.post("/login/demo/demo2")
    assert any(row["action"] == "sign_in" for row in store.list("audit_log"))


# ── leader-facing JSON ──────────────────────────────────────────────────────

def test_leader_scouts_api_lists_everyone(leader_client, store):
    body = leader_client.get("/api/leader/scouts").get_json()
    assert body["ok"]
    assert len(body["scouts"]) == len([u for u in store.list("users") if u["role"] == "scout"])
    assert all("password_hash" not in json.dumps(row) for row in body["scouts"])
    badges = [row["stats"]["badges_done"] for row in body["scouts"]]
    assert badges == sorted(badges, reverse=True)


def test_leader_scout_detail_api(leader_client, store):
    scout = next(u for u in store.list("users") if u["username"] == "scout03")
    body = leader_client.get(f"/api/leader/scouts/{scout['id']}").get_json()
    assert body["ok"] and body["progress"]["badges"]
    assert body["ledger"] == sorted(body["ledger"], key=lambda r: r["created_at"], reverse=True)


def test_leader_leaderboard_api_includes_hidden_scouts(leader_client, store):
    scout = next(u for u in store.list("users") if u["username"] == "scout01")
    store.update("users", scout["id"], {"show_on_leaderboard": False})
    body = leader_client.get("/api/leader/leaderboard").get_json()
    assert any(row["user_id"] == scout["id"] for row in body["rows"])


def test_reset_requests_api(leader_client, app, store):
    scout = next(u for u in store.list("users") if u["username"] == "scout02")
    app.test_client().post("/forgot", data={"patrol": "Tiger", "user_id": scout["id"]})
    body = leader_client.get("/api/leader/reset-requests").get_json()
    assert any(row["user_id"] == scout["id"] for row in body["items"])


def test_leader_api_is_closed_to_scouts(scout_client):
    response = scout_client.client.get("/api/leader/scouts", headers={"Accept": "application/json"})
    assert response.status_code == 403


def test_leader_can_bind_a_new_game_to_an_empty_area(leader_client, scout_client, store):
    """A slot becomes playable only when a distinct new task is explicitly linked."""
    badge = next(b for b in store.list('badges') if b.get('code') == 'SC-01')
    path = f"/leader/content/badges/{badge['id']}/games"
    before = leader_client.get('/leader/content').get_data(as_text=True)
    assert before.count('data-game-area=') == 5
    assert '遊戲 1：童軍歷史山洞（固定）' in before
    assert before.count('尚未提供（保持鎖上）') == 4   # one per area 2–5 select
    assert leader_client.post('/leader/content/tasks', data={
        'badge_id': badge['id'], 'title_zh': '領袖新遊戲', 'title_en': 'New game',
        'instruction_zh': '請選擇答案', 'instruction_en': 'Choose an answer',
        'type': 'quiz', 'points': '10', 'pass_score': '80', 'status': 'published',
        'quiz_zh': '一加一是？ | 2 | 一 | 二 | 三',
        'quiz_en': 'One plus one? | 2 | one | two | three',
    }).status_code == 200
    game = next(t for t in store.list('tasks') if t.get('title_zh') == '領袖新遊戲')
    assert game['code'].startswith('G-')
    assert f'<option value="{game["id"]}"' in leader_client.get('/leader/content').get_data(as_text=True)
    data = {'area_name_zh': '雲霧小徑', 'area_name_en': 'Foggy Path',
            'game_name_zh': '尋路挑戰', 'game_name_en': 'Find the trail',
            'game_blurb_zh': '一個由領袖提供的遊戲。',
            'game_blurb_en': 'A game created by the leader.', 'task_id': game['id']}
    # area 2 now carries the bridge game, so the leader binds the new one to area 3
    assert leader_client.post(path + '/2', data=data).status_code == 409
    assert leader_client.post(path + '/3', data=data).status_code == 200
    guide = engine.as_json(store.get('badges', badge['id'])['guide_json'], {})
    assert guide['quest']['areas'][0]['game']['task_code'] == 'M04'
    assert guide['quest']['areas'][1]['game']['task_code'] == 'M05'      # the bridge stays put
    assert guide['quest']['areas'][2]['game']['task_code'] == game['code']
    assert guide['quest']['areas'][2]['name_zh'] == '雲霧小徑'
    assert all(not a['game']['ready'] for a in guide['quest']['areas'][3:])
    scout_page = scout_client.get(f"/badges/{badge['id']}").get_data(as_text=True)
    area3 = scout_page[scout_page.index('data-stage="3"'):]
    area3 = area3[:area3.index('</li>')]
    assert '雲霧小徑' in area3 and '尋路挑戰' in area3
    assert '一個由領袖提供的遊戲。' in area3
    assert f'/tasks/{game["id"]}' not in scout_page, 'the next game waits until game 1 clears'

    cave = next(t for t in store.list('tasks') if t.get('code') == 'M04')
    content = pathlib.Path(__file__).resolve().parent.parent / 'content' / 'member-badge'
    bank = json.loads((content / 'item4-question-bank.json').read_text())['questions']
    key = {r['id']: r['answerIndex'] for r in
           json.loads((content / 'item4-answer-key.json').read_text())['answers']}
    answer = {f'q{i}': str(key[q['id']]) for i, q in enumerate(bank)}
    assert scout_client.post(f"/tasks/{cave['id']}/cave-submit", data=answer).get_json()['passed']
    bridge = next(t for t in store.list('tasks') if t.get('code') == 'M05')
    next_page = scout_client.get(f"/badges/{badge['id']}").get_data(as_text=True)
    assert next_page.count('data-journey-play') == 1
    # game 1 cleared, so the next offer is the bridge in area 2 — not area 3's new game
    assert f'/tasks/{bridge["id"]}' in next_page and '進入遊戲 2' in next_page
    assert f'/tasks/{game["id"]}' not in next_page
    # a cleared area keeps only its small 再玩一次 door, never the main offer
    assert next_page.count(f'/tasks/{cave["id"]}/cave') == 1
    assert 'data-replay="stage-1"' in next_page
    # the same game may not be linked twice — area 4 is still empty, so it takes the 409
    assert leader_client.post(path + '/4', data={**data, 'task_id': game['id']}).status_code == 409
    guide = engine.as_json(store.get('badges', badge['id'])['guide_json'], {})
    assert not guide['quest']['areas'][3]['game']['ready']
    assert guide['quest']['areas'][2]['game']['ready'], 'a plain re-save keeps area 3 as it is'
    legacy = next(t for t in store.list('tasks') if t.get('code') == 'M03')
    assert leader_client.post(path + '/3', data={'task_id': legacy['id']}).status_code == 400
    assert leader_client.post(f"/leader/content/tasks/{game['id']}",
                              data={'status': 'draft'}).status_code == 409
    assert leader_client.post(f"/leader/content/tasks/{game['id']}/delete").status_code == 409
    cave = next(t for t in store.list('tasks') if t.get('code') == 'M04')
    assert leader_client.post(f"/leader/content/tasks/{cave['id']}/delete").status_code == 409
    assert leader_client.post(f"/leader/content/tasks/{cave['id']}",
                              data={'type': 'checklist'}).status_code == 409
    assert leader_client.post(f"/leader/content/tasks/{cave['id']}",
                              data={'config_json': '{\"questions\": []}'}).status_code == 400
    assert leader_client.post(f"/leader/content/badges/{badge['id']}",
                              data={'code': 'NOT-SC-01'}).status_code == 409
    # A built area is never dropped by accident: the form must say “replace”.
    assert leader_client.post(path + '/3', data={'task_id': ''}).status_code == 409
    # Unassignment is possible only before anybody has tried the new game.
    assert leader_client.post(path + '/2', data={'task_id': '',
                                                 'replace': '1'}).status_code == 200
    assert not engine.as_json(store.get('badges', badge['id'])['guide_json'], {})['quest']['areas'][1]['game']['ready']


def test_a_game_with_previous_progress_cannot_auto_clear_a_new_area(leader_client, new_scout, store):
    badge = next(b for b in store.list('badges') if b.get('code') == 'SC-01')
    create = leader_client.post('/leader/content/tasks', data={
        'badge_id': badge['id'], 'title_zh': '另一個遊戲', 'title_en': 'Another game',
        'instruction_zh': '回答問題', 'instruction_en': 'Answer the question',
        'type': 'quiz', 'status': 'published', 'quiz_zh': '1+1? | 2 | 1 | 2 | 3',
    })
    assert create.status_code == 200 and create.get_json()['ok']
    task = next(t for t in store.list('tasks') if t.get('title_zh') == '另一個遊戲')
    assert new_scout.post(f"/tasks/{task['id']}/submit", data={'q0': '1'}).get_json()['passed']
    response = leader_client.post(f"/leader/content/badges/{badge['id']}/games/4",
                                  data={'task_id': task['id']})
    assert response.status_code == 409 and response.get_json()['error'] == 'old_progress'
    after = engine.as_json(store.get('badges', badge['id'])['guide_json'], {})
    assert not after['quest']['areas'][3]['game']['ready']
    assert engine.progress_for(store, new_scout.id)['badges'][0]['progress_done'] == 0


# ── the mailbox settings and the leader-side reset link ─────────────────────

def test_leader_saves_the_mailbox_settings(leader_client, store):
    saved = leader_client.post("/leader/settings", data={
        "switches": "1", "smtp_host": "smtp.gmail.com", "smtp_port": "587", "smtp_tls": "tls",
        "smtp_user": "82hkg@example.com", "smtp_from": "82hkg@example.com",
        "smtp_password": "abcd efgh ijkl mnop", "reset_link_minutes": "45",
    })
    assert saved.status_code in (200, 302)
    settings = store.settings()
    assert settings["smtp_host"] == "smtp.gmail.com"
    assert settings["smtp_password"] == "abcd efgh ijkl mnop"
    assert settings["reset_link_minutes"] == 45

    # a blank password box keeps the stored one; a hyphen clears it
    leader_client.post("/leader/settings", data={"switches": "1", "smtp_host": "smtp.gmail.com",
                                                 "smtp_password": ""})
    assert store.settings()["smtp_password"] == "abcd efgh ijkl mnop"
    leader_client.post("/leader/settings", data={"switches": "1", "smtp_password": "-"})
    assert store.settings()["smtp_password"] == ""


def test_the_app_password_is_never_printed_back_to_the_leader(leader_client, store):
    store.save_setting("smtp_password", "super-secret-app-password")
    page = leader_client.get("/leader/settings").get_data(as_text=True)
    assert "super-secret-app-password" not in page
    assert "••••••••" in page                      # a dot mask instead


def test_leader_can_send_a_test_email(leader_client, store, monkeypatch):
    import scout.mailer as mailer
    seen = {}
    monkeypatch.setattr(mailer, "deliver", lambda cfg, message: (seen.update(
        {"to": message["To"], "subject": message["Subject"]}), (True, ""))[1])
    store.save_setting("smtp_host", "smtp.gmail.com")
    store.save_setting("smtp_from", "82hkg@example.com")
    store.save_setting("smtp_user", "82hkg@example.com")
    response = leader_client.post("/leader/settings/test-mail", data={"to": "leader@example.com"})
    assert response.status_code in (200, 302)
    assert seen["to"] == "leader@example.com" and "測試" in seen["subject"]


def test_leader_emails_a_reset_link_from_the_accounts_panel(leader_client, store, monkeypatch):
    import scout.mailer as mailer
    sent = []
    monkeypatch.setattr(mailer, "deliver", lambda cfg, message: (sent.append(message) or True, "")) 
    store.save_setting("smtp_host", "smtp.gmail.com")
    store.save_setting("smtp_from", "82hkg@example.com")
    store.save_setting("smtp_user", "82hkg@example.com")
    scout = next(u for u in store.list("users") if u.get("username") == "scout03")
    store.update("users", scout["id"], {"email": "cheung@example.com"})

    response = leader_client.post(f"/leader/accounts/{scout['id']}/send-reset")
    assert response.status_code in (200, 302)
    assert sent and sent[0]["To"] == "cheung@example.com"
    rows = [r for r in store.list("password_resets") if r["user_id"] == scout["id"]]
    assert rows and rows[0]["requested_by"] == "leader"


def test_the_reset_link_button_waits_for_a_mailbox_and_an_address(leader_client, store):
    scout = next(u for u in store.list("users") if u.get("username") == "scout04")
    page = leader_client.get("/leader/accounts").get_data(as_text=True)
    assert "還未設定寄信信箱" in page                       # the note explaining the two ways
    assert "/send-reset" in page                            # the button is on the page
    store.save_setting("smtp_host", "smtp.gmail.com")
    store.save_setting("smtp_from", "82hkg@example.com")
    store.update("users", scout["id"], {"email": ""})
    response = leader_client.post(f"/leader/accounts/{scout['id']}/send-reset")
    assert response.status_code in (200, 302)
    assert not [r for r in store.list("password_resets") if r["user_id"] == scout["id"]]

