import sqlite3
import os

DB_FOLDER = 'data'
DB_NAME = 'reading_tracker.db'
DB_PATH = os.path.join(DB_FOLDER, DB_NAME)

def create_database():
    os.makedirs(DB_FOLDER, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    print(f"Database connection established. Rebuilding tables with FINAL schema...")

    # We use 'IF NOT EXISTS' to be safe, but deleting the old DB is recommended.
    
    # GlobalSettings Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS GlobalSettings (
        setting_id INTEGER PRIMARY KEY CHECK (setting_id = 1),
        minutes_per_point_common INTEGER NOT NULL, minutes_per_point_other INTEGER NOT NULL,
        finish_common_book_points INTEGER NOT NULL, finish_other_book_points INTEGER NOT NULL,
        quote_common_book_points INTEGER NOT NULL, quote_other_book_points INTEGER NOT NULL,
        attend_discussion_points INTEGER NOT NULL, no_log_days_trigger INTEGER NOT NULL,
        no_log_initial_penalty INTEGER NOT NULL, no_log_subsequent_penalty INTEGER NOT NULL,
        no_quote_days_trigger INTEGER NOT NULL, no_quote_initial_penalty INTEGER NOT NULL,
        no_quote_subsequent_penalty INTEGER NOT NULL
    );
    """)
    cursor.execute("SELECT COUNT(*) FROM GlobalSettings")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO GlobalSettings VALUES (1, 10, 5, 50, 25, 3, 1, 25, 3, 10, 2, 3, 5, 1);")

    # Other Core Tables
    cursor.execute("CREATE TABLE IF NOT EXISTS Members (member_id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);")
    cursor.execute("CREATE TABLE IF NOT EXISTS Books (book_id INTEGER PRIMARY KEY, title TEXT NOT NULL UNIQUE, author TEXT, publication_year INTEGER);")
    cursor.execute("CREATE TABLE IF NOT EXISTS ChallengePeriods (period_id INTEGER PRIMARY KEY, start_date TEXT NOT NULL, end_date TEXT NOT NULL, common_book_id INTEGER NOT NULL, FOREIGN KEY (common_book_id) REFERENCES Books (book_id));")
    cursor.execute("CREATE TABLE IF NOT EXISTS ChallengeSpecificRules (rule_id INTEGER PRIMARY KEY, period_id INTEGER NOT NULL UNIQUE, minutes_per_point_common INTEGER, minutes_per_point_other INTEGER, finish_common_book_points INTEGER, finish_other_book_points INTEGER, quote_common_book_points INTEGER, quote_other_book_points INTEGER, attend_discussion_points INTEGER, FOREIGN KEY (period_id) REFERENCES ChallengePeriods (period_id));")
    cursor.execute("CREATE TABLE IF NOT EXISTS ReadingLogs (log_id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL UNIQUE, member_id INTEGER NOT NULL, submission_date TEXT NOT NULL, common_book_minutes INTEGER DEFAULT 0, other_book_minutes INTEGER DEFAULT 0, submitted_common_quote INTEGER DEFAULT 0, submitted_other_quote INTEGER DEFAULT 0, FOREIGN KEY (member_id) REFERENCES Members (member_id));")

    # --- THE FIX IS HERE: Achievements table now has period_id ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Achievements (
        achievement_id INTEGER PRIMARY KEY,
        member_id INTEGER NOT NULL,
        period_id INTEGER, -- ADDED THIS COLUMN
        book_id INTEGER,
        achievement_type TEXT NOT NULL,
        achievement_date TEXT NOT NULL,
        FOREIGN KEY (member_id) REFERENCES Members (member_id),
        FOREIGN KEY (period_id) REFERENCES ChallengePeriods (period_id), -- ADDED THIS CONSTRAINT
        FOREIGN KEY (book_id) REFERENCES Books (book_id)
    );
    """)
    print("- 'Achievements' table created correctly with 'period_id'.")

    # Stats Tables
    cursor.execute("CREATE TABLE IF NOT EXISTS MemberStats (member_id INTEGER PRIMARY KEY, total_points INTEGER DEFAULT 0, total_reading_minutes_common INTEGER DEFAULT 0, total_reading_minutes_other INTEGER DEFAULT 0, total_common_books_read INTEGER DEFAULT 0, total_other_books_read INTEGER DEFAULT 0, total_quotes_submitted INTEGER DEFAULT 0, meetings_attended INTEGER DEFAULT 0, FOREIGN KEY (member_id) REFERENCES Members (member_id));")
    cursor.execute("CREATE TABLE IF NOT EXISTS GroupStats (period_id INTEGER PRIMARY KEY, total_group_minutes_common INTEGER DEFAULT 0, total_group_minutes_other INTEGER DEFAULT 0, total_group_quotes_common INTEGER DEFAULT 0, total_group_quotes_other INTEGER DEFAULT 0, active_members INTEGER DEFAULT 0, FOREIGN KEY (period_id) REFERENCES ChallengePeriods (period_id));")

    conn.commit()
    conn.close()
    
    print("\nDatabase setup complete!")

if __name__ == '__main__':
    create_database()
