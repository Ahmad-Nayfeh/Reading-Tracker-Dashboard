import sqlite3
import os
import pandas as pd

# --- Constants ---
DB_FOLDER = 'data'
DB_NAME = 'reading_tracker.db'
DB_PATH = os.path.join(DB_FOLDER, DB_NAME)

def get_db_connection():
    """Establishes and returns a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- NEW/UPDATED Functions for AppSettings ---

def set_setting(key, value):
    """
    Saves or updates a key-value pair in the AppSettings table.
    This is used to store the Google Sheet and Form URLs.
    The "INSERT OR REPLACE" command is a convenient way to handle both
    creation of a new setting and updating an existing one.
    """
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("INSERT OR REPLACE INTO AppSettings (key, value) VALUES (?, ?)", (key, str(value)))
    except sqlite3.Error as e:
        print(f"Database error in set_setting: {e}")
    finally:
        conn.close()

def get_setting(key):
    """
    Retrieves a value by its key from the AppSettings table.
    Returns the value if the key is found, otherwise returns None.
    """
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT value FROM AppSettings WHERE key = ?", (key,)).fetchone()
        return row['value'] if row and row['value'] else None
    except sqlite3.Error as e:
        print(f"Database error in get_setting: {e}")
        return None
    finally:
        conn.close()


# --- READ Functions (Existing, no changes needed) ---

def load_global_settings():
    """Loads the general rules of the challenge (points, penalties)."""
    conn = get_db_connection()
    try:
        settings_row = conn.execute("SELECT * FROM GlobalSettings WHERE setting_id = 1").fetchone()
        return dict(settings_row) if settings_row else None
    finally:
        conn.close()


def get_all_data_for_stats():
    """Fetches all data needed for the calculation engine in one go for efficiency."""
    conn = get_db_connection()
    try:
        members = [dict(row) for row in conn.execute("SELECT * FROM Members ORDER BY name").fetchall()]
        logs = [dict(row) for row in conn.execute("SELECT * FROM ReadingLogs").fetchall()]
        achievements = [dict(row) for row in conn.execute("SELECT * FROM Achievements").fetchall()]
        query = "SELECT cp.*, b.title, b.author, b.publication_year FROM ChallengePeriods cp JOIN Books b ON cp.common_book_id = b.book_id ORDER BY cp.start_date DESC"
        periods = [dict(row) for row in conn.execute(query).fetchall()]
    
    except sqlite3.Error as e:
        print(f"Error fetching all data from database: {e}")
        return None
    finally:
        conn.close()
    
    return {"members": members, "logs": logs, "achievements": achievements, "periods": periods}

def get_table_as_df(table_name):
    """Fetches an entire table and returns it as a Pandas DataFrame."""
    conn = get_db_connection()
    try:
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    except Exception as e:
        print(f"Error reading table {table_name}: {e}")
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

def check_log_exists(timestamp):
    conn = get_db_connection()
    log_exists = conn.execute("SELECT 1 FROM ReadingLogs WHERE timestamp = ?", (timestamp,)).fetchone()
    conn.close()
    return log_exists is not None

def has_achievement(member_id, achievement_type, period_id):
    conn = get_db_connection()
    query = "SELECT 1 FROM Achievements WHERE member_id = ? AND achievement_type = ? AND period_id = ?"
    achievement_exists = conn.execute(query, (member_id, achievement_type, period_id)).fetchone()
    conn.close()
    return achievement_exists is not None

def did_submit_quote_today(member_id, submission_date, quote_type):
    conn = get_db_connection()
    column_to_check = "submitted_common_quote" if quote_type == 'COMMON' else "submitted_other_quote"
    query = f"SELECT 1 FROM ReadingLogs WHERE member_id = ? AND submission_date = ? AND {column_to_check} = 1"
    quote_exists = conn.execute(query, (member_id, submission_date)).fetchone()
    conn.close()
    return quote_exists is not None

# --- WRITE Functions (Existing, no changes needed) ---

def add_members(names_list):
    conn = get_db_connection()
    with conn:
        conn.executemany("INSERT INTO Members (name) VALUES (?)", [(name,) for name in names_list])
    conn.close()

def add_book_and_challenge(book_info, challenge_info):
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.execute("INSERT INTO Books (title, author, publication_year) VALUES (?, ?, ?)", (book_info['title'], book_info['author'], book_info['year']))
            book_id = cursor.lastrowid
            conn.execute("INSERT INTO ChallengePeriods (start_date, end_date, common_book_id) VALUES (?, ?, ?)", (challenge_info['start_date'], challenge_info['end_date'], book_id))
        return True
    finally:
        conn.close()

def add_log_and_achievements(log_data, achievements_to_add):
    conn = get_db_connection()
    with conn:
        conn.execute("INSERT INTO ReadingLogs (timestamp, member_id, submission_date, common_book_minutes, other_book_minutes, submitted_common_quote, submitted_other_quote) VALUES (:timestamp, :member_id, :submission_date, :common_book_minutes, :other_book_minutes, :submitted_common_quote, :submitted_other_quote)", log_data)
        if achievements_to_add:
            conn.executemany("INSERT INTO Achievements (member_id, achievement_type, achievement_date, period_id, book_id) VALUES (?, ?, ?, ?, ?)", achievements_to_add)
    conn.close()

def rebuild_stats_tables(member_stats_data, group_stats_data):
    conn = get_db_connection()
    with conn:
        conn.execute("DELETE FROM MemberStats;")
        conn.execute("DELETE FROM GroupStats;")
        if member_stats_data:
            conn.executemany("INSERT INTO MemberStats (member_id, total_points, total_reading_minutes_common, total_reading_minutes_other, total_common_books_read, total_other_books_read, total_quotes_submitted, meetings_attended, last_log_date, last_quote_date, log_streak, quote_streak) VALUES (:member_id, :total_points, :total_reading_minutes_common, :total_reading_minutes_other, :total_common_books_read, :total_other_books_read, :total_quotes_submitted, :meetings_attended, :last_log_date, :last_quote_date, :log_streak, :quote_streak)", member_stats_data)
        if group_stats_data:
             conn.executemany("INSERT INTO GroupStats (period_id, total_group_minutes_common, total_group_minutes_other, total_group_quotes_common, total_group_quotes_other, active_members) VALUES (:period_id, :total_group_minutes_common, :total_group_minutes_other, :total_group_quotes_common, :total_group_quotes_other, :active_members)", group_stats_data)
    conn.close()

def update_global_settings(settings_dict):
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                UPDATE GlobalSettings
                SET minutes_per_point_common = :minutes_per_point_common,
                    minutes_per_point_other = :minutes_per_point_other,
                    finish_common_book_points = :finish_common_book_points,
                    finish_other_book_points = :finish_other_book_points,
                    quote_common_book_points = :quote_common_book_points,
                    quote_other_book_points = :quote_other_book_points,
                    attend_discussion_points = :attend_discussion_points,
                    no_log_days_trigger = :no_log_days_trigger,
                    no_log_initial_penalty = :no_log_initial_penalty,
                    no_log_subsequent_penalty = :no_log_subsequent_penalty,
                    no_quote_days_trigger = :no_quote_days_trigger,
                    no_quote_initial_penalty = :no_quote_initial_penalty,
                    no_quote_subsequent_penalty = :no_quote_subsequent_penalty
                WHERE setting_id = 1
            """, settings_dict)
        return True
    except sqlite3.Error as e:
        print(f"Error updating settings: {e}")
        return False
    finally:
        conn.close()
