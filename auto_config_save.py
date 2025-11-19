# This script reads and monitors a YAML configuration file for changes,
# saves its contents to a MongoDB database with versioning,
# and provides a Flask API to retrieve the latest and historical configurations.

# Required Libraries: pyyaml, pymongo, flask, watchdog
# To install, run: pip install -r requirements.txt

import yaml
from datetime import datetime
from flask import Flask, jsonify
from pymongo import MongoClient
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os

# ====================
# Configuration
# ====================
CONFIG_FILE = r'C:\auto_config_save\config.yaml'
SECRETS_FILE = r'C:\auto_config_save\secrets.yaml'
DB_NAME = 'config_db'
COLLECTION_NAME = 'config_data'

# ====================
# Load Secrets
# ====================
def load_secrets(secret_file):
    """Load secrets from a YAML file"""
    abs_path = os.path.abspath(secret_file)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Secrets file not found: {abs_path}")
    try:
        with open(abs_path, 'r') as f:
            secrets = yaml.safe_load(f)
        mongo_uri = secrets.get("mongo", {}).get("uri", "")
        if not mongo_uri:
            raise ValueError("MongoDB URI not found in secrets.yaml")
        return mongo_uri
    except Exception as e:
        raise RuntimeError(f"Error loading secrets: {e}")

# Load MongoDB URI securely
MONGO_URI = load_secrets(SECRETS_FILE)

# ====================
# Config Handling
# ====================
def read_config(file_path):
    """Read YAML configuration file"""
    try:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        print('\nConfiguration File Parser Results:\n')
        return data
    except Exception as e:
        print(f"Error reading YAML file: {e}")
        return None

def convert_numeric_values(data):
    """Recursively convert numeric strings to integers"""
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
    """Save configuration to MongoDB with versioning"""
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]

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
    """Fetch the latest configuration version"""
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
    """Fetch all configuration versions"""
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]

        docs = []
        for doc in collection.find().sort("version", 1):
            docs.append({
                "version": doc["version"],
                "timestamp": doc["timestamp"].isoformat(),
                "config": doc["config"]
            })
        return docs
    except Exception as e:
        print(f"Error fetching from MongoDB: {e}")
        return []

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

# End of File
# To view in browser: http://127.0.0.1:5000/config
# To view history in browser: http://127.0.0.1:5000/config/history

