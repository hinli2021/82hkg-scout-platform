"""推送新版本、重新部署之後，資料會不會不見？── 這是上線前最重要的一條。

用假的 Google 試算表模擬真實世界的一整段時間：

1. 空試算表第一次連上（正式預設：沒有示範帳戶）
2. 建立第一位領袖，再由領袖開一個童軍帳戶
3. 童軍完成一項任務（進度、積分寫入試算表）
4. 領袖改動內容（例如把獎章標題改成自己的字）
5. 「部署新版」：用同一份試算表重新開一個 Store 與 app（等同 Vercel 收到新 commit 後重建）
6. 檢查：所有資料、所有編輯都原封不動，沒有重複列，也沒有示範帳戶偷偷出現
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from scout.drivers.sheets import SheetsDriver          # noqa: E402
from scout.store import Store                          # noqa: E402
from test_sheets_driver import FakeGoogle              # noqa: E402


def boot(fake: FakeGoogle, **overrides) -> Store:
    """等同一次啟動：新的驅動、新的 Store、同一份試算表。"""
    driver = SheetsDriver("sheet-live", {"client_email": "svc@example.iam.gserviceaccount.com",
                                         "private_key": "x", "project_id": "p"})
    driver._api = fake.api
    driver.ensure_schema()
    config = {"demo_login": False, "seed_demo": False, "data_dir": "/tmp", **overrides}
    store = Store(driver=driver, config=config)
    if config["seed_demo"] and store.needs_setup():
        store.seed_demo()
    else:
        store.ensure_catalog()
    return store


def tab(fake: FakeGoogle, name: str) -> list[list]:
    return [row for row in (fake.tabs.get(name) or []) if any(str(cell).strip() for cell in row)]


def count(fake: FakeGoogle, name: str) -> int:
    return max(0, len(tab(fake, name)) - 1)          # 減去標題列


def rows_in(fake: FakeGoogle, name: str, needle: str) -> list[list]:
    return [row for row in tab(fake, name) if needle in json.dumps(row, ensure_ascii=False)]


def test_a_redeploy_never_touches_the_data_in_the_sheet():
    fake = FakeGoogle()

    # ① 空試算表第一次連上：目錄建立，但沒有示範帳戶
    store = boot(fake)
    assert count(fake, "badges") == 5 and count(fake, "tasks") >= 11
    assert count(fake, "users") == 0, "正式版不會自己加入示範帳戶"
    first_run_badges = tab(fake, "badges")

    # ② 建立第一位領袖（走真正的網頁路徑）
    from app import create_app
    app = create_app({"STORE": store, "TESTING": True, "SECRET_KEY": "t"})
    client = app.test_client()
    made = client.post("/setup", data={"unit_zh": "港島第八十二旅童軍團", "name_zh": "陳大文",
                                       "username": "leader1", "password": "harbour-82",
                                       "password2": "harbour-82"}, follow_redirects=False)
    assert made.status_code == 302
    assert count(fake, "users") == 1

    # ③ 領袖開一個童軍帳戶，童軍完成一項任務
    scout = store.insert("users", {
        "role": "scout", "username": "scout01", "password_hash": "x", "password_salt": "y",
        "display_name_zh": "王小明", "display_name_en": "Wong Siu Ming", "email": "a@b.c",
        "scout_no": "S1000", "section": "scout", "patrol": "Tiger", "unit": "港島第八十二旅童軍團",
        "avatar": "", "status": "active", "must_change_password": False,
        "show_on_leaderboard": True, "created_at": "2026-10-16T00:00:00.000Z", "created_by": "leader1",
    })
    badge = store.list("badges")[0]
    task = next(t for t in store.list("tasks") if t.get("badge_id") == badge["id"])
    store.insert("progress_records", {
        "user_id": scout["id"], "badge_id": badge["id"], "task_id": task["id"],
        "attempt_no": 1, "status": "completed", "score": 100, "leader_comment": "",
        "answers_json": None, "checklist_json": None, "evidence_url": "", "reflection_text": "",
        "points_awarded": 15, "submitted_at": "2026-10-16T00:00:00.000Z",
        "decided_at": "2026-10-16T00:00:00.000Z", "decided_by": "auto",
    })
    store.insert("points_ledger", {
        "user_id": scout["id"], "entry_type": "task", "points_delta": 15,
        "reason_zh": "完成任務", "reason_en": "task done", "ref_type": "task",
        "ref_id": task["id"], "created_at": "2026-10-16T00:00:00.000Z", "created_by": "system",
    })
    before = {name: count(fake, name) for name in ("users", "badges", "tasks", "progress_records",
                                                   "points_ledger", "audit_log")}

    # ④ 領袖改動內容：改獎章標題、改一道題的答案（兩者都只是試算表的一格）
    store.update("badges", badge["id"], {"title_zh": "會員章（82 旅版本）"})
    questions = json.loads(json.dumps(task.get("config_json") or {}))
    edited = {**app_edited(task), "note": "領袖改過"}
    store.update("tasks", task["id"], {"config_json": edited})

    # ⑤ 推送新版本之後，Vercel 用同一份試算表重建
    store2 = boot(fake)                                   # 新的進程、新的驅動
    app2 = create_app({"STORE": store2, "TESTING": True, "SECRET_KEY": "t"})
    again = app2.test_client()

    # ⑥ 所有資料與編輯都應該原封不動
    after = {name: count(fake, name) for name in before}
    assert after == before, f"列數改變了：{before} → {after}"

    assert str(store2.get("badges", badge["id"])["title_zh"]) == "會員章（82 旅版本）"
    saved = app_edited(store2.get("tasks", task["id"]))
    assert saved.get("note") == "領袖改過", f'領袖的改動不見了：{saved}' 
    assert str(store2.get("users", scout["id"])["display_name_zh"]) == "王小明"
    assert store2.get("users", scout["id"])["patrol"] == "Tiger"
    still = store2.list("progress_records")
    assert any(r["task_id"] == task["id"] and r["user_id"] == scout["id"] for r in still)
    earned = sum(int(r["points_delta"]) for r in store2.list("points_ledger")
                 if r["user_id"] == scout["id"])
    assert earned == 15

    # 目錄沒有被重寫、也沒有新增一次
    assert tab(fake, "badges") == first_run_badges
    assert count(fake, "users") == 2, "重新部署不會再加入任何帳戶（領袖 + 童軍）"

    # 領袖登入仍然有效（密碼存在試算表）
    door = again.post("/login/leader", data={"password": "harbour-82"}, follow_redirects=False)
    assert door.status_code == 302 and "/leader" in door.headers["Location"]
    assert "王小明" in again.get("/leader/accounts").get_data(as_text=True)


def test_even_with_demo_seeding_on_an_existing_sheet_is_left_alone():
    """就算誤開了 SEED_DEMO=true，已有領袖的試算表也不會被植入示範資料。"""
    fake = FakeGoogle()
    store = boot(fake)
    store.create_first_leader(username="leader1", password="harbour-82", display_name_zh="陳大文")
    before = count(fake, "users")

    store2 = boot(fake, seed_demo=True)                   # 誤開示範
    assert count(fake, "users") == before, "已有領袖就不會示範植入"
    assert count(fake, "badges") == 5, "目錄也沒有重複建立"


def app_edited(task: dict) -> dict:
    """把任務設定取出來（本地是 dict，試算表回來是 JSON 字串）。"""
    config = task.get("config_json") or {}
    return json.loads(config) if isinstance(config, str) else dict(config)
