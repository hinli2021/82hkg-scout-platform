"""Vercel entry point — the same Flask app, served as a serverless function.

Everything the platform does (sign-in, the games, the leader console) runs here
unchanged. Two things are set before the app is imported:

* ``DATA_DIR`` — Vercel's disk is read-only apart from ``/tmp``, so the JSON
  store lives there. That is enough to walk the whole platform on a test
  deployment (示範帳號、遊戲、領袖後台), but ``/tmp`` is per-instance: after a
  while without traffic the instance is recycled and the demo data is seeded
  again. For data that survives between visits, set ``DATA_DRIVER=sheets`` and
  the ``GOOGLE_*`` variables — the spreadsheet is the database, exactly as
  ``docs/02-google-sheets-setup.md`` describes.
* ``SESSION_SECRET`` — ``app.py`` otherwise generates a random key per process,
  which would invalidate every cookie and every signed cave run on each cold
  start. Set ``SESSION_SECRET`` in the Vercel project settings and this default
  is not used.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("DATA_DIR", "/tmp/scout-platform-data")
os.environ.setdefault("DEMO_LOGIN", "true")     # /login/demo/demo1 … for testing
os.environ.setdefault("SEED_DEMO", "true")      # 示範領袖與七個示範童軍
os.environ.setdefault("SESSION_SECRET", "82hkg-vercel-test-key-change-me")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app  # noqa: E402  (the factory already ran at import time)

handler = app          # Vercel looks for `app`/`handler`
application = app
