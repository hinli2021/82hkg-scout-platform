"""Card packs are earned, opened five at a time, and never bought."""
from __future__ import annotations

import random

from scout import gacha


class AlwaysCommon(random.Random):
    """Every roll lands in the first bucket, which is Common."""

    def randrange(self, start, stop=None, step=1):
        return 0

    def sample(self, population, k):
        return list(population)[:k]


def test_rates_are_the_public_table():
    assert sum(weight for _, weight in gacha.RATES) == 1000
    assert gacha.roll_rarity(AlwaysCommon()) == "C"
    assert gacha.roll_rarity(AlwaysCommon(), floor="SR") == "SR"


def test_ten_dry_packs_force_an_sr(store, new_scout):
    user = new_scout.user
    state = gacha.load_state(store, user["id"])
    state["packs_json"] = [{
        "id": "p", "kind": "standard", "source": "task", "ref_id": "x",
        "reason_zh": "測試", "reason_en": "Test", "granted_at": "2026-01-01",
    }]
    state["pity"] = gacha.PITY_AFTER
    gacha.save_state(store, state)
    opened = gacha.open_next(store, user, rng=AlwaysCommon())
    assert len(opened["cards"]) == 5
    assert any(card["rarity"] in gacha.SR_PLUS for card in opened["cards"])
    assert gacha.load_state(store, user["id"])["pity"] == 0


def test_a_gold_pack_also_guarantees_sr(store, new_scout):
    user = new_scout.user
    gacha.grant_pack(
        store, user, key="badge:test", kind="gold", source="badge", ref_id="b",
        reason_zh="考獲測試章", reason_en="Earned a test badge",
    )
    opened = gacha.open_next(store, user, rng=AlwaysCommon())
    assert opened["pack"]["kind"] == "gold"
    assert any(card["rarity"] in gacha.SR_PLUS for card in opened["cards"])


def test_opening_credit_does_not_earn_a_pack_but_a_real_task_does(store, new_scout):
    user = new_scout.user
    task = next(row for row in store.list("tasks") if row.get("status") == "published")
    before = gacha.sync_earned_packs(store, user)
    store.insert("progress_records", {
        "user_id": user["id"], "badge_id": task["badge_id"], "task_id": task["id"],
        "status": "completed", "decided_by": "opening", "score": 100,
    })
    skipped = gacha.sync_earned_packs(store, user)
    assert len(skipped["packs_json"]) == len(before["packs_json"])
    store.insert("progress_records", {
        "user_id": user["id"], "badge_id": task["badge_id"], "task_id": "task-real",
        "status": "completed", "decided_by": "auto", "score": 80,
    })
    earned = gacha.sync_earned_packs(store, user)
    assert len(earned["packs_json"]) == len(before["packs_json"]) + 1
    assert earned["packs_json"][-1]["kind"] == "standard"
    assert gacha.sync_earned_packs(store, user)["grants_json"].count("task:task-real") == 1


def test_a_badge_earns_one_gold_pack(store, new_scout):
    user = new_scout.user
    badge = store.list("badges")[0]
    store.insert("badge_awards", {
        "user_id": user["id"], "badge_id": badge["id"], "awarded_at": "2026-01-01",
        "awarded_by": "auto", "note": "",
    })
    state = gacha.sync_earned_packs(store, user)
    gold = [pack for pack in state["packs_json"] if pack["kind"] == "gold"]
    assert len(gold) == 1
    assert gold[0]["source"] == "badge"


def test_points_buy_a_normal_pack_only(store, new_scout):
    user = new_scout.user
    store.stats_for(user["id"])
    store.update("stats", user["id"], {"points_balance": gacha.PACK_PRICE + 5})
    bought = gacha.buy_standard_pack(store, user)
    assert bought["ok"] and bought["balance"] == 5
    state = gacha.load_state(store, user["id"])
    packs = [pack for pack in state["packs_json"] if pack["source"] == "points"]
    assert len(packs) == 1 and packs[0]["kind"] == "standard"
    # a second buy must fail without taking the last 5 points or adding a pack
    refused = gacha.buy_standard_pack(store, user)
    assert not refused["ok"] and refused["balance"] == 5
    state = gacha.load_state(store, user["id"])
    assert sum(1 for pack in state["packs_json"] if pack["source"] == "points") == 1
    # the form cannot ask for gold — the route ignores any kind field
    store.update("stats", user["id"], {"points_balance": gacha.PACK_PRICE})
    response = new_scout.post("/cards/buy", data={"kind": "gold"})
    assert response.status_code == 200
    state = gacha.load_state(store, user["id"])
    assert state["packs_json"][-1]["kind"] == "standard"
    assert state["packs_json"][-1]["source"] == "points"


def test_album_is_split_into_categories(store, new_scout):
    sections = gacha.album_sections(gacha.sync_earned_packs(store, new_scout.user))
    assert [row["id"] for row in sections] == [
        "membership", "history", "patrol", "knots", "drill", "camping",
        "pursuit", "service", "interest",
    ]
    assert sum(row["total"] for row in sections) == 46
    assert sections[0]["show_family"] and sections[0]["family"] == "skill"
    assert sections[6]["show_family"] and sections[6]["family"] == "badge"
    page = new_scout.get("/cards").get_data(as_text=True)
    assert "技能卡" in page and "會員章" in page and "專科徽章" in page and "技能組" in page
    # every card is shown by default; a category only narrows the album
    assert "全部卡" in page and "選一個類別" not in page
    assert "童軍誓詞" in page and "平結" in page
    assert page.count("mini-card") == 46
    assert page.index("會員章") < page.index("繩結") < page.index("技能組")
    knots = new_scout.get("/cards?cat=knots").get_data(as_text=True)
    assert "平結" in knots and "稱人結" in knots
    assert "童軍誓詞" not in knots and "烹飪" not in knots
    assert "cat=knots" in knots and "aria-current" in knots
    # an unknown category falls back to showing everything
    assert "童軍誓詞" in new_scout.get("/cards?cat=nope").get_data(as_text=True)
    new_scout.get("/set-language/en")
    english = new_scout.get("/cards").get_data(as_text=True)
    assert "Skill cards" in english and "Membership" in english
    assert "Proficiency badges" in english and "All cards" in english
    assert "Choose a category" not in english
    assert english.index("Membership") < english.index("Knots") < english.index("Pursuit")
    knots_en = new_scout.get("/cards?cat=knots").get_data(as_text=True)
    assert "Reef knot" in knots_en and "Scout Promise" not in knots_en
    for word in ("技能卡", "會員章", "專科徽章", "技能組", "圖鑑分類", "平結", "童軍誓詞"):
        assert word not in knots_en


def test_cards_page_is_bilingual_and_can_be_switched_off(new_scout, store):
    # cards get a square home button too, the same shape as a badge tile
    home = new_scout.get("/home").get_data(as_text=True)
    assert "badge-tile feature-tile" in home and "抽卡" in home
    page = new_scout.get("/cards?cat=membership").get_data(as_text=True)
    assert "抽卡" in page and "童軍誓詞" in page
    new_scout.get("/set-language/en")
    english = new_scout.get("/cards?cat=membership").get_data(as_text=True)
    assert "Cards" in english and "Scout Promise" in english
    assert "Buy a normal pack" in english and "Gold packs cannot be bought" in english
    for word in ("抽卡", "卡包", "圖鑑", "童軍誓詞", "知識", "實踐", "積分"):
        assert word not in english
    flags = dict(store.settings()["feature_flags"])
    store.save_setting("feature_flags", {**flags, "gacha": False})
    assert new_scout.get("/cards", follow_redirects=False).status_code == 302
    assert 'href="/cards"' not in new_scout.get("/home").get_data(as_text=True)
