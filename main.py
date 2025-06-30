import pandas as pd
from datetime import datetime, date, timedelta
import db_manager as db
import gspread

def run_data_update(gc: gspread.Client):
    update_log = ["--- بدء عملية تحديث بيانات التحدي ---"]
    spreadsheet_url = db.get_setting("spreadsheet_url")
    if not spreadsheet_url:
        update_log.append("❌ خطأ: لم يتم العثور على رابط جدول البيانات في الإعدادات.")
        return update_log
    update_log.append(f"🔗 جاري سحب البيانات من Google Sheet...")
    try:
        spreadsheet = gc.open_by_url(spreadsheet_url)
        worksheet = spreadsheet.worksheet("Form Responses 1")
        records = worksheet.get_all_records()
        raw_data_df = pd.DataFrame(records)
        update_log.append(f"✅ تم العثور على {len(raw_data_df)} صف في الجدول.")
    except Exception as e:
        update_log.append(f"❌ خطأ أثناء سحب البيانات: {e}")
        return update_log

    if raw_data_df is not None and not raw_data_df.empty:
        all_data = db.get_all_data_for_stats()
        if not all_data or not all_data.get("members") or not all_data.get("periods"):
            update_log.append("❌ خطأ حرج: لم تكتمل عملية الإعداد.")
            return update_log
        new_entries_count = process_new_data(raw_data_df, all_data)
        update_log.append(f"🔄 تم العثور على ومعالجة {new_entries_count} تسجيل جديد.")
        update_log.append("🧮 جاري حساب وتحديث جميع الإحصائيات...")
        calculate_and_update_stats()
        update_log.append("✅ اكتمل حساب الإحصائيات.")
    else:
        update_log.append("ℹ️ لا توجد بيانات جديدة في الجدول.")
    update_log.append("\n--- ✅ انتهت عملية مزامنة البيانات بنجاح ---")
    return update_log

def parse_duration_to_minutes(duration_str):
    if not isinstance(duration_str, str) or not duration_str: return 0
    try:
        parts = list(map(int, duration_str.split(':')))
        h, m, s = (parts + [0, 0, 0])[:3]
        return h * 60 + m
    except (ValueError, TypeError): return 0

def process_new_data(df, all_data):
    member_map = {member['name']: member['member_id'] for member in all_data['members']}
    today = date.today()
    new_entries_processed = 0
    for index, row in df.iterrows():
        timestamp = str(row.get('Timestamp', '')).strip()
        if not timestamp or db.check_log_exists(timestamp):
            continue
        
        # --- LOGIC FIX: Correctly parse the dropdown date format ---
        submission_date_str = str(row.get('تاريخ القراءة', '')).strip()
        try:
            date_part = submission_date_str.split(' ')[0]
            submission_date_obj = datetime.strptime(date_part, '%Y-%m-%d').date()
        except (ValueError, TypeError, IndexError):
            continue
        
        if submission_date_obj > today: continue
        
        member_name = str(row.get('اسمك', '')).strip()
        member_id = member_map.get(member_name)
        if not member_id: continue
        
        new_entries_processed += 1
        
        # --- LOGIC FIX: Use the correct column name for quotes ---
        quote_responses = str(row.get('ما هي الاقتباسات التي أرسلتها اليوم؟ (اختر كل ما ينطبق)', ''))
        common_quote_today = 1 if 'الكتاب المشترك' in quote_responses else 0
        other_quote_today = 1 if 'كتاب آخر' in quote_responses else 0
        
        submission_date_db_format = submission_date_obj.strftime('%d/%m/%Y')
        if common_quote_today and db.did_submit_quote_today(member_id, submission_date_db_format, 'COMMON'): common_quote_today = 0
        if other_quote_today and db.did_submit_quote_today(member_id, submission_date_db_format, 'OTHER'): other_quote_today = 0
            
        log_data = {
            "timestamp": timestamp, "member_id": member_id, "submission_date": submission_date_db_format,
            "common_book_minutes": parse_duration_to_minutes(row.get('مدة قراءة الكتاب المشترك')),
            "other_book_minutes": parse_duration_to_minutes(row.get('مدة قراءة كتاب آخر (إن وجد)')),
            "submitted_common_quote": common_quote_today,
            "submitted_other_quote": other_quote_today,
        }
        
        # --- LOGIC FIX: Use the correct column name for achievements ---
        achievements_to_add = []
        achievement_responses = str(row.get('إنجازات الكتب والنقاش', ''))
        current_period = next((p for p in all_data['periods'] if p['start_date'] <= str(submission_date_obj) <= p['end_date']), None)
        
        if current_period:
            period_id = current_period['period_id']
            if 'أنهيت الكتاب المشترك' in achievement_responses and not db.has_achievement(member_id, 'FINISHED_COMMON_BOOK', period_id):
                achievements_to_add.append((member_id, 'FINISHED_COMMON_BOOK', str(submission_date_obj), period_id, current_period['common_book_id']))
            if 'حضرت جلسة النقاش' in achievement_responses and not db.has_achievement(member_id, 'ATTENDED_DISCUSSION', period_id):
                 achievements_to_add.append((member_id, 'ATTENDED_DISCUSSION', str(submission_date_obj), period_id, None))
            if 'أنهيت كتاباً آخر' in achievement_responses:
                achievements_to_add.append((member_id, 'FINISHED_OTHER_BOOK', str(submission_date_obj), period_id, None))
        
        db.add_log_and_achievements(log_data, achievements_to_add)
    return new_entries_processed

def calculate_and_update_stats():
    settings = db.load_global_settings()
    all_data = db.get_all_data_for_stats()
    if not settings or not all_data["members"]: return
    today = date.today()
    member_stats_data = []
    for member in all_data["members"]:
        member_id = member['member_id']
        total_points = 0
        member_logs = sorted([log for log in all_data["logs"] if log['member_id'] == member_id], key=lambda x: datetime.strptime(x['submission_date'], '%d/%m/%Y').date())
        member_achievements = [ach for ach in all_data["achievements"] if ach['member_id'] == member_id]
        
        total_reading_minutes_common = sum(log['common_book_minutes'] for log in member_logs)
        total_reading_minutes_other = sum(log['other_book_minutes'] for log in member_logs)
        common_quotes_count = sum(log['submitted_common_quote'] for log in member_logs)
        other_quotes_count = sum(log['submitted_other_quote'] for log in member_logs)
        total_points += (total_reading_minutes_common // settings['minutes_per_point_common']) if settings['minutes_per_point_common'] > 0 else 0
        total_points += (total_reading_minutes_other // settings['minutes_per_point_other']) if settings['minutes_per_point_other'] > 0 else 0
        total_points += common_quotes_count * settings['quote_common_book_points']
        total_points += other_quotes_count * settings['quote_other_book_points']
        
        finished_common_count = len([a for a in member_achievements if a['achievement_type'] == 'FINISHED_COMMON_BOOK'])
        attended_discussion_count = len([a for a in member_achievements if a['achievement_type'] == 'ATTENDED_DISCUSSION'])
        finished_other_raw_count = len([a for a in member_achievements if a['achievement_type'] == 'FINISHED_OTHER_BOOK'])
        valid_finished_other_count = min(finished_other_raw_count, total_reading_minutes_other // 180 if total_reading_minutes_other > 0 else 0)
        total_points += finished_common_count * settings['finish_common_book_points']
        total_points += valid_finished_other_count * settings['finish_other_book_points']
        total_points += attended_discussion_count * settings['attend_discussion_points']
        
        log_streak = 0
        quote_streak = 0
        
        # --- LOGIC FIX: Streaks and penalties are only calculated if the member has logs ---
        if member_logs:
            first_log_date = datetime.strptime(member_logs[0]['submission_date'], '%d/%m/%Y').date()
            last_log_date = datetime.strptime(member_logs[-1]['submission_date'], '%d/%m/%Y').date()
            days_since_last_log = (today - last_log_date).days
            if days_since_last_log >= settings['no_log_days_trigger']:
                penalty = settings['no_log_initial_penalty'] + (days_since_last_log - settings['no_log_days_trigger']) * settings['no_log_subsequent_penalty']
                total_points -= penalty
                log_streak = days_since_last_log
            
            last_quote_log = next((log for log in reversed(member_logs) if log['submitted_common_quote'] or log['submitted_other_quote']), None)
            # The start date for quote streak is the member's first log, not the challenge start.
            last_quote_date = datetime.strptime(last_quote_log['submission_date'], '%d/%m/%Y').date() if last_quote_log else first_log_date
            days_since_last_quote = (today - last_quote_date).days
            if days_since_last_quote >= settings['no_quote_days_trigger']:
                penalty = settings['no_quote_initial_penalty'] + (days_since_last_quote - settings['no_quote_days_trigger']) * settings['no_quote_subsequent_penalty']
                total_points -= penalty
                quote_streak = days_since_last_quote
        
        member_stats_data.append({
            "member_id": member_id, "total_points": total_points,
            "total_reading_minutes_common": total_reading_minutes_common, "total_reading_minutes_other": total_reading_minutes_other,
            "total_common_books_read": finished_common_count, "total_other_books_read": valid_finished_other_count,
            "total_quotes_submitted": common_quotes_count + other_quotes_count, "meetings_attended": attended_discussion_count,
            "last_log_date": str(last_log_date) if member_logs else None,
            "last_quote_date": str(last_quote_date) if member_logs else None,
            "log_streak": log_streak, "quote_streak": quote_streak
        })
    
    db.rebuild_stats_tables(member_stats_data, []) # Group stats can be rebuilt later
