#!/usr/bin/env python3
"""Builds bridge-preview.html — 遊戲 2 alone, as ONE clickable offline file.

    cd scout-platform-py && python3 tools/bridge_preview.py

`demo-preview.html` tells the whole story, so a visitor has to walk the cave
before the crossing opens. The leader wanted a direct door for reviewing game 2,
so this script renders just the 迷霧渡口 page, clears its server endpoint (the
game checks the planks itself offline) and inlines every style, script and
picture. Open it and the river bank is already on screen.
"""
from __future__ import annotations

import base64
import html
import json
import os
import pathlib
import re
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SECRET_KEY", "offline-demo")
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="bridge-preview-")
os.environ["SEED_DEMO"] = "true"
os.environ.setdefault("DEMO_LOGIN", "true")

from app import create_app                                   # noqa: E402
from scout.store import Store                                # noqa: E402

BUILD = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")

app = create_app()
client = app.test_client()
store = Store.from_env()

work = next(t for t in store.list("tasks") if t.get("code") == "M05")
membership = sorted(store.list("badges"), key=lambda b: int(b["order_index"]))[0]

response = client.post("/login/demo/demo2", follow_redirects=False)
sid = response.headers["Location"].split("sid=", 1)[1]
page = client.get(f"/tasks/{work['id']}/bridge?sid={sid}").get_data(as_text=True)


def data_uri(path: pathlib.Path) -> str:
    kind = {"webp": "webp", "jpg": "jpeg", "jpeg": "jpeg", "png": "png"}[path.suffix.lstrip(".").lower()]
    return f"data:image/{kind};base64," + base64.b64encode(path.read_bytes()).decode()


# ── the one screen ─────────────────────────────────────────────────────────
style_blocks = re.findall(r"<style>(.*?)</style>", page, re.S)
body = re.search(r"<body[^>]*>(.*)</body>", page, re.S).group(1)
# no breadcrumbs in a single-screen file, and no dead doors: the game is all there is
body = re.sub(r'<div class="crumbs">.*?</div>\s*', "", body, flags=re.S)
body = body.replace('href="/home"', 'href="#" data-off="1"')
body = body.replace(f'href="/badges/{membership["id"]}"', 'href="#" data-off="1"')
# the hidden clone of 回到會員章 is only useful inside the platform; the task's
# revision links stay (in this file they are ordinary external links)
body = re.sub(r'<a data-bridge-link="badge"[^>]*>[^<]*</a>', "", body, count=1)
# this copy is self-contained: it grades the planks itself, with no endpoint
def clear_submit(match: re.Match) -> str:
    config = json.loads(html.unescape(match.group(2)))
    config["submit_url"] = ""
    config.pop("run_key", None)
    return match.group(1) + html.escape(json.dumps(config, ensure_ascii=False), quote=True) + match.group(3)


body = re.sub(r'(data-bridge-config=")(.*?)(")', clear_submit, body, count=1, flags=re.S)
assert 'data-bridge-config' in body and '"submit_url": ""' in html.unescape(body)

css = (ROOT / "static/styles.css").read_text()
fx = (ROOT / "static/js/effects.js").read_text()
game = (ROOT / "static/js/bridge.js").read_text()

out = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>迷霧渡口 · 遊戲 2 · 離線試玩 The misty crossing · offline play</title>
<!-- build: {BUILD} -->
<style>
{css}
/* ── the single-screen shell ── */
body {{ margin: 0; background: #101a15; }}
.cave-art {{ display: block; }}
a[data-off] {{ cursor: default; opacity: .55; }}
</style>
<script>
{fx}
</script>
</head>
<body>
{body}
<div hidden aria-hidden="true">{"".join(f'<span>{block}</span>' for block in style_blocks)}</div>
<script>
{game}
</script>
<script>
/* the whole file is one game: a stray # link must not reload it */
document.addEventListener('click', function (event) {{
  var off = event.target.closest('a[data-off]');
  if (off) event.preventDefault();
}});
</script>
</body>
</html>
"""

for path in sorted((ROOT / "static").rglob("*")):
    if path.suffix.lower() in (".webp", ".jpg", ".jpeg", ".png"):
        src = "/static/" + path.relative_to(ROOT / "static").as_posix()
        out = out.replace(f'src="{src}"', f'src="{data_uri(path)}"')
out = re.sub(r'src="/(?!data:)[^"]+"', 'src=""', out)

target = pathlib.Path(os.environ.get("BRIDGE_PREVIEW_OUTPUT") or ROOT / "bridge-preview.html")
target.write_text(out)
left = len(re.findall(r'src="/(?!data:)', out))
print(f"{target.name} written — {target.stat().st_size / 1024:,.0f} KB, "
      f"external fetches left: {left}")
