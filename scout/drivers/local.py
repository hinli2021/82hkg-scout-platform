"""
Local JSON driver — zero-setup storage (development, or a laptop at a meeting).

  data/db/<collection>.json   one array per collection
  data/uploads/<id>.<ext>     photo evidence, served at /uploads/<name>

Writes are atomic (temp file + os.replace) so a crash can never leave a
half-written collection on disk.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from typing import Any, Callable, Iterable

from ..schema import COLLECTION_ORDER, key_field
from ..util import new_id


class LocalDriver:
    name = "local"

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.db_dir = os.path.join(data_dir, "db")
        self.uploads_dir = os.path.join(data_dir, "uploads")
        self._cache: dict[str, list[dict]] = {}
        # file stamps, so a change made *outside* this process (hand-editing the
        # JSON, a second process, a test run) is noticed instead of being served
        # from a stale cache. This is what makes "I reset the demo account from
        # a script" actually show up in the running server.
        self._stamps: dict[str, tuple | None] = {}
        self._lock = threading.RLock()

    # --- lifecycle ----------------------------------------------------------
    def ensure_schema(self) -> None:
        os.makedirs(self.db_dir, exist_ok=True)
        os.makedirs(self.uploads_dir, exist_ok=True)
        for collection in COLLECTION_ORDER:
            path = self._path(collection)
            if not os.path.exists(path):
                self._write_file(path, [])

    def _path(self, collection: str) -> str:
        return os.path.join(self.db_dir, f"{collection}.json")

    @staticmethod
    def _write_file(path: str, rows: list[dict]) -> None:
        directory = os.path.dirname(path)
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(rows, handle, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    # --- reads / writes -----------------------------------------------------
    def _stamp(self, path: str) -> tuple | None:
        """(mtime_ns, size) of the file, or None when it does not exist yet."""
        try:
            info = os.stat(path)
            return (info.st_mtime_ns, info.st_size)
        except OSError:
            return None

    def _read(self, collection: str) -> list[dict]:
        with self._lock:
            path = self._path(collection)
            stamp = self._stamp(path)
            if collection in self._cache and self._stamps.get(collection) == stamp:
                return self._cache[collection]
            try:
                with open(path, encoding="utf-8") as handle:
                    rows = json.load(handle)
                if not isinstance(rows, list):
                    rows = []
            except (FileNotFoundError, json.JSONDecodeError):
                rows = []
            self._cache[collection] = rows
            self._stamps[collection] = stamp
            return rows

    def _persist(self, collection: str) -> None:
        with self._lock:
            path = self._path(collection)
            self._write_file(path, self._cache.get(collection, []))
            self._stamps[collection] = self._stamp(path)

    def list(self, collection: str) -> list[dict]:
        return [dict(row) for row in self._read(collection)]

    def get(self, collection: str, key: Any) -> dict | None:
        field = key_field(collection)
        for row in self._read(collection):
            if str(row.get(field)) == str(key):
                return dict(row)
        return None

    def insert(self, collection: str, record: dict) -> dict:
        with self._lock:
            rows = self._read(collection)
            field = key_field(collection)
            record = dict(record)
            if not record.get(field):
                record[field] = new_id()
            rows.append(record)
            self._persist(collection)
            return dict(record)

    def update(self, collection: str, key: Any, patch: dict) -> dict | None:
        with self._lock:
            rows = self._read(collection)
            field = key_field(collection)
            for index, row in enumerate(rows):
                if str(row.get(field)) == str(key):
                    rows[index] = {**row, **patch}
                    self._persist(collection)
                    return dict(rows[index])
        return None

    def remove(self, collection: str, key: Any) -> bool:
        with self._lock:
            rows = self._read(collection)
            field = key_field(collection)
            for index, row in enumerate(rows):
                if str(row.get(field)) == str(key):
                    rows.pop(index)
                    self._persist(collection)
                    return True
        return False

    def remove_where(self, collection: str, predicate: Callable[[dict], bool]) -> int:
        with self._lock:
            rows = self._read(collection)
            kept = [row for row in rows if not predicate(row)]
            removed = len(rows) - len(kept)
            self._cache[collection] = kept
            self._persist(collection)
            return removed

    # --- media --------------------------------------------------------------
    def upload_file(self, *, name: str, mime_type: str, data: bytes) -> dict:
        os.makedirs(self.uploads_dir, exist_ok=True)
        ext = os.path.splitext(str(name or ""))[1].lower() or ".jpg"
        safe = f"{new_id()}{ext}"
        with open(os.path.join(self.uploads_dir, safe), "wb") as handle:
            handle.write(data)
        return {"id": safe, "url": f"/uploads/{safe}", "stored": "local"}

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._stamps.clear()
            for collection in COLLECTION_ORDER:
                self._write_file(self._path(collection), [])
            if os.path.isdir(self.uploads_dir):
                for entry in os.listdir(self.uploads_dir):
                    path = os.path.join(self.uploads_dir, entry)
                    if os.path.isfile(path):
                        os.unlink(path)
