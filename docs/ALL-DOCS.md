# 港島第八十二旅童軍團 · 平台文件（合訂本）

**82nd Hong Kong Group — Scout Platform: the complete manual**

_由 `tools/compile_docs.py` 於 2026-10-18 由各份文件自動合併；改動任何一份之後請重新執行。_

_Compiled automatically from the individual documents below. Edit the source file, then run the tool again._

---

## 目錄 · Contents

1. [總覽：這個平台是甚麼 — Overview — what this platform is](#1-總覽這個平台是甚麼--overview--what-this-platform-is)  
　<sub>`README.md`</sub>
2. [上線步驟（一次做完） — Going live, step by step](#2-上線步驟一次做完--going-live-step-by-step)  
　<sub>`LAUNCH.md`</sub>
3. [部署到 Vercel — Deploying to Vercel](#3-部署到-vercel--deploying-to-vercel)  
　<sub>`docs/05-vercel.md`</sub>
4. [試算表：所有人共用同一份資料 — Google Sheets as the shared database](#4-試算表所有人共用同一份資料--google-sheets-as-the-shared-database)  
　<sub>`docs/02-google-sheets-setup.md`</sub>
5. [電郵：重設密碼 — Email — password resets](#5-電郵重設密碼--email--password-resets)  
　<sub>`docs/03-email-setup.md`</sub>
6. [GitHub：備份與版本 — GitHub — backup and history](#6-github備份與版本--github--backup-and-history)  
　<sub>`docs/04-github.md`</sub>
7. [架構與設計 — Architecture and design](#7-架構與設計--architecture-and-design)  
　<sub>`docs/01-architecture.md`</sub>
8. [更新時，資料會不會受影響？ — Will an update touch the data?](#8-更新時資料會不會受影響--will-an-update-touch-the-data)  
　<sub>`docs/06-safe-updates.md`</sub>
9. [示範卡 — Demo card](#9-示範卡--demo-card)  
　<sub>`DEMO.md`</sub>


<a id="1-總覽這個平台是甚麼--overview--what-this-platform-is"></a>

## 1. 總覽：這個平台是甚麼 — Overview — what this platform is

<sub>來源 / source: `README.md`</sub>

Scout Progress Platform — the **Python edition**. Flask renders the scout and
leader pages; the interactive cave uses JavaScript. Scouts explore an island,
leaders manage content and accounts. The app supports local JSON or Google Sheets
storage and includes a one-file offline walkthrough.

> **童軍版**：童軍登入 → 看進度 → 玩任務 → 考取進度性獎章 → 儲積分換獎品。
> **領袖版**：編輯獎章與任務、開設童軍帳戶、審批提交、發公告、管理獎品。

---

### 文件：一份合訂本 + 一個打包 / the docs, compiled and packed

全部說明文件（README、LAUNCH、DEMO、docs/01–06）已合併成單一檔案
**`docs/ALL-DOCS.md`** —— 有目錄、可整份閱讀或列印。改過任何一份之後：

    python3 tools/compile_docs.py      # 重新合併 → docs/ALL-DOCS.md

要把整個平台（程式、內容、文件、截圖、原稿）收成一個檔案保存或交收：

    python3 tools/pack_release.py      # → ../deliverables/82hkg-platform-<日期>.zip

打包不含 `.git`（歷史在 GitHub）、離線示範 HTML（可用 `tools/offline_demo.py`
重新產生）與執行時資料；包內有 `MANIFEST.txt` 逐項列出內容。

---

### 離線示範 / the offline demo — `demo-preview.html`

One file, no server, no cookies: **13 screens**, from camp login and the
leader-code card to the scout's home, the single「你被困住了！」island page,
and **game 1 in location 1**. A name without a password opens the first-time
form — password and a valid email are required, nothing typed into it is kept,
and Home · 獎章 · 會員章 · 山洞 all bounce back to it until it is filled in. The syllabus reference is no longer linked from
the game page (its old direct URL still works on the live server). Game information is
printed directly on the first map stop; a single bottom button opens the cave,
without selecting a pin or casting off. Inside: four teaching murals with timelines, 50 questions, photo-backed
dead ends, local grading and a review of actual mistakes. Leaving the game
opens a cancelable restart reminder; staying preserves the current answers,
and leaving means the next visit starts from the entrance. A pass returns to
the map at **1/5 games cleared**. Games 2–5 remain locked until the leader
provides them. There is **no separate paper**, cast-off step, or automatic task
credit just for opening the game. Every screen has a 🏠 主頁 exit. The leader editors require the
live server; the offline file shows a clickable leader-home sample.

    python3 tools/offline_demo.py     # rebuild it after any template/style change

五個瀏覽器檢查（需要 `bash tools/bootstrap_browser.sh` 一次、以及 `LD_LIBRARY_PATH=/tmp/syslibs`）：

| 檢查 | 走什麼 |
|---|---|
| `tools/checks/check_offline.py` | 離線先走第一次登入的必填表單（重複密碼、長度、電郵四種錯誤＋繞路全部擋下），再走完四段壁畫和 50 題（包括死路），按實際選項算分，返回地圖見 1/5；檢查主頁出口、領袖代碼與 0 個外部請求 |
| `tools/checks/check_cave.py` | 實機版山洞：中文全程、一次錯路、伺服器評分與錯題回顧；示範童軍進度在檢查後還原 |
| `tools/checks/check_bridge.py` | 實機版**迷霧渡口**（遊戲 2）：三關教學牌、錯板重講、鋪滿過橋、伺服器記錄與會員章進度；跑完用 `demo_reset.blank_game` 還原示範童軍 |
| `tools/check_sheets.py` | 部署前先驗 Google 試算表：環境變數、金鑰、建立分頁、讀寫與相片上載，逐項報錯並印 `ALL GOOD` |
| `tools/push.sh` | 把改動提交並推送 GitHub（Vercel 隨自動部署）：`GITHUB_TOKEN=… bash tools/push.sh "說明"`；token 也可放入 `~/.82hkg-github-token` |
| `tools/bridge_preview.py` | 產生 `bridge-preview.html`：只含遊戲 2 的單檔離線試玩（不需要先過山洞），供領袖試玩及截圖 |
| `tools/checks/check_cave_editor.py` | 領袖代碼登入、四壁 50 題編輯入口、答案欄位、英語切換和手機版；不更動題庫 |
| `tools/checks/check_exit.py` | 實機和離線版離開山洞提示：主頁／會員章／頁首、取消保留答案、確認後重入由頭開始，以及英文／手機版 |
| `tools/checks/check_doors.py` | 會員章兩個入口都到「你被困住了！」；第一區直接展示遊戲資料，頁底單一按鈕直達山洞，不必選位置或「划出去」 |

The live server is the other path, and only lives while a session is open:

    # 正式預設＝沒有示範帳戶：第一次開啟會顯示「建立第一位領袖」。
    # 想看示範帳戶（demo1/demo2）就加上 DEMO_LOGIN=true SEED_DEMO=true
    pip install flask && SECRET_KEY=dev DATA_DIR=./data \
      python3 -m flask --app app run --host 0.0.0.0 --port 5001

### 1. 快速開始 (Quick start)

```bash
cd scout-platform-py
pip install flask                 # 只有這一個必要套件
python3 -m flask --app app run --host 0.0.0.0 --port 5001
```

Open <http://localhost:5001>. A brand-new install seeds sample content so every
screen is populated — replace it with your own in *Content*.

#### 示範登入 (demo sign-in — no passwords to type)

| 帳戶 | 方法 | 看到 |
|---|---|---|
| 領袖（示範部署）| `POST /login/demo/demo1` | 領袖後台 |
| 童軍（示範部署）| `POST /login/demo/demo2` | 童軍主頁 |
| 直接登入 | 領袖代碼 `0082` | 領袖後台 |
| 一按即入 | 領袖登入頁的 🧭 示範領袖 / 🎒 示範童軍 | 領袖後台 / 童軍主頁 |
| 第一次登入 | `POST /login/demo/demo3` | 免密碼進入後**必須**設定密碼 + 電郵，否則不能進入任何童軍頁面 |
| 直接登入 | `scout01 … scout06 / scout1234` | 童軍帳戶（scout07 吳卓穎 未有密碼 — 按名字即入，示範第一次登入） |

**旅團標誌**：`static/img/brand/82hkg-logo.webp`（由你提供的 JPEG 去背製作，綠色與紅色保持原色、
邊緣平滑、可放在任何底色上）、`favicon.png`（瀏覽器分頁圖示）、`82hkg-mark.webp`（「82」單字，
備用）。登入頁右上角有低調的旅團標誌，登入後的頂欄、領袖登入卡與 favicon 亦有標誌。

**名字一律英文行先**：歡迎句、頂欄、龍虎榜、帳戶表、選名頁全部以英文名做主體，中文名在旁邊略小；小隊名同理（TIGER 大字，老虎在下面）。介面文字（按鈕、標籤）仍然是中英雙語，預設中文、可切換。

**登入頁是一張全螢幕營地圖**：三隻小隊吉祥物（老虎 / 水獺 / 海鷗）就站在畫面裡，
**牠們本身就是按鈕** — 沒有另外的按鈕框。畫面左上角不加標題、底部不顯示示範帳戶、
不放「忘記密碼」、不設語言切換；右下角只有一個「🧭 領袖登入」，旅團標誌留在右上角。
- 滑鼠移上去（或 Tab 到）：那隻動物被「打燈」亮起（其餘仍然清楚可見）、畫面徐徐向牠推進，
  牠名字上方出現跳動的 ▾，底部一行字變成「老虎 · 按一下，我帶你進去」。
- 按下去：牠的名字放大、粒子四散、播放音效，約 0.6 秒後轉去該小隊的選名頁。
- 窄視窗仍然是同一張圖，改成三欄：滑到哪一欄，圖就滑過去令那隻動物填滿畫面；
  只有極窄（≤360px）才退回三張卡片版。
- 沒有 JavaScript、開啟「減少動態效果」、或用鍵盤：全部都照樣可以進入（每隻動物都是一條普通連結）。
- 圖檔：`static/img/mascots/scene.jpg`（1920×1048，1.95:1）、`tiger/otter/seagull.webp`（單隻，供卡片與選名頁用）；
  三隻動物在圖中的位置寫在 `scout/mascots.py` 的 `spot_x` / `spot_w`，換圖時改這兩個數字即可對位。
- 語言切換、忘記密碼、示範帳戶都仍然存在，只是不放在首頁：語言在登入後的頂欄（中文／EN）、
  忘記密碼**只在密碼頁**（選名頁沒有，因為那時還未需要密碼）、示範帳戶見 `/login/demo/demo1|demo2|demo3`。

童軍登入方式：**小隊 → 姓名**。

> **預覽環境小知識**：Arena 的預覽把網頁放在第三方的 iframe 內，瀏覽器會拒收 cookie。
> 平台因此把登入憑證同時放在網址（`?sid=…`），所有連結和表單都會自動帶著它 —
> 所以在預覽、無痕視窗、關掉 cookie 的瀏覽器都一樣登入得到；正常瀏覽器仍然用 cookie。

- **第一次**：按自己的名字直接進入（**毋須密碼**）— 但接著**必須**設定個人密碼並填寫
  聯絡電郵，兩項齊備才可進入主頁、獎章、山洞或任何童軍頁面；直接輸入網址或呼叫介面
  也一樣回到這張表單（`setup_required`）。之後每次登入都用這個密碼。
- **之後**：小隊 → 姓名 → 輸入自己設定的密碼。忘記了按密碼頁的「忘記密碼？」，平台會
  寄一條**一次性重設連結**到他第一次登入時填的**電郵**，他打開連結就自行設定新密碼
  （連結 60 分鐘內有效、只可以用一次；設定後舊密碼即時失效）。
  要在 *設定 → 寄信信箱* 填好單位 Gmail（應用程式密碼）才會寄信，步驟見
  `docs/03-email-setup.md`；未設定信箱、或帳號還未有電郵時，平台會改用電郵即時重設，
  docs/04-github.md           把計劃放上 GitHub（備份、版本記錄、三條路徑）
docs/05-vercel.md          正式上線：Vercel 部署、第一次建立領袖、Google 試算表儲存、上線前檢查清單
  或由領袖在 *帳戶* 版面按 🔑 代為重設。
- `scout07 吳卓穎` 保持「未設定密碼」狀態，方便示範第一次進入的情況（每次 `demo3` 進入
  都會先清空密碼，所以下次仍然由必填表單開始）。

---

### 2. 兩種儲存方式 (two storage modes)

| `DATA_DRIVER` | 資料 | 相片 | 適合 |
|---|---|---|---|
| `local` (預設) | `./data/db/*.json` | `./data/uploads/` | 試用、單機、離線 |
| `sheets` | 你的 Google 試算表（一個分頁一個資料表） | 你的 Google Drive 資料夾 | 正式使用，免費，多人即時共用 |

設定 Google 試算表：見 [`docs/02-google-sheets-setup.md`](docs/02-google-sheets-setup.md)。

**與 Node 版共用同一份試算表**：分頁名稱、欄位名稱、JSON 儲存格格式、密碼雜湊
（scrypt, n=2¹⁴, r=8, p=1, dklen=64, hex）全部一致 — 兩邊都可以讀寫同一個檔案，
帳戶與進度互通（已用測試驗證）。

---

### 3. 畫面一覽 (what's where)

#### 童軍 (scout)
| 網址 | 內容 |
|---|---|
| `/` `/home` | 主頁 — 問候（連公告）、我的獎章（五個進度性獎章）、建議（4 則 + 顯示全部；**不顯示積分**） |
| `/badges` | 獎章路線圖 (journey map)：已完成 ✅ / 進行中 ▶ / 未解鎖 🔒 |
| `/badges/<id>` | 會員章**只有一個入口頁**：「你被困住了！」故事、五區尋寶圖與沙灘木筏。第一區地圖標記**直接顯示** 🎮 童軍歷史山洞的玩法；頁底單一按鈕直達山洞，沒有選位置或「划出去」步驟。遊戲 2–5 尚未提供時顯示即將推出。進度 = 已通過遊戲數 / 5，**全部五個遊戲**才頒發會員章。地圖底部只有一顆按鈕，指向下一個**未完成而內容齊備**的遊戲；已完成的區域保留一個小門「🎮 再玩一次」（`[data-replay="stage-N"]`），入口只影響這一區，其餘進度不變，全部完成後該按鈕消失。其他獎章依原來方式顯示 |
| `/badges/<id>?intro=1` | 同一頁；舊書籤的 `?started=1` 仍可開啟原有提示，但不是新流程 |
| `/badges/<id>/requirements` | 保留給舊書籤的 **童軍綱要參考** 直接網址；會員章地圖不再顯示入口。現有 11 個參考條目與資源不是過關條件；第 4 項直接通往第一區山洞，沒有第二份試卷 |
| `POST /badges/<id>/start` | 舊入口相容路由；新畫面不再呼叫。直接以 `GET /tasks/<id>/cave` 進入遊戲，不會因進入而加分 |
| `/tasks/<id>/bridge` | 遊戲 2（M05）**迷霧渡口**：三關（銘言 3 塊 → 誓詞 15 塊 → 規律 21 塊＝全橋 39 塊）。**教學牌給原文與說明**：`teach.sentences_zh／en` 一行一句照著讀（官方措辭） —— 銘言「準備／Be Prepared」，誓詞四句（「我願以信譽為誓，竭盡所能；」「對神明，對國家，盡責任；」「對別人，要幫助；」「對規律，必遵行。」，英文用香港童軍總會官方英文誓詞「On my honour, I promise that I will do my best to do my duty to God and to my Country to help other people and to keep the Scout Law.」），規律七條（「童軍信用為人敬。」…，英文「A Scout is to be trusted.」…）。每句原文之下另給一行 `teach.details_zh／en` 說明（細字、淺色、金色左線，與原文同盒，原文一字不改），最後一行 `teach.note_zh／en` 說明木板怎樣排。**鋪木板時，空格按句子排成一行**：每塊木板帶 `line` 編號（誓詞 4 行、規律 7 行、銘言 2 行），行首寫上「第一句」／「第一條」，該行的木板拼起來就是那一句原文。句子切到最細：誓詞一塊木板一個詞（連「對」也是一塊，共四塊），規律每條切成「童軍」加兩個詞（七塊「童軍」）。**同樣文字的木板可以互換**：判定看木板寫的是甚麼（`zh`／`en`），不看它是哪一塊，只要次序對，用哪一塊都可以；選中的那一塊只會從河岸取走自己。次序錯了木板滑到河裡，教學牌的原文再講一次（不含解釋）。三關鋪滿即可過橋，`POST …/bridge-submit` 逐關比對**木板文字串**，全對才記錄完成並頒 15 分；未完成回 400 `bridge_incomplete`。中途離開同樣先提示，重入由第 1 關開始 |
| `/tasks/<id>/cave` | 遊戲 1（M04）：四段教學壁畫 + 50 題；畫面分兩層 —— 圖在上、文字卡在下（`.cave-picture` + `.cave-card-wrap`），壁畫時間線、死路、回頭故事與錯題檢討排在圖畫下方、不覆蓋圖畫；遊戲框開到最大（`min(62rem, 100dvh - 6.5rem)`，遊戲頁 `body.is-game` 收起童軍姓名那一行並收窄麵包屑），文字太長時在框內文字區捲動並顯示「▾ 向下捲動」提示（`[data-cave-more]` / `[data-bridge-more]`，捲到最後一行自動消失，右側另有可見捲軸），轉場回到該卡開頭；手機版改為整頁捲動；各組做完才開下一幅壁畫；錯路返回重試。頁首的主頁／會員章等離開入口先提示「重入須從頭開始」，可取消並保留當前作答；作答期間按瀏覽器返回／重新整理則使用瀏覽器的通用離開提示。走到洞口即自動記錄完成 M04（不須額外提交），無論分數多少均通關；分數只供檢討，不用再做試卷。**一段路錯三次**（`content/member-badge/cave.json` → `setbacks.wrong_limit`，可改 4 或 5）：死路卡會先顯示火把剩餘次數，第三次錯便彈出一個回頭故事（火把熄了／走錯路繞回原處／洞裡太悶昏倒／太累要休息／碎石封路／筆記留在壁畫前，六個故事輪流、六張新插畫），按一下回到這一幅壁畫，這一組由第一題重新答；之前錯過的題仍照樣計分。結果卡第一顆按鈕是「🎮 繼續歷程 · 進入遊戲 2」，直接開始下一段歷程（`data-cave-link="next"`）；已通關的一次離開不再顯示「重入須從頭開始」提示，未完成的一次離開仍會提示 |
| `/tasks/<id>` | 第 4 項的舊連結直接跳山洞；其他任務照常走小測驗／清單／領袖核實流程，但**不會取代**五個區域遊戲 |
| `/welcome` | 第一次進入的必填頁：新密碼 + 確認 + 聯絡電郵（`required`）。未完成前其他童軍頁面一律導回此頁，介面呼叫回 403 `setup_required`；完成後返回 `?ok=password` |
| `/rewards` | 獎品 — **唯一顯示積分的地方**（積分錢包 + 寶箱） |
| `/history` | 我的紀錄（時間軸） |
| `/leaderboard` | 龍虎榜 — 先比獎章，再比任務；全部 / 本月 / 本週 × 全旅團 / 小隊 |

#### 領袖 (leader)
| 網址 | 內容 |
|---|---|
| `/leader` | 總覽 + 六個快速動作 + 小隊狀況 + 最新提交 |
| `/leader/content` | 獎章與任務編輯器（上移/下移、草稿/發佈、前置獎章） |
| `/leader/content/tasks/<id>` | 任務內容：一般小測驗逐行輸入、清單逐行輸入、最少字數…；M04 山洞的題庫另有專用編輯頁 |
| `/leader/content/tasks/<id>/cave-questions` | **只限領袖**：按四面壁畫選擇並逐題修改山洞的中英文題目、3–4 個選項、正確答案及錯路溫習提示 |
| `/leader/review` | 審批：批准（可調分）／退回（附評語）／稍後再審 |
| `/leader/accounts` | 開設帳戶、編輯、停用、重設密碼（重設後該童軍回到「按名字即入」）、CSV 匯入匯出、調整積分 |
| `/leader/announcements` | 公告（可置頂、可設到期日） |
| `/leader/rewards` | 獎品目錄（換領功能預設關閉） |
| `/leader/settings` | 單位名稱、小隊、功能開關（獎品／龍虎榜／連續活躍／上載／公告）— **獎品與龍虎榜預設關閉** |
| `/leader/audit` | 操作紀錄（誰在何時做了甚麼） |

---

### 4. 規則 (the rules, in one place)

* **獎章 (進度性獎章)** — 會員章特別規則：五個區域各有**不同的已提供遊戲**，
  五個全部通過才頒發；未提供的遊戲**永不自動完成**。其餘進度性獎章使用所有已發佈任務的規則。
  前置獎章未完成時，後續獎章仍鎖住。
* **任務類型** — `quiz` 立即評分（合格分數）；`checklist` 全部打勾即完成；
  `evidence` / `reflection` / `signoff` 提交後**由領袖核實**才完成。
* **積分** — 只由「積分帳本 (points_ledger)」計算，永不漂移；任務分 + 獎章獎金，
  童軍只在 `/rewards` 看到餘額。
* **連續活躍 (streak)** — 每天首次完成任務 +1，中斷則重設，最佳紀錄保留。
* **龍虎榜** — 依「已考獲獎章 → 已完成任務」排序，**永不依積分排序**。
* **沒有 XP／等級** — 遊戲元素（圓環、路線圖、彩紙、音效）只是包裝，不是第二套分數。
* **地圖與綱要** — 五個區域的完成狀態只看各自的**遊戲**；現有的綱要項目
  只是補充參考，不算五個通關條件。遊戲 1 對應原第 4 項，移到第一區且取代其試卷；
  第一區不顯示其他任務。進入遊戲沒有隱藏任務獎勵。
* **童軍不能自行註冊** — 所有帳戶由領袖開設。

---

### 4b. 會員章 = 五個遊戲（每個區域一個）

會員章**不是一次考試**：五個區域各有一個遊戲，**五個遊戲全部完成**才可以考取會員章。

| 區域 | 遊戲 | 狀態 |
|---|---|---|
| 1 🌿 叢林深處 | **🎮 遊戲 1 · 童軍歷史山洞**（原第 4 項）| ✅ 可玩，沒有其他第一區任務或獨立試卷 |
| 2 🧭 迷霧小徑 | **🎮 遊戲 2 · 迷霧渡口**（第 5 項：誓詞、規律和銘言）| ✅ 可玩：三關木板次序遊戲（切到單詞，共 39 塊；教學牌只給官方原文，空格按句子排成一行；四塊「對」、七塊「童軍」可以互換），M05 為其任務代號 |
| 3 ⛰️ 石壁山嶺 | 遊戲 3 待領袖提供 | 🔒 即將推出 |
| 4 🏞️ 溪谷旗桿 | 遊戲 4 待領袖提供 | 🔒 即將推出 |
| 5 🌊 臨海山崗 | 遊戲 5 待領袖提供 | 🔒 即將推出 |

尋寶圖上每個區域標記直接顯示遊戲名稱與狀態；**第一區的標記直接展示山洞簡介**，
其他區域由領袖提供遊戲後亦顯示簡介，尚未提供時顯示「即將推出 · 等待領袖加入」。
不用點選地點或閱讀地圖下方的另一張卡；**頁面底部只設一個開始歷險／進入下一個遊戲的按鈕**，
不再有「划出去」或區域內的第二個 Play 連結。通關後如下一個遊戲尚未提供，按鈕暫時改為等待提示。
玩法頁的燈塔顯示 `🎮 N / 5 個遊戲已完成`。

遊戲設定保存在獎章的 `guide_json.quest.areas[].game`，初始資料來源是
`content/member-badge/guide.json`。領袖在 **領袖 → 內容 → 會員章 → 五區遊戲設定**
可修改區域的中英文名稱，並把**新建、已發佈、內容完整**的任務掛到遊戲 2–5；
如未指派，該區繼續鎖上。第一區的山洞與其 M04 進度固定為遊戲 1，第二區的渡口固定為遊戲 2（M05）；已在使用的區域要更換遊戲，須在表單勾選「確定取代這一區的遊戲」。
建立／指派任務不會替任何童軍自動通關；舊綱要任務也不會自動充當其他遊戲。
日後領袖提供遊戲的具體玩法與內容後可在此擴充，現在不預設題目。

若你在更新前已有本機 `data/db/*.json`，只需執行
`DATA_DIR=./data SEED_DEMO=false python3 tools/migrate_member_five_games.py`
**一次**，將現有會員章轉為五遊戲規則，並更新山洞的舊預設「80 分合格」文案與分數欄位（領袖自訂文字不覆蓋）；不刪童軍帳戶、進度或積分，已完成的第 4 項仍計作遊戲 1。
全新資料庫則會直接使用新設定。腳本可重跑，第二次不會更動資料。

### 4c. 領袖逐題修改山洞 / Edit cave questions as a leader

1. 在**實機版**登入領袖帳戶（示範帳戶 `demo1`：登入頁右下方**領袖入口**，代碼 `0082`），打開 **領袖 → 內容 → 會員章 → 第 4 項 M04 → 🕯️ 編輯山洞題目與答案**。在會員章的任務清單也可直接按「🕯️ 編輯題目與答案」。童軍帳戶及離線 HTML 不能儲存編輯。
2. 以左方四面壁畫的清單選擇一題。修改**中、英文題目**、3–4 個選項，按選項旁的圓點指定**唯一正確答案**，並更新**錯路溫習提示**。前三個中文選項必填、第四個可留空；英文選項留空時暫以中文顯示，但建議填妥譯文。請同時核對選項、答案、溫習提示與壁畫史實。
3. 按 **💾 儲存這一題**，然後以童軍示範帳戶試玩。每次只改一題，**50 個題號、分組、順序及既有進度均保留**；不需要另一份 80 分試卷。正在玩的童軍仍會按其進洞時看到的題目答案計分；新開始的一局才使用更改後的版本。後台**操作紀錄**會記錄修改。
4. 切勿把一般測驗內容貼入 M04 的任務編輯欄位，或直接在 `data/db/tasks.json` 調換題號／次序：兩者會破壞四面壁畫與題目的關聯；M04 的普通測驗提交已被封鎖。如要修改壁畫及時間線，應由維護者一併校對 `content/member-badge/cave.json`，那不是這個逐題表單的一部分。

**離線版與實機版不同步。** 實機修改寫入當前資料庫；`demo-preview.html` 是獨立的靜態示範，不能在檔內編輯。若實機使用本專案的**本機 JSON 資料夾**，在專案目錄執行 `python3 tools/offline_demo.py` 後，產生器會在題號／順序一致時，把本機 M04 的 50 題複製進新離線檔；童軍帳戶、進度及積分**不會複製**。若實機使用 Google Sheets，產生器不會自行連接雲端表格；需另備本機題庫來源才能帶入修改。`content/member-badge/item4-question-bank.json` 等是新資料的種子，不會覆蓋已儲存的實機修改。

**English:** Sign in as a leader → Content → Member Badge → M04 → **Edit cave questions & answers**. Pick a question from its wall, edit both prompts and the choices, mark the correct choice, update the wrong-turn recap, and save. IDs/groups remain fixed; previous progress is untouched and an open run is graded against the version it loaded. Rebuild the offline HTML after **local** database edits; Google Sheets content is not imported automatically.

### 5. 遊戲層 (the game feel)

* `static/styles.css` — 與 Node 版共用的設計系統 + 遊戲層（圓環、路線圖、寶箱、巡迴導覽、粒子）。
* `static/js/effects.js` — 音效（Web Audio 合成，無需檔案）、數字跳動、圓環動畫、
  粒子爆炸、按壓回饋、第一次進入的三步導覽、每部裝置的音效開關；
  大冒險另加：`[data-cheer]` 一按即爆星；尋寶圖的第一區資訊一直可見，不用選取標記。
* `static/js/scout.js` — 以 fetch 提交表單（無 JS 時自動退回普通表單提交）、
  小測驗進度點、清單勾選音效、相片上載、結果橫幅（合格／不合格／獎章）、
  遊戲結果與進度更新。舊版「划出去」的 JS 只保留作舊深連結相容；新畫面不使用它。
* `static/js/leader.js` — 審批佇列即時處理、行內儲存、確認對話框、設定頁小隊標籤。
* 一切尊重 `prefers-reduced-motion`；沙盒 iframe、無音效裝置、無 localStorage 都仍然可用。

---

> 沙盒重置之後（Chromium、Playwright、Python 套件都會消失）先跑一次
> `bash tools/bootstrap_browser.sh`，然後
> `LD_LIBRARY_PATH=/tmp/syslibs python3 tools/checks/check_offline.py` 就可以用真瀏覽器
> 走一次離線示範檔（不會改動任何內容，只會報告）。

### 6. 專案結構 (project layout)

```
app.py                     Flask app factory · cookies · language · uploads · /health
scout/
  schema.py                15 collections (同一份欄位表) · DEFAULT_SETTINGS · 會員章五遊戲種子 + 綱要參考
  content.py               讀 content/：綱要參考、50 題題庫、山洞場景
  util.py                  scrypt 密碼 (與 Node byte-compatible) · 日期 (Asia/Hong_Kong)
  store.py                 Store：settings / stats / uploads / 首次設定 / 示範資料
  engine.py                所有規則：評分、獎章、帳本、連續活躍、龍虎榜、建議
  auth.py                  工作階段、各級權限守衛、登入輔助
  drivers/local.py         JSON 檔（原子寫入）+ 本機相片
  drivers/sheets.py        Google Sheets v4 + Drive 上載（服務帳戶）
  routes/auth_routes.py    登入 / 小隊選名（第一次免密碼進入）/ 第一次必填設定 / 忘記密碼（寄出重設連結 + 開啟連結設定新密碼）/ 示範登入
  mailer.py                寄信：SMTP 設定、一次性重設連結信件（雙語）、測試郵件
  routes/scout_routes.py   童軍頁面 + 提交 + 上載 + JSON 視圖
  routes/leader_routes.py  領袖後台全部功能 + CSV + 審批 + 設定
templates/                 24 個 Jinja 模板 (base · partials/macros · auth · scout · leader)
                           會員章：badge_intro.html (單一故事＋五區地圖) · badge_detail.html (綱要參考)
static/                    styles.css (共用設計系統) · js/{effects,scout,leader}.js · img/ (官方獎章圖)
content/member-badge/      guide.json (11 項指南) · item4-question-bank.json (50 題) · item4-answer-key.json
tools/migrate_member_five_games.py  更新既有本機示範資料（保留帳戶、成績、積分）
docs/screens/              實機與離線截圖（故事、遊戲 1 山洞、遊戲 2 迷霧渡口、綱要、主頁；實機由 tools/checks/shots.py 重拍）
tests/                     pytest 規則、頁面、領袖與離線流程檢查
```

---

### 7. 測試 (tests)

```bash
python3 -m pytest -q          # 五區遊戲規則、舊試卷禁用、領袖配置、離線示範等
```

| 檔案 | 覆蓋 |
|---|---|
| `test_auth.py` | 小隊→姓名（第一次免密碼）→**必填設定頁**（直接開網址／呼叫介面都擋下）、密碼規則、**電郵重設連結**（只存雜湊、一次性、過期／重複使用擋下、一小時五封上限、寄信失敗不留連結）、**未設定信箱時的電郵即時重設**、示範登入、角色分隔、工作階段 |
| `test_scout_flow.py` | 每個任務類型、合格分數、獎章鎖、重做、積分帳本、連續活躍、上載 |
| `test_leader.py` | 後台、審批、帳戶、內容、**寄信設定與測試郵件（密碼永不回顯）**、**由後台寄出重設連結**、區域 2–5 遊戲配置（重複／舊任務／已有進度均擋下） |
| `test_leader_cave_editor.py` | 領袖逐題編輯、權限、50 題／四壁不變、舊進度、玩到一半時的版本、離線重新建立 |
| `test_engine.py` | 純規則：評分、答案隱藏、獎章、帳本、龍虎榜排序、建議 |
| `test_pages.py` | 每頁 200、雙語、12 個離線內嵌畫面、主頁出口、單一開始按鈕、山洞本地計分合約 |
| `test_sheets_driver.py` | 以假 Google API 驗證分頁建立、標題列、JSON 儲存格、定點更新、快取、Drive 上載 |
| `test_member_badge_guide.py` | 同一入口頁、五個不同遊戲才發會員章；第一區只有山洞、綱要參考非額外條件、舊試卷不能提交 |
| `test_cave_game.py` | 遊戲 1：四段圖文與時間線、50 題、錯路／重試、英文說明、真實分數、沒有第二份試卷 |
| `test_parity.py` | 與 Node 版比對分頁/欄位/主鍵/種子碼，以及**雙向密碼互通** |

---

### 8. 環境變數 (environment)

見 [`.env.example`](.env.example)。最常用的：

```bash
DATA_DIR=./data            # local 模式的資料夾
SECRET_KEY=...             # 表單及山洞進行中題庫的簽署密鑰（正式使用請設定固定值；SESSION_SECRET 亦可）
COOKIE_SECURE=true         # 只在 HTTPS 之下
DEMO_LOGIN=true            # 只為示範：開放 demo1 / demo2 / demo3 一按即入
SEED_DEMO=true             # 只為示範：加入示範領袖與七個示範童軍
                           # 正式上線兩者都留空（＝關閉），第一次開啟會顯示「建立第一位領袖」
DATA_DRIVER=sheets
GOOGLE_SHEET_ID=...
GOOGLE_DRIVE_FOLDER_ID=...
GOOGLE_SERVICE_ACCOUNT_FILE=./service-account.json
```

---

### 9. 起步次序 (recommended order for a real unit)

1. **設定** → 單位名稱、小隊（Tiger / Otter / Seagull → 改成你們的名字）、功能開關。
2. **內容** → 保留五枚進度性獎章並修改文字；在會員章下新增任務，內容完備後透過「五區遊戲設定」逐一掛到區域 2–5。不要把綱要參考任務當成額外通關條件。
3. **帳戶** → 逐一開設童軍（或用 CSV 匯入）。把名字告訴他們：他們按名字就可以進入，
   但**第一次必須**自行設定密碼和填寫電郵，才會見到主頁。領袖若填了初始密碼，
   該童軍登入後仍要設定個人密碼及電郵（初始密碼隨即失效）。
4. 把連結發給童軍，示範帳戶 `demo2` 可演示遊戲 1 與遊戲 2；其餘遊戲等內容提供後才開放。
5. 集會後到 **審批** 處理相片／反思／簽核。
6. 獎品備妥後，在 **設定** 打開換領，才在 `/rewards` 出現「換領」按鈕。

---

### 10. 出處 (credit)

獎章圖片取自香港童軍總會《童軍訓練綱要》
<https://scoutsinfohub.org.hk/scout-training-scheme>，供本旅團內部使用。
- **更新平台前後**：[`docs/06-safe-updates.md`](docs/06-safe-updates.md) —— 推送新版本不會動到試算表資料，附存檔工具 `tools/backup_sheet.py`。
- **正式上線步驟**：[`LAUNCH.md`](LAUNCH.md) —— 由開 Google 試算表到第一位領袖登入，一步步跟著做。

---

<a id="2-上線步驟一次做完--going-live-step-by-step"></a>

## 2. 上線步驟（一次做完） — Going live, step by step

<sub>來源 / source: `LAUNCH.md`</sub>

全部在瀏覽器做，約 30 分鐘。做完你會有三樣東西：

1. **一張 Google 試算表** —— 所有資料住的地方（帳戶、進度、積分、內容）
2. **一個 Vercel 網址** —— 童軍打開來玩的地方（例如 `https://82hkg-scout-platform.vercel.app`）
3. **一組你自己設定的領袖登入** —— 只有你有

> 全程順序很重要：**先接好試算表，才建立第一位領袖**。
> 反過來做的話，領袖帳戶會寫在臨時空間，執行個體一回收就不見。

---

### 第 0 步　先讓我推送一個修正（1 分鐘）⭐

新試算表要**最新版的程式**才會自動建立獎章目錄（會員章、5 個獎章、17 個項目）。
如果現在就接上試算表，網站會開得起來但**一張獎章都沒有**。

- 把 GitHub token 貼給我，我推送之後你再開始第 1 步。
- 或者你自己有 token 時，在專案資料夾跑：
  ```bash
  GITHUB_TOKEN=github_pat_xxx bash tools/push.sh "上線前修正"
  ```
- 推送後 Vercel 會自動重新建置（1–2 分鐘）。**先等它建好再往下做。**

---

### 第 1 步　開一張 Google 試算表（3 分鐘）

1. 用旅團的 Google 帳號登入，開 <https://sheets.new> → 建立新的空白試算表
2. 左上角改名：**82旅童軍進度**
3. 看網址列，ID 就是中間這一段：

   ```
   https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz1234567890/edit
                                          └──────────── 這就是 GOOGLE_SHEET_ID ────────────┘
   ```
4. 抄下來（複製整段 ID）。**不用**自己加工作表 —— 程式第一次連上會自動建立 15 個。

---

### 第 2 步　開一個「服務帳戶」，讓程式可以寫入試算表（8 分鐘）

這一步是給程式用的機器人帳號：它沒有密碼，只有一把鑰匙（JSON 檔）。

1. 開 <https://console.cloud.google.com> → 最上方專案選單 → **新增專案**
   - 名稱：`82hkg-scout` → 建立 → 等幾秒 → 切換到這個專案
2. 左邊選單 **API 和服務 → 程式庫**（APIs & Services → Library）
   - 搜尋 **Google Sheets API** → **啟用**
   - 再搜尋 **Google Drive API** → **啟用**（相片上載用；一齊開好省事）
   - 兩個都要在同一個專案（就是上面建立的 `82hkg-scout`）。
     完成後可以在 **API 和服務 → 已啟用的 API 和服務** 見到這兩個名字。
   - 這一步驟不會收費；小型旅團的用量遠低於免費額度。
   - ⚠️ 若未啟用，之後 `/health` 會顯示「Google Sheets API 還未在 Google Cloud 專案啟用」——
     那不是共用設定錯，而是回到這一頁按「啟用」。
3. 左邊 **APIs 和服務 → 憑證**（Credentials）→ **建立憑證 → 服務帳戶**
   - 名稱：`scout-platform` → 建立並繼續 → （不用給角色）繼續 → 完成
4. 在服務帳戶清單點進剛才那個 → 上方分頁 **金鑰（Keys）**
   → **新增金鑰 → 建立新的金鑰 → JSON → 建立** → 電腦會下載一個 `.json` 檔
5. 打開那個 JSON 檔（用記事本／文字編輯器即可），找到這一欄：

   ```json
   "client_email": "scout-platform@82hkg-scout.iam.gserviceaccount.com"
   ```

   **這個電郵就是「機器人電郵」**，下一步要共用給它。

> 金鑰檔等於密碼，不要放在公開的雲端硬碟或 GitHub。Vercel 的環境變數就是它該去的地方。

---

### 第 3 步　先驗一次金鑰（1 分鐘，強烈建議）

用瀏覽器打開 **`tools/check-service-account.html`**，把 JSON 檔的內容貼進去按「檢查」。
看到 ✅ 才繼續；它同時會告訴你 `client_email`（要共用給哪個電郵）。
最常見的三個錯誤它都會指出：

- 只複製了一部分（結尾應該見到 `}`）
- 貼了**檔案路徑**而不是檔案內容
- 複製時把 `\n` 變成了真換行（可一鍵修正）

這個工具完全在你的瀏覽器內運作，**不會上傳任何內容**。

---

### 第 4 步　把試算表和資料夾共用給機器人（2 分鐘）

1. 回到第 1 步的試算表 → 右上角 **共用** → 貼上機器人電郵
   → 權限選 **編輯者**（不是檢視者）→ 傳送
2. 相片用的資料夾（童軍上載證據相片）：
   - <https://drive.google.com> → **新增 → 資料夾** → 命名 `82旅童軍相片`
   - 右鍵 → 共用 → 同一個機器人電郵 → **編輯者**
   - 進去資料夾，網址是 `.../drive/folders/`**`<這一段>`**，那就是 `GOOGLE_DRIVE_FOLDER_ID`
3. 如果暫時不需要相片上載，第 2 點可以跳過（之後再補也可以）。

---

### 第 5 步　Vercel 部署（7 分鐘）

1. 開 <https://vercel.com> → **Continue with GitHub** → 授權登入（`hinli2021`）
2. **Add New… → Project → Import** 選 `82hkg-scout-platform`
   - 如果看不到這個 repo：按 *Configure GitHub App* 授權 Vercel 讀取它
   - **Framework Preset**：`Other`
   - **Root Directory / Build / Output**：全部留空（`vercel.json` 已經寫好）
3. **Environment Variables 在哪裡**：進入專案後，按專案上方的 **Settings**
   → 左邊清單的 **Environment Variables**（不在 General、不在 Domains，
   也不是 GitHub 的 Settings），然後 **Add New**。
   圖解見 `docs/screens/vercel-env-howto.svg`。逐個貼上，
   **Environments 要勾 Production**（Preview 建議一齊勾）：

   | 名稱 | 值 | 從哪裡拿 |
   |---|---|---|
   | `SESSION_SECRET` | 隨機 32 位以上的字串（例如 `openssl rand -hex 32` 的輸出；亂打一串英數也可以） | 自己定，定好不要再改 |
   | `GOOGLE_SHEET_ID` | 第 1 步抄下的那一段 | 試算表網址 |
   | `GOOGLE_SERVICE_ACCOUNT_JSON` | **整份 JSON 檔內容**（全選複製，連大括號一起貼上） | 第 2 步下載的檔案 |
   | `GOOGLE_DRIVE_FOLDER_ID` | 第 3 步抄下的那一段（沒有就留空或整項不填） | Drive 網址 |
   | `DATA_DRIVER` | `sheets` | 固定值 |

   - `DEMO_LOGIN`、`SEED_DEMO` **不要設定**（正式版要關掉示範帳戶）
   - ⏰ 時區已固定在程式裡（Asia/Hong_Kong），不用設
4. **存好變數之後**，到 **Deployments → 最上面那個 → ⋯ → Redeploy** → 等 1–2 分鐘。
   這一步不能省：Vercel 只在建置時讀取環境變數，已經部署好的舊版本不會自動看到新變數。
   （第一次部署時按 **Deploy** 也可以；之後每次改動變數都一定要 Redeploy。）
   → 完成後會給你網址，例如 `https://82hkg-scout-platform.vercel.app`
   - 想用自己的網域：Settings → Domains

---

### 第 6 步　第一次打開：建立第一位領袖（2 分鐘）

1. 打開那個網址 —— 應該直接看到 **「建立第一位領袖」**（不是登入頁，也不是示範帳戶）
2. 填：單位名稱（中文已預設「港島第八十二旅童軍團」）、你的姓名、登入帳號、密碼（至少 6 個字，輸入兩次）
3. 按「建立領袖帳戶，開始使用」→ 直接進入**領袖後台**，而且已經登入
4. 到 領袖後台 → **設定**，最上面有一張 **🧭 設定檢查** 卡（它只看，不會改動資料）。

   | 卡上看到甚麼 | 代表 |
   |---|---|
   | **✅ 全部就緒** ＋ 「資料儲存在 Google 試算表」 | 成功，資料以後都存在那裡 |
   | **⚠️ 還有 1 項要處理** ＋ 「資料暫存中」 | 未接通 —— 回第 5 步檢查變數名稱、`GOOGLE_SERVICE_ACCOUNT_JSON` 是否貼完整，然後 Redeploy |

   卡上共 7 項：儲存位置、獎章目錄、任務與遊戲項目、遊戲 1／2 內容、領袖帳戶、童軍帳戶、
   寄信信箱（可選）。未完成的那一項會直接寫「怎樣做」。

5. 回頭看試算表：應該多了 15 個工作表；`badges` 有 5 列、`tasks` 有 17 列。
   這代表獎章目錄已經建立好，之後的更新都不會再改動它。

**領袖登入**：登入頁右下角「領袖入口」→ 在「領袖代碼」一欄輸入**你自己設定的密碼**。

---

### 第 7 步　開童軍帳戶（每人約 30 秒）

領袖後台 → **帳戶 → ➕ 開設童軍帳戶**：中文姓名、英文姓名、小隊（Otter／Tiger／Seagull）、
用戶名稱（留空自動產生）→ 把臨時密碼給童軍。

童軍那邊：打開網址 → **登入** → 點自己的小隊（英文）→ 點自己的中文名 →
第一次登入要**建立自己的密碼**並填**電郵**（忘記密碼用的）。

- 想一次輸入全團：用同一頁的 **⬇️ 匯出 CSV** 保存帳戶清單
- 童軍**不能自行註冊**，所有帳戶都由你開

---

### 第 8 步　電郵（找回密碼）—— 可選但建議（10 分鐘）

沒有設定也能用：系統會請童軍在設定頁自行輸入電郵即時重設。
要讓「寄一條重設連結」真的寄得出去，見 `docs/03-email-setup.md`：
Gmail 應用密碼 → 領袖後台 → 設定 → 寄信信箱 → **試寄一封**。

---

### 第 9 步　上線前最後檢查

- [ ] GitHub repository 已改為 **Private**（Settings → General → Danger Zone）
- [ ] 領袖後台 → 設定：看到 **✅ 資料存放於 Google 試算表**（不是暫存警告）
- [ ] 用領袖代碼登入過一次
- [ ] 開了一個**測試童軍**帳戶，實際玩過遊戲 1（石室）與遊戲 2（過河）
- [ ] 玩完之後，試算表 `progress_records`、`points_ledger` 多了對應的列
- [ ] 試算表 **檔案 → 建立副本** 留一份備份（或設定 → 版本記錄，看你做過的每一步）
- [ ] 已把網址發給童軍（連同離線檔 `demo-preview.html` 一起給更好）

---

### 隨時檢查：打開網址後加 `/health`

在瀏覽器輸入 **`<你的網址>/health`**，會看到一張「🩺 平台狀態」頁：

- **✅ 一切正常** ＋ 「資料儲存在 Google 試算表」 → 設定完成
- **⚠️ 有 N 項要處理** ＋ 「資料暫存在執行個體空間」 → 未接通，頁面會直接寫出怎樣做
  （最常見：加了環境變數但**未 Redeploy**）

同一頁下半部會列出獎章／任務／帳戶的數量，以及示範帳戶是否已關閉。
它只讀，不會改動任何資料，也不會顯示任何姓名。

---

### 出事怎辦

| 情況 | 處理 |
|---|---|
| 網站顯示錯誤 / 500 | Vercel → 專案 → **Logs** 看 `api/index` 的訊息；最常見是 Google 金鑰貼錯或截斷 |
| 玩了一段時間後回到登入頁、資料像重置了 | 未接上試算表（領袖後台 → 設定會顯示暫存警告）→ 回第 5 步 |
| 想回到舊版本 | Vercel → **Deployments** → 上一個正常版本 → ⋯ → **Promote to Production**（一分鐘，資料不變） |
| 試算表誤刪／改錯 | 試算表 → **檔案 → 版本記錄 → 查看版本記錄**，還原到任何時間點 |
| 相片上載失敗 | `GOOGLE_DRIVE_FOLDER_ID` 未設，或資料夾未共用給機器人電郵 |
| 忘記領袖密碼 | 有填電郵的話可用「忘記密碼」；否則用另一個領袖帳戶代為重設 |

---

### 可以貼給我看的東西（不要貼金鑰）

- Vercel 網址 —— 我可以從這裡檢查正式站：沒有示範帳戶、登入頁正常、遊戲進得去
- 第 5 步「設定」那張卡是 ✅ 還是 ⚠️
- 機器人電郵（`scout-platform@…iam.gserviceaccount.com`）—— 用來確認共用對象對不對

相關文件：
`docs/02-google-sheets-setup.md`（試算表詳解）、`docs/05-vercel.md`（部署與疑難排解）、
`docs/06-safe-updates.md`（更新時資料的安全保證）、`docs/03-email-setup.md`（寄信設定）。

---

<a id="3-部署到-vercel--deploying-to-vercel"></a>

## 3. 部署到 Vercel — Deploying to Vercel

<sub>來源 / source: `docs/05-vercel.md`</sub>

正式版的流程：在這裡改東西 → 推送 GitHub（`tools/push.sh`）→ Vercel 自動重新建置 →
童軍打開網址就可以用。**資料不在 Vercel 上**，資料在 Google 試算表（見第 4 節），
Vercel 只是跑程式的地方。

> 想一步一步跟著做（開試算表 → 服務帳戶 → 共用 → Vercel → 第一位領袖）：
> 見根目錄的 **[`LAUNCH.md`](../LAUNCH.md)**。這份文件是細節與疑難排解。

---

### 1. 首次部署（瀏覽器做一次，約 5 分鐘）

1. **Vercel**：<https://vercel.com> → **Continue with GitHub**（`hinli2021`）登入 →
   **Add New… → Project → Import** 選 `82hkg-scout-platform`。
   - 私人 repository 要按 *Configure GitHub App* 授權 Vercel 讀取它。
   - **Framework Preset**：`Other`；**Build／Output Directory 留空**（`vercel.json` 已寫好）。
2. **Environment Variables**（Settings → Environment Variables，Production 與 Preview 都勾）見第 3 節。
3. **Deploy**。完成後會有網址，例如 `https://82hkg-scout-platform.vercel.app`。
   （可以再綁自己的網域：Settings → Domains。）

### 2. 第一次開啟平台：建立第一位領袖

正式版**沒有示範帳戶**。第一次打開網址，平台會直接顯示 **「建立第一位領袖」**：

1. 填單位名稱（中文必需，英文可留空）、領袖姓名（中文必需）、登入帳號、密碼（至少 6 個字）。
2. 按「建立領袖帳戶，開始使用」→ 直接進入**領袖後台**，並且已登入。
3. 之後這一頁自動收起，任何人再到網址就只看到登入頁。

> 領袖登入：登入頁右下角**領袖入口** → 在「領袖代碼」一欄輸入**你自己設定的密碼**。
> （示範帳戶的 `0082` 只屬於離線試玩檔與示範部署。）

**接著在領袖後台建立童軍帳戶**：領袖 → 帳戶 → 新增（選擇小隊、姓名、設定密碼）。
童軍第一次登入會看到「建立密碼／填電郵」的設定頁，之後就可以玩。

### 3. 環境變數

| 名稱 | 值 | 說明 |
| --- | --- | --- |
| `SESSION_SECRET` | 隨機長字串（例如 `openssl rand -hex 32`） | **建議設定**。未設定時平台會自動產生一次並保存在資料庫（試算表）裡，同樣不會登出；但明確設定最清楚 |
| `DATA_DRIVER` | `sheets` | 正式儲存：資料寫進 Google 試算表（第 4 節）。不設定而只給 `GOOGLE_SHEET_ID` 時，程式也會自動用 `sheets` |
| `GOOGLE_SHEET_ID` | 試算表 ID | 網址 `docs.google.com/spreadsheets/d/`**`<這一段>`**`/edit` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 服務帳戶金鑰**整段 JSON** | 貼在值欄（`GOOGLE_SERVICE_ACCOUNT_FILE` 亦可，但 Vercel 上通常用 JSON 變數） |
| `GOOGLE_DRIVE_FOLDER_ID` | 雲端硬碟資料夾 ID（可留空） | 童軍證據相片存放位置；留空則不能上載相片 |
| `DEMO_LOGIN` | 不設定（＝關閉） | 只在**示範部署**才設 `true` |
| `SEED_DEMO` | 不設定（＝關閉） | 同上；正式版不要開，否則會加入示範童軍 |
| `DATA_DIR` | `/tmp/scout-platform-data` | 只在沒有設定試算表時才用得到的暫存位置 |

**TZ** 已在 `api/index.py` 固定為 `Asia/Hong_Kong`，日期與「今日」都以香港時間計。

### 4. 資料放在 Google 試算表（正式版的資料庫）

1. 開一個新的 Google 試算表（名稱例如「82旅童軍進度」）。
2. 到 <https://console.cloud.google.com>：建立專案 → 啟用 **Google Sheets API** 與 **Google Drive API**
   → **IAM 與管理 → 服務帳戶** → 建立服務帳戶 → 建立**金鑰（JSON）**。
3. 把試算表**共用**給服務帳戶的電郵（`…@….iam.gserviceaccount.com`），權限「編輯者」；
   相片用的雲端硬碟資料夾亦一樣共用。
4. 把 JSON 金鑰內容貼進 Vercel 的 `GOOGLE_SERVICE_ACCOUNT_JSON`，並填 `GOOGLE_SHEET_ID`。
5. Redeploy。第一次連上時，程式會在試算表建立所有工作表（一行一筆資料），之後就可以用。

逐步做法見 **`docs/02-google-sheets-setup.md`**（Google 三步 → Vercel 環境變數 → 檢查）。
做完之後，領袖後台 → 設定 會顯示 **✅ 資料存放於 Google 試算表**（附連結）；仍顯示「⚠️ 資料暫存中」即代表未接通。

本機可以先驗一次再部署：

```bash
export DATA_DRIVER=sheets GOOGLE_SHEET_ID=1AbC…xyz GOOGLE_SERVICE_ACCOUNT_FILE=./service-account.json
python3 tools/check_sheets.py      # 逐項檢查，最後印 ALL GOOD
```

> **沒有試算表會怎樣？** 平台仍可運作，但資料寫在執行個體的 `/tmp`，
> 一段時間沒有流量就回收 → 帳戶與進度回到空白。領袖後台 → **設定** 會顯示
> 「⚠️ 資料暫存中」的提醒，看到這個提示就代表還未接上試算表。

### 隨時檢查部署：`/health`

瀏覽器打開 `<網址>/health` 會看到「🩺 平台狀態」頁（程式呼叫時仍是 JSON）：

- 儲存位置是否為 Google 試算表（不是就會寫出修正步驟）
- 獎章／任務／帳戶數量
- 示範帳戶是否已關閉
- 這一頁只讀，不會寫入任何資料，也不含任何個人資料

> JSON 版本（供腳本用）：`curl -s <網址>/health` → `{"ok":true,"storage":"sheets",…,"setup_ready":true}`

### 5. 每次更新的流程

```bash
cd scout-platform-py
GITHUB_TOKEN=github_pat_xxx bash tools/push.sh "這次改了甚麼"
```

推送 `main` 之後，Vercel 約 30–60 秒自動建置新版本（Deployments 頁可看進度）。
Token 只需要這個 repository 的 **Contents: Read and write**，用完可以即時撤銷。

### 6. 上線前檢查清單

- [ ] repository 已設為 **Private**（GitHub → Settings → General → 最底 Danger Zone）
- [ ] Vercel 已加 `SESSION_SECRET`、`GOOGLE_SHEET_ID`、`GOOGLE_SERVICE_ACCOUNT_JSON`
- [ ] 已建立第一位領袖，並且用領袖代碼登入過一次
- [ ] 領袖後台 → 設定 → **🧭 設定檢查** 卡顯示「全部就緒」（7 項之中，寄信信箱為可選）
- [ ] 領袖後台 → 設定，**沒有**看到「資料暫存中」警告
- [ ] 已建立至少一個童軍帳戶，實際玩過遊戲 1 與遊戲 2
- [ ] 領袖後台 → 設定 → SMTP，用「試寄一封」確認找回密碼的郵件真的出得去（`docs/03-email-setup.md`）
- [ ] 已把網址發給童軍（可連同 `demo-preview.html` 離線檔一起）

### 7. 疑難排解

| 情況 | 處理 |
| --- | --- |
| 網站顯示 page is not available／Function crashed 之後改好環境變數仍然一樣 | 多數是部署缺少套件或變數內容有誤。2026-10-16 曾發生：`requirements.txt` 少了 `google-auth`，一設 `DATA_DRIVER=sheets` 就在啟動時 `ModuleNotFoundError: No module named 'google'` 而全站掛掉。已修正；Redeploy 最新版本即可。現在程式亦會在連不上試算表時改用暫存並在 `/health` 說明原因，不會再整站消失 |
| 網站 500（Function Error） | Vercel → Project → Logs 看 `api/index` 的訊息；最常見是 `templates/`、`content/` 沒有被 `includeFiles` 帶上，或 Google 金鑰貼錯 |
| 玩了很久之後回到登入頁 | 執行個體被回收、資料回到示範狀態 → 未接上試算表；按第 4 節設定 |
| 童軍上載相片失敗 | 未設 `GOOGLE_DRIVE_FOLDER_ID`，或資料夾未共用給服務帳戶 |
| 忘記領袖密碼 | 有電郵的帳戶可用「忘記密碼」；否則在另一個已登入的領袖帳戶 → 帳戶 → 重設密碼 |
| 想換網址 | Settings → Domains 綁自己的網域；更新後記得在領袖設定填回正確網址 |

### 上線之後：推送新版本安全嗎？

安全。資料在 Google 試算表，不在程式碼裡；新版本只會讀取，不會覆寫。

- 目錄（獎章／任務）只在**空試算表第一次連上**時建立一次，之後永不重寫。
- 領袖改過的任何內容、童軍的進度與積分，全部留在試算表，Redeploy 後照樣在。
- 自動測試 `tests/test_redeploy_keeps_data.py` 已模擬「推送＋重新部署」整段流程並通過。
- 詳見 `docs/02-google-sheets-setup.md`「推送新版本會不會洗掉資料？」。
- 完整的安全更新流程（更新前備份、更新後比對、一鍵回舊版）：`docs/06-safe-updates.md`；
  存檔工具：`python3 tools/backup_sheet.py`（只讀試算表，存到 `backups/`）。

---

<a id="4-試算表所有人共用同一份資料--google-sheets-as-the-shared-database"></a>

## 4. 試算表：所有人共用同一份資料 — Google Sheets as the shared database

<sub>來源 / source: `docs/02-google-sheets-setup.md`</sub>

目標：**你的 Google 試算表就是資料庫**，相片存在你的 Google Drive 資料夾。
童軍在家用電話、在集會用平板、領袖在電腦登入，看到的都是同一份進度；
Vercel 重新部署、執行個體被回收，資料都不會消失。

> 已經有 Node 版用的試算表？不用重建。填同一個 Sheet ID 即可 ——
> 分頁、欄位、密碼格式完全相容。

**次序**：①②③ 在 Google 做，④ 在 Vercel 做，⑤ 回來這頁檢查。

---

### ① 建立試算表（1 分鐘）

1. 到 <https://sheets.new> 建立新試算表。
2. 命名為例如「童軍進度平台 2026」。
3. 從網址複製 ID：
   `https://docs.google.com/spreadsheets/d/`**`1AbC…xyz`**`/edit`
   → 這就是 `GOOGLE_SHEET_ID`。
4. **分頁不用自己建立** —— 程式首次連上時會自動建立 15 個分頁與標題列。

### ② 建立服務帳戶與金鑰（3 分鐘，只需一次）

1. 到 <https://console.cloud.google.com/> → 上方專案選單 → **新增專案**（例如 `scout-platform`）。
2. **API 和服務 → 程式庫** → 分別搜尋並**啟用**兩個 API：
   * **Google Sheets API**
   * **Google Drive API**（相片用；沒有它其餘功能照常）
3. **IAM 與管理 → 服務帳戶 → 建立服務帳戶**
   * 名稱：`scout-platform`；角色可留空（權限由「分享」決定）。
4. 建立後點進該服務帳戶 → **金鑰 → 新增金鑰 → JSON → 建立**，會下載一個 `.json` 檔。
5. 打開那個檔案，找到 `client_email`，樣子像：
   `scout-platform@你的專案.iam.gserviceaccount.com`
   → **複製它**，下一步要用。

### ③ 分享給「機械人」電郵（最容易漏的一步）

| 分享甚麼 | 給誰 | 權限 |
|---|---|---|
| 你的**試算表**（按「共用」） | 上一步的服務帳戶電郵 | **編輯者** |
| Drive 的**相片資料夾**（可選） | 同上 | **編輯者** |

就像分享文件給同事，只是對象是一個機械人電郵；**不是**分享給自己。
權限一定要「編輯者」，只給「檢視者」會在第一次寫入時失敗（403）。

相片資料夾：在 Drive 建立例如「童軍進度平台 — 相片」，共用給同一電郵，
然後從網址複製 `https://drive.google.com/drive/folders/`**`1XyZ…`** → 這是
`GOOGLE_DRIVE_FOLDER_ID`。不設定也可以，相片會放在服務帳戶自己的 Drive。

### ④ 在 Vercel 加入環境變數（3 分鐘）

Vercel → 你的專案 → **Settings → Environment Variables**，逐項 **Add**：

| 名稱 | 值 | 備註 |
|---|---|---|
| `DATA_DRIVER` | `sheets` | 一定要 |
| `GOOGLE_SHEET_ID` | ①的 ID | 一定要 |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | ②下載的**整個 JSON 檔案內容**（由 `{` 到 `}` 全部貼上） | 一定要 |
| `GOOGLE_DRIVE_FOLDER_ID` | ③的資料夾 ID | 要收相片才需要 |
| `SESSION_SECRET` | 隨機長字串（`openssl rand -hex 32`） | 建議 |

* 貼 JSON 時把檔案的內容**原文**貼進值欄即可，不需要改格式。
* 加好之後 → **Deployments → 最新一筆 → …→ Redeploy**（改環境變數一定要重新部署）。

### ⑤ 檢查接通了沒有

**方法一（最直接）**：登入領袖後台 → **設定**，看到

> ✅ **資料存放於 Google 試算表**（附試算表連結）

就代表成功。若看到「⚠️ 資料暫存中，會自己重置」，即代表還未接上（多數是 `DATA_DRIVER` 或步驟③的分享）。

**方法二（本機先驗一次，最省時間）**：在自己電腦用同一組環境變數跑

```bash
export DATA_DRIVER=sheets
export GOOGLE_SHEET_ID=1AbC…xyz
export GOOGLE_SERVICE_ACCOUNT_FILE=./service-account.json
python3 tools/check_sheets.py
```

它會順序檢查：環境變數 → 金鑰 → 開試算表 → 建立分頁 → 讀寫測試 → 相片上載，
最後印 `ALL GOOD` 或指出哪一步要修。**在 Vercel 之前跑一次，就不用來回部署。**

**方法三**：打開試算表本身，分頁裡應該即時看到 `users`（領袖那一列）等資料。

---

### 之後會是怎樣

- 童軍在任何裝置登入 → 讀寫的都是同一份試算表；換電話、換電腦進度都不會不見。
- 領袖後台改內容、開帳戶、審批 → 直接寫入試算表；同步到所有裝置。
- 每次部署新版本（`tools/push.sh`）**不會**影響資料：資料在試算表，不在 Vercel。

### 推送新版本會不會洗掉資料？（答案：不會）

這是設計上刻意保證的，不是巧合：

| 情況 | 會發生的事 |
|---|---|
| 空試算表第一次連上 | 程式建立獎章、任務等「目錄」一次，內容是空的 |
| 以後每次部署新版本 | 目錄**已存在就完全不碰**；只讀，不寫 |
| 領袖在後台改過的標題、題目、答案 | 永遠保留，新版本不會蓋過去 |
| 童軍的進度、積分、提交記錄 | 全部在試算表，程式只新增，不重寫 |
| 想換回舊版本 | 直接 Redeploy 舊 commit 也可以，資料完全不變 |
| 誤開了 `SEED_DEMO=true` | 若已有領袖，示範資料**不會**被植入 |

自動測試 `tests/test_redeploy_keeps_data.py` 會真的模擬一次「推送新版本＋重新部署」：
建立領袖、開童軍帳戶、完成任務、改標題與題目，再用同一份試算表重新啟動 ——
所有列數與編輯必須一字不差。所以**不需要重設，也不需要重新輸入資料**。

> 日後如果程式新增「新的獎章或新的遊戲」，下次開啟平台時會**自動補上缺少的
> 那一項**（只新增，不會動到你已有的內容）。你在後台**刪除**過的項目會記在
> 設定的 `catalog_removed`，不會自己回來。
- 建議偶爾在試算表「檔案 → 建立副本」留一份備份；也可以下載成 `.xlsx` 存檔。

### 常見問題

| 情況 | 原因 / 解法 |
|---|---|
| 領袖設定仍顯示「資料暫存中」 | `DATA_DRIVER=sheets` 未設，或未 Redeploy |
| `403 … has not been used in project … or it is disabled` | **API 未啟用**（不是共用問題）：到 console.cloud.google.com → API 和服務 → 程式庫，啟用 **Google Sheets API** 與 **Google Drive API**，等一兩分鐘後 Redeploy |
| `403 … The caller does not have permission` | 未分享試算表給服務帳戶電郵，或只給了檢視權限 |
| `GOOGLE_SHEET_ID is required` | 環境變數名稱打錯，或值有前後空白 |
| 相片打不開 | Drive 資料夾未分享給服務帳戶；程式會嘗試設為「知道連結者可檢視」 |
| 想確認是不是真的在寫入 | 一邊用人員帳戶玩遊戲，一邊開著試算表 `progress_records` 分頁看它增加 |
| 想搬回本機 | `DATA_DRIVER=local`，資料就寫到 `./data/db/*.json` |
| 想由本機轉上雲端 | 把 `data/db/*.json` 的內容貼到對應分頁（欄位相同），第一列放欄位名稱 |

### 本機測試（不用 Vercel）

```bash
export DATA_DRIVER=sheets
export GOOGLE_SHEET_ID=1AbC…xyz
export GOOGLE_SERVICE_ACCOUNT_FILE=./service-account.json
export SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))")
python3 -m flask --app app run --host 0.0.0.0 --port 5001
```

### 免費額度

Sheets API 對小型旅團（數十位童軍、每天數百次讀寫）遠遠用不完；
讀取有 15 秒快取，寫入是定點更新，不會重寫整個分頁。

### 貼上金鑰之前，先驗一次

用瀏覽器打開 `tools/check-service-account.html`，貼上 JSON 內容按「檢查」：
它會告訴你金鑰是否有效、`client_email` 要共用給哪個電郵，並指出最常見的三個貼上錯誤
（只複製一部分、貼了檔案路徑、複製時 `\n` 變成真換行）。
工具只在你的瀏覽器內運作，不會上傳任何內容。

> 程式現在也會自行處理兩種情況：整段值被引號包住，以及 `private_key` 裡的 `\n`
> 變成真換行。其餘錯誤會在 `/health` 與領袖後台 → 設定 直接寫出原因與做法。

---

<a id="5-電郵重設密碼--email--password-resets"></a>

## 5. 電郵：重設密碼 — Email — password resets

<sub>來源 / source: `docs/03-email-setup.md`</sub>

平台要寄出「重設密碼」連結，就需要一個寄信信箱。**單位的 Gmail 就可以了**（學校或總會的
帳戶通常封鎖外部登入，除非管理員另外給你應用程式密碼；一般 Gmail 最簡單）。

設定好之後的流程：

1. 童軍在密碼頁按「忘記密碼？」。
2. 平台寄一封信到他**第一次登入時填的電郵**（他不需要再打一次電郵）。
3. 他打開信裡的連結（一次性、預設 60 分鐘內有效），設定新密碼。
4. 舊密碼即時失效；舊的登入狀態也會一併登出。

---

### 一、開一個 Gmail 應用程式密碼（約 3 分鐘）

1. 用單位 Gmail 登入 <https://myaccount.google.com>。
2. **安全性** → 開啟 **兩步驗證（2-Step Verification）**。沒有開這個，下面就不會出現
   應用程式密碼。
3. 回到**安全性** → **應用程式密碼 / App passwords**。
4. 名稱隨意填（例如 `scout platform`），按**建立**。
5. Google 會給你 16 個英文字母（顯示為 4 組、每組 4 個字，例如 `abcd efgh ijkl mnop`）。
   **複製它** —— 只會顯示一次。

> 這 16 個字是給程式用的，不是你平時登入 Gmail 的密碼。如果外洩，可以隨時在同一個頁面
> 刪除再建立一個新的。

### 二、填進平台

領袖登入 → **⚙️ 設定** → **✉️ 寄信信箱（重設密碼連結）**：

| 欄位 | 填甚麼 |
|---|---|
| SMTP 主機 | `smtp.gmail.com` |
| 連接埠 | `587` |
| 加密 | `TLS (587)` |
| 寄件人 | 單位 Gmail，例如 `82hkg@gmail.com` |
| 帳號 | 同一個 Gmail |
| 應用程式密碼 | 貼上那 16 個字 |
| 重設連結有效期 | 預設 60 分鐘 |
| 平台網址 | 留空即可（見下） |

按**儲存設定**，然後在「🧪 試寄一封」填自己的電郵按**寄測試郵件**。收到就成功了。
設定頁會顯示上一次寄信的結果，失敗時會寫出原因（例如 `SMTPAuthenticationError` = 應用程式
密碼錯了）。

### 三、網址要注意的事

電郵裡的連結會用「使用者正在用的網址」。所以：

- **在自己電腦跑**（例：`http://192.168.1.20:5001`）：童軍要在同一個 Wi-Fi 才開得到。
  想指定另一個地址，就在「平台網址」填上，例如 `http://192.168.1.20:5001`。
- **真正放在伺服器**（有網域）：在「平台網址」填 `https://your-domain.example`。

### 四、沒有設定信箱時會怎樣？

不會壞，只是走另一條路：

- 童軍按「忘記密碼？」時，會看到「領袖還未設定寄信的信箱」，然後可以**即時**用電郵 +
  新密碼自行重設（這個方法無須寄信）。
- 帳號未有電郵的童軍，就只會看到「通知領袖重設密碼」的按鈕。
- 領袖後台的「🔑」鈕（代為重設）任何時候都可以用。

### 五、安全設計（供領袖了解）

- 連結裡是隨機 32 位元組的 token；平台只存它的 **SHA-256 雜湊**，資料庫被看到也不能用。
- **一次性**：設定完新密碼即失效，其他未用的連結亦一併作廢。
- **有時限**：預設 60 分鐘（可改成 5–1440 分鐘）。
- **寄出頻率有上限**：同一帳號一分鐘最多一封、一小時最多五封，避免有人用來濫發。
- 寄信失敗時，那個 token 立即作廢，不會留下「未寄出但有效」的連結。
- 電郵內容只寫姓名、連結與有效期，**永不包含密碼**。

---

<a id="6-github備份與版本--github--backup-and-history"></a>

## 6. GitHub：備份與版本 — GitHub — backup and history

<sub>來源 / source: `docs/04-github.md`</sub>

**現況：已放上 https://github.com/hinli2021/82hkg-scout-platform（私人 repository）**
- 第一次上載：2026-10-16，163 個檔案、一次提交（commit `821d44e`）。
- 未上載：`data/db/sessions.json`（登入憑證，程式自動重建）、`data/uploads/`（童軍相片）。
- **110 張介面截圖**存放在同一個 repository 的另一個分支 **`screenshots`**
  （壓縮版，22 MB），不佔用本機空間：
  `https://github.com/hinli2021/82hkg-scout-platform/tree/screenshots/docs/screens`
- 本機 `docs/screens/` 只保留最新 12 張（壓縮版），PNG 不入版控，重拍不會弄髒 `git status`；
  檢查腳本隨時可以重拍任何一張。

### 每次改動之後推送

```bash
GITHUB_TOKEN=github_pat_xxx bash tools/push.sh "這次改了甚麼"
```

推送 `main` 之後，Vercel 會自動重新部署正式網站（見 `docs/05-vercel.md`）。
token 只需要**這一個 repository** 的 **Contents: Read and write**；用完可以即時撤銷。
若把 token 寫入 `~/.82hkg-github-token`（在 repository 之外，不入版控），
`tools/push.sh` 就會自動讀取，之後不必每次貼上。

整個計劃就是 `scout-platform-py` 這一個資料夾。放上 GitHub 之後，每次改動都有一個記錄，
換電腦、換領袖接手，都可以由同一個地方取回完整檔案。

### 三條路，選一條

#### A. 由這裡直接推送（最快，需要一個 GitHub token）　←　現時採用這一條
1. 在 GitHub 開一個新的 repository：名稱 `82hkg-scout-platform`、**Private**，
   **不要**勾選 Add README／.gitignore／licence（要完全空白）。
2. 開一個 **fine-grained token**：GitHub → 右上頭像 → Settings → Developer settings →
   Personal access tokens → **Fine-grained tokens** → Generate new token：
   - Repository access → Only select repositories → 只選 `82hkg-scout-platform`
   - Permissions → Repository permissions → **Contents: Read and write**（其餘保持 No access）
   - Expiration 選最短（例如 7 days）
3. 把 **repository 網址**（`https://github.com/<你的帳號>/82hkg-scout-platform.git`）與 **token** 交給平台。
   平台會把 163 個檔案推送上去（附一次提交記錄）。
4. 推送完成後，立即回 GitHub 同一頁按 **Revoke** 撤銷那個 token；日後要再推送，另開一個新 token。

> token 等於一次性的鑰匙：只給這一個 repository、只給推送權限、用完即撤銷。
> 若不想交出 token，用 B 或 C。

#### B. 下載後在 GitHub 網頁上傳（不需要安裝任何工具）
1. 下載 `scout-platform-py.zip`，解壓縮。
2. GitHub → New repository → 建立空的 repository（私人或公開由領袖決定）。
3. 在新 repository 按 **Add file → Upload files**，把解壓後資料夾內的東西**全部**拖進去
   （如檔案太多，可只上載 `app.py`、`scout/`、`content/`、`templates/`、`static/`、`data/`、
   `tools/`、`tests/`、`docs/` 及說明文件）。
4. 按 Commit changes，完成。

#### C. 用 git 或 GitHub Desktop（日後要自己更新的話最方便）
```bash
cd scout-platform-py
git init -b main          # 或直接解壓 zip 後執行以下指令
git config user.name "你的名字"
git config user.email "你的電郵"
git add .
git commit -m "童軍進度平台：第一次上載"
git remote add origin https://github.com/<你的帳號>/<repo>.git
git push -u origin main
```
GitHub Desktop 的話：File → Add local repository → 選 `scout-platform-py` → Publish repository。

### 以下東西不會上載（`.gitignore` 已設好）

| 檔案／資料夾 | 原因 |
| --- | --- |
| `docs/screens/` | 110 張介面截圖（約 68 MB）；留在工作區，檢查腳本可隨時重拍，不入庫 |
| `data/db/sessions.json` | 登入憑證（已清空才提交；程式會自動重建這個檔案） |
| `data/uploads/*` | 童軍上載的相片，屬於個別帳戶的私人資料 |
| `__pycache__/`、`.pytest_cache/`、`*.pyc` | 執行時產生的暫存檔 |
| `.env`、`*.pem` | 任何秘密（SMTP 密碼、服務帳戶金鑰） |
| `*.log`、`*.tmp` | 測試記錄等暫存檔 |

`data/db/` 其餘的示範資料（示範領袖與七個示範童軍、獎章、內容）都會上載，
這樣在任何電腦 clone 下來都可以直接 `python3 app.py` 開來試玩。

### 檔案大小

截圖已排除，repository 約 **22 MB**（163 個檔案）：程式、內容題庫、離線試玩檔與測試都在內。
需要看畫面時，在平台這裡開 `docs/screens/` 就可以，或用 `tools/checks/` 內的檢查腳本重拍。

### 日後更新

- 平台代你推送：改完之後說一聲「更新 GitHub」，平台會再推一次。
- 自己推送：把新的檔案覆蓋到同一個資料夾，然後 `git add -A && git commit -m "說明" && git push`。

---

<a id="7-架構與設計--architecture-and-design"></a>

## 7. 架構與設計 — Architecture and design

<sub>來源 / source: `docs/01-architecture.md`</sub>

### 沒有 cookie 也要登入得到 (the preview iframe)

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

### 第一次進入的流程 (first entry: password + email are required)

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

### 為甚麼是伺服器渲染

Node 版是一個 SPA：一個 HTML 檔 + JavaScript 在前端畫出所有畫面。這一版把同樣的
功能改成**每一頁有自己的網址**：

* 童軍可以加書籤、按上一頁、把 `/badges` 的連結貼給隊友 — 對小朋友重要。
* 無 JavaScript 也完全可用（學校電腦、舊平板、被封鎖的瀏覽器）；JS 只是加分項。
* 領袖可以「右鍵 → 開新分頁」同時開審批與內容。
* 搜尋引擎與列印（領袖想印進度表）自然可用。

遊戲層（圓環、路線圖、彩紙、音效）全部保留，改為「裝飾已經存在的頁面」。

### 請求的生命週期

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

### 模組

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

### 資料模型（與 Node 版完全相同）

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

### 遊戲層

* 圓環 (`ring-wrap`) 由 Jinja macro 直接輸出 SVG：沒有載入閃爍，JS 只負責由 0 動畫到目標值。
* 路線圖 (`quest-map`) 是純 HTML/CSS，節點狀態 done / current / locked 由 `progress_for` 決定。
* 彩紙 (`burst`)、音效 (`sfx`)、按壓 (`pressable`)、初次導覽 (`maybeShowTour`) 在 `effects.js`；
  導覽的「下一步」是**真的換頁**（`/badges`、`/`），所以每一頁都是正常網址。
* `prefers-reduced-motion` 之下所有動畫與粒子自動消失。

#### 會員章大冒險 (the adventure)

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

### 與 Node 版的分工

| | Node 版 | Python 版 |
|---|---|---|
| 前端 | SPA（`app.js` 畫畫面） | Jinja 伺服器渲染，每頁一網址 |
| 遊戲層 | `public/js/effects.js` | `static/js/effects.js`（同樣功能，無 import） |
| 資料 | local JSON / Google Sheets | 相同 |
| 密碼 | scrypt | 相同（雙向互通，`test_parity.py` 驗證） |
| 離線示範 | `demo-preview.html`（單檔） | 直接跑 `python3 -m flask --app app run` |

兩者可以同時使用，指向同一個 Google 試算表。

---

<a id="8-更新時資料會不會受影響--will-an-update-touch-the-data"></a>

## 8. 更新時，資料會不會受影響？ — Will an update touch the data?

<sub>來源 / source: `docs/06-safe-updates.md`</sub>

**答案：不會。** 這份文件說明為甚麼，以及每次更新前後你可以做的事。

---

### 一句話版本

> **資料住在 Google 試算表，程式住在 GitHub／Vercel。**
> 更新＝換掉「讀寫資料的程式」，不是換掉資料。試算表一直在原位，內容一格都不會被清空。

| 甚麼東西 | 放在哪裡 | 更新時會不會變 |
|---|---|---|
| 帳戶、密碼、童軍姓名／旅團／小隊 | 試算表 `users` 分頁 | 不會 |
| 進度、提交內容、審批記錄 | 試算表 `progress_records` | 不會 |
| 積分、兌換記錄 | 試算表 `points_ledger`、`redemptions` | 不會 |
| 獎章標題、任務／遊戲題目與答案、公告、獎勵 | 試算表 `badges`、`tasks`、`announcements`、`rewards` | 不會（你改過的就是你改的） |
| 畫面、遊戲、按鈕、流程 | GitHub → Vercel（程式碼） | **會換成新版本** |
| 遊戲的預設題目（原始稿） | 程式碼裡的 `content/` | 會換；但**試算表已有內容時不會覆蓋** |

---

### 我每次更新會遵守的四條規則

1. **只加不刪。** 新功能用新的分頁或新的欄位；不會重寫、不會搬動已有的列。
2. **目錄只建立一次。** 獎章與任務目錄只在「空白試算表第一次連上」時建立，
   之後任何部署、重啟都不會再寫入 —— 你在後台改過的標題、題目、正確答案全部保留。
3. **不做「清空再匯入」式更新。** 永遠不需要你把資料重新輸入一次。
4. **每批更新都附上自動測試。** `tests/test_redeploy_keeps_data.py` 會真的模擬
   「推送新版本 ＋ Vercel 重新部署」：建領袖、開童軍、完成任務、改標題與題目，
   然後用同一份試算表重新啟動，逐項確認資料與編輯一字不差、沒有重複列。

> **新增項目**（例如日後的新獎章或新遊戲）：下次開啟平台時會自動補上缺少的
> 那一項 —— 只新增、不覆寫；你在後台刪除過的項目不會自己回來。
> 每次啟動只會補「程式有、試算表沒有」的列，仍然不會動你已有的內容。

---

### 更新流程（照著做就好）

**更新之前**

1. 在專案資料夾跑一次存檔工具（**只讀，不會改動試算表**）：
   ```bash
   python3 tools/backup_sheet.py
   ```
   它會把所有分頁存成 `backups/sheet-<日期>-<時間>/`（每個分頁一個 CSV ＋ 一份完整 JSON ＋ 指紋）。
2. 或在 Google 試算表按 **檔案 → 建立副本**，多留一份線上備份（幾秒鐘）。

**更新之後**

3. 再跑一次 `python3 tools/backup_sheet.py`：它會列出每個分頁比上次**多／少幾列**，
   例如 `＋ progress_records：18 → 24 列`。用這個就知道更新有沒有意外動到資料。
4. 三個畫面各看一次：**領袖後台總覽**、**一位童軍的獎章頁**、**排行榜**。
5. 有問題就回報我；急的話你可以自己一分鐘回到舊版（見下）。

---

### 兩層免費保險（Google 自己就有）

- **版本記錄**：試算表內 **檔案 → 版本記錄 → 查看版本記錄**。
  每個時間點的內容都留著，可以隨時還原到任何一刻。這是對付「誤刪、誤覆蓋」最有效的一招。
- **建立副本**：**檔案 → 建立副本**，多一份完整線上備份。

### 程式出問題時的一鍵回頭（Vercel）

1. 打開 Vercel → 你的專案 → **Deployments**
2. 找到上一個正常的部署 → 右邊 **⋯ → Promote to Production**（或 Rollback）
3. 一分鐘內回到舊版本。**試算表完全不變**，資料照樣在。

所以「更新 → 不合意 → 回到舊版」不會損失任何資料，只損失那一分鐘。

---

### 甚麼情況才會動到資料？

| 情況 | 會不會動資料 |
|---|---|
| 我在後台改內容、開帳戶、審批 | 會 —— 這正是它應該做的事（寫入試算表） |
| 我推送新版本、Vercel 重新部署 | 不會 |
| 領袖改密碼、童軍完成遊戲 | 不會（只在原有分頁新增／更新該列） |
| 你明確要我「刪除某個帳戶／某項記錄」 | 會 —— 我會**先跟你確認、先備份**，才動手 |
| 其他任何情況 | 不會 |

### 我對你的承諾

- 不會有任何一次更新要求你「重設平台」或「重新輸入資料」。
- 不會有更新清空任何分頁。
- 每次更新的說明我都會寫明：**這次會不會碰到資料**（絕大多數是「不會」）。
- 如果我認為某個改動有機會影響資料，我會先告訴你風險與備份方法，等你同意才做。

---

### 給未來的自己：更新清單

- [ ] 更新前跑 `python3 tools/backup_sheet.py`（或建立副本）
- [ ] 推送新版本 → 等 Vercel 部署完成（網址不變）
- [ ] 更新後再跑一次存檔工具，看增減是否合理
- [ ] 走一次：領袖登入 → 童軍登入 → 開一個遊戲 → 排行榜
- [ ] 有異常：Vercel Rollback，再回頭查

---

### 不小心刪了內建的遊戲？（2026-10-17 新增）

領袖在 內容 頁按下垃圾桶把**石室（第 4 項）或渡口（第 5 項）**刪走的話，同一頁上方有一張
「🔧 修復遊戲與缺少的項目」卡：

| 按鈕 | 作用 | 會不會影響資料 |
|---|---|---|
| 🔧 還原內建遊戲（石室、渡口） | 清走「已刪除」記號、重建缺少的任務、重新接好第 1／2 區 | **只新增**；重建時會沿用舊記錄的 id，童軍已完成的記錄保留 |
| ↺ 還原所有內建項目 | 連其他獎章的示範任務（M01…、T-…）也一次帶回 | 同上；你自己建立的內容、自己改過的區域安排一律不動 |

- 卡上會直接寫出缺少了甚麼（例如「缺少任務 M05 · 第 2 區未接好」，或「M05 的內容被清空了」），齊全時顯示 ✓。
- **你自己按垃圾桶刪掉的任務不算「缺少」**：卡上只會一行列出「你已刪除 M07、M08…（不計入）」，旁邊顯示 14 / 14，並不會催你還原。只有「沒有刪除記錄卻不見了」（例如直接在試算表刪掉一行）或兩個內建遊戲（石室、渡口）不見了，才會出警告。
- 「內容被清空」是指任務列還在、但題目／設定空掉：修復只會填回**真的空了**的欄位，你改過的題目不會被覆蓋。
- 內建遊戲（M04、M05）與會員章本身**現在不能刪除**：要換走某一區的遊戲，請在該區改派另一項任務。
- 還原後按 F5 重新載入，第 1、2 區就會恢復原狀；已在該遊戲完成的童軍仍然是「已完成」。

---

### 壁畫與遊戲插圖，放在哪裡？（改圖改字不用碰試算表）

山洞的壁畫、教學牌與遊戲插圖，全部住在程式碼的 `content/member-badge/cave.json`
（文字）與 `static/img/quest/cave/`（圖片），**更新版本就會生效，不會動到試算表**。

| 想改 | 改哪裡 |
|---|---|
| 壁畫上的字（導言、時間線、資料欄、記憶提示） | `content/member-badge/cave.json` 的 `groups[n].wall` |
| 壁畫圖片 | 換掉 `static/img/quest/cave/wall-*.jpg`（同名即可） |
| 題目、選項、正確答案 | 領袖後台 → 🕯️ 編輯題目與答案（寫入試算表的 `tasks` 分頁） |
| 遊戲內的按鈕文字 | `content/member-badge/cave.json` 的 `labels` |

2026-10-17 的例子：旅巾由綠色改為紫色、兩邊綠紅條紋 —— 換了 `wall-group.jpg`、
改了壁畫三的文字，丙14 的選項與種子答案也一併更新（種子只在**首次建立**時寫入，
所以領袖已在平台改過的答案不會被覆蓋）。

---

### 山洞的成績怎樣算？（2026-10-17 起）

走出洞口時，成績以**百分比**顯示，不再只是「78 分」：

   78% — 50 題中第一次就答對 39 題
   全程共作答 87 次，其中 37 次答錯。上面的百分比只看第一次作答 —— 起初多錯幾題，百分比就會低一些。

- **百分比＝第一次作答就答對的題數 ÷ 50。** 答錯後重試、被死路送回壁畫再答，
  都**不會**把已錯的第一答改回正確；起初多錯幾題，最終百分比就低一些。
- **第二次數字**是全程作答次數與答錯次數（含重試）—— 想讓童軍知道「錯了 37 次」就看這裡。
- 進度記錄（試算表 `progress_records` 的 `score`）仍然保存第一次作答的百分比，
  領袖在後台看到的也一樣。
- 通關不受百分比影響：走完 50 題即完成第 4 項。

相關文件：`docs/02-google-sheets-setup.md`（試算表接線）、`docs/05-vercel.md`（部署與上線清單）。

---

### 遊戲 2（渡口）的考核與代碼（2026-10-18 起）

第 5 項（誓詞、規律、銘言）分**兩半**完成：

1. **過橋**：三關木板全部鋪好，紀錄為 `crossed`（已過橋）。這一步只證明次序排對了，
   **未算完成**：分數、徽章進度、「已完成」都不會出現。
2. **領袖考核 + 代碼**：童軍找領袖**背誦**銘言、誓詞、規律，並**講解**日常生活怎樣實行；
   通過後領袖交出一個代碼，童軍輸入後第 5 項才算完成（分數、點數、徽章進度在這一步一次過發放）。

- **代碼預設是 `82BP`**。想換代碼：在 `settings` 分頁加一行 key=`bridge_assess_code`、
  value 填新代碼（大小寫、空格、全形半形都不拘，`８２ｂｐ` 一樣有效）。
- 已過橋但未輸入代碼：地圖第 2 區顯示「🧭 已過橋 · 找領袖考核」，**行程可以繼續去遊戲 3**，
  代碼隨時補輸（遊戲內的代碼輸入卡、或「綱要參考」頁第 5 項的輸入框都可以）。
- 重新打開渡口遊戲會直接站在考核卡，不用重鋪三關。
- 考核卡的文字（要背甚麼、要講解甚麼）在 `content/member-badge/river.json` 的 `assess` 一節。

---

### 尋寶圖的光跟人走（2026-10-18 起）

地圖上**大張的亮卡（第一站）只會站在童軍的下一站**：完成了的站會退回普通小卡（打勾、變淡），
「▶ 下一站 · 你在這裡」的金框亮卡與童軍頭像會移到下一個要玩的遊戲。

- 未開始：第 1 區（山洞）是大卡「第一站 · 從這裡開始」——跟以前一樣。
- 完成 2 個遊戲後：第 1、2 區是打了勾的小卡，第 3 區是亮卡（附「▶ 下一站」），不會再停在山洞。
- 過了橋等代碼：亮卡一樣移到第 3 區，第 2 區顯示 🧭 與「輸入領袖代碼」的門。
- **地圖卡不再顯示遊戲簡介**（2026-10-18）：每個地點只剩編號、名稱、遊戲名與狀態，
  遊戲的內容走進去自然會知道。領袖在後台填的簡介仍會儲存（第 3–5 區將來用得着），
  只是地圖不再展示。

---

<a id="9-示範卡--demo-card"></a>

## 9. 示範卡 — Demo card

<sub>來源 / source: `DEMO.md`</sub>

### 開啟 / Open

- **實機 / Live preview:** Arena 的 **LIVE PREVIEW → Scout platform**（連接埠 5001）。直接複製預覽代理網址可能需要 Arena 的存取權杖；請由面板進入。
- **離線 / Offline:** 開啟 [`demo-preview.html`](demo-preview.html)。這是獨立檔案；不需要伺服器、網絡或 cookie。瀏覽器中可玩完整的第一個遊戲。
- **重新建立離線檔:** `python3 tools/offline_demo.py`。改完模板、圖像或本機山洞題目後請重新建立。

預覽 iframe 可能封鎖第三方 cookie。實機登入後會沿 `?sid=…` 帶着工作階段，所以在預覽內也可以跳頁；這是登入憑證，請不要轉寄含 `sid` 的網址。

### 登入 / Sign in

登入畫面是營地：**水獺 → 老虎 → 海鷗**三個小隊按鈕；右下角是低調的**領袖入口**。點隊名後選童軍名字。童軍**不能自行註冊**；第一次登入不用密碼，之後可自行設定密碼和電郵。

| 要示範的身分 | 方法 |
|---|---|
| 童軍 `demo2` | 登入頁 → 領袖入口 → 示範童軍；或走正常小隊／姓名登入（已設密碼的帳戶 `scout01`–`scout06`：`scout1234`） |
| 領袖 `demo1` | 登入頁右下角 → 只輸入代碼 **`0082`**；可由領袖登入卡選示範領袖 |
| 首次登入童軍 `demo3` | 選海鷗小隊 → 吳卓穎；不需要密碼，但**必須**填寫新密碼 + 電郵（兩項齊備才可進入平台；離線檔同樣擋下，且不會保留你輸入的密碼） |

示範帳戶只在**示範部署**出現：本機要加 `DEMO_LOGIN=true SEED_DEMO=true`，離線檔已內建；正式上線（Vercel）兩者都關上，第一次開啟會顯示「建立第一位領袖」，帳戶全部由領袖建立（見 `docs/05-vercel.md`）。伺服器的 `/login/demo/demo1`、`…/demo2` 和 `…/demo3` 是 **POST** 捷徑，不能直接貼進地址列。離線檔的示範按鈕可以直接點；實機版使用上表入口。英文可在語言切換鍵或 `/set-language/en` 選擇。

### 童軍三分鐘路線 / Scout walkthrough

1. 主頁只見問候（日行一善與公告）、五個彩色進度性獎章方格和最多四則建議，按「顯示全部」可展開。**主頁沒有積分卡**；餘額只在「獎勵」。
2. 按 **會員章**。唯一的入口頁標題是 **「你被困住了！」**：在荒島上走過五個區域，路線末端是沙灘與木筏。從主頁方格或獎章總覽進入，都到同一頁。**第一區 · 叢林深處**的地圖標記上直接寫明 **遊戲 1 · 童軍歷史山洞**的玩法，不必選位置或查看下方說明面板。頁面最下方只有**一個開始歷險按鈕**，一按就進入山洞，沒有「划出去」或第二次「開始遊戲」。開啟地圖或進入山洞都不會暗中完成任務。
3. 第一區**沒有其他任務**；原來「4. 童軍大考驗」由山洞遊戲取代，**沒有第二份試卷**。會員章頁面不再顯示「童軍綱要參考」入口。
4. 畫面分兩層：**上面是圖，下面的文字卡放在圖的下方**，任何訊息（壁畫時間線、死路提示、回頭故事、錯題檢討）都不會蓋住圖畫；圖畫完整顯示，不會被裁走。長文字在下方自己捲動：**遊戲框開到最大**：框佔整個畫面（`min(62rem, 100dvh − 6.5rem)`，遊戲頁只保留品牌列、分頁、語言鍵與麵包屑，自動收起童軍姓名那一行），圖畫跟着框放大；文字排在图畫下方，字太長時**在框內的文字區向下捲動**，底部淡出並顯示「▾ 向下捲動」，捲到最後一行提示消失，右側另有可見捲軸；每次轉場回到該卡的開頭。手機版框自動變成整頁捲動。依次看四幅壁畫與可讀的時間線，進石室逐題選路；錯路會顯示圖片與史實補充，卡片下方同時顯示**火把還可以錯幾次**。同一段錯足**三次**，就會有一個故事把你送回這一幅壁畫（火把熄了、走錯路繞回原處、洞裡太悶昏倒、太累要休息、碎石封路、筆記留在壁畫前；每次抽一個，六段故事輪着來），這一組要由第一題重新答，之前答錯的題仍照樣計分。全程 50 題，每題 2 分；**走到洞口即自動通關，無論得分多少，毋須再次提交或重玩**。分數按第一次選擇計算，只供檢討錯題；離線檔也會按你實際選的答案計分，而非預設分數。**途中按頁首「主頁」、「會員章」或其他離開入口會先顯示提示**：可繼續遊戲而保留本次作答，或確認離開；離開後再進入須由頭開始。實機版於作答期間也會用瀏覽器的通用提示補足返回、重新整理及關閉分頁。
網上正式網站（Vercel）：見 `docs/05-vercel.md`。正式站沒有示範帳戶 —— 第一次開啟會顯示「建立第一位領袖」，之後由領袖建立童軍帳戶；想示範給人看，用本檔的離線檔 `demo-preview.html`。

5. 洞口結果卡的**第一顆按鈕**是「🎮 繼續歷程 · 進入遊戲 2（迷霧渡口）」：一按即接上第 2 區的渡口；「再玩一次山洞」改為次要按鈕。通關後離開山洞**不再提示**（提示只留給未走完的行程）；已完成的第 1 區在地圖上保留一個小門「🎮 再玩一次」，可隨時重玩遊戲 1，不影響已完成記錄。
6. 通關返回地圖時顯示 **1 / 5 個遊戲已完成**。此後再玩**由遊戲 2 開始**（地圖底部單一按鈕變為「🎮 繼續歷險 · 進入遊戲 2」），第 1 區仍可自行重玩。第 2–5 區各有一個遊戲位置，但領袖尚未提供內容，現時顯示「即將推出」且不會自動完成。**五個不同遊戲全部通關才頒發會員章**，之後才解鎖下一枚獎章。
7. 頁首的 **🏠 主頁** 在離線和實機畫面均可返回。其餘四個獎章維持彩色圖示與鎖定標記；龍虎榜按獎章／任務排序，不按積分排序。

> **綱要資料仍然保留，但不在遊戲頁面提供入口。** 實機版已知的 `/badges/<id>/requirements` 網址仍可打開既有的 11 條說明與資源，供學習、領袖核實及日後校對；它們不算另外 11 個通關條件。領袖文件列出的是第 1–10 項，正式文案與後續四個遊戲應以領袖提供的內容為準。第 4 項的舊 Google 表單不再用於本遊戲；其他參考資源依原頁保留。

### 領袖手動改山洞題目 / Edit game 1 questions

這個功能須用**實機版**，離線檔的領袖畫面只供點按示範，不能儲存修改。

1. 以 `demo1` 登入領袖入口（代碼 `0082`）→ **內容** → **會員章** → **第 4 項 M04** → **🕯️ 編輯山洞題目與答案**；亦可從會員章任務清單的 🕯️ 按鈕直達。
2. 從四面壁畫的題目清單選一題，修改中文／英文問題及選項，按圓點選正確答案；最後檢查中文／英文**錯路溫習提示**並按 **💾 儲存這一題**。前三個中文選項必填；第四個可留空。請勿更改題號、四組順序，或改用一般小測驗文字框貼上整份題庫。
3. 新開始的遊戲使用改後版本；已完成的童軍紀錄不會重設。有人玩到一半時，該局依入洞時看到的版本計分。以 `demo2` 試玩，檢查新題目、選項、錯路及答案；史實若改變，亦應請維護者核對教學壁畫。
4. 若實機使用本機 `data/db/tasks.json`，修改後在專案目錄執行 `python3 tools/offline_demo.py`，才會把相同 50 題號的本機題庫複製到新的 `demo-preview.html`。**離線檔不會即時同步，也不會複製帳戶／成績。** Google Sheets 資料目前不會自動匯入離線產生器。

**English:** Leader → Content → Member Badge → M04 → **Edit cave questions & answers**. Choose one of the 50 questions; edit its bilingual prompts and choices, select the correct answer, revise the dead-end recap, then save. Existing progress is safe; rebuild the offline HTML after local-data edits.

### 領袖準備遊戲 2–5 / Leader setup

在實機版進入 **領袖 → 內容 → 會員章**：

1. 先按「在此獎章加入任務」，填入中文、英文標題與內容，在任務編輯器輸入實際題目或清單，檢查後發佈。平台會自動產生唯一任務代號。
2. 開啟 **🎮 五區遊戲設定**；第一區山洞固定為遊戲 1，但五個區域的中英文名稱可改。逐區把一項**新建、已發佈、有內容的任務**指派給遊戲 2–5，並補上雙語遊戲簡介。
3. 未指派的區域仍然鎖住；第 1–11 項原有的綱要任務不能冒充遊戲 2–5；同一任務也不能佔多個遊戲位置。已有童軍作答的普通任務不能倒過來當作一個全新的遊戲，以免自動通關。
4. 領袖仍可在後台開設童軍、編輯其他獎章／公告／獎品、審批待核實提交；**核實綱要項目不會直接頒發會員章**，會員章只看五個遊戲。

後四個遊戲的名稱、題目與玩法尚待領袖提供，現階段**不會猜造內容**。結構已備妥；若新遊戲需要獨特玩法而非現有任務類型，可在取得要求後擴充。

### 離線範圍 / Offline scope

想看**只有遊戲 2** 的畫面，開 `bridge-preview.html`（由 `python3 tools/bridge_preview.py` 產生）：一個檔案、遊戲即開，三關鋪好會有通關卡。完整故事與遊戲 2 都在 `demo-preview.html`。

`demo-preview.html` 有 **14 個內嵌畫面**（新增第一次登入的必填表單），內嵌圖像與腳本，不會抓外部資源，亦不含任何工作階段憑證。遊戲 1 的 50 題、錯路、離開提示、實際計分、錯題檢討及 1/5 地圖進度可離線操作，之後按一顆按鈕接著玩**遊戲 2 · 迷霧渡口**（三關木板次序：教學牌給原文與說明 —— 銘言、誓詞、規律一字一句照著讀，每句之下有一行說明，鋪木板時空格按句子排成一行，木板切到單詞共 39 塊，四塊一樣的「對」、七塊一樣的「童軍」可以互換），過橋後地圖走到 2/5，而第 1、2 區各自留下「🎮 再玩一次」小門可重玩；領袖代碼卡與領袖首頁可預覽。新增帳戶、編輯題目、儲存伺服器積分和跨裝置同步須使用實機版。

### 驗證 / Checks

```bash
python3 -m pytest -q
LD_LIBRARY_PATH=/tmp/syslibs python3 tools/checks/check_offline.py
LD_LIBRARY_PATH=/tmp/syslibs python3 tools/checks/check_cave.py --fast
LD_LIBRARY_PATH=/tmp/syslibs python3 tools/checks/check_bridge.py
LD_LIBRARY_PATH=/tmp/syslibs python3 tools/checks/check_cave_editor.py --fast
LD_LIBRARY_PATH=/tmp/syslibs python3 tools/checks/check_exit.py
```

已存在的本機示範資料可以跑 `DATA_DIR=./data SEED_DEMO=false python3 tools/migrate_member_five_games.py` 更新五遊戲設定及山洞的舊預設合格文案；腳本不刪帳戶、進度或積分，已完成的第 4 項仍計作遊戲 1。

獎章圖片源自香港童軍總會《童軍訓練綱要》：<https://scoutsinfohub.org.hk/scout-training-scheme>。

---
