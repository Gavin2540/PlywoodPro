"""Build the standalone app with PyInstaller (same command on Windows, macOS, CI).

    python tools/build.py

Windows -> dist/Plywood Pro.exe (single file; what the auto-updater ships)
macOS   -> dist/Plywood Pro.app (for trying the packaged app on a Mac)
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEP = ";" if sys.platform.startswith("win") else ":"

# Qt pieces the app never touches; leaving them out keeps the download small.
EXCLUDES = ["PySide6.QtNetwork", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtQml",
            "PySide6.QtQuick", "PySide6.QtPdf", "PySide6.QtDBus", "PySide6.QtTest", "PySide6.QtXml",
            "PySide6.QtConcurrent", "PySide6.QtSql", "tkinter", "unittest", "pytest", "matplotlib", "numpy"]


def main():
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
           "--name", "Plywood Pro",
           "--add-data", f"database/schema.sql{SEP}database",
           "--add-data", f"icon.ico{SEP}.",
           "--hidden-import", "unicodedata", "--paths", "tools", "--hidden-import", "seed_demo",
           # pages are loaded by name at runtime, so PyInstaller must be told about them
           "--collect-submodules", "ui", "--collect-submodules", "models", "--collect-submodules", "utils"]
    if sys.platform.startswith("win"):
        cmd += ["--onefile", "--icon", "icon.ico"]
    elif sys.platform == "darwin":
        cmd += ["--osx-bundle-identifier", "com.plywoodpro.app"]
    for mod in EXCLUDES:
        cmd += ["--exclude-module", mod]
    cmd.append("main.py")
    print(" ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
