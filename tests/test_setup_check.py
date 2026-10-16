"""領袖後台「設定檢查」卡與 /health 的回報 —— 上線時一眼看到準備好了沒有。

這一張卡是給領袖自己用的：它只看，不會改動任何資料；有未完成的項目會直接
寫出「怎樣做」。測試用假試算表走正式路徑（沒有示範帳戶）驗證每一列的判斷。
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from app import create_app                                     # noqa: E402
from scout.drivers.sheets import SheetsDriver                   # noqa: E402
from scout.routes.leader_routes import setup_checks             # noqa: E402
from scout.store import Store                                   # noqa: E402
from test_sheets_driver import FakeGoogle                       # noqa: E402


def rows(checks: dict) -> dict[str, dict]:
    return {item["key"]: item for item in checks["checks"]}


def boot(fake: FakeGoogle, **config) -> Store:
    driver = SheetsDriver("sheet-live", {"client_email": "svc@example.iam.gserviceaccount.com",
                                         "private_key": "x", "project_id": "p"})
    driver._api = fake.api
    driver.ensure_schema()
    store = Store(driver=driver, config={"demo_login": False, "seed_demo": False,
                                         "data_dir": "/tmp", **config})
    store.ensure_catalog()                    # 等同正式部署第一次連上空試算表
    return store


def test_a_ready_deployment_shows_every_check_green():
    fake = FakeGoogle()
    store = boot(fake)
    store.create_first_leader(username="leader1", password="harbour-82",
                              display_name_zh="陳大文", unit="港島第八十二旅童軍團")
    store.insert("users", {"role": "scout", "username": "scout01", "display_name_zh": "王小明",
                           "patrol": "Tiger", "status": "active"})

    checks = setup_checks(store)
    by_key = rows(checks)
    for key in ("storage", "badges", "tasks", "games", "leaders", "scouts"):
        assert by_key[key]["ok"], f"{key} 應該已經完成：{by_key[key]}"
    assert checks["ready"] is True and checks["pending"] == 0
    assert checks["counts"]["badges"] == 5 and checks["counts"]["scouts"] == 1
    assert by_key["badges"]["detail_zh"].startswith("5")

    # 寄信信箱是可選項：未設定不算「未就緒」，但會提示怎樣做
    assert by_key["email"]["ok"] is False and by_key["email"]["optional"] is True
    assert "docs/03" in by_key["email"]["fix_zh"]
    assert checks["optional_pending"] == 1


def test_an_empty_deployment_points_at_what_is_missing():
    fake = FakeGoogle()
    store = boot(fake)

    checks = setup_checks(store)
    by_key = rows(checks)
    assert by_key["badges"]["detail_zh"] == "5 個獎章"      # 目錄已建立
    assert by_key["scouts"]["ok"] is False                  # 還沒有童軍
    assert "開設童軍帳戶" in by_key["scouts"]["fix_zh"]
    assert checks["ready"] is False
    assert checks["counts"]["leaders"] == 0


def test_local_storage_is_flagged_with_the_way_to_fix_it():
    import tempfile

    from scout.drivers.local import LocalDriver

    store = Store(driver=LocalDriver(tempfile.mkdtemp()),
                  config={"demo_login": False, "seed_demo": False, "data_dir": "/tmp"})
    store.ensure_catalog()
    by_key = rows(setup_checks(store))
    assert by_key["storage"]["ok"] is False
    assert "暫存" in by_key["storage"]["detail_zh"]
    assert "GOOGLE_SHEET_ID" in by_key["storage"]["fix_zh"]


def test_the_card_renders_in_the_console_and_never_writes_anything():
    fake = FakeGoogle()
    store = boot(fake)
    store.create_first_leader(username="leader1", password="harbour-82", display_name_zh="陳大文")
    app = create_app({"STORE": store, "TESTING": True, "SECRET_KEY": "t"})
    client = app.test_client()
    client.post("/login/leader", data={"password": "harbour-82"})

    before = {name: len(fake.tabs.get(name) or []) for name in ("badges", "tasks", "users", "settings")}
    page = client.get("/leader/settings").get_data(as_text=True)
    after = {name: len(fake.tabs.get(name) or []) for name in before}

    assert "設定檢查" in page and "資料儲存在 Google 試算表" in page
    assert "不會改動任何資料" in page
    assert before == after, "看一次設定頁不應該寫入任何列"


def test_health_reports_counts_without_any_names():
    fake = FakeGoogle()
    store = boot(fake)
    store.create_first_leader(username="leader1", password="harbour-82", display_name_zh="陳大文")
    app = create_app({"STORE": store, "TESTING": True, "SECRET_KEY": "t"})

    body = app.test_client().get("/health").get_json()
    assert body["ok"] is True and body["storage"] == "sheets"
    assert body["demo"] is False
    assert body["counts"] == {"badges": 5, "tasks": 17, "users": 1}
    assert body["setup_ready"] is True
    assert "陳大文" not in json.dumps(body, ensure_ascii=False), "健康檢查不可以回傳姓名"
