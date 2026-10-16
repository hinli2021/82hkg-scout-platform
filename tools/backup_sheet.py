#!/usr/bin/env python3
"""把整份 Google 試算表複製一份到電腦（**只讀，不會改動試算表**）。

每次更新平台之前，先跑一次這個。它給你一個可以隨時翻查的存檔，
即使最壞情況發生（例如誤刪分頁），也有一份完整的資料在手。

    export DATA_DRIVER=sheets
    export GOOGLE_SHEET_ID=1AbC…xyz
    export GOOGLE_SERVICE_ACCOUNT_FILE=./service-account.json
    python3 tools/backup_sheet.py

它會做四件事：

1. 讀出試算表內**所有分頁**（包括平台不認識、你自己加的分頁）的每一格
2. 寫到 `backups/sheet-<日期>-<時間>/`：每個分頁一個 `.csv`，
   加一份 `all-tabs.json`（完整備份）和 `manifest.txt`（指紋）
3. 跟**上一次**的備份比較，列出每個分頁多了／少了幾列
4. 印出存檔位置，並回報 `BACKUP OK`

試算表本身也有兩個免費保命功能（見 docs/06-safe-updates.md）：
「檔案 → 版本記錄」可以回到任何時間點，「檔案 → 建立副本」則多一份線上備份。

備份檔含童軍姓名等個人資料，**不要**上傳到 GitHub（`.gitignore` 已經排除 `backups/`）。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import pathlib
import sys
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MAX_ROWS = 20000          # 每個分頁最多讀幾列（遠超一個旅團的需要）
LAST_COLUMN = "ZZ"


# --- 讀取 -------------------------------------------------------------------
def open_driver(env: dict | None = None):
    """建立一個只讀的 Google Sheets 連線（不會建立分頁、不會寫入）。"""
    env = env if env is not None else os.environ
    from scout.drivers.sheets import SheetsDriver

    account: dict = {}
    path = env.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            account = json.load(handle)
    elif env.get("GOOGLE_SERVICE_ACCOUNT_JSON"):
        account = json.loads(env["GOOGLE_SERVICE_ACCOUNT_JSON"])
    else:
        raise FileNotFoundError("找不到服務帳戶金鑰（GOOGLE_SERVICE_ACCOUNT_FILE / _JSON）")

    sheet_id = (env.get("GOOGLE_SHEET_ID") or "").strip()
    if not sheet_id:
        raise ValueError("未設定 GOOGLE_SHEET_ID")
    return SheetsDriver(spreadsheet_id=sheet_id, service_account=account,
                        drive_folder_id=env.get("GOOGLE_DRIVE_FOLDER_ID", ""))


def tab_titles(driver) -> list[str]:
    """試算表裡現有的分頁名稱，按試算表的次序。"""
    from scout.drivers.sheets import SHEETS_API

    meta = driver._api(f"{SHEETS_API}/{driver.spreadsheet_id}?fields=sheets.properties.title")
    return [sheet["properties"]["title"] for sheet in meta.get("sheets", [])]


def read_tab(driver, title: str) -> list[list[str]]:
    from scout.drivers.sheets import SHEETS_API

    rng = f"{title}!A1:{LAST_COLUMN}{MAX_ROWS}"
    data = driver._api(f"{SHEETS_API}/{driver.spreadsheet_id}/values/{rng}")
    return [[str(cell) for cell in row] for row in (data.get("values") or [])]


def grab(driver) -> dict[str, list[list[str]]]:
    """所有分頁的原樣內容。"""
    return {title: read_tab(driver, title) for title in tab_titles(driver)}


# --- 寫檔 -------------------------------------------------------------------
def safe_name(title: str) -> str:
    keep = [character if character not in '/\\:*?"<>|' else "_" for character in title]
    return "".join(keep).strip() or "tab"


def unique_dir(path: pathlib.Path) -> pathlib.Path:
    """永遠不覆蓋既有存檔：同一分鐘內跑兩次也不會蓋掉上一份。

    更新前後的比較全靠兩份存檔；如果第二份蓋掉第一份，就等於沒有備份。
    """
    if not path.exists() or not any(path.iterdir()):
        return path
    for suffix in range(2, 100):
        candidate = path.with_name(f"{path.name}-{suffix}")
        if not candidate.exists() or not any(candidate.iterdir()):
            return candidate
    raise RuntimeError(f"存檔資料夾太多同名：{path}")


def write_backup(tabs: dict[str, list[list[str]]], out_dir: pathlib.Path) -> dict:
    out_dir = unique_dir(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(tabs, ensure_ascii=False, indent=1, sort_keys=True)
    (out_dir / "all-tabs.json").write_text(payload, encoding="utf-8")

    counts: dict[str, int] = {}
    for title, rows in tabs.items():
        counts[title] = max(0, len(rows) - 1)
        with (out_dir / f"{safe_name(title)}.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            csv.writer(handle).writerows(rows)

    fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    lines = [
        f"試算表存檔　{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"分頁數：{len(tabs)}　指紋：{fingerprint}",
        "",
        *[f"{counts[title]:>6} 列　{title}" for title in tabs],
    ]
    (out_dir / "manifest.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"dir": out_dir, "fingerprint": fingerprint, "counts": counts}


def previous_backup(parent: pathlib.Path, current: pathlib.Path) -> pathlib.Path | None:
    others = sorted(
        (folder for folder in parent.glob("sheet-*")
         if folder.is_dir() and folder != current and (folder / "all-tabs.json").exists()),
        key=lambda folder: (folder.stat().st_mtime, folder.name),
    )
    return others[-1] if others else None


def compare(previous: pathlib.Path, current: dict) -> list[str]:
    """跟上一次備份比，列出每個分頁的增減。"""
    before_file = previous / "all-tabs.json"
    if not before_file.exists():
        return [f"（上一次存檔 {previous.name} 沒有 all-tabs.json，略過比較）"]
    before = json.loads(before_file.read_text(encoding="utf-8"))
    after = json.loads((current["dir"] / "all-tabs.json").read_text(encoding="utf-8"))
    lines: list[str] = []
    for title in sorted(set(before) | set(after)):
        was = max(0, len(before.get(title, [])) - 1)
        now = max(0, len(after.get(title, [])) - 1)
        if title not in before:
            lines.append(f"＋ 新分頁　{title}（{now} 列）")
        elif title not in after:
            lines.append(f"－ 分頁不見了　{title}（原本 {was} 列）")
        elif was != now:
            sign = "＋" if now > was else "－"
            lines.append(f"{sign} {title}：{was} → {now} 列（{sign}{abs(now - was)}）")
    same = json.dumps(before, ensure_ascii=False, sort_keys=True) == json.dumps(after, ensure_ascii=False, sort_keys=True)
    if not lines:
        lines.append("所有分頁的列數都沒有變（內容可能有編輯，例如改標題、改分數）")
    if same:
        lines = ["跟上次備份完全一樣。"]
    return lines


# --- 主程式 -----------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把整份 Google 試算表存一份到 backups/")
    parser.add_argument("--out", default="", help="存檔位置（預設 backups/sheet-<日期>-<時間>）")
    parser.add_argument("--root", default=str(ROOT), help="相對於哪個資料夾（預設：專案根目錄）")
    parser.add_argument("--quiet", action="store_true", help="只印結果")
    args = parser.parse_args(argv)

    root = pathlib.Path(args.root).resolve()
    folder = pathlib.Path(args.out) if args.out else \
        root / "backups" / datetime.now().strftime("sheet-%Y-%m-%d_%H%M%S")
    folder = unique_dir(folder)

    if not args.quiet:
        print("── 連接試算表（只讀）──")
    try:
        driver = open_driver()
        tabs = grab(driver)
    except FileNotFoundError as exc:
        print(f"  FAIL {exc}")
        print("        本機請設 GOOGLE_SERVICE_ACCOUNT_FILE；或先照 docs/02-google-sheets-setup.md 做。")
        return 1
    except ValueError as exc:
        print(f"  FAIL {exc}")
        return 1
    except Exception as exc:                                    # noqa: BLE001
        print(f"  FAIL 讀取失敗：{type(exc).__name__}: {exc}")
        print("        403 通常是試算表沒有共用給服務帳戶電郵；網路問題可再試一次。")
        return 2

    if not tabs:
        print("  FAIL 試算表裡面沒有任何分頁 —— 檢查 GOOGLE_SHEET_ID 是否指向正確的檔案。")
        return 2

    made = write_backup(tabs, folder)

    if not args.quiet:
        print(f"  ok   讀到 {len(tabs)} 個分頁，共 {sum(made['counts'].values())} 列")
        for title, count in made["counts"].items():
            print(f"       {count:>6} 列　{title}")

        earlier = previous_backup(folder.parent, folder)
        print("\n── 與上一次備份比較 ──")
        if earlier:
            print(f"       上一次：{earlier.name}")
            for line in compare(earlier, made):
                print("       " + line)
        else:
            print("       這是第一份備份，沒有可比較的存檔。")

    print()
    print(f"BACKUP OK — 存檔位置：{folder}")
    print(f"           指紋：{made['fingerprint'][:16]}…")
    print("           試算表沒有被改動（這個工具只讀）。")
    print("           更新平台之前先跑一次；更新之後再跑一次，就會告訴你資料增減。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
