import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
import db_manager as db
import plotly.express as px
import plotly.graph_objects as go
from main import run_data_update
import auth_manager
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import gspread
import time
import locale

# --- Helper function for Date Dropdown ---
def generate_date_options():
    try:
        locale.setlocale(locale.LC_TIME, 'ar_SA.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, 'C')
    today_obj = date.today()
    dates = []
    arabic_days = {"Monday": "الاثنين", "Tuesday": "الثلاثاء", "Wednesday": "الأربعاء", "Thursday": "الخميس", "Friday": "الجمعة", "Saturday": "السبت", "Sunday": "الأحد"}
    for i in range(7):
        current = today_obj - timedelta(days=i)
        english_day_name = current.strftime('%A')
        arabic_day_name = arabic_days.get(english_day_name, english_day_name)
        dates.append(f"{current.strftime('%Y-%m-%d')} ({arabic_day_name})")
    return dates

# --- Helper function to update Google Form ---
def update_form_members(forms_service, form_id, question_id, active_member_names):
    """Updates the dropdown options for the member selection question in the Google Form."""
    if not form_id or not question_id:
        st.error("لم يتم العثور على معرّف النموذج أو معرّف سؤال الأعضاء في الإعدادات.")
        return False
    
    update_request = {
        "requests": [
            {
                "updateItem": {
                    "item": {
                        "itemId": question_id,
                        "questionItem": {
                            "question": {
                                "choiceQuestion": {
                                    "options": [{"value": name} for name in sorted(active_member_names)]
                                }
                            }
                        }
                    },
                    "location": {"index": 0},
                    "updateMask": "questionItem.question.choiceQuestion.options"
                }
            }
        ]
    }
    
    try:
        forms_service.forms().batchUpdate(formId=form_id, body=update_request).execute()
        return True
    except HttpError as e:
        st.error(f"⚠️ فشل تحديث نموذج جوجل: {e}")
        return False
    except Exception as e:
        st.error(f"حدث خطأ غير متوقع أثناء تحديث النموذج: {e}")
        return False

# --- Page Configuration ---
st.set_page_config(page_title="ماراثون القراءة", page_icon="📚", layout="wide")

# --- 1. Main Authentication Call ---
creds = auth_manager.authenticate()
gc = auth_manager.get_gspread_client()
forms_service = build('forms', 'v1', credentials=creds)

# --- 2. Initial Workspace Setup Wizard ---
spreadsheet_url = db.get_setting("spreadsheet_url")
form_url = db.get_setting("form_url")

if not spreadsheet_url:
    st.header("✨ الخطوة 1: تجهيز مساحة العمل")
    st.info("سيقوم التطبيق بإنشاء جدول بيانات (Google Sheet) في حسابك ليكون قاعدة البيانات المركزية لجميع تحديات القراءة.")
    if 'sheet_title' not in st.session_state:
        st.session_state.sheet_title = f"بيانات تحدي القراءة - {date.today().year}"
    st.session_state.sheet_title = st.text_input("اختر اسماً لجدول البيانات", value=st.session_state.sheet_title)
    if st.button("🚀 إنشاء جدول البيانات الآن", type="primary", use_container_width=True):
        with st.spinner("جاري إنشاء جدول البيانات..."):
            try:
                spreadsheet = gc.create(st.session_state.sheet_title)
                db.set_setting("spreadsheet_url", spreadsheet.url)
                st.success("✅ تم إنشاء جدول البيانات بنجاح!")
                st.balloons()
                st.rerun()
            except Exception as e:
                st.error(f"🌐 خطأ في الاتصال بخدمات جوجل: {e}")
    st.stop()

if not form_url:
    st.header("👥 الخطوة 2: إضافة أعضاء فريقك وإنشاء النموذج")
    st.info("قبل إنشاء نموذج التسجيل، يرجى إضافة أسماء المشاركين في التحدي (كل اسم في سطر).")
    all_data_for_form = db.get_all_data_for_stats()
    members_df_for_form = pd.DataFrame(all_data_for_form.get('members', []))
    if members_df_for_form.empty:
        with st.form("initial_members_form"):
            names_str = st.text_area("أدخل أسماء المشاركين (كل اسم في سطر جديد):", height=150, placeholder="خالد\nسارة\n...")
            if st.form_submit_button("إضافة الأعضاء وحفظهم", use_container_width=True):
                names = [name.strip() for name in names_str.split('\n') if name.strip()]
                if names:
                    db.add_members(names)
                    st.success("تمت إضافة الأعضاء بنجاح! يمكنك الآن إنشاء النموذج.")
                    st.rerun()
    else:
        st.success(f"تم العثور على {len(members_df_for_form)} أعضاء. أنت جاهز لإنشاء النموذج.")
        if st.button("📝 إنشاء نموذج التسجيل الآن", type="primary", use_container_width=True):
            with st.spinner("جاري إنشاء النموذج..."):
                try:
                    sheet_title = gc.open_by_url(spreadsheet_url).title
                    member_names = members_df_for_form['name'].tolist()
                    new_form_info = {"info": {"title": sheet_title, "documentTitle": sheet_title}}
                    form_result = forms_service.forms().create(body=new_form_info).execute()
                    form_id = form_result['formId']
                    date_options = generate_date_options()
                    
                    update_requests = {"requests": [
                        {"updateFormInfo": {"info": {"description": "يرجى ملء هذا النموذج يومياً لتسجيل نشاطك في تحدي القراءة. بالتوفيق!"}, "updateMask": "description"}},
                        {"createItem": {"item": {"title": "اسمك", "questionItem": {"question": {"required": True, "choiceQuestion": {"type": "DROP_DOWN", "options": [{"value": name} for name in member_names]}}}}, "location": {"index": 0}}},
                        {"createItem": {"item": {"title": "تاريخ القراءة", "questionItem": {"question": {"required": True, "choiceQuestion": {"type": "DROP_DOWN", "options": [{"value": d} for d in date_options]}}}}, "location": {"index": 1}}},
                        {"createItem": {"item": {"title": "مدة قراءة الكتاب المشترك", "questionItem": {"question": {"required": True, "timeQuestion": {"duration": True}}}}, "location": {"index": 2}}},
                        {"createItem": {"item": {"title": "مدة قراءة كتاب آخر (إن وجد)", "questionItem": {"question": {"timeQuestion": {"duration": True}}}}, "location": {"index": 3}}},
                        {"createItem": {"item": {"title": "ما هي الاقتباسات التي أرسلتها اليوم؟ (اختر كل ما ينطبق)", "questionItem": {"question": {"choiceQuestion": {"type": "CHECKBOX", "options": [{"value": "أرسلت اقتباساً من الكتاب المشترك"}, {"value": "أرسلت اقتباساً من كتاب آخر"}]}}}}, "location": {"index": 4}}},
                        {"createItem": {"item": {"title": "إنجازات خاصة (اختر فقط عند حدوثه لأول مرة)", "pageBreakItem": {}}, "location": {"index": 5}}},
                        {"createItem": {"item": {"title": "إنجازات الكتب والنقاش", "questionItem": {"question": {"choiceQuestion": {"type": "CHECKBOX", "options": [{"value": "أنهيت الكتاب المشترك"}, {"value": "أنهيت كتاباً آخر"}, {"value": "حضرت جلسة النقاش"}]}}}}, "location": {"index": 6}}}
                    ]}
                    
                    update_result = forms_service.forms().batchUpdate(formId=form_id, body=update_requests).execute()
                    
                    member_question_id = update_result['replies'][1]['createItem']['itemId']
                    db.set_setting("form_id", form_id)
                    db.set_setting("member_question_id", member_question_id)
                    db.set_setting("form_url", form_result['responderUri'])
                    
                    with st.spinner("تتم مزامنة الملف مع Google Drive..."): time.sleep(7)
                    st.success("✅ تم إنشاء النموذج وحفظ معرّفاته بنجاح!")
                    st.info("🔗 الخطوة 3: الربط النهائي (تتم يدوياً)")
                    editor_url = f"https://docs.google.com/forms/d/{form_id}/edit"
                    st.write("1. **افتح النموذج للتعديل** من الرابط أدناه:")
                    st.code(editor_url)
                    st.write("2. انتقل إلى تبويب **\"الردود\" (Responses)**.")
                    st.write("3. اضغط على أيقونة **'Link to Sheets'**.")
                    st.write("4. اختر **'Select existing spreadsheet'** وقم باختيار الجدول الذي أنشأته.")
                    if st.button("لقد قمت بالربط، تابع!"):
                        with st.spinner("جاري تنظيف جدول البيانات..."):
                            try:
                                spreadsheet = gc.open_by_url(spreadsheet_url)
                                default_sheet = spreadsheet.worksheet('Sheet1')
                                spreadsheet.del_worksheet(default_sheet)
                            except gspread.exceptions.WorksheetNotFound: pass
                            except Exception as e: st.warning(f"لم نتمكن من حذف الصفحة الفارغة تلقائياً: {e}.")
                        st.rerun()
                except Exception as e:
                    st.error(f"🌐 خطأ في الاتصال بخدمات جوجل: {e}")
    st.stop()

# --- 3. Main Application Interface ---
all_data = db.get_all_data_for_stats()
members_df = pd.DataFrame(all_data.get('members', []))
periods_df = pd.DataFrame(all_data.get('periods', []))
setup_complete = not periods_df.empty

st.sidebar.title("لوحة التحكم")
st.sidebar.success(f"أهلاً بك! (تم تسجيل الدخول)")
if st.sidebar.button("🔄 تحديث وسحب البيانات", type="primary", use_container_width=True):
    with st.spinner("جاري سحب البيانات..."):
        update_log = run_data_update(gc)
        st.session_state['update_log'] = update_log
    st.rerun()
if 'update_log' in st.session_state:
    st.info("اكتملت عملية المزامنة.")
    with st.expander("عرض تفاصيل سجل التحديث الأخير"):
        for message in st.session_state.update_log:
            st.text(message)
    del st.session_state['update_log']
st.sidebar.divider()

if not setup_complete:
    st.header("الخطوة الأخيرة: إنشاء أول تحدي")
    st.info("أنت على وشك الانتهاء! كل ما عليك فعله هو إضافة تفاصيل أول كتاب وتحدي للبدء.")
    with st.form("new_challenge_form", clear_on_submit=True):
        st.text_input("عنوان الكتاب المشترك الأول", key="book_title")
        st.text_input("اسم المؤلف", key="book_author")
        st.number_input("سنة النشر", key="pub_year", value=date.today().year, step=1)
        st.date_input("تاريخ بداية التحدي", key="start_date", value=date.today())
        st.date_input("تاريخ نهاية التحدي", key="end_date", value=date.today() + timedelta(days=30))
        if st.form_submit_button("بدء التحدي الأول!", use_container_width=True):
            if st.session_state.book_title and st.session_state.book_author:
                book_info = {'title': st.session_state.book_title, 'author': st.session_state.book_author, 'year': st.session_state.pub_year}
                challenge_info = {'start_date': str(st.session_state.start_date), 'end_date': str(st.session_state.end_date)}
                default_rules = db.load_global_settings()
                if default_rules:
                    if 'setting_id' in default_rules:
                        del default_rules['setting_id']
                    success, message = db.add_book_and_challenge(book_info, challenge_info, default_rules)
                    if success:
                        st.success("🎉 اكتمل الإعداد! تم إنشاء أول تحدي بنجاح.")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(f"❌ فشلت العملية: {message}")
                else:
                    st.error("لم يتم العثور على الإعدادات الافتراضية في قاعدة البيانات.")
            else:
                st.error("✏️ بيانات غير مكتملة: يرجى إدخال عنوان الكتاب واسم المؤلف.")
    st.stop()

# --- Main App Pages ---
st.sidebar.title("التنقل")
page_options = ["لوحة التحكم", "⚙️ الإدارة والتحكم", "إعدادات التحدي والنقاط"]
page = st.sidebar.radio("اختر صفحة لعرضها:", page_options, key="navigation")

# Load dataframes once
logs_df = pd.DataFrame(all_data.get('logs', []))
if not logs_df.empty:
    logs_df['submission_date_dt'] = pd.to_datetime(logs_df['submission_date'], format='%d/%m/%Y', errors='coerce').dt.date

achievements_df = pd.DataFrame(all_data.get('achievements', []))
member_stats_df = db.get_table_as_df('MemberStats')
if not member_stats_df.empty and not members_df.empty:
    member_stats_df = pd.merge(member_stats_df, members_df[['member_id', 'name']], on='member_id', how='left')

if page == "لوحة التحكم":
    st.header("📊 لوحة التحكم الرئيسية")
    
    if periods_df.empty:
        st.info("لا توجد تحديات حالية. يمكنك إضافة تحدي جديد من صفحة 'الإدارة والتحكم'.")
        st.stop()
    
    today = date.today()
    
    challenge_options_map = {'all': {'title': 'كل التحديات'}}
    for index, period in periods_df.iterrows():
        challenge_options_map[period['period_id']] = period.to_dict()

    active_challenges, past_challenges, future_challenges = [], [], []
    for period_id, period_data in challenge_options_map.items():
        if period_id == 'all': continue
        start_date_obj = datetime.strptime(period_data['start_date'], '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(period_data['end_date'], '%Y-%m-%d').date()
        
        if start_date_obj > today:
            future_challenges.append(period_id)
        elif end_date_obj < today:
            past_challenges.append(period_id)
        else:
            active_challenges.append(period_id)
            
    future_challenges.sort(key=lambda pid: datetime.strptime(challenge_options_map[pid]['start_date'], '%Y-%m-%d').date())
    past_challenges.sort(key=lambda pid: datetime.strptime(challenge_options_map[pid]['start_date'], '%Y-%m-%d').date(), reverse=True)
    
    sorted_option_ids = ['all'] + future_challenges + active_challenges + past_challenges
    
    def format_challenge_option(period_id):
        period_data = challenge_options_map[period_id]
        if period_id == 'all':
            return "⭐️ كل التحديات (عرض تراكمي)"
        
        status_emoji = ""
        if period_id in active_challenges: status_emoji = " (الحالي) 🟢"
        if period_id in past_challenges: status_emoji = " (السابق) 🏁"
        if period_id in future_challenges: status_emoji = " (المقبل) ⏳"
            
        return f"{period_data['title']} - {period_data['author']} | {period_data['start_date']} إلى {period_data['end_date']}{status_emoji}"

    default_index = 0
    if active_challenges:
        active_id = active_challenges[0]
        if active_id in sorted_option_ids:
            default_index = sorted_option_ids.index(active_id)
    
    selected_period_id = st.selectbox(
        "اختر عرضاً للبيانات:",
        options=sorted_option_ids,
        format_func=format_challenge_option,
        index=default_index,
        key="challenge_selector"
    )

    # --- Data Filtering and Display Logic ---
    if selected_period_id == 'all':
        st.subheader("إحصائيات كل التحديات")
        display_stats_df = member_stats_df
    else:
        period_rules = challenge_options_map[selected_period_id]
        st.subheader(f"📖 إحصائيات تحدي: {period_rules['title']}")
        start_date_obj = datetime.strptime(period_rules['start_date'], '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(period_rules['end_date'], '%Y-%m-%d').date()
        
        period_logs_df = pd.DataFrame()
        if not logs_df.empty:
            period_logs_df = logs_df[(logs_df['submission_date_dt'].notna()) & (logs_df['submission_date_dt'] >= start_date_obj) & (logs_df['submission_date_dt'] <= end_date_obj)].copy()
        
        period_achievements_df = pd.DataFrame()
        if not achievements_df.empty:
            period_achievements_df = achievements_df[achievements_df['period_id'] == selected_period_id].copy()
        
        period_points = {member['member_id']: 0 for _, member in members_df.iterrows()}
        
        if not period_logs_df.empty:
            log_summary = period_logs_df.groupby('member_id').agg(
                total_common_minutes=('common_book_minutes', 'sum'),
                total_other_minutes=('other_book_minutes', 'sum'),
                total_common_quotes=('submitted_common_quote', 'sum'),
                total_other_quotes=('submitted_other_quote', 'sum')
            ).to_dict('index')

            for member_id, summary in log_summary.items():
                points = 0
                if period_rules.get('minutes_per_point_common', 0) > 0:
                    points += summary['total_common_minutes'] // period_rules['minutes_per_point_common']
                if period_rules.get('minutes_per_point_other', 0) > 0:
                    points += summary['total_other_minutes'] // period_rules['minutes_per_point_other']
                points += summary['total_common_quotes'] * period_rules.get('quote_common_book_points', 0)
                points += summary['total_other_quotes'] * period_rules.get('quote_other_book_points', 0)
                period_points[member_id] += int(points)

        if not period_achievements_df.empty:
            for _, ach in period_achievements_df.iterrows():
                member_id = ach['member_id']
                ach_type = ach['achievement_type']
                if ach_type == 'FINISHED_COMMON_BOOK':
                    period_points[member_id] += period_rules.get('finish_common_book_points', 0)
                elif ach_type == 'ATTENDED_DISCUSSION':
                    period_points[member_id] += period_rules.get('attend_discussion_points', 0)
                elif ach_type == 'FINISHED_OTHER_BOOK':
                    # Validation for other books finished within the period
                    if not period_logs_df.empty:
                         member_period_logs = period_logs_df[period_logs_df['member_id'] == member_id]
                         if not member_period_logs.empty:
                             other_minutes_in_period = member_period_logs['other_book_minutes'].sum()
                             # Simple validation: 1 book per 3 hours
                             if other_minutes_in_period >= 180:
                                period_points[member_id] += period_rules.get('finish_other_book_points', 0)
        
        period_display_data = [{'member_id': mid, 'total_points': pts} for mid, pts in period_points.items()]
        period_stats_df = pd.DataFrame(period_display_data)
        display_stats_df = pd.merge(period_stats_df, members_df[['member_id', 'name']], on='member_id', how='left')

    st.divider()

    st.info("سيتم بناء المخططات البيانية والأقسام الجديدة هنا في الخطوات القادمة.")
    
    if not display_stats_df.empty:
        st.write("### مثال: عرض إجمالي النقاط للمستخدمين")
        if 'name' in display_stats_df.columns:
            st.dataframe(display_stats_df[['name', 'total_points']].sort_values('total_points', ascending=False), use_container_width=True)
        else:
            st.warning("حدث خطأ في تجهيز البيانات للعرض.")
    else:
        st.warning("لا توجد بيانات إحصائية لعرضها.")

elif page == "⚙️ الإدارة والتحكم":
    st.header("✨ لوحة التحكم الإدارية")
    
    st.subheader("👥 إدارة المشاركين")
    
    with st.form("add_member_form"):
        new_member_name = st.text_input("اسم العضو الجديد")
        submitted = st.form_submit_button("➕ إضافة أو إعادة تنشيط عضو")
        if submitted and new_member_name:
            with st.spinner(f"جاري إضافة {new_member_name}..."):
                status_code, message = db.add_single_member(new_member_name.strip())
                if status_code in ['added', 'reactivated']:
                    st.success(message)
                    all_members = db.get_table_as_df('Members')
                    active_members = all_members[all_members['is_active'] == 1]['name'].tolist()
                    form_id = db.get_setting('form_id')
                    question_id = db.get_setting('member_question_id')
                    if update_form_members(forms_service, form_id, question_id, active_members):
                        st.info("✅ تم تحديث نموذج جوجل بنجاح.")
                    st.rerun()
                elif status_code == 'exists':
                    st.warning(message)
                else:
                    st.error(message)

    st.divider()

    all_members_df = db.get_table_as_df('Members')
    active_members_df = all_members_df[all_members_df['is_active'] == 1]
    inactive_members_df = all_members_df[all_members_df['is_active'] == 0]

    st.subheader(f"✅ الأعضاء النشطون ({len(active_members_df)})")
    if not active_members_df.empty:
        for index, member in active_members_df.iterrows():
            col1, col2 = st.columns([4, 1])
            col1.write(member['name'])
            if col2.button("🚫 تعطيل", key=f"deactivate_{member['member_id']}", use_container_width=True):
                with st.spinner(f"جاري تعطيل {member['name']}..."):
                    db.set_member_status(member['member_id'], 0)
                    updated_active_members = active_members_df[active_members_df['member_id'] != member['member_id']]['name'].tolist()
                    form_id = db.get_setting('form_id')
                    question_id = db.get_setting('member_question_id')
                    if update_form_members(forms_service, form_id, question_id, updated_active_members):
                        st.success(f"تم تعطيل {member['name']} وإزالته من نموذج التسجيل.")
                    st.rerun()
    else:
        st.info("لا يوجد أعضاء نشطون حالياً.")

    st.subheader(f"_ أرشيف الأعضاء ({len(inactive_members_df)})")
    if not inactive_members_df.empty:
        for index, member in inactive_members_df.iterrows():
            col1, col2 = st.columns([4, 1])
            col1.write(f"_{member['name']}_")
            if col2.button("🔄 إعادة تنشيط", key=f"reactivate_{member['member_id']}", use_container_width=True):
                 with st.spinner(f"جاري إعادة تنشيط {member['name']}..."):
                    db.set_member_status(member['member_id'], 1)
                    current_active_names = active_members_df['name'].tolist()
                    current_active_names.append(member['name'])
                    form_id = db.get_setting('form_id')
                    question_id = db.get_setting('member_question_id')
                    if update_form_members(forms_service, form_id, question_id, current_active_names):
                        st.success(f"تم إعادة تنشيط {member['name']} وإضافته إلى نموذج التسجيل.")
                    st.rerun()
    else:
        st.info("لا يوجد أعضاء في الأرشيف.")

    st.divider()

    st.subheader("📅 إدارة تحديات القراءة")
    today_str = str(date.today())
    active_period_id = None
    if not periods_df.empty:
        active_periods_ids = [p['period_id'] for i, p in periods_df.iterrows() if p['start_date'] <= today_str <= p['end_date']]
        if active_periods_ids:
            active_period_id = active_periods_ids[0]
            
    if not periods_df.empty:
        cols = st.columns((4, 2, 2, 2, 1))
        headers = ["عنوان الكتاب", "المؤلف", "تاريخ البداية", "تاريخ النهاية", "إجراء"]
        for col, header in zip(cols, headers):
            col.write(f"**{header}**")
        for index, period in periods_df.iterrows():
            col1, col2, col3, col4, col5 = st.columns((4, 2, 2, 2, 1))
            col1.write(period['title'])
            col2.write(period['author'])
            col3.write(period['start_date'])
            col4.write(period['end_date'])
            is_active = period['period_id'] == active_period_id
            delete_button_disabled = bool(is_active)
            delete_button_help = "لا يمكن حذف التحدي النشط حالياً." if is_active else None
            if col5.button("🗑️ حذف", key=f"delete_{period['period_id']}", disabled=delete_button_disabled, help=delete_button_help, use_container_width=True):
                st.session_state['challenge_to_delete'] = period['period_id']
                st.session_state['delete_confirmation_phrase'] = f"أوافق على حذف {period['title']}"
    else:
        st.info("لا توجد تحديات لعرضها.")
    
    with st.expander("اضغط هنا لإضافة تحدي جديد"):
        with st.form("add_new_challenge_details_form"):
            st.write("**تفاصيل الكتاب والتحدي**")
            new_title = st.text_input("عنوان الكتاب الجديد", key="new_chal_title")
            new_author = st.text_input("مؤلف الكتاب الجديد", key="new_chal_author")
            new_year = st.number_input("سنة نشر الكتاب الجديد", value=datetime.now().year, step=1, key="new_chal_year")
            
            last_end_date = pd.to_datetime(periods_df['end_date'].max()).date() if not periods_df.empty else date.today() - timedelta(days=1)
            suggested_start = last_end_date + timedelta(days=1)
            new_start = st.date_input("تاريخ بداية التحدي الجديد", value=suggested_start, key="new_chal_start")
            new_end = st.date_input("تاريخ نهاية التحدي الجديد", value=suggested_start + timedelta(days=30), key="new_chal_end")

            if st.form_submit_button("إضافة التحدي"):
                if new_start <= last_end_date:
                    st.error(f"⛔ التواريخ متداخلة: يرجى اختيار تاريخ بداية بعد {last_end_date}.")
                elif not new_title or not new_author:
                    st.error("✏️ بيانات غير مكتملة: يرجى إدخال عنوان الكتاب واسم المؤلف للمتابعة.")
                elif new_start >= new_end:
                    st.error("🗓️ خطأ في التواريخ: تاريخ نهاية التحدي يجب أن يكون بعد تاريخ بدايته.")
                else:
                    st.session_state.new_challenge_data = {
                        'book_info': {'title': new_title, 'author': new_author, 'year': new_year},
                        'challenge_info': {'start_date': str(new_start), 'end_date': str(new_end)}
                    }
                    st.session_state.show_rules_choice = True

    if 'show_rules_choice' in st.session_state and st.session_state.show_rules_choice:
        @st.dialog("اختر نظام النقاط للتحدي")
        def show_rules_choice_dialog():
            st.write(f"اختر نظام النقاط الذي تريد تطبيقه على تحدي كتاب **'{st.session_state.new_challenge_data['book_info']['title']}'**.")
            
            if st.button("📈 استخدام النظام الافتراضي", use_container_width=True):
                default_rules = db.load_global_settings()
                if 'setting_id' in default_rules: del default_rules['setting_id']
                
                success, message = db.add_book_and_challenge(
                    st.session_state.new_challenge_data['book_info'],
                    st.session_state.new_challenge_data['challenge_info'],
                    default_rules
                )
                if success:
                    st.success(f"✅ {message}")
                else:
                    st.error(f"❌ {message}")
                
                del st.session_state.show_rules_choice
                del st.session_state.new_challenge_data
                st.rerun()

            if st.button("🛠️ تخصيص القوانين", type="primary", use_container_width=True):
                st.session_state.show_custom_rules_form = True
                del st.session_state.show_rules_choice
                st.rerun()

        show_rules_choice_dialog()

    if 'show_custom_rules_form' in st.session_state and st.session_state.show_custom_rules_form:
        @st.dialog("تخصيص قوانين التحدي")
        def show_custom_rules_dialog():
            default_settings = db.load_global_settings()
            with st.form("custom_rules_form"):
                st.info("أنت الآن تقوم بتعيين قوانين خاصة لهذا التحدي فقط.")
                c1, c2 = st.columns(2)
                rules = {}
                rules['minutes_per_point_common'] = c1.number_input("دقائق قراءة الكتاب المشترك لكل نقطة:", value=default_settings['minutes_per_point_common'], min_value=0)
                rules['minutes_per_point_other'] = c2.number_input("دقائق قراءة كتاب آخر لكل نقطة:", value=default_settings['minutes_per_point_other'], min_value=0)
                rules['quote_common_book_points'] = c1.number_input("نقاط اقتباس الكتاب المشترك:", value=default_settings['quote_common_book_points'], min_value=0)
                rules['quote_other_book_points'] = c2.number_input("نقاط اقتباس كتاب آخر:", value=default_settings['quote_other_book_points'], min_value=0)
                rules['finish_common_book_points'] = c1.number_input("نقاط إنهاء الكتاب المشترك:", value=default_settings['finish_common_book_points'], min_value=0)
                rules['finish_other_book_points'] = c2.number_input("نقاط إنهاء كتاب آخر:", value=default_settings['finish_other_book_points'], min_value=0)
                rules['attend_discussion_points'] = st.number_input("نقاط حضور جلسة النقاش:", value=default_settings['attend_discussion_points'], min_value=0)
                st.divider()
                st.write("**نظام الخصومات (أدخل 0 لإلغاء الخصم)**")
                c3, c4 = st.columns(2)
                rules['no_log_days_trigger'] = c3.number_input("أيام الغياب عن التسجيل لبدء الخصم:", value=default_settings['no_log_days_trigger'], min_value=0)
                rules['no_log_initial_penalty'] = c3.number_input("قيمة الخصم الأول للغياب:", value=default_settings['no_log_initial_penalty'], min_value=0)
                rules['no_log_subsequent_penalty'] = c3.number_input("قيمة الخصم المتكرر للغياب:", value=default_settings['no_log_subsequent_penalty'], min_value=0)
                rules['no_quote_days_trigger'] = c4.number_input("أيام عدم إرسال اقتباس لبدء الخصم:", value=default_settings['no_quote_days_trigger'], min_value=0)
                rules['no_quote_initial_penalty'] = c4.number_input("قيمة الخصم الأول للاقتباس:", value=default_settings['no_quote_initial_penalty'], min_value=0)
                rules['no_quote_subsequent_penalty'] = c4.number_input("قيمة الخصم المتكرر للاقتباس:", value=default_settings['no_quote_subsequent_penalty'], min_value=0)

                if st.form_submit_button("حفظ التحدي بالقوانين المخصصة"):
                    success, message = db.add_book_and_challenge(
                        st.session_state.new_challenge_data['book_info'],
                        st.session_state.new_challenge_data['challenge_info'],
                        rules
                    )
                    if success:
                        st.success(f"✅ {message}")
                    else:
                        st.error(f"❌ {message}")

                    del st.session_state.show_custom_rules_form
                    del st.session_state.new_challenge_data
                    st.rerun()

        show_custom_rules_dialog()

    if 'challenge_to_delete' in st.session_state:
        @st.dialog("🚫 تأكيد الحذف النهائي (لا يمكن التراجع)")
        def show_challenge_delete_dialog():
            st.warning("☢️ إجراء لا يمكن التراجع عنه: أنت على وشك حذف التحدي وكل ما يتعلق به من إنجازات وإحصائيات.")
            confirmation_phrase = st.session_state['delete_confirmation_phrase']
            st.code(confirmation_phrase)
            user_input = st.text_input("اكتب عبارة التأكيد هنا:", key="challenge_delete_input")
            if st.button("❌ حذف التحدي نهائياً", disabled=(user_input != confirmation_phrase), type="primary"):
                if db.delete_challenge(st.session_state['challenge_to_delete']):
                    del st.session_state['challenge_to_delete']; st.success("🗑️ اكتمل الحذف."); st.rerun()
            if st.button("إلغاء"):
                del st.session_state['challenge_to_delete']; st.rerun()
        show_challenge_delete_dialog()

elif page == "إعدادات التحدي والنقاط":
    st.header("⚙️ إعدادات التحدي والنقاط")
    st.subheader("🔗 روابط جوجل (للمرجعية)")
    st.text_input("رابط جدول البيانات (Google Sheet)", value=db.get_setting("spreadsheet_url"), disabled=True)
    st.text_input("رابط نموذج التسجيل (للمستخدمين)", value=db.get_setting("form_url"), disabled=True)
    editor_url = (db.get_setting("form_url") or "").replace("/viewform", "/edit")
    st.text_input("رابط تعديل النموذج (للمشرف)", value=editor_url, disabled=True)
    st.divider()
    st.subheader("🎯 نظام النقاط والخصومات الافتراضي")
    st.info("هذه هي القوانين الافتراضية التي سيتم تطبيقها على التحديات الجديدة التي لا يتم تخصيص قوانين لها.")
    settings = db.load_global_settings()
    if settings:
        with st.form("settings_form"):
            c1, c2 = st.columns(2)
            s_m_common = c1.number_input("دقائق قراءة الكتاب المشترك لكل نقطة:", value=settings['minutes_per_point_common'], min_value=0)
            s_m_other = c2.number_input("دقائق قراءة كتاب آخر لكل نقطة:", value=settings['minutes_per_point_other'], min_value=0)
            s_q_common = c1.number_input("نقاط اقتباس الكتاب المشترك:", value=settings['quote_common_book_points'], min_value=0)
            s_q_other = c2.number_input("نقاط اقتباس كتاب آخر:", value=settings['quote_other_book_points'], min_value=0)
            s_f_common = c1.number_input("نقاط إنهاء الكتاب المشترك:", value=settings['finish_common_book_points'], min_value=0)
            s_f_other = c2.number_input("نقاط إنهاء كتاب آخر:", value=settings['finish_other_book_points'], min_value=0)
            s_a_disc = st.number_input("نقاط حضور جلسة النقاش:", value=settings['attend_discussion_points'], min_value=0)
            st.divider()
            st.subheader("نظام الخصومات (أدخل 0 لإلغاء الخصم)")
            c3, c4 = st.columns(2)
            s_nl_trigger = c3.number_input("أيام الغياب عن التسجيل لبدء الخصم:", value=settings['no_log_days_trigger'], min_value=0)
            s_nl_initial = c3.number_input("قيمة الخصم الأول للغياب:", value=settings['no_log_initial_penalty'], min_value=0)
            s_nl_subsequent = c3.number_input("قيمة الخصم المتكرر للغياب:", value=settings['no_log_subsequent_penalty'], min_value=0)
            s_nq_trigger = c4.number_input("أيام عدم إرسال اقتباس لبدء الخصم:", value=settings['no_quote_days_trigger'], min_value=0)
            s_nq_initial = c4.number_input("قيمة الخصم الأول للاقتباس:", value=settings['no_quote_initial_penalty'], min_value=0)
            s_nq_subsequent = c4.number_input("قيمة الخصم المتكرر للاقتباس:", value=settings['no_quote_subsequent_penalty'], min_value=0)
            if st.form_submit_button("حفظ الإعدادات الافتراضية", use_container_width=True):
                new_settings = {"minutes_per_point_common": s_m_common, "minutes_per_point_other": s_m_other, "quote_common_book_points": s_q_common, "quote_other_book_points": s_q_other, "finish_common_book_points": s_f_common, "finish_other_book_points": s_f_other, "attend_discussion_points": s_a_disc, "no_log_days_trigger": s_nl_trigger, "no_log_initial_penalty": s_nl_initial, "no_log_subsequent_penalty": s_nl_subsequent, "no_quote_days_trigger": s_nq_trigger, "no_quote_initial_penalty": s_nq_initial, "no_quote_subsequent_penalty": s_nq_subsequent}
                if db.update_global_settings(new_settings):
                    st.success("👍 تم حفظ التغييرات! تم تحديث نظام النقاط والخصومات الافتراضي بنجاح.")
                else:
                    st.error("حدث خطأ أثناء تحديث الإعدادات.")