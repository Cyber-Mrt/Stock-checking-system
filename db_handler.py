# db_handler.py
import sqlite3
import datetime
from config import DB_NAME, COLUMNS, APP_DIR, resource_path
import os
import shutil
import sqlite3
import config

# db_handler.py en üstüne ekle:
import os

# config.APP_DIR ile gelen yolu kesin oluştur
os.makedirs(APP_DIR, exist_ok=True)
DEV_DB = os.path.join(APP_DIR, DB_NAME)
PKG_DB = resource_path(DB_NAME)

# Eğer APP_DIR’yi kullanmaya devam edeceksen:
LOCAL_DB_PATH = os.path.join(APP_DIR, DB_NAME)

# Ancak PyInstaller paketinden doğrudan exe yanından okumak için:
# LOCAL_DB_PATH = resource_path(DB_NAME)

ORIGINAL_DB_PATH = os.path.join(os.path.dirname(__file__), DB_NAME)
def get_db_path():
    # Eğer exe içinden çalışıyorsan PKG_DB varlığını öncelikle kontrol et
    if os.path.exists(PKG_DB):
        return PKG_DB
    # Yoksa geliştirme ortamındaki lokali kullan
    return DEV_DB

# Eğer AppData'da yoksa, orijinal veritabanını kopyala
if not os.path.exists(LOCAL_DB_PATH):
    try:
        shutil.copy(ORIGINAL_DB_PATH, LOCAL_DB_PATH)
        print("Veritabanı AppData dizinine kopyalandı.")
    except Exception as e:
        print(f"Veritabanı kopyalanamadı: {e}")

# Eğer geliştirme ortamında DB’nin APP_DIR’e kopyalanmasını istiyorsan:
if not os.path.exists(DEV_DB):
    try:
        shutil.copy(os.path.join(os.path.dirname(__file__), DB_NAME), DEV_DB)
        print("Dev DB kopyalandı:", DEV_DB)
    except Exception as e:
        print("Dev DB kopyalanamadı:", e)

def get_category_counts():
    """
    Her kategori için toplam quantity değerini döner:
      [ (kategori1, toplam_adet1), (kategori2, toplam_adet2), ... ]
    """
    # AppData içindeki gerçek DB dosyası:
    db_path = os.path.join(APP_DIR, DB_NAME)
    print(f"[DEBUG] get_category_counts connecting to: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT category, SUM(quantity) AS total_qty
          FROM components
         WHERE category IS NOT NULL
           AND category <> ''
         GROUP BY category
    """)
    rows = cursor.fetchall()
    conn.close()

    print(f"[DEBUG] get_category_counts returned: {rows}")
    return rows

def component_exists(name, drawer_code):
    """
    Aynı name + drawer_code ikilisiyle bir kayıt var mı diye bakar.
    Varsa True, yoksa False döner.
    """
    query = "SELECT 1 FROM components WHERE name = ? AND drawer_code = ?"
    row = execute_query(query, (name, drawer_code), fetch="one")
    return row is not None

def create_connection():
    db_path = get_db_path()
    try:
        return sqlite3.connect(db_path)
    except sqlite3.Error as e:
        print(f"[DB ERROR] Bağlanamadı: {db_path} — {e}")
        return None

def execute_query(query, params=(), fetch=None):
    conn = create_connection()
    if conn is None:
        # Bağlantı yoksa
        return [] if fetch == "all" else None
    try:
        cur = conn.cursor()
        cur.execute(query, params)
        if fetch == "one":
            return cur.fetchone()
        if fetch == "all":
            return cur.fetchall() or []   # kesinlikle liste dön
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"[SQL ERROR] {e} — Query: {query}")
        return [] if fetch == "all" else None


def setup_database():
    """
    1) components tablosunu oluşturur (eğer yoksa),
    2) mevcutsa eksik sütunları ekler.
    """
    conn = create_connection()
    if conn is None:
        print("Veritabanı açılamadı.")
        return

    cursor = conn.cursor()

    # 1) Tabloyu oluştur (image_path dahil)
    columns_sql = ", ".join([
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "name TEXT NOT NULL",
        "category TEXT",
        "drawer_code TEXT NOT NULL",
        "quantity INTEGER NOT NULL",
        "datasheet TEXT",
        "description TEXT",
        "added_date TEXT",
        "image_path TEXT"
    ])
    create_query = f"CREATE TABLE IF NOT EXISTS components ({columns_sql});"
    cursor.execute(create_query)

    # 2) Eğer tablo zaten varsa, sütun bilgisini al ve eksikse ekle
    cursor.execute("PRAGMA table_info(components);")
    existing_columns = [row[1] for row in cursor.fetchall()]

    if "image_path" not in existing_columns:
        cursor.execute("ALTER TABLE components ADD COLUMN image_path TEXT;")
        print("image_path sütunu eklendi.")

    conn.commit()
    conn.close()

# --- Component Data Functions ---

def get_all_components(order_by="name"):
    query = f"SELECT {', '.join(COLUMNS)} FROM components ORDER BY {order_by}"
    dbp = get_db_path()
    print(f"[DEBUG] get_all_components bağlanıyor: {dbp} (exists? {os.path.exists(dbp)})")
    rows = execute_query(query, fetch="all")
    print(f"[DEBUG] get_all_components döndü: {rows!r}")
    return rows


def add_component(data):
    """Adds a new component to the database."""
    query = """
        INSERT INTO components (name, category, drawer_code, quantity, datasheet, description, image_path, added_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        data['name'], data['category'], data['drawer_code'], data['quantity'],
        data['datasheet'], data['description'], data.get('image_path', ''),
        datetime.date.today().isoformat()
    )
    return execute_query(query, params)

def update_component(comp_id, data):
    """Updates an existing component in the database."""
    query = """
        UPDATE components
        SET name = ?, category = ?, drawer_code = ?, quantity = ?, 
            datasheet = ?, description = ?, image_path = ?
        WHERE id = ?
    """
    params = (
        data['name'], data['category'], data['drawer_code'], data['quantity'],
        data['datasheet'], data['description'], data.get('image_path', ''), comp_id
    )
    return execute_query(query, params)

def delete_component(comp_id):
    """Deletes a component from the database by its ID."""
    return execute_query("DELETE FROM components WHERE id = ?", (comp_id,))

def get_distinct_categories():
    """Gets all unique categories from the database."""
    query = "SELECT DISTINCT category FROM components WHERE category IS NOT NULL AND category != '' ORDER BY category"
    cats = execute_query(query, fetch="all")
    return [cat[0] for cat in cats] if cats else []

def search_components(search_term, category):
    """Searches and filters components."""
    query = f"SELECT {', '.join(COLUMNS)} FROM components WHERE (lower(name) LIKE ? OR lower(drawer_code) LIKE ?)"
    params = (f'%{search_term}%', f'%{search_term}%')

    if category != "All":
        query += " AND category = ?"
        params += (category,)

    query += " ORDER BY name"
    return execute_query(query, params, fetch="all")