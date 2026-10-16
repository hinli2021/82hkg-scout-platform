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
            "demo_login": (env.get("DEMO_LOGIN") or "true").lower() != "false",
            "seed_demo": (env.get("SEED_DEMO") or "true").lower() != "false",
            "data_dir": env.get("DATA_DIR") or os.path.join(os.getcwd(), "data"),
        }
        if driver_name == "sheets":
            account: dict = {}
            path = env.get("GOOGLE_SERVICE_ACCOUNT_FILE")
            if path and os.path.exists(path):
                with open(path, encoding="utf-8") as handle:
                    account = json.load(handle)
            elif env.get("GOOGLE_SERVICE_ACCOUNT_JSON"):
                account = json.loads(env["GOOGLE_SERVICE_ACCOUNT_JSON"])
            driver = SheetsDriver(
                spreadsheet_id=env.get("GOOGLE_SHEET_ID", ""),
                service_account=account,
                drive_folder_id=env.get("GOOGLE_DRIVE_FOLDER_ID", ""),
            )
        else:
            driver = LocalDriver(config["data_dir"])
        store = cls(driver=driver, config=config)
        store.driver.ensure_schema()
        if config["seed_demo"] and store.needs_setup():
            store.seed_demo()
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

    # --- demo seed ----------------------------------------------------------
    def seed_demo(self) -> None:
        """Placeholder content so every screen is visible on first run."""
        now = now_iso()
        hashed, salt = hash_password(DEMO_PASSWORDS["leader"])
        leader = self.insert("users", {
            "role": "leader", "username": "leader1", "password_hash": hashed, "password_salt": salt,
            "display_name_zh": "陳領袖", "display_name_en": "Leader Chan", "email": "",
            "scout_no": "", "section": "leader", "patrol": "", "unit": "Sample Scout Group",
            "avatar": "🧭", "status": "active", "must_change_password": False,
            "show_on_leaderboard": False, "created_at": now, "created_by": "seed",
        })
        self.stats_for(leader["id"])

        badge_ids: list[str] = []
        task_rows: list[dict] = []
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
                task_rows.append(row)

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
            for badge_id in badge_ids:
                check_badge_completion(self, user=scout, badge=self.get("badges", badge_id))
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
