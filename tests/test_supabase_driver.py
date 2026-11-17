"""The Supabase driver and the copy tool, exercised against a fake PostgREST.

Nothing touches the network: the driver's transport is replaced, but tab
checks, key handling, upserts and the whole Store above it are real.
"""
from __future__ import annotations

import json
import pathlib
import sys
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from scout.drivers.supabase import SupabaseDriver          # noqa: E402
from scout.schema import COLLECTION_ORDER                  # noqa: E402


class FakeSupabase:
    """Pretends to be the PostgREST + Storage endpoints the driver calls."""

    def __init__(self, tables=None):
        self.tables: dict[str, dict[str, dict]] = {
            name: {} for name in (tables if tables is not None else COLLECTION_ORDER)}
        self.objects: dict[str, bytes] = {}

    def api(self, path, method="GET", body=None, raw=None, content_type="application/json", prefer=""):
        split = urlsplit(path)
        query = {k: v[0] for k, v in parse_qs(split.query).items()}
        if split.path.startswith("/storage/v1/object/"):
            bucket_path = split.path[len("/storage/v1/object/"):]
            self.objects[bucket_path] = raw or b""
            return {"Key": bucket_path}
        collection = split.path.rsplit("/", 1)[-1]
        if collection not in self.tables:
            raise RuntimeError(f"Supabase API GET {path} → 404: PGRST205 table not found")
        rows = self.tables[collection]

        def matches(entry):
            condition = query.get("key", "")
            if condition.startswith("eq."):
                return entry["key"] == unquote(condition[3:])
            if condition == "not.is.null":
                return True
            return True

        if method == "GET":
            found = [entry for entry in sorted(rows.values(), key=lambda e: e.get("seq", 0)) if matches(entry)]
            offset = int(query.get("offset", 0))
            limit = int(query.get("limit", len(found) or 1))
            return [{"data": dict(entry["data"])} for entry in found[offset:offset + limit]]
        if method == "POST":
            upsert = "merge-duplicates" in prefer
            for payload in body or []:
                if payload["key"] in rows and not upsert:
                    raise RuntimeError(f"Supabase API POST {path} → 409: duplicate key")
                previous = rows.get(payload["key"], {})
                rows[payload["key"]] = {"key": payload["key"], "data": dict(payload["data"]),
                                        "seq": previous.get("seq", len(rows) + 1)}
            return None
        if method == "PATCH":
            for entry in rows.values():
                if matches(entry):
                    entry["data"] = dict((body or {})["data"])
            return None
        if method == "DELETE":
            for key in [k for k, entry in rows.items() if matches(entry)]:
                del rows[key]
            return None
        raise AssertionError(f"unexpected call: {method} {path}")


@pytest.fixture()
def fake():
    return FakeSupabase()


@pytest.fixture()
def db(fake):
    driver = SupabaseDriver("https://demo.supabase.co", "service-role-test-key")
    driver._api = fake.api
    return driver


def test_insert_get_update_remove(db, fake):
    created = db.insert("users", {"role": "scout", "username": "Chan"})
    assert created["id"]
    assert db.get("users", created["id"])["username"] == "Chan"

    db.update("users", created["id"], {"username": "Lee"})
    assert db.get("users", created["id"])["username"] == "Lee"

    assert db.remove("users", created["id"]) is True
    assert db.get("users", created["id"]) is None
    assert db.remove("users", created["id"]) is False


def test_a_duplicate_key_is_an_error_not_an_overwrite(db):
    db.insert("settings", {"key": "unit_name_zh", "value_json": "\"甲旅\""})
    with pytest.raises(RuntimeError, match="409"):
        db.insert("settings", {"key": "unit_name_zh", "value_json": "\"乙旅\""})
    assert "甲旅" in db.get("settings", "unit_name_zh")["value_json"]


def test_append_and_upsert_many(db):
    made = db.append_many("badges", [{"code": "SC-01"}, {"code": "SC-02"}])
    assert [row["code"] for row in db.list("badges")] == ["SC-01", "SC-02"]
    # re-running a copy replaces the same rows instead of duplicating them
    db.upsert_many("badges", [made[0]])
    assert len(db.list("badges")) == 2


def test_missing_tables_are_named_with_the_fix(db):
    db._api = FakeSupabase(tables=[]).api
    with pytest.raises(RuntimeError, match="supabase_schema"):
        db.ensure_schema()


def test_upload_goes_to_storage_with_a_public_link(db, fake):
    result = db.upload_file(name="card-u1.webp", mime_type="image/webp", data=b"img")
    assert result["stored"] == "supabase"
    assert result["url"].startswith("https://demo.supabase.co/storage/v1/object/public/uploads/")
    assert b"img" in fake.objects.values()


def test_missing_configuration_is_reported_clearly():
    with pytest.raises(ValueError, match="SUPABASE_URL"):
        SupabaseDriver("", "key")
    with pytest.raises(ValueError, match="SUPABASE_SERVICE_ROLE_KEY"):
        SupabaseDriver("https://demo.supabase.co", "")


def test_store_round_trips_through_the_supabase_driver(db):
    """The whole Store works with Supabase underneath, not just the driver."""
    from scout.engine import progress_for
    from scout.store import Store

    store = Store(driver=db, config={"demo_login": True, "seed_demo": True, "data_dir": "/tmp"})
    store.seed_demo()
    scout = next(u for u in store.list("users") if u["username"] == "scout03")
    progress = progress_for(store, scout["id"])
    assert progress["overall"]["tasks_total"] == len(store.list("tasks"))
    store.save_setting("unit_name_zh", "雲端旅團")
    assert store.settings(force=True)["unit_name_zh"] == "雲端旅團"


def test_from_env_without_supabase_details_falls_back_with_a_reason(monkeypatch):
    import scout.store as store_module

    store = store_module.Store.from_env({"DATA_DRIVER": "supabase", "DATA_DIR": "/tmp/none-x"})
    assert store.driver.name == "local"
    assert "SUPABASE" in store.config["storage_error"]
    reason, advice = store_module.storage_advice(store.config["storage_error"])
    assert "Supabase" in reason and "SUPABASE_URL" in advice
    reason_en, _ = store_module.storage_advice_en(store.config["storage_error"])
    assert "Supabase" in reason_en


def test_copy_tool_moves_everything_and_can_run_twice(tmp_path):
    """來源是本機資料；複製到 Supabase 後每一列都在，JSON 備份也完整。"""
    from scout.drivers.local import LocalDriver
    from scout.store import Store
    from tools.copy_to_supabase import build_backup, copy_store

    source = Store(driver=LocalDriver(str(tmp_path)),
                   config={"demo_login": True, "seed_demo": True, "data_dir": str(tmp_path)})
    source.seed_demo()

    fake = FakeSupabase()
    target = SupabaseDriver("https://demo.supabase.co", "service-role-test-key")
    target._api = fake.api

    counts = copy_store(source, target)
    assert counts["users"] == len(source.list("users")) and counts["users"] > 1
    assert copy_store(source, target) == counts           # 重跑不重複

    check = Store(driver=target, config={})
    assert {u["username"] for u in check.list("users")} == {u["username"] for u in source.list("users")}

    backup = build_backup(source)
    restored = json.loads(json.dumps(backup, ensure_ascii=False))
    assert restored["collections"]["users"], "JSON 備份要有使用者資料"
    assert set(restored["collections"]) == set(COLLECTION_ORDER)
