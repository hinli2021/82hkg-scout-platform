# 童軍進度平台 — Python 版 (Flask + Jinja)

Scout Progress Platform — the **Python edition**. Flask renders the scout and
leader pages; the interactive cave uses JavaScript. Scouts explore an island,
leaders manage content and accounts. The app supports local JSON or Google Sheets
storage and includes a one-file offline walkthrough.

> **童軍版**：童軍登入 → 看進度 → 玩任務 → 考取進度性獎章 → 儲積分換獎品。
> **領袖版**：編輯獎章與任務、開設童軍帳戶、審批提交、發公告、管理獎品。

---

## 文件：一份合訂本 + 一個打包 / the docs, compiled and packed

全部說明文件（README、LAUNCH、DEMO、docs/01–06）已合併成單一檔案
**`docs/ALL-DOCS.md`** —— 有目錄、可整份閱讀或列印。改過任何一份之後：

    python3 tools/compile_docs.py      # 重新合併 → docs/ALL-DOCS.md

要把整個平台（程式、內容、文件、截圖、原稿）收成一個檔案保存或交收：

    python3 tools/pack_release.py      # → ../deliverables/82hkg-platform-<日期>.zip

打包不含 `.git`（歷史在 GitHub）、離線示範 HTML（可用 `tools/offline_demo.py`
重新產生）與執行時資料；包內有 `MANIFEST.txt` 逐項列出內容。

---

## 離線示範 / the offline demo — `demo-preview.html`

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

## 1. 快速開始 (Quick start)

```bash
cd scout-platform-py
pip install flask                 # 只有這一個必要套件
python3 -m flask --app app run --host 0.0.0.0 --port 5001
```

Open <http://localhost:5001>. A brand-new install seeds sample content so every
screen is populated — replace it with your own in *Content*.

### 示範登入 (demo sign-in — no passwords to type)

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

## 2. 兩種儲存方式 (two storage modes)

| `DATA_DRIVER` | 資料 | 相片 | 適合 |
|---|---|---|---|
| `local` (預設) | `./data/db/*.json` | `./data/uploads/` | 試用、單機、離線 |
| `sheets` | 你的 Google 試算表（一個分頁一個資料表） | 你的 Google Drive 資料夾 | 正式使用，免費，多人即時共用 |

設定 Google 試算表：見 [`docs/02-google-sheets-setup.md`](docs/02-google-sheets-setup.md)。

**與 Node 版共用同一份試算表**：分頁名稱、欄位名稱、JSON 儲存格格式、密碼雜湊
（scrypt, n=2¹⁴, r=8, p=1, dklen=64, hex）全部一致 — 兩邊都可以讀寫同一個檔案，
帳戶與進度互通（已用測試驗證）。

---

## 3. 畫面一覽 (what's where)

### 童軍 (scout)
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

### 領袖 (leader)
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

## 4. 規則 (the rules, in one place)

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

## 4b. 會員章 = 五個遊戲（每個區域一個）

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

## 4c. 領袖逐題修改山洞 / Edit cave questions as a leader

1. 在**實機版**登入領袖帳戶（示範帳戶 `demo1`：登入頁右下方**領袖入口**，代碼 `0082`），打開 **領袖 → 內容 → 會員章 → 第 4 項 M04 → 🕯️ 編輯山洞題目與答案**。在會員章的任務清單也可直接按「🕯️ 編輯題目與答案」。童軍帳戶及離線 HTML 不能儲存編輯。
2. 以左方四面壁畫的清單選擇一題。修改**中、英文題目**、3–4 個選項，按選項旁的圓點指定**唯一正確答案**，並更新**錯路溫習提示**。前三個中文選項必填、第四個可留空；英文選項留空時暫以中文顯示，但建議填妥譯文。請同時核對選項、答案、溫習提示與壁畫史實。
3. 按 **💾 儲存這一題**，然後以童軍示範帳戶試玩。每次只改一題，**50 個題號、分組、順序及既有進度均保留**；不需要另一份 80 分試卷。正在玩的童軍仍會按其進洞時看到的題目答案計分；新開始的一局才使用更改後的版本。後台**操作紀錄**會記錄修改。
4. 切勿把一般測驗內容貼入 M04 的任務編輯欄位，或直接在 `data/db/tasks.json` 調換題號／次序：兩者會破壞四面壁畫與題目的關聯；M04 的普通測驗提交已被封鎖。如要修改壁畫及時間線，應由維護者一併校對 `content/member-badge/cave.json`，那不是這個逐題表單的一部分。

**離線版與實機版不同步。** 實機修改寫入當前資料庫；`demo-preview.html` 是獨立的靜態示範，不能在檔內編輯。若實機使用本專案的**本機 JSON 資料夾**，在專案目錄執行 `python3 tools/offline_demo.py` 後，產生器會在題號／順序一致時，把本機 M04 的 50 題複製進新離線檔；童軍帳戶、進度及積分**不會複製**。若實機使用 Google Sheets，產生器不會自行連接雲端表格；需另備本機題庫來源才能帶入修改。`content/member-badge/item4-question-bank.json` 等是新資料的種子，不會覆蓋已儲存的實機修改。

**English:** Sign in as a leader → Content → Member Badge → M04 → **Edit cave questions & answers**. Pick a question from its wall, edit both prompts and the choices, mark the correct choice, update the wrong-turn recap, and save. IDs/groups remain fixed; previous progress is untouched and an open run is graded against the version it loaded. Rebuild the offline HTML after **local** database edits; Google Sheets content is not imported automatically.

## 5. 遊戲層 (the game feel)

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

## 6. 專案結構 (project layout)

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

## 7. 測試 (tests)

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

## 8. 環境變數 (environment)

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

## 9. 起步次序 (recommended order for a real unit)

1. **設定** → 單位名稱、小隊（Tiger / Otter / Seagull → 改成你們的名字）、功能開關。
2. **內容** → 保留五枚進度性獎章並修改文字；在會員章下新增任務，內容完備後透過「五區遊戲設定」逐一掛到區域 2–5。不要把綱要參考任務當成額外通關條件。
3. **帳戶** → 逐一開設童軍（或用 CSV 匯入）。把名字告訴他們：他們按名字就可以進入，
   但**第一次必須**自行設定密碼和填寫電郵，才會見到主頁。領袖若填了初始密碼，
   該童軍登入後仍要設定個人密碼及電郵（初始密碼隨即失效）。
4. 把連結發給童軍，示範帳戶 `demo2` 可演示遊戲 1 與遊戲 2；其餘遊戲等內容提供後才開放。
5. 集會後到 **審批** 處理相片／反思／簽核。
6. 獎品備妥後，在 **設定** 打開換領，才在 `/rewards` 出現「換領」按鈕。

---

## 10. 出處 (credit)

獎章圖片取自香港童軍總會《童軍訓練綱要》
<https://scoutsinfohub.org.hk/scout-training-scheme>，供本旅團內部使用。
- **更新平台前後**：[`docs/06-safe-updates.md`](docs/06-safe-updates.md) —— 推送新版本不會動到試算表資料，附存檔工具 `tools/backup_sheet.py`。
- **正式上線步驟**：[`LAUNCH.md`](LAUNCH.md) —— 由開 Google 試算表到第一位領袖登入，一步步跟著做。
