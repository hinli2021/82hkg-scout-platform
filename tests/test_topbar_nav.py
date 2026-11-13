"""手機頂欄 — the top bar collapses into a hamburger menu on narrow screens,
and the home tiles for cards and feedback keep their wording short."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_both_roles_get_a_hamburger_button(store, new_scout, leader_client):
    for page in (new_scout.get("/home").get_data(as_text=True),
                 leader_client.get("/leader").get_data(as_text=True)):
        assert 'data-nav-toggle' in page
        assert 'id="top-nav"' in page
        assert 'aria-expanded="false"' in page
        assert 'aria-controls="top-nav"' in page


def test_the_hamburger_rules_live_in_the_stylesheet():
    css = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")
    assert "@media (max-width: 960px)" in css
    assert ".tabbar.open" in css
    assert ".topbar .nav-toggle { display: none;" in css  # wide screens keep the full bar
    js = (ROOT / "static" / "js" / "effects.js").read_text(encoding="utf-8")
    assert "data-nav-toggle" in js and "aria-expanded" in js


def test_home_tiles_keep_their_wording_short(store, new_scout):
    home = new_scout.get("/home").get_data(as_text=True)
    # the long explanations are gone from the square tiles
    assert "完成遊戲就有卡包" not in home
    assert "領袖查看後，可能會給你積分作獎勵" not in home
    assert "平台有問題，或者你有新主意" not in home
    # one short line each is enough
    assert "收集技能卡" in home
    assert "報告問題，提出建議" in home

    new_scout.get("/set-language/en")
    english = new_scout.get("/home").get_data(as_text=True)
    assert "Collect skill cards" in english
    assert "Report bugs, share ideas" in english
    assert "收集技能卡" not in english
