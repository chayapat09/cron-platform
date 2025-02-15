import datetime, io, contextlib, traceback, requests, sys, os, tempfile, subprocess
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # Replace with a strong secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jobs.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ---------------------------
# Database Models
# ---------------------------
class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    cron = db.Column(db.String(100), nullable=False)  # e.g., "*/5 * * * *"
    code = db.Column(db.Text, nullable=False)
    # New field: Extra dependencies (as pip requirements, one per line)
    dependencies = db.Column(db.Text, nullable=True)
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow,
                           onupdate=datetime.datetime.utcnow)

class RunHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    status = db.Column(db.String(20))  # "Success" or "Failed"
    output = db.Column(db.Text)
    error = db.Column(db.Text)

class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)

# ---------------------------
# Scheduler Setup
# ---------------------------
scheduler = BackgroundScheduler()
scheduler.start()

def run_job(job_id):
    """Execute the job’s Python code in an isolated virtual environment and record the output/error."""
    job = Job.query.get(job_id)
    if not job or not job.enabled:
        return
    output = ""
    error = ""
    status = "Success"
    try:
        # Create a temporary directory for the isolated environment
        with tempfile.TemporaryDirectory() as tmpdirname:
            # Create a virtual environment inside the temporary directory
            venv_path = os.path.join(tmpdirname, "venv")
            subprocess.run([sys.executable, "-m", "venv", venv_path], check=True)
            
            # Determine the correct paths to the virtual environment's python and pip
            if os.name == "nt":
                python_bin = os.path.join(venv_path, "Scripts", "python.exe")
                pip_bin = os.path.join(venv_path, "Scripts", "pip.exe")
            else:
                python_bin = os.path.join(venv_path, "bin", "python")
                pip_bin = os.path.join(venv_path, "bin", "pip")
            
            # If extra dependencies are provided, install them
            if job.dependencies and job.dependencies.strip():
                req_path = os.path.join(tmpdirname, "requirements.txt")
                with open(req_path, "w") as req_file:
                    req_file.write(job.dependencies)
                # Install dependencies (capture output to avoid printing to console)
                pip_install = subprocess.run([pip_bin, "install", "-r", req_path],
                                             capture_output=True, text=True)
                if pip_install.returncode != 0:
                    raise Exception("Dependency installation failed:\n" +
                                    pip_install.stderr)
            
            # Write the job's code to a temporary file
            script_path = os.path.join(tmpdirname, "job_script.py")
            with open(script_path, "w", encoding="utf-8") as script_file:
                script_file.write(job.code)
            
            # Execute the script using the virtual environment's python interpreter
            result = subprocess.run([python_bin, script_path],
                                    capture_output=True, text=True)
            output = result.stdout
            error = result.stderr
            if result.returncode != 0:
                status = "Failed"
    except Exception as e:
        error += "\n" + traceback.format_exc()
        status = "Failed"
    
    # Record run history in the database.
    run = RunHistory(job_id=job.id, status=status, output=output, error=error)
    db.session.add(run)
    db.session.commit()

    # Push the result to Discord if a webhook URL is configured.
    discord_setting = Setting.query.filter_by(key="discord_webhook").first()
    if discord_setting and discord_setting.value:
        webhook_url = discord_setting.value.strip()
        message = (
            f"**Job:** {job.name}\n"
            f"**Time (UTC):** {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"**Status:** {status}\n"
            f"**Output:**\n```python\n{output if output.strip() else '---'}\n```\n"
            f"**Error:**\n```python\n{error}\n```"
        )
        payload = {"content": message}

        payload = {"content": message}
        try:
            requests.post(webhook_url, json=payload)
        except Exception as e:
            print("Error pushing to Discord:", e)

def schedule_job(job):
    """Add a job to the scheduler based on its cron expression.
       Expected cron format: 'minute hour day month weekday' (5 parts).
    """
    parts = job.cron.strip().split()
    if len(parts) != 5:
        print(f"Invalid cron format for job {job.name}")
        return
    try:
        trigger = CronTrigger(minute=parts[0], hour=parts[1],
                                day=parts[2], month=parts[3],
                                day_of_week=parts[4])
        scheduler.add_job(func=run_job,
                          trigger=trigger,
                          args=[job.id],
                          id=str(job.id),
                          replace_existing=True)
    except Exception as e:
        print("Error scheduling job:", e)

# ---------------------------
# One-Time Initialization Using a Before Request Hook
# ---------------------------
initialized = False

@app.before_request
def initialize_once():
    global initialized
    if not initialized:
        db.create_all()
        # (Re)load all enabled jobs into the scheduler.
        for job in Job.query.filter_by(enabled=True).all():
            schedule_job(job)
        initialized = True

# ---------------------------
# Routes & Views
# ---------------------------

@app.route('/')
def dashboard():
    jobs = Job.query.order_by(Job.created_at.desc()).all()
    return render_template('dashboard.html', jobs=jobs)

@app.route('/job/<int:job_id>')
def job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    run_history = RunHistory.query.filter_by(job_id=job_id).order_by(RunHistory.timestamp.desc()).all()
    return render_template('job_detail.html', job=job, run_history=run_history)

@app.route('/job/add', methods=['GET', 'POST'])
def add_job():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description', '')
        cron = request.form['cron']
        code = request.form['code']
        # Read the extra dependencies (if any)
        dependencies = request.form.get('dependencies', '')
        new_job = Job(name=name, description=description, cron=cron,
                      code=code, dependencies=dependencies, enabled=True)
        db.session.add(new_job)
        db.session.commit()
        schedule_job(new_job)
        flash("Job added successfully", "success")
        return redirect(url_for('dashboard'))
    return render_template('add_job.html')

@app.route('/job/edit/<int:job_id>', methods=['GET', 'POST'])
def edit_job(job_id):
    job = Job.query.get_or_404(job_id)
    if request.method == 'POST':
        job.name = request.form['name']
        job.description = request.form.get('description', '')
        job.cron = request.form['cron']
        job.code = request.form['code']
        job.dependencies = request.form.get('dependencies', '')
        job.enabled = True if request.form.get('enabled') == 'on' else False
        db.session.commit()
        try:
            scheduler.remove_job(str(job.id))
        except Exception:
            pass
        if job.enabled:
            schedule_job(job)
        flash("Job updated successfully", "success")
        return redirect(url_for('dashboard'))
    return render_template('edit_job.html', job=job)

@app.route('/job/delete/<int:job_id>', methods=['POST'])
def delete_job(job_id):
    job = Job.query.get_or_404(job_id)
    db.session.delete(job)
    db.session.commit()
    try:
        scheduler.remove_job(str(job.id))
    except Exception:
        pass
    flash("Job deleted", "success")
    return redirect(url_for('dashboard'))

@app.route('/job/run/<int:job_id>', methods=['POST'])
def run_job_manual(job_id):
    run_job(job_id)
    flash("Job executed manually", "info")
    return redirect(url_for('job_detail', job_id=job_id))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    discord_setting = Setting.query.filter_by(key="discord_webhook").first()
    if request.method == 'POST':
        webhook = request.form.get('discord_webhook', '')
        if discord_setting:
            discord_setting.value = webhook
        else:
            discord_setting = Setting(key="discord_webhook", value=webhook)
            db.session.add(discord_setting)
        db.session.commit()
        flash("Settings updated", "success")
        return redirect(url_for('settings'))
    current_webhook = discord_setting.value if discord_setting else ''
    return render_template('settings.html', discord_webhook=current_webhook)

# ---------------------------
# Run the App
# ---------------------------
if __name__ == '__main__':
    app.run(debug=True)
