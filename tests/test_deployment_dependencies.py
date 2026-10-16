"""Deployment dependencies: anything the app imports must be in requirements.txt.

The bug this prevents: the Sheets driver signs its Google requests with
`google-auth`, imported lazily inside `_token()`. That import never ran in the
test suite (the tests replace the HTTP transport instead), so the package was
missing from requirements.txt — and on Vercel the function crashed at start-up
the moment a Google Sheet was configured, which looked like 「page is not
available」 with nothing in the UI to explain it.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STDLIB = set(sys.stdlib_module_names)
OUR_OWN = {"scout", "app", "api", "tools", "tests", "conftest"}   # 自己專案裡的模組
# third-party names as imported  →  the distribution that provides them
DISTRIBUTION = {
    "flask": "flask",
    "requests": "requests",
    "itsdangerous": "itsdangerous",
    "google": "google-auth",
    "werkzeug": "werkzeug",
    "jinja2": "jinja2",
    "markupsafe": "markupsafe",
}


def imported_third_party() -> set[str]:
    """Every top-level third-party module imported anywhere in the package."""
    found: set[str] = set()
    for path in sorted(ROOT.glob("scout/**/*.py")) + [ROOT / "app.py", ROOT / "api/index.py"]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top not in STDLIB and top not in OUR_OWN:
                        found.add(top)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                top = node.module.split(".")[0]
                if top not in STDLIB and top not in OUR_OWN:
                    found.add(top)
    return found


def requirements() -> str:
    return (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()


def test_every_import_the_app_makes_is_declared_for_the_deployment():
    missing = []
    for module in sorted(imported_third_party()):
        distribution = DISTRIBUTION.get(module, module)
        if distribution not in requirements():
            missing.append(f"{module}（需要 {distribution}）")
    assert not missing, "requirements.txt 缺少：" + ", ".join(missing)


def test_google_auth_is_declared_because_the_sheets_driver_signs_requests():
    text = (ROOT / "scout/drivers/sheets.py").read_text(encoding="utf-8")
    assert "google.oauth2" in text or "google.auth" in text
    assert "google-auth" in requirements(), "Google Sheets 驅動需要 google-auth"


def test_the_driver_imports_google_auth_only_lazily_so_local_runs_stay_light():
    """A missing google-auth must not stop the app from booting at all."""
    source = (ROOT / "scout/drivers/sheets.py").read_text(encoding="utf-8")
    top = source.split("def _token", 1)[0]
    assert "import google" not in top, "google-auth 應該只在 _token() 內 import"
