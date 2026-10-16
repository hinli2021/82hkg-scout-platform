"""The first boot against a fresh Sheet must be cheap, and must only add.

Measured before this work: 63 Google API calls to build the catalogue one row at
a time ≈ 10–25 s, past the serverless limit — the boot timed out and every
request answered 500. Now: one meta read, two batch writes, a few reads.
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

BUDGET = 20


def boot(fake: FakeGoogle, monkeypatch=None, **extra) -> Store:
    """Start the app the way a deployment does — against the fake Google API."""
    driver = SheetsDriver("sheet-live", {"client_email": "svc@example.iam.gserviceaccount.com",
                                         "private_key": "x", "project_id": "p"})
    driver._api = fake.api
    if monkeypatch is not None:                      # 不要污染其他測試
        monkeypatch.setattr(store_module, "_sheets_driver", lambda env: driver)
    return Store.from_env({"DATA_DRIVER": "sheets", "GOOGLE_SHEET_ID": "sheet-live",
                           "GOOGLE_SERVICE_ACCOUNT_JSON": "{}", "DATA_DIR": "/tmp/none",
                           **extra})


def test_the_first_boot_stays_inside_its_call_budget(monkeypatch):
    fake = FakeGoogle()
    store = boot(fake, monkeypatch)
    assert store.driver.name == "sheets"
    assert len(store.list("badges")) == 5 and len(store.list("tasks")) == 17
    calls = len(fake.calls)
    assert calls <= BUDGET, f"第一次啟動用了 {calls} 次 Google 呼叫（上限 {BUDGET}）：{fake.calls}"
    # the 15 header rows go in one batch request, not fifteen
    batches = [url for method, url in fake.calls if "values:batchUpdate" in url]
    assert len(batches) == 1


def test_a_warm_boot_does_not_write_anything(monkeypatch):
    fake = FakeGoogle()
    boot(fake, monkeypatch)
    writes = sum(1 for method, _ in fake.calls if method in ("PUT", "POST"))
    store2 = boot(fake, monkeypatch)                        # 等同一次冷啟動／Redeploy
    assert store2.config.get("storage_error", "") == ""
    assert len(store2.list("badges")) == 5 and len(store2.list("tasks")) == 17
    after = sum(1 for method, _ in fake.calls if method in ("PUT", "POST"))
    # 分頁與標題列已存在，所以連建立動作都不會再出現
    assert after == writes, "暖啟動不應該再寫入任何一列"


def test_a_partly_built_catalogue_is_completed_without_touching_what_is_there(monkeypatch):
    fake = FakeGoogle()
    store = boot(fake, monkeypatch)
    badges = store.list("badges")
    # 領袖改過第一個獎章的標題，然後有人刪走第三個獎章
    store.update("badges", badges[0]["id"], {"title_zh": "會員章（82 旅版本）"})
    store.remove("badges", badges[2]["id"])
    store.remove_where("tasks", lambda row: row.get("code") == "M03")

    again = boot(fake, monkeypatch)
    by_code = {row["code"]: row for row in again.list("badges")}
    assert str(by_code[badges[0]["code"]]["title_zh"]) == "會員章（82 旅版本）", "領袖的標題被蓋掉了"
    assert badges[2]["code"] in by_code, "缺少的獎章要補回來"
    assert any(row.get("code") == "M03" for row in again.list("tasks")), "缺少的任務要補回來"
    assert len(again.list("tasks")) == 17


def test_a_badge_the_leader_deleted_on_purpose_is_not_resurrected(monkeypatch):
    fake = FakeGoogle()
    store = boot(fake, monkeypatch)
    badge = next(row for row in store.list("badges") if row["code"] != "SC-01")
    app = create_app({"STORE": store, "TESTING": True, "SECRET_KEY": "t"})
    client = app.test_client()
    store.create_first_leader(username="leader1", password="harbour-82", display_name_zh="陳大文")
    client.post("/login/leader", data={"password": "harbour-82"})

    removed = client.post(f"/leader/content/badges/{badge['id']}/delete", follow_redirects=False)
    assert removed.status_code in (200, 302)
    assert all(row["code"] != badge["code"] for row in store.list("badges"))
    assert badge["code"] in (store.settings().get("catalog_removed") or []), "刪除要被記住"

    again = boot(fake, monkeypatch)                          # 部署新版本之後
    assert all(row["code"] != badge["code"] for row in again.list("badges")), \
        "領袖刪除過的獎章不可以在新版本自己回來"


def test_a_failing_catalogue_never_blocks_the_site(monkeypatch):
    fake = FakeGoogle()
    driver = SheetsDriver("sheet-live", {"client_email": "svc@example.iam.gserviceaccount.com",
                                         "private_key": "x", "project_id": "p"})
    driver._api = fake.api
    monkeypatch.setattr(store_module, "_sheets_driver", lambda env: driver)
    boom = type("Boom", (), {"ensure_catalog": lambda self: (_ for _ in ()).throw(
        RuntimeError("quota exceeded"))})
    monkeypatch.setattr(store_module.Store, "ensure_catalog", boom.ensure_catalog)

    store = Store.from_env({"DATA_DRIVER": "sheets", "GOOGLE_SHEET_ID": "sheet-live",
                            "GOOGLE_SERVICE_ACCOUNT_JSON": "{}", "DATA_DIR": "/tmp/none"})
    assert store.driver.name == "sheets", "建立目錄失敗不可以令網站退回暫存"
    assert "quota exceeded" in store.config.get("catalog_error", "")

    app = create_app({"STORE": store, "TESTING": True, "SECRET_KEY": "t"})
    client = app.test_client()
    landing = client.get("/", follow_redirects=True)
    assert landing.status_code == 200
    assert "建立第一位領袖" in landing.get_data(as_text=True)

    store.create_first_leader(username="leader1", password="harbour-82", display_name_zh="陳大文")
    client.post("/login/leader", data={"password": "harbour-82"})
    page = client.get("/leader/settings").get_data(as_text=True)
    assert "建立失敗" in page or "quota" in page, "設定檢查要說出目錄建立失敗"


def test_the_two_writes_are_whole_tables_not_rows(monkeypatch):
    """獎章一次、任務一次 —— 這樣才不會超時。"""
    fake = FakeGoogle()
    boot(fake, monkeypatch)
    puts = [url for method, url in fake.calls if method == "PUT"]
    assert len(puts) == 2, puts
    assert any("badges!A2:" in url for url in puts), puts
    assert any("tasks!A2:" in url for url in puts), puts
