"""
Data model — identical to the Node build, so an existing Google Sheet or a
Node-created ./data folder works unchanged (and vice versa).

One collection = one tab in the Sheet. Complex values (arrays/objects) are
stored as JSON text inside a single cell, so a leader can still read — and
carefully edit — the Sheet by eye.
"""
from __future__ import annotations

COLLECTIONS: dict[str, dict] = {
    "users": {
        "label": "Accounts",
        "fields": [
            "id", "role", "username", "password_hash", "password_salt",
            "display_name_zh", "display_name_en", "email", "scout_no", "section",
            "patrol", "unit", "avatar", "status", "must_change_password",
            "show_on_leaderboard", "created_at", "created_by",
        ],
    },
    "password_reset_requests": {
        "label": "Password resets",
        "fields": ["id", "user_id", "status", "requested_at", "resolved_at", "resolved_by", "note"],
    },
    "password_resets": {
        # one row per emailed reset link; `token_hash` only — the link is never stored
        "label": "Reset links",
        "fields": ["id", "user_id", "token_hash", "email", "created_at", "expires_at",
                   "used_at", "requested_by", "sent_to"],
    },
    "stats": {
        "label": "Stats",
        "fields": [
            "user_id", "points_balance", "tasks_done", "badges_done",
            "streak_current", "streak_best", "last_active_date", "updated_at",
        ],
    },
    "badges": {
        "label": "Badges",
        "fields": [
            "id", "section", "order_index", "code", "title_zh", "title_en",
            "subtitle_zh", "subtitle_en", "desc_zh", "desc_en", "emoji", "image_url",
            "color", "points_reward", "prerequisite_badge_ids",
            "guide_json", "status", "created_at", "updated_at",
        ],
    },
    "tasks": {
        "label": "Tasks",
        "fields": [
            "id", "badge_id", "order_index", "code", "title_zh", "title_en",
            "instruction_zh", "instruction_en", "type", "points", "pass_score",
            "config_json", "status", "created_at", "updated_at",
        ],
    },
    "progress_records": {
        "label": "Progress",
        "fields": [
            "id", "user_id", "badge_id", "task_id", "attempt_no", "status", "score",
            "answers_json", "checklist_json", "evidence_url", "reflection_text",
            "leader_comment", "points_awarded", "submitted_at", "decided_at", "decided_by",
        ],
    },
    "badge_awards": {
        "label": "BadgeAwards",
        "fields": ["id", "user_id", "badge_id", "awarded_at", "awarded_by", "note"],
    },
    "points_ledger": {
        "label": "Ledger",
        "fields": [
            "id", "user_id", "entry_type", "points_delta", "reason_zh", "reason_en",
            "ref_type", "ref_id", "created_at", "created_by",
        ],
    },
    "rewards": {
        "label": "Rewards",
        "fields": [
            "id", "title_zh", "title_en", "desc_zh", "desc_en", "emoji",
            "points_cost", "stock", "category", "active",
        ],
    },
    "redemptions": {
        "label": "Redemptions",
        "fields": [
            "id", "user_id", "reward_id", "points_cost", "status",
            "requested_at", "decided_by", "decided_at", "note",
        ],
    },
    "suggestions": {
        "label": "Suggestions",
        "fields": [
            "id", "emoji", "category", "title_zh", "title_en", "desc_zh", "desc_en",
            "link_url", "link_label_zh", "link_label_en", "order_index", "active", "created_at",
        ],
    },
    "announcements": {
        "label": "Announcements",
        "fields": [
            "id", "title_zh", "title_en", "body_zh", "body_en",
            "audience", "pinned", "created_at", "expires_at",
        ],
    },
    "audit_log": {
        "label": "AuditLog",
        "fields": ["id", "actor_id", "actor_role", "action", "entity", "entity_id", "detail_json", "created_at"],
    },
    "sessions": {
        "label": "Sessions",
        "fields": ["token", "user_id", "created_at", "expires_at", "user_agent"],
    },
    "settings": {
        "label": "Settings",
        "fields": ["key", "value_json", "updated_at"],
    },
}

COLLECTION_ORDER = list(COLLECTIONS.keys())

#: Fields stored as JSON text in a single cell (arrays / objects).
JSON_FIELDS = {
    "guide_json",          # 會員章的完成指南（一整份結構）
    "prerequisite_badge_ids", "config_json", "answers_json", "checklist_json",
    "detail_json", "value_json",
}
#: Fields stored as numbers.
NUMBER_FIELDS = {
    "order_index", "points_reward", "points", "pass_score", "attempt_no", "score",
    "points_awarded", "points_delta", "points_cost", "stock", "points_balance",
    "tasks_done", "badges_done", "streak_current", "streak_best",
}
#: Fields stored as booleans.
BOOL_FIELDS = {"must_change_password", "show_on_leaderboard", "active", "pinned"}


def key_field(collection: str) -> str:
    if collection == "stats":
        return "user_id"
    if collection == "settings":
        return "key"
    if collection == "sessions":
        return "token"
    return "id"


DEFAULT_SETTINGS: dict = {
    "unit_name_zh": "港島第八十二旅童軍團",
    "unit_name_en": "Sample Scout Group",
    "section": "scout",
    # Optional extras. Each one is off until the unit is ready for it: flip it
    # in 領袖後台 → 設定 → 功能開關 and the page + nav link come back by
    # themselves (one item at a time, nothing to rebuild).
    "feature_flags": {
        "leaderboard": False,     # 龍虎榜 — hidden for now
        "redeem": False,          # 獎品 / reward shop — hidden for now
        "evidence_upload": True,
        "streaks": True,
        "announcements": True,
    },
    "leaderboard_metrics": ["badges", "tasks"],
    "leaderboard_scopes": ["unit", "patrol", "all"],
    "motto_zh": "日行一善",
    "motto_en": "Do a good turn every day",
    "patrols": ["Tiger", "Otter", "Seagull"],   # 小隊, in sign-in order
    "scout_self_reset": False,                  # «forgot password» clears it instantly
    "ui_sound": True,                           # game sounds on by default
    # ── the mailbox that sends password-reset links (see scout/mailer.py) ──
    "smtp_host": "",                            # smtp.gmail.com for a unit Gmail
    "smtp_port": 587,
    "smtp_tls": "tls",                          # tls (587) | ssl (465) | none
    "smtp_user": "",
    "smtp_password": "",                        # a Gmail *app password*, never the login one
    "smtp_from": "",
    "public_base_url": "",                      # leave blank: use the address in the browser
    "reset_link_minutes": 60,                   # how long a reset link stays good
}

PATROL_LABELS = {
    "tiger": {"zh": "老虎", "en": "Tiger"},
    "otter": {"zh": "水獺", "en": "Otter"},
    "seagull": {"zh": "海鷗", "en": "Seagull"},
}


def patrol_label(value: str) -> dict:
    hit = PATROL_LABELS.get(str(value or "").strip().lower())
    return dict(hit) if hit else {"zh": value, "en": value}


# the leaders' door uses a short, easy-to-share code: 領袖登入 → 0082
DEMO_PASSWORDS = {"leader": "0082", "scout": "scout1234"}

DEMO_LOGIN_MAP = {
    "demo1": {"username": "leader1", "label_zh": "領袖示範", "label_en": "Leader demo"},
    "demo2": {"username": "scout03", "label_zh": "童軍示範", "label_en": "Scout demo"},
    # The password-free first entry: a scout who has never set a password.
    "demo3": {"username": "scout07", "label_zh": "第一次登入示範", "label_en": "First-time demo",
              "first_time": True},
}

TASK_TYPES = {
    "quiz": {
        "auto": True, "needs_approval": False, "icon": "🧠",
        "label_zh": "小測驗", "label_en": "Quiz",
        "note_zh": "即時自動評分，達到合格分數即完成",
        "note_en": "Auto-graded — reaching the pass mark completes the task",
    },
    "checklist": {
        "auto": True, "needs_approval": False, "icon": "✅",
        "label_zh": "清單任務", "label_en": "Checklist",
        "note_zh": "逐項打勾，全部完成即完成任務",
        "note_en": "Tick every item to complete the task",
    },
    "evidence": {
        "auto": False, "needs_approval": True, "icon": "📸",
        "label_zh": "證明上載", "label_en": "Photo evidence",
        "note_zh": "上載相片／連結，交由領袖核實",
        "note_en": "Upload a photo or a link for a leader to verify",
    },
    "reflection": {
        "auto": False, "needs_approval": True, "icon": "✍️",
        "label_zh": "反思短文", "label_en": "Reflection",
        "note_zh": "用文字分享所學，由領袖評閱",
        "note_en": "Write what you learned; reviewed by a leader",
    },
    "signoff": {
        "auto": False, "needs_approval": True, "icon": "🤝",
        "label_zh": "領袖簽核", "label_en": "Leader sign-off",
        "note_zh": "集會時由領袖即場考核並簽核",
        "note_en": "Assessed in person at a meeting and signed off",
    },
}

# ── placeholder content (structure demo — leaders replace it in the console) ──

SEED_BADGES = [
    {
        "code": "SC-01",
        "title_zh": "會員章", "title_en": "Membership Badge",
        "subtitle_zh": "進度性獎章 1 / 5", "subtitle_en": "Progressive award 1 of 5",
        "desc_zh": "荒島上的五個區域，各有一個遊戲。完成全部五個遊戲，就能考獲會員章。",
        "desc_en": "There is one game in each of the island's five areas. Clear all five to earn the Membership Badge.",
        "emoji": "🌱", "image_url": "/img/badges/membership.webp",
        "color": "#3f9142", "points_reward": 50,
        # Keep the 11 syllabus items as reference/optional practice. The award is
        # earned by clearing the five *games* defined in guide.json, not by
        # doing these 11 tasks. Item 4 is completed by game 1 (the cave) only.
        "tasks": [
            {
                "code": "M01",
                "title_zh": "第 1 項：與小隊長商議加入安排",
                "title_en": "Item 1 — talk to your patrol leader about joining",
                "instruction_zh": "與你的小隊長商議有關加入童軍團之安排。領袖確認你已加入童軍團。",
                "instruction_en": "Discuss the arrangements for joining the Scout Troop with your patrol leader. A leader confirms that you have joined.",
                # Supplementary syllabus reference, not the first location's game.
                "type": "signoff", "points": 10,
                "config_json": {}, 
            },
            {
                "code": "M02",
                "title_zh": "第 2 項：加入小隊，認識隊中成員",
                "title_en": "Item 2 — join a patrol and know its members",
                "instruction_zh": "加入一小隊，並從小隊活動中認識隊中其他成員。考核時說出：小隊成員、小隊職位、小隊成員電話號碼（隊長／聯絡）。",
                "instruction_en": "Join a patrol and get to know the other members through patrol activities. Show your leader that you know: the members, the patrol jobs, and the patrol phone numbers (leader / contact).",
                "type": "signoff", "points": 10, "config_json": {},
            },
            {
                "code": "M03",
                "title_zh": "第 3 項：參加六次團集會／活動",
                "title_en": "Item 3 — attend six meetings / activities",
                "instruction_zh": "最少參加六次團集會／活動，其中一次在戶外舉行。每次出席後打勾，領袖會核對出席紀錄。",
                "instruction_en": "Take part in at least six troop meetings or activities, one of them outdoors. Tick each one after you attend — your leader checks the attendance record.",
                "type": "checklist", "points": 20,
                "config_json": {"items": [
                    {"zh": "第一次室內集會／活動", "en": "First indoor meeting / activity"},
                    {"zh": "第二次室內集會／活動", "en": "Second indoor meeting / activity"},
                    {"zh": "第三次室內集會／活動", "en": "Third indoor meeting / activity"},
                    {"zh": "第四次室內集會／活動", "en": "Fourth indoor meeting / activity"},
                    {"zh": "第五次室內集會／活動", "en": "Fifth indoor meeting / activity"},
                    {"zh": "一次戶外集會／活動", "en": "One outdoor meeting / activity"},
                ]},
            },
            {
                "code": "M04",
                "title_zh": "第 4 項：童軍歷史山洞（遊戲 1）",
                "title_en": "Item 4 — The Cave of Scouting History (game 1)",
                "instruction_zh": "第一個區域只有童軍歷史山洞：先閱讀四段壁畫，再在石室完成全部 50 題。走到洞口便自動通關並完成第 4 項；每題 2 分，成績只供回顧，不設合格分數，亦無須另做試卷。",
                "instruction_en": "The first area's only game is the cave: read four wall paintings, then finish all 50 chamber questions. Reaching the exit automatically clears game 1 and item 4, whatever your score. Each question is worth 2 marks for review; there is no separate paper.",
                "type": "quiz", "points": 30, "pass_score": 0,
                # Reuse the server-side bank to mark the cave's first attempts.
                # It is not a second quiz page: /tasks/<id> redirects to the game.
                "config_json": {"bank": "member-badge/item4", "require_all": True,
                                "links": [
                                    {"label_zh": "溫習資源", "label_en": "Study resources",
                                     "url": "https://drive.google.com/drive/folders/18XAKwwF-ECWkcO6NLd1L1Hw8lomZBCEb?usp=sharing"},
                                ]},
            },
            {
                "code": "M05",
                "title_zh": "第 5 項：迷霧渡口（遊戲 2）",
                "title_en": "Item 5 — the misty crossing (game 2)",
                "instruction_zh": "明瞭及接納童軍誓詞、規律和銘言。第二個區域只有這一個遊戲：先讀教學牌，再把木板按正確次序鋪成橋。三關全部鋪好即完成第 5 項，無須另做考核；宣誓時領袖仍會聽你親口講出誓詞、規律和銘言。",
                "instruction_en": "Understand and accept the Scout Promise, Law and Motto. The second area's only game: read each teaching card, then lay the planks across the river in the right order. Laying all three stages completes item 5 — there is no separate paper. Your leader will still hear you say them aloud when you are invested.",
                "type": "quiz", "points": 15, "pass_score": 0,
                "config_json": {"kind": "bridge", "require_all": True,
                                "links": [
                                    {"label_zh": "童軍誓詞與規律（香港童軍總會）",
                                     "label_en": "Scout Promise and Law (SAHK)",
                                     "url": "https://www.scout.org.hk/tc/scouting/promise-law.html"},
                                ]},
            },
            {
                "code": "M06",
                "title_zh": "第 6 項：宣誓禮儀與中式隊列",
                "title_en": "Item 6 — investiture customs and drill",
                "instruction_zh": "認識宣誓時應有之童軍禮儀，以及中式隊列之基本動作。考核動作：salute；alert／stand-at-ease；right turn／left turn／about turn；pace forward／backward／left／right march；dressing right dress；mark time；by the front quick march。",
                "instruction_en": "Know the Scout customs for the investiture ceremony and the basic movements of Chinese-style drill. Show: salute; alert / stand-at-ease; right turn / left turn / about turn; pace forward / backward / left / right march; dressing right dress; mark time; by the front quick march.",
                "type": "signoff", "points": 15,
                "config_json": {"links": [
                    {"label_zh": "步操示範資源", "label_en": "Drill reference",
                     "url": "https://drive.google.com/drive/folders/1o7CruXDWSruWb10vEhxfPO_yNiWi93-d?usp=sharing"},
                ]},
            },
            {
                "code": "M07",
                "title_zh": "第 7 項：國旗與國徽",
                "title_en": "Item 7 — national flag and emblem",
                "instruction_zh": "能辨認中華人民共和國國旗和國徽，並能說明其含意。完成「第 7 至 10 項試卷」（24 分／30 分合格）後打勾。",
                "instruction_en": "Recognise the national flag and emblem of the PRC and explain their meaning. Tick this when you have completed the Items 7–10 paper (pass mark 24/30).",
                "type": "checklist", "points": 10,
                "config_json": {
                    "items": [{"zh": "我已完成第 7 至 10 項試卷（24 分／30 分或以上），並能說出國旗、國徽的含意",
                               "en": "I passed the Items 7–10 paper (24/30 or above) and can explain the national flag and emblem"}],
                    "links": [
                        {"label_zh": "第 7 至 10 項試卷（Google Form）", "label_en": "Items 7–10 paper (Google Form)",
                         "url": "https://forms.gle/NmdM72WapUpbajFHA"},
                        {"label_zh": "溫習資源", "label_en": "Study resources",
                         "url": "https://drive.google.com/drive/folders/1LtM4RykgGrrITxZRwWHeN-pWHnxKBKTY?usp=drive_link"},
                    ]},
            },
            {
                "code": "M08",
                "title_zh": "第 8 項：區旗與區徽",
                "title_en": "Item 8 — regional flag and emblem",
                "instruction_zh": "能辨認香港特別行政區區旗和區徽，並能說明其含意。由「第 7 至 10 項試卷」考核。",
                "instruction_en": "Recognise the HKSAR regional flag and emblem and explain their meaning. Covered by the Items 7–10 paper.",
                "type": "checklist", "points": 10,
                "config_json": {
                    "items": [{"zh": "我能認出區旗、區徽，並說出它們的含意",
                               "en": "I can recognise the regional flag and emblem and explain their meaning"}],
                    "links": [
                        {"label_zh": "第 7 至 10 項試卷（Google Form）", "label_en": "Items 7–10 paper (Google Form)",
                         "url": "https://forms.gle/NmdM72WapUpbajFHA"},
                    ]},
            },
            {
                "code": "M09",
                "title_zh": "第 9 項：國歌奏唱與升旗禮儀",
                "title_en": "Item 9 — etiquette for the anthem and flag-raising",
                "instruction_zh": "認識在國歌奏唱和升掛國旗、區旗時應有之禮儀，以及升國旗的基本程序。由「第 7 至 10 項試卷」考核。",
                "instruction_en": "Know the proper etiquette when the national anthem is played and the flags are raised, and the basic flag-raising procedure. Covered by the Items 7–10 paper.",
                "type": "checklist", "points": 10,
                "config_json": {"items": [
                    {"zh": "我知道國歌奏唱及升旗時應有的禮儀，以及升國旗的基本程序",
                     "en": "I know the etiquette for the anthem and flag-raising, and the basic procedure"}]},
            },
            {
                "code": "M10",
                "title_zh": "第 10 項：國歌的用意與背唱",
                "title_en": "Item 10 — purpose of the anthem, sing from memory",
                "instruction_zh": "明瞭設立國歌的用意，並能背唱之。由「第 7 至 10 項試卷」考核。",
                "instruction_en": "Understand the purpose of the national anthem and be able to sing it from memory. Covered by the Items 7–10 paper.",
                "type": "checklist", "points": 10,
                "config_json": {"items": [
                    {"zh": "我明瞭國歌的用意，並能背唱國歌",
                     "en": "I understand the purpose of the anthem and can sing it from memory"}]},
            },
            {
                "code": "M11",
                "title_zh": "第 11 項：認識兒童侵害與保護自己",
                "title_en": "Item 11 — child protection",
                "instruction_zh": "認識常見兒童侵害情況、預防方法及處理方法。領袖會講解並與大家討論，之後核實。",
                "instruction_en": "Know common situations of child abuse, how to prevent them and how to handle them. Your leader runs the session and the discussion, then signs this off.",
                "type": "signoff", "points": 10, "config_json": {},
            },
        ],
    },
    {
        "code": "SC-02",
        "title_zh": "童軍探索獎章", "title_en": "Scout Pathfinder Award",
        "subtitle_zh": "進度性獎章 2 / 5", "subtitle_en": "Progressive award 2 of 5",
        "desc_zh": "完成會員章之後開啟。任務由領袖在後台加入（現時未有內容）。",
        "desc_en": "Opens once the Membership Badge is earned. Tasks come from the leader console (empty for now).",
        "emoji": "🧭", "image_url": "/img/badges/pathfinder.webp",
        "color": "#2f6f9f", "points_reward": 100,
        "tasks": [],
    },
    {
        "code": "SC-03",
        "title_zh": "童軍標準獎章", "title_en": "Scout Standard Award",
        "subtitle_zh": "進度性獎章 3 / 5", "subtitle_en": "Progressive award 3 of 5",
        "desc_zh": "技能與戶外活動（示例內容）。需要先完成童軍探索獎章。",
        "desc_en": "Skills and outdoor activity (sample content). Requires the Pathfinder Award first.",
        "emoji": "⛺", "image_url": "/img/badges/standard.webp",
        "color": "#2f6f9f", "points_reward": 80,
        "tasks": [
            {
                "code": "T-11",
                "title_zh": "繩結小測驗（示例）", "title_en": "Knots quiz (sample)",
                "instruction_zh": "示例題目，可由領袖替換。", "instruction_en": "Sample questions, replaceable by leaders.",
                "type": "quiz", "points": 35, "pass_score": 80,
                "config_json": {
                    "questions": [{
                        "q_zh": "示例題目：平結的主要用途是？",
                        "q_en": "Sample question: what is a reef knot mainly used for?",
                        "options": [
                            {"zh": "示例選項 A", "en": "Sample option A"},
                            {"zh": "示例選項 B（正解）", "en": "Sample option B (correct)"},
                            {"zh": "示例選項 C", "en": "Sample option C"},
                        ],
                        "answer": 1,
                    }]
                },
            },
            {
                "code": "T-12",
                "title_zh": "戶外活動紀錄（示例）", "title_en": "Outdoor activity log (sample)",
                "instruction_zh": "上載活動相片或連結。", "instruction_en": "Upload a photo or a link.",
                "type": "evidence", "points": 40,
                "config_json": {"hint_zh": "可上載相片，或貼上雲端相簿連結",
                                "hint_en": "Upload a photo or paste a shared album link"},
            },
            {
                "code": "T-13",
                "title_zh": "領袖技能考核（示例）", "title_en": "Practical assessment (sample)",
                "instruction_zh": "於集會中由領袖即場考核。",
                "instruction_en": "Assessed in person by a leader at a meeting.",
                "type": "signoff", "points": 45, "config_json": {},
            },
        ],
    },
    {
        "code": "SC-04",
        "title_zh": "童軍高級獎章", "title_en": "Scout Advanced Award",
        "subtitle_zh": "進度性獎章 4 / 5", "subtitle_en": "Progressive award 4 of 5",
        "desc_zh": "服務與領導（示例內容）。需要先完成童軍標準獎章。",
        "desc_en": "Service and leadership (sample content). Requires the Standard Award first.",
        "emoji": "🏅", "image_url": "/img/badges/advanced.webp",
        "color": "#b07d2b", "points_reward": 120,
        "tasks": [
            {
                "code": "T-21",
                "title_zh": "服務紀錄（示例）", "title_en": "Service log (sample)",
                "instruction_zh": "記錄一次服務經歷。", "instruction_en": "Record one service experience.",
                "type": "evidence", "points": 50, "config_json": {},
            },
            {
                "code": "T-22",
                "title_zh": "反思短文（示例）", "title_en": "Reflection (sample)",
                "instruction_zh": "分享你對服務的體會。", "instruction_en": "Share what the service meant to you.",
                "type": "reflection", "points": 50, "config_json": {"min_chars": 50, "max_chars": 800},
            },
            {
                "code": "T-23",
                "title_zh": "小隊領袖簽核（示例）", "title_en": "Patrol leader sign-off (sample)",
                "instruction_zh": "由領袖確認領導表現。", "instruction_en": "Leader confirms leadership performance.",
                "type": "signoff", "points": 60, "config_json": {},
            },
        ],
    },
    {
        "code": "SC-05",
        "title_zh": "總領袖獎章", "title_en": "Chief Scout's Award",
        "subtitle_zh": "進度性獎章 5 / 5", "subtitle_en": "Progressive award 5 of 5",
        "desc_zh": "童軍支部的最高獎章。任務由領袖在後台加入（現時未有內容）。",
        "desc_en": "The highest award in the Scout section. Tasks come from the leader console (empty for now).",
        "emoji": "👑", "image_url": "/img/badges/chief-scout.webp",
        "color": "#7d4b8f", "points_reward": 250,
        "tasks": [],
    },
]

SEED_SUGGESTIONS = [
    {
        "emoji": "🪢", "category": "skill",
        "title_zh": "練習一個繩結", "title_en": "Practise one knot",
        "desc_zh": "拿出繩子，試試平結或稱人結。每週練一種，集會時可以教其他隊員。",
        "desc_en": "Grab a rope and try a reef knot or a bowline. One a week, then teach your patrol.",
    },
    {
        "emoji": "📖", "category": "learn",
        "title_zh": "認識童軍誓詞的意思", "title_en": "Learn what the Promise means",
        "desc_zh": "把童軍誓詞讀一遍，想想每一句在你日常生活裡代表什麼。",
        "desc_en": "Read the Scout Promise and think about what each line means in your daily life.",
    },
    {
        "emoji": "🏕️", "category": "outdoor",
        "title_zh": "學習露營基本技巧", "title_en": "Learn basic campcraft",
        "desc_zh": "先在家練習搭帳篷、收拾裝備，下次露營就會得心應手。",
        "desc_en": "Practise pitching a tent and packing your kit at home so camp day is easy.",
    },
    {
        "emoji": "🧭", "category": "outdoor",
        "title_zh": "學用地圖與指南針", "title_en": "Read a map and compass",
        "desc_zh": "與家人到附近行山，練習定向和辨認地標。",
        "desc_en": "Take a short hike with your family and practise orienteering and landmarks.",
    },
    {
        "emoji": "🤝", "category": "service",
        "title_zh": "日行一善", "title_en": "Do a good turn",
        "desc_zh": "每天做一件幫助別人的小事，寫在筆記簿，集會時分享。",
        "desc_en": "Do one small helpful thing each day, note it down, and share at the meeting.",
    },
    {
        "emoji": "🎨", "category": "creative",
        "title_zh": "畫下你的小隊徽章", "title_en": "Design your patrol badge",
        "desc_zh": "用鉛筆或顏色筆設計一個代表你小隊的標誌。",
        "desc_en": "Draw a symbol that represents your patrol — pencils, colours, anything goes.",
    },
    {
        "emoji": "🏃", "category": "fun",
        "title_zh": "保持體能", "title_en": "Keep fit",
        "desc_zh": "每週運動三次，可以是跑步、跳繩或游泳。",
        "desc_en": "Move three times a week — running, skipping or swimming all count.",
    },
]

SEED_REWARDS = [
    {"title_zh": "營繩（示例）", "title_en": "Guy rope (sample)", "emoji": "🪢",
     "points_cost": 200, "stock": -1, "category": "gear"},
    {"title_zh": "童軍頸巾扣（示例）", "title_en": "Woggle (sample)", "emoji": "🌀",
     "points_cost": 350, "stock": 10, "category": "gear"},
    {"title_zh": "旅團紀念章（示例）", "title_en": "Group badge (sample)", "emoji": "🎖️",
     "points_cost": 500, "stock": 20, "category": "gear"},
    {"title_zh": "免費參加一次特別活動（示例）", "title_en": "Free entry to a special activity (sample)",
     "emoji": "🎟️", "points_cost": 800, "stock": 5, "category": "experience"},
]
