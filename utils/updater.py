"""
PlywoodPro Auto-Updater Engine
================================
Silent background updater that pulls new versions from GitHub Releases.

IMPORTANT: Your GitHub repository MUST be set to PUBLIC for this to work
without an authentication token. If the repo is private, you will need to
add a "Authorization: token YOUR_PAT" header to the urllib request.

How it works:
  1. A daemon thread fires on app startup and hits the GitHub Releases API.
  2. It compares the remote tag_name (e.g. "v1.0.2") against CURRENT_VERSION.
  3. If a newer version exists, it calls a callback on the main UI thread.
  4. When the user accepts, it downloads the .zip, generates a tiny .bat
     that overwrites the old files and restarts the new .exe, then exits.

Uses only built-in stdlib (urllib) — no 'requests' dependency.
"""

import sys
import os
import json
import threading
import tempfile
import urllib.request
import urllib.error

# ─────────────────────────────────────────────────────────────────────────────
#  ⚙️  CONFIGURATION — update these for your own GitHub repo
# ─────────────────────────────────────────────────────────────────────────────

CURRENT_VERSION = "1.0.0"

# Replace with your actual GitHub username and repository name
GITHUB_USER = "Gavin2540"
GITHUB_REPO = "PlywoodPro"

LATEST_RELEASE_URL = (
    f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
)

# Name of your compiled executable (must match PyInstaller --name)
EXE_NAME = "PlywoodPro.exe"

# ─────────────────────────────────────────────────────────────────────────────
#  Version comparison helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_version(tag: str) -> tuple:
    """Strips leading 'v' and splits into a tuple of ints for comparison.
       e.g. 'v1.2.3' -> (1, 2, 3)
    """
    tag = tag.strip().lstrip("vV")
    parts = []
    for p in tag.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def is_newer(remote_tag: str, local_version: str = CURRENT_VERSION) -> bool:
    """Returns True if remote_tag represents a version newer than local_version."""
    return _parse_version(remote_tag) > _parse_version(local_version)


# ─────────────────────────────────────────────────────────────────────────────
#  Core: Check for updates (runs in background thread)
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_latest_release() -> dict | None:
    """Hits the GitHub API and returns the JSON payload, or None on any failure."""
    try:
        req = urllib.request.Request(
            LATEST_RELEASE_URL,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "PlywoodPro-Updater",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError):
        # Network down, rate-limited, timeout, etc. — fail silently
        return None


def _find_zip_asset(release_data: dict) -> dict | None:
    """Finds the first .zip file in the release's assets list."""
    for asset in release_data.get("assets", []):
        if asset.get("name", "").lower().endswith(".zip"):
            return asset
    return None


def check_for_updates(callback):
    """
    Background worker (called inside a daemon thread).
    
    If a newer release is found, invokes `callback(version, download_url)`
    from the BACKGROUND thread. The caller is responsible for marshalling
    to the main thread (see check_for_updates_async below).
    """
    release = _fetch_latest_release()
    if release is None:
        return  # No internet or API issue — silently abort

    remote_tag = release.get("tag_name", "")
    if not remote_tag or not is_newer(remote_tag):
        return  # Already up-to-date

    zip_asset = _find_zip_asset(release)
    if zip_asset is None:
        return  # Release exists but has no zip — nothing to download

    download_url = zip_asset.get("browser_download_url", "")
    if download_url:
        callback(remote_tag, download_url)


def check_for_updates_async(callback):
    """
    Kicks off the update check in a daemon thread so it never blocks the UI.
    
    Usage from your main window:
        from utils.updater import check_for_updates_async
        check_for_updates_async(lambda ver, url: self.after(0, self._on_update_available, ver, url))
    """
    t = threading.Thread(target=check_for_updates, args=(callback,), daemon=True)
    t.start()


# ─────────────────────────────────────────────────────────────────────────────
#  Core: Download & apply the update
# ─────────────────────────────────────────────────────────────────────────────

def _get_app_dir() -> str:
    """Returns the directory where the running .exe (or script) lives."""
    if getattr(sys, "frozen", False):
        # Running as a PyInstaller bundle
        return os.path.dirname(sys.executable)
    else:
        # Running as a normal Python script (dev mode)
        return os.path.dirname(os.path.abspath(__file__))


def download_and_apply_update(download_url: str, progress_callback=None):
    """
    Downloads the zip, writes a self-destructing .bat updater, and exits.
    
    The batch script:
      1. Waits 2 seconds for this process to fully terminate.
      2. Uses PowerShell Expand-Archive to extract and overwrite files.
      3. Deletes the downloaded .zip.
      4. Restarts the new .exe.
      5. Deletes itself.
    
    Args:
        download_url: Direct URL to the .zip asset from GitHub Releases.
        progress_callback: Optional callable(bytes_downloaded, total_bytes)
                           for showing a progress bar in the UI.
    """
    app_dir = _get_app_dir()
    zip_filename = "PlywoodPro_update.zip"
    zip_path = os.path.join(app_dir, zip_filename)
    bat_path = os.path.join(app_dir, "_apply_update.bat")
    exe_path = os.path.join(app_dir, EXE_NAME)

    # ── Step 1: Download the zip ──────────────────────────────────────────
    try:
        req = urllib.request.Request(
            download_url,
            headers={"User-Agent": "PlywoodPro-Updater"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 65536  # 64 KB chunks
            with open(zip_path, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total > 0:
                        progress_callback(downloaded, total)
    except Exception as e:
        # Clean up partial download
        if os.path.exists(zip_path):
            try:
                os.remove(zip_path)
            except OSError:
                pass
        raise RuntimeError(f"Download failed: {e}")

    # ── Step 2: Generate the update batch script ──────────────────────────
    #
    # Key design decisions:
    #   - "timeout /t 2" gives the Python process time to fully exit.
    #   - "-Force" on Expand-Archive overwrites existing files.
    #   - The batch file deletes itself at the very end (del "%~f0").
    #
    bat_content = f"""@echo off
echo ============================================
echo   PlywoodPro Auto-Updater — Applying update
echo ============================================
echo.
echo Waiting for application to close...
timeout /t 2 /nobreak >nul

echo Extracting update files...
powershell -NoProfile -Command "Expand-Archive -Path '{zip_path}' -DestinationPath '{app_dir}' -Force"

echo Cleaning up...
del /f /q "{zip_path}"

echo Restarting PlywoodPro...
start "" "{exe_path}"

echo Update complete!
(goto) 2>nul & del "%~f0"
"""

    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)

    # ── Step 3: Launch the batch script and exit ──────────────────────────
    os.startfile(bat_path)
    sys.exit(0)
