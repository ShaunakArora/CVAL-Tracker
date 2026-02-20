from flask import Flask, render_template, jsonify, send_from_directory, request, redirect, url_for, flash, session
import os
import json
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask_wtf.csrf import CSRFProtect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))

# Security Configuration
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key_here') # Load from ENV in production
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'

# Database Configuration
db_uri = os.environ.get('DATABASE_URL', 'postgresql://neondb_owner:npg_Qa9KTfvgFEd1@ep-hidden-tree-aipy45fo-pooler.c-4.us-east-1.aws.neon.tech/cval-db?sslmode=require&channel_binding=require')
if db_uri and db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri or f"sqlite:///{os.path.join(BASE_DIR, 'app.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

csrf = CSRFProtect(app)

# --- SQLAlchemy Models ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='employee')
    department = db.Column(db.String(80))
    shift = db.Column(db.String(50))
    location = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_member = db.Column(db.String(80), nullable=False)
    function = db.Column(db.String(100))
    date = db.Column(db.Date)
    file_number = db.Column(db.String(50))
    status = db.Column(db.String(50))
    tier1_escalation_reason = db.Column(db.String(200))
    im_escalation_reason = db.Column(db.String(200))
    department = db.Column(db.String(80))
    comments = db.Column(db.Text)

class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    message = db.Column(db.String(500), nullable=False)

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

def add_system_alert(message):
    """Adds a system alert to the database and keeps the latest 50."""
    new_alert = Alert(message=message, timestamp=datetime.now())
    db.session.add(new_alert)

    # Keep only the last 50 alerts
    try:
        alert_count = Alert.query.count()
        if alert_count > 50:
            oldest_alerts = Alert.query.order_by(Alert.timestamp.asc()).limit(alert_count - 50).all()
            for alert in oldest_alerts:
                db.session.delete(alert)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error managing alerts: {e}")

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

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['user'] = user.username
            session['role'] = user.role
            
            if user.role == 'employee':
                add_system_alert(f"Employee {user.username} logged in.")
            
            if user.role == 'admin':
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
            date_str = request.form.get('date')
            log_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else None

            new_log = Log(
                team_member=session.get('user', 'Guest'),
                function=request.form.get('function'),
                date=log_date,
                file_number=request.form.get('file_number'),
                status=request.form.get('status'),
                tier1_escalation_reason=request.form.get('tier1_escalation'),
                im_escalation_reason=request.form.get('im_escalation'),
                department=request.form.get('department'),
                comments=request.form.get('comments')
            )
            db.session.add(new_log)
            db.session.commit()
            flash('Work log added successfully!', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving data: {str(e)}', 'danger')
        return redirect(url_for('employee_update'))

    # Fetch logs for the current user
    logs = Log.query.filter_by(
        team_member=session.get('user', 'Guest')
    ).order_by(
        Log.id.desc()
    ).all()

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

    logs = Log.query.filter_by(team_member=session.get('user')).all()

    summary_counts = {func: 0 for func in ALL_FUNCTIONS}
    for log in logs:
        function = log.function
        if function in summary_counts:
            summary_counts[function] += 1
    
    functions = sorted(summary_counts.keys())

    return render_template('employee/summary.html', 
                           summary_counts=summary_counts, 
                           functions=functions, 
                           employee_name=session.get('user'))

@app.route('/admin/summary')
@admin_required
def admin_summary():
    # Using a more efficient query
    summary_counts_query = db.session.query(Log.function, func.count(Log.function)).group_by(Log.function).all()
    
    summary_counts = {func: 0 for func in ALL_FUNCTIONS}
    for function, count in summary_counts_query:
        if function in summary_counts:
            summary_counts[function] = count
    
    functions = sorted(summary_counts.keys())

    return render_template('admin/summary.html', summary_counts=summary_counts, functions=functions)

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    alerts = Alert.query.order_by(Alert.timestamp.desc()).all()
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

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash(f'Employee "{username}" already exists.', 'danger')
            return redirect(url_for('create_employee'))

        hashed_password = generate_password_hash(password)
        
        new_user = User(
            username=username,
            department=department,
            role=role,
            shift=shift,
            location=location,
            password=hashed_password,
            created_at=datetime.now()
        )
        db.session.add(new_user)
        db.session.commit()
        flash(f'Employee "{username}" created successfully!', 'success')
        return redirect(url_for('view_employees'))

    return render_template('admin/create_employee.html')

@app.route('/admin/view_employees')
@admin_required
def view_employees():
    users = User.query.order_by(User.username).all()

    # Get the most recent log date for each user in a single query
    subquery = db.session.query(
        Log.team_member,
        func.max(Log.date).label('last_log_date')
    ).group_by(Log.team_member).subquery()

    last_log_dates = {row.team_member: row.last_log_date for row in db.session.query(subquery).all()}

    employees = []
    seven_days_ago = datetime.now().date() - timedelta(days=7)

    for user in users:
        last_date = last_log_dates.get(user.username)
        status = 'Inactive'
        
        if last_date and last_date >= seven_days_ago:
            status = 'Active'

        employees.append({
            'Team Member': user.username,
            'Department': user.department,
            'Shift': user.shift,
            'Location': user.location,
            'Status': status,
            'Last_Login': last_date.strftime('%Y-%m-%d') if last_date else 'N/A'
        })
    return render_template('admin/view_employees.html', 
                           employees=employees)

@app.route('/admin/tracker')
@admin_required
def track_employee():
    users = User.query.order_by(User.username).all()
    employees = [user.username for user in users]

    selected_employee = request.args.get('employee')
    
    query = Log.query
    if selected_employee:
        query = query.filter_by(team_member=selected_employee)
        
    logs_to_display = query.order_by(Log.id.desc()).all()
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
    try:
        # Query logs and aggregate by date and function
        logs_by_date_func = db.session.query(
            Log.date,
            Log.function,
            func.count(Log.id)
        ).group_by(Log.date, Log.function).all()

        columns = ALL_FUNCTIONS + ["Total Hours"] # Total Hours seems unused, keeping for compatibility

        # Aggregate data by Date
        aggregated_data = {}
        for log_date, function, count in logs_by_date_func:
            if not log_date:
                continue
            
            date_str = log_date.strftime('%Y-%m-%d')
                
            if date_str not in aggregated_data:
                # Initialize row with 0s
                row = {col: 0 for col in columns}
                row['Date'] = date_str
                aggregated_data[date_str] = row
            
            # Increment count if the function matches a column
            if function in aggregated_data[date_str]:
                aggregated_data[date_str][function] += count

        # Convert dict to list
        return jsonify(list(aggregated_data.values()))
    except Exception as e:
        print(f"Error generating chart data: {e}")
        return jsonify({'error': str(e)})

@app.cli.command("init-db")
def init_db_command():
    """Creates the database tables and a default admin user."""
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        hashed_password = generate_password_hash('admin')
        admin_user = User(username='admin', password=hashed_password, role='admin', department='System')
        db.session.add(admin_user)
        db.session.commit()
        print("Database initialized and admin user created.")
    else:
        print("Database already initialized.")

@app.cli.command("import-data")
def import_data_command():
    """Imports data from existing JSON files into the database."""
    
    # Import Users
    users_file = os.path.join(BASE_DIR, 'users.json')
    if os.path.exists(users_file):
        with open(users_file, 'r') as f:
            users_data = json.load(f)
            for u_data in users_data:
                if not User.query.filter_by(username=u_data['username']).first():
                    created_at = datetime.utcnow()
                    if 'created_at' in u_data:
                        try:
                            created_at = datetime.strptime(u_data['created_at'], '%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            pass
                    
                    user = User(
                        username=u_data['username'],
                        password=u_data['password'], # Already hashed in JSON
                        role=u_data['role'],
                        department=u_data.get('department'),
                        shift=u_data.get('shift'),
                        location=u_data.get('location'),
                        created_at=created_at
                    )
                    db.session.add(user)
            db.session.commit()
            print(f"Imported users from {users_file}")

    # Import Logs
    data_file = os.path.join(BASE_DIR, 'data.json')
    if os.path.exists(data_file):
        with open(data_file, 'r') as f:
            logs_data = json.load(f)
            for l_data in logs_data:
                log_date = None
                if l_data.get('Date'):
                    try:
                        log_date = datetime.strptime(l_data['Date'], '%Y-%m-%d').date()
                    except ValueError:
                        pass
                
                log = Log(
                    team_member=l_data.get('Team Member'),
                    function=l_data.get('Function'),
                    date=log_date,
                    file_number=l_data.get('File Number'),
                    status=l_data.get('Status'),
                    tier1_escalation_reason=l_data.get('Tier 1 Escalation Reason'),
                    im_escalation_reason=l_data.get('IM Escalation Reason'),
                    department=l_data.get('Department'),
                    comments=l_data.get('Comments')
                )
                db.session.add(log)
            db.session.commit()
            print(f"Imported logs from {data_file}")

    # Import Alerts
    alerts_file = os.path.join(BASE_DIR, 'alerts.json')
    if os.path.exists(alerts_file):
        with open(alerts_file, 'r') as f:
            alerts_data = json.load(f)
            for a_data in alerts_data:
                timestamp = datetime.utcnow()
                if a_data.get('timestamp'):
                    try:
                        timestamp = datetime.strptime(a_data['timestamp'], '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        pass
                
                alert = Alert(
                    message=a_data.get('message'),
                    timestamp=timestamp
                )
                db.session.add(alert)
            db.session.commit()
            print(f"Imported alerts from {alerts_file}")

if __name__ == '__main__':
    print(f"Template folder set to: {os.path.join(BASE_DIR, 'templates')}")
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, port=5000)
