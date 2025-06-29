import streamlit as st
import pandas as pd
import datetime
import db_manager as db
import plotly.express as px
import plotly.graph_objects as go


# --- Page Configuration ---
st.set_page_config(
    page_title="Reading Challenge Dashboard",
    page_icon="📚",
    layout="wide"
)

# --- Initial Data Load & State Check ---
all_data = db.get_all_data_for_stats()
if all_data:
    members_df = pd.DataFrame(all_data.get('members', []))
    periods_df = pd.DataFrame(all_data.get('periods', []))
    logs_df = pd.DataFrame(all_data.get('logs', []))
    achievements_df = pd.DataFrame(all_data.get('achievements', []))
    books_df = db.get_table_as_df('Books')
    
    member_stats_df = db.get_table_as_df('MemberStats')
    if not member_stats_df.empty and not members_df.empty:
        member_stats_df = pd.merge(member_stats_df, members_df, on='member_id')

    setup_complete = not (members_df.empty or periods_df.empty)
else:
    members_df, periods_df, logs_df, achievements_df, member_stats_df, books_df = pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    setup_complete = False

# --- Main Application Logic ---
st.title("📚 لوحة تحكم تحدي القرّاء")

# State 1 & 2: Setup Wizard and Script Generation
if not setup_complete:
    st.warning("👋 مرحباً بك! لنقم بإعداد تحدي القراءة الخاص بك.")
    if members_df.empty:
        st.subheader("الخطوة 1: إضافة أعضاء المجموعة")
        with st.form("new_members_form"):
            names_str = st.text_area("أسماء الأعضاء", height=150, placeholder="خالد\nسارة\n...")
            if st.form_submit_button("إضافة الأعضاء"):
                names = [name.strip() for name in names_str.split('\n') if name.strip()]
                if names:
                    db.add_members(names)
                    st.rerun()
    elif periods_df.empty:
        st.subheader("الخطوة 2: إنشاء أول فترة تحدي")
        with st.form("new_challenge_form", clear_on_submit=True):
            st.text_input("عنوان الكتاب", key="book_title"); st.text_input("اسم المؤلف", key="book_author")
            st.number_input("سنة النشر", key="pub_year", value=2024, step=1)
            st.date_input("تاريخ بداية التحدي", key="start_date")
            st.date_input("تاريخ نهاية التحدي", key="end_date", value=datetime.date.today() + datetime.timedelta(days=30))
            if st.form_submit_button("إنشاء التحدي"):
                if st.session_state.book_title and st.session_state.book_author:
                    book_info = {'title': st.session_state.book_title, 'author': st.session_state.book_author, 'year': st.session_state.pub_year}
                    challenge_info = {'start_date': str(st.session_state.start_date), 'end_date': str(st.session_state.end_date)}
                    if db.add_book_and_challenge(book_info, challenge_info):
                        st.session_state['show_script_after_setup'] = True
                        st.rerun()
                else:
                    st.error("الرجاء ملء عنوان الكتاب والمؤلف.")

elif st.session_state.get('show_script_after_setup', False):
    st.success("🎉 تم إعداد التحدي بنجاح! الخطوة الأخيرة هي ربط نموذج جوجل.")
    st.header("⚙️ إنشاء وربط نموذج جوجل (Google Form)")
    st.info(
        """
        لقد تم إنشاء كود **Google Apps Script** المخصص لمجموعتك.
        1.  **انسخ** الكود الموجود في الأسفل.
        2.  اتبع الخطوات المذكورة في ملف **README.md** لفتح محرر السكربت في Google Sheet ولصق هذا الكود.
        3.  بعد تشغيل الكود هناك، اضغط على الزر أدناه للانتقال إلى لوحة التحكم.
        """
    )
    member_names_for_js = ',\n'.join([f'  "{name}"' for name in members_df['name']])
    apps_script_code = f"""
function createReadingChallengeForm() {{
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const memberNames = [
{member_names_for_js}
  ];
  const form = FormApp.create('تسجيل القراءة اليومي - تحدي القرّاء')
    .setDescription('يرجى ملء هذا النموذج يومياً لتسجيل نشاطك في تحدي القراءة. بالتوفيق!')
    .setConfirmationMessage('شكراً لك، تم تسجيل قراءتك بنجاح!');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, spreadsheet.getId());
  const formUrl = form.getPublishedUrl();
  Logger.log('تم إنشاء النموذج بنجاح! الرابط الذي ستشاركه مع الأعضاء هو: ' + formUrl);
  form.addListItem().setTitle('اسمك').setHelpText('اختر اسمك من القائمة.').setRequired(true).setChoiceValues(memberNames);
  form.addDateItem().setTitle('تاريخ القراءة').setHelpText('حدد تاريخ اليوم الذي قرأت فيه.').setRequired(true);
  form.addDurationItem().setTitle('مدة قراءة الكتاب المشترك').setHelpText('أدخل المدة التي قضيتها في قراءة الكتاب المشترك اليوم.').setRequired(true);
  form.addDurationItem().setTitle('مدة قراءة كتاب آخر (إن وجد)').setHelpText('إذا كنت تقرأ كتاباً آخر، أدخل مدة قراءته هنا.').setRequired(false);
  const quoteItem = form.addCheckboxItem();
  quoteItem.setTitle('ما هي الاقتباسات التي أرسلتها اليوم؟ (اختر كل ما ينطبق)').setChoices([quoteItem.createChoice('أرسلت اقتباساً من الكتاب المشترك'), quoteItem.createChoice('أرسلت اقتباساً من كتاب آخر')]);
  form.addPageBreakItem().setTitle('الإنجازات الخاصة (اختر ما ينطبق عليك *فقط* عند حدوثه)');
  const achievementItem = form.addCheckboxItem();
  achievementItem.setTitle('إنجازات الكتب والنقاش').setHelpText('اختر هذا الخيار مرة واحدة فقط لكل إنجاز للحصول على النقاط الإضافية.').setChoices([achievementItem.createChoice('أنهيت الكتاب المشترك'), achievementItem.createChoice('أنهيت كتاباً آخر'), achievementItem.createChoice('حضرت جلسة النقاش')]);
  Logger.log('اكتملت العملية بنجاح. يمكنك الآن إغلاق محرر السكربت. الرابط لمشاركته مع الأعضاء تم طباعته في السجل أعلاه.');
}}
"""
    st.subheader("كود Google Apps Script المخصص لك")
    st.code(apps_script_code, language='javascript')
    if st.button("✅ لقد نسخت الكود، انتقل إلى لوحة التحكم"):
        st.session_state['show_script_after_setup'] = False
        st.rerun()

# State 3: Normal application view
else:
    st.sidebar.title("تنقل")
    page_options = ["لوحة التحكم", "مستكشف البيانات", "الإضافات", "الإعدادات"]
    page = st.sidebar.radio("اختر صفحة", page_options, key="navigation")

    if page == "لوحة التحكم":
        st.header("📊 لوحة التحكم الرئيسية")
        
        # --- Filter and data prep ---
        challenge_options = {period['period_id']: f"{period['title']} ({period['start_date']} to {period['end_date']})" for index, period in periods_df.iterrows()}
        default_challenge_id = periods_df['period_id'].max() if not periods_df.empty else 0
        selected_challenge_id = st.selectbox("اختر فترة التحدي لعرضها:", options=list(challenge_options.keys()), format_func=lambda x: challenge_options[x], index=0)
        
        selected_period = periods_df[periods_df['period_id'] == selected_challenge_id].iloc[0]
        start_date = pd.to_datetime(selected_period['start_date']).date()
        end_date = pd.to_datetime(selected_period['end_date']).date()
        
        if not logs_df.empty:
            logs_df['submission_date_dt'] = pd.to_datetime(logs_df['submission_date'], format='%d/%m/%Y').dt.date
            # THE FIX IS HERE: Use .copy() to avoid the warning
            period_logs_df = logs_df[(logs_df['submission_date_dt'] >= start_date) & (logs_df['submission_date_dt'] <= end_date)].copy()
        else:
            period_logs_df = pd.DataFrame()
            
        period_achievements_df = achievements_df[achievements_df['period_id'] == selected_challenge_id]
        
        days_total = (end_date - start_date).days + 1
        days_passed = (datetime.date.today() - start_date).days + 1
        
        with st.container(border=True):
            st.subheader(f"📖 التحدي الحالي: {selected_period['title']}")
            st.caption(f"تأليف: {selected_period['author']} | مدة التحدي: من {selected_period['start_date']} إلى {selected_period['end_date']}")
            progress = min(max(days_passed / days_total, 0), 1)
            st.progress(progress, text=f"انقضى {days_passed if days_passed >= 0 else 0} يوم من أصل {days_total} يوم")
        
        st.divider()
        
        tab1, tab2, tab3, tab4 = st.tabs(["📊 نظرة عامة", "🏆 لوحة المتصدرين", "🔔 تنبيهات النشاط", "👤 بطاقة القارئ"])
        
        with tab1:
            st.subheader("نظرة عامة على أداء المجموعة")
            
            # KPIs
            total_minutes = period_logs_df['common_book_minutes'].sum() + period_logs_df['other_book_minutes'].sum() if not period_logs_df.empty else 0
            active_members_count = period_logs_df['member_id'].nunique()
            total_quotes = period_logs_df['submitted_common_quote'].sum() + period_logs_df['submitted_other_quote'].sum() if not period_logs_df.empty else 0
            meetings_attended_count = period_achievements_df['member_id'].nunique() if not period_achievements_df.empty else 0
            avg_daily_reading = (total_minutes / active_members_count / days_passed) if active_members_count > 0 and days_passed > 0 else 0

            kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
            kpi1.metric("إجمالي ساعات القراءة", f"{total_minutes / 60:.1f} ساعة")
            kpi2.metric("الأعضاء النشطون", f"{active_members_count} عضو")
            kpi3.metric("إجمالي الاقتباسات", f"{total_quotes} اقتباس")
            kpi4.metric("حضور جلسة النقاش", f"{meetings_attended_count} عضو")
            kpi5.metric("متوسط القراءة اليومي للعضو", f"{avg_daily_reading:.1f} دقيقة")
            
            st.divider()

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("زخم القراءة التراكمي")
                if not period_logs_df.empty:
                    daily_minutes = period_logs_df.groupby('submission_date_dt')[['common_book_minutes', 'other_book_minutes']].sum().sum(axis=1).reset_index(name='total_minutes')
                    daily_minutes = daily_minutes.sort_values('submission_date_dt')
                    daily_minutes['cumulative_minutes'] = daily_minutes['total_minutes'].cumsum()
                    fig = px.area(daily_minutes, x='submission_date_dt', y='cumulative_minutes', labels={'submission_date_dt': 'التاريخ', 'cumulative_minutes': 'مجموع الدقائق'})
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("لا توجد بيانات قراءة مسجلة لهذا التحدي بعد.")
            with col2:
                st.subheader("توزيع القراءة الأسبوعي")
                if not period_logs_df.empty:
                    # THE FIX IS HERE: Add .copy() before modification
                    period_logs_df['weekday'] = pd.to_datetime(period_logs_df['submission_date_dt']).dt.day_name()
                    weekday_order = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                    weekly_activity = period_logs_df.groupby('weekday')['common_book_minutes'].count().reindex(weekday_order).reset_index(name='logs_count')
                    fig = px.bar(weekly_activity, x='weekday', y='logs_count', labels={'weekday': 'اليوم', 'logs_count': 'عدد التسجيلات'})
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("لا توجد بيانات لرسم هذا المخطط.")
            
            st.divider()
            
            st.subheader("تحليلات إضافية")
            col3, col4 = st.columns(2)
            with col3:
                st.subheader("توزيع وقت القراءة")
                if total_minutes > 0:
                    reading_split_data = {
                        'نوع القراءة': ['الكتاب المشترك', 'كتب أخرى'],
                        'الدقائق': [period_logs_df['common_book_minutes'].sum(), period_logs_df['other_book_minutes'].sum()]
                    }
                    fig = px.pie(pd.DataFrame(reading_split_data), names='نوع القراءة', values='الدقائق', hole=0.4, title="تقسيم وقت القراءة")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("لا توجد بيانات لعرض تقسيم وقت القراءة.")
            with col4:
                st.subheader("تحليل مصادر النقاط")
                settings = db.load_global_settings()
                if settings:
                    reading_points_common = (period_logs_df['common_book_minutes'].sum() // settings.get('minutes_per_point_common', 1))
                    reading_points_other = (period_logs_df['other_book_minutes'].sum() // settings.get('minutes_per_point_other', 1))
                    quote_points_common = period_logs_df['submitted_common_quote'].sum() * settings.get('quote_common_book_points', 0)
                    quote_points_other = period_logs_df['submitted_other_quote'].sum() * settings.get('quote_other_book_points', 0)
                    finish_points_common = len(period_achievements_df[period_achievements_df['achievement_type'] == 'FINISHED_COMMON_BOOK']) * settings.get('finish_common_book_points', 0)
                    finish_points_other = len(period_achievements_df[period_achievements_df['achievement_type'] == 'FINISHED_OTHER_BOOK']) * settings.get('finish_other_book_points', 0)
                    discussion_points = meetings_attended_count * settings.get('attend_discussion_points', 0)
                    total_reading_points = reading_points_common + reading_points_other
                    total_quote_points = quote_points_common + quote_points_other
                    total_finish_points = finish_points_common + finish_points_other
                    total_all_points = total_reading_points + total_quote_points + total_finish_points + discussion_points
                    if total_all_points > 0:
                        chart_data = []
                        if total_reading_points > 0: chart_data.append({"النشاط": "نقاط القراءة", "النقاط": total_reading_points})
                        if total_quote_points > 0: chart_data.append({"النشاط": "نقاط الاقتباسات", "النقاط": total_quote_points})
                        if total_finish_points > 0: chart_data.append({"النشاط": "نقاط إنهاء الكتب", "النقاط": total_finish_points})
                        if discussion_points > 0: chart_data.append({"النشاط": "نقاط النقاش", "النقاط": discussion_points})
                        if chart_data:
                            points_df = pd.DataFrame(chart_data)
                            fig = px.pie(points_df, names='النشاط', values='النقاط', title="من أين تأتي نقاط الفريق؟", hole=0.4)
                            fig.update_traces(textposition='inside', textinfo='percent+label')
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("لا توجد نقاط مكتسبة بعد لعرض هذا التحليل.")
                    else:
                        st.info("لا توجد نقاط مكتسبة بعد لعرض هذا التحليل.")
                else:
                    st.info("لا يمكن تحميل إعدادات النقاط.")

        with tab2:
            st.subheader("قائمة المتصدرين والإنجازات")
            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader("🏆 المتصدرون حسب النقاط")
                if not member_stats_df.empty:
                    top_members = member_stats_df.sort_values('total_points', ascending=False)
                    fig = px.bar(top_members, y='name', x='total_points', orientation='h', 
                                 title="أعلى الأعضاء نقاطاً", text_auto=True,
                                 labels={'name': 'اسم العضو', 'total_points': 'مجموع النقاط'})
                    fig.update_layout(yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("لا توجد إحصائيات لعرضها. يرجى تشغيل main.py")
            with col2:
                st.subheader("🏅 أبطال الإنجازات")
                if not period_achievements_df.empty and not member_stats_df.empty:
                    common_finishers = period_achievements_df[period_achievements_df['achievement_type'] == 'FINISHED_COMMON_BOOK']
                    if not common_finishers.empty:
                        fastest_finisher_id = common_finishers.sort_values('achievement_date').iloc[0]['member_id']
                        fastest_finisher_name = members_df[members_df['member_id'] == fastest_finisher_id]['name'].iloc[0]
                        st.metric("🚀 القارئ الصاروخي", fastest_finisher_name)
                    finished_books_count = member_stats_df.set_index('name')[['total_common_books_read', 'total_other_books_read']].sum(axis=1)
                    if not finished_books_count.empty:
                        king_of_books = finished_books_count.idxmax()
                        st.metric("👑 ملك الكتب", king_of_books, int(finished_books_count.max()))
                    meetings_count = member_stats_df.set_index('name')['meetings_attended']
                    if not meetings_count.empty and meetings_count.max() > 0:
                        discussion_dean = meetings_count.idxmax()
                        st.metric("⭐ عميد الحضور", discussion_dean, int(meetings_count.max()))
                else:
                    st.info("لم يتم تسجيل أي إنجازات بعد.")
            st.divider()
            st.subheader("تحليل الاقتباسات حسب العضو")
            if not period_logs_df.empty:
                quote_data = period_logs_df.groupby('member_id')[['submitted_common_quote', 'submitted_other_quote']].sum().reset_index()
                quote_data = pd.merge(quote_data, members_df, on='member_id')
                quote_data = quote_data.melt(id_vars=['name'], value_vars=['submitted_common_quote', 'submitted_other_quote'],
                                             var_name='نوع الاقتباس', value_name='العدد')
                quote_data['نوع الاقتباس'] = quote_data['نوع الاقتباس'].map({
                    'submitted_common_quote': 'اقتباس من كتاب مشترك',
                    'submitted_other_quote': 'اقتباس من كتاب آخر'
                })
                fig = px.bar(quote_data, x='name', y='العدد', color='نوع الاقتباس',
                             title="تحليل الاقتباسات المرسلة من كل عضو",
                             labels={'name': 'اسم العضو', 'العدد': 'عدد الاقتباسات'})
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("لا توجد بيانات اقتباسات لعرضها.")

        with tab3:
            st.subheader("تنبيهات حول نشاط الأعضاء")
            st.warning("هذه القوائم تظهر الأعضاء الذين تجاوزوا الحد المسموح به للغياب وقد يتم تطبيق خصومات عليهم.")
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("الغياب عن تسجيل القراءة")
                if not member_stats_df.empty:
                    inactive_loggers = member_stats_df[member_stats_df['log_streak'] > 0][['name', 'log_streak']].sort_values('log_streak', ascending=False)
                    if not inactive_loggers.empty:
                        st.dataframe(inactive_loggers.rename(columns={'name': 'الاسم', 'log_streak': 'أيام الغياب'}), use_container_width=True, hide_index=True)
                    else:
                        st.success("جميع الأعضاء ملتزمون بتسجيل قراءتهم. عمل رائع!")
                else:
                    st.info("لا توجد بيانات لعرضها.")
            with col2:
                st.subheader("الغياب عن إرسال الاقتباسات")
                if not member_stats_df.empty:
                    inactive_quoters = member_stats_df[member_stats_df['quote_streak'] > 0][['name', 'quote_streak']].sort_values('quote_streak', ascending=False)
                    if not inactive_quoters.empty:
                        st.dataframe(inactive_quoters.rename(columns={'name': 'الاسم', 'quote_streak': 'أيام بلا اقتباس'}), use_container_width=True, hide_index=True)
                    else:
                        st.success("جميع الأعضاء ملتزمون بإرسال الاقتباسات. ممتاز!")
                else:
                    st.info("لا توجد بيانات لعرضها.")
        
        with tab4:
            st.subheader("👤 بطاقة القارئ: تحليل الأداء الفردي")
            if not members_df.empty:
                member_list = members_df['name'].tolist()
                selected_member_name = st.selectbox("اختر قارئًا لعرض بطاقته:", member_list)
                if selected_member_name:
                    member_id = members_df[members_df['name'] == selected_member_name]['member_id'].iloc[0]
                    # THE FIX IS HERE: Use .copy() to avoid the warning
                    member_logs_all = logs_df[logs_df['member_id'] == member_id].copy()
                    member_stats_all = member_stats_df[member_stats_df['member_id'] == member_id].iloc[0]
                    st.header(f"بطاقة أداء: {selected_member_name}")
                    total_books_read = member_stats_all['total_common_books_read'] + member_stats_all['total_other_books_read']
                    total_reading_hours = (member_stats_all['total_reading_minutes_common'] + member_stats_all['total_reading_minutes_other']) / 60
                    days_logged = member_logs_all['submission_date_dt'].nunique()
                    total_minutes_logged = member_logs_all['common_book_minutes'].sum() + member_logs_all['other_book_minutes'].sum()
                    avg_minutes_per_reading_day = total_minutes_logged / days_logged if days_logged > 0 else 0
                    kpi1, kpi2, kpi3 = st.columns(3)
                    kpi1.metric("📚 إجمالي الكتب المنهَاة", f"{total_books_read} كتاب")
                    kpi2.metric("⏱️ إجمالي ساعات القراءة", f"{total_reading_hours:.1f} ساعة")
                    kpi3.metric("📈 متوسط القراءة اليومي", f"{avg_minutes_per_reading_day:.1f} دقيقة/يوم")
                    st.divider()
                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader("نمط القراءة اليومي (آخر 30 يوم)")
                        if not member_logs_all.empty:
                            thirty_days_ago = datetime.date.today() - datetime.timedelta(days=30)
                            recent_logs = member_logs_all[member_logs_all['submission_date_dt'] > thirty_days_ago]
                            if not recent_logs.empty:
                                daily_data = recent_logs.groupby('submission_date_dt')[['common_book_minutes', 'other_book_minutes']].sum().sum(axis=1).reset_index(name='total_minutes')
                                fig = px.bar(daily_data, x='submission_date_dt', y='total_minutes', title="دقائق القراءة اليومية", labels={'submission_date_dt': 'التاريخ', 'total_minutes': 'مجموع الدقائق'})
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info("لم يتم تسجيل أي قراءة في آخر 30 يوم.")
                        else:
                            st.info("لا توجد سجلات قراءة لهذا العضو.")
                    with col2:
                        st.subheader("ساعات القراءة التراكمية")
                        if not member_logs_all.empty:
                            cumulative_logs = member_logs_all.sort_values('submission_date_dt')
                            cumulative_logs['total_minutes'] = cumulative_logs['common_book_minutes'] + cumulative_logs['other_book_minutes']
                            cumulative_logs['cumulative_hours'] = cumulative_logs['total_minutes'].cumsum() / 60
                            fig = px.area(cumulative_logs, x='submission_date_dt', y='cumulative_hours', title="نمو إجمالي ساعات القراءة", labels={'submission_date_dt': 'التاريخ', 'cumulative_hours': 'مجموع الساعات'})
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("لا توجد بيانات كافية لرسم هذا المخطط.")
                    st.divider()
                    st.subheader("شخصيتك القرائية الأسبوعية")
                    if not member_logs_all.empty:
                        member_logs_all['weekday'] = pd.to_datetime(member_logs_all['submission_date_dt']).dt.day_name()
                        weekday_order = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                        weekly_avg = member_logs_all.groupby('weekday')[['common_book_minutes', 'other_book_minutes']].sum().sum(axis=1).reindex(weekday_order).reset_index(name='total_minutes')
                        fig = go.Figure()
                        fig.add_trace(go.Scatterpolar(
                              r=weekly_avg['total_minutes'],
                              theta=weekly_avg['weekday'],
                              fill='toself',
                              name='مجموع دقائق القراءة'
                        ))
                        fig.update_layout(
                          polar=dict(radialaxis=dict(visible=True, range=[0, weekly_avg['total_minutes'].max()])),
                          showlegend=False,
                          title="متوسط نشاطك خلال أيام الأسبوع"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("لا توجد بيانات كافية لعرض شخصيتك القرائية.")
            else:
                st.info("لا يوجد أعضاء في قاعدة البيانات لعرضهم.")

    elif page == "مستكشف البيانات":
        st.header("🔬 مستكشف البيانات")
        st.subheader("ملخص قاعدة البيانات")
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("👥 عدد الأعضاء", f"{len(members_df)} عضو")
        kpi2.metric("📖 عدد الكتب", f"{len(books_df)} كتاب")
        kpi3.metric("✍️ إجمالي التسجيلات", f"{len(logs_df)} تسجيل")
        st.divider()
        st.subheader("استعراض تفاصيل الجداول")
        with st.expander("📖 عرض جدول سجلات القراءة (ReadingLogs)"):
            if not logs_df.empty and not members_df.empty:
                display_df = pd.merge(logs_df, members_df, on='member_id', how='left')
                st.dataframe(
                    display_df[['timestamp', 'name', 'submission_date', 'common_book_minutes', 'other_book_minutes', 'submitted_common_quote', 'submitted_other_quote']].rename(columns={
                        'timestamp': 'وقت التسجيل', 'name': 'اسم العضو', 'submission_date': 'تاريخ القراءة',
                        'common_book_minutes': 'دقائق الكتاب المشترك', 'other_book_minutes': 'دقائق الكتب الأخرى',
                        'submitted_common_quote': 'أرسل اقتباس مشترك', 'submitted_other_quote': 'أرسل اقتباس آخر'
                    }), use_container_width=True, hide_index=True
                )
            else:
                st.info("جدول سجلات القراءة فارغ.")
        with st.expander("🏆 عرض جدول الإنجازات (Achievements)"):
            if not achievements_df.empty and not members_df.empty:
                display_df = pd.merge(achievements_df, members_df, on='member_id', how='left')
                if not books_df.empty:
                    display_df = pd.merge(display_df, books_df, on='book_id', how='left', suffixes=('', '_book'))
                st.dataframe(
                    display_df[['achievement_date', 'name', 'achievement_type', 'title']].rename(columns={
                        'achievement_date': 'تاريخ الإنجاز', 'name': 'اسم العضو',
                        'achievement_type': 'نوع الإنجاز', 'title': 'عنوان الكتاب المرتبط'
                    }), use_container_width=True, hide_index=True
                )
            else:
                st.info("جدول الإنجازات فارغ.")
        with st.expander("📊 عرض جدول إحصائيات الأعضاء (MemberStats)"):
            if not member_stats_df.empty:
                display_df = member_stats_df.drop(columns=['member_id'])
                st.dataframe(display_df, use_container_width=True, hide_index=True)
            else:
                st.info("جدول إحصائيات الأعضاء فارغ.")
        with st.expander("📚 عرض الجداول الأخرى (كتب، أعضاء، فترات التحدي)"):
            st.write("#### جدول الأعضاء (Members)")
            st.dataframe(members_df.drop(columns=['member_id']), use_container_width=True, hide_index=True)
            st.write("#### جدول الكتب (Books)")
            st.dataframe(books_df.drop(columns=['book_id']), use_container_width=True, hide_index=True)
            st.write("#### جدول فترات التحدي (ChallengePeriods)")
            st.dataframe(periods_df.drop(columns=['period_id', 'common_book_id']), use_container_width=True, hide_index=True)

    elif page == "الإضافات":
        st.header("➕ إدارة التحديات")
        st.subheader("قائمة التحديات الحالية والسابقة")
        if not periods_df.empty:
            st.dataframe(periods_df[['title', 'author', 'start_date', 'end_date']].rename(columns={'title': 'عنوان الكتاب', 'author': 'المؤلف', 'start_date': 'تاريخ البداية', 'end_date': 'تاريخ النهاية'}), use_container_width=True, hide_index=True)
        with st.expander("اضغط هنا لإضافة تحدي جديد"):
            with st.form("add_new_challenge_form", clear_on_submit=True):
                new_title = st.text_input("عنوان الكتاب الجديد")
                new_author = st.text_input("مؤلف الكتاب الجديد")
                new_year = st.number_input("سنة نشر الكتاب الجديد", value=datetime.date.today().year, step=1)
                last_end_date = pd.to_datetime(periods_df['end_date'].max()).date() if not periods_df.empty else datetime.date.today() - datetime.timedelta(days=1)
                suggested_start = last_end_date + datetime.timedelta(days=1)
                new_start = st.date_input("تاريخ بداية التحدي الجديد", value=suggested_start)
                new_end = st.date_input("تاريخ نهاية التحدي الجديد", value=suggested_start + datetime.timedelta(days=30))
                if st.form_submit_button("إضافة التحدي"):
                    if new_start <= last_end_date:
                        st.error(f"خطأ: تاريخ بداية التحدي الجديد ({new_start}) يجب أن يكون بعد تاريخ نهاية آخر تحدي ({last_end_date}).")
                    elif not new_title or not new_author:
                        st.error("الرجاء ملء عنوان الكتاب والمؤلف.")
                    elif new_start >= new_end:
                        st.error("تاريخ النهاية يجب أن يكون بعد تاريخ البداية.")
                    else:
                        book_info = {'title': new_title, 'author': new_author, 'year': new_year}
                        challenge_info = {'start_date': str(new_start), 'end_date': str(new_end)}
                        if db.add_book_and_challenge(book_info, challenge_info):
                            st.success(f"تمت إضافة تحدي '{new_title}' بنجاح!"); st.rerun()

    elif page == "الإعدادات":
        st.header("⚙️ الإعدادات العامة")
        st.info("هنا يمكنك تعديل 'قوانين اللعبة' الأساسية التي تنطبق على جميع التحديات.")
        settings = db.load_global_settings()
        if settings:
            with st.form("settings_form"):
                st.subheader("نظام حساب النقاط")
                c1, c2 = st.columns(2)
                s_m_common = c1.number_input("دقائق قراءة الكتاب المشترك لكل نقطة:", value=settings['minutes_per_point_common'])
                s_m_other = c2.number_input("دقائق قراءة كتاب آخر لكل نقطة:", value=settings['minutes_per_point_other'])
                s_q_common = c1.number_input("نقاط اقتباس الكتاب المشترك:", value=settings['quote_common_book_points'])
                s_q_other = c2.number_input("نقاط اقتباس كتاب آخر:", value=settings['quote_other_book_points'])
                s_f_common = c1.number_input("نقاط إنهاء الكتاب المشترك:", value=settings['finish_common_book_points'])
                s_f_other = c2.number_input("نقاط إنهاء كتاب آخر:", value=settings['finish_other_book_points'])
                s_a_disc = st.number_input("نقاط حضور جلسة النقاش:", value=settings['attend_discussion_points'])
                st.divider()
                st.subheader("نظام الخصومات")
                c3, c4 = st.columns(2)
                s_nl_trigger = c3.number_input("أيام الغياب عن التسجيل لبدء الخصم:", value=settings['no_log_days_trigger'])
                s_nl_initial = c3.number_input("قيمة الخصم الأول للغياب:", value=settings['no_log_initial_penalty'])
                s_nl_subsequent = c3.number_input("قيمة الخصم المتكرر للغياب:", value=settings['no_log_subsequent_penalty'])
                s_nq_trigger = c4.number_input("أيام عدم إرسال اقتباس لبدء الخصم:", value=settings['no_quote_days_trigger'])
                s_nq_initial = c4.number_input("قيمة الخصم الأول للاقتباس:", value=settings['no_quote_initial_penalty'])
                s_nq_subsequent = c4.number_input("قيمة الخصم المتكرر للاقتباس:", value=settings['no_quote_subsequent_penalty'])
                if st.form_submit_button("حفظ الإعدادات"):
                    new_settings = {
                        "minutes_per_point_common": s_m_common, "minutes_per_point_other": s_m_other,
                        "quote_common_book_points": s_q_common, "quote_other_book_points": s_q_other,
                        "finish_common_book_points": s_f_common, "finish_other_book_points": s_f_other,
                        "attend_discussion_points": s_a_disc, "no_log_days_trigger": s_nl_trigger,
                        "no_log_initial_penalty": s_nl_initial, "no_log_subsequent_penalty": s_nl_subsequent,
                        "no_quote_days_trigger": s_nq_trigger, "no_quote_initial_penalty": s_nq_initial,
                        "no_quote_subsequent_penalty": s_nq_subsequent
                    }
                    if db.update_global_settings(new_settings):
                        st.success("تم تحديث الإعدادات بنجاح!")
                    else:
                        st.error("حدث خطأ أثناء تحديث الإعدادات.")
        else:
            st.error("لا يمكن تحميل الإعدادات من قاعدة البيانات.")