#!/usr/bin/env bash
# Rebuild what a sandbox reset wipes: python packages, a headless chromium, and
# the shared libraries it needs. Everything lands outside the workspace *except*
# this script, so the next reset costs one command, not twenty.
#
#   bash tools/bootstrap_browser.sh
#
# Afterwards run playwright with:
#   LD_LIBRARY_PATH=/tmp/syslibs python3 script.py
set -euo pipefail

echo "── python packages ──"
pip install --quiet flask playwright 2>&1 | tail -2 || true
python3 -c "import flask, playwright; print('  flask', flask.__version__ if hasattr(flask, '__version__') else 'ok', '/ playwright ok')"

echo "── chromium ──"
python3 -m playwright install chromium 2>&1 | tail -2

echo "── shared libraries → /tmp/syslibs ──"
mkdir -p /tmp/debs /tmp/unpack /tmp/syslibs
cd /tmp/debs
for p in libnspr4 libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 libxdamage1 \
         libxkbcommon0 libasound2t64 libatspi2.0-0t64 libxcomposite1 libxrandr2 \
         libxfixes3 libcups2t64 libgbm1 libdrm2 libpango-1.0-0 libpangocairo-1.0-0 \
         libcairo2 libx11-xcb1 libxcb1 libexpat1; do
  [ -f "${p}"*.deb ] || apt-get download "$p" >/dev/null 2>&1 || echo "  (skipped $p)"
done
for d in *.deb; do dpkg-deb -x "$d" /tmp/unpack 2>/dev/null || true; done
find /tmp/unpack -name "*.so*" -exec cp -a {} /tmp/syslibs/ \; 2>/dev/null || true
echo "  $(ls /tmp/syslibs | wc -l) libraries in /tmp/syslibs"

echo "── smoke test ──"
LD_LIBRARY_PATH=/tmp/syslibs python3 - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch()
    p = b.new_page(); p.set_content("<h1>ok</h1>")
    print("  chromium speaks:", p.inner_text('h1'))
    b.close()
PY

echo "── the demo server (optional) ──"
echo "  cd scout-platform-py && SECRET_KEY=dev-secret-key-for-preview DATA_DIR=./data \\"
echo "    DEMO_LOGIN=true SEED_DEMO=true python3 -m flask --app app run --host 0.0.0.0 --port 5001"
