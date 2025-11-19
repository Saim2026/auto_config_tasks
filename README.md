# Auto_Config_Save Version-02

This script reads and monitors a YAML configuration file for changes,
saves its contents to a MongoDB database with versioning,
and provides a Flask API to retrieve the latest and historical configurations.
This also prevents the duplication of configurations being inserted in mongodb.

## Required Libraries: 
- pyyaml 
- pymongo
- flask
- watchdog

## To install:
run: pip install -r requirements.txt


## NEW FEATURES ADDED in Version-02

- YAML config parsing and numeric conversion

- MongoDB versioning with duplicate prevention across all records

- Rollback functionality that also updates the YAML file on disk

- Watchdog auto-update

### Flask API endpoints:

- /config → latest version

- /config/history → all versions in order

- /config/all → view all existing records in the database

### Browser Usage

Latest config: http://127.0.0.1:5000/config

All versions: http://127.0.0.1:5000/config/history

Full MongoDB view: http://127.0.0.1:5000/config/all
