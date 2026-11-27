"""Backup and restore.

A ``.plypro`` file is a zip holding ``plywoodpro.db`` and ``meta.json``.
Restoring validates the file in a temporary folder first and always keeps a
safety copy of the current data, so a bad file can never destroy the books.
"""
import datetime
import glob
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile

from database.db import DatabaseManager

REQUIRED_TABLES = {"products", "purchases", "sales", "expenses"}


def _backup_dir():
    path = os.path.join(os.path.dirname(DatabaseManager.db_path()), "backups")
    os.makedirs(path, exist_ok=True)
    return path


def _snapshot(dest_db_path):
    """Consistent copy of the live database, safe while the app is using it."""
    dest = sqlite3.connect(dest_db_path)
    try:
        DatabaseManager.get_connection().backup(dest)
    finally:
        dest.close()


def export_database(destination_path):
    """Write the current data to a .plypro backup file."""
    from utils.updater import CURRENT_VERSION
    with tempfile.TemporaryDirectory() as tmp:
        db_copy = os.path.join(tmp, "plywoodpro.db")
        _snapshot(db_copy)
        meta = {"export_date": datetime.datetime.now().isoformat(timespec="seconds"),
                "app": "PlywoodPro", "version": CURRENT_VERSION}
        with zipfile.ZipFile(destination_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(db_copy, arcname="plywoodpro.db")
            z.writestr("meta.json", json.dumps(meta, indent=2))
    return destination_path


def _validate(db_file):
    try:
        conn = sqlite3.connect(db_file)
        try:
            ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        finally:
            conn.close()
    except sqlite3.Error:
        raise ValueError("The backup file is damaged or is not a Plywood Pro backup.")
    if ok != "ok" or not REQUIRED_TABLES <= tables:
        raise ValueError("The backup file is damaged or is not a Plywood Pro backup.")


def import_database(source_path):
    """Replace the current data with a backup. Returns the path of the safety copy."""
    if not zipfile.is_zipfile(source_path):
        raise ValueError("The selected file is not a Plywood Pro backup.")
    db_path = DatabaseManager.db_path()
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(source_path) as z:
            if "plywoodpro.db" not in z.namelist():
                raise ValueError("The selected file is not a Plywood Pro backup.")
            z.extract("plywoodpro.db", tmp)
        candidate = os.path.join(tmp, "plywoodpro.db")
        _validate(candidate)

        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        safety = os.path.join(_backup_dir(), f"before-restore-{stamp}.db")
        _snapshot(safety)

        DatabaseManager.close()
        for suffix in ("-wal", "-shm", "-journal"):
            if os.path.exists(db_path + suffix):
                os.remove(db_path + suffix)
        shutil.copy2(candidate, db_path)
    try:
        DatabaseManager.initialize(db_path)  # also upgrades an older backup
    except Exception:
        DatabaseManager.close()
        shutil.copy2(safety, db_path)
        DatabaseManager.initialize(db_path)
        raise ValueError("That backup could not be opened, so your current data was kept.")
    return safety


def auto_backup(keep=14):
    """One automatic backup per day, keeping the most recent ``keep`` files."""
    target = os.path.join(_backup_dir(), f"auto-{datetime.date.today().isoformat()}.plypro")
    export_database(target)
    files = sorted(glob.glob(os.path.join(_backup_dir(), "auto-*.plypro")))
    for old in files[:-keep] if keep > 0 else []:
        try:
            os.remove(old)
        except OSError:
            pass
    return target


def list_backups():
    files = glob.glob(os.path.join(_backup_dir(), "*"))
    return sorted(files, key=os.path.getmtime, reverse=True)
