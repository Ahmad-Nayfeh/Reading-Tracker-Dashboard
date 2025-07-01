import sqlite3
import os

DB_FOLDER = 'data'
DB_NAME = 'reading_tracker.db'
DB_PATH = os.path.join(DB_FOLDER, DB_NAME)

def create_database():
    """
    Sets up or updates the database schema.
    It creates all necessary tables for the application to function
    and adds the 'is_active' column to the Members table if it doesn't exist.
    """
    os.makedirs(DB_FOLDER, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    print(f"Database connection established. Building schema...")

    # --- App Settings Table ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS AppSettings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)
    cursor.execute("INSERT OR IGNORE INTO AppSettings (key, value) VALUES ('spreadsheet_url', '')")
    cursor.execute("INSERT OR IGNORE INTO AppSettings (key, value) VALUES ('form_url', '')")
    cursor.execute("INSERT OR IGNORE INTO AppSettings (key, value) VALUES ('form_id', '')")
    cursor.execute("INSERT OR IGNORE INTO AppSettings (key, value) VALUES ('member_question_id', '')")

    # --- Members Table (with is_active column) ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Members (
        member_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        is_active INTEGER NOT NULL DEFAULT 1
    );
    """)

    # --- Core Tables ---
    cursor.execute("CREATE TABLE IF NOT EXISTS GlobalSettings (setting_id INTEGER PRIMARY KEY, minutes_per_point_common INTEGER, minutes_per_point_other INTEGER, finish_common_book_points INTEGER, finish_other_book_points INTEGER, quote_common_book_points INTEGER, quote_other_book_points INTEGER, attend_discussion_points INTEGER, no_log_days_trigger INTEGER, no_log_initial_penalty INTEGER, no_log_subsequent_penalty INTEGER, no_quote_days_trigger INTEGER, no_quote_initial_penalty INTEGER, no_quote_subsequent_penalty INTEGER);")
    cursor.execute("SELECT COUNT(*) FROM GlobalSettings")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO GlobalSettings VALUES (1, 10, 5, 50, 25, 3, 1, 25, 3, 10, 2, 3, 5, 1);")
    
    cursor.execute("CREATE TABLE IF NOT EXISTS Books (book_id INTEGER PRIMARY KEY, title TEXT NOT NULL UNIQUE, author TEXT, publication_year INTEGER);")
    cursor.execute("CREATE TABLE IF NOT EXISTS ChallengePeriods (period_id INTEGER PRIMARY KEY, start_date TEXT NOT NULL, end_date TEXT NOT NULL, common_book_id INTEGER NOT NULL, FOREIGN KEY (common_book_id) REFERENCES Books (book_id));")
    cursor.execute("CREATE TABLE IF NOT EXISTS ReadingLogs (log_id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL UNIQUE, member_id INTEGER NOT NULL, submission_date TEXT NOT NULL, common_book_minutes INTEGER DEFAULT 0, other_book_minutes INTEGER DEFAULT 0, submitted_common_quote INTEGER DEFAULT 0, submitted_other_quote INTEGER DEFAULT 0, FOREIGN KEY (member_id) REFERENCES Members (member_id));")
    cursor.execute("CREATE TABLE IF NOT EXISTS Achievements (achievement_id INTEGER PRIMARY KEY, member_id INTEGER NOT NULL, period_id INTEGER, book_id INTEGER, achievement_type TEXT NOT NULL, achievement_date TEXT NOT NULL, FOREIGN KEY (member_id) REFERENCES Members (member_id), FOREIGN KEY (period_id) REFERENCES ChallengePeriods (period_id), FOREIGN KEY (book_id) REFERENCES Books (book_id));")

    # --- Stats Tables ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS MemberStats (
        member_id INTEGER PRIMARY KEY,
        total_points INTEGER DEFAULT 0,
        total_reading_minutes_common INTEGER DEFAULT 0,
        total_reading_minutes_other INTEGER DEFAULT 0,
        total_common_books_read INTEGER DEFAULT 0,
        total_other_books_read INTEGER DEFAULT 0,
        total_quotes_submitted INTEGER DEFAULT 0,
        meetings_attended INTEGER DEFAULT 0,
        last_log_date TEXT,
        last_quote_date TEXT,
        log_streak INTEGER DEFAULT 0,
        quote_streak INTEGER DEFAULT 0,
        FOREIGN KEY (member_id) REFERENCES Members (member_id)
    );
    """)
    cursor.execute("CREATE TABLE IF NOT EXISTS GroupStats (period_id INTEGER PRIMARY KEY, total_group_minutes_common INTEGER DEFAULT 0, total_group_minutes_other INTEGER DEFAULT 0, total_group_quotes_common INTEGER DEFAULT 0, total_group_quotes_other INTEGER DEFAULT 0, active_members INTEGER DEFAULT 0, FOREIGN KEY (period_id) REFERENCES ChallengePeriods (period_id));")
    
    cursor.execute("DROP TABLE IF EXISTS ChallengeSpecificRules")

    conn.commit()
    conn.close()
    print("\nDatabase setup complete! 'Members' table is ready for activation status.")

if __name__ == '__main__':
    create_database()
