import sqlite3
import os

# --- Configuration ---
DB_FOLDER = 'data'
DB_NAME = 'reading_tracker.db'
DB_PATH = os.path.join(DB_FOLDER, DB_NAME)

def create_database():
    """
    ينشئ قاعدة البيانات وجميع الجداول اللازمة بناءً على التصميم النهائي (V10).
    يقوم أيضًا بإضافة صف الإعدادات الافتراضية.
    يجب تشغيل هذا السكربت مرة واحدة فقط في بداية إعداد المشروع.
    """
    
    os.makedirs(DB_FOLDER, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print(f"Database connection established to '{DB_PATH}'. Creating tables...")

    # --- CORE DATA LAYER (The Engine Room) ---
    
    # 1. GlobalSettings Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS GlobalSettings (
        setting_id INTEGER PRIMARY KEY CHECK (setting_id = 1),
        minutes_per_point_common INTEGER NOT NULL,
        minutes_per_point_other INTEGER NOT NULL,
        finish_common_book_points INTEGER NOT NULL,
        finish_other_book_points INTEGER NOT NULL,
        quote_common_book_points INTEGER NOT NULL,
        quote_other_book_points INTEGER NOT NULL,
        attend_discussion_points INTEGER NOT NULL,
        no_log_days_trigger INTEGER NOT NULL,
        no_log_initial_penalty INTEGER NOT NULL,
        no_log_subsequent_penalty INTEGER NOT NULL,
        no_quote_days_trigger INTEGER NOT NULL,
        no_quote_initial_penalty INTEGER NOT NULL,
        no_quote_subsequent_penalty INTEGER NOT NULL
    );
    """)
    print("- 'GlobalSettings' table created or already exists.")

    # Insert default settings only if the table is empty
    cursor.execute("SELECT COUNT(*) FROM GlobalSettings")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO GlobalSettings VALUES (
            1, 10, 5, 50, 25, 3, 1, 25, 3, 10, 2, 3, 5, 1
        );
        """)
        print("  -> Default settings inserted into 'GlobalSettings'.")

    # 2. Members Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Members (
        member_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    );
    """)
    print("- 'Members' table created or already exists.")

    # 3. Books Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Books (
        book_id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL UNIQUE,
        author TEXT,
        publication_year INTEGER
    );
    """)
    print("- 'Books' table created or already exists.")

    # 4. ChallengePeriods Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ChallengePeriods (
        period_id INTEGER PRIMARY KEY AUTOINCREMENT,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        common_book_id INTEGER NOT NULL,
        FOREIGN KEY (common_book_id) REFERENCES Books (book_id)
    );
    """)
    print("- 'ChallengePeriods' table created or already exists.")

    # 5. ChallengeSpecificRules Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ChallengeSpecificRules (
        rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        period_id INTEGER NOT NULL UNIQUE,
        minutes_per_point_common INTEGER,
        minutes_per_point_other INTEGER,
        finish_common_book_points INTEGER,
        finish_other_book_points INTEGER,
        quote_common_book_points INTEGER,
        quote_other_book_points INTEGER,
        attend_discussion_points INTEGER,
        FOREIGN KEY (period_id) REFERENCES ChallengePeriods (period_id)
    );
    """)
    print("- 'ChallengeSpecificRules' table created or already exists.")

    # 6. ReadingLogs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ReadingLogs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        submission_date TEXT NOT NULL,
        common_book_minutes INTEGER DEFAULT 0,
        other_book_minutes INTEGER DEFAULT 0,
        quote_status TEXT NOT NULL CHECK(quote_status IN ('COMMON', 'OTHER', 'NONE')),
        FOREIGN KEY (member_id) REFERENCES Members (member_id)
    );
    """)
    print("- 'ReadingLogs' table created or already exists.")

    # 7. Achievements Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Achievements (
        achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        book_id INTEGER,
        achievement_type TEXT NOT NULL CHECK(achievement_type IN ('FINISHED_COMMON_BOOK', 'FINISHED_OTHER_BOOK', 'ATTENDED_DISCUSSION')),
        achievement_date TEXT NOT NULL,
        FOREIGN KEY (member_id) REFERENCES Members (member_id),
        FOREIGN KEY (book_id) REFERENCES Books (book_id)
    );
    """)
    print("- 'Achievements' table created or already exists.")


    # --- SUMMARY/STATS LAYER (The Dashboard Showroom) ---

    # 8. MemberStats Table
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
        FOREIGN KEY (member_id) REFERENCES Members (member_id)
    );
    """)
    print("- 'MemberStats' table created or already exists.")

    # 9. GroupStats Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS GroupStats (
        period_id INTEGER PRIMARY KEY,
        total_group_minutes_common INTEGER DEFAULT 0,
        total_group_minutes_other INTEGER DEFAULT 0,
        total_group_quotes_common INTEGER DEFAULT 0,
        total_group_quotes_other INTEGER DEFAULT 0,
        active_members INTEGER DEFAULT 0,
        FOREIGN KEY (period_id) REFERENCES ChallengePeriods (period_id)
    );
    """)
    print("- 'GroupStats' table created or already exists.")


    # --- Commit the changes and close the connection ---
    conn.commit()
    conn.close()
    
    print("\nDatabase setup complete!")
    print(f"Database file can be found at: {os.path.abspath(DB_PATH)}")

if __name__ == '__main__':
    create_database()
