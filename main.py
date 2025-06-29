import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
import os
import db_manager as db # Our database manager

# --- Configuration ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SERVICE_ACCOUNT_FILE = 'credentials.json'
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1TmFRDCp_OyJjlKJuU24OIVkdn3dgpE7DZKOnSmJcPuU/edit?gid=0#gid=0"

# --- Helper Functions from previous step ---
def parse_duration_to_minutes(duration_str):
    if not isinstance(duration_str, str) or not duration_str: return 0
    try:
        parts = list(map(int, duration_str.split(':')))
        h, m, s = (parts + [0, 0, 0])[:3] # Pad with zeros if needed
        return h * 60 + m
    except (ValueError, TypeError): return 0

def check_log_exists_by_timestamp(timestamp):
    return db.check_log_exists(timestamp) # We will move this function to db_manager

def add_reading_log_with_timestamp(log_data):
    db.add_reading_log(log_data) # We will move this function to db_manager


# --- Main Logic Functions ---

def fetch_data_from_sheet(gc, sheet_url):
    # ... (This function remains the same as the previous version)
    try:
        spreadsheet = gc.open_by_url(sheet_url)
        worksheet = spreadsheet.worksheet("Data")
        records = worksheet.get_all_records()
        return pd.DataFrame(records)
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def process_new_logs(df, members_list):
    # ... (This function remains the same, we'll just rename it for clarity)
    print(f"\nProcessing {len(df)} rows from Google Sheet...")
    new_logs_added = 0
    member_map = {member['name']: member['member_id'] for member in members_list}
    
    # Define column names from your Google Form
    ts_col, name_col, date_col, common_minutes_col, other_minutes_col, quote_col = \
        'Timestamp', 'اسمك', 'تاريخ القراءة', 'مدة قراءة الكتاب المشترك', \
        'مدة قراءة كتاب آخر (إن وجد)', 'ما هي الاقتباسات التي أرسلتها اليوم؟ (اختر كل ما ينطبق)'

    for index, row in df.iterrows():
        timestamp = row.get(ts_col, '')
        if not timestamp: continue

        if db.check_log_exists(timestamp):
            continue

        member_name = row.get(name_col)
        member_id = member_map.get(member_name)
        if not member_id: continue

        print(f"  + New log found with timestamp '{timestamp}'. Processing...")
        
        log_data = {
            "timestamp": timestamp, "member_id": member_id, "submission_date": row.get(date_col),
            "common_book_minutes": parse_duration_to_minutes(row.get(common_minutes_col)),
            "other_book_minutes": parse_duration_to_minutes(row.get(other_minutes_col)),
            "submitted_common_quote": 1 if 'الكتاب المشترك' in str(row.get(quote_col)) else 0,
            "submitted_other_quote": 1 if 'كتاب آخر' in str(row.get(quote_col)) else 0,
        }
        
        db.add_reading_log(log_data)
        new_logs_added += 1

    print(f"Processing complete. Added {new_logs_added} new logs.")
    return new_logs_added > 0

def calculate_and_update_stats():
    """
    The main engine. Fetches all data from our local DB, calculates points,
    and rebuilds the stats tables.
    """
    print("\n--- Starting Stats Calculation Engine ---")
    
    # 1. Fetch all necessary data from our database
    settings = db.load_global_settings()
    members = db.get_all_members()
    all_logs = db.get_all_reading_logs()
    all_achievements = db.get_all_achievements() # Assuming we will add achievements processing later
    
    if not settings:
        print("ERROR: Could not load settings. Aborting stats calculation.")
        return

    # 2. Calculate stats for each member
    member_stats_data = []
    for member in members:
        member_id = member['member_id']
        total_points = 0
        
        # Filter logs and achievements for the current member
        member_logs = [log for log in all_logs if log['member_id'] == member_id]
        member_achievements = [ach for ach in all_achievements if ach['member_id'] == member_id]
        
        # --- Calculate points from daily reading logs ---
        total_reading_minutes_common = sum(log['common_book_minutes'] for log in member_logs)
        total_reading_minutes_other = sum(log['other_book_minutes'] for log in member_logs)
        
        points_from_common_reading = (total_reading_minutes_common // settings['minutes_per_point_common'])
        points_from_other_reading = (total_reading_minutes_other // settings['minutes_per_point_other'])
        
        total_points += points_from_common_reading
        total_points += points_from_other_reading

        # --- Calculate points from quotes ---
        common_quotes = sum(log['submitted_common_quote'] for log in member_logs)
        other_quotes = sum(log['submitted_other_quote'] for log in member_logs)
        
        points_from_common_quotes = common_quotes * settings['quote_common_book_points']
        points_from_other_quotes = other_quotes * settings['quote_other_book_points']
        
        total_points += points_from_common_quotes
        total_points += points_from_other_quotes
        
        # --- TODO: Calculate points from achievements ---
        # This part will be added when we process achievements from the form
        
        # --- TODO: Calculate penalties ---
        # This part will be added later
        
        # Append the calculated stats for this member
        member_stats_data.append({
            "member_id": member_id,
            "total_points": total_points,
            "total_reading_minutes_common": total_reading_minutes_common,
            "total_reading_minutes_other": total_reading_minutes_other,
            "total_common_books_read": 0, # Placeholder
            "total_other_books_read": 0,  # Placeholder
            "total_quotes_submitted": common_quotes + other_quotes,
            "meetings_attended": 0 # Placeholder
        })

    # 3. Rebuild the stats tables with the new data
    if member_stats_data:
        db.rebuild_stats_tables(member_stats_data)
        
    print("--- Stats Calculation Engine Finished ---")


def main():
    print("--- Starting Reading Challenge Data Processor ---")
    
    # Step 1: Authenticate
    try:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        gc = gspread.authorize(creds)
    except Exception as e:
        print(f"Authentication Error: {e}")
        return

    # Step 2: Fetch raw data from Google Sheet
    raw_data_df = fetch_data_from_sheet(gc, SPREADSHEET_URL)
    
    if raw_data_df is not None and not raw_data_df.empty:
        # Step 3: Get members list from our DB
        members_list = db.get_all_members()
        if not members_list:
            print("ERROR: No members in DB. Run app.py setup first.")
            return

        # Step 4: Process new logs and add them to the core database
        process_new_logs(raw_data_df, members_list)
        
        # Step 5: Recalculate all statistics from scratch
        calculate_and_update_stats()
        
    else:
        print("No new data found in sheet or failed to fetch.")

    print("\n--- Data Processor Finished ---")

if __name__ == '__main__':
    main()
