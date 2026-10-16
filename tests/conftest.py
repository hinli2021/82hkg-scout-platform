"""Test fixtures: a fresh, seeded, throw-away store per test session."""
from __future__ import annotations

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app           # noqa: E402
from scout.store import Store        # noqa: E402


@pytest.fixture()
def data_dir():
    with tempfile.TemporaryDirectory(prefix="pyscout-test-") as folder:
        yield folder


@pytest.fixture()
def store(data_dir, monkeypatch):
    monkeypatch.setenv("DATA_DIR", data_dir)
    monkeypatch.setenv("DATA_DRIVER", "local")
    monkeypatch.setenv("SEED_DEMO", "true")
    monkeypatch.setenv("DEMO_LOGIN", "true")
    return Store.from_env()


@pytest.fixture()
def app(store):
    application = create_app({"STORE": store, "TESTING": True, "SECRET_KEY": "test-secret"})
    application.testing = True
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def extras_on(store):
    """獎品 and 龍虎榜 are hidden by default; tests that cover them switch them on.

    This is the same thing a leader does in 設定 → 功能開關, so the tests walk
    the real path instead of a test-only door.
    """
    flags = dict(store.settings()["feature_flags"])
    store.save_setting("feature_flags", {**flags, "redeem": True, "leaderboard": True})
    return store


class Scout:
    """A signed-in scout client plus the user row behind it."""

    def __init__(self, client, user):
        self.client = client
        self.user = user

    @property
    def id(self):
        return self.user["id"]

    def get(self, path, **kw):
        return self.client.get(path, **kw)

    def post(self, path, data=None, json=None, **kw):
        headers = {"Accept": "application/json", "X-Requested-With": "fetch"}
        headers.update(kw.pop("headers", {}))
        return self.client.post(path, data=data, json=json, headers=headers, **kw)


def _find(store, username):
    return next(u for u in store.list("users") if u["username"] == username)


@pytest.fixture()
def scout_client(app, store):
    """signs in as scout01 through the real demo shortcut."""
    client = app.test_client()
    client.post("/login/demo/demo2")
    return Scout(client, _find(store, "scout03"))


@pytest.fixture()
def fresh_scout(app, store):
    """scout07 — never signed in, so the first-time flow can be tested."""
    return Scout(app.test_client(), _find(store, "scout07"))


def enter_as_first_timer(app, store, username="scout07", password=None):
    """Tap a name → required password/email setup before any scout pages."""
    user = _find(store, username)
    patrol = user["patrol"]
    client = app.test_client()
    client.get(f"/login/scout/{patrol}/{user['id']}")          # no password asked
    if password:
        client.post("/welcome", data={"password": password, "confirm": password,
                                      "email": "newscout@example.com"},
                    headers={"Accept": "application/json", "X-Requested-With": "fetch"})
    return Scout(client, user)


@pytest.fixture()
def new_scout(app, store):
    """scout07 signed in through the first-time flow — a blank slate.

    scout03 is already 5/9 through the sample content, so the tests that walk a
    scout through their *first* quiz / checklist / reflection use this one.
    """
    user = _find(store, "scout07")
    client = app.test_client()
    client.get(f"/login/scout/Seagull/{user['id']}")           # first tap → straight in
    client.post("/welcome", data={"password": "tiger777", "confirm": "tiger777",
                                  "email": "ng@example.com"},
                headers={"Accept": "application/json", "X-Requested-With": "fetch"})
    return Scout(client, user)


def leader_api(app, store):
    """A signed-in leader, for the console-only actions a test needs."""
    client = app.test_client()
    client.post("/login/leader", data={"username": "leader1", "password": "0082"})
    return client


def grant_awards(app, store, username, orders=(1, 2)):
    """A leader grants awards by hand — the console can do this too.

    In normal play a scout earns the awards in order; this is the shortcut the
    review tests use so the later awards' tasks are reachable.
    (POST /api/leader/scouts/<id>/award-badge/<badge_id>)
    """
    user = _find(store, username)
    leader = leader_api(app, store)
    badges = sorted(store.list("badges"), key=lambda b: int(b.get("order_index") or 0))
    for order in orders:
        badge = badges[order - 1]
        leader.post(f"/api/leader/scouts/{user['id']}/award-badge/{badge['id']}")
    return user


@pytest.fixture()
def mid_scout(app, store):
    """scout04 with 會員章 + 探索獎章 granted, so 標準獎章 is open.

    That is the award carrying the evidence and sign-off sample tasks.
    """
    user = grant_awards(app, store, "scout04", orders=(1, 2))
    client = app.test_client()
    client.post(f"/login/scout/Otter/{user['id']}", data={"password": "scout1234"})
    return Scout(client, user)


@pytest.fixture()
def leader_client(app, store):
    client = app.test_client()
    response = client.post("/login/leader", data={"username": "leader1", "password": "0082"})
    assert response.status_code in (200, 302)
    return Scout(client, _find(store, "leader1"))
