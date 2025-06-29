import sqlite3
import os

DB_FOLDER = 'data'
DB_NAME = 'reading_tracker.db'
DB_PATH = os.path.join(DB_FOLDER, DB_NAME)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- READ Functions ---

def load_global_settings():
    conn = get_db_connection()
    settings_row = conn.execute("SELECT * FROM GlobalSettings WHERE setting_id = 1").fetchone()
    conn.close()
    return dict(settings_row) if settings_row else None

def get_all_members():
    conn = get_db_connection()
    members = conn.execute("SELECT * FROM Members ORDER BY name").fetchall()
    conn.close()
    return [dict(row) for row in members]

def get_all_reading_logs():
    conn = get_db_connection()
    logs = conn.execute("SELECT * FROM ReadingLogs").fetchall()
    conn.close()
    return [dict(row) for row in logs]
    
def get_all_achievements():
    conn = get_db_connection()
    achievements = conn.execute("SELECT * FROM Achievements").fetchall()
    conn.close()
    return [dict(row) for row in achievements]

# --- THE FIX IS HERE ---
def check_log_exists(timestamp):
    """Checks if a log with a specific timestamp already exists."""
    conn = get_db_connection()
    log_exists = conn.execute(
        "SELECT 1 FROM ReadingLogs WHERE timestamp = ?",
        (timestamp,)
    ).fetchone()
    conn.close()
    return log_exists is not None

# --- WRITE Functions ---

def add_reading_log(log_data):
    conn = get_db_connection()
    with conn:
        conn.execute("""
            INSERT INTO ReadingLogs (timestamp, member_id, submission_date, common_book_minutes, 
                                     other_book_minutes, submitted_common_quote, submitted_other_quote)
            VALUES (:timestamp, :member_id, :submission_date, :common_book_minutes, :other_book_minutes,
                    :submitted_common_quote, :submitted_other_quote)
        """, log_data)
    conn.close()

def rebuild_stats_tables(member_stats_data):
    """Clears and rebuilds the stats tables with freshly calculated data."""
    conn = get_db_connection()
    with conn:
        conn.execute("DELETE FROM MemberStats;")
        conn.executemany("""
            INSERT INTO MemberStats (member_id, total_points, total_reading_minutes_common,
                                     total_reading_minutes_other, total_common_books_read,
                                     total_other_books_read, total_quotes_submitted, meetings_attended)
            VALUES (:member_id, :total_points, :total_reading_minutes_common,
                    :total_reading_minutes_other, :total_common_books_read,
                    :total_other_books_read, :total_quotes_submitted, :meetings_attended)
        """, member_stats_data)
    print(f"Successfully rebuilt stats for {len(member_stats_data)} members.")
    conn.close()
