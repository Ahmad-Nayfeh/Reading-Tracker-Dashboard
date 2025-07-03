import streamlit as st
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import os

# --- Configuration Constants ---

# This is the file you downloaded from Google Cloud Console.
# It identifies your application to Google.
CLIENT_SECRET_FILE = 'client_secret.json' 

# This file will be created automatically to store the user's token
# after they log in for the first time. It avoids asking them to log in every time.
TOKEN_FILE = 'data/token.json'

# These are the permissions the app will ask the user for.
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/forms.body"
]

def authenticate():
    """
    The main authentication function. It handles all authentication logic
    in a robust, sequential way that is compatible with Streamlit.

    Returns:
        google.oauth2.credentials.Credentials: A valid user credential object.
    """
    
    # Check the session state first for existing credentials.
    creds = st.session_state.get('credentials')

    # If credentials are not in the session state, try loading from the token file.
    if not creds:
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    # If we have credentials, check if they are still valid or need refreshing.
    if creds:
        if creds.valid:
            st.session_state.credentials = creds
            return creds
        elif creds.expired and creds.refresh_token:
            creds.refresh(Request())
            st.session_state.credentials = creds
            save_credentials_to_file(creds) # Save the refreshed token
            return creds

    # If we have no valid credentials, we need to start the login flow.
    try:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri='http://localhost:8501' # Must match Google Cloud Console
        )
    except FileNotFoundError:
        # --- LINGUISTIC UPDATE ---
        st.error(f"🔑 **خطأ في الإعدادات:** لم يتم العثور على ملف `{CLIENT_SECRET_FILE}`. يرجى التأكد من اتباع إرشادات الإعداد في ملف `README.md` ووضع الملف في المجلد الرئيسي للمشروع.")
        st.stop()

    # Check if we are in the redirect phase (coming back from Google).
    authorization_code = st.query_params.get("code")
    if authorization_code:
        flow.fetch_token(code=authorization_code)
        creds = flow.credentials
        st.session_state.credentials = creds
        save_credentials_to_file(creds)
        
        # Clear the query parameters from the URL and rerun the app.
        st.query_params.clear()
        st.rerun()
    
    # If we are not in the redirect phase, show the login button.
    else:
        auth_url, _ = flow.authorization_url(prompt='consent')
        # --- LINGUISTIC UPDATE ---
        st.title("🚀 أهلاً بك في \"ماراثون القراءة\"")
        st.info("للبدء، يرجى ربط حسابك في جوجل. سيقوم التطبيق بإنشاء مساحة عمل خاصة بك (Google Sheet و Form) لإدارة تحديات القراءة بكل سهولة.")
        st.link_button("🔗 **الربط بحساب جوجل والبدء**", auth_url, use_container_width=True, type="primary")
        st.stop()


def save_credentials_to_file(creds):
    """Saves user's credentials to a file for future sessions."""
    os.makedirs('data', exist_ok=True)
    with open(TOKEN_FILE, 'w') as token:
        token.write(creds.to_json())


@st.cache_resource
def get_gspread_client():
    """Uses authenticated credentials to create a gspread client."""
    creds = st.session_state.get('credentials')
    if not creds:
        # --- LINGUISTIC UPDATE ---
        st.error("🔒 **خطأ في المصادقة:** لم نتمكن من التحقق من صلاحيات الوصول. قد تكون هناك مشكلة في الاتصال أو أنك لم تمنح الصلاحيات اللازمة.")
        st.stop()
    return gspread.authorize(creds)