"""
Shared helpers — ids, password hashing, dates, small conversions.

Password hashing deliberately matches the Node build byte-for-byte:
Node:   crypto.scryptSync(password, salt, 64)  → hex
Python: hashlib.scrypt(password, salt=salt, n=2**14, r=8, p=1, dklen=64)
Both use N=16384, r=8, p=1 (Node's defaults), so an account created by either
version can sign in to the other — the Google Sheet stays the source of truth.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from datetime import date, datetime, timedelta, timezone

TZ = "Asia/Hong_Kong"
SCRYPT_N, SCRYPT_R, SCRYPT_P, SCRYPT_LEN = 2**14, 8, 1, 64


def new_id() -> str:
    """16-char hex id, same shape as the Node build's ids."""
    return secrets.token_hex(8)


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(
        str(password).encode("utf-8"), salt=salt.encode("utf-8"),
        n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=SCRYPT_LEN,
    )
    return digest.hex(), salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    if not hashed or not salt:
        return False
    candidate, _ = hash_password(password, salt)
    return hmac.compare_digest(candidate, str(hashed))


def now_iso() -> str:
    """UTC ISO-8601 with milliseconds, the format both builds store."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"


def today_iso(tz: str = TZ) -> str:
    """YYYY-MM-DD in the unit's local timezone (Hong Kong by default)."""
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(tz)).date().isoformat()
    except Exception:  # pragma: no cover - exotic environments
        return datetime.now(timezone.utc).date().isoformat()


def days_between(a: str, b: str) -> float:
    if not a or not b:
        return float("inf")
    try:
        d1 = date.fromisoformat(str(a)[:10])
        d2 = date.fromisoformat(str(b)[:10])
    except ValueError:
        return float("inf")
    return (d2 - d1).days


def shift_date(iso_date: str, days: int) -> str:
    d = date.fromisoformat(str(iso_date)[:10])
    return (d + timedelta(days=days)).isoformat()


def local_date(value: str, tz: str = TZ) -> str:
    """The unit's calendar date for a stored timestamp."""
    if not value:
        return ""
    iso = str(value)
    if len(iso) <= 10:
        return iso
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        from zoneinfo import ZoneInfo

        return dt.astimezone(ZoneInfo(tz)).date().isoformat()
    except Exception:
        return iso[:10]


def parse_time(value: str) -> float:
    """Timestamp → epoch seconds (0 when empty/unparseable). Used for sorting."""
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"true", "1", "yes", "y", "on"}


def clamp(n, low, high) -> float:
    try:
        value = float(n)
    except (TypeError, ValueError):
        value = 0.0
    return max(low, min(high, value))


def slug(text: str) -> str:
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", str(text or "").strip().lower()))


def generate_password() -> str:
    """Readable temporary password (avoid ambiguous characters)."""
    words = ["tiger", "otter", "gull", "camp", "rope", "trail", "map", "fire"]
    word = secrets.choice(words)
    return f"{word}-{secrets.randbelow(90) + 10}-{secrets.token_hex(2)}"


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
