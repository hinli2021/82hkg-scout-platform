"""存檔工具（tools/backup_sheet.py）本身的測試。

用假的 Google API 走一次完整流程：讀出所有分頁 → 寫成 CSV ＋ JSON →
假裝平台更新後資料多了幾列 → 再存一次並確認它報得出增減。
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from scout.drivers.sheets import SheetsDriver              # noqa: E402
from test_sheets_driver import FakeGoogle                   # noqa: E402
from tools.backup_sheet import compare, grab, write_backup   # noqa: E402


def driver_for(fake: FakeGoogle) -> SheetsDriver:
    driver = SheetsDriver("sheet-live", {"client_email": "svc@example.iam.gserviceaccount.com",
                                         "private_key": "x", "project_id": "p"})
    driver._api = fake.api
    return driver


def test_backup_saves_every_tab_including_ones_the_platform_does_not_know(tmp_path):
    fake = FakeGoogle()
    fake.tabs["users"] = [["id", "display_name_zh"], ["u1", "王小明"], ["u2", "陳小美"]]
    fake.tabs["badges"] = [["id", "title_zh"], ["b1", "會員章"]]
    fake.tabs["教練筆記"] = [["日期", "內容"], ["2026-10-16", "泳池活動"]]

    tabs = grab(driver_for(fake))
    assert set(tabs) == {"users", "badges", "教練筆記"}, "平台不認識的分頁也要備份"
    assert tabs["users"][1] == ["u1", "王小明"]

    made = write_backup(tabs, tmp_path / "sheet-2026-10-16_0000")
    folder = made["dir"]
    assert (folder / "all-tabs.json").exists() and (folder / "users.csv").exists()
    assert (folder / "教練筆記.csv").exists()
    assert made["counts"] == {"users": 2, "badges": 1, "教練筆記": 1}
    assert "王小明" in (folder / "all-tabs.json").read_text(encoding="utf-8")
    assert "王小明" in (folder / "users.csv").read_text(encoding="utf-8-sig")
    assert "users" in (folder / "manifest.txt").read_text(encoding="utf-8")
    assert len(made["fingerprint"]) == 64


def test_the_second_backup_reports_what_the_update_changed(tmp_path):
    fake = FakeGoogle()
    fake.tabs["progress_records"] = [["id", "user_id"], ["p1", "u1"]]
    fake.tabs["badges"] = [["id", "title_zh"], ["b1", "會員章"]]

    first = write_backup(grab(driver_for(fake)), tmp_path / "sheet-2026-10-16_1000")

    # 平台更新之後：童軍完成任務（多一列）、領袖刪走一個獎章
    fake.tabs["progress_records"].append(["p2", "u1"])
    fake.tabs["badges"] = [["id", "title_zh"]]

    second = write_backup(grab(driver_for(fake)), tmp_path / "sheet-2026-10-16_1100")
    lines = compare(first["dir"], second)

    assert any("progress_records" in line and "1 → 2" in line for line in lines), lines
    assert any("badges" in line and "1 → 0" in line for line in lines), lines
    assert first["fingerprint"] != second["fingerprint"]


def test_no_change_between_two_backups_says_so(tmp_path):
    fake = FakeGoogle()
    fake.tabs["users"] = [["id", "display_name_zh"], ["u1", "王小明"]]
    first = write_backup(grab(driver_for(fake)), tmp_path / "sheet-2026-10-16_1000")
    second = write_backup(grab(driver_for(fake)), tmp_path / "sheet-2026-10-16_1010")
    assert compare(first["dir"], second) == ["跟上次備份完全一樣。"]
    assert first["fingerprint"] == second["fingerprint"]


def test_a_stored_backup_can_be_read_back_as_json(tmp_path):
    """存檔要是可以重新讀入的 JSON —— 最壞情況靠它還原。"""
    fake = FakeGoogle()
    fake.tabs["users"] = [["id", "display_name_zh", "patrol"], ["u1", "王小明", "Tiger"]]
    made = write_backup(grab(driver_for(fake)), tmp_path / "sheet-2026-10-16_1000")

    restored = json.loads((made["dir"] / "all-tabs.json").read_text(encoding="utf-8"))
    assert restored["users"] == fake.tabs["users"]
