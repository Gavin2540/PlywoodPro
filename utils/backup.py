import os
import sys
import zipfile
import shutil
import json
from datetime import datetime
from database.db import DatabaseManager

def export_database(destination_path):
    """
    Exports the current database as a .plypro file (zip archive).
    """
    db_path = DatabaseManager._db_path
    if not db_path or not os.path.exists(db_path):
        raise FileNotFoundError("Database file not found.")

    # Create metadata
    metadata = {
        "export_date": datetime.now().isoformat(),
        "app": "PlywoodPro",
        "version": "1.0"
    }

    # Create temporary metadata file
    meta_path = db_path + ".meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4)

    try:
        # Create the zip archive (.plypro)
        with zipfile.ZipFile(destination_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(db_path, arcname="plywoodpro.db")
            zipf.write(meta_path, arcname="meta.json")
    finally:
        if os.path.exists(meta_path):
            os.remove(meta_path)

def import_database(source_path):
    """
    Imports a .plypro file, replacing the current database.
    """
    db_path = DatabaseManager._db_path
    if not db_path:
        DatabaseManager.initialize()
        db_path = DatabaseManager._db_path

    if not zipfile.is_zipfile(source_path):
        raise ValueError("Selected file is not a valid PlywoodPro backup.")

    with zipfile.ZipFile(source_path, 'r') as zipf:
        file_list = zipf.namelist()
        if "plywoodpro.db" not in file_list:
            raise ValueError("Backup file is missing the database component.")

        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Replace the database file
        # We need to ensure we can overwrite it. If it's locked, this might raise an error.
        temp_dir = os.path.dirname(db_path)
        zipf.extract("plywoodpro.db", temp_dir)
