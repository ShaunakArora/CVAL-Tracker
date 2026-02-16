from flask import Flask, render_template, jsonify, send_from_directory, request, redirect, url_for, flash, session
import json
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask_wtf.csrf import CSRFProtect

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data.json')
USERS_FILE = os.path.join(BASE_DIR, 'users.json')
ALERTS_FILE = os.path.join(BASE_DIR, 'alerts.json')
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))

# Security Configuration
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key_here') # Load from ENV in production
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production' # True requires HTTPS

csrf = CSRFProtect(app)

ALL_FUNCTIONS = [
    "VI 3D Scan Pro",
    "VI 3D Desktop Pro",
    "Full Review",
    "Full Revision",
    "Short Review",
    "Short Revision",
    "VI Second Review",
    "Digital Operations - Sourcing",
    "Full Reports",
    "QCF (Underwriter Queue)",
    "Full Review (CI Abridged)",
    "CMP Client Import",
    "Text Followup",
    "ACR",
    "DNU Checklist Update",
    "PDC Compliance",
    "Meetings/Training"
]

def get_users():
    """Helper function to read users from file."""
    if not os.path.exists(USERS_FILE):
        return []
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return []

def save_users(users):
    """Helper function to save users to file."""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

def add_system_alert(message):
    """Helper function to add a system alert."""
    alerts = []
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE, 'r') as f:
                alerts = json.load(f)
        except (IOError, json.JSONDecodeError):
            alerts = []
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    alerts.insert(0, {'timestamp': timestamp, 'message': message})
    # Keep only the last 50 alerts to prevent file from growing too large
    alerts = alerts[:50]
    
    with open(ALERTS_FILE, 'w') as f:
        json.dump(alerts, f, indent=4)

def login_required(f):
    """Decorator to ensure a user is logged in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('You need to be logged in to view this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to ensure a user is an admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('You need to be logged in to view this page.', 'warning')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('You do not have permission to access this page.', 'danger')
            # Redirect non-admins to their own dashboard
            return redirect(url_for('employee_dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def landing():
    return render_template('login.html')

@app.route('/summary')
@login_required
def summary():
    if session.get('role') == 'admin':
        return redirect(url_for('admin_summary'))
    elif session.get('role') == 'employee':
        return redirect(url_for('employee_summary'))
    else:
        flash('You do not have permission to view a summary.', 'danger')
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # On first run, create a default admin if no users file
        if not os.path.exists(USERS_FILE):
            users = [{
                'username': 'admin',
                'password': generate_password_hash('admin'),
                'role': 'admin',
                'department': 'System',
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }]
            save_users(users)
        else:
            users = get_users()

        user = next((u for u in users if u['username'] == username), None)

        if user and check_password_hash(user.get('password'), password):
            session['user'] = user['username']
            session['role'] = user['role']
            
            if user['role'] == 'employee':
                add_system_alert(f"Employee {user['username']} logged in.")
            
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('employee_dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    if 'user' in session:
        # Log the logout if it's an employee
        if session.get('role') == 'employee':
            add_system_alert(f"Employee {session.get('user')} logged out.")
        session.clear()
    return redirect(url_for('login'))

@app.route('/employee/update', methods=['GET', 'POST'])
@login_required
def employee_update():
    if request.method == 'POST':
        try:
            # 1. Collect data from the form
            new_data = {
                'Team Member': session.get('user', 'Guest'),
                'Function': request.form.get('function'),
                'Date': request.form.get('date'),
                'File Number': request.form.get('file_number'),
                'Status': request.form.get('status'),
                'Tier 1 Escalation Reason': request.form.get('tier1_escalation'),
                'IM Escalation Reason': request.form.get('im_escalation'),
                'Department': request.form.get('department'),
                'Comments': request.form.get('comments')
            }

            # Load existing data
            logs = []
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, 'r') as f:
                    logs = json.load(f)
            
            logs.insert(0, new_data)
            
            # Save back to file
            with open(DATA_FILE, 'w') as f:
                json.dump(logs, f, indent=4)

            flash('Work log added successfully!', 'success')
            
        except Exception as e:
            flash(f'Error saving data: {str(e)}', 'danger')
        return redirect(url_for('employee_update'))

    # Fetch logs from file for the current user
    logs = []
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            all_logs = json.load(f)
            logs = [log for log in all_logs if log.get('Team Member') == session.get('user', 'Guest')]

    return render_template('employee/update_work.html', employee_name=session.get('user', 'Guest'), logs=logs)

@app.route('/employee/dashboard')
@login_required
def employee_dashboard():
    return render_template('employee/dashboard.html')

@app.route('/employee/summary')
@login_required
def employee_summary():
    # This page is for employees only.
    if session.get('role') != 'employee':
        flash('Access denied.', 'danger')
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('login'))

    logs = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                all_logs = json.load(f)
            logs = [log for log in all_logs if log.get('Team Member') == session.get('user')]
        except (IOError, json.JSONDecodeError):
            pass

    summary_counts = {func: 0 for func in ALL_FUNCTIONS}
    for log in logs:
        function = log.get('Function')
        if function:
            if function not in summary_counts:
                summary_counts[function] = 0
            summary_counts[function] += 1
    
    functions = sorted(summary_counts.keys())

    return render_template('employee/summary.html', 
                           summary_counts=summary_counts, 
                           functions=functions, 
                           employee_name=session.get('user'))

@app.route('/admin/summary')
@admin_required
def admin_summary():
    logs = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                logs = json.load(f)
        except (IOError, json.JSONDecodeError):
            pass

    summary_counts = {func: 0 for func in ALL_FUNCTIONS}
    for log in logs:
        function = log.get('Function')
        if function:
            if function not in summary_counts:
                summary_counts[function] = 0
            summary_counts[function] += 1
    
    functions = sorted(summary_counts.keys())
    return render_template('admin/summary.html', summary_counts=summary_counts, functions=functions)

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    alerts = []
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE, 'r') as f:
                alerts = json.load(f)
        except (IOError, json.JSONDecodeError):
            pass
    return render_template('admin/dashboard.html', alerts=alerts)

@app.route('/admin/create_employee', methods=['GET', 'POST'])
@admin_required
def create_employee():
    if request.method == 'POST':
        username = request.form.get('team_member')
        department = request.form.get('department')
        role = request.form.get('role')
        shift = request.form.get('shift')
        location = request.form.get('location')
        password = request.form.get('password')

        if not all([username, department, role, shift, location, password]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('create_employee'))

        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return redirect(url_for('create_employee'))

        users = get_users()
        if any(u.get('username') == username for u in users):
            flash(f'Employee "{username}" already exists.', 'danger')
            return redirect(url_for('create_employee'))

        hashed_password = generate_password_hash(password)
        
        users.append({
            'username': username,
            'department': department,
            'role': role,
            'shift': shift,
            'location': location,
            'password': hashed_password,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        save_users(users)
        flash(f'Employee "{username}" created successfully!', 'success')
        return redirect(url_for('view_employees'))

    return render_template('admin/create_employee.html')

@app.route('/admin/view_employees')
@admin_required
def view_employees():
    users = get_users()
    logs = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                logs = json.load(f)
        except (IOError, json.JSONDecodeError):
            pass  # Ignore if log file is empty or corrupt

    # Create a dictionary to hold the latest log date for each employee
    last_log_dates = {}
    for log in logs:
        name = log.get('Team Member')
        date_str = log.get('Date')
        if name and date_str and name not in last_log_dates:
            last_log_dates[name] = date_str  # Since logs are newest first

    employees = []
    now = datetime.now()
    for user in users:
        last_date_str = last_log_dates.get(user['username'])
        status = 'Inactive'
        
        if last_date_str:
            try:
                last_date = datetime.strptime(last_date_str, '%Y-%m-%d')
                if (now - last_date).days <= 7:
                    status = 'Active'
            except ValueError:
                pass  # Ignore invalid date formats

        employees.append({
            'Team Member': user['username'],
            'Department': user.get('department', ''),
            'Shift': user.get('shift', ''),
            'Location': user.get('location', ''),
            'Status': status,
            'Last_Login': last_date_str
        })
    return render_template('admin/view_employees.html', 
                           employees=employees)

@app.route('/admin/tracker')
@admin_required
def track_employee():
    all_logs = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                all_logs = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            flash(f'Error reading log data: {e}', 'danger')
    
    # Get employees from users file for the dropdown
    users = get_users()
    employees = sorted([user['username'] for user in users])

    selected_employee = request.args.get('employee')
    logs_to_display = [log for log in all_logs if log.get('Team Member') == selected_employee] if selected_employee else all_logs
    return render_template('admin/track_employee.html', employees=employees, logs=logs_to_display, selected_employee=selected_employee)

@app.route('/logo.png')
def serve_logo():
    return send_from_directory(os.path.join(BASE_DIR, 'templates'), 'logo.png')

@app.route('/favicon.ico')
def favicon():
    # Handle browser request for favicon to prevent 404 error
    return '', 204

@app.route('/chart-data')
@login_required
def chart_data():
    if not os.path.exists(DATA_FILE):
        return jsonify([])

    try:
        with open(DATA_FILE, 'r') as f:
            logs = json.load(f)

        # Define the columns expected by index.html
        columns = [
            "VI 3D Scan Pro", "VI 3D Desktop Pro", "Full Review", "Full Revision",
            "Short Review", "Short Revision", "VI Second Review", 
            "Digital Operations - Sourcing", "Full Reports", "QCF (Underwriter Queue)",
            "Full Review (CI Abridged)", "CMP Client Import", "Text Followup",
            "ACR", "DNU Checklist Update", "PDC Compliance", "Total Hours", 
            "Meetings/Training"
        ]

        # Aggregate data by Date
        aggregated_data = {}
        
        for log in logs:
            date = log.get('Date')
            function = log.get('Function')
            
            if not date:
                continue
                
            if date not in aggregated_data:
                # Initialize row with 0s
                row = {col: 0 for col in columns}
                row['Date'] = date
                aggregated_data[date] = row
            
            # Increment count if the function matches a column
            if function in aggregated_data[date]:
                aggregated_data[date][function] += 1

        # Convert dict to list
        return jsonify(list(aggregated_data.values()))
    except Exception as e:
        print(f"Error generating chart data: {e}")
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    print(f"Template folder set to: {os.path.join(BASE_DIR, 'templates')}")
    # Disable debug mode by default for security. Enable via env var if needed.
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, port=5000)
