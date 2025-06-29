import sqlite3
import os

DB_FOLDER = 'data'
DB_NAME = 'reading_tracker.db'
DB_PATH = os.path.join(DB_FOLDER, DB_NAME)

def get_db_connection():
    """Establishes and returns a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- READ Functions ---

def load_global_settings():
    """Loads the single row of global settings from the database."""
    conn = get_db_connection()
    settings_row = conn.execute("SELECT * FROM GlobalSettings WHERE setting_id = 1").fetchone()
    conn.close()
    return dict(settings_row) if settings_row else None

def get_all_data_for_stats():
    """Fetches all data needed for the calculation engine in one go."""
    conn = get_db_connection()
    members = [dict(row) for row in conn.execute("SELECT * FROM Members").fetchall()]
    logs = [dict(row) for row in conn.execute("SELECT * FROM ReadingLogs").fetchall()]
    achievements = [dict(row) for row in conn.execute("SELECT * FROM Achievements").fetchall()]
    periods = [dict(row) for row in conn.execute("SELECT cp.*, b.title FROM ChallengePeriods cp JOIN Books b ON cp.common_book_id = b.book_id").fetchall()]
    conn.close()
    return {
        "members": members,
        "logs": logs,
        "achievements": achievements,
        "periods": periods
    }

def check_log_exists(timestamp):
    """Checks if a log with a specific timestamp already exists."""
    conn = get_db_connection()
    log_exists = conn.execute("SELECT 1 FROM ReadingLogs WHERE timestamp = ?", (timestamp,)).fetchone()
    conn.close()
    return log_exists is not None

def has_achievement(member_id, achievement_type, period_id):
    """Checks if a member already has a specific achievement within a challenge period."""
    conn = get_db_connection()
    query = "SELECT 1 FROM Achievements WHERE member_id = ? AND achievement_type = ? AND period_id = ?"
    achievement_exists = conn.execute(query, (member_id, achievement_type, period_id)).fetchone()
    conn.close()
    return achievement_exists is not None

def did_submit_quote_today(member_id, submission_date, quote_type):
    """Checks if a member has already submitted a specific type of quote today."""
    conn = get_db_connection()
    column_to_check = "submitted_common_quote" if quote_type == 'COMMON' else "submitted_other_quote"
    query = f"SELECT 1 FROM ReadingLogs WHERE member_id = ? AND submission_date = ? AND {column_to_check} = 1"
    quote_exists = conn.execute(query, (member_id, submission_date)).fetchone()
    conn.close()
    return quote_exists is not None

# --- WRITE Functions ---

def add_members(names_list):
    """Adds a list of members to the database."""
    conn = get_db_connection()
    with conn:
        conn.executemany("INSERT INTO Members (name) VALUES (?)", [(name,) for name in names_list])
    conn.close()

def add_book_and_challenge(book_info, challenge_info):
    """Adds a new book and a new challenge period in a single transaction."""
    conn = get_db_connection()
    try:
        with conn:
            # 1. Add the book
            cursor = conn.execute("INSERT INTO Books (title, author, publication_year) VALUES (?, ?, ?)", 
                                  (book_info['title'], book_info['author'], book_info['year']))
            book_id = cursor.lastrowid
            
            # 2. Add the challenge period
            conn.execute("INSERT INTO ChallengePeriods (start_date, end_date, common_book_id) VALUES (?, ?, ?)",
                         (challenge_info['start_date'], challenge_info['end_date'], book_id))
    except sqlite3.Error as e:
        print(f"Transaction failed: {e}")
        return False
    finally:
        conn.close()
    return True

def add_log_and_achievements(log_data, achievements_to_add):
    """A transactional function to add a log and its related achievements together."""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("INSERT INTO ReadingLogs (timestamp, member_id, submission_date, common_book_minutes, other_book_minutes, submitted_common_quote, submitted_other_quote) VALUES (:timestamp, :member_id, :submission_date, :common_book_minutes, :other_book_minutes, :submitted_common_quote, :submitted_other_quote)", log_data)
            if achievements_to_add:
                conn.executemany("INSERT INTO Achievements (member_id, achievement_type, achievement_date, period_id, book_id) VALUES (?, ?, ?, ?, ?)", achievements_to_add)
    except sqlite3.Error as e:
        print(f"Transaction failed: {e}")
    finally:
        conn.close()

def rebuild_stats_tables(member_stats_data, group_stats_data):
    """Clears and rebuilds the stats tables with freshly calculated data."""
    conn = get_db_connection()
    with conn:
        conn.execute("DELETE FROM MemberStats;")
        conn.execute("DELETE FROM GroupStats;")
        if member_stats_data:
            conn.executemany("INSERT INTO MemberStats (member_id, total_points, total_reading_minutes_common, total_reading_minutes_other, total_common_books_read, total_other_books_read, total_quotes_submitted, meetings_attended) VALUES (:member_id, :total_points, :total_reading_minutes_common, :total_reading_minutes_other, :total_common_books_read, :total_other_books_read, :total_quotes_submitted, :meetings_attended)", member_stats_data)
        if group_stats_data:
             conn.executemany("INSERT INTO GroupStats (period_id, total_group_minutes_common, total_group_minutes_other, total_group_quotes_common, total_group_quotes_other, active_members) VALUES (:period_id, :total_group_minutes_common, :total_group_minutes_other, :total_group_quotes_common, :total_group_quotes_other, :active_members)", group_stats_data)
    print(f"Successfully rebuilt stats tables.")
