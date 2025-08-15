#!/usr/bin/env python3
"""
Cross-platform env bootstrapper for the HTML Structure Analyzer.

What it does (idempotent):
- Detects OS (Windows vs Linux/macOS)
- Creates or reuses a virtualenv at ./.venv
- Upgrades pip/setuptools/wheel
- Installs from requirements.txt if present; otherwise installs core deps
- Ensures Playwright is installed
- Installs Playwright browsers (with --with-deps on Linux)

Usage:
    python setup_env.py
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

VENV_DIR = Path(".venv")
IS_WINDOWS = platform.system().lower().startswith("win")
IS_LINUX = platform.system().lower().startswith("lin")
IS_MAC = platform.system().lower().startswith("darwin")

# Core deps in case requirements.txt is not present
CORE_DEPS = [
    "streamlit",
    "pandas",
    "lxml",
    "selectolax",
    "requests",
    # optional but useful fallback
    "selenium",
]

def run(cmd, env=None, check=True):
    print(f"▶ {' '.join(cmd)}")
    return subprocess.run(cmd, env=env, check=check)

def python_in_venv() -> Path:
    if IS_WINDOWS:
        return VENV_DIR / "Scripts" / "python.exe"
    else:
        return VENV_DIR / "bin" / "python"

def ensure_venv():
    if not VENV_DIR.exists():
        print(f"📦 Creating virtualenv at {VENV_DIR} ...")
        run([sys.executable, "-m", "venv", str(VENV_DIR)])
    else:
        print(f"✅ Reusing existing virtualenv at {VENV_DIR}")

def upgrade_pip(python: Path):
    print("⬆️  Upgrading pip/setuptools/wheel ...")
    run([str(python), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])

def install_requirements_or_core(python: Path):
    req = Path("requirements.txt")
    if req.exists():
        print("📄 Installing from requirements.txt ...")
        run([str(python), "-m", "pip", "install", "-r", str(req)])
    else:
        print("ℹ️  requirements.txt not found; installing core deps ...")
        run([str(python), "-m", "pip", "install", "--upgrade", *CORE_DEPS])

def ensure_playwright_installed(python: Path):
    print("🔎 Checking Playwright installation ...")
    code = "import importlib, sys; sys.exit(0 if importlib.util.find_spec('playwright') else 1)"
    result = subprocess.run([str(python), "-c", code])
    if result.returncode == 0:
        print("✅ Playwright already installed")
    else:
        print("📥 Installing Playwright ...")
        run([str(python), "-m", "pip", "install", "--upgrade", "playwright"])

def install_playwright_browsers(python: Path):
    print("🧭 Installing Playwright browsers ...")
    args = [str(python), "-m", "playwright", "install", "chromium", "firefox", "webkit"]
    if IS_LINUX:
        # include system deps on Linux
        args.insert(3, "install")
        # already inserted; add flag
        args = [str(python), "-m", "playwright", "install", "--with-deps", "chromium", "firefox", "webkit"]
    run(args)

def main():
    print(f"🖥️  OS detected: {platform.system()} {platform.release()}")
    ensure_venv()
    py = python_in_venv()
    if not py.exists():
        print("❌ Could not locate venv python interpreter.")
        sys.exit(1)

    upgrade_pip(py)
    install_requirements_or_core(py)
    ensure_playwright_installed(py)
    install_playwright_browsers(py)

    print("\n🎉 Setup complete!")
    if IS_WINDOWS:
        print("▶ Activate venv: .\\.venv\\Scripts\\Activate.ps1")
    else:
        print("▶ Activate venv: source .venv/bin/activate")
    print("▶ Run app:       streamlit run app.py")

if __name__ == "__main__":
    main()
