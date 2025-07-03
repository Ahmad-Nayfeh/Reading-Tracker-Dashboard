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

# --- AppSettings Functions ---

def set_setting(key, value):
    """Saves or updates a key-value pair in the AppSettings table."""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("INSERT OR REPLACE INTO AppSettings (key, value) VALUES (?, ?)", (key, str(value)))
    except sqlite3.Error as e:
        print(f"Database error in set_setting: {e}")
    finally:
        conn.close()

def get_setting(key):
    """Retrieves a value by its key from the AppSettings table."""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT value FROM AppSettings WHERE key = ?", (key,)).fetchone()
        return row['value'] if row and row['value'] else None
    except sqlite3.Error as e:
        print(f"Database error in get_setting: {e}")
        return None
    finally:
        conn.close()

# --- READ Functions ---

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
        # Now fetches the is_active status as well
        members = [dict(row) for row in conn.execute("SELECT * FROM Members ORDER BY name").fetchall()]
        logs = [dict(row) for row in conn.execute("SELECT * FROM ReadingLogs").fetchall()]
        achievements = [dict(row) for row in conn.execute("SELECT * FROM Achievements").fetchall()]
        # --- MODIFIED: The query now fetches all columns, including the new rule columns ---
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

# --- WRITE/UPDATE Functions ---

def add_members(names_list):
    """Adds a list of new members, setting them as active by default."""
    conn = get_db_connection()
    with conn:
        # Inserts only the name, relying on the default value for is_active
        conn.executemany("INSERT OR IGNORE INTO Members (name) VALUES (?)", [(name,) for name in names_list])
    conn.close()

def add_single_member(name):
    """
    Adds a single new member or reactivates an existing inactive one.
    Returns a status tuple: (status_code, message)
    - 'added': New member was added.
    - 'reactivated': Existing member was reactivated.
    - 'exists': Member already exists and is active.
    - 'error': An error occurred.
    """
    conn = get_db_connection()
    try:
        with conn:
            # Check if the member exists by name (case-insensitive for robustness)
            cursor = conn.execute("SELECT member_id, is_active FROM Members WHERE name = ?", (name,))
            member = cursor.fetchone()
            
            if member:
                if member['is_active'] == 1:
                    return ('exists', f"العضو '{name}' موجود ونشط بالفعل.")
                else:
                    # Reactivate the member
                    conn.execute("UPDATE Members SET is_active = 1 WHERE member_id = ?", (member['member_id'],))
                    return ('reactivated', f"تمت إعادة تنشيط العضو '{name}' بنجاح.")
            else:
                # Add a new member, who will be active by default
                conn.execute("INSERT INTO Members (name) VALUES (?)", (name,))
                return ('added', f"تمت إضافة العضو الجديد '{name}' بنجاح.")
    except sqlite3.Error as e:
        return ('error', f"Database error: {e}")
    finally:
        conn.close()

def set_member_status(member_id, is_active: int):
    """
    Sets a member's status to active (1) or inactive (0).
    """
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("UPDATE Members SET is_active = ? WHERE member_id = ?", (is_active, member_id))
        return True
    except sqlite3.Error as e:
        print(f"Database error in set_member_status: {e}")
        return False
    finally:
        conn.close()

# --- CORRECTED: This function now consistently returns a tuple (bool, str) ---
def add_book_and_challenge(book_info, challenge_info, rules_info):
    """Adds a new book and a new challenge period with its specific rules."""
    conn = get_db_connection()
    try:
        with conn:
            # Add the book first
            cursor = conn.execute("INSERT INTO Books (title, author, publication_year) VALUES (?, ?, ?)",
                                  (book_info['title'], book_info['author'], book_info['year']))
            book_id = cursor.lastrowid

            # Prepare the data for the new challenge period, including all rules
            challenge_data = {
                'start_date': challenge_info['start_date'],
                'end_date': challenge_info['end_date'],
                'common_book_id': book_id,
                **rules_info  # Unpack the rules dictionary directly into the data
            }
            
            # Insert the new challenge with its rules
            conn.execute("""
                INSERT INTO ChallengePeriods (
                    start_date, end_date, common_book_id,
                    minutes_per_point_common, minutes_per_point_other,
                    finish_common_book_points, finish_other_book_points,
                    quote_common_book_points, quote_other_book_points,
                    attend_discussion_points, no_log_days_trigger,
                    no_log_initial_penalty, no_log_subsequent_penalty,
                    no_quote_days_trigger, no_quote_initial_penalty,
                    no_quote_subsequent_penalty
                ) VALUES (
                    :start_date, :end_date, :common_book_id,
                    :minutes_per_point_common, :minutes_per_point_other,
                    :finish_common_book_points, :finish_other_book_points,
                    :quote_common_book_points, :quote_other_book_points,
                    :attend_discussion_points, :no_log_days_trigger,
                    :no_log_initial_penalty, :no_log_subsequent_penalty,
                    :no_quote_days_trigger, :no_quote_initial_penalty,
                    :no_quote_subsequent_penalty
                )
            """, challenge_data)
        # On success, return a tuple
        return True, "تمت إضافة التحدي بنجاح."
    except sqlite3.Error as e:
        # On failure, also return a tuple
        if "UNIQUE constraint failed: Books.title" in str(e):
             return False, f"خطأ: كتاب بعنوان '{book_info['title']}' موجود بالفعل في قاعدة البيانات."
        print(f"Database error in add_book_and_challenge: {e}")
        return False, f"خطأ في قاعدة البيانات: {e}"
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

def delete_challenge(period_id):
    """Deletes a challenge period and associated data."""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("DELETE FROM Achievements WHERE period_id = ?", (period_id,))
            conn.execute("DELETE FROM GroupStats WHERE period_id = ?", (period_id,))
            cursor = conn.execute("SELECT common_book_id FROM ChallengePeriods WHERE period_id = ?", (period_id,))
            result = cursor.fetchone()
            if result:
                book_id = result['common_book_id']
                conn.execute("DELETE FROM ChallengePeriods WHERE period_id = ?", (period_id,))
                cursor = conn.execute("SELECT COUNT(*) FROM ChallengePeriods WHERE common_book_id = ?", (book_id,))
                if cursor.fetchone()[0] == 0:
                    conn.execute("DELETE FROM Books WHERE book_id = ?", (book_id,))
        return True
    except sqlite3.Error as e:
        print(f"Database error in delete_challenge: {e}")
        return False
    finally:
        conn.close()