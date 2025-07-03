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
        
        quote_responses = str(row.get('ما هي الاقتباسات التي أرسلتها اليوم؟ (اختر كل ما ينطبق)', ''))
        common_quote_today = 1 if 'الكتاب المشترك' in quote_responses or 'أرسلت اقتباساً من الكتاب المشترك' in quote_responses else 0
        other_quote_today = 1 if 'كتاب آخر' in quote_responses or 'أرسلت اقتباساً من كتاب آخر' in quote_responses else 0
        
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
    return new_entries_processed

# --- CORRECTED: Added data type enforcement ---
def calculate_and_update_stats():
    all_data = db.get_all_data_for_stats()
    if not all_data or not all_data.get("members"): return
    today = date.today()

    periods_map = {p['period_id']: p for p in all_data["periods"]}
    logs_df = pd.DataFrame(all_data["logs"])
    
    # --- FIX: Enforce correct data types after reading from DB ---
    if not logs_df.empty:
        # Convert date column
        logs_df['submission_date_dt'] = pd.to_datetime(logs_df['submission_date'], format='%d/%m/%Y', errors='coerce').dt.date
        
        # Convert all expected numeric columns to numbers, coercing errors to NaN and then filling with 0
        numeric_cols = ['common_book_minutes', 'other_book_minutes', 'submitted_common_quote', 'submitted_other_quote']
        for col in numeric_cols:
            logs_df[col] = pd.to_numeric(logs_df[col], errors='coerce').fillna(0).astype(int)

    achievements_df = pd.DataFrame(all_data["achievements"])
    final_member_stats_data = []

    for member in all_data["members"]:
        member_id = member['member_id']
        
        member_stats = {
            "member_id": member_id, "total_points": 0, "total_reading_minutes_common": 0, 
            "total_reading_minutes_other": 0, "total_common_books_read": 0, 
            "total_other_books_read": 0, "total_quotes_submitted": 0, 
            "meetings_attended": 0, "last_log_date": None, "last_quote_date": None, 
            "log_streak": 0, "quote_streak": 0
        }

        member_logs_df = logs_df[logs_df['member_id'] == member_id] if not logs_df.empty else pd.DataFrame()
        member_achievements_df = achievements_df[achievements_df['member_id'] == member_id] if not achievements_df.empty else pd.DataFrame()
        
        if not member_logs_df.empty:
            for index, log in member_logs_df.iterrows():
                log_date = log['submission_date_dt']
                if pd.isna(log_date): continue

                log_period = next((p for p in all_data['periods'] if datetime.strptime(p['start_date'], '%Y-%m-%d').date() <= log_date <= datetime.strptime(p['end_date'], '%Y-%m-%d').date()), None)

                if log_period:
                    if log_period['minutes_per_point_common'] > 0:
                        member_stats['total_points'] += log['common_book_minutes'] // log_period['minutes_per_point_common']
                    if log_period['minutes_per_point_other'] > 0:
                        member_stats['total_points'] += log['other_book_minutes'] // log_period['minutes_per_point_other']
                    
                    member_stats['total_points'] += log['submitted_common_quote'] * log_period['quote_common_book_points']
                    member_stats['total_points'] += log['submitted_other_quote'] * log_period['quote_other_book_points']

        if not member_achievements_df.empty:
            for index, achievement in member_achievements_df.iterrows():
                period_id = achievement.get('period_id')
                if period_id in periods_map:
                    achievement_period_rules = periods_map[period_id]
                    
                    if achievement['achievement_type'] == 'FINISHED_COMMON_BOOK':
                        member_stats['total_points'] += achievement_period_rules['finish_common_book_points']
                    elif achievement['achievement_type'] == 'ATTENDED_DISCUSSION':
                        member_stats['total_points'] += achievement_period_rules['attend_discussion_points']
        
        if not member_logs_df.empty:
            member_stats['total_reading_minutes_common'] = int(member_logs_df['common_book_minutes'].sum())
            member_stats['total_reading_minutes_other'] = int(member_logs_df['other_book_minutes'].sum())
            member_stats['total_quotes_submitted'] = int(member_logs_df['submitted_common_quote'].sum() + member_logs_df['submitted_other_quote'].sum())
            member_stats['last_log_date'] = str(member_logs_df['submission_date_dt'].max())
            quote_logs = member_logs_df[(member_logs_df['submitted_common_quote'] == 1) | (member_logs_df['submitted_other_quote'] == 1)]
            if not quote_logs.empty and not quote_logs['submission_date_dt'].isnull().all():
                member_stats['last_quote_date'] = str(quote_logs['submission_date_dt'].max())

        if not member_achievements_df.empty:
            member_stats['total_common_books_read'] = len(member_achievements_df[member_achievements_df['achievement_type'] == 'FINISHED_COMMON_BOOK'])
            member_stats['meetings_attended'] = len(member_achievements_df[member_achievements_df['achievement_type'] == 'ATTENDED_DISCUSSION'])
            
            finished_other_raw_count = len(member_achievements_df[member_achievements_df['achievement_type'] == 'FINISHED_OTHER_BOOK'])
            valid_other_books = min(finished_other_raw_count, member_stats['total_reading_minutes_other'] // 180 if member_stats['total_reading_minutes_other'] > 0 else 0)
            member_stats['total_other_books_read'] = valid_other_books

            other_book_achievements = member_achievements_df[member_achievements_df['achievement_type'] == 'FINISHED_OTHER_BOOK'].sort_values(by='achievement_id').head(valid_other_books)
            for index, achievement_row in other_book_achievements.iterrows():
                period_id = achievement_row.get('period_id')
                if period_id in periods_map:
                    member_stats['total_points'] += periods_map[period_id]['finish_other_book_points']

        active_period = next((p for p in all_data['periods'] if datetime.strptime(p['start_date'], '%Y-%m-%d').date() <= today <= datetime.strptime(p['end_date'], '%Y-%m-%d').date()), None)
        if active_period and member_stats['last_log_date']:
            days_since_last_log = (today - datetime.strptime(member_stats['last_log_date'], '%Y-%m-%d').date()).days
            if days_since_last_log >= active_period['no_log_days_trigger']:
                penalty = active_period['no_log_initial_penalty'] + (days_since_last_log - active_period['no_log_days_trigger']) * active_period['no_log_subsequent_penalty']
                member_stats['total_points'] -= penalty
                member_stats['log_streak'] = days_since_last_log

            if member_stats['last_quote_date']:
                last_quote_date = datetime.strptime(member_stats['last_quote_date'], '%Y-%m-%d').date()
            else:
                last_quote_date = datetime.strptime(active_period['start_date'], '%Y-%m-%d').date()

            days_since_last_quote = (today - last_quote_date).days
            if days_since_last_quote >= active_period['no_quote_days_trigger']:
                penalty = active_period['no_quote_initial_penalty'] + (days_since_last_quote - active_period['no_quote_days_trigger']) * active_period['no_quote_subsequent_penalty']
                member_stats['total_points'] -= penalty
                member_stats['quote_streak'] = days_since_last_quote
        
        final_member_stats_data.append(member_stats)
    
    db.rebuild_stats_tables(final_member_stats_data, [])