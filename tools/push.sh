#!/usr/bin/env bash
# 把改動提交並推送 GitHub（Vercel 會自動重新部署）。
#
#   GITHUB_TOKEN=github_pat_xxx bash tools/push.sh "這次改了甚麼"
#
# token 由環境變數傳入；若沒有，會嘗試讀 ~/.82hkg-github-token（那個檔案不入版控）。
# 需要 fine-grained token：該 repository 的 Contents: Read and write。
set -euo pipefail

cd "$(dirname "$0")/.."

msg="${1:-更新}"
token="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
if [ -z "$token" ] && [ -f "$HOME/.82hkg-github-token" ]; then
  token="$(tr -d '[:space:]' < "$HOME/.82hkg-github-token")"
fi
if [ -z "$token" ]; then
  echo "沒有 token：請用 GITHUB_TOKEN=… bash tools/push.sh \"說明\"，或把 token 寫入 ~/.82hkg-github-token" >&2
  exit 1
fi

GITHUB_TOKEN="$token" git add -A
if ! git diff --cached --quiet; then
  git commit -q -m "$msg"
  echo "已提交：$(git log -1 --format='%h %s')"
else
  echo "沒有未提交的改動，直接推送。"
fi

GITHUB_TOKEN="$token" git -c credential.helper='!f() { echo username=x-access-token; echo "password=${GITHUB_TOKEN}"; }; f' push origin main
echo "推送完成：$(git log -1 --format='%h %s')  →  Vercel 會自動重新部署"
