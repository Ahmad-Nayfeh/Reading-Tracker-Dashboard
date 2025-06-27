import streamlit as st
import pandas as pd
import datetime
from db_manager import (
    get_db_connection, 
    get_all_members, 
    add_members,
    get_challenge_periods,
    add_book,
    add_challenge_period
)

# --- Page Configuration ---
st.set_page_config(
    page_title="Reading Challenge Dashboard",
    page_icon="📚",
    layout="wide"
)

# --- Helper Functions ---
def check_setup():
    """Checks if the initial setup (members and first challenge) is complete."""
    members = get_all_members()
    periods = get_challenge_periods()
    setup_complete = bool(members and periods)
    return setup_complete, members, periods

# --- Main Application Logic ---
st.title("📚 لوحة تحكم تحدي القرّاء")

# Check the setup status
setup_complete, members, periods = check_setup()

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
                        add_members(names)
                        st.success(f"تمت إضافة {len(names)} أعضاء بنجاح!")
                        st.rerun() # Rerun to proceed to the next setup step
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
                # Basic Validation
                if not book_title or not book_author:
                    st.error("الرجاء إدخال عنوان الكتاب واسم المؤلف.")
                elif start_date >= end_date:
                    st.error("يجب أن يكون تاريخ نهاية التحدي بعد تاريخ البداية.")
                else:
                    try:
                        # 1. Add the book and get its ID
                        book_id = add_book(book_title, book_author, publication_year)
                        
                        # 2. Add the challenge period with the new book ID
                        add_challenge_period(str(start_date), str(end_date), book_id)
                        
                        st.success(f"تم إنشاء التحدي لكتاب '{book_title}' بنجاح!")
                        st.balloons()
                        st.info("🎉 رائع! تم إكمال الإعداد. سيتم عرض لوحة التحكم الآن.")
                        st.rerun() # Rerun to show the main dashboard
                    except Exception as e:
                        st.error(f"حدث خطأ في قاعدة البيانات أثناء إنشاء التحدي: {e}")

else:
    # --- MAIN DASHBOARD VIEW ---
    st.success("🎉 تم إعداد النظام بنجاح!")
    st.header("لوحة التحكم الرئيسية")
    st.info("سيتم عرض الإحصائيات والرسوم البيانية هنا قريباً.")

    # Display current challenges
    st.subheader("فترات التحدي الحالية والسابقة:")
    periods_df = pd.DataFrame(periods)
    st.dataframe(
        periods_df[['title', 'author', 'start_date', 'end_date']],
        use_container_width=True,
        hide_index=True,
        column_config={
            "title": "عنوان الكتاب",
            "author": "المؤلف",
            "start_date": "تاريخ البداية",
            "end_date": "تاريخ النهاية"
        }
    )

