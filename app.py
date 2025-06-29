import streamlit as st
import pandas as pd
import datetime
import db_manager as db # Our single source for all DB interactions

# --- Page Configuration ---
st.set_page_config(
    page_title="Reading Challenge Dashboard",
    page_icon="📚",
    layout="wide"
)

# --- Initial Data Load ---
# We fetch all data once at the start to determine the app's state.
all_data = db.get_all_data_for_stats()
members = all_data['members']
periods = all_data['periods']
setup_complete = bool(members and periods)

# --- Main Application Logic ---
st.title("📚 لوحة تحكم تحدي القرّاء")

if not setup_complete:
    # --- SETUP WIZARD ---
    st.warning("👋 مرحباً بك! لنقم بإعداد تحدي القراءة الخاص بك.")

    # Step 1: Add Members (if none exist)
    if not members:
        st.subheader("الخطوة 1: إضافة أعضاء المجموعة")
        st.info("أدخل أسماء المشاركين، كل اسم في سطر جديد.")

        with st.form("new_members_form"):
            member_names_str = st.text_area("أسماء الأعضاء", height=250, placeholder="خالد\nسارة\nمحمد\n...")
            submitted = st.form_submit_button("إضافة الأعضاء والانتقال للخطوة التالية")

            if submitted:
                names = [name.strip() for name in member_names_str.split('\n') if name.strip()]
                if names:
                    try:
                        db.add_members(names)
                        st.success(f"تمت إضافة {len(names)} أعضاء بنجاح!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"حدث خطأ: {e}")
                else:
                    st.error("الرجاء إدخال اسم واحد على الأقل.")
    
    # Step 2: Add First Challenge Period (if members exist but no periods)
    elif not periods:
        st.subheader("الخطوة 2: إنشاء أول فترة تحدي")
        st.info("الآن، لندخل معلومات الكتاب المشترك الأول وتواريخ التحدي.")

        with st.form("new_challenge_form"):
            st.write("#### معلومات الكتاب")
            book_title = st.text_input("عنوان الكتاب")
            book_author = st.text_input("اسم المؤلف")
            publication_year = st.number_input("سنة النشر", min_value=1000, max_value=datetime.date.today().year, step=1, value=datetime.date.today().year)

            st.write("---")
            st.write("#### تواريخ التحدي")
            today = datetime.date.today()
            start_date = st.date_input("تاريخ بداية التحدي", value=today)
            end_date = st.date_input("تاريخ نهاية التحدي", value=today + datetime.timedelta(days=30))
            
            submitted = st.form_submit_button("إنشاء التحدي والبدء!")

            if submitted:
                if not book_title or not book_author:
                    st.error("الرجاء إدخال عنوان الكتاب واسم المؤلف.")
                elif start_date >= end_date:
                    st.error("يجب أن يكون تاريخ نهاية التحدي بعد تاريخ البداية.")
                else:
                    book_info = {'title': book_title, 'author': book_author, 'year': publication_year}
                    challenge_info = {'start_date': str(start_date), 'end_date': str(end_date)}
                    
                    if db.add_book_and_challenge(book_info, challenge_info):
                        st.success(f"تم إنشاء التحدي لكتاب '{book_title}' بنجاح!")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("حدث خطأ في قاعدة البيانات أثناء إنشاء التحدي.")
else:
    # --- MAIN DASHBOARD VIEW ---
    # This is where we will build the 4 pages you designed.
    st.sidebar.title("تنقل")
    page = st.sidebar.radio("اختر صفحة", ["لوحة التحكم", "عرض البيانات", "الإضافات", "الإعدادات"])

    if page == "لوحة التحكم":
        st.header("📊 لوحة التحكم الرئيسية (Dashboard)")
        st.info("سيتم عرض الإحصائيات والرسوم البيانية هنا قريباً.")
        # TODO: Build Dashboard UI
    
    elif page == "عرض البيانات":
        st.header("🗂️ عرض البيانات (Data Viewer)")
        st.info("سيتم عرض جداول البيانات هنا مع إمكانية الفلترة.")
        # TODO: Build Data Viewer UI

    elif page == "الإضافات":
        st.header("➕ الإضافات (Add New)")
        st.info("سيتم عرض زر لإضافة تحدي جديد هنا.")
        # TODO: Build Add-ons UI

    elif page == "الإعدادات":
        st.header("⚙️ الإعدادات (Settings)")
        st.info("سيتم عرض الإعدادات العامة والخاصة هنا.")
        # TODO: Build Settings UI

