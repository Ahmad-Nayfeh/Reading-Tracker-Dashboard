import sqlite3
import os

# --- Constants ---
# تعريف مسار قاعدة البيانات ليكون متاحاً في كل المشروع
DB_FOLDER = 'data'
DB_NAME = 'reading_tracker.db'
DB_PATH = os.path.join(DB_FOLDER, DB_NAME)

def get_db_connection():
    """
    ينشئ اتصالاً بقاعدة البيانات ويعيده.
    نستخدم row_factory للتمكن من الوصول للأعمدة عبر أسمائها.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # This is a key line!
    return conn

def load_global_settings():
    """
    يجلب صف الإعدادات العامة الوحيد من قاعدة البيانات.
    يعيد قاموساً (dictionary) يحتوي على الإعدادات.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM GlobalSettings WHERE setting_id = 1")
        settings_row = cursor.fetchone()
        conn.close()
        
        if settings_row:
            # تحويل كائن الصف إلى قاموس لسهولة الاستخدام
            return dict(settings_row)
        else:
            print("ERROR: Global settings not found in the database!")
            return None
    except sqlite3.Error as e:
        print(f"Database error while loading settings: {e}")
        return None

def get_all_members():
    """
    يجلب جميع الأعضاء من جدول Members.
    يعيد قائمة من القواميس (list of dictionaries).
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Members ORDER BY name")
        members = cursor.fetchall()
        conn.close()
        return [dict(row) for row in members]
    except sqlite3.Error as e:
        print(f"Database error while fetching members: {e}")
        return []

# هذا الجزء مخصص للاختبار فقط.
# يمكننا تشغيل هذا الملف مباشرة لاختبار الدوال.
if __name__ == '__main__':
    print("Testing db_manager functions...")
    
    settings = load_global_settings()
    if settings:
        print("\n--- Default Global Settings Loaded ---")
        # طباعة بعض الإعدادات كمثال
        print(f"Minutes per point (common book): {settings['minutes_per_point_common']}")
        print(f"Points for finishing common book: {settings['finish_common_book_points']}")
    else:
        print("\nCould not load global settings.")
        
    members = get_all_members()
    if not members:
        print("\nNo members found in the database yet. (This is expected)")

