# This script reads and monitors a YAML configuration file for changes,
# saves its contents to a MongoDB database with versioning,
# and provides a Flask API to retrieve the latest and historical configurations.
# This also prevents the duplication of configurations being inserted in mongodb.

# Required Libraries: pyyaml, pymongo, flask, watchdog
# To install, run: pip install -r requirements.txt


import yaml
import os
from datetime import datetime
from flask import Flask, jsonify
from pymongo import MongoClient
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ====================
# Configuration
# ====================
CONFIG_FILE = r'C:\HeroVired\Assignments\Python_Assignments\auto_config_save\config.yaml'
SECRETS_FILE = r'C:\HeroVired\Assignments\Python_Assignments\auto_config_save\secrets.yaml'
DB_NAME = 'config_db'
COLLECTION_NAME = 'config_data'

# ====================
# Load Secrets
# ====================
def load_secrets(secret_file):
    abs_path = os.path.abspath(secret_file)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Secrets file not found: {abs_path}")
    with open(abs_path, 'r') as f:
        secrets = yaml.safe_load(f)
    mongo_uri = secrets.get("mongo", {}).get("uri", "")
    if not mongo_uri:
        raise ValueError("MongoDB URI not found in secrets.yaml")
    return mongo_uri

MONGO_URI = load_secrets(SECRETS_FILE)

# ====================
# Config Handling
# ====================
def read_config(file_path):
    try:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            print(f"Error: YAML file must contain a dictionary at top level")
            return None
        return data
    except Exception as e:
        print(f"Error reading YAML file: {e}")
        return None

def convert_numeric_values(data):
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                convert_numeric_values(v)
            elif isinstance(v, str) and v.isdigit():
                data[k] = int(v)
    return data

# ====================
# MongoDB Handling
# ====================
def save_to_mongo(data):
    """Save configuration only if it doesn't already exist"""
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]

        # Check if identical config exists in any document
        existing_doc = collection.find_one({"config": data})
        if existing_doc:
            print(f"Configuration already exists in MongoDB (version {existing_doc['version']}). No new version created.")
            return

        # Determine next version
        last_doc = collection.find_one(sort=[("version", -1)])
        next_version = 1 if not last_doc else last_doc['version'] + 1

        doc = {
            "version": next_version,
            "timestamp": datetime.utcnow(),
            "config": data
        }
        collection.insert_one(doc)
        print(f"Configuration saved to MongoDB (version {next_version})")
    except Exception as e:
        print(f"Error saving to MongoDB: {e}")

def fetch_latest_from_mongo():
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]

        latest_doc = collection.find_one(sort=[("version", -1)])
        if latest_doc:
            return {
                "version": latest_doc["version"],
                "timestamp": latest_doc["timestamp"].isoformat(),
                "config": latest_doc["config"]
            }
        return {}
    except Exception as e:
        print(f"Error fetching from MongoDB: {e}")
        return {}

def fetch_all_versions():
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]

        docs = []
        for doc in collection.find().sort("version", 1):
            docs.append({
                "version": doc["version"],
                "timestamp": doc["timestamp"].isoformat(),
                "config": doc["config"],
                "rolled_back_from": doc.get("rolled_back_from", None)
            })
        return docs
    except Exception as e:
        print(f"Error fetching from MongoDB: {e}")
        return []

def rollback_to_version(version):
    """Rollback to a previous version, insert as new version, and update YAML file"""
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]

        doc = collection.find_one({"version": version})
        if not doc:
            return False, f"Version {version} not found."

        # Insert rollback as a new version
        last_doc = collection.find_one(sort=[("version", -1)])
        next_version = 1 if not last_doc else last_doc['version'] + 1

        rollback_doc = {
            "version": next_version,
            "timestamp": datetime.utcnow(),
            "config": doc['config'],
            "rolled_back_from": version
        }
        collection.insert_one(rollback_doc)

        # Update the YAML file on disk
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(doc['config'], f, default_flow_style=False)

        print(f"Rollback complete. Config.yaml updated to version {version}.")
        return True, f"Rolled back to version {version} as new version {next_version} and updated config.yaml"
    except Exception as e:
        return False, str(e)

# ====================
# Watchdog Event Handler
# ====================
class ConfigFileHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if os.path.abspath(event.src_path) == os.path.abspath(CONFIG_FILE):
            print(f"\nDetected changes in {CONFIG_FILE}. Updating MongoDB...")
            data = read_config(CONFIG_FILE)
            if data:
                data = convert_numeric_values(data)
                save_to_mongo(data)

# ====================
# Flask API
# ====================
app = Flask(__name__)

@app.route('/config', methods=['GET'])
def get_latest_config():
    data = fetch_latest_from_mongo()
    return jsonify(data)

@app.route('/config/history', methods=['GET'])
def get_config_history():
    data = fetch_all_versions()
    return jsonify(data)

@app.route('/config/all', methods=['GET'])
def view_all_configs():
    """View all existing records in MongoDB"""
    records = fetch_all_versions()
    return jsonify(records)

@app.route('/config/rollback/<int:version>', methods=['POST'])
def rollback(version):
    success, msg = rollback_to_version(version)
    return jsonify({"success": success, "message": msg})

# ====================
# Main Execution
# ====================
if __name__ == "__main__":
    # Initial load
    data = read_config(CONFIG_FILE)
    if data:
        data = convert_numeric_values(data)
        save_to_mongo(data)

        print("Initial Configuration:")
        for section, kv in data.items():
            print(f"\n{section}:")
            for k, v in kv.items():
                print(f"- {k}: {v}")

    # Watchdog to auto-update
    event_handler = ConfigFileHandler()
    observer = Observer()
    observer.schedule(event_handler, path=os.path.dirname(os.path.abspath(CONFIG_FILE)) or '.', recursive=False)
    observer.start()
    print(f"\nWatching {CONFIG_FILE} for changes...")

    try:
        app.run(debug=True, use_reloader=False)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
