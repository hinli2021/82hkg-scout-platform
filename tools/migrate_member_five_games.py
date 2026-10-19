#!/usr/bin/env python3
"""Bring an EXISTING local demo's membership badge up to the five-game rule.

Run once after updating the code:

    DATA_DIR=./data SEED_DEMO=false python3 tools/migrate_member_five_games.py

It does not delete accounts, task progress, points or awards. Previously
completed item-4 records still count for game 1; new completions can only come
from finishing all 50 cave questions, regardless of score. Existing default
80-point copy is refreshed without overwriting leader-authored text. The
user-authored 11-item guide remains available as reference.
For a brand-new install, the normal seed already carries the new contract.
"""
from __future__ import annotations

import copy
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATA_DIR", str(ROOT / "data"))
os.environ.setdefault("SEED_DEMO", "false")

from scout.content import member_badge_guide       # noqa: E402
from scout.engine import as_int, as_json            # noqa: E402
from scout.schema import SEED_BADGES                # noqa: E402
from scout.store import Store                       # noqa: E402
from scout.util import now_iso                      # noqa: E402


# Replace only the previous default wording, never a leader's custom story.
LEGACY_STORY_COPY = {
    "start_zh": "划出去 →",
    "start_en": "Cast off →",
    "first_stage_note_zh": "按下「划出去」開始逃生冒險；第一個區域的遊戲是童軍歷史山洞。",
    "first_stage_note_en": "Cast off to begin your escape. The first area holds The Cave of Scouting History.",
    "trail_lead_zh": "這是你的荒島尋寶圖：點按任何一個區域，查看該區的遊戲。完成五個遊戲，才能到達沙灘取得木筏。",
    "trail_lead_en": "This is your island treasure map. Tap any area to see its game. Clear all five games to reach the raft on the beach.",
    "start_note_zh": "開始冒險 · 走過五個區域，便會到達沙灘",
    "start_note_en": "Start the adventure · five areas and you reach the beach",
}


def refresh_story_copy(guide: dict, source: dict) -> bool:
    changed = False
    quest = guide.get("quest") or {}
    for key, previous in LEGACY_STORY_COPY.items():
        if quest.get(key) == previous:
            quest[key] = source["quest"][key]
            changed = True
    return changed


# Earlier cave releases still described a pass mark, although game 1 now
# clears on reaching the exit. Only refresh that release's default sentences:
# an edited instruction or syllabus explanation belongs to its leader.
LEGACY_CAVE_COPY = {
    "req_zh": "在第一個區域完成「童軍歷史山洞」遊戲：閱讀四面壁畫，逐組完成 50 題；滿分 100 分，80 分合格。",
    "req_en": "In area one, clear The Cave of Scouting History: read four wall paintings and answer all 50 questions in groups. The pass mark is 80 out of 100.",
    "stage_hint_zh": "看完四段壁畫，在石室回答共 50 題；80 分合格，無須另做試卷。",
    "stage_hint_en": "Read four wall paintings and answer 50 chamber questions; pass at 80. No separate paper.",
    "method_note_zh": "完成山洞遊戲後自動記錄成績",
    "method_note_en": "The cave records your score automatically",
    "instruction_zh": "第一個區域只有童軍歷史山洞：先閱讀四段壁畫，再在石室走過 50 題；每題 2 分，80 分合格。完成山洞就完成第 4 項，不必另做試卷。",
    "instruction_en": "The first area's only game is the cave: read four wall paintings, then answer 50 chamber questions. Each is worth 2 marks; pass at 80. Clearing the cave completes item 4 — no separate paper.",
}


def refresh_cave_copy(guide: dict, source: dict) -> bool:
    item = guide["items"][3]
    standard = source["items"][3]
    changed = False
    for key in ("req_zh", "req_en"):
        entries = item.get(key) or []
        if entries and entries[0] == LEGACY_CAVE_COPY[key]:
            entries[0] = standard[key][0]
            changed = True
    for key in ("stage_hint_zh", "stage_hint_en", "method_note_zh", "method_note_en"):
        if item.get(key) == LEGACY_CAVE_COPY[key]:
            item[key] = standard[key]
            changed = True
    return changed


def cave_task_patch(task: dict, canonical: dict) -> dict:
    patch = {}
    if as_int(task.get("pass_score")) != 0:
        patch["pass_score"] = 0
    for key in ("instruction_zh", "instruction_en"):
        if task.get(key) == LEGACY_CAVE_COPY[key]:
            patch[key] = canonical[key]
    return patch


# ── game 2: the bridge in area 2 ──────────────────────────────────────────
# The misty crossing (迷霧渡口) is bound to M05 and belongs to the second area.
# Existing installs may predate both the area binding and the task itself.
BRIDGE_CODE = "M05"


def ensure_bridge(st: Store, badge: dict, blueprint: dict) -> tuple[bool, bool]:
    """Returns (guide_changed, task_changed). Never touches leader edits."""
    guide_changed = task_changed = False

    canonical = next((t for t in SEED_BADGES[0]["tasks"] if t["code"] == BRIDGE_CODE), None)
    if canonical is None:
        return False, False
    area = (blueprint["areas"][1] if len(blueprint["areas"]) > 1 else {})

    task = next((t for t in st.list("tasks")
                 if t.get("badge_id") == badge["id"] and t.get("code") == BRIDGE_CODE), None)
    if task is None:
        config = dict(canonical.get("config_json", {}))
        task = st.insert("tasks", {
            "badge_id": badge["id"], "order_index": 5, "code": BRIDGE_CODE,
            "title_zh": canonical["title_zh"], "title_en": canonical["title_en"],
            "instruction_zh": canonical["instruction_zh"],
            "instruction_en": canonical["instruction_en"],
            "type": canonical["type"], "points": canonical["points"],
            "pass_score": canonical.get("pass_score", 0), "config_json": config,
            "status": "published", "created_at": now_iso(), "updated_at": now_iso(),
        })
        task_changed = True
    else:
        # Fill in only what is missing, so a leader's own plank wording survives.
        config = as_json(task.get("config_json"), {})
        patch = {}
        if not config.get("kind"):
            config["kind"] = "bridge"
            patch["config_json"] = config
        for key in ("title_zh", "title_en", "instruction_zh", "instruction_en"):
            if not task.get(key) and canonical.get(key):
                patch[key] = canonical[key]
        if patch:
            st.update("tasks", task["id"], patch)
            task_changed = True

    # Re-read the row: the caller may have written the new layout already.
    fresh = st.get("badges", badge["id"]) or {}
    old = as_json(fresh.get("guide_json"), {})
    quest = old.setdefault("quest", {})
    areas = quest.get("areas") or []
    if len(areas) == 5:
        current = areas[1].get("game") or {}
        if current.get("task_code") != BRIDGE_CODE or not current.get("ready"):
            areas[1]["game"] = copy.deepcopy(area.get("game") or {})
            areas[1]["game"]["task_code"] = BRIDGE_CODE
            areas[1]["game"]["ready"] = True
            areas[1]["game"]["kind"] = "bridge"
            areas[1]["game"]["n"] = 2
            if area.get("hint_zh"):
                areas[1]["hint_zh"] = area["hint_zh"]
            if area.get("hint_en"):
                areas[1]["hint_en"] = area["hint_en"]
            areas[1]["items"] = [n for n in areas[1].get("items", []) if n != 5]
            st.update("badges", badge["id"], {"guide_json": old})
            guide_changed = True
    return guide_changed, task_changed


# ── game 3: the drill ground in area 3 ────────────────────────────────────
# 步操訓練場 (M06) is bound to the third area. Existing installs know item 6
# as a sign-off task (宣誓禮儀與中式隊列); the migration brings that task up
# to the game's shape, replacing only text that is still the shipped default.
DRILL_CODE = "M06"

LEGACY_M06_SIGNOFF = {
    "title_zh": "第 6 項：宣誓禮儀與中式隊列",
    "title_en": "Item 6 — investiture customs and drill",
    "instruction_zh": "認識宣誓時應有之童軍禮儀，以及中式隊列之基本動作。考核動作：salute；alert／stand-at-ease；right turn／left turn／about turn；pace forward／backward／left／right march；dressing right dress；mark time；by the front quick march。",
    "instruction_en": "Know the Scout customs for the investiture ceremony and the basic movements of Chinese-style drill. Show: salute; alert / stand-at-ease; right turn / left turn / about turn; pace forward / backward / left / right march; dressing right dress; mark time; by the front quick march.",
}


def ensure_drill(st: Store, badge: dict, blueprint: dict) -> tuple[bool, bool]:
    """Returns (guide_changed, task_changed). Never touches leader edits."""
    guide_changed = task_changed = False

    canonical = next((t for t in SEED_BADGES[0]["tasks"] if t["code"] == DRILL_CODE), None)
    if canonical is None:
        return False, False
    area = (blueprint["areas"][2] if len(blueprint["areas"]) > 2 else {})

    task = next((t for t in st.list("tasks")
                 if t.get("badge_id") == badge["id"] and t.get("code") == DRILL_CODE), None)
    if task is None:
        config = dict(canonical.get("config_json", {}))
        task = st.insert("tasks", {
            "badge_id": badge["id"], "order_index": 6, "code": DRILL_CODE,
            "title_zh": canonical["title_zh"], "title_en": canonical["title_en"],
            "instruction_zh": canonical["instruction_zh"],
            "instruction_en": canonical["instruction_en"],
            "type": canonical["type"], "points": canonical["points"],
            "pass_score": canonical.get("pass_score", 0), "config_json": config,
            "status": "published", "created_at": now_iso(), "updated_at": now_iso(),
        })
        task_changed = True
    else:
        # The item used to be a sign-off task: raise it to the game's shape.
        # Type and kind are structural; titles and instructions are replaced
        # only when they still carry the shipped sign-off wording.
        config = as_json(task.get("config_json"), {})
        patch = {}
        if str(task.get("type") or "") != canonical["type"]:
            patch["type"] = canonical["type"]
            patch["pass_score"] = canonical.get("pass_score", 0)
        if not config.get("kind"):
            config["kind"] = "drill"
            patch["config_json"] = config
        for key in ("title_zh", "title_en", "instruction_zh", "instruction_en"):
            if task.get(key) == LEGACY_M06_SIGNOFF.get(key) and canonical.get(key):
                patch[key] = canonical[key]
        if patch:
            st.update("tasks", task["id"], patch)
            task_changed = True

    # Re-read the row: the caller may have written the new layout already.
    fresh = st.get("badges", badge["id"]) or {}
    old = as_json(fresh.get("guide_json"), {})
    quest = old.setdefault("quest", {})
    areas = quest.get("areas") or []
    if len(areas) == 5:
        current = areas[2].get("game") or {}
        if current.get("ready") and current.get("task_code") and current.get("task_code") != DRILL_CODE:
            return guide_changed, task_changed       # 領袖自己換了遊戲 → 不碰
        if current.get("task_code") != DRILL_CODE or not current.get("ready"):
            areas[2]["game"] = copy.deepcopy(area.get("game") or {})
            areas[2]["game"]["task_code"] = DRILL_CODE
            areas[2]["game"]["ready"] = True
            areas[2]["game"]["kind"] = "drill"
            areas[2]["game"]["n"] = 3
            if area.get("hint_zh"):
                areas[2]["hint_zh"] = area["hint_zh"]
            if area.get("hint_en"):
                areas[2]["hint_en"] = area["hint_en"]
            areas[2]["items"] = [n for n in areas[2].get("items", []) if n != 6]
            st.update("badges", badge["id"], {"guide_json": old})
            guide_changed = True
    return guide_changed, task_changed


def main() -> None:
    st = Store.from_env()
    badge = next((b for b in st.list("badges") if b.get("code") == "SC-01"), None)
    if badge is None:
        raise SystemExit("SC-01 not found; no changes made")
    old = as_json(badge.get("guide_json"), {})
    if not old.get("items") or len(old.get("items")) < 4:
        raise SystemExit("SC-01 has no 11-item guide; no changes made")

    source = member_badge_guide()
    task = next((t for t in st.list("tasks")
                 if t.get("badge_id") == badge["id"] and t.get("code") == "M04"), None)
    if not task:
        raise SystemExit("M04 not found under SC-01; no changes made")
    canonical = next(t for t in SEED_BADGES[0]["tasks"] if t["code"] == "M04")
    old_quest = old.get("quest") or {}
    if (old_quest.get("award_rule") == "five_games"
            and (old_quest.get("areas") or [{}])[0].get("game", {}).get("task_code") == "M04"):
        revised = copy.deepcopy(old)
        story_changed = refresh_story_copy(revised, source)
        cave_changed = refresh_cave_copy(revised, source)
        task_patch = cave_task_patch(task, canonical)
        if story_changed or cave_changed:
            st.update("badges", badge["id"], {"guide_json": revised})
        if task_patch:
            st.update("tasks", task["id"], task_patch)
        bridge_guide, bridge_task = ensure_bridge(st, badge, source["quest"])
        drill_guide, drill_task = ensure_drill(st, badge, source["quest"])
        if story_changed:
            print("SC-01 journey copy updated for the one-button start; scout records preserved")
        elif cave_changed or task_patch:
            print("SC-01 cave completion rule updated; scout records preserved")
        if bridge_guide or bridge_task:
            print("SC-01 gained game 2, the bridge in area 2; scout records preserved")
        if drill_guide or drill_task:
            print("SC-01 gained game 3, the drill ground in area 3; scout records preserved")
        if not (story_changed or cave_changed or task_patch or bridge_guide or bridge_task):
            print("SC-01 already uses the completion-based cave; nothing changed")
        return

    revised = copy.deepcopy(old)
    quest = revised.setdefault("quest", {})
    blueprint = source["quest"]
    for key in ("award_rule", "game_rule_zh", "game_rule_en", "first_stage_note_zh",
                "first_stage_note_en", "credited_body_zh", "credited_body_en",
                "trail_lead_zh", "trail_lead_en", "trail_last_note_zh", "trail_last_note_en"):
        quest[key] = blueprint[key]
    refresh_story_copy(revised, source)
    quest["beats_zh"][2]["text"] = blueprint["beats_zh"][2]["text"]
    quest["beats_en"][2]["text"] = blueprint["beats_en"][2]["text"]
    areas = quest.get("areas") or []
    if len(areas) != 5:
        raise SystemExit("SC-01's area layout is not five locations; no changes made")
    # Keep custom area names and art. Move only the game and the area's old
    # item-4 double entry; items 1 & 2 stay as supplementary guide references.
    areas[0]["items"] = []
    areas[0]["game"] = copy.deepcopy(blueprint["areas"][0]["game"])
    areas[0]["hint_zh"] = blueprint["areas"][0]["hint_zh"]
    areas[0]["hint_en"] = blueprint["areas"][0]["hint_en"]
    areas[1]["items"] = [n for n in areas[1].get("items", []) if n != 4]
    for index, area in enumerate(areas[1:], start=1):
        game = area.get("game") or {}
        if index == 1 and game.get("task_code") == "M04":
            game = {}
        if not game.get("ready"):
            game = copy.deepcopy(blueprint["areas"][index]["game"])
        else:
            game["n"] = index + 1
        area["game"] = game
    areas[1]["hint_zh"] = blueprint["areas"][1]["hint_zh"]
    areas[1]["hint_en"] = blueprint["areas"][1]["hint_en"]

    old_item4 = revised["items"][3]
    new_item4 = source["items"][3]
    for key in ("req_zh", "req_en", "method_note_zh", "method_note_en",
                "stage_zh", "stage_en", "stage_icon", "stage_hint_zh", "stage_hint_en"):
        old_item4[key] = copy.deepcopy(new_item4[key])
    old_item4["links"] = [link for link in old_item4.get("links", [])
                          if "forms.gle/M4vtu6GwsMd5do1J8" not in link.get("url", "")]

    config = as_json(task.get("config_json"), {})
    config["require_all"] = True
    config["links"] = [link for link in config.get("links", [])
                       if "forms.gle/M4vtu6GwsMd5do1J8" not in link.get("url", "")]
    # Keeping the existing 50 questions preserves any edits the leader made.
    if len(config.get("questions") or []) != 50:
        raise SystemExit("M04 has no 50-question bank; no changes made")

    st.update("badges", badge["id"], {"guide_json": revised,
                                      "desc_zh": SEED_BADGES[0]["desc_zh"],
                                      "desc_en": SEED_BADGES[0]["desc_en"]})
    st.update("tasks", task["id"], {"title_zh": canonical["title_zh"],
                                    "title_en": canonical["title_en"],
                                    "instruction_zh": canonical["instruction_zh"],
                                    "instruction_en": canonical["instruction_en"],
                                    "pass_score": 0, "config_json": config})
    item1 = next((t for t in st.list("tasks")
                  if t.get("badge_id") == badge["id"] and t.get("code") == "M01"), None)
    if item1:
        cfg = as_json(item1.get("config_json"), {})
        cfg.pop("start_credited", None)
        st.update("tasks", item1["id"], {"config_json": cfg})
    bridge_guide, bridge_task = ensure_bridge(st, badge, blueprint)
    drill_guide, drill_task = ensure_drill(st, badge, blueprint)
    print("SC-01 updated: cave = game 1 in area 1; old paper removed; "
          "game 2 (the bridge) sits in area 2; game 3 (the drill ground) sits in "
          "area 3; games 4–5 still await the leader. No scout records were deleted.")


if __name__ == "__main__":
    main()
