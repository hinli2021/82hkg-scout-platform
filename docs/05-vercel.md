# 正式上線（Vercel + GitHub）

正式版的流程：在這裡改東西 → 推送 GitHub（`tools/push.sh`）→ Vercel 自動重新建置 →
童軍打開網址就可以用。**資料不在 Vercel 上**，資料在 Google 試算表（見第 4 節），
Vercel 只是跑程式的地方。

---

## 1. 首次部署（瀏覽器做一次，約 5 分鐘）

1. **Vercel**：<https://vercel.com> → **Continue with GitHub**（`hinli2021`）登入 →
   **Add New… → Project → Import** 選 `82hkg-scout-platform`。
   - 私人 repository 要按 *Configure GitHub App* 授權 Vercel 讀取它。
   - **Framework Preset**：`Other`；**Build／Output Directory 留空**（`vercel.json` 已寫好）。
2. **Environment Variables**（Settings → Environment Variables，Production 與 Preview 都勾）見第 3 節。
3. **Deploy**。完成後會有網址，例如 `https://82hkg-scout-platform.vercel.app`。
   （可以再綁自己的網域：Settings → Domains。）

## 2. 第一次開啟平台：建立第一位領袖

正式版**沒有示範帳戶**。第一次打開網址，平台會直接顯示 **「建立第一位領袖」**：

1. 填單位名稱（中文必需，英文可留空）、領袖姓名（中文必需）、登入帳號、密碼（至少 6 個字）。
2. 按「建立領袖帳戶，開始使用」→ 直接進入**領袖後台**，並且已登入。
3. 之後這一頁自動收起，任何人再到網址就只看到登入頁。

> 領袖登入：登入頁右下角**領袖入口** → 在「領袖代碼」一欄輸入**你自己設定的密碼**。
> （示範帳戶的 `0082` 只屬於離線試玩檔與示範部署。）

**接著在領袖後台建立童軍帳戶**：領袖 → 帳戶 → 新增（選擇小隊、姓名、設定密碼）。
童軍第一次登入會看到「建立密碼／填電郵」的設定頁，之後就可以玩。

## 3. 環境變數

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

## 4. 資料放在 Google 試算表（正式版的資料庫）

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

## 5. 每次更新的流程

```bash
cd scout-platform-py
GITHUB_TOKEN=github_pat_xxx bash tools/push.sh "這次改了甚麼"
```

推送 `main` 之後，Vercel 約 30–60 秒自動建置新版本（Deployments 頁可看進度）。
Token 只需要這個 repository 的 **Contents: Read and write**，用完可以即時撤銷。

## 6. 上線前檢查清單

- [ ] repository 已設為 **Private**（GitHub → Settings → General → 最底 Danger Zone）
- [ ] Vercel 已加 `SESSION_SECRET`、`GOOGLE_SHEET_ID`、`GOOGLE_SERVICE_ACCOUNT_JSON`
- [ ] 已建立第一位領袖，並且用領袖代碼登入過一次
- [ ] 領袖後台 → 設定，**沒有**看到「資料暫存中」警告
- [ ] 已建立至少一個童軍帳戶，實際玩過遊戲 1 與遊戲 2
- [ ] 領袖後台 → 設定 → SMTP，用「試寄一封」確認找回密碼的郵件真的出得去（`docs/03-email-setup.md`）
- [ ] 已把網址發給童軍（可連同 `demo-preview.html` 離線檔一起）

## 7. 疑難排解

| 情況 | 處理 |
| --- | --- |
| 網站 500（Function Error） | Vercel → Project → Logs 看 `api/index` 的訊息；最常見是 `templates/`、`content/` 沒有被 `includeFiles` 帶上，或 Google 金鑰貼錯 |
| 玩了很久之後回到登入頁 | 執行個體被回收、資料回到示範狀態 → 未接上試算表；按第 4 節設定 |
| 童軍上載相片失敗 | 未設 `GOOGLE_DRIVE_FOLDER_ID`，或資料夾未共用給服務帳戶 |
| 忘記領袖密碼 | 有電郵的帳戶可用「忘記密碼」；否則在另一個已登入的領袖帳戶 → 帳戶 → 重設密碼 |
| 想換網址 | Settings → Domains 綁自己的網域；更新後記得在領袖設定填回正確網址 |

## 上線之後：推送新版本安全嗎？

安全。資料在 Google 試算表，不在程式碼裡；新版本只會讀取，不會覆寫。

- 目錄（獎章／任務）只在**空試算表第一次連上**時建立一次，之後永不重寫。
- 領袖改過的任何內容、童軍的進度與積分，全部留在試算表，Redeploy 後照樣在。
- 自動測試 `tests/test_redeploy_keeps_data.py` 已模擬「推送＋重新部署」整段流程並通過。
- 詳見 `docs/02-google-sheets-setup.md`「推送新版本會不會洗掉資料？」。
- 完整的安全更新流程（更新前備份、更新後比對、一鍵回舊版）：`docs/06-safe-updates.md`；
  存檔工具：`python3 tools/backup_sheet.py`（只讀試算表，存到 `backups/`）。

