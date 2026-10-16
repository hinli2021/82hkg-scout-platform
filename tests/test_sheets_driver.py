"""
The Google Sheets driver, exercised against a fake Sheets + Drive API.

Nothing here touches the network — the driver's own transport is replaced — but
everything above it is real: tab creation, the header row, JSON-in-cell, typed
values coming back, targeted range writes and the short read cache.
"""
from __future__ import annotations

import json
import re

import pytest

from scout.drivers.sheets import CACHE_SECONDS, SheetsDriver, _column_letter
from scout.schema import COLLECTION_ORDER, COLLECTIONS


class FakeGoogle:
    """Pretends to be the Sheets v4 and Drive v3 endpoints the driver calls."""

    def __init__(self):
        self.tabs: dict[str, list[list]] = {}
        self.calls: list[tuple[str, str]] = []
        self.uploads: list[bytes] = []
        self.permissions: list[str] = []

    def api(self, url: str, method: str = "GET", body=None, raw=None, content_type="application/json"):
        self.calls.append((method, url))
        path = url.split("?")[0]

        if method == "GET" and "/values/" in path:
            tab, cell_range = _split_range(url)
            if tab not in self.tabs:
                # exactly what Google answers for a tab that does not exist yet
                raise RuntimeError(
                    f'Google API GET {url} → 400: {{"error": {{"code": 400, "message": '
                    f'"Unable to parse range: {tab}!{cell_range}"}}}}')
            grid = self.tabs.get(tab, [])
            start = re.search(r"[A-Z]+(\d+)", cell_range)
            first = int(start.group(1)) if start else 1
            return {"values": grid[first - 1:]}

        if method == "GET" and "/spreadsheets/" in path and "/values/" not in path:
            return {"sheets": [{"properties": {"title": title}} for title in self.tabs]}

        if method == "POST" and path.endswith("/values:batchUpdate"):
            for entry in (body or {}).get("data", []):
                _reject_non_scalars(url, entry.get("values", []))
            for entry in (body or {}).get("data", []):
                tab, _, cell_range = entry["range"].partition("!")
                if tab not in self.tabs:
                    raise RuntimeError(
                        f'Google API POST {url} → 400: {{"error": {{"code": 400, "message": '
                        f'"Unable to parse range: {entry["range"]}"}}}}')
                grid = self.tabs[tab]
                match = re.search(r"([A-Z]+)(\d+)", cell_range)
                row_number = int(match.group(2))
                while len(grid) < row_number:
                    grid.append([])
                for offset, row_values in enumerate(entry.get("values", [])):
                    row = grid[row_number - 1 + offset]
                    for index, value in enumerate(row_values):
                        while len(row) <= index:
                            row.append("")
                        row[index] = value
            return {"totalUpdatedCells": sum(len(entry.get("values", [[]])[0])
                                             for entry in (body or {}).get("data", []))}

        if method == "POST" and path.endswith(":batchUpdate"):
            for request in (body or {}).get("requests", []):
                title = request["addSheet"]["properties"]["title"]
                self.tabs.setdefault(title, [])
            return {"replies": []}

        if method == "PUT" and "/values/" in path:
            _reject_non_scalars(url, (body or {}).get("values", []))
            tab, cell_range = _split_range(url)
            match = re.search(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", cell_range)
            col_start = _col_index(match.group(1))
            row_start, row_end = int(match.group(2)), int(match.group(4))
            grid = self.tabs.setdefault(tab, [])
            while len(grid) < row_end:
                grid.append([])
            for offset, row_values in enumerate((body or {}).get("values", [])):
                row = grid[row_start - 1 + offset]
                for index, value in enumerate(row_values):
                    column = col_start + index
                    while len(row) <= column:
                        row.append("")
                    row[column] = value
            return {"updatedRows": len((body or {}).get("values", []))}

        if method == "POST" and "upload/drive" in url:
            self.uploads.append(raw or b"")
            return {"id": "drive-file-1", "webViewLink": "https://drive.google.com/file/d/drive-file-1/view"}

        if method == "POST" and "/permissions" in path:
            self.permissions.append(path)
            return {}

        raise AssertionError(f"unexpected call: {method} {url}")



def _reject_non_scalars(url, values):
    """Google accepts only strings, numbers, booleans and null in a values write."""
    for row in values or []:
        for cell in (row if isinstance(row, list) else [row]):
            if isinstance(cell, (dict, list, tuple)):
                detail = 'Invalid value at data.values[0][0]: ' + type(cell).__name__ + ' object'
                raise RuntimeError('Google API PUT ' + url + ' -> 400: ' + detail)


def _split_range(url: str) -> tuple[str, str]:
    """…/values/<tab>!<A1 range>?query  →  ("tab", "A1 range")"""
    range_part = url.split("/values/")[1].partition("?")[0]
    tab, _, cell_range = range_part.partition("!")
    return tab, cell_range


def cell(fake, tab: str, row_number: int, field: str):
    """Read one cell the way a human would: find the column by its header."""
    grid = fake.tabs[tab]
    column = grid[0].index(field)
    row = grid[row_number - 1]
    return row[column] if column < len(row) else ""


def _col_index(letters: str) -> int:
    index = 0
    for char in letters:
        index = index * 26 + (ord(char) - 64)
    return index - 1


@pytest.fixture()
def fake():
    return FakeGoogle()


@pytest.fixture()
def sheets(fake, monkeypatch):
    driver = SheetsDriver("sheet-123", {"client_email": "svc@example.iam.gserviceaccount.com",
                                        "private_key": "x", "project_id": "p"})
    monkeypatch.setattr(driver, "_api", fake.api)
    return driver


# ── ranges and marshalling ──────────────────────────────────────────────────

def test_column_letters():
    assert _column_letter(1) == "A"
    assert _column_letter(26) == "Z"
    assert _column_letter(27) == "AA"


def test_json_and_typed_values_round_trip(sheets):
    cell = sheets._to_cell("config_json", {"questions": [{"q_zh": "一"}]})
    assert isinstance(cell, str) and json.loads(cell)["questions"][0]["q_zh"] == "一"
    assert sheets._from_cell("config_json", cell)["questions"][0]["q_zh"] == "一"
    assert sheets._from_cell("prerequisite_badge_ids", '["a","b"]') == ["a", "b"]
    assert sheets._from_cell("prerequisite_badge_ids", "") == []
    assert sheets._from_cell("show_on_leaderboard", "true") is True
    assert sheets._from_cell("show_on_leaderboard", "") is False
    assert sheets._from_cell("points", "42") == 42
    assert sheets._from_cell("points", "") == 0
    assert sheets._to_cell("active", True) == "true"


# ── the spreadsheet itself ──────────────────────────────────────────────────

def test_first_run_creates_one_tab_per_collection(sheets, fake):
    sheets.ensure_schema()
    assert set(fake.tabs) == set(COLLECTION_ORDER)
    # and writes the header row each collection expects
    for collection in ("users", "tasks", "points_ledger"):
        header = fake.tabs[collection][0]
        assert header == list(COLLECTIONS[collection]["fields"])


def test_existing_tabs_are_left_alone(sheets, fake):
    fake.tabs["users"] = [["id", "role"], ["u1", "scout"]]
    sheets.ensure_schema()
    assert fake.tabs["users"][0] == ["id", "role"]        # not overwritten


def test_insert_appends_a_row_and_reads_back(sheets, fake):
    sheets.ensure_schema()
    created = sheets.insert("badges", {
        "title_zh": "會員章", "title_en": "Membership", "code": "SC-01",
        "order_index": 1, "points_reward": 50, "prerequisite_badge_ids": [],
        "status": "published", "emoji": "🎖",
    })
    assert created["id"]
    assert cell(fake, "badges", 2, "title_zh") == "會員章"
    assert str(cell(fake, "badges", 2, "points_reward")) == "50"
    back = sheets.get("badges", created["id"])
    assert back["title_zh"] == "會員章"
    assert int(back["points_reward"]) == 50
    assert back["prerequisite_badge_ids"] == []


def test_insert_keeps_json_in_a_single_cell(sheets, fake):
    sheets.ensure_schema()
    task = sheets.insert("tasks", {
        "badge_id": "b1", "title_zh": "小測驗", "type": "quiz", "points": 10,
        "config_json": {"questions": [{"q_zh": "一", "q_en": "one", "answer": 1,
                                       "options": [{"zh": "A", "en": "A"}]}]},
        "status": "published",
    })
    assert json.loads(cell(fake, "tasks", 2, "config_json"))["questions"][0]["answer"] == 1
    assert sheets.get("tasks", task["id"])["config_json"]["questions"][0]["q_zh"] == "一"


def test_list_skips_blank_rows(sheets, fake):
    sheets.ensure_schema()
    first = sheets.insert("rewards", {"title_zh": "獎品一", "points_cost": 10})
    sheets.insert("rewards", {"title_zh": "獎品二", "points_cost": 20})
    sheets.remove("rewards", first["id"])                  # blanks the row
    rows = sheets.list("rewards")
    assert [row["title_zh"] for row in rows] == ["獎品二"]


def test_update_writes_only_that_row(sheets, fake):
    sheets.ensure_schema()
    a = sheets.insert("announcements", {"title_zh": "第一則"})
    b = sheets.insert("announcements", {"title_zh": "第二則"})
    fake.calls.clear()
    sheets.update("announcements", b["id"], {"title_zh": "第二則（更新）", "pinned": True})
    writes = [call for call in fake.calls if call[0] == "PUT"]
    assert len(writes) == 1
    assert "announcements!A3:" in writes[0][1]             # row 3, not a rewrite
    assert cell(fake, "announcements", 2, "title_zh") == a["title_zh"]
    assert cell(fake, "announcements", 3, "title_zh") == "第二則（更新）"
    assert cell(fake, "announcements", 3, "pinned") in (True, "true")


def test_update_rejects_an_unknown_key(sheets):
    sheets.ensure_schema()
    assert sheets.update("badges", "nope", {"title_zh": "x"}) is None


def test_remove_where(sheets, fake):
    sheets.ensure_schema()
    sheets.insert("users", {"role": "scout", "username": "a"})
    sheets.insert("users", {"role": "leader", "username": "b"})
    removed = sheets.remove_where("users", lambda row: row.get("role") == "scout")
    assert removed == 1
    assert [row["username"] for row in sheets.list("users")] == ["b"]


def test_reads_are_cached_for_a_short_while(sheets, fake):
    sheets.ensure_schema()
    sheets.insert("suggestions", {"title_zh": "建議"})
    fake.calls.clear()
    sheets.list("suggestions")
    sheets.list("suggestions")
    reads = [call for call in fake.calls if call[0] == "GET"]
    assert len(reads) == 1, "the second read should come from the cache"
    assert CACHE_SECONDS >= 5, "…but the cache must be short-lived"


def test_a_write_invalidates_the_cache(sheets, fake):
    sheets.ensure_schema()
    sheets.insert("suggestions", {"title_zh": "第一"})
    sheets.insert("suggestions", {"title_zh": "第二"})
    assert len(sheets.list("suggestions")) == 2


# ── Drive uploads ───────────────────────────────────────────────────────────

def test_upload_goes_to_drive_and_is_shared(sheets, fake):
    sheets.drive_folder_id = "folder-9"
    result = sheets.upload_file(name="proof.jpg", mime_type="image/jpeg", data=b"\xff\xd8\xff\xe0photo")
    assert result["stored"] == "drive"
    assert result["url"] == "https://drive.google.com/file/d/drive-file-1/view"
    assert fake.uploads and b"photo" in fake.uploads[0]
    body = fake.uploads[0]
    assert b'"parents": ["folder-9"]' in body
    assert fake.permissions, "the file should be shared so the unit can open it"


def test_upload_without_a_folder_still_works(sheets, fake):
    result = sheets.upload_file(name="p.jpg", mime_type="image/jpeg", data=b"x")
    assert result["id"] == "drive-file-1"
    assert b"parents" not in fake.uploads[0]


def test_missing_configuration_is_reported_clearly():
    with pytest.raises(ValueError, match="GOOGLE_SHEET_ID"):
        SheetsDriver("", {"client_email": "a@b.c"})
    with pytest.raises(ValueError, match="service account"):
        SheetsDriver("sheet-1", {})


def test_driver_reports_its_name(sheets):
    assert sheets.name == "sheets"


def test_store_round_trips_through_the_sheets_driver(sheets):
    """The whole Store works with Google Sheets underneath, not just the driver."""
    from scout.engine import progress_for
    from scout.store import Store

    sheets.ensure_schema()          # a real deployment creates the tabs on boot
    store = Store(driver=sheets, config={"demo_login": True, "seed_demo": True, "data_dir": "/tmp"})
    store.seed_demo()
    scout = next(u for u in store.list("users") if u["username"] == "scout03")
    progress = progress_for(store, scout["id"])
    # 11 items of 會員章 + 6 from the later awards
    assert progress["overall"]["tasks_total"] == len(store.list("tasks"))
    assert progress["overall"]["tasks_total"] == 17
    assert progress["stats"]["tasks_done"] >= 1
    assert progress["stats"]["badges_done"] == 0        # nothing earned in the seed
    # a settings write comes back through the same path
    store.save_setting("unit_name_zh", "雲端旅團")
    assert store.settings(force=True)["unit_name_zh"] == "雲端旅團"


# ── the local driver notices edits made outside the process ────────────────

def test_local_driver_picks_up_changes_made_on_disk(tmp_path):
    """Hand-editing the JSON (or a script doing a demo reset) must show up.

    The running server used to keep its own copy, so a reset done from another
    process was invisible — the first-time demo showed a password box instead
    of the "create a password" page.
    """
    from scout.drivers.local import LocalDriver

    driver = LocalDriver(str(tmp_path))
    driver.ensure_schema()
    driver.insert("users", {"id": "u1", "role": "scout", "username": "scout07",
                            "password_hash": "x", "password_salt": "y"})
    assert driver.get("users", "u1")["password_hash"] == "x"          # cached

    # …now somebody edits the file behind the driver's back
    path = tmp_path / "db" / "users.json"
    rows = json.loads(path.read_text())
    rows[0]["password_hash"] = ""
    path.write_text(json.dumps(rows, ensure_ascii=False))

    assert driver.get("users", "u1")["password_hash"] == ""           # seen
    assert driver.list("users")[0]["password_hash"] == ""


def test_local_driver_still_caches_when_the_file_is_untouched(tmp_path):
    from scout.drivers.local import LocalDriver

    driver = LocalDriver(str(tmp_path))
    driver.ensure_schema()
    driver.insert("users", {"id": "u1", "role": "scout", "username": "a"})
    first = driver._read("users")
    assert driver._read("users") is first          # same object: no re-read

# ── the whole platform on a Sheet: first run, then the leader console ──────

def test_a_fresh_sheet_asks_for_the_first_leader_and_then_stores_everything(fake):
    """正式上線的完整路徑：空試算表 → 建立第一位領袖 → 資料寫在試算表裡。

    沒有任何示範帳戶（DEMO_LOGIN / SEED_DEMO 都關），所以第一次開啟一定是
    「建立第一位領袖」；建立之後領袖後台要顯示資料存放的位置，而不是暫存警告。
    """
    import pathlib as _pathlib
    import sys

    sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent.parent))
    from app import create_app                                      # noqa: E402
    from scout.store import Store                                   # noqa: E402

    driver = SheetsDriver("sheet-123", {"client_email": "svc@example.iam.gserviceaccount.com",
                                        "private_key": "x", "project_id": "p"})
    driver._api = fake.api
    store = Store(driver=driver, config={"demo_login": False, "seed_demo": False,
                                         "data_dir": "/tmp"})
    driver.ensure_schema()

    client = create_app({"STORE": store, "TESTING": True,
                         "SECRET_KEY": "t"}).test_client()

    first = client.get("/", follow_redirects=True)
    body = first.get_data(as_text=True)
    assert first.status_code == 200 and "建立第一位領袖" in body
    assert "示範帳戶" not in body, "正式站不應出現示範帳戶"

    made = client.post("/setup", data={
        "unit_zh": "港島第八十二旅童軍團", "name_zh": "陳大文",
        "username": "leader1", "password": "harbour-82", "password2": "harbour-82",
    }, follow_redirects=False)
    assert made.status_code == 302 and "/leader" in made.headers["Location"]

    # 資料真的在試算表：users 分頁有領袖那一列
    users_tab = [row for row in (fake.tabs.get("users") or [])]
    assert any("leader1" in json.dumps(row, ensure_ascii=False) for row in users_tab)

    settings = client.get("/leader/settings").get_data(as_text=True)
    assert "資料存放於 Google 試算表" in settings
    assert "docs.google.com/spreadsheets/d/sheet-123/edit" in settings
    assert "資料暫存中" not in settings, "接了試算表就不應再顯示暫存警告"
