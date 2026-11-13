"""遊戲音樂與音效 — a synthesised cheerful tune on game pages only, plus the
extra sound effects the pipe game and the card reveal play."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_the_music_engine_is_synthesised_and_game_only():
    js = read("static/js/effects.js")
    assert "MUSIC_MELODY" in js
    assert "function startMusic" in js and "function stopMusic" in js
    assert "function pageWantsMusic" in js
    assert "is-game" in js and "data-music" in js
    assert "music: { start: startMusic" in js
    # no audio files: the tune is built from notes so it works offline
    assert ".mp3" not in js and ".wav" not in js and ".ogg" not in js


def test_the_extra_sound_effects_exist():
    js = read("static/js/effects.js")
    for name in ("pop", "place", "flip", "sparkle", "win", "fanfare"):
        assert f"{name}: function" in js, name


def test_game_pages_ask_for_music(store, new_scout):
    daily = new_scout.get("/daily").get_data(as_text=True)
    assert 'data-music="game"' in daily
    cards = new_scout.get("/cards").get_data(as_text=True)
    assert 'data-music="game"' in cards
    # ordinary pages stay quiet
    home = new_scout.get("/home").get_data(as_text=True)
    assert 'data-music="game"' not in home
    feedback = new_scout.get("/feedback").get_data(as_text=True)
    assert 'data-music="game"' not in feedback


def test_the_member_badge_games_still_carry_the_game_marker():
    for page in ("cave", "bridge", "drill", "flag"):
        assert 'class="is-game"' in read(f"templates/scout/{page}.html"), page


def test_the_pipe_game_plays_its_sound_effects():
    js = read("static/js/flag.js")
    assert 'sfx("place")' in js      # a pipe drops into its hole
    assert 'sfx("wrong")' in js      # the start button turns red
    assert 'sfx("win")' in js        # a run is right, the flag goes up
    assert '"fanfare"' in js         # the last run finishes the ceremony


def test_the_sound_button_now_covers_music_too(store, new_scout):
    page = new_scout.get("/home").get_data(as_text=True)
    assert "遊戲音樂與音效" in page
    new_scout.get("/set-language/en")
    english = new_scout.get("/home").get_data(as_text=True)
    assert "Game music and sound" in english
    assert "遊戲音樂與音效" not in english
