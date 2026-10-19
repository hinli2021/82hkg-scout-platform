"""誤刪了內建遊戲（石室／渡口）之後，要救得回來，而且童軍進度不能消失。

領袖真實個案：不小心刪了渡口。這裡走完整條路：
登入 → 刪除 → 修復 → 確認任務回來、區域重新接好、玩過的童軍仍然算完成。
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import scout.store as store_module                                  # noqa: E402
from app import create_app                                          # noqa: E402
from scout.drivers.sheets import SheetsDriver                       # noqa: E402
from scout.store import Store                                        # noqa: E402
from test_sheets_driver import FakeGoogle                            # noqa: E402


def boot(fake: FakeGoogle, monkeypatch, **extra) -> Store:
    driver = SheetsDriver("sheet-live", {"client_email": "svc@example.iam.gserviceaccount.com",
                                         "private_key": "x", "project_id": "p"})
    driver._api = fake.api
    monkeypatch.setattr(store_module, "_sheets_driver", lambda env: driver)
    return Store.from_env({"DATA_DRIVER": "sheets", "GOOGLE_SHEET_ID": "sheet-live",
                           "GOOGLE_SERVICE_ACCOUNT_JSON": "{}", "DATA_DIR": "/tmp/none",
                           **extra})


def leader_client(store):
    """A signed-in leader — created if this database has none yet."""
    app = create_app({"STORE": store, "TESTING": True, "SECRET_KEY": "t"})
    client = app.test_client()
    if not any(row.get("role") == "leader" for row in store.list("users")):
        store.create_first_leader(username="leader1", password="harbour-82", display_name_zh="陳大文")
    signed_in = client.post("/login/leader", data={"password": "harbour-82"})
    assert signed_in.status_code == 302 and "/leader" in signed_in.headers["Location"], \
        "領袖要真的登入了，後面的斷言才有意義"
    return client


def task_by_code(store, code):
    return next((row for row in store.list("tasks") if row.get("code") == code), None)


def area(store, n):
    badge = next(row for row in store.list("badges") if row.get("code") == "SC-01")
    guide = badge["guide_json"] if isinstance(badge["guide_json"], dict) else json.loads(badge["guide_json"])
    return guide["quest"]["areas"][n - 1]


def test_the_build_in_games_cannot_be_deleted_at_all(monkeypatch):
    fake = FakeGoogle()
    store = boot(fake, monkeypatch)
    client = leader_client(store)
    for code in ("M04", "M05"):
        task = task_by_code(store, code)
        answer = client.post(f"/leader/content/tasks/{task['id']}/delete", follow_redirects=False)
        assert answer.status_code == 409, f"{code} 應該不能刪除"
        assert task_by_code(store, code), f"{code} 仍然要在"
    assert task_by_code(store, "M05")["code"] == "M05"


def test_the_console_shows_a_lock_instead_of_a_bin_for_the_built_in_games(monkeypatch):
    """連按都按不到，就不會再誤刪。其他任務（包括領袖自己加的）照樣有垃圾桶。"""
    fake = FakeGoogle()
    store = boot(fake, monkeypatch)
    client = leader_client(store)
    page = client.get("/leader/content").get_data(as_text=True)
    assert "內建遊戲：不能刪除" in page
    for code in ("M04", "M05"):
        task = task_by_code(store, code)
        assert f"/leader/content/tasks/{task['id']}/delete" not in page, code
    mine = store.insert("tasks", {"badge_id": task_by_code(store, "M05")["badge_id"],
                                  "code": "X-09", "title_zh": "我的任務", "title_en": "Mine",
                                  "type": "checklist", "points": 3, "status": "draft",
                                  "order_index": 99, "config_json": {}})
    page = client.get("/leader/content").get_data(as_text=True)
    assert f"/leader/content/tasks/{mine['id']}/delete" in page, "領袖自己的任務仍然可以刪"


def test_the_membership_badge_cannot_be_deleted(monkeypatch):
    fake = FakeGoogle()
    store = boot(fake, monkeypatch)
    client = leader_client(store)
    badge = next(row for row in store.list("badges") if row["code"] == "SC-01")
    answer = client.post(f"/leader/content/badges/{badge['id']}/delete", follow_redirects=False)
    assert answer.status_code == 409
    assert any(row["code"] == "SC-01" for row in store.list("badges"))


def test_a_deleted_game_comes_back_with_the_progress_of_every_scout(monkeypatch):
    """模擬領袖的意外：先解除該區遊戲，再刪走任務。修復後童軍仍然算完成。"""
    fake = FakeGoogle()
    store = boot(fake, monkeypatch)
    bridge = task_by_code(store, "M05")
    scout = store.insert("users", {"role": "scout", "username": "scout01", "display_name_zh": "王小明",
                                    "display_name_en": "Wong Siu Ming", "patrol": "Tiger",
                                    "status": "active", "section": "scout"})
    # 一位童軍玩過渡口（記錄指向 M05 的 id；渡口的答案以 stage1…3 存放）
    store.insert("progress_records", {
        "user_id": scout["id"], "badge_id": bridge["badge_id"], "task_id": bridge["id"],
        "attempt_no": 1, "status": "completed", "score": 100,
        "answers_json": json.dumps({"stage1": ["m1"], "stage2": ["p1"], "stage3": ["l1a"]}),
        "submitted_at": "2026-10-16T00:00:00.000Z", "decided_at": "2026-10-16T00:00:00.000Z",
        "decided_by": "auto", "points_awarded": 15,
    })

    # 意外：區域遊戲被清空，然後任務被刪走（直接經 store，等同 UI 的效果）
    badge = next(row for row in store.list("badges") if row["code"] == "SC-01")
    guide = json.loads(json.dumps(badge["guide_json"])) if isinstance(badge["guide_json"], dict) \
        else json.loads(badge["guide_json"])
    guide["quest"]["areas"][1]["game"] = {"n": 2, "kind": "", "ready": False, "task_code": "",
                                          "name_zh": "即將推出", "name_en": "Coming soon",
                                          "blurb_zh": "內容待領袖提供。", "blurb_en": ""}
    store.update("badges", badge["id"], {"guide_json": guide})
    store.remember_removed("M05")
    store.remove("tasks", bridge["id"])
    assert task_by_code(store, "M05") is None
    assert "M05" in (store.settings().get("catalog_removed") or [])

    client = leader_client(store)
    fixed = client.post("/leader/content/repair-games", follow_redirects=False)
    assert fixed.status_code == 302 and "/leader/content" in fixed.headers["Location"], fixed.status_code

    # 領袖按完要看到結果，不是猜（橫額由轉址帶來的參數渲染）
    page = client.get(fixed.headers["Location"]).get_data(as_text=True)
    assert "還原完成" in page and "補回 M05" in page and "童軍進度保留" in page

    restored = task_by_code(store, "M05")
    assert restored, "渡口要回來"
    assert restored["id"] == bridge["id"], "要沿用舊 id，否則童軍的完成記錄會變成孤兒"
    assert "M05" not in (store.settings().get("catalog_removed") or []), "記號要清走"
    game = area(store, 2)["game"]
    assert game["ready"] is True and game["task_code"] == "M05" and game["kind"] == "bridge"

    # 童軍的完成記錄仍然對得上（這是進度計算的關鍵）
    from scout.engine import progress_for
    progress = progress_for(store, scout["id"])
    badge_row = next(row for row in progress["badges"] if row["code"] == "SC-01")
    task_row = next(row for row in badge_row["tasks"] if row["code"] == "M05")
    assert task_row["status"] == "completed", task_row


def test_repair_leaves_a_leaders_own_replacement_game_alone(monkeypatch):
    """領袖在第 2 區換上了自己的任務：修復要把內建渡口放回任務表，但不可搶走那一區。"""
    fake = FakeGoogle()
    store = boot(fake, monkeypatch)
    badge = next(row for row in store.list("badges") if row["code"] == "SC-01")
    custom = store.insert("tasks", {
        "badge_id": badge["id"], "code": "G-01", "title_zh": "自製遊戲", "title_en": "My game",
        "instruction_zh": "玩", "instruction_en": "Play", "type": "quiz", "points": 5,
        "status": "published", "order_index": 99, "config_json": {"questions": [1]},
    })
    guide = json.loads(json.dumps(badge["guide_json"])) if isinstance(badge["guide_json"], dict) \
        else json.loads(badge["guide_json"])
    guide["quest"]["areas"][1]["game"] = {"n": 2, "kind": "task", "ready": True, "task_code": "G-01",
                                          "name_zh": "自製遊戲", "name_en": "My game",
                                          "blurb_zh": "玩", "blurb_en": "Play"}
    store.update("badges", badge["id"], {"guide_json": guide})

    client = leader_client(store)
    client.post("/leader/content/repair-games", follow_redirects=False)

    game = area(store, 2)["game"]
    assert game["task_code"] == "G-01" and game["ready"] is True, "領袖的安排不可以被蓋掉"
    assert task_by_code(store, "M05"), "內建渡口本身仍然要回到任務表（不會自動接上第 2 區）"
    assert task_by_code(store, "G-01")


def test_the_repair_card_is_on_the_content_page(monkeypatch):
    fake = FakeGoogle()
    store = boot(fake, monkeypatch)
    client = leader_client(store)
    page = client.get("/leader/content").get_data(as_text=True)
    assert "修復遊戲與缺少的項目" in page
    assert "還原內建遊戲（石室、渡口、訓練場）" in page
    assert "還原所有缺少的內建項目" in page
    assert 'name="scope" value="games"' in page and 'name="scope" value="all"' in page
    assert "repair-games" in page
    assert "全部內建項目齊全" in page, "齊全時應該顯示 ✓ 而不是警告"
    assert "17 / 17" in page, "要顯示內建項目對照"


def test_the_card_warns_while_the_bridge_is_missing(monkeypatch):
    fake = FakeGoogle()
    store = boot(fake, monkeypatch)
    bridge = task_by_code(store, "M05")
    badge = next(row for row in store.list("badges") if row["code"] == "SC-01")
    guide = json.loads(json.dumps(badge["guide_json"])) if isinstance(badge["guide_json"], dict) \
        else json.loads(badge["guide_json"])
    guide["quest"]["areas"][1]["game"] = {"n": 2, "kind": "", "ready": False, "task_code": ""}
    store.update("badges", badge["id"], {"guide_json": guide})
    store.remember_removed("M05")
    store.remove("tasks", bridge["id"])

    client = leader_client(store)
    page = client.get("/leader/content").get_data(as_text=True)
    assert "有東西需要還原" in page
    assert "M05" in page and "第 2 區未接好" in page
    assert "16 / 17" in page, "要寫出少了幾項"


def test_games_scope_does_not_resurrect_other_awards_tasks_but_all_scope_does(monkeypatch):
    """領袖只想要兩個遊戲回來時，其他獎章的刪除要照樣保持；要全部回來就按第二個按鈕。"""
    fake = FakeGoogle()
    store = boot(fake, monkeypatch)
    client = leader_client(store)
    standard = task_by_code(store, "T-13")
    scout = store.insert("users", {"role": "scout", "username": "scout02", "display_name_zh": "李小花",
                                    "display_name_en": "Lee Siu Fa", "patrol": "Otter",
                                    "status": "active", "section": "scout"})
    store.insert("progress_records", {
        "user_id": scout["id"], "badge_id": standard["badge_id"], "task_id": standard["id"],
        "attempt_no": 1, "status": "completed", "score": 100, "answers_json": None,
        "submitted_at": "2026-10-16T00:00:00.000Z", "decided_at": "2026-10-16T00:00:00.000Z",
        "decided_by": "leader1", "points_awarded": 5,
    })
    client.post(f"/leader/content/tasks/{standard['id']}/delete")
    assert task_by_code(store, "T-13") is None

    client.post("/leader/content/repair-games", data={"scope": "games"})
    assert task_by_code(store, "T-13") is None, "只還原遊戲時，其他獎章的刪除要保持"
    assert task_by_code(store, "M05"), "遊戲一定要回來"

    client.post("/leader/content/repair-games", data={"scope": "all"})
    back = task_by_code(store, "T-13")
    assert back and back["id"] == standard["id"], "還原所有內建項目時要沿用舊 id"
    assert "T-13" not in (store.settings().get("catalog_removed") or [])


def test_a_game_row_that_was_emptied_gets_its_content_back(monkeypatch):
    """另一種「刪掉遊戲」：任務列還在，但題目／設定被清空。修復要把內容填回，但不碰領袖的編輯。"""
    fake = FakeGoogle()
    store = boot(fake, monkeypatch)
    client = leader_client(store)
    cave, bridge = task_by_code(store, "M04"), task_by_code(store, "M05")
    store.update("tasks", bridge["id"], {"config_json": {"kind": "", "links": []}})
    page = client.get("/leader/content").get_data(as_text=True)
    assert "的內容被清空了" in page, "應提示內容空了"

    client.post("/leader/content/repair-games", data={"scope": "games"})
    back = task_by_code(store, "M05")
    assert (back["config_json"] or {}).get("kind") == "bridge", "渡口的設定要填回"
    assert len((task_by_code(store, "M04")["config_json"] or {}).get("questions") or []) == 50, \
        "石室的 50 題要齊全"

    # 領袖自己改過的題目：不是空的，就不會被覆蓋
    edited = [{"prompt_zh": "領袖自己出的題", "prompt_en": "Mine", "choices": ["a", "b"],
               "answer": 0}]
    store.update("tasks", cave["id"], {"config_json": {"questions": edited}})
    client.post("/leader/content/repair-games", data={"scope": "games"})
    assert (task_by_code(store, "M04")["config_json"] or {}).get("questions") == edited, \
        "有內容的題目不可以被覆蓋"


def test_tasks_the_leader_deleted_on_purpose_are_not_reported_as_missing(monkeypatch):
    """領袖手動刪了幾項不用的任務：修復卡不應催他還原。"""
    fake = FakeGoogle()
    store = boot(fake, monkeypatch)
    client = leader_client(store)
    for code in ("M07", "M08", "M09"):
        task = task_by_code(store, code)
        client.post(f"/leader/content/tasks/{task['id']}/delete")
    page = client.get("/leader/content").get_data(as_text=True)
    assert "有東西需要還原" not in page, "故意刪除的項目不應觸發警告"
    assert "全部內建項目齊全" in page
    assert "你已刪除" in page and "M07" in page and "M09" in page
    assert "14 / 14" in page, "分母不計故意刪除的三項"


def test_a_row_edited_straight_out_of_the_sheet_is_still_reported(monkeypatch):
    """直接在試算表刪掉（沒有記號）—— 這種才要提示。"""
    fake = FakeGoogle()
    store = boot(fake, monkeypatch)
    client = leader_client(store)
    task = task_by_code(store, "M08")
    store.remove("tasks", task["id"])          # 不呼叫 remember_removed
    page = client.get("/leader/content").get_data(as_text=True)
    assert "有東西需要還原" in page and "M08" in page
