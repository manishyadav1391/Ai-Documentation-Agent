import os
import json
import zipfile
import shutil
import logging
from datetime import datetime

class Exporter:
    def __init__(self, base_dir="."):
        self.base_dir = os.path.abspath(base_dir)
        self.sessions_dir = os.path.join(self.base_dir, "sessions")
        self.output_dir = os.path.join(self.base_dir, "output")
        
        # Ensure base directories exist
        os.makedirs(self.sessions_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

    def create_session_layout(self, session_id):
        """
        Creates directory structure for a new session:
        sessions/session_id/
        └── screenshots/
        """
        session_path = os.path.join(self.sessions_dir, session_id)
        screenshots_path = os.path.join(session_path, "screenshots")
        
        os.makedirs(session_path, exist_ok=True)
        os.makedirs(screenshots_path, exist_ok=True)
        
        logging.info(f"Created session directory layout: {session_path}")
        return session_path, screenshots_path

    def save_session(self, session_id, steps, start_time, end_time, app_name="Generic Desktop Application"):
        """
        Writes session.json and metadata.json to the session directory.
        """
        session_path = os.path.join(self.sessions_dir, session_id)
        if not os.path.exists(session_path):
            os.makedirs(session_path, exist_ok=True)

        # 1. Format and save steps to session.json
        session_data = {
            "application": app_name,
            "steps": steps
        }
        
        session_json_path = os.path.join(session_path, "session.json")
        with open(session_json_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2)
            
        # 2. Write metadata.json
        metadata = {
            "session_id": session_id,
            "application": app_name,
            "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S") if isinstance(start_time, datetime) else str(start_time),
            "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S") if isinstance(end_time, datetime) else str(end_time),
            "total_steps": len(steps),
            "os": "Windows",
            "exporter_version": "1.0"
        }
        
        metadata_json_path = os.path.join(session_path, "metadata.json")
        with open(metadata_json_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
            
        logging.info(f"Saved session.json and metadata.json for {session_id}")
        return session_json_path, metadata_json_path

    def export_zip(self, session_id):
        """
        Zips the session directory and writes it to the output folder.
        Returns the path to the zip file.
        """
        session_path = os.path.join(self.sessions_dir, session_id)
        if not os.path.exists(session_path):
            raise FileNotFoundError(f"Session path {session_path} does not exist.")
            
        zip_filename = f"{session_id}.zip"
        zip_filepath = os.path.join(self.output_dir, zip_filename)
        
        logging.info(f"Zipping session {session_id} to {zip_filepath}...")
        
        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(session_path):
                for file in files:
                    file_abspath = os.path.join(root, file)
                    # Get relative path within the session directory to keep structure inside ZIP
                    rel_path = os.path.relpath(file_abspath, session_path)
                    # We can prefix the ZIP entries with the session_id folder name
                    zip_entry_name = os.path.join(session_id, rel_path)
                    zipf.write(file_abspath, zip_entry_name)
                    
        logging.info(f"Exported session successfully as ZIP: {zip_filepath}")
        return zip_filepath
