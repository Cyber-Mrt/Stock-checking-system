# config.py
import os
import sys
import json

# -----------------------------
# Kaynak yolu (PyInstaller uyumlu)
# -----------------------------
def resource_path(rel_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, rel_path)

# -----------------------------
# Uygulama dizinleri / dosyalar
# -----------------------------
# Windows için AppData\Local, diğer platformlarda HOME altı
LOCAL_APPDATA = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
APP_DIR = os.path.join(LOCAL_APPDATA, "ComponentTracker")
os.makedirs(APP_DIR, exist_ok=True)

# Ayar dosyası
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".component_tracker_settings.json")
DEFAULT_SETTINGS = {
    "window_size": (1300, 750),
    "column_widths": {},
    "theme": "dark",
}

def load_settings():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return DEFAULT_SETTINGS.copy()

def save_settings(settings: dict) -> None:
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

# -----------------------------
# Veritabanı
# -----------------------------
DB_NAME = "components.db"
# Uygulama klasörü yerine proje kökünde tutmak istersen:
DB_FILE = os.path.join(os.path.dirname(__file__), DB_NAME)
# db_handler zaten kendi yolunu kullanıyorsa DB_FILE’ı yalnızca referans amaçlı bırak.

# -----------------------------
# Sütunlar (DB SIRASIYLA)
# ÖNEMLİ: Bu sıra veritabanı şemanla birebir aynı olmalı.
# -----------------------------
COLUMNS = (
    "id",
    "name",
    "category",
    "drawer_code",
    "quantity",
    "datasheet",
    "description",
    "added_date",
    "image_path",
)

# Başlıklar (Treeview)
COLUMN_TITLES = {
    "id": "ID",
    "name": "NAME",
    "category": "CATEGORY",
    "drawer_code": "DRAWER CODE",
    "quantity": "QUANTITY",
    "datasheet": "DATASHEET",
    "description": "DESCRIPTION",
    "added_date": "ADDED DATE",
    "image_path": "IMAGE",  # genelde gizli
}

# Genişlikler (istediğini özelleştir)
COLUMN_WIDTHS = {
    "id": 40,
    "name": 180,
    "category": 120,
    "drawer_code": 120,
    "quantity": 70,
    "datasheet": 180,
    "description": 220,
    "added_date": 110,
    "image_path": 160,
}

# Form etiketleri
FORM_LABELS = {
    "name": "Name*",
    "category": "Category",
    "drawer_code": "Drawer Code*",
    "quantity": "Quantity*",
    "datasheet": "Datasheet",
    "description": "Description",
    "image_path": "Image Path",
    "added_date": "Added Date (YYYY-MM-DD)",
}

# -----------------------------
# Görsel önizleme
# -----------------------------
IMAGE_PREVIEW_SIZE = (200, 200)

# -----------------------------
# İş mantığı ayarları
# -----------------------------
LOW_STOCK_THRESHOLD = 2

# -----------------------------
# QR ayarları (termal yazıcı dostu)
# -----------------------------
QR_DEFAULT_SCALE = 4          # ~8-10 box_size termal için iyi başlar
QR_BORDER = 2                 # kenar boşluğu (modül sayısı)
# Etiket dosya adı formatı (PNG). Güvenli dosya adı için main_app sanitize ediyor.
QR_FILENAME_FORMAT = "QR_{drawer_code}_{name}_{id}.png"

# --- QR payload görünümü ---
# "pretty": Satırlı, okunaklı metin | "json": JSON string
QR_PAYLOAD_STYLE = "pretty"

# Pretty moda özel şablon (istediğin gibi düzenleyebilirsin)
QR_PRETTY_TEMPLATE = (
    "{name}  |  {drawer_code}\n"
    "Qty: {quantity}    ID: {id}\n"
    "Cat: {category}\n"
    "Added: {added_date}\n"
    "ComponentTracker"
)