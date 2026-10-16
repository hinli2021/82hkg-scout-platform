# 把 GitHub 接到 Vercel，開一個測試站

Vercel 會**看着這個 GitHub repository**：每次 `main` 有新提交，它就自動重新建置一個新版本。
所以流程是 —— 在這裡改東西 → 推送 GitHub（`tools/push.sh`）→ Vercel 幾十秒後就是新版本，
直接在手機或電腦打開網址就可以試。

## 第一次設定（在瀏覽器做一次，約三分鐘）

1. 開 **https://vercel.com** → **Continue with GitHub** → 用 **hinli2021** 登入。
2. **Add New… → Project → Import Git Repository** → 選 **`82hkg-scout-platform`**。
   - 私人 repository 要按 **Adjust GitHub App Permissions / Configure** 授權 Vercel 讀取它。
3. 設定頁面：
   - **Framework Preset**：`Other`
   - **Root Directory**：`./`（不改）
   - **Build Command / Output Directory**：**留空** —— `vercel.json` 已經寫好
     （靜態檔由 `public/` 供應，其餘全部交給 `api/index.py` 的 Flask 應用）。
4. **Environment Variables** 加入（見下一節）。
5. 按 **Deploy**。完成後網址會像 `https://82hkg-scout-platform.vercel.app`。

## 環境變數（Settings → Environment Variables）

| 名稱 | 值 | 為甚麼 |
| --- | --- | --- |
| `SESSION_SECRET` | 一段長隨機字串（例如 32 個字母數字） | 沒有它，程式每次啟動都會換鎖匙，登入與遊戲進度會在中途失效 |
| `DEMO_LOGIN` | `true` | 讓 `/login/demo/demo1`（領袖）、`demo2`（童軍）一按即登入，方便測試 |
| `SEED_DEMO` | `true` | 每次都建立示範領袖與七個示範童軍 |
| `DATA_DIR` | `/tmp/scout-platform-data` | Vercel 只有 `/tmp` 可以寫入（見下方「資料會否保存」） |

改了環境變數要 **Redeploy** 一次（Deployments → … → Redeploy）才會生效。

## 資料會否保存？

**預設（本機 JSON 驅動）**：不會。Vercel 的檔案系統是唯讀的，只有 `/tmp` 可以寫；
`/tmp` 是每個執行個體自己的，一段時間沒有流量就會被回收，之後示範資料會重新建立。
用來「打開看看、玩一局、試領袖後台」完全足夠，但不適合給多位童軍同時長期使用。

**要真正保存進度**：讓平台把資料寫進 Google 試算表（這個專案本來就支援）：

| 名稱 | 值 |
| --- | --- |
| `DATA_DRIVER` | `sheets` |
| `GOOGLE_SHEET_ID` | 試算表 ID（網址中 `/d/` 之後那一段） |
| `GOOGLE_DRIVE_FOLDER_ID` | 放童軍證據相片的雲端硬碟資料夾 ID（可留空） |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 服務帳戶金鑰的**整段 JSON**（貼在值欄；或用 `GOOGLE_SERVICE_ACCOUNT_FILE` 指向檔案） |

設定步驟見 `docs/02-google-sheets-setup.md`（把試算表與資料夾分享給服務帳戶的電郵即可）。
設定好之後，帳戶、進度、積分、相片都會跨裝置保存，Vercel 只是跑程式的地方。

## 測試站上有甚麼

- `/`（`public/index.html`）：測試站首頁，一按即用示範帳號登入，另有離線試玩入口。
- `/welcome`：真正的登入頁；`/login/demo/demo1`、`/login/demo/demo2` 直接登入示範帳號。
- `/tasks/<id>/cave` 遊戲 1（山洞）、`/tasks/<id>/bridge` 遊戲 2（迷霧渡口）。
- `/demo-preview.html`、`/bridge-preview.html`：離線單檔試玩（同一個部署的靜態檔）。
- `docs/`、`tests/`、`tools/`、截圖 **不會**上載到 Vercel（`.vercelignore`），
  亦不會經網址取用；`data/db/*.json` 只在函式內部使用，靜態輸出目錄是 `public/`，
  所以帳戶資料不會被公開下載。

## 每次更新的流程

```bash
cd scout-platform-py
GITHUB_TOKEN=github_pat_xxx bash tools/push.sh "改了甚麼"
```

推送完成後 Vercel 會自動建置新版本（Deployments 頁面可以看到進度，約 30–60 秒）。
`GITHUB_TOKEN` 需要該 repository 的 **Contents: Read and write**；用完可以即時撤銷。

## 如果 Vercel 失敗

- **Build 失敗**：多數是 `requirements.txt` 或 `vercel.json` 被改壞；在 Vercel 的 Build Logs 看最後十行即可。
- **網站 500（Function Error）**：到 Vercel → Project → Logs，看 `api/index` 的錯誤訊息；
  最常見是 `SESSION_SECRET` 未設定，或 `includeFiles` 漏了 `templates/`、`content/`。
- **玩了很久之後回到登入頁**：執行個體被回收（正常），重新登入即可；要避免就設定 Sheets 儲存。
