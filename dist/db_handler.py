# db_handler.py
import sqlite3
import datetime
from config import DB_NAME, COLUMNS, APP_DIR
import os
import shutil
import sqlite3
import config

# AppData klasörünü kullan
LOCAL_DB_PATH = os.path.join(APP_DIR, DB_NAME)
ORIGINAL_DB_PATH = os.path.join(os.path.dirname(__file__), DB_NAME)

# Modül seviyesinde bir kez bağlantı aç
conn = sqlite3.connect(config.DB_FILE)
conn.row_factory = sqlite3.Row  # istersen kolay dict-okuma için

# Eğer AppData'da yoksa, orijinal veritabanını kopyala
if not os.path.exists(LOCAL_DB_PATH):
    try:
        shutil.copy(ORIGINAL_DB_PATH, LOCAL_DB_PATH)
        print("Veritabanı AppData dizinine kopyalandı.")
    except Exception as e:
        print(f"Veritabanı kopyalanamadı: {e}")

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

def create_connection():
    try:
        return sqlite3.connect(LOCAL_DB_PATH)
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        return None

def execute_query(query, params=(), fetch=None):
    """A central function to execute database queries."""
    with create_connection() as conn:
        if conn is None:
            return None if fetch else False
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            if fetch == "one":
                return cursor.fetchone()
            if fetch == "all":
                return cursor.fetchall()
            conn.commit()
            return True # Indicates success for non-fetch queries
        except sqlite3.Error as e:
            print(f"Query failed: {e}")
            return None if fetch else False


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
    """Fetches all components from the database."""
    query = f"SELECT {', '.join(COLUMNS)} FROM components ORDER BY {order_by}"
    return execute_query(query, fetch="all")

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