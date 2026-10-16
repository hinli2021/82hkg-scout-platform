#!/usr/bin/env python3
"""Prove the Google Sheet connection before anyone relies on it.

    export DATA_DRIVER=sheets
    export GOOGLE_SHEET_ID=1AbC…xyz
    export GOOGLE_SERVICE_ACCOUNT_FILE=./service-account.json   # 或 _JSON=…
    export GOOGLE_DRIVE_FOLDER_ID=1XyZ…                         # 可選
    python3 tools/check_sheets.py

It answers, in order, the four things that usually go wrong:

1. is the service-account JSON readable?
2. can the platform open the spreadsheet at all? (shared with the robot email?)
3. can it create the 15 tabs and write a row? (editor permission?)
4. can it write and delete a photo in the Drive folder? (optional)

Nothing is changed beyond creating missing tabs and one scratch setting that is
removed again. Run it on a laptop with the same environment variables Vercel
has; when it prints ALL GOOD, the deployment will work too.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OK = "  ok   "
BAD = "  FAIL "


def main() -> int:
    env = os.environ
    sheet_id = (env.get("GOOGLE_SHEET_ID") or "").strip()
    folder_id = (env.get("GOOGLE_DRIVE_FOLDER_ID") or "").strip()
    has_file = bool((env.get("GOOGLE_SERVICE_ACCOUNT_FILE") or "").strip())
    has_json = bool((env.get("GOOGLE_SERVICE_ACCOUNT_JSON") or "").strip())
    problems: list[str] = []

    def say(good: bool, message: str, fix: str = "") -> None:
        print((OK if good else BAD) + message)
        if not good:
            problems.append(message + (f" — {fix}" if fix else ""))

    print("── 1. 環境變數 ──")
    say(env.get("DATA_DRIVER", "").lower() == "sheets",
        f"DATA_DRIVER={env.get('DATA_DRIVER') or '(未設定)'}",
        "設 DATA_DRIVER=sheets（Vercel 上同樣要設）")
    say(bool(sheet_id), f"GOOGLE_SHEET_ID={'…' + sheet_id[-6:] if sheet_id else '(未設定)'}",
        "由試算表網址 /d/<這一段>/edit 複製")
    say(has_file or has_json,
        "服務帳戶金鑰：" + ("檔案" if has_file else "") + ("＋" if has_file and has_json else "")
        + ("JSON 變數" if has_json else "" if has_file else "(未設定)"),
        "設 GOOGLE_SERVICE_ACCOUNT_FILE（本機）或 GOOGLE_SERVICE_ACCOUNT_JSON（Vercel）")
    if has_file:
        path = pathlib.Path(env["GOOGLE_SERVICE_ACCOUNT_FILE"])
        ok = path.exists()
        say(ok, f"金鑰檔案：{path}" + ("" if ok else "（找不到）"),
            "確認路徑，或改用 GOOGLE_SERVICE_ACCOUNT_JSON")
        if ok:
            try:
                account = json.loads(path.read_text(encoding="utf-8"))
                say(bool(account.get("client_email")) and bool(account.get("private_key")),
                    f"金鑰內容可用：{account.get('client_email', '(沒有 client_email)')}",
                    "重新下載服務帳戶的 JSON 金鑰")
            except ValueError as exc:
                say(False, f"金鑰不是有效 JSON：{exc}", "重新下載一次金鑰")
    if not sheet_id or not (has_file or has_json):
        print("\n先補好上面幾項，再跑一次。")
        return 1

    print("\n── 2. 連接試算表 ──")
    from scout.store import Store

    try:
        store = Store.from_env()
    except Exception as exc:                                  # noqa: BLE001
        say(False, f"建立連線失敗：{type(exc).__name__}: {exc}",
            "檢查金鑰內容與 GOOGLE_SHEET_ID；403 通常是未分享試算表給服務帳戶電郵")
        return 1
    say(store.driver.name == "sheets", f"驅動程式：{store.driver.name}",
        "設 DATA_DRIVER=sheets")

    try:
        store.driver.ensure_schema()
        say(True, "分頁已建立（缺少的會自動補上，共 15 個）")
    except Exception as exc:                                  # noqa: BLE001
        say(False, f"建立分頁失敗：{type(exc).__name__}: {exc}",
            "把試算表共用給服務帳戶電郵（編輯者）：console 的 403 就是這一項")
        return 1

    print("\n── 3. 讀寫測試 ──")
    try:
        rows = store.list("users")
        leaders = [r for r in rows if r.get("role") == "leader"]
        say(True, f"讀取成功：users 分頁 {len(rows)} 列，其中領袖 {len(leaders)} 位")
        if not leaders:
            print("        ↳ 還沒有領袖帳戶 —— 部署後第一次開啟會顯示「建立第一位領袖」。")
    except Exception as exc:                                  # noqa: BLE001
        say(False, f"讀取失敗：{type(exc).__name__}: {exc}", "確認已分享試算表")
        return 1

    from scout.util import now_iso

    try:
        store.insert("settings", {"key": "check_sheets_probe", "value_json": now_iso(),
                                  "updated_at": now_iso()})
        store.remove_where("settings", lambda row: row.get("key") == "check_sheets_probe")
        say(True, "寫入並刪除測試列成功（資料可以保存）")
    except Exception as exc:                                  # noqa: BLE001
        say(False, f"寫入失敗：{type(exc).__name__}: {exc}",
            "試算表權限要是「編輯者」，不是「檢視者」")
        return 1

    print("\n── 4. 相片資料夾（可選）──")
    if folder_id:
        try:
            store.driver.upload_file(name="check-sheets-probe.txt", mime_type="text/plain",
                                     data=b"scout platform probe\n")
            say(True, f"相片上載測試成功（{folder_id[:12]}…）")
        except Exception as exc:                              # noqa: BLE001
            say(False, f"上載失敗：{type(exc).__name__}: {exc}",
                "把 Drive 資料夾共用給服務帳戶電郵（編輯者），或留空 GOOGLE_DRIVE_FOLDER_ID")
    else:
        print("  skip 未設定 GOOGLE_DRIVE_FOLDER_ID —— 童軍相片會放到服務帳戶自己的 Drive。")

    print()
    if problems:
        print(f"{len(problems)} 項要處理：")
        for item in problems:
            print("  -", item)
        return 1
    print("ALL GOOD — 試算表已經接通，平台可以把資料寫進去。")
    print("Vercel 上把同樣的環境變數設好，Redeploy 一次即可。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
