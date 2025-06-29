📚 Reading-Tracker-Dashboard
A data-driven dashboard to automate, visualize, and gamify your book club's reading challenges.

🎯 The Project Idea
This project provides a comprehensive, easy-to-use system for reading group administrators to manage a group reading challenge. The system automatically calculates member points based on their daily Google Form submissions and displays all statistics on a live, interactive dashboard.

👥 Who Is This For?
This project is designed for:

Book Clubs looking to add an element of fun, engagement, and friendly competition.

Groups of Friends who want to encourage and motivate each other to read more consistently.

Administrators & Organizers seeking a simple tool to automate the tedious process of tracking points and managing the challenge, instead of relying on manual calculations.

🚀 Getting Started (Admin's Guide)
Welcome, Admin! This guide will walk you through the entire process of setting up and running the system. Please follow the steps in order.

Stage 1: One-Time Prerequisite Setup
This stage covers everything you need to do on your local machine and on Google's platform to prepare for the application.

1. Requirements
Ensure you have Python 3.8+ installed.

Ensure you have Git installed.

2. Clone the Repository & Install Dependencies
Open your terminal or command prompt, and run the following commands to clone the project and set up the Python environment:

```
# Clone the repository to your computer
git clone https://github.com/your-username/Reading-Tracker-Dashboard.git

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

3. Setup the Google API Interface
This is the most detailed step. Its purpose is to create a secure "key" (a service account) that allows our Python script to automatically and safely read the data from your private Google Sheet.

Navigate to Google Cloud Console: Go to the Google Cloud Console and sign in.

Create a New Project: From the top navigation bar, select the project dropdown and click "New Project". Give it a descriptive name like Reading Challenge Bot and create it.

Enable APIs:

From the navigation menu (☰), go to "APIs & Services" > "Library".

Search for and Enable the following two APIs:

Google Sheets API (Allows the script to read spreadsheet data).

Google Drive API (Allows the script to find your sheet by its name or URL).

Create a Service Account:

From the navigation menu, go to "APIs & Services" > "Credentials".

Click "+ CREATE CREDENTIALS" and select "Service account".

Give it a name (e.g., sheet-reader-bot) and click "Create and Continue".

You can skip the next two optional steps ("Grant this service account access" and "Grant users access") by clicking "Continue" and then "Done".

Generate the JSON Key:

Back on the Credentials screen, you will see your new service account listed. Click on its email address.

Go to the "KEYS" tab.

Click "ADD KEY" and select "Create new key".

Choose the key type JSON and click "CREATE".

A JSON file will be automatically downloaded to your computer. This is your secret key. Treat it like a password.

Place the Key in Your Project: Rename the downloaded file to credentials.json and place it in the root directory of your project folder.

Stage 2: Initial Application Setup
Now that the code and keys are ready, we will run the application for the first time to complete the setup.

1. Create the Database
In your terminal (make sure the virtual environment is still active), run the following command only once:

python database_setup.py

This will create an empty, structured database file (data/reading_tracker.db) for your project.

2. Run the Setup Wizard
Now, start the application's user interface:

streamlit run app.py

The app will open in your browser and detect that this is the first run.

It will first ask you to enter your group members' names. Enter them and click "Save".

Next, it will ask you to enter the details for the first challenge (book title, author, dates). Enter them and click "Save".

3. Create and Link the Google Form
This final setup step connects the data entry form to our system.

Create a Google Sheet: Go to sheets.google.com and create a new, blank spreadsheet. Name it something clear, like "Reading Challenge Data".

Share the Sheet with the Service Account:

Open your credentials.json file. Find and copy the client_email address (it looks like sheet-reader-bot@...).

In your Google Sheet, click the green "Share" button.

Paste the client_email into the sharing dialog, grant it "Viewer" access, and click "Share".

Link the Sheet to the App:

Copy the URL of your Google Sheet from the browser's address bar.

In the Streamlit app, navigate to the "Settings" page. Paste the URL into the designated field and click save.

Generate and Deploy the Apps Script:

Navigate to the dedicated page in the Streamlit app for generating the Apps Script code. The app will automatically generate the script with your members' names included.

Copy the generated code.

Go back to your Google Sheet, and from the top menu, select Extensions > Apps Script.

Delete any existing code in the editor, paste the code you just copied, and click "Run" (▶️).

Authorize the script when prompted. It will then create the Google Form and link it to this sheet. You will find the shareable Form link in the execution log.

Stage 3: Daily Operation
You are now fully set up!

Members: Fill out the Google Form to log their daily reading.

Admin (You): Periodically (daily or weekly), run the backend engine from your terminal to process all new entries and recalculate stats:

python main.py

Everyone: View the live, updated results by running the Streamlit dashboard:

streamlit run app.py

Project Structure
```
Reading-Tracker-Dashboard/
├── .gitignore
├── data/
│   └── reading_tracker.db
├── app.py
├── database_setup.py
├── db_manager.py
├── main.py
├── README.md
└── requirements.txt
```