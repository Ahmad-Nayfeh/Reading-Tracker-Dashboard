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

# --- Initial Data Load ---
all_data = db.get_all_data_for_stats()
if all_data:
    members = all_data.get('members', [])
    periods = all_data.get('periods', [])
    setup_complete = bool(members and periods)
else:
    members, periods, setup_complete = [], [], False

# --- Main Application Logic ---
st.title("📚 لوحة تحكم تحدي القرّاء")

if not setup_complete:
    # --- SETUP WIZARD ---
    st.warning("👋 مرحباً بك! لنقم بإعداد تحدي القراءة الخاص بك.")
    if not members:
        st.subheader("الخطوة 1: إضافة أعضاء المجموعة")
        with st.form("new_members_form"):
            names_str = st.text_area("أسماء الأعضاء", height=150, placeholder="خالد\nسارة\n...")
            if st.form_submit_button("إضافة الأعضاء"):
                names = [name.strip() for name in names_str.split('\n') if name.strip()]
                if names: db.add_members(names); st.rerun()
    elif not periods:
        st.subheader("الخطوة 2: إنشاء أول فترة تحدي")
        with st.form("new_challenge_form", clear_on_submit=True):
            st.text_input("عنوان الكتاب", key="book_title")
            st.text_input("اسم المؤلف", key="book_author")
            st.number_input("سنة النشر", key="pub_year", value=2024, step=1)
            st.date_input("تاريخ بداية التحدي", key="start_date")
            st.date_input("تاريخ نهاية التحدي", key="end_date", value=datetime.date.today() + datetime.timedelta(days=30))
            if st.form_submit_button("إنشاء التحدي"):
                if st.session_state.book_title and st.session_state.book_author:
                    book_info = {'title': st.session_state.book_title, 'author': st.session_state.book_author, 'year': st.session_state.pub_year}
                    challenge_info = {'start_date': str(st.session_state.start_date), 'end_date': str(st.session_state.end_date)}
                    if db.add_book_and_challenge(book_info, challenge_info): st.rerun()
                else: st.error("الرجاء ملء عنوان الكتاب والمؤلف.")
else:
    # --- MAIN APPLICATION WITH 4 PAGES ---
    st.sidebar.title("تنقل")
    page_options = ["لوحة التحكم", "عرض البيانات", "الإضافات", "الإعدادات"]
    page = st.sidebar.radio("اختر صفحة", page_options, key="navigation")

    # --- Page 1: Dashboard ---
    if page == "لوحة التحكم":
        # ... (Dashboard code remains the same)
        st.header("📊 لوحة التحكم الرئيسية (Dashboard)")
        conn = db.get_db_connection()
        try:
            query = "SELECT m.name, ms.* FROM MemberStats ms JOIN Members m ON ms.member_id = m.member_id ORDER BY ms.total_points DESC"
            stats_df = pd.read_sql_query(query, conn)
        finally: conn.close()
        if not stats_df.empty:
            st.subheader("إحصائيات سريعة للمجموعة")
            col1, col2, col3, col4 = st.columns(4)
            total_minutes = stats_df['total_reading_minutes_common'].sum() + stats_df['total_reading_minutes_other'].sum()
            total_common_challenges = len(periods)
            total_quotes = stats_df['total_quotes_submitted'].sum()
            col1.metric("إجمالي ساعات القراءة", f"{total_minutes / 60:.1f} ساعة")
            col2.metric("عدد التحديات", f"{total_common_challenges} تحدي")
            col3.metric("إجمالي الاقتباسات", f"{total_quotes} اقتباس")
            col4.metric("عدد المشاركين", f"{len(stats_df)} عضو")
            st.divider()
            st.subheader("🏆 قائمة المتصدرين")
            st.dataframe(stats_df[['name', 'total_points']].rename(columns={'name': 'الاسم', 'total_points': 'النقاط'}), use_container_width=True, hide_index=True)
        else: st.info("لم يتم حساب أي إحصائيات بعد. يرجى تشغيل `main.py` أولاً.")

    # --- Page 2: Data Viewer ---
    elif page == "عرض البيانات":
        st.header("🗂️ عرض بيانات قاعدة البيانات")
        table_names = db.get_table_names()
        if table_names:
            selected_table = st.selectbox("اختر الجدول لعرضه:", table_names)
            if selected_table:
                df = db.get_table_as_df(selected_table)
                st.dataframe(df, use_container_width=True)
    
    # --- Page 3: Add-ons ---
    elif page == "الإضافات":
        st.header("➕ إدارة التحديات")
        st.subheader("قائمة التحديات الحالية والسابقة")
        if periods:
            periods_df = pd.DataFrame(periods)
            st.dataframe(
                periods_df[['title', 'author', 'start_date', 'end_date']].rename(columns={
                    'title': 'عنوان الكتاب', 'author': 'المؤلف', 'start_date': 'تاريخ البداية', 'end_date': 'تاريخ النهاية'
                }), use_container_width=True, hide_index=True)
        else: st.write("لا توجد فترات تحدي بعد.")
        
        st.divider()

        with st.expander("اضغط هنا لإضافة تحدي جديد"):
            with st.form("add_new_challenge_form", clear_on_submit=True):
                new_title = st.text_input("عنوان الكتاب الجديد")
                new_author = st.text_input("مؤلف الكتاب الجديد")
                new_year = st.number_input("سنة نشر الكتاب الجديد", value=datetime.date.today().year, step=1)
                
                last_end_date = datetime.datetime.strptime(periods[0]['end_date'], '%Y-%m-%d').date() if periods else datetime.date.today() - datetime.timedelta(days=1)
                suggested_start = last_end_date + datetime.timedelta(days=1)
                
                new_start = st.date_input("تاريخ بداية التحدي الجديد", value=suggested_start)
                new_end = st.date_input("تاريخ نهاية التحدي الجديد", value=suggested_start + datetime.timedelta(days=30))

                if st.form_submit_button("إضافة التحدي"):
                    # --- THE FIX IS HERE ---
                    # Stricter validation to prevent overlaps
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
                            st.success(f"تمت إضافة تحدي '{new_title}' بنجاح!")
                            st.rerun()
                        else:
                            st.error("حدث خطأ أثناء إضافة التحدي.")

    # --- Page 4: Settings ---
    elif page == "الإعدادات":
        st.header("⚙️ الإعدادات")
        st.info("سيتم بناء هذه الصفحة قريباً.")
