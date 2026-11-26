"""
Supabase (Postgres) driver — a trial alternative to the Google Sheet.

Layout: one Postgres table per collection, created by
`tools/supabase_schema.sql`. Each table is deliberately small:

    seq         bigint identity         -- insertion order, as rows in a Sheet
    key         text primary key        -- the collection's own key field
    data        jsonb not null          -- the whole record, as the app uses it
    updated_at  timestamptz

Keeping the record as JSONB means the platform can gain a field (as profiles
gained 職位） without a database migration, while the data stays queryable
from the Supabase dashboard (`data->>'username'`). Access goes through the
PostgREST API with the service_role key, which lives only on the server —
tables have Row Level Security switched on with no public policies, so the
public anon key cannot read a single row.

Set DATA_DRIVER=supabase with SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to
use it. Nothing here is used unless those are set, so the Google Sheet stays
the production store until a trial says otherwise.
"""
from __future__ import annotations

import json
from typing import Any, Callable
from urllib.parse import quote

import requests

from ..schema import COLLECTION_ORDER, key_field
from ..util import new_id, now_iso

PAGE_SIZE = 1000


def _clean(record: dict) -> dict:
    """Only plain JSON values may travel — the same rule Sheets enforces."""
    return json.loads(json.dumps(record, ensure_ascii=False, default=str))


class SupabaseDriver:
    name = "supabase"

    def __init__(self, url: str, service_role_key: str, bucket: str = "uploads"):
        if not url:
            raise ValueError("未設定 SUPABASE_URL")
        if not service_role_key:
            raise ValueError("未設定 SUPABASE_SERVICE_ROLE_KEY")
        self.base_url = str(url).rstrip("/")
        self.service_role_key = service_role_key
        self.bucket = bucket or "uploads"
        self._tables_checked = False
        # One session for the life of the driver: a page load fires a dozen
        # PostgREST calls, and a fresh TCP+TLS handshake on every one of them
        # costs far more than the queries themselves when the database is an
        # ocean away from the last deployment region this ran in.
        self._session = requests.Session()

    # --- transport ----------------------------------------------------------
    def _api(self, path: str, method: str = "GET", body=None, raw: bytes | None = None,
             content_type: str = "application/json", prefer: str = "") -> Any:
        headers = {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
        }
        if prefer:
            headers["Prefer"] = prefer
        data = raw
        if body is not None:
            headers["Content-Type"] = content_type
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif raw is not None:
            headers["Content-Type"] = content_type
        response = requests.request(method, self.base_url + path, headers=headers,
                                    data=data, timeout=30)
        if response.status_code >= 400:
            raise RuntimeError(
                f"Supabase API {method} {path} → {response.status_code}: {response.text[:400]}")
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return None

    def _rest(self, collection: str, query: str = "") -> str:
        return f"/rest/v1/{collection}{query}"

    # --- schema -------------------------------------------------------------
    def ensure_schema(self) -> None:
        if self._tables_checked:
            return
        missing: list[str] = []
        for collection in COLLECTION_ORDER:
            try:
                self._api(self._rest(collection, "?select=key&limit=1"))
            except RuntimeError as exc:
                text = str(exc)
                if "PGRST205" in text or "42P01" in text or "does not exist" in text:
                    missing.append(collection)
                else:
                    raise
        if missing:
            raise RuntimeError(
                "Supabase 資料表未建立（缺少：" + "、".join(missing) + "）。"
                "請先在 Supabase 的 SQL Editor 執行 tools/supabase_schema.sql。")
        self._tables_checked = True

    # --- collection API -------------------------------------------------------
    def refresh(self, collection: str | None = None) -> None:
        """Nothing is cached here; every read already asks the database."""

    def list(self, collection: str) -> list[dict]:
        rows: list[dict] = []
        offset = 0
        while True:
            page = self._api(self._rest(
                collection,
                f"?select=data&order=seq.asc&limit={PAGE_SIZE}&offset={offset}")) or []
            rows.extend(dict(entry.get("data") or {}) for entry in page)
            if len(page) < PAGE_SIZE:
                return rows
            offset += PAGE_SIZE

    def get(self, collection: str, key: Any) -> dict | None:
        found = self._api(self._rest(
            collection, f"?select=data&key=eq.{quote(str(key), safe='')}&limit=1")) or []
        if not found:
            return None
        return dict(found[0].get("data") or {})

    def _payload(self, collection: str, record: dict) -> dict:
        record = _clean(dict(record))
        field = key_field(collection)
        if not record.get(field):
            record[field] = new_id()
        return {"key": str(record[field]), "data": record, "updated_at": now_iso()}

    def insert(self, collection: str, record: dict) -> dict:
        self.ensure_schema()
        payload = self._payload(collection, record)
        self._api(self._rest(collection), method="POST", body=[payload],
                  prefer="return=minimal")
        return dict(payload["data"])

    def append_many(self, collection: str, records: list[dict]) -> list[dict]:
        records = [dict(record) for record in records]
        if not records:
            return []
        self.ensure_schema()
        payloads = [self._payload(collection, record) for record in records]
        self._api(self._rest(collection), method="POST", body=payloads,
                  prefer="return=minimal")
        return [payload["data"] for payload in payloads]

    def upsert_many(self, collection: str, records: list[dict]) -> list[dict]:
        """Insert, or replace on a repeated key — the copy tool's safe retry."""
        records = [dict(record) for record in records]
        if not records:
            return []
        self.ensure_schema()
        payloads = [self._payload(collection, record) for record in records]
        self._api(self._rest(collection), method="POST", body=payloads,
                  prefer="resolution=merge-duplicates,return=minimal")
        return [payload["data"] for payload in payloads]

    def update(self, collection: str, key: Any, patch: dict) -> dict | None:
        current = self.get(collection, key)
        if current is None:
            return None
        merged = _clean({**current, **patch})
        self._api(self._rest(collection, f"?key=eq.{quote(str(key), safe='')}"),
                  method="PATCH",
                  body={"data": merged, "updated_at": now_iso()},
                  prefer="return=minimal")
        return dict(merged)

    def remove(self, collection: str, key: Any) -> bool:
        if self.get(collection, key) is None:
            return False
        self._api(self._rest(collection, f"?key=eq.{quote(str(key), safe='')}"),
                  method="DELETE", prefer="return=minimal")
        return True

    def remove_where(self, collection: str, predicate: Callable[[dict], bool]) -> int:
        removed = 0
        for row in self.list(collection):
            if predicate(row) and self.remove(collection, row.get(key_field(collection))):
                removed += 1
        return removed

    # --- media: Supabase Storage ---------------------------------------------
    def upload_file(self, *, name: str, mime_type: str, data: bytes) -> dict:
        safe = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in str(name or "file"))
        path = f"{new_id()}-{safe.lstrip('.-') or 'file'}"
        self._api(f"/storage/v1/object/{self.bucket}/{path}", method="POST",
                  raw=data, content_type=mime_type or "application/octet-stream")
        return {
            "id": path,
            "url": f"{self.base_url}/storage/v1/object/public/{self.bucket}/{path}",
            "stored": "supabase",
        }

    def clear(self) -> None:
        for collection in COLLECTION_ORDER:
            self._api(self._rest(collection, "?key=not.is.null"),
                      method="DELETE", prefer="return=minimal")
