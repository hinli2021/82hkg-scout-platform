"""Small shared helpers for the route modules."""
from __future__ import annotations

import csv
import io
import json

from flask import current_app, g, jsonify, redirect, request

from ..schema import COLLECTIONS, BOOL_FIELDS, JSON_FIELDS, NUMBER_FIELDS
from ..util import now_iso, to_bool


def store():
    return current_app.extensions["store"]


def wants_json() -> bool:
    """True when the game layer is driving the request (fetch), not the browser."""
    if request.headers.get("X-Requested-With") == "fetch":
        return True
    best = request.accept_mimetypes.best_match(["text/html", "application/json"])
    return best == "application/json"


def payload() -> dict:
    if request.is_json:
        return request.get_json(silent=True) or {}
    if request.form:
        return {k: v for k, v in request.form.items()}
    return {}


def field_list(value):
    """Form values may arrive as one string or a list; always give a list."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def checkbox(name: str, default: bool = False) -> bool:
    """HTML checkboxes only send a value when ticked."""
    if name not in request.form:
        return default
    return to_bool(request.form.get(name))


def sanitize(collection: str, body: dict | None = None, partial: bool = False) -> dict:
    """Keep only the columns the schema declares, cast to their declared type.

    Leaders post arbitrary form data, so this is what stops a typo from adding
    a phantom column to your Google Sheet.
    """
    body = body if body is not None else payload()
    fields = COLLECTIONS[collection]["fields"]
    out: dict = {}
    for field in fields:
        if field not in body or field in {"id", "created_at"}:
            continue
        value = body[field]
        if field in JSON_FIELDS:
            if isinstance(value, str):
                try:
                    out[field] = json.loads(value)
                except json.JSONDecodeError:
                    out[field] = None
            else:
                out[field] = value
        elif field in NUMBER_FIELDS:
            try:
                out[field] = float(value) if "." in str(value) else int(str(value or 0))
            except (TypeError, ValueError):
                out[field] = 0
        elif field in BOOL_FIELDS:
            out[field] = to_bool(value)
        else:
            out[field] = "" if value is None else str(value)
    if not partial:
        out["updated_at"] = now_iso()
    return out


def ok(**data):
    return jsonify({"ok": True, **data})


def fail(status: int, code: str, zh: str, en: str = "", **extra):
    return jsonify({"error": code, "message_zh": zh, "message_en": en or zh, **extra}), status


def audit(actor: dict, action: str, entity: str = "", entity_id: str = "", detail: dict | None = None) -> None:
    store().insert("audit_log", {
        "actor_id": (actor or {}).get("id", ""), "actor_role": (actor or {}).get("role", ""),
        "action": action, "entity": entity, "entity_id": entity_id,
        "detail_json": json.dumps(detail or {}, ensure_ascii=False), "created_at": now_iso(),
    })


def to_csv(rows: list[dict], headers: list[str] | None = None) -> str:
    if not rows and not headers:
        return ""
    cols = headers or list(rows[0].keys())
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({col: _csv_value(row.get(col)) for col in cols})
    return buffer.getvalue()


def _csv_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return value


def parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]


class Redirect(Exception):
    """Raised to bounce a form POST back to a page (with a flash message)."""

    def __init__(self, endpoint: str, **values):
        super().__init__(endpoint)
        self.endpoint = endpoint
        self.values = values


def back(fallback: str = "scout_routes.home"):
    """Where to send a browser form post: the page it came from."""
    target = request.headers.get("Referer") or ""
    if target and request.host_url in target:
        return redirect(target)
    from flask import url_for

    return redirect(url_for(fallback))


__all__ = [
    "store", "wants_json", "payload", "sanitize", "ok", "fail", "audit",
    "to_csv", "parse_csv", "back", "field_list", "checkbox", "Redirect", "g",
]
