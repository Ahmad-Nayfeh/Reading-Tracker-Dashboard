import streamlit as st
import pandas as pd
import datetime
import db_manager as db
import plotly.express as px

# --- Page Configuration ---
st.set_page_config(
    page_title="Reading Challenge Dashboard",
    page_icon="📚",
    layout="wide"
)

# --- Initial Data Load & State Check ---
# (This part remains unchanged)
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
# (This part remains unchanged)
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
        # (This page's code remains the same as the last version)
        st.header("📊 لوحة التحكم الرئيسية")
        challenge_options = {period['period_id']: f"{period['title']} ({period['start_date']} to {period['end_date']})" for index, period in periods_df.iterrows()}
        default_challenge_id = periods_df['period_id'].max()
        selected_challenge_id = st.selectbox("اختر فترة التحدي لعرضها:", options=list(challenge_options.keys()), format_func=lambda x: challenge_options[x], index=0)
        selected_period = periods_df[periods_df['period_id'] == selected_challenge_id].iloc[0]
        start_date = pd.to_datetime(selected_period['start_date']).date()
        end_date = pd.to_datetime(selected_period['end_date']).date()
        logs_df['submission_date_dt'] = pd.to_datetime(logs_df['submission_date'], format='%d/%m/%Y').dt.date
        period_logs_df = logs_df[(logs_df['submission_date_dt'] >= start_date) & (logs_df['submission_date_dt'] <= end_date)]
        period_achievements_df = achievements_df[achievements_df['period_id'] == selected_challenge_id]
        with st.container(border=True):
            st.subheader(f"📖 التحدي الحالي: {selected_period['title']}")
            st.caption(f"تأليف: {selected_period['author']} | مدة التحدي: من {selected_period['start_date']} إلى {selected_period['end_date']}")
            days_total = (end_date - start_date).days + 1
            days_passed = (datetime.date.today() - start_date).days + 1
            progress = min(max(days_passed / days_total, 0), 1)
            st.progress(progress, text=f"انقضى {days_passed if days_passed > 0 else 0} يوم من أصل {days_total} يوم")
        st.divider()
        tab1, tab2, tab3, tab4 = st.tabs(["📊 نظرة عامة", "🏆 لوحة المتصدرين", "🔔 تنبيهات النشاط", "🧐 تحليل فردي"])
        with tab1:
            st.subheader("نظرة عامة على أداء المجموعة")
            total_minutes = period_logs_df['common_book_minutes'].sum() + period_logs_df['other_book_minutes'].sum()
            active_members_count = period_logs_df['member_id'].nunique()
            total_quotes = period_logs_df['submitted_common_quote'].sum() + period_logs_df['submitted_other_quote'].sum()
            meetings_attended = period_achievements_df[period_achievements_df['achievement_type'] == 'ATTENDED_DISCUSSION']['member_id'].nunique()
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("إجمالي ساعات القراءة", f"{total_minutes / 60:.1f} ساعة")
            kpi2.metric("الأعضاء النشطون", f"{active_members_count} عضو")
            kpi3.metric("إجمالي الاقتباسات", f"{total_quotes} اقتباس")
            kpi4.metric("حضور جلسة النقاش", f"{meetings_attended} عضو")
            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("زخم القراءة التراكمي")
                if not period_logs_df.empty:
                    daily_minutes = period_logs_df.groupby('submission_date_dt')[['common_book_minutes', 'other_book_minutes']].sum().sum(axis=1).reset_index(name='total_minutes')
                    daily_minutes = daily_minutes.sort_values('submission_date_dt')
                    daily_minutes['cumulative_minutes'] = daily_minutes['total_minutes'].cumsum()
                    fig = px.area(daily_minutes, x='submission_date_dt', y='cumulative_minutes', title="مجموع دقائق القراءة اليومية", labels={'submission_date_dt': 'التاريخ', 'cumulative_minutes': 'مجموع الدقائق'})
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("لا توجد بيانات قراءة مسجلة لهذا التحدي بعد.")
            with col2:
                st.subheader("توزيع القراءة الأسبوعي")
                if not period_logs_df.empty:
                    period_logs_df['weekday'] = pd.to_datetime(period_logs_df['submission_date_dt']).dt.day_name()
                    weekday_order = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                    weekly_activity = period_logs_df.groupby('weekday')['common_book_minutes'].count().reindex(weekday_order).reset_index(name='logs_count')
                    fig = px.bar(weekly_activity, x='weekday', y='logs_count', title="عدد تسجيلات القراءة حسب اليوم", labels={'weekday': 'اليوم', 'logs_count': 'عدد التسجيلات'})
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("لا توجد بيانات لرسم هذا المخطط.")
        with tab2:
            st.subheader("قائمة المتصدرين والإنجازات")
            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader("🏆 المتصدرون حسب النقاط")
                if not member_stats_df.empty:
                    top_members = member_stats_df.sort_values('total_points', ascending=False)
                    fig = px.bar(top_members, y='name', x='total_points', orientation='h', title="أعلى الأعضاء نقاطاً", text_auto=True, labels={'name': 'اسم العضو', 'total_points': 'مجموع النقاط'})
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
                        st.metric("🚀 القارئ الصاروخي (أنهى الكتاب أولاً)", fastest_finisher_name)
                    finished_books_count = member_stats_df.set_index('name')[['total_common_books_read', 'total_other_books_read']].sum(axis=1)
                    if not finished_books_count.empty:
                        king_of_books = finished_books_count.idxmax()
                        st.metric("👑 ملك الكتب (الأكثر إنهاءً للكتب)", king_of_books, int(finished_books_count.max()))
                    meetings_count = member_stats_df.set_index('name')['meetings_attended']
                    if not meetings_count.empty and meetings_count.max() > 0:
                        discussion_dean = meetings_count.idxmax()
                        st.metric("⭐ عميد الحضور (الأكثر حضوراً للنقاش)", discussion_dean, int(meetings_count.max()))
                else:
                    st.info("لم يتم تسجيل أي إنجازات بعد.")
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
            st.subheader("تحليل الأداء الفردي")
            if not members_df.empty and not member_stats_df.empty:
                member_list = members_df['name'].tolist()
                selected_member_name = st.selectbox("اختر عضواً لعرض تحليله التفصيلي:", member_list)
                if selected_member_name:
                    selected_member_id = members_df[members_df['name'] == selected_member_name]['member_id'].iloc[0]
                    member_stats = member_stats_df[member_stats_df['member_id'] == selected_member_id].iloc[0]
                    member_logs = period_logs_df[period_logs_df['member_id'] == selected_member_id]
                    with st.container(border=True):
                        st.header(f"بطاقة أداء: {selected_member_name}")
                        m_col1, m_col2, m_col3 = st.columns(3)
                        m_col1.metric("إجمالي النقاط", f"{member_stats['total_points']} نقطة")
                        total_member_minutes = member_stats['total_reading_minutes_common'] + member_stats['total_reading_minutes_other']
                        m_col2.metric("إجمالي ساعات القراءة", f"{total_member_minutes / 60:.1f} ساعة")
                        m_col3.metric("إجمالي الاقتباسات", f"{member_stats['total_quotes_submitted']} اقتباس")
                        st.divider()
                        st.subheader("نمط القراءة اليومي")
                        if not member_logs.empty:
                            daily_data = member_logs.groupby('submission_date_dt')[['common_book_minutes', 'other_book_minutes']].sum()
                            st.bar_chart(daily_data)
                        else:
                            st.info(f"لم يسجل {selected_member_name} أي قراءة في هذا التحدي بعد.")
            else:
                st.info("لا يوجد أعضاء لعرضهم.")

    # --- REWRITTEN "DATA EXPLORER" PAGE ---
    elif page == "مستكشف البيانات":
        st.header("🔬 مستكشف البيانات")

        # --- Data Health Check ---
        st.subheader("ملخص قاعدة البيانات")
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("👥 عدد الأعضاء", f"{len(members_df)} عضو")
        kpi2.metric("📖 عدد الكتب", f"{len(books_df)} كتاب")
        kpi3.metric("✍️ إجمالي التسجيلات", f"{len(logs_df)} تسجيل")
        
        st.divider()
        st.subheader("استعراض تفاصيل الجداول")
        
        # --- Reading Logs Expander ---
        with st.expander("📖 عرض جدول سجلات القراءة (ReadingLogs)"):
            if not logs_df.empty and not members_df.empty:
                display_df = pd.merge(logs_df, members_df, on='member_id', how='left')
                # Select and rename columns for a clean view
                st.dataframe(
                    display_df[['timestamp', 'name', 'submission_date', 'common_book_minutes', 'other_book_minutes', 'submitted_common_quote', 'submitted_other_quote']].rename(columns={
                        'timestamp': 'وقت التسجيل',
                        'name': 'اسم العضو',
                        'submission_date': 'تاريخ القراءة',
                        'common_book_minutes': 'دقائق الكتاب المشترك',
                        'other_book_minutes': 'دقائق الكتب الأخرى',
                        'submitted_common_quote': 'أرسل اقتباس مشترك',
                        'submitted_other_quote': 'أرسل اقتباس آخر'
                    }), 
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("جدول سجلات القراءة فارغ.")

        # --- Achievements Expander ---
        with st.expander("🏆 عرض جدول الإنجازات (Achievements)"):
            if not achievements_df.empty and not members_df.empty:
                display_df = pd.merge(achievements_df, members_df, on='member_id', how='left')
                # Merge with books, handling cases where book_id might be null
                if not books_df.empty:
                    display_df = pd.merge(display_df, books_df, on='book_id', how='left', suffixes=('', '_book'))
                
                st.dataframe(
                    display_df[['achievement_date', 'name', 'achievement_type', 'title']].rename(columns={
                        'achievement_date': 'تاريخ الإنجاز',
                        'name': 'اسم العضو',
                        'achievement_type': 'نوع الإنجاز',
                        'title': 'عنوان الكتاب المرتبط'
                    }), 
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("جدول الإنجازات فارغ.")

        # --- Member Stats Expander ---
        with st.expander("📊 عرض جدول إحصائيات الأعضاء (MemberStats)"):
            if not member_stats_df.empty:
                # Assuming member_stats_df is already merged with member names
                display_df = member_stats_df.drop(columns=['member_id']) # Drop the ID as requested
                st.dataframe(display_df, use_container_width=True, hide_index=True)
            else:
                st.info("جدول إحصائيات الأعضاء فارغ.")

        # --- Other Tables Expander ---
        with st.expander("📚 عرض الجداول الأخرى (كتب، أعضاء، فترات التحدي)"):
            st.write("#### جدول الأعضاء (Members)")
            st.dataframe(members_df.drop(columns=['member_id']), use_container_width=True, hide_index=True)
            
            st.write("#### جدول الكتب (Books)")
            st.dataframe(books_df.drop(columns=['book_id']), use_container_width=True, hide_index=True)

            st.write("#### جدول فترات التحدي (ChallengePeriods)")
            st.dataframe(periods_df.drop(columns=['period_id', 'common_book_id']), use_container_width=True, hide_index=True)


    elif page == "الإضافات":
        # (This page's code remains the same)
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
        # (This page's code remains the same)
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