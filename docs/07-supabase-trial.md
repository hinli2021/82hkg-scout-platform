# Supabase 試用：先複製資料，試好才決定是否轉用

目標：**先把現有資料複製一份到 Supabase 試用，正式站繼續使用 Google 試算表。**
試用站和正式站使用不同的環境變數，所以試用不會影響童軍正在使用的正式站。

## ① 建立 Supabase 專案

1. 到 <https://supabase.com> 登入，按「New project」。
2. 名稱可填 `82hkg-scout`；自行設定資料庫密碼並妥善保存；地區選 Singapore；計劃選 Free。
3. 等待專案建立完成，到 **Project Settings → API** 查看：
   - **Project URL**（例如 `https://xxxxx.supabase.co`）
   - **service_role** 金鑰（按 reveal 才顯示）

> ⚠️ service_role 金鑰等同管理員密碼。不要把它放進 git、文件或聊天；只可以放進伺服器的環境變數。

## ② 建立資料表

1. 在 Supabase 左邊選單開 **SQL Editor**。
2. 把 `tools/supabase_schema.sql` 整份貼上，按 **Run** 一次。
3. 這會建立 19 張資料表和一個名為 `uploads` 的檔案儲存桶。每張表的資料以 JSONB 保存，平台日後新增欄位時不用再改資料表。

## ③ 複製現有資料，並產生 JSON 備份檔

在專案根目錄執行（來源沿用正式站的試算表設定，金鑰不要存進任何檔案）：

```bash
DATA_DRIVER=sheets GOOGLE_SHEET_ID=<試算表 ID> GOOGLE_SERVICE_ACCOUNT_JSON=<服務帳戶 JSON> \
SUPABASE_URL=https://<專案>.supabase.co \
SUPABASE_SERVICE_ROLE_KEY=<service_role 金鑰> \
python3 tools/copy_to_supabase.py
```

工具會逐一列出每個分頁複製了多少列，並在目前目錄寫下一份
`backup-supabase-<日期時間>.json`。重複執行是安全的：同一列只會更新，不會重複。
加 `--dry-run` 可以只產生 JSON 備份檔，不寫入 Supabase。

## ④ 用 Supabase 開一個試用站

在 Vercel 為試用部署（Preview）設定以下環境變數，正式站（Production）不要改：

```
DATA_DRIVER=supabase
SUPABASE_URL=https://<專案>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service_role 金鑰>
```

重新部署後，先開 `/health`：`storage` 應顯示 `supabase`。
再到領袖後台「設定 → 設定檢查」，「資料儲存在 Supabase」應為完成。
試用時請用測試帳戶登入、完成一個任務、開一個卡包，確認資料在
Supabase 的 **Table Editor** 即時出現。

## English summary

Goal: trial Supabase with a copy of the live data while production stays on
Google Sheets. Create a Supabase project (region: Singapore, Free plan), run
`tools/supabase_schema.sql` once in the SQL Editor, copy the data with
`tools/copy_to_supabase.py` (it also writes a `backup-supabase-*.json` file),
then set `DATA_DRIVER=supabase`, `SUPABASE_URL` and
`SUPABASE_SERVICE_ROLE_KEY` on a **Preview** deployment only. Check `/health`
shows `"storage": "supabase"` and the leader setup check passes. Never commit
or share the service_role key — it belongs only in server environment
variables.
