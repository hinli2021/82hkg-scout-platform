"""Cloudflare R2 — where card pictures live when the leader sets it up.

Card pictures are the one upload the platform shows back to every scout, so
they earn a real image host: R2 stores them as objects and serves them from
a public address, instead of a Google Drive folder whose links open a viewer
page. Everything here is opt-in — until the five environment values below
are set, `configured()` is false and callers keep using the unit Drive.

R2 speaks the S3 protocol, so the upload is one signed PUT. The signature
is AWS Signature Version 4, written out by hand to keep the dependency list
exactly as it is.
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from urllib.parse import quote, urlparse

import requests

#: Environment (or app config) names the leader fills in — see 設定檢查.
ENV_KEYS = (
    "CLOUDFLARE_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET",
    "R2_PUBLIC_BASE_URL",
)


def config(app_config=None, environ=None) -> dict:
    """Read the five values; app config wins, the environment backs it up."""
    values = {}
    for key in ENV_KEYS:
        value = ""
        if app_config is not None:
            value = str(app_config.get(key) or "")
        if not value and environ is not None:
            value = str(environ.get(key) or "")
        values[key] = value.strip()
    return values


def configured(cfg: dict) -> bool:
    return all(cfg.get(key) for key in ENV_KEYS)


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _signed_headers(cfg: dict, url: str, payload_hash: str) -> dict:
    """AWS SigV4 headers for one PUT to R2 (region 'auto', service 's3')."""
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    host = urlparse(url).netloc
    headers = {
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }
    signed = ";".join(sorted(headers))
    canonical = "\n".join([
        "PUT", urlparse(url).path, "",
        "".join(f"{name}:{headers[name]}\n" for name in sorted(headers)),
        signed, payload_hash,
    ])
    scope = f"{date_stamp}/auto/s3/aws4_request"
    to_sign = "\n".join([
        "AWS4-HMAC-SHA256", amz_date, scope,
        hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    ])
    key = _sign(("AWS4" + cfg["R2_SECRET_ACCESS_KEY"]).encode("utf-8"), date_stamp)
    key = _sign(key, "auto")
    key = _sign(key, "s3")
    key = _sign(key, "aws4_request")
    signature = hmac.new(key, to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    headers["Authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={cfg['R2_ACCESS_KEY_ID']}/{scope}, "
        f"SignedHeaders={signed}, Signature={signature}"
    )
    return headers


def upload(cfg: dict, *, name: str, mime_type: str, data: bytes) -> dict:
    """Put one picture in the bucket; returns the usual upload record."""
    key = f"cards/{name}"
    endpoint = (
        f"https://{cfg['CLOUDFLARE_ACCOUNT_ID']}.r2.cloudflarestorage.com"
        f"/{cfg['R2_BUCKET']}/{quote(key, safe='/')}"
    )
    headers = _signed_headers(cfg, endpoint, hashlib.sha256(data).hexdigest())
    headers["Content-Type"] = mime_type or "image/png"
    response = requests.put(endpoint, data=data, headers=headers, timeout=30)
    if response.status_code not in (200, 201, 204):
        raise RuntimeError(f"R2 answered {response.status_code}")
    return {
        "id": key,
        "url": f"{cfg['R2_PUBLIC_BASE_URL'].rstrip('/')}/{key}",
        "stored": "r2",
    }
