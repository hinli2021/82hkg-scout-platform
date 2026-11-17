#!/usr/bin/env python3
"""把現有資料複製到 Supabase，並留下一份 JSON 備份檔。

用途是「試用 Supabase 作主儲存」之前的安全複製：來源（正式的 Google
試算表，或本機資料）完全不會被改動；目的地用 upsert 寫入，工具重跑
一次也不會產生重複。

用法（在專案根目錄執行）：

    # 來源：正式試算表（沿用現有環境變數）
    DATA_DRIVER=sheets GOOGLE_SHEET_ID=... GOOGLE_SERVICE_ACCOUNT_JSON=... \\
    SUPABASE_URL=https://<專案>.supabase.co \\
    SUPABASE_SERVICE_ROLE_KEY=<service_role 金鑰> \\
        python3 tools/copy_to_supabase.py [--json 備份檔路徑] [--dry-run]

事前準備：在 Supabase 的 SQL Editor 執行一次 tools/supabase_schema.sql。
service_role 金鑰只應放在伺服器或這次指令的環境變數，不要存進 git，
不要貼到聊天或文件。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scout.schema import COLLECTION_ORDER            # noqa: E402
from scout.store import Store, _supabase_driver      # noqa: E402


def build_backup(source) -> dict:
    """整份資料的一個版本：每個分頁一個列表，加上匯出時間。"""
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "collections": {name: source.list(name) for name in COLLECTION_ORDER},
    }


def copy_store(source, target_driver) -> dict[str, int]:
    """把來源的每一列 upsert 到 Supabase；回傳每個分頁的列數。"""
    counts: dict[str, int] = {}
    for name in COLLECTION_ORDER:
        rows = source.list(name)
        if rows:
            target_driver.upsert_many(name, rows)
        counts[name] = len(rows)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="複製現有資料到 Supabase")
    parser.add_argument("--json", default="", help="JSON 備份檔路徑（預設 backup-supabase-<時間>.json）")
    parser.add_argument("--dry-run", action="store_true", help="只產生 JSON 備份檔和列數，不寫入 Supabase")
    args = parser.parse_args()

    source = Store.from_env()
    print(f"來源：{source.driver.name}（只讀，不會改動）")
    backup = build_backup(source)
    counts = {name: len(rows) for name, rows in backup["collections"].items()}

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    json_path = args.json or f"backup-supabase-{stamp}.json"
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(backup, handle, ensure_ascii=False, indent=2)
    print(f"JSON 備份檔：{json_path}")

    if args.dry_run:
        print("試行模式：沒有寫入 Supabase。")
    else:
        target = _supabase_driver(dict(os.environ))
        target.ensure_schema()
        copied = copy_store(source, target)
        assert copied == counts, (copied, counts)
        print("已寫入 Supabase。")
    for name in COLLECTION_ORDER:
        print(f"  {name}: {counts[name]} 列")
    print(f"合共 {sum(counts.values())} 列。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
