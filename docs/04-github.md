# 放上 GitHub（備份與版本記錄）

**現況：已放上 https://github.com/hinli2021/82hkg-scout-platform（私人 repository）**
- 第一次上載：2026-10-16，163 個檔案、一次提交（commit `821d44e`）。
- 未上載：`data/db/sessions.json`（登入憑證，程式自動重建）、`data/uploads/`（童軍相片）。
- **110 張介面截圖**存放在同一個 repository 的另一個分支 **`screenshots`**
  （壓縮版，22 MB），不佔用本機空間：
  `https://github.com/hinli2021/82hkg-scout-platform/tree/screenshots/docs/screens`
- 本機 `docs/screens/` 只保留最新 12 張（壓縮版），PNG 不入版控，重拍不會弄髒 `git status`；
  檢查腳本隨時可以重拍任何一張。

## 每次改動之後推送

```bash
GITHUB_TOKEN=github_pat_xxx bash tools/push.sh "這次改了甚麼"
```

推送 `main` 之後，Vercel 會自動重新部署測試站（見 `docs/05-vercel.md`）。
token 只需要**這一個 repository** 的 **Contents: Read and write**；用完可以即時撤銷。
若把 token 寫入 `~/.82hkg-github-token`（在 repository 之外，不入版控），
`tools/push.sh` 就會自動讀取，之後不必每次貼上。

整個計劃就是 `scout-platform-py` 這一個資料夾。放上 GitHub 之後，每次改動都有一個記錄，
換電腦、換領袖接手，都可以由同一個地方取回完整檔案。

## 三條路，選一條

### A. 由這裡直接推送（最快，需要一個 GitHub token）　←　現時採用這一條
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

### B. 下載後在 GitHub 網頁上傳（不需要安裝任何工具）
1. 下載 `scout-platform-py.zip`，解壓縮。
2. GitHub → New repository → 建立空的 repository（私人或公開由領袖決定）。
3. 在新 repository 按 **Add file → Upload files**，把解壓後資料夾內的東西**全部**拖進去
   （如檔案太多，可只上載 `app.py`、`scout/`、`content/`、`templates/`、`static/`、`data/`、
   `tools/`、`tests/`、`docs/` 及說明文件）。
4. 按 Commit changes，完成。

### C. 用 git 或 GitHub Desktop（日後要自己更新的話最方便）
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

## 以下東西不會上載（`.gitignore` 已設好）

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

## 檔案大小

截圖已排除，repository 約 **22 MB**（163 個檔案）：程式、內容題庫、離線試玩檔與測試都在內。
需要看畫面時，在平台這裡開 `docs/screens/` 就可以，或用 `tools/checks/` 內的檢查腳本重拍。

## 日後更新

- 平台代你推送：改完之後說一聲「更新 GitHub」，平台會再推一次。
- 自己推送：把新的檔案覆蓋到同一個資料夾，然後 `git add -A && git commit -m "說明" && git push`。
