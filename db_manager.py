import sqlite3
import os

# --- Constants ---
DB_FOLDER = 'data'
DB_NAME = 'reading_tracker.db'
DB_PATH = os.path.join(DB_FOLDER, DB_NAME)

def get_db_connection():
    """
    ينشئ اتصالاً بقاعدة البيانات ويعيده.
    نستخدم row_factory للتمكن من الوصول للأعمدة عبر أسمائها.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- READ Functions ---

def load_global_settings():
    """يجلب صف الإعدادات العامة الوحيد من قاعدة البيانات."""
    try:
        conn = get_db_connection()
        settings_row = conn.execute("SELECT * FROM GlobalSettings WHERE setting_id = 1").fetchone()
        conn.close()
        return dict(settings_row) if settings_row else None
    except sqlite3.Error as e:
        print(f"Database error while loading settings: {e}")
        return None

def get_all_members():
    """يجلب جميع الأعضاء من جدول Members."""
    try:
        conn = get_db_connection()
        members = conn.execute("SELECT * FROM Members ORDER BY name").fetchall()
        conn.close()
        return [dict(row) for row in members]
    except sqlite3.Error as e:
        print(f"Database error while fetching members: {e}")
        return []

def get_challenge_periods():
    """يجلب جميع فترات التحدي مع معلومات كتبها."""
    try:
        conn = get_db_connection()
        query = """
        SELECT cp.*, b.title, b.author, b.publication_year
        FROM ChallengePeriods cp
        JOIN Books b ON cp.common_book_id = b.book_id
        ORDER BY cp.start_date DESC
        """
        periods = conn.execute(query).fetchall()
        conn.close()
        return [dict(row) for row in periods]
    except sqlite3.Error as e:
        print(f"Database error while fetching challenge periods: {e}")
        return []

# --- WRITE Functions ---

def add_members(names_list):
    """يضيف قائمة من الأعضاء إلى قاعدة البيانات."""
    conn = get_db_connection()
    try:
        with conn:
            conn.executemany("INSERT INTO Members (name) VALUES (?)", [(name,) for name in names_list])
    finally:
        conn.close()

def add_book(title, author, year):
    """يضيف كتاباً جديداً ويعيد الـ ID الخاص به."""
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.execute(
                "INSERT INTO Books (title, author, publication_year) VALUES (?, ?, ?)",
                (title, author, year)
            )
            return cursor.lastrowid # يعيد ID الصف الجديد الذي تم إضافته
    finally:
        conn.close()

def add_challenge_period(start_date, end_date, book_id):
    """يضيف فترة تحدي جديدة إلى قاعدة البيانات."""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                "INSERT INTO ChallengePeriods (start_date, end_date, common_book_id) VALUES (?, ?, ?)",
                (start_date, end_date, book_id)
            )
    finally:
        conn.close()


# --- Test block ---
if __name__ == '__main__':
    print("Testing db_manager functions...")
    settings = load_global_settings()
    if settings:
        print("\n--- Global Settings Loaded ---")
        print(f"Minutes per point (common book): {settings['minutes_per_point_common']}")
    
    members = get_all_members()
    if not members:
        print("\nNo members found yet.")
    else:
        print(f"\nFound {len(members)} members.")
    
    periods = get_challenge_periods()
    if not periods:
        print("\nNo challenge periods found yet. (This is expected)")

