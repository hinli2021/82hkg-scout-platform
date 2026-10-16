"""
Store — the one thing the rest of the app talks to.

It wraps a driver (local JSON or Google Sheets) and adds the parts that are the
same in both: settings merged over defaults, cached per-user stats, file
uploads, and the demo seeder.
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable

from .drivers.local import LocalDriver
from .drivers.sheets import SheetsDriver
from .schema import (
    COLLECTION_ORDER, DEFAULT_SETTINGS, DEMO_PASSWORDS, SEED_BADGES,
    SEED_REWARDS, SEED_SUGGESTIONS,
)
from .util import hash_password, new_id, now_iso, parse_time, today_iso
from .content import item4_meta, item4_questions, member_badge_guide



def _unescape_raw_newlines(text: str) -> str:
    """Escape newlines/tabs that ended up *inside* JSON strings.

    Copying a key through some editors turns the private key's \n escapes into
    real line breaks, which is invalid JSON. Walk the text, and while inside a
    string literal, escape them back.
    """
    out: list[str] = []
    in_string = False
    escaped = False
    for character in text:
        if escaped:
            out.append(character)
            escaped = False
            continue
        if character == "\\":
            out.append(character)
            escaped = True
            continue
        if character == '"':
            in_string = not in_string
            out.append(character)
            continue
        if in_string and character == "\n":
            out.append("\\n")
            continue
        if in_string and character == "\r":
            continue
        if in_string and character == "\t":
            out.append("\\t")
            continue
        out.append(character)
    return "".join(out)


def parse_service_account(raw: str) -> dict:
    """Parse the key the way it actually arrives, not the way it should."""
    text = str(raw or "").strip().lstrip("\ufeff")
    if not text:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON 是空的")
    if text.startswith('"') and text.endswith('"') and len(text) > 2:
        inner = text[1:-1].strip()                      # 整段被引號包住
        try:
            json.loads(inner)
            text = inner
        except ValueError:
            unescaped = inner.replace('\\"', '"').replace("\\\\", "\\")
            text = unescaped
    try:
        return json.loads(text)
    except ValueError as first:
        try:
            return json.loads(_unescape_raw_newlines(text))
        except ValueError:
            raise first from None                       # 保留原本的錯誤訊息（給 advice 判斷）


def _sheets_driver(env: dict):
    """Build the Google Sheets driver from the environment."""
    account: dict = {}
    path = env.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            account = json.load(handle)
    elif env.get("GOOGLE_SERVICE_ACCOUNT_JSON"):
        account = parse_service_account(env["GOOGLE_SERVICE_ACCOUNT_JSON"])
    if not isinstance(account, dict) or not account.get("client_email"):
        raise ValueError("服務帳戶金鑰不完整：GOOGLE_SERVICE_ACCOUNT_JSON 要是整份 JSON 檔的內容")
    if not (env.get("GOOGLE_SHEET_ID") or "").strip():
        raise ValueError("未設定 GOOGLE_SHEET_ID")
    sheet_id = env["GOOGLE_SHEET_ID"].strip()
    if "/" in sheet_id or "docs.google.com" in sheet_id or " " in sheet_id:
        raise ValueError("GOOGLE_SHEET_ID 是一整條網址；只要 /d/ 與 /edit 中間那一小段")
    return SheetsDriver(
        spreadsheet_id=sheet_id,
        service_account=account,
        drive_folder_id=env.get("GOOGLE_DRIVE_FOLDER_ID", ""),
    )


def _probe(driver) -> None:
    """Prove the key, the ID and the sharing before the app relies on them.

    Tabs missing from a brand-new Sheet are created here (the app does this on
    every boot anyway). A bare 「Unable to parse range」 still counts as
    reachable — it only means the tab was not there yet.
    """
    driver.ensure_schema()
    try:
        driver.list("badges")
    except Exception as exc:                    # noqa: BLE001
        if "Unable to parse range" in str(exc):
            return
        raise


def storage_advice(error: str) -> tuple[str, str]:
    """(中文說明, 中文修正) — 把 Google／Python 的錯誤翻譯成人看的兩句。"""
    text = str(error or "")
    if not text.strip():
        return ("", "")                      # 沒有錯誤就不要嚇人
    if "ModuleNotFoundError" in text or "No module named" in text:
        missing = text.split("'")[1] if "'" in text else "某個套件"
        return (f"部署缺少套件（{missing}），所以連不上 Google。",
                "requirements.txt 未包含這個套件；部署最新版本（程式已補上 google-auth）後即可。")
    if "deserialize" in text.lower() or "Could not parse" in text or "InvalidKey" in text:
        return ("服務帳戶金鑰的 private_key 不完整（貼上時被截斷，或前後加了引號）。",
                "在 Vercel 重新貼上整份 JSON 檔內容：由 { 到 } 都要有，private_key 整段（含 -----BEGIN…-----）不可換行錯誤，前後不要加引號，存檔後 Redeploy。")
    if "JSONDecodeError" in text or "服務帳戶金鑰不完整" in text:
        return ("服務帳戶金鑰（GOOGLE_SERVICE_ACCOUNT_JSON）不是有效的 JSON。",
                "在 Vercel 重新貼上整份 JSON 檔內容，由 { 到 } 都要有，前後不要加引號，存檔後 Redeploy。"
                "（可先在瀏覽器打開 tools/check-service-account.html 貼上檢查一次）")
    if "GOOGLE_SHEET_ID" in text:
        return ("未設定 GOOGLE_SHEET_ID。",
                "把試算表網址 /d/ 與 /edit 中間那一段貼進 Vercel 的 GOOGLE_SHEET_ID，存檔後 Redeploy。")
    if ("has not been used in project" in text or "SERVICE_DISABLED" in text
            or "is disabled" in text or "accessNotConfigured" in text):
        api = "Google Drive API" if "drive" in text.lower() else "Google Sheets API"
        return (f"{api} 還未在 Google Cloud 專案啟用。",
                "到 console.cloud.google.com → 左邊「API 和服務 → 程式庫」，搜尋 Google Sheets API 與 "
                "Google Drive API，各按一次「啟用」（上面的錯誤訊息裡也有直接連結）。啟用後等一兩分鐘，"
                "回到 Vercel Redeploy 一次即可。")
    if "Unable to parse range" in text:
        return ("試算表已連上，但分頁還未建立（程式會自動補上）。",
                "重新開啟平台一次即可；程式在第一次連上時會建立 15 個分頁。"
                "若持續出現，到 Vercel → Deployments → Redeploy 部署最新版本。")
    if "Invalid spreadsheet id" in text or "invalid spreadsheet id" in text:
        return ("GOOGLE_SHEET_ID 不完整或格式不對。",
                "由試算表網址 /d/ 與 /edit 中間複製完整那一段（通常 44 個字元，只會有英文字母、數字、- 和 _），"
                "貼回 Vercel 的 GOOGLE_SHEET_ID，存檔後 Redeploy。")
    if "400" in text:
        return ("Google 回應 400：請求格式有問題，最常見是 GOOGLE_SHEET_ID 貼得不完整。",
                "重新複製試算表網址 /d/ 與 /edit 中間那一段，貼回 Vercel 的 GOOGLE_SHEET_ID，存檔後 Redeploy。")
    if "insufficient" in text.lower() and "scope" in text.lower():
        return ("服務帳戶金鑰的授權範圍不足。",
                "重新下載一次服務帳戶金鑰（Google Cloud → IAM 與管理 → 服務帳戶 → 金鑰 → JSON），"
                "重新貼上並 Redeploy。")
    if "403" in text:
        return ("Google 拒絕存取：試算表（或資料夾）未共用給服務帳戶電郵。",
                "打開試算表 → 共用 → 加入服務帳戶電郵（…@….iam.gserviceaccount.com），權限「編輯者」。")
    if "404" in text:
        return ("找不到那張試算表：GOOGLE_SHEET_ID 可能不是這份檔案的 ID。",
                "重新複製試算表網址 /d/ 與 /edit 中間那一段，貼回 GOOGLE_SHEET_ID，存檔後 Redeploy。")
    if "401" in text or "invalid_grant" in text or "credentials" in text.lower():
        return ("服務帳戶金鑰被拒：金鑰可能已被刪除或複製不完整。",
                "到 Google Cloud → IAM 與管理 → 服務帳戶 → 金鑰，建立新的 JSON 金鑰並重新貼上。")
    return ("連不上 Google 試算表：" + text[:160],
            "檢查 GOOGLE_SHEET_ID、GOOGLE_SERVICE_ACCOUNT_JSON 與共用設定，然後 Redeploy。")


class Store:
    def __init__(self, driver, config: dict):
        self.driver = driver
        self.config = config
        self._settings_cache: dict | None = None

    # --- construction -------------------------------------------------------
    @classmethod
    def from_env(cls, env: dict | None = None) -> "Store":
        env = env or os.environ
        driver_name = (env.get("DATA_DRIVER") or "local").lower()
        config = {
            # 正式預設：示範帳戶與示範資料都關上 —— 第一次開啟會看到
            # 「建立第一位領袖」。要示範帳戶，明確設 DEMO_LOGIN=true /
            # SEED_DEMO=true（離線試玩檔與檢查腳本會自行設定）。
            "demo_login": (env.get("DEMO_LOGIN") or "false").lower() == "true",
            "seed_demo": (env.get("SEED_DEMO") or "false").lower() == "true",
            "data_dir": env.get("DATA_DIR") or os.path.join(os.getcwd(), "data"),
        }
        config["storage_error"] = ""
        if driver_name == "sheets":
            try:
                driver = _sheets_driver(env)
                _probe(driver)                      # read one tab: proves key + id + sharing
            except Exception as exc:                # noqa: BLE001 — never let config kill the site
                config["storage_error"] = f"{type(exc).__name__}: {exc}"
                driver = LocalDriver(config["data_dir"])
        else:
            driver = LocalDriver(config["data_dir"])
        store = cls(driver=driver, config=config)
        store.driver.ensure_schema()
        if config["seed_demo"] and store.needs_setup():
            store.seed_demo()
        else:
            # 正式部署：空資料庫第一次連上時建立獎章目錄（只建立一次，
            # 之後任何部署、任何重啟都不會改動已有的資料）
            store.ensure_catalog()
        return store

    # --- pass-throughs ------------------------------------------------------
    def list(self, collection: str) -> list[dict]:
        return self.driver.list(collection)

    def get(self, collection: str, key: Any) -> dict | None:
        return self.driver.get(collection, key)

    def insert(self, collection: str, record: dict) -> dict:
        return self.driver.insert(collection, record)

    def update(self, collection: str, key: Any, patch: dict) -> dict | None:
        return self.driver.update(collection, key, patch)

    def remove(self, collection: str, key: Any) -> bool:
        return self.driver.remove(collection, key)

    def remove_where(self, collection: str, predicate: Callable[[dict], bool]) -> int:
        return self.driver.remove_where(collection, predicate)

    def upload_file(self, *, name: str, mime_type: str, data: bytes) -> dict:
        return self.driver.upload_file(name=name, mime_type=mime_type, data=data)

    # --- settings -----------------------------------------------------------
    def settings(self, force: bool = False) -> dict:
        if self._settings_cache is not None and not force:
            return self._settings_cache
        merged = json.loads(json.dumps(DEFAULT_SETTINGS))
        for row in self.driver.list("settings"):
            key = row.get("key")
            if not key:
                continue
            value = row.get("value_json")
            if isinstance(value, str) and value.strip():
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
            merged[key] = value
        merged["feature_flags"] = {**DEFAULT_SETTINGS["feature_flags"], **(merged.get("feature_flags") or {})}
        self._settings_cache = merged
        return merged

    def settings_cached(self) -> dict:
        """Never hits the network — safe for templates on every request."""
        return self._settings_cache if self._settings_cache is not None else self.settings()

    def save_setting(self, key: str, value) -> dict:
        existing = self.driver.get("settings", key)
        if existing:
            self.driver.update("settings", key, {"value_json": json.dumps(value, ensure_ascii=False), "updated_at": now_iso()})
        else:
            self.driver.insert("settings", {
                "key": key, "value_json": json.dumps(value, ensure_ascii=False), "updated_at": now_iso(),
            })
        self._settings_cache = None
        return self.settings(force=True)

    # --- stats --------------------------------------------------------------
    def stats_for(self, user_id: str) -> dict:
        stats = self.driver.get("stats", user_id)
        if not stats:
            stats = self.driver.insert("stats", {
                "user_id": user_id,
                "points_balance": 0, "tasks_done": 0, "badges_done": 0,
                "streak_current": 0, "streak_best": 0, "last_active_date": "",
                "updated_at": now_iso(),
            })
        return stats

    def rebuild_stats(self, user_id: str) -> dict:
        """Recomputes a scout's cached numbers from the ledger + records.

        The ledger is the source of truth, so this can never disagree with it —
        the same invariant the Node build enforces in its tests.
        """
        ledger = [row for row in self.list("points_ledger") if row.get("user_id") == user_id]
        records = [row for row in self.list("progress_records") if row.get("user_id") == user_id]
        awards = [row for row in self.list("badge_awards") if row.get("user_id") == user_id]
        balance = sum(int(float(row.get("points_delta") or 0)) for row in ledger)
        done = [row for row in records if row.get("status") == "completed"]
        days = sorted({str(row.get("decided_at") or row.get("submitted_at") or "")[:10] for row in done})
        streak_current, streak_best = 0, 0
        if days:
            run = 1
            for previous, current in zip(days, days[1:]):
                from .util import days_between

                run = run + 1 if days_between(previous, current) == 1 else 1
                streak_best = max(streak_best, run)
            streak_best = max(streak_best, 1)
            from .util import days_between

            streak_current = run if days_between(days[-1], today_iso()) <= 1 else 0
        patch = {
            "points_balance": max(0, balance),
            "tasks_done": len(done),
            "badges_done": len(awards),
            "streak_current": streak_current,
            "streak_best": streak_best,
            "last_active_date": days[-1] if days else "",
            "updated_at": now_iso(),
        }
        return self.update("stats", user_id, patch) or patch

    # --- first run ----------------------------------------------------------
    def needs_setup(self) -> bool:
        return not any(row.get("role") == "leader" for row in self.list("users"))

    def create_first_leader(self, *, username: str, password: str, display_name_zh: str,
                            display_name_en: str = "", unit: str = "") -> dict:
        hashed, salt = hash_password(password)
        leader = self.insert("users", {
            "role": "leader", "username": username.strip().lower(),
            "password_hash": hashed, "password_salt": salt,
            "display_name_zh": display_name_zh or username,
            "display_name_en": display_name_en or display_name_zh or username,
            "email": "", "scout_no": "", "section": "leader", "patrol": "",
            "unit": unit, "avatar": "🧭", "status": "active",
            "must_change_password": False, "show_on_leaderboard": False,
            "created_at": now_iso(), "created_by": "setup",
        })
        self.stats_for(leader["id"])
        if unit:
            self.save_setting("unit_name_zh", unit)
        return leader

    # --- the platform's own content -----------------------------------------
    def ensure_catalog(self) -> bool:
        """建立獎章與任務目錄 —— 只在完全沒有獎章時執行一次。

        正式上線第一次連上（空試算表）就會跑，把會員章、其餘四個獎章及 11 個
        項目建立好；之後每次部署、每次重啟都不會再寫，所以領袖改過的標題、
        題目、獎章設定都不會被新版本覆蓋。回傳 True 代表這次真的建立了內容。
        """
        if self.list("badges"):
            return False
        now = now_iso()
        badge_ids: list[str] = []
        # 完成指南: the 11 items in the unit's own words (content/member-badge/guide.json)
        guide = member_badge_guide()
        item4 = item4_questions()
        for index, badge in enumerate(SEED_BADGES):
            created = self.insert("badges", {
                "section": "scout", "order_index": index + 1, "code": badge["code"],
                "title_zh": badge["title_zh"], "title_en": badge["title_en"],
                "subtitle_zh": badge["subtitle_zh"], "subtitle_en": badge["subtitle_en"],
                "desc_zh": badge["desc_zh"], "desc_en": badge["desc_en"],
                "emoji": badge["emoji"], "image_url": badge["image_url"], "color": badge["color"],
                "points_reward": badge["points_reward"],
                "prerequisite_badge_ids": [] if index == 0 else [badge_ids[index - 1]],
                # the first award (會員章) is the one with a step-by-step guide
                "guide_json": guide if index == 0 else None,
                "status": "published", "created_at": now, "updated_at": now,
            })
            badge_ids.append(created["id"])
            for order, task in enumerate(badge["tasks"], start=1):
                config = dict(task.get("config_json", {}))
                if config.get("bank") == "member-badge/item4" and item4:
                    # merge the 50-question paper in; `bank` stays as a breadcrumb
                    config["questions"] = item4
                    config["quiz_title"] = item4_meta().get("title_zh", "")
                    config["per_question"] = item4_meta().get("per_question", 2)
                row = self.insert("tasks", {
                    "badge_id": created["id"], "order_index": order, "code": task["code"],
                    "title_zh": task["title_zh"], "title_en": task["title_en"],
                    "instruction_zh": task["instruction_zh"], "instruction_en": task["instruction_en"],
                    "type": task["type"], "points": task["points"],
                    "pass_score": task.get("pass_score", 0),
                    "config_json": config,
                    "status": "published", "created_at": now, "updated_at": now,
                })
        return True

    # --- demo seed ----------------------------------------------------------
    def seed_demo(self) -> None:
        """Placeholder content so every screen is visible on first run."""
        now = now_iso()
        self.ensure_catalog()                     # 示範部署一樣要有正式目錄
        hashed, salt = hash_password(DEMO_PASSWORDS["leader"])
        leader = self.insert("users", {
            "role": "leader", "username": "leader1", "password_hash": hashed, "password_salt": salt,
            "display_name_zh": "陳領袖", "display_name_en": "Leader Chan", "email": "",
            "scout_no": "", "section": "leader", "patrol": "", "unit": "Sample Scout Group",
            "avatar": "🧭", "status": "active", "must_change_password": False,
            "show_on_leaderboard": False, "created_at": now, "created_by": "seed",
        })
        self.stats_for(leader["id"])
        task_rows: list[dict] = [row for row in self.list("tasks") if row.get("code")]

        # A handful of scouts, each somewhere inside the FIRST award (會員章):
        # the tasks they have finished, and one that may be waiting for a leader.
        # The four awards that follow 會員章 stay locked until it is earned, so
        # the demo keeps the real shape of the scheme — one door open at a time.
        demo_scouts = [
            # M05 is the bridge game now (finished by playing), so the item waiting
            # for a leader's word is M06 — 宣誓禮儀與中式隊列.
            ("scout01", "王小明", "Wong Siu Ming", "Tiger", "🦊", ["M01", "M02", "M03"], "M06"),
            ("scout02", "李美儀", "Lee Mei Yee", "Tiger", "🐼", ["M01", "M02", "M03", "M04"], None),
            ("scout03", "張家豪", "Cheung Ka Ho", "Otter", "🦉", ["M01", "M02"], "M06"),
            ("scout04", "何嘉欣", "Ho Ka Yan", "Otter", "🐧", ["M01"], None),
            ("scout05", "陳大文", "Chan Tai Man", "Seagull", "🐯", ["M01", "M03"], None),
            ("scout06", "林小玲", "Lam Siu Ling", "Seagull", "🐨", [], None),
            ("scout07", "吳卓穎", "Ng Cheuk Wing", "Seagull", "🐬", [], None),
        ]
        by_code = {row["code"]: row for row in task_rows}
        scout_hashed, scout_salt = hash_password(DEMO_PASSWORDS["scout"])
        for index, (username, zh, en, patrol, avatar, done_codes, waiting_code) in enumerate(demo_scouts):
            never_signed_in = username == "scout07"
            scout = self.insert("users", {
                "role": "scout", "username": username,
                "password_hash": "" if never_signed_in else scout_hashed,
                "password_salt": "" if never_signed_in else scout_salt,
                "display_name_zh": zh, "display_name_en": en,
                # everyone but the never-signed-in demo has an email on file —
                # that address is what lets them reset their own password
                "email": "" if never_signed_in else f"{username}@82hkg.example",
                "scout_no": f"S{1000 + index}", "section": "scout", "patrol": patrol,
                "unit": "Sample Scout Group", "avatar": avatar, "status": "active",
                "must_change_password": never_signed_in, "show_on_leaderboard": True,
                "created_at": now, "created_by": leader["id"],
            })
            self.stats_for(scout["id"])
            for task in [by_code[c] for c in done_codes if c in by_code]:
                config = task.get("config_json") or {}
                config = json.loads(config) if isinstance(config, str) else config
                answers_json = checklist_json = None
                score = 100
                if task["type"] == "quiz":
                    # a finished paper: the demo scout passed with 92% (4 slips),
                    # so the 錯題檢討 has something real to show
                    questions = config.get("questions") or []
                    answers = []
                    for index, question in enumerate(questions):
                        key = question.get("answer")
                        if index % 13 == 12 and isinstance(key, int):      # every 13th one
                            answers.append((key + 1) % max(1, len(question.get("options") or [1])))
                        else:
                            answers.append(key)
                    answers_json = json.dumps(answers, ensure_ascii=False)
                    right = sum(1 for index, question in enumerate(questions)
                                if index < len(answers) and answers[index] == question.get("answer"))
                    score = round(right / len(questions) * 100) if questions else 100
                elif task["type"] == "checklist":
                    checklist_json = json.dumps([True] * len(config.get("items") or []))
                self.insert("progress_records", {
                    "user_id": scout["id"], "badge_id": task["badge_id"], "task_id": task["id"],
                    "attempt_no": 1, "status": "completed", "score": score,
                    "answers_json": answers_json, "checklist_json": checklist_json,
                    "evidence_url": "",
                    "reflection_text": f"我是{zh}。這次活動讓我學會了團隊合作和與人溝通。" if task["type"] == "reflection" else "",
                    "leader_comment": "", "points_awarded": task["points"],
                    "submitted_at": now, "decided_at": now, "decided_by": "auto",
                })
                self.insert("points_ledger", {
                    "user_id": scout["id"], "entry_type": "task",
                    "points_delta": task["points"],
                    "reason_zh": f"完成任務「{task['title_zh']}」",
                    "reason_en": f"Completed task \"{task['title_en']}\"",
                    "ref_type": "task", "ref_id": task["id"], "created_at": now, "created_by": "auto",
                })
            if waiting_code and waiting_code in by_code:
                # one submission sits in the leaders' review queue
                waiting = by_code[waiting_code]
                kind = waiting["type"]
                self.insert("progress_records", {
                    "user_id": scout["id"], "badge_id": waiting["badge_id"], "task_id": waiting["id"],
                    "attempt_no": 1, "status": "pending", "score": 0,
                    "answers_json": None,
                    "checklist_json": [True, False] if kind == "checklist" else None,
                    "evidence_url": ("https://drive.google.com/file/d/1SampleEvidenceFileId/view"
                                     if kind == "evidence" else ""),
                    "reflection_text": (f"我是{zh}，已經練好宣誓的禮儀和隊列動作，請領袖考核。"
                                        if kind == "signoff" else
                                        f"我是{zh}，想同大家分享這次活動的經歷。" if kind == "reflection" else ""),
                    "leader_comment": "", "points_awarded": 0,
                    "submitted_at": now, "decided_at": "", "decided_by": "",
                })
            # Use the very same rule as real gameplay: the Membership Badge
            # cannot be seeded as earned while games 2–5 are placeholders.
            from .engine import check_badge_completion
            for badge in self.list("badges"):        # 目錄已建立（可能早於這次示範）
                check_badge_completion(self, user=scout, badge=badge)
            self.rebuild_stats(scout["id"])

        for order, idea in enumerate(SEED_SUGGESTIONS, start=1):
            self.insert("suggestions", {
                "emoji": idea["emoji"], "category": idea["category"],
                "title_zh": idea["title_zh"], "title_en": idea["title_en"],
                "desc_zh": idea["desc_zh"], "desc_en": idea["desc_en"],
                "link_url": "", "link_label_zh": "", "link_label_en": "",
                "order_index": order, "active": True, "created_at": now,
            })
        for reward in SEED_REWARDS:
            self.insert("rewards", {**reward, "desc_zh": reward.get("desc_zh", ""),
                                    "desc_en": reward.get("desc_en", ""), "active": True})
        self.insert("announcements", {
            "title_zh": "歡迎來到童軍進度平台（示例公告）",
            "title_en": "Welcome to the Scout Progress Platform (sample notice)",
            "body_zh": "這是一則示例公告，領袖可在後台修改或刪除。",
            "body_en": "This is a sample notice — leaders can edit or delete it in the console.",
            "audience": "all", "pinned": True, "created_at": now, "expires_at": "",
        })
        self.insert("audit_log", {
            "actor_id": leader["id"], "actor_role": "leader", "action": "seed_demo",
            "entity": "system", "entity_id": "", "detail_json": json.dumps({"scouts": len(demo_scouts)}),
            "created_at": now,
        })
        self._settings_cache = None


def bootstrap_data_dir(store: Store) -> None:
    """Creates ./data on first run so the app starts cleanly."""
    if store.driver.name == "local":
        store.driver.ensure_schema()


def parse_sort_time(value: str) -> float:
    return parse_time(value)
