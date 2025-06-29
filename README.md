# 📚 Reading-Tracker-Dashboard
A data-driven dashboard to automate, visualize, and gamify your book club's reading challenges.

## 🎯 The Project Idea
This project provides a comprehensive, easy-to-use system for reading group administrators to manage a group reading challenge. The system automatically calculates member points based on their daily Google Form submissions and displays all statistics on a live, interactive dashboard.

## 👥 Who Is This For?
This project is designed for:

* **Book Clubs** looking to add an element of fun, engagement, and friendly competition.
* **Groups of Friends** who want to encourage and motivate each other to read more consistently.
* **Administrators & Organizers** seeking a simple tool to automate the tedious process of tracking points and managing the challenge, instead of relying on manual calculations.

## 🚀 Getting Started (Admin's Guide)
Welcome, Admin! This guide will walk you through the entire process of setting up and running the system. Please follow the steps in order.

### Stage 1: One-Time Prerequisite Setup
This stage covers everything you need to do on your local machine and on Google's platform to prepare for the application.

**1. Requirements**
* Ensure you have Python 3.8+ installed.
* Ensure you have Git installed.

**2. Clone the Repository & Install Dependencies**
Open your terminal or command prompt, and run the following commands to clone the project and set up the Python environment:

```bash
# Clone the repository to your computer
git clone https://github.com/Ahmad-Nayfeh/Reading-Tracker-Dashboard.git

# Navigate into the project directory
cd Reading-Tracker-Dashboard

# Create a virtual environment
python -m venv venv

# Activate the environment (on Windows)
venv\Scripts\activate

# Activate the environment (on Mac/Linux)
# source venv/bin/activate

# Install all required libraries
pip install -r requirements.txt
```

**3. Setup the Google API Interface**
This step creates a secure "key" (a service account) that allows our Python script to access your private Google Sheet.

* **Navigate to Google Cloud Console:** Go to the Google Cloud Console and sign in.
* **Create a New Project:** From the top navigation bar, select the project dropdown and click "New Project". Give it a descriptive name like `Reading Challenge Bot` and create it.
* **Enable APIs:**
    * From the navigation menu (☰), go to "APIs & Services" > "Library".
    * Search for and **Enable** the following two APIs:
        1.  **Google Sheets API**
        2.  **Google Drive API**
* **Create a Service Account:**
    * From the navigation menu, go to "APIs & Services" > "Credentials".
    * Click "+ CREATE CREDENTIALS" and select "Service account".
    * Give it a name (e.g., `sheet-reader-bot`) and click "Create and Continue".
    * You can skip the next two optional steps. Click "Continue" and then "Done".
* **Generate the JSON Key:**
    * Back on the Credentials screen, click on your new service account's email address.
    * Go to the "KEYS" tab. Click "ADD KEY" > "Create new key".
    * Choose the key type **JSON** and click "CREATE".
    * A JSON file will be downloaded. Rename it to `credentials.json` and place it in your project's root directory.

### Stage 2: Application and Form Setup
Now we will set up the database, configure the connection to Google Sheets, and generate the Google Form for daily entries.

**1. Create the Database**
In your terminal (with the virtual environment active), run this command **once**:

```bash
python database_setup.py
```

**2. Configure Google Sheet URL**
This step links the project to your specific Google Sheet.

* **Create a Google Sheet:** Go to `sheets.google.com` and create a new, blank spreadsheet. Name it something clear, like "Reading Challenge Data".
* **Copy its URL** from your browser's address bar.
* **Create your environment file:** In your terminal, in the project directory, run:
    ```bash
    # For Mac/Linux
    cp .env.example .env

    # For Windows
    copy .env.example .env
    ```
* **Edit the `.env` file:** Open the new `.env` file in a text editor. Paste your Google Sheet URL as the value for `SPREADSHEET_URL`. Save and close the file.

**3. Share the Sheet & Deploy the Form Script**
Finally, we give our script permission to read the sheet and then deploy the form.

* **Share the Sheet:**
    * In your `credentials.json` file, find and copy the `client_email` address.
    * In your Google Sheet, click the green "Share" button. Paste the `client_email`, grant it **"Viewer"** access, and click "Share".
* **Run the Setup Wizard:**
    * In your terminal, start the app:
        ```bash
        streamlit run app.py
        ```
    * The app will guide you to add members and create the first challenge.
    * After you save the first challenge, the app will **automatically display the Google Apps Script code**. Copy this code.
* **Deploy the Script:**
    * Go back to your Google Sheet and select `Extensions` > `Apps Script`.
    * Delete any existing code, paste the code you copied from the app, and click "Run" (▶️).
    * Authorize the script when prompted. It will create the form and log its shareable link.

### Stage 3: Daily Operation
You are now fully set up!

* **Members:** Fill out the Google Form to log their daily reading.
* **Admin (You):** Periodically, run the backend engine from your terminal to process new entries:
    ```bash
    python main.py
    ```
* **Everyone:** View the live, updated results by running the Streamlit dashboard:
    ```bash
    streamlit run app.py
    ```

## Project Structure
```
Reading-Tracker-Dashboard/
├── .gitignore
├── data/
│   └── reading_tracker.db
├── .env.example
├── app.py
├── database_setup.py
├── db_manager.py
├── main.py
├── README.md
└── requirements.txt
```