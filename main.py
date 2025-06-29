import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from datetime import datetime, date, timedelta
import os
import db_manager as db

# --- Configuration ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SERVICE_ACCOUNT_FILE = 'credentials.json'
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1TmFRDCp_OyJjlKJuU24OIVkdn3dgpE7DZKOnSmJcPuU/edit?gid=0#gid=0"

# --- Helper Functions ---
def parse_duration_to_minutes(duration_str):
    if not isinstance(duration_str, str) or not duration_str: return 0
    try:
        parts = list(map(int, duration_str.split(':')))
        h, m, s = (parts + [0, 0, 0])[:3]
        return h * 60 + m
    except (ValueError, TypeError): return 0

def fetch_data_from_sheet(gc, sheet_url):
    try:
        spreadsheet = gc.open_by_url(sheet_url)
        worksheet = spreadsheet.worksheet("Data")
        records = worksheet.get_all_records()
        return pd.DataFrame(records)
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

# --- Stage 1: Process New Data ---
def process_new_data(df, all_data):
    print(f"\nProcessing {len(df)} rows from Google Sheet...")
    member_map = {member['name']: member['member_id'] for member in all_data['members']}
    today = date.today()

    for index, row in df.iterrows():
        timestamp = str(row.get('Timestamp', '')).strip()
        if not timestamp or db.check_log_exists(timestamp):
            continue

        submission_date_str = str(row.get('تاريخ القراءة', '')).strip()
        try:
            submission_date_obj = datetime.strptime(submission_date_str, '%d/%m/%Y').date()
        except ValueError: continue
        
        if submission_date_obj > today: continue
        
        member_name = str(row.get('اسمك', '')).strip()
        member_id = member_map.get(member_name)
        if not member_id: continue

        print(f"  + New entry found for '{member_name}' with timestamp '{timestamp}'.")
        
        common_quote_today = 1 if 'الكتاب المشترك' in str(row.get('ما هي الاقتباسات التي أرسلتها اليوم؟ (اختر كل ما ينطبق)')) else 0
        other_quote_today = 1 if 'كتاب آخر' in str(row.get('ما هي الاقتباسات التي أرسلتها اليوم؟ (اختر كل ما ينطبق)')) else 0

        if common_quote_today and db.did_submit_quote_today(member_id, submission_date_str, 'COMMON'): common_quote_today = 0
        if other_quote_today and db.did_submit_quote_today(member_id, submission_date_str, 'OTHER'): other_quote_today = 0
            
        log_data = {
            "timestamp": timestamp, "member_id": member_id, "submission_date": submission_date_str,
            "common_book_minutes": parse_duration_to_minutes(row.get('مدة قراءة الكتاب المشترك')),
            "other_book_minutes": parse_duration_to_minutes(row.get('مدة قراءة كتاب آخر (إن وجد)')),
            "submitted_common_quote": common_quote_today,
            "submitted_other_quote": other_quote_today,
        }

        achievements_to_add = []
        achievement_responses = str(row.get('إنجازات الكتب والنقاش', ''))
        current_period = next((p for p in all_data['periods'] if datetime.strptime(p['start_date'], '%Y-%m-%d').date() <= submission_date_obj <= datetime.strptime(p['end_date'], '%Y-%m-%d').date()), None)
        
        if current_period:
            period_id = current_period['period_id']
            if 'أنهيت الكتاب المشترك' in achievement_responses and not db.has_achievement(member_id, 'FINISHED_COMMON_BOOK', period_id):
                achievements_to_add.append((member_id, 'FINISHED_COMMON_BOOK', str(submission_date_obj), period_id, current_period['common_book_id']))
            if 'حضرت جلسة النقاش' in achievement_responses and not db.has_achievement(member_id, 'ATTENDED_DISCUSSION', period_id):
                 achievements_to_add.append((member_id, 'ATTENDED_DISCUSSION', str(submission_date_obj), period_id, None))
            if 'أنهيت كتاباً آخر' in achievement_responses:
                achievements_to_add.append((member_id, 'FINISHED_OTHER_BOOK', str(submission_date_obj), period_id, None))

        db.add_log_and_achievements(log_data, achievements_to_add)

# --- Stage 2: Calculate and Update Stats ---
def calculate_and_update_stats():
    print("\n--- Starting Full Stats & Penalty Calculation Engine ---")
    
    settings = db.load_global_settings()
    all_data = db.get_all_data_for_stats()
    if not settings or not all_data["members"]: return

    today = date.today()
    
    # --- Part A: Calculate Member Stats ---
    member_stats_data = []
    for member in all_data["members"]:
        member_id, total_points = member['member_id'], 0
        member_logs = sorted([log for log in all_data["logs"] if log['member_id'] == member_id], key=lambda x: datetime.strptime(x['submission_date'], '%d/%m/%Y').date())
        member_achievements = [ach for ach in all_data["achievements"] if ach['member_id'] == member_id]
        
        total_reading_minutes_common = sum(log['common_book_minutes'] for log in member_logs)
        total_reading_minutes_other = sum(log['other_book_minutes'] for log in member_logs)
        common_quotes_count = sum(log['submitted_common_quote'] for log in member_logs)
        other_quotes_count = sum(log['submitted_other_quote'] for log in member_logs)

        total_points += (total_reading_minutes_common // settings['minutes_per_point_common'])
        total_points += (total_reading_minutes_other // settings['minutes_per_point_other'])
        total_points += common_quotes_count * settings['quote_common_book_points']
        total_points += other_quotes_count * settings['quote_other_book_points']
        
        finished_common_count = len([a for a in member_achievements if a['achievement_type'] == 'FINISHED_COMMON_BOOK'])
        attended_discussion_count = len([a for a in member_achievements if a['achievement_type'] == 'ATTENDED_DISCUSSION'])
        finished_other_raw_count = len([a for a in member_achievements if a['achievement_type'] == 'FINISHED_OTHER_BOOK'])
        valid_finished_other_count = min(finished_other_raw_count, total_reading_minutes_other // 180)
        
        total_points += finished_common_count * settings['finish_common_book_points']
        total_points += valid_finished_other_count * settings['finish_other_book_points']
        total_points += attended_discussion_count * settings['attend_discussion_points']

        last_log_date = datetime.strptime(member_logs[-1]['submission_date'], '%d/%m/%Y').date() if member_logs else datetime.strptime(all_data['periods'][0]['start_date'], '%Y-%m-%d').date()
        days_since_last_log = (today - last_log_date).days
        log_streak = 0
        if days_since_last_log >= settings['no_log_days_trigger']:
            penalty = settings['no_log_initial_penalty'] + (days_since_last_log - settings['no_log_days_trigger']) * settings['no_log_subsequent_penalty']
            total_points -= penalty
            log_streak = days_since_last_log
        
        last_quote_log = next((log for log in reversed(member_logs) if log['submitted_common_quote'] or log['submitted_other_quote']), None)
        last_quote_date = datetime.strptime(last_quote_log['submission_date'], '%d/%m/%Y').date() if last_quote_log else datetime.strptime(all_data['periods'][0]['start_date'], '%Y-%m-%d').date()
        days_since_last_quote = (today - last_quote_date).days
        quote_streak = 0
        if days_since_last_quote >= settings['no_quote_days_trigger']:
            penalty = settings['no_quote_initial_penalty'] + (days_since_last_quote - settings['no_quote_days_trigger']) * settings['no_quote_subsequent_penalty']
            total_points -= penalty
            quote_streak = days_since_last_quote
        
        member_stats_data.append({
            "member_id": member_id, "total_points": total_points,
            "total_reading_minutes_common": total_reading_minutes_common, "total_reading_minutes_other": total_reading_minutes_other,
            "total_common_books_read": finished_common_count, "total_other_books_read": valid_finished_other_count,
            "total_quotes_submitted": common_quotes_count + other_quotes_count, "meetings_attended": attended_discussion_count,
            "last_log_date": str(last_log_date), "last_quote_date": str(last_quote_date),
            "log_streak": log_streak, "quote_streak": quote_streak
        })
    
    # --- Part B: Calculate Group Stats (NEW LOGIC) ---
    group_stats_data = []
    for period in all_data["periods"]:
        period_id = period['period_id']
        start_date = datetime.strptime(period['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
        
        # Filter logs that fall within this challenge period
        period_logs = [
            log for log in all_data["logs"] 
            if start_date <= datetime.strptime(log['submission_date'], '%d/%m/%Y').date() <= end_date
        ]
        
        if not period_logs:
            active_members = 0
            total_group_minutes_common, total_group_minutes_other = 0, 0
            total_group_quotes_common, total_group_quotes_other = 0, 0
        else:
            active_members = len(set(log['member_id'] for log in period_logs))
            total_group_minutes_common = sum(log['common_book_minutes'] for log in period_logs)
            total_group_minutes_other = sum(log['other_book_minutes'] for log in period_logs)
            total_group_quotes_common = sum(log['submitted_common_quote'] for log in period_logs)
            total_group_quotes_other = sum(log['submitted_other_quote'] for log in period_logs)
            
        group_stats_data.append({
            "period_id": period_id,
            "total_group_minutes_common": total_group_minutes_common,
            "total_group_minutes_other": total_group_minutes_other,
            "total_group_quotes_common": total_group_quotes_common,
            "total_group_quotes_other": total_group_quotes_other,
            "active_members": active_members
        })

    # --- Part C: Rebuild Stats Tables ---
    if member_stats_data:
        db.rebuild_stats_tables(member_stats_data, group_stats_data)
        
    print("--- Full Stats & Penalty Engine Finished ---")

# --- Main Execution Block ---
def main():
    print("--- Starting Reading Challenge Data Processor ---")
    try:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        gc = gspread.authorize(creds)
    except Exception as e:
        print(f"Authentication Error: {e}"); return

    raw_data_df = fetch_data_from_sheet(gc, SPREADSHEET_URL)
    
    if raw_data_df is not None and not raw_data_df.empty:
        all_data = db.get_all_data_for_stats()
        if not all_data["members"] or not all_data["periods"]:
            print("ERROR: Incomplete setup. Run app.py first."); return

        process_new_data(raw_data_df, all_data)
        calculate_and_update_stats()
    else:
        print("No new data found in sheet or failed to fetch.")

    print("\n--- Data Processor Finished ---")

if __name__ == '__main__':
    main()
