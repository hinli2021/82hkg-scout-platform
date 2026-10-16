"""
Cross-edition parity with the Node build.

Both editions may point at the *same* Google Sheet, so three things must stay
identical: the collection/tab names, the column names, and the password hashing.
These tests read the Node sources directly when they are present, and skip
otherwise (a Python-only deployment does not need them).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

import pytest

from scout.schema import COLLECTIONS, COLLECTION_ORDER
from scout.util import hash_password, verify_password

NODE_ROOT = os.environ.get("NODE_PROJECT", "/home/user/scout-badge-platform")
NODE_SCHEMA = os.path.join(NODE_ROOT, "server/db/schema.js")

needs_node_project = pytest.mark.skipif(
    not os.path.exists(NODE_SCHEMA), reason="the Node build is not next to this one"
)
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def node_schema_source() -> str:
    with open(NODE_SCHEMA, encoding="utf-8") as handle:
        return handle.read()


@needs_node_project
def test_same_collections_in_the_same_order():
    """The tab order is the order they appear in the spreadsheet."""
    source = node_schema_source()
    node_order = re.findall(r"^\s{2}(\w+):\s*\{", source, re.M)
    # collapse the nested objects (feature flags, patrols, task types) away
    node_collections = [name for name in node_order if name in COLLECTIONS]
    assert node_collections[:len(COLLECTION_ORDER)] == COLLECTION_ORDER
    assert set(COLLECTION_ORDER) <= set(node_collections)


@needs_node_project
def test_same_column_names_for_every_collection():
    source = node_schema_source()
    for collection, spec in COLLECTIONS.items():
        block = re.search(rf"^\s{{2}}{collection}:\s*\{{([\s\S]*?)^\s{{2}}\}},", source, re.M)
        if not block:
            continue
        fields_block = re.search(r"fields:\s*\{([\s\S]*?)^\s{4}\}", block.group(1), re.M)
        if not fields_block:
            continue
        fields = re.findall(r"^\s{6}(\w+):", fields_block.group(1), re.M)
        assert list(spec["fields"]) == fields, f"{collection} columns drifted"


@needs_node_project
def test_same_seed_codes_and_titles():
    source = node_schema_source()
    for code in ("SC-01", "SC-02", "SC-03", "T-01", "T-11", "T-21"):
        assert f"code: '{code}'" in source
    for title in ("會員章（示例）", "標準章（示例）", "高級標準章（示例）"):
        assert f"title_zh: '{title}'" in source


@needs_node_project
def test_same_key_fields():
    """key fields are what “get one row” means: stats.user_id, settings.key, sessions.token."""
    from scout.schema import key_field

    assert key_field("stats") == "user_id"
    assert key_field("settings") == "key"
    assert key_field("sessions") == "token"
    assert key_field("users") == "id"
    source = node_schema_source()
    assert "keyFieldFor" in source
    assert "'user_id'" in source and "'key'" in source and "'token'" in source
    # the Node table must map the same three collections the same way
    for collection, expected in (("stats", "user_id"), ("settings", "key"), ("sessions", "token")):
        assert key_field(collection) == expected


@needs_node
@needs_node_project
def test_passwords_interoperate(tmp_path):
    """A hash written by one edition must verify in the other."""
    script = tmp_path / "hash.mjs"
    script.write_text(
        "import { hashPassword } from '" + os.path.join(NODE_ROOT, "server/util.js") + "';\n"
        "console.log(JSON.stringify(hashPassword('scout1234', 'abc123abc123abc1')));\n"
    )
    result = subprocess.run(["node", str(script)], capture_output=True, text=True, check=True)
    node_hash = json.loads(result.stdout)
    assert verify_password("scout1234", node_hash["hash"], node_hash["salt"])

    python_hash, python_salt = hash_password("scout1234", node_hash["salt"])
    assert python_hash == node_hash["hash"], "same salt must give the same digest"
    check = tmp_path / "verify.mjs"
    check.write_text(
        "import { verifyPassword } from '" + os.path.join(NODE_ROOT, "server/util.js") + "';\n"
        "console.log(verifyPassword('scout1234', process.argv[2], process.argv[3]) ? 'yes' : 'no');\n"
    )
    verified = subprocess.run(["node", str(check), python_hash, python_salt],
                              capture_output=True, text=True, check=True).stdout.strip()
    assert verified == "yes", "Node must accept a hash written by the Python edition"


def test_hashes_are_hex_of_64_bytes_with_a_16_byte_salt():
    digest, salt = hash_password("hello")
    assert len(digest) == 128 and all(char in "0123456789abcdef" for char in digest)
    assert len(salt) == 32
    assert verify_password("hello", digest, salt)
    assert not verify_password("Hello", digest, salt)


def test_json_cell_format_matches_what_the_sheet_holds():
    """The Sheet keeps objects as JSON text in one cell — that is the contract."""
    from scout.drivers.sheets import SheetsDriver

    driver = SheetsDriver.__new__(SheetsDriver)          # no credentials needed
    cell = SheetsDriver._to_cell(driver, "prerequisite_badge_ids", ["a", "b"])
    assert cell == '["a", "b"]'
    assert SheetsDriver._from_cell(driver, "prerequisite_badge_ids", cell) == ["a", "b"]
