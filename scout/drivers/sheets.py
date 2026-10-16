"""
Google Sheets + Drive driver — your spreadsheet IS the database, your Drive
folder holds the photo evidence. Free, and nothing extra to run.

Layout (identical to the Node build, so either version can read the same file):
  • one tab per collection; row 1 = column headers, created on first run
  • complex values (arrays/objects) are stored as JSON text in one cell
  • reads are cached briefly; writes are targeted range updates, not rewrites

Auth uses a *service account* (not OAuth): you share the Sheet and the Drive
folder with the service-account email, exactly like sharing with a colleague.

Credentials can be given two ways:
  GOOGLE_SERVICE_ACCOUNT_FILE=./service-account.json
  GOOGLE_SERVICE_ACCOUNT_JSON={...}      # the whole JSON in one env var
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Callable

import requests

from ..schema import COLLECTION_ORDER, JSON_FIELDS, key_field
from ..util import new_id, to_bool

SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
DRIVE_API = "https://www.googleapis.com/upload/drive/v3/files"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]
CACHE_SECONDS = 15


def _column_letter(index: int) -> str:
    """1 → A, 27 → AA (Sheets ranges)."""
    letters = ""
    while index > 0:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


class SheetsDriver:
    name = "sheets"

    def __init__(self, spreadsheet_id: str, service_account: dict, drive_folder_id: str = ""):
        if not spreadsheet_id:
            raise ValueError("GOOGLE_SHEET_ID is required when DATA_DRIVER=sheets")
        if not service_account or not service_account.get("client_email"):
            raise ValueError("A Google service account is required when DATA_DRIVER=sheets")
        self.spreadsheet_id = spreadsheet_id
        self.drive_folder_id = drive_folder_id or ""
        self.service_account = service_account
        self._credentials = None
        self._cache: dict[str, dict] = {}
        self._tabs_checked = False

    # --- auth ---------------------------------------------------------------
    def _token(self) -> str:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account as sa

        if self._credentials is None:
            self._credentials = sa.Credentials.from_service_account_info(self.service_account, scopes=SCOPES)
        if not self._credentials.valid:
            self._credentials.refresh(Request())
        return self._credentials.token

    def _api(self, url: str, method: str = "GET", body: dict | None = None, raw: bytes | None = None,
             content_type: str = "application/json") -> dict:
        headers = {"Authorization": f"Bearer {self._token()}"}
        if raw is None:
            headers["Content-Type"] = content_type
        response = requests.request(
            method, url, headers=headers,
            data=json.dumps(body).encode("utf-8") if body is not None else raw,
            timeout=30,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Google API {method} {url} → {response.status_code}: {response.text[:400]}")
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {}

    # --- tab management -----------------------------------------------------
    def _headers(self, collection: str) -> list[str]:
        from ..schema import COLLECTIONS

        return list(COLLECTIONS[collection]["fields"])

    def ensure_schema(self) -> None:
        if self._tabs_checked:
            return
        meta = self._api(f"{SHEETS_API}/{self.spreadsheet_id}?fields=sheets.properties.title")
        existing = {sheet["properties"]["title"] for sheet in meta.get("sheets", [])}
        missing = [c for c in COLLECTION_ORDER if c not in existing]
        if missing:
            self._api(
                f"{SHEETS_API}/{self.spreadsheet_id}:batchUpdate",
                method="POST",
                body={"requests": [{"addSheet": {"properties": {"title": name}}} for name in missing]},
            )
        if missing:
            data = []
            for collection in missing:              # 一次請求寫好所有標題列
                headers = self._headers(collection)
                rng = f"{collection}!A1:{_column_letter(len(headers))}1"
                data.append({"range": rng, "values": [headers]})
            self._api(
                f"{SHEETS_API}/{self.spreadsheet_id}/values:batchUpdate",
                method="POST",
                body={"valueInputOption": "RAW", "data": data},
            )
        self._tabs_checked = True

    # --- value marshalling --------------------------------------------------
    def _to_cell(self, field: str, value: Any) -> Any:
        if field in JSON_FIELDS:
            return json.dumps(value, ensure_ascii=False) if value not in (None, "") else ""
        if isinstance(value, bool):
            return "true" if value else "false"
        return "" if value is None else value

    def _from_cell(self, field: str, cell: Any) -> Any:
        text = "" if cell is None else str(cell)
        if field in JSON_FIELDS:
            if not text.strip():
                return [] if field in {"prerequisite_badge_ids"} else {}
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return [] if field in {"prerequisite_badge_ids"} else {}
        if field in {"must_change_password", "show_on_leaderboard", "active", "pinned"}:
            return to_bool(text)
        if field in {"order_index", "points_reward", "points", "pass_score", "attempt_no", "score",
                     "points_awarded", "points_delta", "points_cost", "stock", "points_balance",
                     "tasks_done", "badges_done", "streak_current", "streak_best"}:
            try:
                return float(text) if "." in text else int(text or 0)
            except ValueError:
                return 0
        return text

    def _fetch(self, collection: str, force: bool = False) -> dict:
        cached = self._cache.get(collection)
        if cached and not force and (time.time() - cached["ts"]) < CACHE_SECONDS:
            return cached
        headers = self._headers(collection)
        rng = f"{collection}!A1:{_column_letter(max(len(headers), 1))}20000"
        data = self._api(f"{SHEETS_API}/{self.spreadsheet_id}/values/{rng}")
        values = data.get("values", []) or []
        sheet_headers = [str(h) for h in (values[0] if values else headers)] or headers
        rows: list[dict] = []
        index_by_id: dict[str, int] = {}
        last_row = 1                                   # the header row
        key = key_field(collection)
        for offset, raw in enumerate(values[1:], start=2):
            if not any(str(cell).strip() for cell in raw):
                continue
            last_row = max(last_row, offset)
            padded = list(raw) + [""] * (len(sheet_headers) - len(raw))
            row = {field: self._from_cell(field, padded[i] if i < len(padded) else "")
                   for i, field in enumerate(sheet_headers)}
            rows.append(row)
            index_by_id[str(row.get(key))] = offset
        entry = {"rows": rows, "row_index": index_by_id, "headers": sheet_headers,
                 "last_row": last_row, "ts": time.time()}
        self._cache[collection] = entry
        return entry

    def _write_row(self, collection: str, row_number: int, row: dict, headers: list[str]) -> None:
        values = [self._to_cell(field, row.get(field, "")) for field in headers]
        rng = f"{collection}!A{row_number}:{_column_letter(len(headers))}{row_number}"
        self._api(
            f"{SHEETS_API}/{self.spreadsheet_id}/values/{rng}?valueInputOption=RAW",
            method="PUT",
            body={"values": [values]},
        )
        self._cache.pop(collection, None)

    # --- collection API -----------------------------------------------------
    def list(self, collection: str) -> list[dict]:
        return [dict(row) for row in self._fetch(collection)["rows"]]

    def get(self, collection: str, key: Any) -> dict | None:
        field = key_field(collection)
        for row in self._fetch(collection)["rows"]:
            if str(row.get(field)) == str(key):
                return dict(row)
        return None

    def insert(self, collection: str, record: dict) -> dict:
        self.ensure_schema()
        entry = self._fetch(collection, force=True)
        headers = entry["headers"]
        key = key_field(collection)
        record = dict(record)
        if not record.get(key):
            record[key] = new_id()
        row_number = entry.get("last_row", len(entry["rows"]) + 1) + 1
        self._write_row(collection, row_number, record, headers)
        return dict(record)

    def append_many(self, collection: str, records: list[dict]) -> list[dict]:
        """Add several rows in one request — used when a fresh Sheet is set up.

        One GET for the headers, one PUT for the whole block: a first boot costs
        two calls per table instead of two per row, which is what keeps it
        inside a serverless function's time limit.
        """
        records = [dict(record) for record in records]
        if not records:
            return []
        self.ensure_schema()
        entry = self._fetch(collection, force=True)
        headers = entry["headers"]
        key = key_field(collection)
        for record in records:
            if not record.get(key):
                record[key] = new_id()
        start = entry.get("last_row", len(entry["rows"]) + 1) + 1
        end = start + len(records) - 1
        values = [[self._to_cell(field, record.get(field, "")) for field in headers]
                  for record in records]
        rng = f"{collection}!A{start}:{_column_letter(len(headers))}{end}"
        self._api(
            f"{SHEETS_API}/{self.spreadsheet_id}/values/{rng}?valueInputOption=RAW",
            method="PUT",
            body={"values": values},
        )
        self._cache.pop(collection, None)
        return records

    def update(self, collection: str, key: Any, patch: dict) -> dict | None:
        entry = self._fetch(collection, force=True)
        field = key_field(collection)
        row_number = entry["row_index"].get(str(key))
        if row_number is None:
            return None
        current = next((r for r in entry["rows"] if str(r.get(field)) == str(key)), {})
        merged = {**current, **patch}
        self._write_row(collection, row_number, merged, entry["headers"])
        return dict(merged)

    def remove(self, collection: str, key: Any) -> bool:
        entry = self._fetch(collection, force=True)
        field = key_field(collection)
        row_number = entry["row_index"].get(str(key))
        if row_number is None:
            return False
        # Blank the row's cells (cheap, keeps every other row's line number valid).
        headers = entry["headers"]
        blank = [""] * len(headers)
        rng = f"{collection}!A{row_number}:{_column_letter(len(headers))}{row_number}"
        self._api(f"{SHEETS_API}/{self.spreadsheet_id}/values/{rng}?valueInputOption=RAW",
                  method="PUT", body={"values": [blank]})
        self._cache.pop(collection, None)
        return True

    def remove_where(self, collection: str, predicate: Callable[[dict], bool]) -> int:
        rows = self.list(collection)
        removed = 0
        for row in rows:
            if predicate(row):
                if self.remove(collection, row.get(key_field(collection))):
                    removed += 1
        return removed

    # --- media: Google Drive -------------------------------------------------
    def upload_file(self, *, name: str, mime_type: str, data: bytes) -> dict:
        """Uploads to the configured Drive folder and returns a link + file id."""
        metadata = {"name": name or "evidence.jpg", "mimeType": mime_type or "image/jpeg"}
        if self.drive_folder_id:
            metadata["parents"] = [self.drive_folder_id]
        boundary = "scoutboundary" + new_id()
        body = (
            f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{json.dumps(metadata)}\r\n"
            f"--{boundary}\r\nContent-Type: {metadata['mimeType']}\r\n\r\n"
        ).encode("utf-8") + data + f"\r\n--{boundary}--\r\n".encode("utf-8")
        result = self._api(
            f"{DRIVE_API}?uploadType=multipart&fields=id,webViewLink",
            method="POST", raw=body, content_type=f"multipart/related; boundary={boundary}",
        )
        file_id = result.get("id", "")
        # Anyone in the unit follows the link when they are signed in to Drive.
        try:
            self._api(f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions",
                      method="POST", body={"role": "reader", "type": "anyone"})
        except RuntimeError:
            pass  # sharing is best-effort; the file still exists and is linked
        return {
            "id": file_id,
            "url": result.get("webViewLink") or f"https://drive.google.com/file/d/{file_id}/view",
            "stored": "drive",
        }

    def clear(self) -> None:
        for collection in COLLECTION_ORDER:
            for row in self.list(collection):
                self.remove(collection, row.get(key_field(collection)))
