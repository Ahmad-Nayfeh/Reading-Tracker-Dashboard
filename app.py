import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
import db_manager as db
import plotly.express as px
import plotly.graph_objects as go
from main import run_data_update
import auth_manager
from googleapiclient.discovery import build
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
                st.error(f"🌐 خطأ في الاتصال بخدمات جوجل: لم نتمكن من إنشاء جدول البيانات. قد يكون السبب مشكلة مؤقتة. الخطأ: {e}")
    st.stop()

if not form_url:
    st.header("👥 الخطوة 2: إضافة أعضاء فريقك")
    st.info("قبل إنشاء نموذج التسجيل، يرجى إضافة أسماء المشاركين في التحدي (كل اسم في سطر). ستظهر هذه الأسماء تلقائياً في النموذج.")
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
                    update_requests = {"requests": [{"updateFormInfo": {"info": {"description": "يرجى ملء هذا النموذج يومياً لتسجيل نشاطك في تحدي القراءة. بالتوفيق!"}, "updateMask": "description"}}, {"createItem": {"item": {"title": "اسمك", "questionItem": {"question": {"required": True, "choiceQuestion": {"type": "DROP_DOWN", "options": [{"value": name} for name in member_names]}}}}, "location": {"index": 0}}}, {"createItem": {"item": {"title": "تاريخ القراءة", "questionItem": {"question": {"required": True, "choiceQuestion": {"type": "DROP_DOWN", "options": [{"value": d} for d in date_options]}}}}, "location": {"index": 1}}}, {"createItem": {"item": {"title": "مدة قراءة الكتاب المشترك", "questionItem": {"question": {"required": True, "timeQuestion": {"duration": True}}}}, "location": {"index": 2}}}, {"createItem": {"item": {"title": "مدة قراءة كتاب آخر (إن وجد)", "questionItem": {"question": {"timeQuestion": {"duration": True}}}}, "location": {"index": 3}}}, {"createItem": {"item": {"title": "ما هي الاقتباسات التي أرسلتها اليوم؟ (اختر كل ما ينطبق)", "questionItem": {"question": {"choiceQuestion": {"type": "CHECKBOX", "options": [{"value": "أرسلت اقتباساً من الكتاب المشترك"}, {"value": "أرسلت اقتباساً من كتاب آخر"}]}}}}, "location": {"index": 4}}}, {"createItem": {"item": {"title": "إنجازات خاصة (اختر فقط عند حدوثه لأول مرة)", "pageBreakItem": {}}, "location": {"index": 5}}}, {"createItem": {"item": {"title": "إنجازات الكتب والنقاش", "questionItem": {"question": {"choiceQuestion": {"type": "CHECKBOX", "options": [{"value": "أنهيت الكتاب المشترك"}, {"value": "أنهيت كتاباً آخر"}, {"value": "حضرت جلسة النقاش"}]}}}}, "location": {"index": 6}}}]}
                    forms_service.forms().batchUpdate(formId=form_id, body=update_requests).execute()
                    db.set_setting("form_url", form_result['responderUri'])
                    with st.spinner("تتم مزامنة الملف مع Google Drive..."): time.sleep(7)
                    st.success("✅ تم إنشاء النموذج بنجاح!")
                    st.info("🔗 الخطوة 3: الربط النهائي (تتم يدوياً)")
                    editor_url = f"https://docs.google.com/forms/d/{form_id}/edit"
                    st.write("1. **افتح النموذج للتعديل** من الرابط الصحيح والمضمون أدناه:")
                    st.code(editor_url)
                    st.write("2. انتقل إلى تبويب **\"الردود\" (Responses)** داخل النموذج.")
                    st.write("3. اضغط على أيقونة جدول البيانات الأخضر **'Link to Sheets'**.")
                    st.write("4. اختر **'Select existing spreadsheet'** وقم باختيار الجدول الذي يحمل نفس الاسم.")
                    if st.button("لقد قمت بربط النموذج، تابع إلى الخطوة الأخيرة!"):
                        with st.spinner("جاري تنظيف جدول البيانات..."):
                            try:
                                spreadsheet = gc.open_by_url(spreadsheet_url)
                                default_sheet = spreadsheet.worksheet('Sheet1')
                                spreadsheet.del_worksheet(default_sheet)
                            except gspread.exceptions.WorksheetNotFound: pass
                            except Exception as e: st.warning(f"لم نتمكن من حذف الصفحة الفارغة تلقائياً: {e}.")
                        st.rerun()
                except Exception as e:
                    st.error(f"🌐 خطأ في الاتصال بخدمات جوجل: لم نتمكن من إنشاء النموذج. قد يكون السبب مشكلة مؤقتة. الخطأ: {e}")
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
                db.add_book_and_challenge(book_info, challenge_info)
                st.success("🎉 اكتمل الإعداد! تم إنشاء أول تحدي بنجاح. التطبيق جاهز الآن لاستقبال تسجيلات فريقك.")
                st.balloons()
                st.rerun()
            else:
                st.error("✏️ بيانات غير مكتملة: يرجى إدخال عنوان الكتاب واسم المؤلف للمتابعة.")
    st.stop()

# --- Main Dashboard Section ---
st.sidebar.title("التنقل")
page_options = ["لوحة التحكم", "مستكشف البيانات", "⚙️ الإدارة والتحكم", "إعدادات التحدي والنقاط"]
page = st.sidebar.radio("اختر صفحة لعرضها:", page_options, key="navigation")

logs_df = pd.DataFrame(all_data.get('logs', []))
achievements_df = pd.DataFrame(all_data.get('achievements', []))
books_df = db.get_table_as_df('Books')
member_stats_df = db.get_table_as_df('MemberStats')
if not member_stats_df.empty and not members_df.empty:
    member_stats_df = pd.merge(member_stats_df, members_df, on='member_id', how='left')

if page == "لوحة التحكم":
    st.header("📊 لوحة التحكم الرئيسية")
    challenge_options = {period['period_id']: f"{period['title']} ({period['start_date']} to {period['end_date']})" for index, period in periods_df.iterrows()}
    if not challenge_options:
        st.info("لا توجد تحديات حالية. يمكنك إضافة تحدي جديد من صفحة 'الإدارة والتحكم'.")
        st.stop()
    selected_challenge_id = st.selectbox("اختر فترة التحدي لعرضها:", options=list(challenge_options.keys()), format_func=lambda x: challenge_options[x], index=0)
    selected_period = periods_df[periods_df['period_id'] == selected_challenge_id].iloc[0]
    start_date_obj = pd.to_datetime(selected_period['start_date']).date()
    end_date_obj = pd.to_datetime(selected_period['end_date']).date()
    
    if not logs_df.empty:
        logs_df['submission_date_dt'] = pd.to_datetime(logs_df['submission_date'], format='%d/%m/%Y', errors='coerce').dt.date
        period_logs_df = logs_df[(logs_df['submission_date_dt'] >= start_date_obj) & (logs_df['submission_date_dt'] <= end_date_obj)].copy()
    else:
        period_logs_df = pd.DataFrame(columns=['common_book_minutes', 'other_book_minutes', 'member_id', 'submitted_common_quote', 'submitted_other_quote', 'submission_date_dt'])
    
    period_achievements_df = achievements_df[achievements_df['period_id'] == selected_challenge_id] if not achievements_df.empty else pd.DataFrame()
    days_total = (end_date_obj - start_date_obj).days + 1
    days_passed = (date.today() - start_date_obj).days + 1
    
    with st.container(border=True):
        st.subheader(f"📖 التحدي الحالي: {selected_period['title']}")
        st.caption(f"تأليف: {selected_period.get('author', 'غير معروف')} | مدة التحدي: من {selected_period['start_date']} إلى {selected_period['end_date']}")
        progress = min(max(days_passed / days_total, 0), 1)
        st.progress(progress, text=f"انقضى {days_passed if days_passed >= 0 else 0} يوم من أصل {days_total} يوم")
    st.divider()
    
    tab1, tab2, tab3, tab4 = st.tabs(["📈 أداء المجموعة", "🥇 منصة التتويج", "🔔 مؤشر الالتزام", "🔎 بطاقة القارئ"])
    
    with tab1:
        st.subheader("📈 أداء المجموعة في أرقام")
        if not period_logs_df.empty:
            total_minutes = period_logs_df['common_book_minutes'].sum() + period_logs_df['other_book_minutes'].sum()
            active_members_count = period_logs_df['member_id'].nunique()
            total_quotes = period_logs_df['submitted_common_quote'].sum() + period_logs_df['submitted_other_quote'].sum()
            avg_daily_reading = (total_minutes / active_members_count / days_passed) if active_members_count > 0 and days_passed > 0 else 0
        else:
            total_minutes, active_members_count, total_quotes, avg_daily_reading = 0, 0, 0, 0
        
        meetings_attended_count = period_achievements_df[period_achievements_df['achievement_type'] == 'ATTENDED_DISCUSSION']['member_id'].nunique() if not period_achievements_df.empty else 0
        
        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        kpi1.metric("إجمالي ساعات القراءة", f"{total_minutes / 60:.1f} ساعة")
        kpi2.metric("الأعضاء النشطون", f"{active_members_count} عضو")
        kpi3.metric("إجمالي الاقتباسات", f"{int(total_quotes)} اقتباس")
        kpi4.metric("حضور جلسة النقاش", f"{meetings_attended_count} عضو")
        kpi5.metric("متوسط القراءة اليومي للعضو", f"{avg_daily_reading:.1f} دقيقة")
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🔥 مؤشر حماس المجموعة (تراكمي)")
            if not period_logs_df.empty:
                daily_minutes = period_logs_df.groupby('submission_date_dt')[['common_book_minutes', 'other_book_minutes']].sum().sum(axis=1).reset_index(name='total_minutes')
                daily_minutes = daily_minutes.sort_values('submission_date_dt')
                daily_minutes['cumulative_minutes'] = daily_minutes['total_minutes'].cumsum()
                fig = px.area(daily_minutes, x='submission_date_dt', y='cumulative_minutes', labels={'submission_date_dt': 'التاريخ', 'cumulative_minutes': 'مجموع الدقائق التراكمي'})
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("لا توجد بيانات قراءة مسجلة لهذا التحدي بعد.")
        with col2:
            st.subheader("🗓️ الأيام الأكثر نشاطاً في الأسبوع")
            if not period_logs_df.empty:
                period_logs_df['weekday'] = pd.to_datetime(period_logs_df['submission_date_dt']).dt.day_name()
                weekday_order = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                weekly_activity = period_logs_df.groupby('weekday')['common_book_minutes'].count().reindex(weekday_order).reset_index(name='logs_count')
                fig = px.bar(weekly_activity, x='weekday', y='logs_count', labels={'weekday': 'اليوم', 'logs_count': 'عدد التسجيلات'})
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("لا توجد بيانات لرسم هذا المخطط.")

    with tab2:
        st.subheader("🥇 منصة التتويج: المتصدرون بالنقاط")
        if member_stats_df.empty:
            st.info("لا توجد إحصائيات لعرضها. الرجاء الضغط على زر التحديث لمزامنة البيانات.")
        else:
            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader("🏆 المتصدرون بالنقاط")
                top_members = member_stats_df.sort_values('total_points', ascending=False)
                fig = px.bar(top_members, y='name', x='total_points', orientation='h', title="أعلى الأعضاء نقاطاً", text_auto=True, labels={'name': 'اسم العضو', 'total_points': 'مجموع النقاط'})
                fig.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                st.subheader("🌟 نجوم التحدي")
                if not period_achievements_df.empty and not members_df.empty:
                    common_finishers = period_achievements_df[period_achievements_df['achievement_type'] == 'FINISHED_COMMON_BOOK']
                    if not common_finishers.empty:
                        fastest_finisher_id = common_finishers.sort_values('achievement_date').iloc[0]['member_id']
                        fastest_finisher_name = members_df[members_df['member_id'] == fastest_finisher_id]['name'].iloc[0]
                        st.metric("🚀 القارئ الصاروخي", fastest_finisher_name)
                    finished_books_count = member_stats_df.set_index('name')[['total_common_books_read', 'total_other_books_read']].sum(axis=1)
                    if not finished_books_count.empty and finished_books_count.max() > 0:
                        king_of_books = finished_books_count.idxmax()
                        st.metric("👑 ملك الكتب", king_of_books, int(finished_books_count.max()))
                    meetings_count = member_stats_df.set_index('name')['meetings_attended']
                    if not meetings_count.empty and meetings_count.max() > 0:
                        discussion_dean = meetings_count.idxmax()
                        st.metric("⭐ عميد الحضور", discussion_dean, int(meetings_count.max()))
                else:
                    st.info("لم يتم تسجيل أي إنجازات بعد.")

    with tab3:
        st.subheader("🔔 مؤشر الالتزام (تنبيهات الغياب)")
        st.warning("هذه القوائم تظهر الأعضاء الذين تجاوزوا الحد المسموح به للغياب وقد يتم تطبيق خصومات عليهم.")
        if member_stats_df.empty:
            st.info("لا توجد إحصائيات لعرضها. الرجاء الضغط على زر التحديث لمزامنة البيانات.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("الغياب عن تسجيل القراءة")
                inactive_loggers = member_stats_df[member_stats_df['log_streak'] > 0][['name', 'log_streak']].sort_values('log_streak', ascending=False)
                if not inactive_loggers.empty:
                    st.dataframe(inactive_loggers.rename(columns={'name': 'الاسم', 'log_streak': 'أيام الغياب'}), use_container_width=True, hide_index=True)
                else:
                    st.success("✅ جميع الأعضاء ملتزمون بتسجيل قراءتهم. عمل رائع!")
            with col2:
                st.subheader("الغياب عن إرسال الاقتباسات")
                inactive_quoters = member_stats_df[member_stats_df['quote_streak'] > 0][['name', 'quote_streak']].sort_values('quote_streak', ascending=False)
                if not inactive_quoters.empty:
                    st.dataframe(inactive_quoters.rename(columns={'name': 'الاسم', 'quote_streak': 'أيام بلا اقتباس'}), use_container_width=True, hide_index=True)
                else:
                    st.success("✅ جميع الأعضاء ملتزمون بإرسال الاقتباسات. ممتاز!")
    
    with tab4:
        st.subheader("🔎 تحليل الأداء الفردي: بطاقة القارئ")
        if not members_df.empty:
            member_list = members_df['name'].tolist()
            selected_member_name = st.selectbox("اختر قارئًا لعرض بطاقته:", member_list)
            if selected_member_name and not member_stats_df.empty:
                member_id = members_df[members_df['name'] == selected_member_name]['member_id'].iloc[0]
                member_logs_all = logs_df[logs_df['member_id'] == member_id].copy() if not logs_df.empty else pd.DataFrame()
                member_stats_row = member_stats_df[member_stats_df['member_id'] == member_id]
                if not member_stats_row.empty:
                    member_stats_all = member_stats_row.iloc[0]
                    st.header(f"بطاقة أداء: {selected_member_name}")
                    total_books_read = member_stats_all['total_common_books_read'] + member_stats_all['total_other_books_read']
                    total_reading_hours = (member_stats_all['total_reading_minutes_common'] + member_stats_all['total_reading_minutes_other']) / 60
                    if not member_logs_all.empty:
                        member_logs_all['submission_date_dt'] = pd.to_datetime(member_logs_all['submission_date'], format='%d/%m/%Y').dt.date
                        days_logged = member_logs_all['submission_date_dt'].nunique()
                        total_minutes_logged = member_logs_all['common_book_minutes'].sum() + member_logs_all['other_book_minutes'].sum()
                        avg_minutes_per_reading_day = total_minutes_logged / days_logged if days_logged > 0 else 0
                    else:
                        avg_minutes_per_reading_day = 0
                    kpi1, kpi2, kpi3 = st.columns(3)
                    kpi1.metric("📚 إجمالي الكتب المنهَاة", f"{int(total_books_read)} كتاب")
                    kpi2.metric("⏱️ إجمالي ساعات القراءة", f"{total_reading_hours:.1f} ساعة")
                    kpi3.metric("📈 متوسط القراءة اليومي", f"{avg_minutes_per_reading_day:.1f} دقيقة/يوم")
                else:
                    st.info(f"لم يتم العثور على إحصائيات لـ {selected_member_name}. الرجاء تحديث البيانات.")
            else:
                st.info("لا يوجد أعضاء في قاعدة البيانات لعرضهم.")
        else:
            st.info("لا يوجد أعضاء في قاعدة البيانات لعرضهم.")

elif page == "مستكشف البيانات":
    st.header("🔬 مستكشف البيانات")
    st.info("هذه الصفحة تتيح لك استعراض البيانات الخام في قاعدة البيانات مباشرة للتأكد من صحتها.")
    st.subheader("ملخص قاعدة البيانات")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("👥 عدد الأعضاء", f"{len(members_df)} عضو")
    kpi2.metric("📖 عدد الكتب", f"{len(books_df)} كتاب")
    kpi3.metric("✍️ إجمالي التسجيلات", f"{len(logs_df)} تسجيل")
    kpi4.metric("🏆 إجمالي الإنجازات", f"{len(achievements_df)} إنجاز")
    st.divider()
    st.subheader("استعراض تفاصيل الجداول")
    with st.expander("📖 عرض جدول سجلات القراءة (ReadingLogs)"):
        if not logs_df.empty and not members_df.empty:
            display_df = pd.merge(logs_df, members_df, on='member_id', how='left')
            st.dataframe(display_df, use_container_width=True)
        else:
            st.info("جدول سجلات القراءة فارغ.")
    with st.expander("🏆 عرض جدول الإنجازات (Achievements)"):
        if not achievements_df.empty:
            display_df = pd.merge(achievements_df, members_df, on='member_id', how='left', suffixes=('', '_member'))
            if not books_df.empty:
                 display_df = pd.merge(display_df, books_df, on='book_id', how='left', suffixes=('', '_book'))
            st.dataframe(display_df, use_container_width=True)
        else:
            st.info("جدول الإنجازات فارغ.")
    with st.expander("📊 عرض جدول إحصائيات الأعضاء (MemberStats)"):
        if not member_stats_df.empty:
            st.dataframe(member_stats_df, use_container_width=True)
        else:
            st.info("جدول إحصائيات الأعضاء فارغ. قم بمزامنة البيانات لتعبئته.")
    with st.expander("📚 عرض الجداول الأساسية (كتب، أعضاء، فترات)"):
        st.write("#### جدول الأعضاء (Members)"); st.dataframe(members_df, use_container_width=True)
        st.write("#### جدول الكتب (Books)"); st.dataframe(books_df, use_container_width=True)
        st.write("#### جدول فترات التحدي (ChallengePeriods)"); st.dataframe(periods_df, use_container_width=True)

elif page == "⚙️ الإدارة والتحكم":
    st.header("✨ لوحة التحكم الإدارية")
    st.subheader("📅 إدارة تحديات القراءة")
    today_str = str(date.today())
    active_period_id = None
    if not periods_df.empty:
        active_periods = periods_df[(periods_df['start_date'] <= today_str) & (periods_df['end_date'] >= today_str)]
        if not active_periods.empty:
            active_period_id = active_periods.iloc[0]['period_id']
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
        with st.form("add_new_challenge_form", clear_on_submit=True):
            new_title = st.text_input("عنوان الكتاب الجديد")
            new_author = st.text_input("مؤلف الكتاب الجديد")
            new_year = st.number_input("سنة نشر الكتاب الجديد", value=datetime.now().year, step=1)
            last_end_date = pd.to_datetime(periods_df['end_date'].max()).date() if not periods_df.empty else date.today() - timedelta(days=1)
            suggested_start = last_end_date + timedelta(days=1)
            new_start = st.date_input("تاريخ بداية التحدي الجديد", value=suggested_start)
            new_end = st.date_input("تاريخ نهاية التحدي الجديد", value=suggested_start + timedelta(days=30))
            if st.form_submit_button("إضافة التحدي"):
                if new_start <= last_end_date:
                    st.error(f"⛔ التواريخ متداخلة: لا يمكن بدء تحدي جديد قبل انتهاء التحدي السابق. يرجى اختيار تاريخ بداية بعد {last_end_date}.")
                elif not new_title or not new_author:
                    st.error("✏️ بيانات غير مكتملة: يرجى إدخال عنوان الكتاب واسم المؤلف للمتابعة.")
                elif new_start >= new_end:
                    st.error("🗓️ خطأ في التواريخ: تاريخ نهاية التحدي يجب أن يكون بعد تاريخ بدايته.")
                else:
                    book_info = {'title': new_title, 'author': new_author, 'year': new_year}
                    challenge_info = {'start_date': str(new_start), 'end_date': str(new_end)}
                    if db.add_book_and_challenge(book_info, challenge_info):
                        st.success(f"✅ تمت الإضافة بنجاح! تحدي قراءة كتاب \"{new_title}\" جاهز الآن."); st.rerun()
    st.divider()
    st.subheader("👥 إدارة المشاركين")
    st.warning("⚠️ تنبيه هام: حذف عضو هو إجراء نهائي سيؤدي إلى مسح جميع سجلاته وإنجازاته ونقاطه بشكل دائم.")
    cols = st.columns((4, 1))
    cols[0].write("**اسم العضو**")
    cols[1].write("**إجراء**")
    all_members_df = db.get_table_as_df('Members')
    for index, member in all_members_df.iterrows():
        col1, col2 = st.columns((4, 1))
        col1.write(member['name'])
        if col2.button("🗑️ حذف", key=f"delete_member_{member['member_id']}", use_container_width=True):
            st.session_state['member_to_delete'] = member['member_id']
            st.session_state['member_delete_confirmation_phrase'] = f"أوافق على حذف {member['name']}"
    if 'challenge_to_delete' in st.session_state:
        @st.experimental_dialog("🚫 تأكيد الحذف النهائي (لا يمكن التراجع)")
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
    if 'member_to_delete' in st.session_state:
        @st.experimental_dialog("🚫 تأكيد الحذف النهائي (لا يمكن التراجع)")
        def show_member_delete_dialog():
            st.warning("☢️ إجراء لا يمكن التراجع عنه: أنت على وشك حذف العضو وكل بياناته نهائياً.")
            confirmation_phrase = st.session_state['member_delete_confirmation_phrase']
            st.code(confirmation_phrase)
            user_input = st.text_input("اكتب عبارة التأكيد هنا:", key="member_delete_input")
            if st.button("❌ حذف العضو نهائياً", disabled=(user_input != confirmation_phrase), type="primary"):
                if db.delete_member(st.session_state['member_to_delete']):
                    del st.session_state['member_to_delete']; st.success("🗑️ اكتمل الحذف."); st.rerun()
            if st.button("إلغاء"):
                del st.session_state['member_to_delete']; st.rerun()
        show_member_delete_dialog()

elif page == "إعدادات التحدي والنقاط":
    st.header("⚙️ إعدادات التحدي والنقاط")
    st.subheader("🔗 روابط جوجل (للمرجعية)")
    st.text_input("رابط جدول البيانات (Google Sheet)", value=db.get_setting("spreadsheet_url"), disabled=True)
    st.text_input("رابط نموذج التسجيل (للمستخدمين)", value=db.get_setting("form_url"), disabled=True)
    editor_url = (db.get_setting("form_url") or "").replace("/viewform", "/edit")
    st.text_input("رابط تعديل النموذج (للمشرف)", value=editor_url, disabled=True)
    st.divider()
    st.subheader("🎯 نظام النقاط والخصومات")
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
            if st.form_submit_button("حفظ الإعدادات", use_container_width=True):
                new_settings = {"minutes_per_point_common": s_m_common, "minutes_per_point_other": s_m_other, "quote_common_book_points": s_q_common, "quote_other_book_points": s_q_other, "finish_common_book_points": s_f_common, "finish_other_book_points": s_f_other, "attend_discussion_points": s_a_disc, "no_log_days_trigger": s_nl_trigger, "no_log_initial_penalty": s_nl_initial, "no_log_subsequent_penalty": s_nl_subsequent, "no_quote_days_trigger": s_nq_trigger, "no_quote_initial_penalty": s_nq_initial, "no_quote_subsequent_penalty": s_nq_subsequent}
                if db.update_global_settings(new_settings):
                    st.success("👍 تم حفظ التغييرات! تم تحديث نظام النقاط والخصومات بنجاح.")
                else:
                    st.error("حدث خطأ أثناء تحديث الإعدادات.")
