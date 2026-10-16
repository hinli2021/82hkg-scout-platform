# Google 試算表儲存：令所有人、所有裝置共用同一份資料

目標：**你的 Google 試算表就是資料庫**，相片存在你的 Google Drive 資料夾。
童軍在家用電話、在集會用平板、領袖在電腦登入，看到的都是同一份進度；
Vercel 重新部署、執行個體被回收，資料都不會消失。

> 已經有 Node 版用的試算表？不用重建。填同一個 Sheet ID 即可 ——
> 分頁、欄位、密碼格式完全相容。

**次序**：①②③ 在 Google 做，④ 在 Vercel 做，⑤ 回來這頁檢查。

---

## ① 建立試算表（1 分鐘）

1. 到 <https://sheets.new> 建立新試算表。
2. 命名為例如「童軍進度平台 2026」。
3. 從網址複製 ID：
   `https://docs.google.com/spreadsheets/d/`**`1AbC…xyz`**`/edit`
   → 這就是 `GOOGLE_SHEET_ID`。
4. **分頁不用自己建立** —— 程式首次連上時會自動建立 15 個分頁與標題列。

## ② 建立服務帳戶與金鑰（3 分鐘，只需一次）

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

## ③ 分享給「機械人」電郵（最容易漏的一步）

| 分享甚麼 | 給誰 | 權限 |
|---|---|---|
| 你的**試算表**（按「共用」） | 上一步的服務帳戶電郵 | **編輯者** |
| Drive 的**相片資料夾**（可選） | 同上 | **編輯者** |

就像分享文件給同事，只是對象是一個機械人電郵；**不是**分享給自己。
權限一定要「編輯者」，只給「檢視者」會在第一次寫入時失敗（403）。

相片資料夾：在 Drive 建立例如「童軍進度平台 — 相片」，共用給同一電郵，
然後從網址複製 `https://drive.google.com/drive/folders/`**`1XyZ…`** → 這是
`GOOGLE_DRIVE_FOLDER_ID`。不設定也可以，相片會放在服務帳戶自己的 Drive。

## ④ 在 Vercel 加入環境變數（3 分鐘）

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

## ⑤ 檢查接通了沒有

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

## 之後會是怎樣

- 童軍在任何裝置登入 → 讀寫的都是同一份試算表；換電話、換電腦進度都不會不見。
- 領袖後台改內容、開帳戶、審批 → 直接寫入試算表；同步到所有裝置。
- 每次部署新版本（`tools/push.sh`）**不會**影響資料：資料在試算表，不在 Vercel。

## 推送新版本會不會洗掉資料？（答案：不會）

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

## 常見問題

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

## 本機測試（不用 Vercel）

```bash
export DATA_DRIVER=sheets
export GOOGLE_SHEET_ID=1AbC…xyz
export GOOGLE_SERVICE_ACCOUNT_FILE=./service-account.json
export SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))")
python3 -m flask --app app run --host 0.0.0.0 --port 5001
```

## 免費額度

Sheets API 對小型旅團（數十位童軍、每天數百次讀寫）遠遠用不完；
讀取有 15 秒快取，寫入是定點更新，不會重寫整個分頁。

## 貼上金鑰之前，先驗一次

用瀏覽器打開 `tools/check-service-account.html`，貼上 JSON 內容按「檢查」：
它會告訴你金鑰是否有效、`client_email` 要共用給哪個電郵，並指出最常見的三個貼上錯誤
（只複製一部分、貼了檔案路徑、複製時 `\n` 變成真換行）。
工具只在你的瀏覽器內運作，不會上傳任何內容。

> 程式現在也會自行處理兩種情況：整段值被引號包住，以及 `private_key` 裡的 `\n`
> 變成真換行。其餘錯誤會在 `/health` 與領袖後台 → 設定 直接寫出原因與做法。
