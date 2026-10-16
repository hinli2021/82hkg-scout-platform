# Google 試算表 + Drive 設定（免費）

目標：**你的 Google 試算表就是資料庫**，相片存在你的 Google Drive 資料夾裡。
沒有付費服務、沒有外部資料庫，資料一直在你自己的 Google 帳戶內。

> 已經有 Node 版用的試算表？不用重建。把同一個 Sheet ID 填入 Python 版即可 —
> 分頁、欄位、密碼格式完全相容。

---

## 1. 建立試算表

1. 到 <https://sheets.new> 建立新試算表。
2. 命名為例如「童軍進度平台 2026」。
3. 從網址複製 ID：
   `https://docs.google.com/spreadsheets/d/`**`1AbC…xyz`**`/edit`
4. 分頁**不用自己建立** — 首次啟動時程式會自動建立 15 個分頁與標題列。

## 2. 建立服務帳戶 (service account)

1. 到 <https://console.cloud.google.com/> → 建立新專案（例如 `scout-platform`）。
2. **API 和服務** → **程式庫** → 啟用兩個 API：
   * **Google Sheets API**
   * **Google Drive API**
3. **IAM 與管理** → **服務帳戶** → **建立服務帳戶**
   * 名稱：`scout-platform`
   * 角色：可留空（權限由「分享」決定）
4. 建立後 → **金鑰** → **新增金鑰** → **JSON** → 下載。
5. 把檔案放到專案內，改名為 `service-account.json`（**不要**上載到 GitHub）。
6. 服務帳戶電郵看起來像：
   `scout-platform@你的專案.iam.gserviceaccount.com`

## 3. 分享（最重要的一步）

| 分享甚麼 | 給誰 | 權限 |
|---|---|---|
| 你的試算表 | 服務帳戶電郵 | **編輯者** |
| Drive 相片資料夾 | 服務帳戶電郵 | **編輯者** |

就像分享文件給同事一樣，只是對象是那個機械人電郵。

## 4. 相片資料夾（可選但建議）

1. 在 Drive 建立資料夾，例如「童軍進度平台 — 相片」。
2. 分享給服務帳戶電郵（編輯者）。
3. 從網址複製資料夾 ID：`https://drive.google.com/drive/folders/`**`1XyZ…`**

沒有設定資料夾也可以：相片會放到服務帳戶自己的 Drive 根目錄。

## 5. 啟動

```bash
export DATA_DRIVER=sheets
export GOOGLE_SHEET_ID=1AbC…xyz
export GOOGLE_DRIVE_FOLDER_ID=1XyZ…       # 可選
export GOOGLE_SERVICE_ACCOUNT_FILE=./service-account.json
export SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))")
python3 -m flask --app app run --host 0.0.0.0 --port 5001
```

首次啟動會：
1. 建立缺少的分頁（`users`、`badges`、`tasks`… 共 15 個）並寫入標題列。
2. 由於沒有任何領袖帳戶，寫入示範內容（可用 `SEED_DEMO=false` 停用）。

檢查：到 `/leader/settings`，應該顯示 **Storage: sheets**；在試算表的分頁裡即時看到資料。

## 6. 常見問題

| 情況 | 原因 / 解法 |
|---|---|
| `Google API POST … → 403` | 未分享試算表給服務帳戶電郵 |
| `GOOGLE_SHEET_ID is required` | 環境變數未設定或打錯 |
| 相片連結打不開 | 未分享 Drive 資料夾；程式會嘗試設為「知道連結者可檢視」 |
| 讀取慢 | 讀取有 15 秒快取；寫入是定點更新，不會重寫整個分頁 |
| 想搬回本機 | `DATA_DRIVER=local`，資料就寫到 `./data/db/*.json` |
| 想由本機轉上雲端 | 把 `data/db/*.json` 的內容貼到對應分頁（欄位相同），第一列放欄位名稱 |

## 7. 免費額度

Sheets API 對小型旅團（數十位童軍、每天數百次讀寫）遠遠用不完；
上載到 Drive 也只需一般免費 15 GB 空間。相片在寫入前已在瀏覽器壓縮。
