# 架構 (Python 版) — Flask + Jinja

## 沒有 cookie 也要登入得到 (the preview iframe)

Arena 的預覽把頁面放在第三方 iframe，瀏覽器會拒絕儲存 cookie，於是
`POST /login/… → 302 /home → 302 /login`（登入後立即被踢回登入頁）。平台的處理：

```
before_request   token = ?sid=… or X-Session-Token or scout_sid cookie → g.sid → g.user
url_for (Jinja)  自動把 ?sid=… 加在所有內部連結與表單 action 上
after_request    相對轉向的 Location 也補上 ?sid=…；若 token 來自網址，順便補回 cookie
_set_session_cookie  登入後的 302 目標、以及 JSON 回應的 redirect 欄位都帶 ?sid=…
閃退訊息         flash 需要 cookie，所以在無 cookie 環境改用 ?ok= / ?err= / ?done= / ?redo=
                 由頁面自己顯示（例如 /home?ok=password 的「🎉 密碼已設定」）
```

效果：cookie 正常時完全照舊（token 只在第一次轉向出現一次）；cookie 被封鎖時整個平台
（示範登入、開發者選名、任務提交、上載、領袖審批）仍然運作，`tests/test_auth.py` 有五條
「假裝瀏覽器不收 cookie」的測試守住它。

## 第一次進入的流程 (first entry: password + email are required)

```
GET /login/scout/<patrol>            小隊選名頁（未設定密碼的名字有「第一次登入 · 免密碼」標記）
GET /login/scout/<patrol>/<user_id>  未設密碼 → sign_in() → 302 /welcome（不問密碼）
                                     有密碼 → 密碼頁；must_change_password 者輸入後同樣 302 /welcome
GET  /welcome                        必填表單：新密碼 + 確認 + 聯絡電郵（全部 required）
POST /welcome                        set_password(store, user, password, email)
                                     → 302 /home?ok=password｜錯誤 → ?err=short|mismatch|missing_email|email
@scout_required                      未完成設定 → HTML 302 /welcome；fetch/API 403 setup_required
```

設計上的三個要點：

1. **入場免費，設定必做**。`needs_first_time()` 代表「未有個人密碼或仍是領袖給的臨時密碼」，
   所以按名字（或輸入臨時密碼）都只會走到 `/welcome`。`scout_required` 對**每一個**童軍
   GET/POST 檢查它：直接輸入 `/home`、獎章頁或山洞網址都會被導回表單，介面呼叫回
   `403 setup_required`。`home_for()` 與示範捷徑同樣遵守，不能繞過。
2. **重設有三條路**。
   - **電郵連結（預設）**：密碼頁的「忘記密碼？」（`/forgot/scout/<patrol>/<id>`）只有一個
     按鈕 —— 平台寄一條一次性連結到**帳號上已有的電郵**，由他自己設定新密碼。童軍無須輸入
     電郵，所以別人猜到帳號也無法代他重設。`password_resets` 只存 token 的 SHA-256 雜湊，
     連結一次性（用過即失效，其餘同帳號連結同時作廢）、預設 60 分鐘有效，並且每次重設都會
     刪除該帳號所有 `sessions`。寄出頻率：一分鐘一封、一小時五封；寄信失敗即作廢該 token。
     設定步驟見 `docs/03-email-setup.md`。
   - **即時重設（未設定信箱時的後備）**：頁面要求輸入自己第一次登入時填的電郵，對得上就
     即時設定新密碼（`set_password` + `self_reset_password` 稽核）。離線示範與未設定 SMTP 的
     部署行這條路。
   - **領袖代辦**：領袖在帳戶版面按 🔑，清空 `password_hash` 並把 `must_change_password`
     設為 true；那位童軍下次按名字就直接進入必填表單。帳號未有電郵（領袖建立、未完成設定）
     時，自助頁只會顯示通知領袖的按鈕，沿用 `/forgot` 與 `password_reset_requests`；領袖也
     可以在帳戶頁按 ✉️ 直接把連結寄給他。
3. **Flash 與登入 cookie 不可同名**。平台自己的登入憑證用 `scout_sid`（`sessions` 分頁的
   token）。Flask 的 flash 訊息也預設叫 `scout_sid`，於是任何一次 `flash()`（例如提交任務後）
   都會覆寫登入 cookie，把童軍靜靜地登出。現在 flash 的 session cookie 改名為
   `scout_flash`（`app.py` 的 `SESSION_COOKIE_NAME`），`tests/test_auth.py` 有一條回歸測試
   專門守住這件事。

## 為甚麼是伺服器渲染

Node 版是一個 SPA：一個 HTML 檔 + JavaScript 在前端畫出所有畫面。這一版把同樣的
功能改成**每一頁有自己的網址**：

* 童軍可以加書籤、按上一頁、把 `/badges` 的連結貼給隊友 — 對小朋友重要。
* 無 JavaScript 也完全可用（學校電腦、舊平板、被封鎖的瀏覽器）；JS 只是加分項。
* 領袖可以「右鍵 → 開新分頁」同時開審批與內容。
* 搜尋引擎與列印（領袖想印進度表）自然可用。

遊戲層（圓環、路線圖、彩紙、音效）全部保留，改為「裝飾已經存在的頁面」。

## 請求的生命週期

```
request
  └─ before_request: load_user()        讀 scout_sid → sessions 分頁 → users 分頁
  └─ context_processor: inject_globals() lang · L() · settings · user(public) · TASK_TYPES
  └─ blueprint 路由
        auth_routes    登入流程（頁面）+ 表單 POST
        scout_routes   童軍頁面 + /api/*（遊戲層用）
        leader_routes  領袖後台 + /api/leader/*
  └─ 守衛: @scout_required / @leader_required / @login_required
        HTML 請求 → 302 去 /login?next=…
        fetch 請求 (X-Requested-With / Accept: json) → 401/403 JSON
  └─ Jinja 模板 (base.html → 各頁) → HTML
```

同一個 POST 端點服務兩種客戶端：瀏覽器表單（302 + flash）與遊戲層 fetch
（JSON + 事件），因此「無 JS」與「有 JS」走同一套規則，只有回應格式不同。

## 模組

| 模組 | 責任 | 不負責 |
|---|---|---|
| `scout/schema.py` | 資料表定義、欄位型別、預設設定、種子內容、任務類型 | 任何邏輯 |
| `scout/util.py` | 密碼雜湊、日期時間（Asia/Hong_Kong）、ID | 資料存取 |
| `scout/drivers/*` | 一個集合一個 list/get/insert/update/remove（+ 上載） | 規則 |
| `scout/store.py` | 驅動之上的共同層：設定合併、每位童軍的 stats 快取、上載、首次設定、示範資料、帳本重建 | 進度規則 |
| `scout/engine.py` | **所有規則**：評分、獎章自動頒發、積分帳本、連續活躍、龍虎榜、進度、建議 | HTTP |
| `scout/auth.py` | 工作階段、守衛、登入輔助 | 頁面渲染 |
| `scout/routes/*` | HTTP 進出、表單解析、審計 | 規則（一律呼叫 engine） |
| `scout/content.py` | 讀 `content/`：11 項完成指南、第 4 項題庫（答案鍵在伺服器側合併）、山洞歷險劇本 `cave.json` ＋場景圖清單 | 進度規則 |

**內容與程式分開**：獎章的「完成指南」放在 `content/member-badge/guide.json`（`n / title /
req / method / links`），第 4 項 50 題分開 `item4-question-bank.json`（題目）與
`item4-answer-key.json`（答案＋解說）。播題時合併成 `config_json.questions`，
但 `engine.strip_answers()` 在送到瀏覽器之前把 `answer` / `explain_*` 剔走 —
所以答案在頁面原始碼裡面找不到，只有交卷之後由 `scout_routes._task_context()`
以 `quiz_review` 的形式補回來（連「你的答案 vs 正確答案」）。

**山洞歷險（第 4 項的遊戲）**：`content/member-badge/cave.json` 只寫故事 —— 四段壁畫（圖片、標題、
史實、年份小籤）、每段要問哪一條題目、錯路的修正文字、出口文字。題目本身仍然只有一份，住在題庫裡；
`GET /tasks/<id>/cave` 把題目按 1. 隱藏答案、2. 每段把正解插到不同位置（`order.insert(index % len, …)`）
之後，連同全部場景圖名單寫進 `data-cave-config`。遊戲由 `static/js/cave.js` 在瀏覽器內走路
（照片換景、按圖選路、死路回頭），所以同一個遊戲在離線 `demo-preview.html` 裡面一樣玩得到。
故事內容檔換掉，遊戲就換掉 —— 程式不用改。

**單一真相**：`points_ledger`（只加不改）決定餘額；`progress_records` 決定任務狀態。
`stats` 只是快取，`Store.rebuild_stats()` 可以隨時由帳本重建（有測試驗證）。

## 資料模型（與 Node 版完全相同）

15 個集合 = 試算表的 15 個分頁：

| 分頁 | 主鍵 | 用途 |
|---|---|---|
| `users` | id | 領袖與童軍（`role` 分開；`patrol` 小隊；`avatar`） |
| `sessions` | token | 登入工作階段（`expires_at`） |
| `settings` | key | 單位設定，值為 JSON 文字 |
| `stats` | user_id | 每位童軍的餘額／任務數／獎章數／連續活躍（快取） |
| `badges` | id | 進度性獎章（`order_index` 決定路線次序，`prerequisite_badge_ids`，`guide_json` = 完成指南） |
| `tasks` | id | 任務（`type`, `points`, `pass_score`, `config_json`） |
| `progress_records` | id | 每次提交（`attempt_no`, `status`, `score`, 答案／清單／相片／反思） |
| `badge_awards` | id | 已考獲獎章 |
| `points_ledger` | id | 積分帳本（只加不改，每筆都有中英理由） |
| `rewards` / `redemptions` | id | 獎品目錄與換領紀錄（換領預設關閉） |
| `suggestions` | id | 領袖推薦卡 |
| `announcements` | id | 公告（`pinned`, `expires_at`, `audience`） |
| `password_reset_requests` | id | 忘記密碼申請（領袖處理） |
| `password_resets` | id | 已寄出的重設連結：token 雜湊、到期、用過未用（`used_at`） |
| `audit_log` | id | 操作紀錄 |

複雜值（`config_json`、`prerequisite_badge_ids`）在試算表裡是同一個儲存格的 JSON 文字。
`keyFieldFor` 等價物是 `scout/schema.py:key_field`：stats→`user_id`、settings→`key`、sessions→`token`，其餘 `id`。

## 遊戲層

* 圓環 (`ring-wrap`) 由 Jinja macro 直接輸出 SVG：沒有載入閃爍，JS 只負責由 0 動畫到目標值。
* 路線圖 (`quest-map`) 是純 HTML/CSS，節點狀態 done / current / locked 由 `progress_for` 決定。
* 彩紙 (`burst`)、音效 (`sfx`)、按壓 (`pressable`)、初次導覽 (`maybeShowTour`) 在 `effects.js`；
  導覽的「下一步」是**真的換頁**（`/badges`、`/`），所以每一頁都是正常網址。
* `prefers-reduced-motion` 之下所有動畫與粒子自動消失。

### 會員章大冒險 (the adventure)

```
/badges/<id>              badge_intro.html  （唯一一頁：玩法 = 荒島故事 ＋ 尋寶圖 ＋ 區域卡；
                           ?started=1 加「冒險開始！」；?intro=1 是別名，同一頁）
/badges/<id>/requirements 官方 11 項完成要求（原來的完成要求頁）
POST /badges/<id>/start   開始冒險（fetch → JSON{ok, trail, credited}；無 JS → 302 ?started=1）
```

* 會員章**只有一頁**：`badge_intro.html`（玩法）。主頁方塊、獎章頁、任何舊連結都入這一頁；
  `guide_json.quest` 是否存在，決定它是「大冒險」還是「清單」；`?intro=1` 只是舊連結的別名。
  未出發的童軍在頁尾見到 **划出去 →**（POST 後回到 `?started=1`），已出發的見到 **繼續冒險**（`#map`）。
  之前那一頁關卡路線（`badge_quest.html`）已刪除，連同它的 CSS。
  所以領袖可以由 `content/member-badge/guide.json` 決定一個獎章是「遊戲」還是「清單」。
* 路線是**五個區域**，不是 11 關：`quest.areas` 每個區域有 `name_*`、`icon`、`hint_*` 與 `items`（屬該區的
  訓練綱要項目編號，合共 1–11）。`engine.stage_list()` 把區域與任務拼成路線
  （`{n, icon, name_*, hint_*, items_label_*, status, done, next, done_count, tasks[]}`；
  區域的狀態由區內項目歸納：全部完成＝已完成，有一項待批＝等領袖核實）。
* 開始冒險只是**一次過補回第 1 項要求**（`engine.credit_opening_stages()`）：
  該任務 `config_json = {"start_credited": true}`，代表「簡介會已經參加過，不需要再做一次」。
  它是 idempotent 的 — 再按一次不會多得一項。
* 區域只是官方要求的包裝：區域與項目是一對多，官方 11 項全部要在路線之內完成，沒有任何新分數。
* **玩法頁就是一個荒島故事**，不是一堆框：文案全部在 `guide.json` 的 `quest.beats_*`
  （三段：在荒島醒來 → 走過五個區域 → 沙灘上的木筏），頁面沿著一條虛線小徑渲染出來，
  最後一段是**尋寶圖**（= 你的逃生路線）：米色紙、虛線路線、指南針／山脈／波浪與紅色的 ✕
  全部是**內嵌 SVG 墨線**（不是 emoji，也不依賴字型，離線一樣），五個區域是圖上五個標記，
  路線末端是「沙灘 · 木筏」。要修改故事，改 JSON 即可。
* 背景是 `static/img/mascots/quest-island.jpg`（手繪風荒島，與登入頁同一畫風／色系）；
  滑過只會 `transform: scale()`，**沒有 filter**（登入頁的標誌正是被 filter 造成閃爍）。
* 尋寶圖使用**純 radio + label**：
  選哪一個區域（圖上哪一個標記），下面就切換為哪一張卡，全靠頁面自己的那段 `<style>`（每個區域一行由 Jinja 生成，
  放在 `{% block head %}`）——沒有 JavaScript 也能夠切換，離線檔一樣。
* 留意兩件事：(1) `effects.js` 的 `initStageBoard()` **每個板只會綁定一次**
  （`data-stage-bound`），因為離線檔每次切換 pane 都會重新執行 `init()`；
  (2) `tools/offline_demo.py` 會把每一頁 `<head>` 的 `<style>` 抽出來，合併入檔案唯一的那個
  stylesheet —— 否則尋寶圖的規則會留在 pane 裡面，離線時就不會切換卡片。
* 標記的位置是**裝飾，不是規則**：`quest.areas` 的第 1–5 個區域落在圖上寫死的五個座標
  （`.stage-map .stage-chip:nth-child(n)`），超過五個就疊在中央；≤700px 時地圖自動摺成一條直線小路。

## 與 Node 版的分工

| | Node 版 | Python 版 |
|---|---|---|
| 前端 | SPA（`app.js` 畫畫面） | Jinja 伺服器渲染，每頁一網址 |
| 遊戲層 | `public/js/effects.js` | `static/js/effects.js`（同樣功能，無 import） |
| 資料 | local JSON / Google Sheets | 相同 |
| 密碼 | scrypt | 相同（雙向互通，`test_parity.py` 驗證） |
| 離線示範 | `demo-preview.html`（單檔） | 直接跑 `python3 -m flask --app app run` |

兩者可以同時使用，指向同一個 Google 試算表。
