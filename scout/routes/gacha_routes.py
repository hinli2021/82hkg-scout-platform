"""抽卡 — open a pack, keep the album.

Packs are earned, and a normal pack can also be bought with points. A gold
pack cannot be bought. The page works without JavaScript: the form
opens the oldest pack and the next page shows the five cards face up. With
JavaScript, the same POST returns the card markup and the page flips them.
"""
from __future__ import annotations

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from ..auth import scout_required
from ..engine import as_int
from ..gacha import (
    PACK_PRICE, RATES, RARITY_NAME, album, album_sections, buy_standard_pack, enabled,
    open_next, sync_earned_packs, until_sr,
)
from .helpers import audit, fail, ok, store, wants_json

gacha_routes = Blueprint("gacha_routes", __name__)


def _closed():
    flash({"kind": "warn", "zh": "抽卡未開放 — 領袖可在設定中開啟。",
           "en": "Cards are not open yet — a leader can switch them on in Settings."}, "result")
    return redirect(url_for("scout_routes.home"))


def _gate():
    st = store()
    if enabled(st.settings_cached()):
        return None
    if wants_json():
        return fail(403, "gacha_closed", "抽卡未開放", "Cards are not open yet")
    return _closed()


def _families(sections: list[dict]) -> list[dict]:
    families = []
    for section in sections:
        if not families or families[-1]["id"] != section["family"]:
            families.append({
                "id": section["family"],
                "zh": section["family_zh"],
                "en": section["family_en"],
                "sections": [],
            })
        families[-1]["sections"].append(section)
    return families


def _view(user, *, reveal: bool, category: str = "") -> dict:
    st = store()
    state = sync_earned_packs(st, user)
    opened = state.get("last_open_json") if reveal else None
    packs = state["packs_json"]
    nxt = packs[0] if packs else None
    sections = album_sections(state)
    keep = {"reveal": 1} if reveal else {}
    for section in sections:
        section["href"] = url_for("gacha_routes.page", cat=section["id"], **keep)
    chosen = next((section for section in sections if section["id"] == category), None)
    return {
        "summary": {
            "packs": len(packs),
            "gold": sum(1 for pack in packs if pack.get("kind") == "gold"),
            "owned": sum(1 for slot in state["owned_json"].values() if int(slot.get("count") or 0) > 0),
            "total": len(album(state)),
            "until_sr": until_sr(state["pity"]),
            "opened": int(state["opened"] or 0),
            "next_kind": (nxt or {}).get("kind") or "standard",
            "next_reason_zh": (nxt or {}).get("reason_zh") or "",
            "next_reason_en": (nxt or {}).get("reason_en") or "",
            "points": as_int(st.stats_for(user["id"]).get("points_balance")),
            "price": PACK_PRICE,
        },
        "reveal": opened,
        "families": _families(sections),
        "category": chosen,
        # the album opens on every card; a category narrows it to one set
        "all_href": url_for("gacha_routes.page", **keep),
        "sections": [chosen] if chosen else sections,
        "rates": [
            {"code": code, "zh": RARITY_NAME[code][0], "en": RARITY_NAME[code][1],
             "rate": weight / 10}
            for code, weight in RATES
        ],
    }


@gacha_routes.get("/cards")
@scout_required
def page():
    closed = _gate()
    if closed:
        return closed
    return render_template(
        "scout/gacha.html",
        **_view(g.user, reveal=request.args.get("reveal") == "1",
                category=request.args.get("cat") or ""),
    )


@gacha_routes.post("/cards/open")
@scout_required
def open_pack():
    closed = _gate()
    if closed:
        return closed
    st = store()
    sync_earned_packs(st, g.user)
    opened = open_next(st, g.user)
    if not opened:
        if wants_json():
            return fail(409, "no_pack", "沒有卡包可打開", "No pack to open")
        flash({"kind": "warn", "zh": "沒有卡包可打開。完成遊戲或獎章之後再來。",
               "en": "No pack to open. Finish a game or a badge, then come back."}, "result")
        return redirect(url_for("gacha_routes.page"))
    audit(g.user, "open_pack", "gacha", opened["pack"].get("id", ""),
          {"kind": opened["pack"].get("kind"), "source": opened["pack"].get("source"),
           "rarities": [card["rarity"] for card in opened["cards"]]})
    if wants_json():
        view = _view(g.user, reveal=True)
        return ok(
            html=render_template("scout/_gacha_reveal.html", reveal=opened, summary=view["summary"]),
            packs=view["summary"]["packs"],
            until_sr=view["summary"]["until_sr"],
            owned=view["summary"]["owned"],
        )
    return redirect(url_for("gacha_routes.page", reveal=1))


@gacha_routes.post("/cards/buy")
@scout_required
def buy_pack():
    """Points buy one normal pack. The form cannot ask for a gold pack."""
    closed = _gate()
    if closed:
        return closed
    result = buy_standard_pack(store(), g.user)
    if not result["ok"]:
        if wants_json():
            return fail(402, "not_enough_points",
                        f"積分不夠。普通卡包要 {PACK_PRICE} 分。",
                        f"Not enough points. A normal pack costs {PACK_PRICE}.",
                        balance=result["balance"], price=PACK_PRICE)
        flash({"kind": "warn",
               "zh": f"積分不夠。普通卡包要 {PACK_PRICE} 分。",
               "en": f"Not enough points. A normal pack costs {PACK_PRICE}."}, "result")
        return redirect(url_for("gacha_routes.page"))
    audit(g.user, "buy_pack", "gacha", "", {"price": PACK_PRICE, "kind": "standard"})
    if wants_json():
        return ok(balance=result["balance"], price=PACK_PRICE, kind="standard")
    flash({"kind": "success",
           "zh": f"已用 {PACK_PRICE} 積分換了一個普通卡包。",
           "en": f"A normal pack is yours, for {PACK_PRICE} points."}, "result")
    return redirect(url_for("gacha_routes.page"))
