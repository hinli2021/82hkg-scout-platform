#!/usr/bin/env python3
"""Compile every document into one file: docs/ALL-DOCS.md

The workspace holds the same story in eight markdown files (README, LAUNCH,
DEMO and docs/01–06). This tool stitches them into a single document with a
contents table and real anchors, so the whole manual can be read, printed or
handed over as one file — and so nothing depends on a folder still existing.

    cd scout-platform-py && python3 tools/compile_docs.py

Every section keeps its source path, so a reader can still find the original.
Run it again after editing any document.
"""
from __future__ import annotations

import datetime
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "ALL-DOCS.md"

# (source, 中文標題, English title) — order is the order a leader needs them
DOCS = [
    ("README.md", "總覽：這個平台是甚麼", "Overview — what this platform is"),
    ("LAUNCH.md", "上線步驟（一次做完）", "Going live, step by step"),
    ("docs/05-vercel.md", "部署到 Vercel", "Deploying to Vercel"),
    ("docs/02-google-sheets-setup.md", "試算表：所有人共用同一份資料", "Google Sheets as the shared database"),
    ("docs/03-email-setup.md", "電郵：重設密碼", "Email — password resets"),
    ("docs/04-github.md", "GitHub：備份與版本", "GitHub — backup and history"),
    ("docs/01-architecture.md", "架構與設計", "Architecture and design"),
    ("docs/06-safe-updates.md", "更新時，資料會不會受影響？", "Will an update touch the data?"),
    ("DEMO.md", "示範卡", "Demo card"),
]

HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def anchor(text: str) -> str:
    """GitHub-style anchor: lowercase, punctuation dropped, spaces → hyphens."""
    slug = text.strip().lower()
    slug = re.sub(r"[^\w\u4e00-\u9fff\- ]", "", slug)
    return slug.replace(" ", "-")


def demote(line: str) -> str:
    """Push every heading down one level, so the compiled file has one title."""
    match = HEADING.match(line)
    if not match:
        return line
    level = min(len(match.group(1)) + 1, 6)
    return "#" * level + " " + match.group(2)


def main() -> None:
    today = datetime.date.today().isoformat()
    parts: list[str] = []
    parts.append("# 港島第八十二旅童軍團 · 平台文件（合訂本）\n")
    parts.append("**82nd Hong Kong Group — Scout Platform: the complete manual**\n")
    parts.append(f"_由 `tools/compile_docs.py` 於 {today} 由各份文件自動合併；改動任何一份之後請重新執行。_\n")
    parts.append("_Compiled automatically from the individual documents below. Edit the source "
                 "file, then run the tool again._\n")
    parts.append("---\n")
    parts.append("## 目錄 · Contents\n")

    bodies: list[str] = []
    for index, (rel, title_zh, title_en) in enumerate(DOCS, start=1):
        path = ROOT / rel
        if not path.exists():
            bodies.append(f"<!-- {rel} 不存在 -->\n")
            continue
        heading = f"{index}. {title_zh} — {title_en}"
        parts.append(f"{index}. [{title_zh} — {title_en}](#{anchor(heading)})  \n　<sub>`{rel}`</sub>")
        raw = path.read_text(encoding="utf-8").strip("\n")
        lines = raw.splitlines()
        # drop the document's own H1 (it becomes the section heading below)
        if lines and lines[0].startswith("# "):
            lines = lines[1:]
        body = "\n".join(demote(line) for line in lines).strip("\n")
        bodies.append(
            f'\n<a id="{anchor(heading)}"></a>\n\n'
            f"## {heading}\n\n"
            f"<sub>來源 / source: `{rel}`</sub>\n\n"
            f"{body}\n\n---\n"
        )

    parts.append("")
    text = "\n".join(parts) + "\n" + "".join(bodies)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} — {len(text.splitlines())} lines, "
          f"{len(text)/1024:.0f} KB, {len(DOCS)} documents")


if __name__ == "__main__":
    main()
