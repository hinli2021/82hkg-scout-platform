"""The lenient key parser and the browser-side checker the leader can use."""
from __future__ import annotations

import json
import pathlib

import pytest

from scout.store import _unescape_raw_newlines, parse_service_account

ROOT = pathlib.Path(__file__).resolve().parent.parent

KEY = {
    "type": "service_account", "project_id": "82hkg-scout",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkq\n-----END PRIVATE KEY-----\n",
    "client_email": "scout-platform@82hkg-scout.iam.gserviceaccount.com",
    "token_uri": "https://oauth2.googleapis.com/token",
}


def test_a_normal_key_parses():
    assert parse_service_account(json.dumps(KEY))["client_email"] == KEY["client_email"]


def test_a_value_wrapped_in_quotes_is_accepted():
    """Some copy paths hand you the value already quoted."""
    assert parse_service_account(json.dumps(json.dumps(KEY)))["project_id"] == "82hkg-scout"


def test_real_newlines_inside_the_private_key_are_repaired():
    """An editor that turns the key's \\n escapes into real breaks."""
    raw = json.dumps(KEY).replace("\\n", "\n")
    assert "-----BEGIN PRIVATE KEY-----\n" in raw                 # genuinely broken JSON
    parsed = parse_service_account(raw)
    assert parsed["private_key"].count("\n") >= 2
    assert parsed["client_email"] == KEY["client_email"]


def test_stray_whitespace_and_bom_do_not_matter():
    assert parse_service_account("\ufeff  " + json.dumps(KEY) + "\n\n")["project_id"] == "82hkg-scout"


def test_a_pasted_path_is_rejected_with_the_original_message():
    with pytest.raises(ValueError) as caught:
        parse_service_account(r"C:\Users\me\Downloads\82hkg-scout.json")
    assert "Expecting value" in str(caught.value)          # advice text keys off this


def test_a_truncated_key_is_still_rejected():
    with pytest.raises(ValueError):
        parse_service_account('{"type": "service_account", "client_email": "scout@x')


def test_the_unescape_helper_leaves_outside_text_alone():
    text = '{"a": 1,\n "b": "x\\ny"}'
    assert _unescape_raw_newlines(text) == '{"a": 1,\n "b": "x\\ny"}'


def test_the_browser_checker_exists_and_makes_no_network_calls():
    page = ROOT / "tools/check-service-account.html"
    html = page.read_text(encoding="utf-8")
    assert "檢查服務帳戶金鑰" in html
    assert "不會上傳" in html
    for forbidden in ("<script src=", "fetch(", "XMLHttpRequest", "https://fonts", "cdn."):
        assert forbidden not in html, f"檢查工具不可以有外部連線：{forbidden}"
    # it must know the same three mistakes
    for symptom in ("檔案路徑", "service_account", "iam.gserviceaccount.com", "BEGIN PRIVATE KEY"):
        assert symptom in html
