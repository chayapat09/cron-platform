

# Cron Job Manager

This is a Flask-based web application that allows you to schedule Python scripts as cron jobs and send the results to Discord. It includes a virtual environment setup so that it can run on any machine without dependency conflicts.

## Setup Instructions

### 1. Clone the Repository

```
git clone <repository-url>
cd cron_job_manager
```

### 2. Create and Activate a Virtual Environment
On UNIX/Linux/MacOS:

```
python3 -m venv venv
source venv/bin/activate
```

On Windows:
```
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies
```
pip install -r requirements.txt
```

### 4. Run the Application
```
python app.py
```

The app will start on http://127.0.0.1:5000.

## Optional: Running via Provided Scripts
For UNIX-like systems, you can run:
```
./run.sh
```
For Windows, double-click or run run.bat from the command prompt.

### Security Note
WARNING: The app uses exec to run arbitrary Python code. This is insecure for untrusted code. Consider sandboxing or other security measures for production use.
*(For UNIX-like systems – make sure to give execute permission with `chmod +x run.sh`)*
```
cron_job_manager/
├── README.md
├── requirements.txt
├── run.sh          # (Optional: for UNIX-like systems)
├── run.bat         # (Optional: for Windows)
├── app.py
└── templates/
    ├── base.html
    ├── dashboard.html
    ├── add_job.html
    ├── edit_job.html
    ├── job_detail.html
    └── settings.html
```