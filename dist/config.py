# config.py

import json, os

# Bu satırı config.py dosyanıza ekleyin
IMAGE_PREVIEW_SIZE = (200, 200)

# AppData dizini içinde özel klasör oluştur
APP_DIR = os.path.join(os.getenv("LOCALAPPDATA"), "ComponentTracker")
os.makedirs(APP_DIR, exist_ok=True)

SETTINGS_FILE = "settings.json"
DEFAULT_SETTINGS = {
    "window_size": (1300, 750),
    "column_widths": {}
}

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        return json.load(open(SETTINGS_FILE))
    return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)

DB_NAME = "components.db"

# Define columns in the order they appear in the database and Treeview
COLUMNS = ("id", "name", "category", "drawer_code", "quantity", "datasheet", "description", "added_date", "image_path")

# Display names for Treeview headings
COLUMN_TITLES = {
    "id": "ID",
    "name": "NAME",
    "category": "CATEGORY",
    "drawer_code": "DRAWER CODE",
    "quantity": "QUANTITY",
    "datasheet": "DATASHEET",
    "description": "DESCRIPTION",
    "added_date": "ADDED DATE",
    "image_path": "IMAGE" # Hidden by default, but defined
}

# Widths for Treeview columns
COLUMN_WIDTHS = {
    "id": 40,
    "name": 150,
    "category": 100,
    "drawer_code": 100,
    "quantity": 60,
    "datasheet": 150,
    "description": 200,
    "added_date": 90
}

# Labels for the input form. The key is what we use in code, the value is the display text.
FORM_LABELS = {
    "name": "Name*",
    "category": "Category",
    "drawer_code": "Drawer Code*",
    "quantity": "Quantity*",
    "datasheet": "Datasheet",
    "description": "Description",
    "image_path": "Image Path"
}