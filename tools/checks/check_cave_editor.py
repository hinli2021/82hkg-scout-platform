"""Browser smoke test for the leader-only, one-question-at-a-time cave editor.

    LD_LIBRARY_PATH=/tmp/syslibs python3 tools/checks/check_cave_editor.py [base_url] [--fast]

Checks the code-only leader door, all four wall groups, 50 stable IDs, the
question/answer fields, bilingual navigation and a phone-sized layout. It does
NOT submit edits or change scout progress. Unless --fast, saves one screenshot
in docs/screens/leader-cave-editor.png.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

LIBS = subprocess.run("find /tmp/syslibs -name '*.so*' -printf '%h\\n' | sort -u | tr '\\n' ':'",
                      shell=True, capture_output=True, text=True).stdout
os.environ["LD_LIBRARY_PATH"] = LIBS + os.environ.get("LD_LIBRARY_PATH", "")
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = next((x for x in sys.argv[1:] if not x.startswith("--")), "http://127.0.0.1:5001")
FAST = "--fast" in sys.argv
SHOTS = ROOT / "docs" / "screens"


def main():
    rows = json.loads((ROOT / "data/db/tasks.json").read_text(encoding="utf-8"))
    task = next(row for row in rows if row.get("code") == "M04")
    questions = task["config_json"]["questions"]
    assert len(questions) == 50
    groups = json.loads((ROOT / "content/member-badge/cave.json").read_text(encoding="utf-8"))["groups"]
    last_id = groups[-1]["questions"][-1]
    last_index = next(i for i, q in enumerate(questions) if q["id"] == last_id)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900}, locale="zh-HK")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE + "/login/leader")
        page.locator('input[name="password"]').fill("0082")
        page.locator('form[action="/login/leader"] button[type="submit"]').click()
        page.wait_for_url("**/leader*")
        print("leader: entered with code 0082")

        page.goto(BASE + "/leader/content")
        page.locator('a.btn[href*="/cave-questions"]').first.click()
        page.wait_for_load_state("networkidle")
        assert page.locator(".cave-editor-index details").count() == 4
        links = page.locator(".cave-editor-link")
        assert links.count() == 50
        assert page.locator('input[name="question_id"]').input_value() == questions[0]["id"]
        assert page.locator('input[name="answer"]:checked').input_value() == str(questions[0]["answer"])
        assert page.locator('input[name="option_0_zh"]').get_attribute("required") is not None
        assert page.locator('input[name="option_3_zh"]').get_attribute("required") is None
        assert page.locator('textarea[name="q_en"]').input_value()
        assert page.locator('textarea[name="explain_zh"]').input_value()
        if not FAST:
            SHOTS.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOTS / "leader-cave-editor.png"), full_page=True)
        print("editor: 4 walls, 50 selectable IDs, bilingual question and recap, correct-answer control")

        links.nth(49).click()
        assert page.locator('input[name="question_id"]').input_value() == last_id
        assert f"q={last_index}" in page.url
        assert "50 / 50" in page.locator(".cave-editor-form .chip").inner_text()
        page.locator('.lang-switch a', has_text="EN").click()
        assert page.locator('html').get_attribute('lang') == "en"
        assert page.locator('input[name="question_id"]').input_value() == last_id
        assert "Edit cave questions" in page.locator("h1").inner_text()
        print("question 50: retained after switching to English")

        page.set_viewport_size({"width": 390, "height": 844})
        assert page.locator(".cave-editor-index").is_visible()
        assert page.locator(".cave-editor-form").is_visible()
        widths = page.evaluate("({viewport: innerWidth, document: document.documentElement.scrollWidth})")
        print("mobile:", widths)
        assert not errors, f"browser errors: {errors[:3]}"
        browser.close()
    print("console errors: none; no question edited")


if __name__ == "__main__":
    main()
