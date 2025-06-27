import streamlit as st
import sqlite3
import pandas as pd
from db_manager import get_db_connection, get_all_members

# --- Page Configuration ---
st.set_page_config(
    page_title="Reading Challenge Dashboard",
    page_icon="📚",
    layout="wide"
)

# --- Database Connection ---
conn = get_db_connection()

# --- Main Application Logic ---
st.title("📚 لوحة تحكم تحدي القرّاء")

# Check if there are any members in the database
members = get_all_members()

if not members:
    # --- First-Time Setup: Members ---
    st.warning("👋 مرحباً بك! يبدو أن هذه هي المرة الأولى التي تشغل فيها التطبيق.")
    st.info("الخطوة الأولى هي إضافة أسماء أعضاء مجموعة القراءة الخاصة بك.")

    with st.form("new_members_form"):
        st.write("أدخل أسماء المشاركين، كل اسم في سطر جديد:")
        # Use a text area for easy copy-pasting of names
        member_names_str = st.text_area("أسماء الأعضاء", height=250, placeholder="خالد\nسارة\nمحمد\n...")
        
        submitted = st.form_submit_button("إضافة الأعضاء وحفظ")

        if submitted:
            if member_names_str:
                # Split the names by newline, strip whitespace, and filter out empty lines
                names = [name.strip() for name in member_names_str.split('\n') if name.strip()]
                
                if names:
                    try:
                        cursor = conn.cursor()
                        # Use executemany for efficient bulk insertion
                        cursor.executemany("INSERT INTO Members (name) VALUES (?)", [(name,) for name in names])
                        conn.commit()
                        st.success(f"تمت إضافة {len(names)} أعضاء بنجاح!")
                        st.info("🎉 رائع! الخطوة التالية ستكون إنشاء أول فترة تحدي لك.")
                        # Rerun the app to move to the next state
                        st.rerun()
                    except sqlite3.IntegrityError as e:
                        st.error(f"خطأ: يبدو أن أحد الأسماء مكرر. يرجى التأكد من أن كل اسم فريد. التفاصيل: {e}")
                    except sqlite3.Error as e:
                        st.error(f"حدث خطأ في قاعدة البيانات: {e}")
                else:
                    st.error("لم يتم إدخال أي أسماء. يرجى إدخال اسم واحد على الأقل.")
            else:
                st.error("الرجاء إدخال أسماء الأعضاء.")
else:
    # --- Main Dashboard View ---
    st.write("أهلاً بعودتك!")
    st.info("سيتم عرض لوحة التحكم الرئيسية هنا قريباً.")
    
    st.subheader("أعضاء التحدي الحاليين:")
    
    # Display members in a clean table using Pandas DataFrame
    members_df = pd.DataFrame(members)
    st.dataframe(members_df[['name']], use_container_width=True)


# --- Close the connection at the end of the script ---
conn.close()
