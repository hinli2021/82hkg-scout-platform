"""
The three patrol mascots — artwork, colours and a one-line personality.

The drawings come from the group's own mascot draft: the tiger (老虎), the otter
(水獺) and the seagull (海鷗). Each patrol gets the slice of that artwork with
its own character, plus a colour it owns everywhere in the platform (login
cards, HUD chips, progress rings).

Adding a patrol in *Leader → Settings* never breaks the login page: an unknown
patrol simply falls back to an emoji card in scout green.
"""
from __future__ import annotations

# ── the trio ────────────────────────────────────────────────────────────────

MASCOTS: dict[str, dict] = {
    "Tiger": {
        "patrol": "Tiger",
        "emoji": "🐯",
        "en_name": "Tiger",
        "img": "/static/img/mascots/tiger.webp",
        "tint": "#e0813c",
        "tint_dark": "#b9601f",
        "glow": "rgba(224, 129, 60, .55)",
        # where this animal sits in the full-screen scene (percent of width)
        "spot_x": 50.5,
        "spot_w": 25,
        "soft": "rgba(224, 129, 60, .14)",
        "tag_zh": "勇敢 · 敏捷",
        "tag_en": "Brave · quick",
    },
    "Otter": {
        "patrol": "Otter",
        "emoji": "🦦",
        "en_name": "Otter",
        "img": "/static/img/mascots/otter.webp",
        "tint": "#3f8fd0",
        "tint_dark": "#2a6ba3",
        "glow": "rgba(63, 143, 208, .55)",
        # where this animal sits in the full-screen scene (percent of width)
        "spot_x": 19.5,
        "spot_w": 25,
        "soft": "rgba(63, 143, 208, .14)",
        "tag_zh": "靈活 · 樂於助人",
        "tag_en": "Nimble · helpful",
    },
    "Seagull": {
        "patrol": "Seagull",
        "emoji": "🕊️",
        "en_name": "Seagull",
        "img": "/static/img/mascots/seagull.webp",
        "tint": "#2f9e94",
        "tint_dark": "#1f7a72",
        "glow": "rgba(47, 158, 148, .55)",
        # where this animal sits in the full-screen scene (percent of width)
        "spot_x": 80.5,
        "spot_w": 26,
        "soft": "rgba(47, 158, 148, .14)",
        "tag_zh": "高飛 · 眼界遠",
        "tag_en": "Flies high · sees far",
    },
}

FALLBACK: dict = {
    "patrol": "",
    "en_name": "New patrol",
    "emoji": "🐣",
    "img": "",
    "tint": "#2f8f5b",
    "tint_dark": "#1f6b43",
    "glow": "rgba(47, 143, 91, .5)",
    "soft": "rgba(47, 143, 91, .14)",
    "tag_zh": "新小隊",
    "tag_en": "New patrol",
}


def mascot_for(patrol: str) -> dict:
    """Mascot card data for a patrol value ("Tiger", "Otter", "Seagull", …)."""
    hit = MASCOTS.get(str(patrol or ""))
    if hit:
        return hit
    return {**FALLBACK, "patrol": patrol or ""}
