"""試算表設定寫錯時，平台要「開得起來而且說得出原因」，不是整站不見。

真實情境：領袖在 Vercel 加環境變數時，金鑰只貼了一半、ID 打錯、或忘了把
試算表共用給機器人 —— 結果整個網站變成 crashed function。修好之後：
Store.from_env() 讀一次試算表作探測，失敗就改用暫存驅動繼續運作，
並把「原因 + 怎樣做」帶到 /health 與領袖後台。
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import scout.store as store_module                              # noqa: E402
from app import create_app                                      # noqa: E402
from scout.store import Store, storage_advice                    # noqa: E402


def broken_driver(env):
    raise json.JSONDecodeError("Expecting value", "{\"type\": \"service_acc", 3)


def test_a_broken_sheet_key_keeps_the_site_up_and_explains_itself(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "_sheets_driver", broken_driver)
    env = {"DATA_DRIVER": "sheets", "GOOGLE_SHEET_ID": "1AbC", "DATA_DIR": str(tmp_path),
           "GOOGLE_SERVICE_ACCOUNT_JSON": "{\"type\": \"service_acc"}

    store = Store.from_env(env)

    assert store.driver.name == "local", "連不上試算表時要退回暫存，而不是讓網站掛掉"
    assert "JSONDecodeError" in store.config["storage_error"]

    app = create_app({"STORE": store, "TESTING": True, "SECRET_KEY": "t"})
    client = app.test_client()
    landing = client.get("/login", follow_redirects=True)          # 空資料庫 → 建立第一位領袖
    assert landing.status_code == 200, "網站要仍然開得起來"
    assert "建立第一位領袖" in landing.get_data(as_text=True)

    body = client.get("/health").get_json()
    assert body["storage"] == "local"

    page = client.get("/health", headers={"Accept": "text/html"}).get_data(as_text=True)
    assert "試算表連不上" in page
    assert "GOOGLE_SERVICE_ACCOUNT_JSON" in page, "要直接寫出怎樣做"

    # 領袖登入後，設定頁也要見到原因（先建立領袖，因為是空資料庫）
    leader = store.create_first_leader(username="leader1", password="harbour-82",
                                       display_name_zh="陳大文")
    client.post("/login/leader", data={"password": "harbour-82"})
    settings = client.get("/leader/settings").get_data(as_text=True)
    assert "連不上 Google 試算表" in settings
    assert "怎樣做：" in settings
    assert leader["id"]


def test_a_missing_sheet_id_is_named_as_the_problem(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "_sheets_driver",
                        lambda env: (_ for _ in ()).throw(ValueError("未設定 GOOGLE_SHEET_ID")))
    store = Store.from_env({"DATA_DRIVER": "sheets", "DATA_DIR": str(tmp_path),
                            "GOOGLE_SERVICE_ACCOUNT_JSON": json.dumps(
                                {"client_email": "svc@x.iam.gserviceaccount.com", "private_key": "k"})})
    reason, advice = storage_advice(store.config["storage_error"])
    assert "GOOGLE_SHEET_ID" in reason and "GOOGLE_SHEET_ID" in advice
    assert "docs/02" not in reason  # 人話，不是檔名


@pytest.mark.parametrize("error,expect", [
    ("RuntimeError: Google API GET … → 403: The caller does not have permission", "編輯者"),
    ("RuntimeError: Google API GET … → 404: Requested entity was not found.", "找不到那張試算表"),
    ("ValueError: 服務帳戶金鑰不完整：GOOGLE_SERVICE_ACCOUNT_JSON 要是整份 JSON 檔的內容", "整份 JSON"),
    ('json.decoder.JSONDecodeError: Expecting value', "不是有效的 JSON"),
    ("ValueError: Could not deserialize key data. The data may be in an incorrect format",
     "private_key 不完整"),
    ("ModuleNotFoundError: No module named 'google'", "部署缺少套件"),
])
def test_each_common_mistake_gets_its_own_plain_language_fix(error, expect):
    reason, advice = storage_advice(error)
    assert expect in (reason + advice)


@pytest.mark.parametrize("message,expect", [
    ("RuntimeError: Google API GET … → 403: {\"error\": {\"code\": 403, \"message\": "
     "\"Google Sheets API has not been used in project 1234 before or it is disabled. "
     "Enable it by visiting https://console.developers.google.com/apis/api/sheets.googleapis.com/overview?project=1234\"}}",
     "還未在 Google Cloud 專案啟用"),
    ("RuntimeError: Google API POST … → 403: The caller does not have permission", "未共用給服務帳戶電郵"),
])
def test_the_api_not_enabled_message_is_not_blamed_on_sharing(message, expect):
    reason, advice = storage_advice(message)
    assert expect in reason, reason
    if "啟用" in expect:
        assert "程式庫" in advice and "共用" not in reason, "不要把未啟用 API 說成未共用"
    else:
        assert "共用" in advice


def test_a_disabled_drive_api_names_drive_not_sheets():
    reason, _ = storage_advice('403: Google Drive API has not been used in project 9 before or it is disabled')
    assert "Drive" in reason


def test_no_error_means_no_warning_at_all():
    assert storage_advice("") == ("", "")
    assert storage_advice(None) == ("", "")


def test_a_working_sheet_never_triggers_the_fallback(monkeypatch):
    from test_sheets_driver import FakeGoogle
    from scout.drivers.sheets import SheetsDriver

    fake = FakeGoogle()
    driver = SheetsDriver("sheet-live", {"client_email": "svc@example.iam.gserviceaccount.com",
                                         "private_key": "x", "project_id": "p"})
    driver._api = fake.api
    monkeypatch.setattr(store_module, "_sheets_driver", lambda env: driver)

    store = Store.from_env({"DATA_DRIVER": "sheets", "GOOGLE_SHEET_ID": "sheet-live",
                            "GOOGLE_SERVICE_ACCOUNT_JSON": "{}", "DATA_DIR": "/tmp/x"})
    assert store.driver.name == "sheets"
    assert store.config["storage_error"] == ""
    assert len(store.list("badges")) == 5, "目錄在第一次連上時建立"

def test_a_brand_new_empty_sheet_is_reachable_not_broken(tmp_path, monkeypatch):
    """領袖的真實情況：試算表全新、一個分頁都沒有。

    第一次連上時 `values/badges!A1:S20000` 會得到 400「Unable to parse range」，
    因為分頁未存在 —— 這證明試算表其實連得上。之前的探測把它當成失敗，令平台
    錯誤地退回暫存空間，畫面顯示「試算表連不上」。現在必須開得成 sheets。
    """
    from test_sheets_driver import FakeGoogle
    from scout.drivers.sheets import SheetsDriver

    fake = FakeGoogle()                       # 完全空白：沒有任何分頁
    driver = SheetsDriver("sheet-new", {"client_email": "svc@example.iam.gserviceaccount.com",
                                        "private_key": "x", "project_id": "p"})
    driver._api = fake.api
    monkeypatch.setattr(store_module, "_sheets_driver", lambda env: driver)

    store = Store.from_env({"DATA_DRIVER": "sheets", "GOOGLE_SHEET_ID": "sheet-new",
                            "GOOGLE_SERVICE_ACCOUNT_JSON": "{}", "DATA_DIR": str(tmp_path)})

    assert store.config["storage_error"] == "", store.config["storage_error"]
    assert store.driver.name == "sheets", "全新的空試算表不可以被當成連不上"
    assert len(store.list("badges")) == 5, "第一次連上就建立獎章目錄"
    assert set(fake.tabs) >= {"badges", "tasks", "users", "settings"}, "15 個分頁都要建立"


def test_the_probe_also_tolerates_a_range_error_on_its_own(monkeypatch):
    """即使建立分頁那一步做不到，單純的「range 不存在」也不等於連不上。"""
    from scout.store import _probe

    class OnlyRanges:
        def ensure_schema(self):
            raise RuntimeError('Google API POST … → 400: {"error": {"code": 400, '
                               '"message": "Unable to parse range: badges!A1:S20000"}}')

        def list(self, collection):
            raise AssertionError("不應該走到這裡")

    with pytest.raises(RuntimeError):
        _probe(OnlyRanges())                  # 建立分頁失敗仍然要如實拋出

    class Reachable:
        def ensure_schema(self):
            return None

        def list(self, collection):
            raise RuntimeError('Google API GET … → 400: {"error": {"code": 400, '
                               '"message": "Unable to parse range: badges!A1:S20000"}}')

    _probe(Reachable())                       # 讀取時才發現分頁不存在 → 視為已連上


@pytest.mark.parametrize("message,expect", [
    ('Google API GET … → 400: {"error": {"code": 400, "message": "Unable to parse range: badges!A1:S20000"}}',
     "分頁還未建立"),
    ('Google API GET … → 400: {"error": {"code": 400, "message": "Invalid spreadsheet id value: 123"}}',
     "GOOGLE_SHEET_ID 不完整"),
    ("RuntimeError: Google API GET … → 400: some other bad request", "400"),
])
def test_the_four_hundreds_are_explained_in_plain_language(message, expect):
    reason, advice = storage_advice(message)
    assert expect in reason, reason
    assert advice, "每一種都要有「怎樣做」"


def test_a_pasted_url_instead_of_an_id_is_refused_by_name(monkeypatch):
    monkeypatch.setattr(store_module, "_sheets_driver", store_module._sheets_driver)
    with pytest.raises(ValueError) as caught:
        store_module._sheets_driver({
            "GOOGLE_SHEET_ID": "https://docs.google.com/spreadsheets/d/1AbCdef/edit",
            "GOOGLE_SERVICE_ACCOUNT_JSON": json.dumps(
                {"client_email": "svc@x.iam.gserviceaccount.com", "private_key": "k"}),
        })
    assert "中間那一小段" in str(caught.value)
