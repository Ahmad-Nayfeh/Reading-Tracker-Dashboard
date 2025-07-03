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

# --- Helper function to create Activity Heatmap ---
def create_activity_heatmap(df, start_date, end_date, title_text='خريطة الالتزام الحرارية (مجموع دقائق القراءة اليومية)'):
    """Generates a GitHub-style activity heatmap for reading data."""
    if df.empty:
        return go.Figure().update_layout(title="لا توجد بيانات قراءة لعرضها في الخريطة")

    df['date'] = pd.to_datetime(df['submission_date_dt'])
    
    full_date_range = pd.to_datetime(pd.date_range(start=start_date, end=end_date, freq='D'))
    
    daily_minutes = df.groupby(df['date'].dt.date)['total_minutes'].sum()
    
    heatmap_data = pd.DataFrame({'date': daily_minutes.index, 'minutes': daily_minutes.values})
    heatmap_data['date'] = pd.to_datetime(heatmap_data['date'])
    
    heatmap_data = pd.merge(pd.DataFrame({'date': full_date_range}), heatmap_data, on='date', how='left').fillna(0)

    heatmap_data['weekday_name'] = heatmap_data['date'].dt.strftime('%A')
    weekday_map_ar = {"Saturday": "السبت", "Sunday": "الأحد", "Monday": "الاثنين", "Tuesday": "الثلاثاء", "Wednesday": "الأربعاء", "Thursday": "الخميس", "Friday": "الجمعة"}
    heatmap_data['weekday_ar'] = heatmap_data['weekday_name'].map(weekday_map_ar)
    
    heatmap_data['week_of_year'] = heatmap_data['date'].dt.isocalendar().week
    heatmap_data['month_abbr'] = heatmap_data['date'].dt.strftime('%b')
    heatmap_data['day'] = heatmap_data['date'].dt.day
    heatmap_data['hover_text'] = heatmap_data.apply(lambda row: f"<b>{row['date'].strftime('%Y-%m-%d')} ({row['weekday_ar']})</b><br>دقائق القراءة: {int(row['minutes'])}", axis=1)

    weekday_order_ar = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"]
    heatmap_data['weekday_ar'] = pd.Categorical(heatmap_data['weekday_ar'], categories=weekday_order_ar, ordered=True)
    
    heatmap_pivot = heatmap_data.pivot_table(index='weekday_ar', columns='week_of_year', values='minutes', aggfunc='sum').fillna(0)
    hover_pivot = heatmap_data.pivot_table(index='weekday_ar', columns='week_of_year', values='hover_text', aggfunc=lambda x: ' '.join(x))

    month_positions = heatmap_data.drop_duplicates('month_abbr').set_index('month_abbr')
    
    fig = go.Figure(data=go.Heatmap(
        z=heatmap_pivot,
        x=heatmap_pivot.columns,
        y=heatmap_pivot.index,
        colorscale='Greens',
        hoverongaps=False,
        customdata=hover_pivot,
        hovertemplate='%{customdata}<extra></extra>'
    ))

    fig.update_layout(
        title=title_text,
        xaxis_title='أسابيع التحدي',
        yaxis_title='',
        xaxis=dict(tickmode='array', tickvals=list(month_positions.week_of_year), ticktext=list(month_positions.index)),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='#333'
    )
    return fig

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
                                    "type": "DROP_DOWN",
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
page_options = ["📈 لوحة التحكم العامة", "🎯 تحليلات التحديات", "⚙️ الإدارة والإعدادات"]
page = st.sidebar.radio("اختر صفحة لعرضها:", page_options, key="navigation")

# Load dataframes once
logs_df = pd.DataFrame(all_data.get('logs', []))
if not logs_df.empty:
    logs_df['submission_date_dt'] = pd.to_datetime(logs_df['submission_date'], format='%d/%m/%Y', errors='coerce').dt.date

achievements_df = pd.DataFrame(all_data.get('achievements', []))
member_stats_df = db.get_table_as_df('MemberStats')
if not member_stats_df.empty and not members_df.empty:
    member_stats_df = pd.merge(member_stats_df, members_df[['member_id', 'name']], on='member_id', how='left')

if page == "📈 لوحة التحكم العامة":
    st.header("📈 لوحة التحكم العامة")
    st.markdown("---")

    # --- Calculations for KPIs and Champions ---
    if not member_stats_df.empty:
        total_minutes = member_stats_df['total_reading_minutes_common'].sum() + member_stats_df['total_reading_minutes_other'].sum()
        total_hours = int(total_minutes // 60)
        
        total_books_finished = member_stats_df['total_common_books_read'].sum() + member_stats_df['total_other_books_read'].sum()
        total_quotes = member_stats_df['total_quotes_submitted'].sum()
        
        member_stats_df['total_reading_minutes'] = member_stats_df['total_reading_minutes_common'] + member_stats_df['total_reading_minutes_other']
        member_stats_df['total_books_read'] = member_stats_df['total_common_books_read'] + member_stats_df['total_other_books_read']

        king_of_reading = member_stats_df.loc[member_stats_df['total_reading_minutes'].idxmax()]
        king_of_books = member_stats_df.loc[member_stats_df['total_books_read'].idxmax()]
        king_of_points = member_stats_df.loc[member_stats_df['total_points'].idxmax()]
        king_of_quotes = member_stats_df.loc[member_stats_df['total_quotes_submitted'].idxmax()]
    else:
        total_hours, total_books_finished, total_quotes = 0, 0, 0
        king_of_reading, king_of_books, king_of_points, king_of_quotes = [None]*4

    active_members_count = len(members_df[members_df['is_active'] == 1]) if not members_df.empty else 0
    
    completed_challenges_count = 0
    if not periods_df.empty:
        today_date = date.today()
        periods_df['end_date_dt'] = pd.to_datetime(periods_df['end_date']).dt.date
        completed_challenges_count = len(periods_df[periods_df['end_date_dt'] < today_date])

    total_reading_days = len(logs_df['submission_date'].unique()) if not logs_df.empty else 0

    # --- Page Layout ---
    st.subheader("💡 الملخص الذكي")
    st.info("سيتم بناء هذا القسم لعرض رؤى سريعة ومقارنات ذكية.")
    st.markdown("---")

    st.subheader("📊 مؤشرات الأداء الرئيسية (KPIs)")
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric(label="⏳ إجمالي ساعات القراءة", value=f"{total_hours:,}")
    kpi2.metric(label="📚 إجمالي الكتب المنهَاة", value=f"{total_books_finished:,}")
    kpi3.metric(label="✍️ إجمالي الاقتباسات المرسلة", value=f"{total_quotes:,}")

    kpi4, kpi5, kpi6 = st.columns(3)
    kpi4.metric(label="👥 عدد الأعضاء النشطين", value=f"{active_members_count}")
    kpi5.metric(label="🏁 عدد التحديات المكتملة", value=f"{completed_challenges_count}")
    kpi6.metric(label="🗓️ عدد أيام القراءة", value=f"{total_reading_days}")
    st.markdown("---")

    st.subheader("🏆 أبطال الماراثون (All-Time Champions)")
    if king_of_reading is not None:
        champ1, champ2 = st.columns(2)
        with champ1:
            st.success(f"**👑 ملك القراءة: {king_of_reading['name']}**")
            st.write(f"بمجموع **{int(king_of_reading['total_reading_minutes'] // 60)}** ساعة قراءة.")
        with champ2:
            st.success(f"**📚 ملك الكتب: {king_of_books['name']}**")
            st.write(f"بمجموع **{int(king_of_books['total_books_read'])}** كتاب منهى.")
        
        champ3, champ4 = st.columns(2)
        with champ3:
            st.success(f"**⭐ ملك النقاط: {king_of_points['name']}**")
            st.write(f"بمجموع **{int(king_of_points['total_points'])}** نقطة.")
        with champ4:
            st.success(f"**✍️ ملك الاقتباسات: {king_of_quotes['name']}**")
            st.write(f"بمجموع **{int(king_of_quotes['total_quotes_submitted'])}** اقتباس مرسل.")
    else:
        st.info("لا توجد بيانات كافية لعرض الأبطال بعد.")
    st.markdown("---")

    st.subheader("📚 تحليلات الكتب")
    st.info("سيتم بناء هذا القسم لتحليل الكتب الأكثر حماساً والأصعب.")
    st.markdown("---")

    st.subheader("📈 مخططات الأداء التراكمي")
    if logs_df.empty:
        st.info("لا توجد بيانات لعرض المخططات البيانية بعد.")
    else:
        # Reading Growth Chart (Line Chart)
        logs_df['month'] = logs_df['submission_date_dt'].apply(lambda x: x.strftime('%Y-%m'))
        monthly_minutes = logs_df.groupby('month')[['common_book_minutes', 'other_book_minutes']].sum().sum(axis=1).reset_index(name='minutes')
        monthly_minutes['cumulative_minutes'] = monthly_minutes['minutes'].cumsum()
        
        fig_growth = px.line(monthly_minutes, x='month', y='cumulative_minutes', 
                             title='نمو القراءة التراكمي للمجموعة عبر الأشهر',
                             labels={'month': 'الشهر', 'cumulative_minutes': 'مجموع الدقائق التراكمي'},
                             markers=True)
        st.plotly_chart(fig_growth, use_container_width=True)

        # Points Leaderboard (Bar Chart)
        points_leaderboard = member_stats_df.sort_values('total_points', ascending=False).head(15)
        fig_points_leaderboard = px.bar(points_leaderboard, x='total_points', y='name', orientation='h',
                                        title='المتصدرون بالنقاط (إجمالي)',
                                        labels={'total_points': 'إجمالي النقاط', 'name': 'اسم العضو'},
                                        text='total_points')
        fig_points_leaderboard.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_points_leaderboard, use_container_width=True)

        # Reading Hours Leaderboard (Bar Chart)
        member_stats_df['total_hours'] = member_stats_df['total_reading_minutes'] / 60
        hours_leaderboard = member_stats_df.sort_values('total_hours', ascending=False).head(15)
        fig_hours_leaderboard = px.bar(hours_leaderboard, x='total_hours', y='name', orientation='h',
                                       title='المتصدرون بساعات القراءة (إجمالي)',
                                       labels={'total_hours': 'إجمالي ساعات القراءة', 'name': 'اسم العضو'},
                                       text='total_hours')
        fig_hours_leaderboard.update_traces(texttemplate='%{text:.1f}')
        fig_hours_leaderboard.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_hours_leaderboard, use_container_width=True)


elif page == "🎯 تحليلات التحديات":
    st.header("🎯 تحليلات التحديات")

    if periods_df.empty:
        st.info("لا توجد تحديات حالية أو سابقة لعرض تحليلاتها. يمكنك إضافة تحدي جديد من صفحة 'الإدارة والإعدادات'.")
        st.stop()
    
    today = date.today()
    
    challenge_options_map = {period['period_id']: period.to_dict() for index, period in periods_df.iterrows()}

    active_challenges, past_challenges, future_challenges = [], [], []
    for period_id, period_data in challenge_options_map.items():
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
    
    sorted_option_ids = future_challenges + active_challenges + past_challenges
    
    if not sorted_option_ids:
        st.info("لا توجد تحديات لعرضها في الفلتر.")
        st.stop()

    def format_challenge_option(period_id):
        period_data = challenge_options_map[period_id]
        
        status_emoji = ""
        if period_id in active_challenges: status_emoji = " (الحالي) 🟢"
        if period_id in past_challenges: status_emoji = " (السابق) 🏁"
        if period_id in future_challenges: status_emoji = " (المقبل) ⏳"
            
        return f"{period_data['title']} | {period_data['start_date']} إلى {period_data['end_date']}{status_emoji}"

    default_index = 0
    if active_challenges:
        active_id = active_challenges[0]
        if active_id in sorted_option_ids:
            default_index = sorted_option_ids.index(active_id)
    
    selected_period_id = st.selectbox(
        "اختر تحدياً لعرض تحليلاته:",
        options=sorted_option_ids,
        format_func=format_challenge_option,
        index=default_index,
        key="challenge_selector"
    )

    st.markdown("---")

    if selected_period_id:
        selected_challenge_data = challenge_options_map[selected_period_id]
        st.subheader(f"تحليلات تحدي: {selected_challenge_data['title']}")

        start_date_obj = datetime.strptime(selected_challenge_data['start_date'], '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(selected_challenge_data['end_date'], '%Y-%m-%d').date()
        
        period_logs_df = pd.DataFrame()
        if not logs_df.empty:
            period_logs_df = logs_df[(logs_df['submission_date_dt'].notna()) & (logs_df['submission_date_dt'] >= start_date_obj) & (logs_df['submission_date_dt'] <= end_date_obj)].copy()
        
        period_achievements_df = pd.DataFrame()
        if not achievements_df.empty:
            period_achievements_df = achievements_df[achievements_df['period_id'] == selected_period_id].copy()

        podium_df = pd.DataFrame()
        if not period_logs_df.empty:
            period_participants_ids = period_logs_df['member_id'].unique()
            period_members_df = members_df[members_df['member_id'].isin(period_participants_ids)]

            podium_data = []
            period_rules = selected_challenge_data

            for _, member in period_members_df.iterrows():
                member_id = member['member_id']
                member_logs = period_logs_df[period_logs_df['member_id'] == member_id]
                
                member_achievements = pd.DataFrame()
                if not period_achievements_df.empty:
                    member_achievements = period_achievements_df[period_achievements_df['member_id'] == member_id]

                points = 0
                if not member_logs.empty:
                    common_minutes = member_logs['common_book_minutes'].sum()
                    other_minutes = member_logs['other_book_minutes'].sum()
                    common_quotes = member_logs['submitted_common_quote'].sum()
                    other_quotes = member_logs['submitted_other_quote'].sum()

                    if period_rules.get('minutes_per_point_common', 0) > 0:
                        points += common_minutes // period_rules['minutes_per_point_common']
                    if period_rules.get('minutes_per_point_other', 0) > 0:
                        points += other_minutes // period_rules['minutes_per_point_other']
                    
                    points += common_quotes * period_rules.get('quote_common_book_points', 0)
                    points += other_quotes * period_rules.get('quote_other_book_points', 0)
                
                if not member_achievements.empty:
                    for _, ach in member_achievements.iterrows():
                        ach_type = ach['achievement_type']
                        if ach_type == 'FINISHED_COMMON_BOOK':
                            points += period_rules.get('finish_common_book_points', 0)
                        elif ach_type == 'ATTENDED_DISCUSSION':
                            points += period_rules.get('attend_discussion_points', 0)
                        elif ach_type == 'FINISHED_OTHER_BOOK':
                            points += period_rules.get('finish_other_book_points', 0)

                total_minutes = member_logs['common_book_minutes'].sum() + member_logs['other_book_minutes'].sum()
                total_hours = total_minutes / 60
                total_quotes = member_logs['submitted_common_quote'].sum() + member_logs['submitted_other_quote'].sum()

                podium_data.append({
                    'member_id': member_id,
                    'name': member['name'],
                    'points': int(points),
                    'hours': total_hours,
                    'quotes': int(total_quotes)
                })
            podium_df = pd.DataFrame(podium_data)

        tab1, tab2, tab3 = st.tabs(["📝 ملخص التحدي", "🥇 منصة التتويج", "🧑‍💻 بطاقة القارئ"])

        with tab1:
            if period_logs_df.empty:
                st.info("لا توجد بيانات مسجلة لهذا التحدي بعد.")
            else:
                st.write("**مؤشر التقدم**")
                total_days = (end_date_obj - start_date_obj).days
                days_passed = (today - start_date_obj).days if today > start_date_obj else 0
                progress = min(1.0, days_passed / total_days if total_days > 0 else 0)
                st.progress(progress, text=f"انقضى {days_passed} يوم من أصل {total_days} يوم")
                st.markdown("---")

                total_period_minutes = period_logs_df['common_book_minutes'].sum() + period_logs_df['other_book_minutes'].sum()
                total_period_hours = int(total_period_minutes // 60)
                
                active_participants = period_logs_df['member_id'].nunique()
                avg_daily_reading = (total_period_minutes / days_passed / active_participants) if days_passed > 0 and active_participants > 0 else 0
                
                total_period_quotes = period_logs_df['submitted_common_quote'].sum() + period_logs_df['submitted_other_quote'].sum()

                kpi1, kpi2, kpi3, kpi4 = st.columns(4)
                kpi1.metric("⏳ مجموع ساعات القراءة", f"{total_period_hours:,}")
                kpi2.metric("👥 المشاركون الفعليون", f"{active_participants}")
                kpi3.metric("✍️ الاقتباسات المرسلة", f"{total_period_quotes}")
                kpi4.metric("📊 متوسط القراءة اليومي/عضو", f"{avg_daily_reading:.1f} دقيقة")
                st.markdown("---")

                st.write("**مخطط حماس المجموعة**")
                period_logs_df['total_minutes'] = period_logs_df['common_book_minutes'] + period_logs_df['other_book_minutes']
                daily_cumulative_minutes = period_logs_df.groupby('submission_date_dt')['total_minutes'].sum().cumsum().reset_index()
                
                fig_area = px.area(daily_cumulative_minutes, x='submission_date_dt', y='total_minutes', title='مجموع دقائق القراءة التراكمي للمجموعة', labels={'submission_date_dt': 'تاريخ التحدي', 'total_minutes': 'مجموع الدقائق التراكمي'})
                st.plotly_chart(fig_area, use_container_width=True)

                heatmap_fig = create_activity_heatmap(period_logs_df, start_date_obj, end_date_obj)
                st.plotly_chart(heatmap_fig, use_container_width=True)

        with tab2:
            if podium_df.empty:
                st.info("لا توجد بيانات مسجلة لهذا التحدي بعد لعرض منصة التتويج.")
            else:
                st.subheader("🏆 متصدرو النقاط")
                points_chart_df = podium_df.sort_values('points', ascending=False).head(10)
                fig_points = px.bar(points_chart_df, x='points', y='name', orientation='h', 
                                    title="أعلى 10 أعضاء في النقاط",
                                    labels={'points': 'مجموع النقاط', 'name': 'اسم العضو'},
                                    text='points')
                fig_points.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_points, use_container_width=True)

                st.markdown("---")

                st.subheader("⏳ متصدرو القراءة")
                hours_chart_df = podium_df.sort_values('hours', ascending=False).head(10)
                fig_hours = px.bar(hours_chart_df, x='hours', y='name', orientation='h',
                                   title="أعلى 10 أعضاء في ساعات القراءة",
                                   labels={'hours': 'مجموع ساعات القراءة', 'name': 'اسم العضو'},
                                   text='hours')
                fig_hours.update_traces(texttemplate='%{text:.1f}')
                fig_hours.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_hours, use_container_width=True)

                st.markdown("---")

                st.subheader("✍️ متصدرو الاقتباسات")
                quotes_chart_df = podium_df.sort_values('quotes', ascending=False).head(10)
                fig_quotes = px.bar(quotes_chart_df, x='quotes', y='name', orientation='h',
                                    title="أعلى 10 أعضاء في إرسال الاقتباسات",
                                    labels={'quotes': 'مجموع الاقتباسات', 'name': 'اسم العضو'},
                                    text='quotes')
                fig_quotes.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_quotes, use_container_width=True)

        with tab3:
            if podium_df.empty:
                st.info("لا يوجد مشاركون في هذا التحدي بعد.")
            else:
                member_names = sorted(podium_df['name'].tolist())
                selected_member_name = st.selectbox("اختر قارئاً لعرض بطاقته:", member_names)

                if selected_member_name:
                    member_data = podium_df[podium_df['name'] == selected_member_name].iloc[0]
                    member_id = member_data['member_id']
                    
                    st.subheader(f"بطاقة أداء: {selected_member_name}")

                    c1, c2, c3 = st.columns(3)
                    c1.metric("⭐ النقاط", f"{member_data['points']}")
                    c2.metric("⏳ ساعات القراءة", f"{member_data['hours']:.1f}")
                    c3.metric("✍️ الاقتباسات", f"{member_data['quotes']}")
                    st.markdown("---")

                    st.subheader("🏅 الأوسمة والشارات")
                    member_logs = period_logs_df[period_logs_df['member_id'] == member_id]
                    member_achievements = period_achievements_df[period_achievements_df['member_id'] == member_id] if not period_achievements_df.empty else pd.DataFrame()

                    badges_unlocked = []
                    if member_data['quotes'] > 10:
                        badges_unlocked.append("✍️ **وسام الفيلسوف:** إرسال أكثر من 10 اقتباسات.")
                    if not member_achievements.empty:
                        finish_common_ach = member_achievements[member_achievements['achievement_type'] == 'FINISHED_COMMON_BOOK']
                        if not finish_common_ach.empty:
                            finish_date = pd.to_datetime(finish_common_ach.iloc[0]['achievement_date']).date()
                            if (finish_date - start_date_obj).days <= 7:
                                badges_unlocked.append("🏃‍♂️ **وسام العدّاء:** إنهاء الكتاب في الأسبوع الأول.")
                    if not member_logs.empty:
                        log_dates = sorted(member_logs['submission_date_dt'].unique())
                        if len(log_dates) >= 7:
                            max_streak = 0
                            current_streak = 1
                            for i in range(1, len(log_dates)):
                                if (log_dates[i] - log_dates[i-1]).days == 1:
                                    current_streak += 1
                                else:
                                    max_streak = max(max_streak, current_streak)
                                    current_streak = 1
                            max_streak = max(max_streak, current_streak)
                            if max_streak >= 7:
                                badges_unlocked.append(f"💯 **وسام المثابرة:** القراءة لـ {max_streak} أيام متتالية.")
                    
                    if badges_unlocked:
                        for badge in badges_unlocked:
                            st.success(badge)
                    else:
                        st.info("لم يحصل هذا القارئ على أي أوسمة في هذا التحدي بعد.")
                    st.markdown("---")

                    st.subheader("🎯 الإنجازات")
                    if not member_achievements.empty:
                        achievement_map = {
                            'FINISHED_COMMON_BOOK': 'إنهاء الكتاب المشترك',
                            'ATTENDED_DISCUSSION': 'حضور جلسة النقاش',
                            'FINISHED_OTHER_BOOK': 'إنهاء كتاب آخر'
                        }
                        for _, ach in member_achievements.iterrows():
                            st.markdown(f"- **{achievement_map.get(ach['achievement_type'], ach['achievement_type'])}** (بتاريخ: {ach['achievement_date']})")
                    else:
                        st.info("لم يحقق هذا القارئ أي إنجازات في هذا التحدي بعد.")
                    st.markdown("---")
                    
                    member_logs['total_minutes'] = member_logs['common_book_minutes'] + member_logs['other_book_minutes']
                    individual_heatmap = create_activity_heatmap(member_logs, start_date_obj, end_date_obj, title_text=f"خريطة التزام: {selected_member_name}")
                    st.plotly_chart(individual_heatmap, use_container_width=True)

    else:
        st.info("يرجى اختيار تحدي من القائمة أعلاه.")


elif page == "⚙️ الإدارة والإعدادات":
    st.header("⚙️ الإدارة والإعدادات")
    
    admin_tab1, admin_tab2 = st.tabs(["إدارة المشاركين والتحديات", "إعدادات النقاط والروابط"])

    with admin_tab1:
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

    with admin_tab2:
        st.subheader("🔗 روابط جوجل (للمرجعية)")
        st.text_input("رابط جدول البيانات (Google Sheet)", value=db.get_setting("spreadsheet_url"), disabled=True)
        st.text_input("رابط نموذج التسجيل (للمستخدمين)", value=db.get_setting("form_url"), disabled=True)
        editor_url = (db.get_setting("form_url") or "").replace("/viewform", "/edit")
        st.text_input("رابط تعديل النموذج (للمشرف)", value=editor_url, disabled=True)
        st.divider()
        st.subheader("🎯 نظام النقاط الافتراضي")
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
                
                if st.form_submit_button("حفظ الإعدادات الافتراضية", use_container_width=True):
                    new_settings = {
                        "minutes_per_point_common": s_m_common, "minutes_per_point_other": s_m_other,
                        "quote_common_book_points": s_q_common, "quote_other_book_points": s_q_other,
                        "finish_common_book_points": s_f_common, "finish_other_book_points": s_f_other,
                        "attend_discussion_points": s_a_disc
                    }
                    if db.update_global_settings(new_settings):
                        st.success("👍 تم حفظ التغييرات! تم تحديث نظام النقاط الافتراضي بنجاح.")
                    else:
                        st.error("حدث خطأ أثناء تحديث الإعدادات.")
