# config.py

import json, os
import sys

def resource_path(relative_path):
    """
    PyInstaller --onefile veya --onedir modunda, dosyalar
    sys._MEIPASS içinde açılır. Geliştirme ortamında ise current dir.
    """
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)

# Mevcut sabitlerin yanında:
DB_NAME  = "components.db"
COLUMNS  = ["id", "name", "category", "drawer_code", "quantity", "datasheet", "description", "image_path", "added_date"]
APP_DIR  = os.path.join(os.path.expanduser("~"), "AppData", "Local", "ComponentTracker")

# Uygulama dizininde "components.db" adında bir SQLite dosyası kullan
DB_FILE = os.path.join(os.path.dirname(__file__), "components.db")

# Bu satırı config.py dosyanıza ekleyin
IMAGE_PREVIEW_SIZE = (200, 200)

# AppData dizini içinde özel klasör oluştur
APP_DIR = os.path.join(os.getenv("LOCALAPPDATA"), "ComponentTracker")
os.makedirs(APP_DIR, exist_ok=True)

SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".component_tracker_settings.json")
DEFAULT_SETTINGS = {
    "window_size": (1300, 750),
    "column_widths": {},
    "theme": "dark"  
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