"""Auto-updater: pulls new versions from GitHub Releases.

The GitHub repository must be public. Flow:
  1. ``fetch_update()`` asks GitHub for the latest release and returns its
     details when it is newer than CURRENT_VERSION.
  2. ``download_update()`` downloads the .zip and verifies its SHA-256 against
     the digest GitHub publishes for the asset (or a ``<zip>.sha256`` asset).
     A download that does not match is deleted and never run.
  3. ``apply_update()`` (Windows .exe only) writes a small script that waits
     for this process to exit, replaces the .exe and restarts it.

Uses only the standard library.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile

CURRENT_VERSION = "2.0.0"

GITHUB_USER = "Gavin2540"
GITHUB_REPO = "PlywoodPro"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
EXE_NAME = "Plywood Pro.exe"  # must match the PyInstaller --name
_HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "PlywoodPro-Updater"}


class UpdateError(RuntimeError):
    pass


def _parse_version(tag):
    parts = []
    for p in str(tag).strip().lstrip("vV").split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def is_newer(remote_tag, local_version=CURRENT_VERSION):
    a, b = _parse_version(remote_tag), _parse_version(local_version)
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def can_self_update():
    """Only the packaged Windows .exe can replace itself."""
    return sys.platform.startswith("win") and getattr(sys, "frozen", False)


def _get_json(url, timeout=6):
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_update():
    """Return {"version", "url", "sha256", "size", "notes"} if a newer release exists, else None.

    Never raises: with no internet it simply returns None.
    """
    try:
        release = _get_json(LATEST_RELEASE_URL)
    except (urllib.error.URLError, OSError, ValueError):
        return None
    tag = release.get("tag_name", "")
    if not tag or not is_newer(tag):
        return None
    assets = release.get("assets", [])
    zip_asset = next((a for a in assets if a.get("name", "").lower().endswith(".zip")), None)
    if not zip_asset or not zip_asset.get("browser_download_url"):
        return None
    sha = None
    digest = zip_asset.get("digest") or ""
    if digest.startswith("sha256:"):
        sha = digest.split(":", 1)[1].strip().lower()
    else:
        side = next((a for a in assets if a.get("name") == zip_asset["name"] + ".sha256"), None)
        if side:
            try:
                req = urllib.request.Request(side["browser_download_url"], headers=_HEADERS)
                with urllib.request.urlopen(req, timeout=6) as resp:
                    sha = resp.read().decode("utf-8").split()[0].strip().lower()
            except (urllib.error.URLError, OSError, IndexError):
                sha = None
    return {"version": tag, "url": zip_asset["browser_download_url"], "sha256": sha,
            "size": zip_asset.get("size", 0), "notes": release.get("body") or ""}


def download_update(update, progress=None):
    """Download and verify the release zip. Returns its path. Raises UpdateError."""
    if not update.get("sha256"):
        raise UpdateError("This release has no checksum, so it cannot be verified. "
                          "Please download it from the releases page instead.")
    if not update["url"].startswith("https://"):
        raise UpdateError("The download link is not secure.")
    folder = tempfile.mkdtemp(prefix="plywoodpro-update-")
    zip_path = os.path.join(folder, "update.zip")
    hasher = hashlib.sha256()
    try:
        req = urllib.request.Request(update["url"], headers={"User-Agent": _HEADERS["User-Agent"]})
        with urllib.request.urlopen(req, timeout=30) as resp, open(zip_path, "wb") as f:
            total = int(resp.headers.get("Content-Length") or update.get("size") or 0)
            done = 0
            while True:
                chunk = resp.read(131072)
                if not chunk:
                    break
                f.write(chunk)
                hasher.update(chunk)
                done += len(chunk)
                if progress and total:
                    progress(done, total)
    except (urllib.error.URLError, OSError) as e:
        _discard(zip_path)
        raise UpdateError(f"The download failed: {e}")
    if hasher.hexdigest().lower() != update["sha256"]:
        _discard(zip_path)
        raise UpdateError("The downloaded file did not match its checksum and was discarded.")
    try:
        with zipfile.ZipFile(zip_path) as z:
            if EXE_NAME not in z.namelist():
                raise UpdateError("The update package is not in the expected format.")
    except zipfile.BadZipFile:
        _discard(zip_path)
        raise UpdateError("The update package is damaged.")
    return zip_path


def _discard(path):
    try:
        os.remove(path)
    except OSError:
        pass


def apply_update(zip_path):
    """Replace the running .exe with the downloaded one and restart. Windows only."""
    if not can_self_update():
        raise UpdateError("Automatic install is only available in the Windows app.")
    app_dir = os.path.dirname(sys.executable)
    script = os.path.join(os.path.dirname(zip_path), "apply_update.bat")
    ps = lambda s: s.replace("'", "''")  # PowerShell single-quote escaping
    lines = [
        "@echo off",
        "title Plywood Pro - updating",
        "echo Updating Plywood Pro, please wait...",
        ":wait",
        f'tasklist /FI "PID eq {os.getpid()}" 2>nul | find "{os.getpid()}" >nul',
        "if not errorlevel 1 (",
        "  timeout /t 1 /nobreak >nul",
        "  goto wait",
        ")",
        f"powershell -NoProfile -ExecutionPolicy Bypass -Command \"Expand-Archive -LiteralPath '{ps(zip_path)}' "
        f"-DestinationPath '{ps(app_dir)}' -Force\"",
        "if errorlevel 1 (",
        "  echo The update could not be installed. Your current version is unchanged.",
        "  pause",
        "  exit /b 1",
        ")",
        f'del /f /q "{zip_path}"',
        f'start "" "{os.path.join(app_dir, EXE_NAME)}"',
        '(goto) 2>nul & del "%~f0"',
    ]
    with open(script, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\r\n".join(lines) + "\r\n")
    subprocess.Popen(["cmd", "/c", script], cwd=app_dir,
                     creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0), close_fds=True)
