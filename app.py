from flask import Flask, render_template, jsonify, send_from_directory, request, redirect, url_for, flash, session, Response
from dotenv import load_dotenv
load_dotenv()
import os
import json
import io
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask_wtf.csrf import CSRFProtect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, extract, text
import dash
from dash import dcc, html
import plotly.express as px
import pandas as pd
from openpyxl import Workbook
from openpyxl.drawing.image import Image
from openpyxl.styles import Font

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))

# Security Configuration
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key_here') # Load from ENV in production
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'

# Database Configuration
db_uri = os.environ.get('DATABASE_URL')
if db_uri and db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri or f"sqlite:///{os.path.join(BASE_DIR, 'app.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

csrf = CSRFProtect(app)

# --- SQLAlchemy Models ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(50), unique=True, nullable=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='employee')
    department = db.Column(db.String(80))
    shift = db.Column(db.String(50))
    location = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_member = db.Column(db.String(80), nullable=False, index=True)
    function = db.Column(db.String(100))
    date = db.Column(db.Date, index=True)   
    file_number = db.Column(db.String(100))
    status = db.Column(db.String(100))
    tier1_escalation_reason = db.Column(db.String(200))
    im_escalation_reason = db.Column(db.String(200))
    department = db.Column(db.String(80))
    comments = db.Column(db.Text)
    count = db.Column(db.String(50))
    bucket = db.Column(db.String(100))
    time = db.Column(db.String(50))
    production_task = db.Column(db.String(100))
    month = db.Column(db.String(50))

class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    message = db.Column(db.String(500), nullable=False)

class Function(db.Model):
    __tablename__ = 'functions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

class Department(db.Model):
    __tablename__ = 'department'
    id = db.Column(db.Integer, primary_key=True)
    dept_name = db.Column(db.String(100), unique=True, nullable=False)


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

def init_dashboard(app):
    """Create a Plotly Dash dashboard."""
    dash_app = dash.Dash(
        server=app,
        routes_pathname_prefix="/admin/analytics/",
        external_stylesheets=[
            "https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css"
        ],
        suppress_callback_exceptions=True
    )

    # Protect Dash views
    for view_func_name, view_func in app.view_functions.items():
        if view_func_name.startswith(dash_app.config["routes_pathname_prefix"]):
            app.view_functions[view_func_name] = admin_required(view_func)

    # Create Dash layout
    def create_layout():
        logs = Log.query.all()
        if not logs:
            return html.Div([
                html.H1("Analytics Dashboard"),
                html.P("No data available to display.")
            ], className="container")

        df = pd.DataFrame(
            [
                {
                    "team_member": log.team_member,
                    "function": log.function,
                    "date": log.date,
                    "status": log.status,
                }
                for log in logs if log.date # Ensure date is not None
            ]
        )

        if df.empty:
            return html.Div([
                html.H1("Analytics Dashboard"),
                html.P("No data with valid dates available to display.")
            ], className="container")

        # 1. KPI cards
        total_logs = len(df)
        # NOTE: Assuming 'Completed' is a valid status for completion rate.
        completed_logs = df[df['status'].isin(['Completed', 'Approved'])].shape[0]
        completion_rate = (completed_logs / total_logs) * 100 if total_logs > 0 else 0
        top_employee_series = df['team_member'].mode()
        top_employee = top_employee_series[0] if not top_employee_series.empty else "N/A"

        # 2. Interactive Time series
        df['date'] = pd.to_datetime(df['date'])
        logs_over_time = df.groupby(df['date'].dt.date).size().reset_index(name='count')
        time_series_fig = px.line(logs_over_time, x='date', y='count', title='Total Logs Over Time', labels={'date': 'Date', 'count': 'Number of Logs'})

        # 3. Horizontal bars: Top functions and employees
        top_functions = df['function'].value_counts().nlargest(10).sort_values(ascending=True)
        top_functions_fig = px.bar(top_functions, x=top_functions.values, y=top_functions.index, orientation='h', title='Top 10 Functions', labels={'x': 'Count', 'y': 'Function'})

        top_employees = df['team_member'].value_counts().nlargest(10).sort_values(ascending=True)
        top_employees_fig = px.bar(top_employees, x=top_employees.values, y=top_employees.index, orientation='h', title='Top 10 Employees by Logs', labels={'x': 'Count', 'y': 'Employee'})

        # 4. Donut chart: Functions distribution
        function_dist = df['function'].value_counts()
        function_dist_fig = px.pie(function_dist, values=function_dist.values, names=function_dist.index, title='Functions Distribution', hole=0.4)

        layout = html.Div(className="container-fluid", children=[
            html.H1("Analytics Dashboard", className="my-4"),

            # KPI Cards
            html.Div(className="row", children=[
                html.Div(className="col-md-4", children=[
                    html.Div(className="card text-white bg-primary mb-3", children=[
                        html.Div(className="card-header", children="Total Logs"),
                        html.Div(className="card-body", children=[html.H4(f"{total_logs}", className="card-title")])
                    ])
                ]),
                html.Div(className="col-md-4", children=[
                    html.Div(className="card text-white bg-success mb-3", children=[
                        html.Div(className="card-header", children="Completion Rate"),
                        html.Div(className="card-body", children=[html.H4(f"{completion_rate:.2f}%", className="card-title")])
                    ])
                ]),
                html.Div(className="col-md-4", children=[
                    html.Div(className="card text-white bg-info mb-3", children=[
                        html.Div(className="card-header", children="Top Employee (by logs)"),
                        html.Div(className="card-body", children=[html.H4(top_employee, className="card-title")])
                    ])
                ]),
            ]),

            # Time Series
            html.Div(className="row", children=[
                html.Div(className="col", children=[
                    dcc.Graph(figure=time_series_fig)
                ])
            ]),

            # Bar Charts
            html.Div(className="row mt-4", children=[
                html.Div(className="col-md-6", children=[
                    dcc.Graph(figure=top_functions_fig)
                ]),
                html.Div(className="col-md-6", children=[
                    dcc.Graph(figure=top_employees_fig)
                ])
            ]),

            # Donut Chart
            html.Div(className="row mt-4", children=[
                html.Div(className="col-md-8 offset-md-2", children=[
                    dcc.Graph(figure=function_dist_fig)
                ])
            ])
        ])
        return layout

    dash_app.layout = create_layout

    return dash_app.server

def init_daily_dashboard(app):
    """Create a Plotly Dash dashboard for Daily Analytics."""
    dash_app = dash.Dash(
        server=app,
        routes_pathname_prefix="/admin/daily_analytics/",
        external_stylesheets=[
            "https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css"
        ],
        suppress_callback_exceptions=True
    )

    # Protect Dash views
    for view_func_name, view_func in app.view_functions.items():
        if view_func_name.startswith(dash_app.config["routes_pathname_prefix"]):
            app.view_functions[view_func_name] = admin_required(view_func)

    # Create Dash layout
    def create_layout():
        today = datetime.now().date()
        logs = Log.query.filter(Log.date == today).all()
        
        if not logs:
            return html.Div([
                html.H1(f"Daily Analytics ({today})"),
                html.P("No data available for today.")
            ], className="container")

        df = pd.DataFrame(
            [
                {
                    "team_member": log.team_member,
                    "function": log.function,
                    "date": log.date,
                    "status": log.status,
                }
                for log in logs
            ]
        )

        if df.empty:
            return html.Div([
                html.H1(f"Daily Analytics ({today})"),
                html.P("No data available to display.")
            ], className="container")

        # 1. KPI cards
        total_logs = len(df)
        completed_logs = df[df['status'].isin(['Completed', 'Approved'])].shape[0]
        completion_rate = (completed_logs / total_logs) * 100 if total_logs > 0 else 0
        top_employee_series = df['team_member'].mode()
        top_employee = top_employee_series[0] if not top_employee_series.empty else "N/A"

        # 2. Horizontal bars: Top functions and employees
        top_functions = df['function'].value_counts().nlargest(10).sort_values(ascending=True)
        top_functions_fig = px.bar(top_functions, x=top_functions.values, y=top_functions.index, orientation='h', title='Top 10 Functions Today', labels={'x': 'Count', 'y': 'Function'})

        top_employees = df['team_member'].value_counts().nlargest(10).sort_values(ascending=True)
        top_employees_fig = px.bar(top_employees, x=top_employees.values, y=top_employees.index, orientation='h', title='Top 10 Employees Today', labels={'x': 'Count', 'y': 'Employee'})

        # 3. Donut chart: Functions distribution
        function_dist = df['function'].value_counts()
        function_dist_fig = px.pie(function_dist, values=function_dist.values, names=function_dist.index, title='Functions Distribution Today', hole=0.4)

        layout = html.Div(className="container-fluid", children=[
            html.Div(className="row align-items-center my-4", children=[
                html.Div(className="col-md-9", children=[
                    html.H1(f"Daily Analytics ({today})"),
                ]),
                html.Div(className="col-md-3 text-md-end", children=[
                    html.A(
                        [html.I(className="fas fa-file-excel me-2"), "Export to Excel"],
                        href="/admin/daily_analytics/export",
                        className="btn btn-success",
                    )
                ])
            ]),

            # KPI Cards
            html.Div(className="row", children=[
                html.Div(className="col-md-4", children=[
                    html.Div(className="card text-white bg-primary mb-3", children=[
                        html.Div(className="card-header", children="Total Logs Today"),
                        html.Div(className="card-body", children=[html.H4(f"{total_logs}", className="card-title")])
                    ])
                ]),
                html.Div(className="col-md-4", children=[
                    html.Div(className="card text-white bg-success mb-3", children=[
                        html.Div(className="card-header", children="Completion Rate"),
                        html.Div(className="card-body", children=[html.H4(f"{completion_rate:.2f}%", className="card-title")])
                    ])
                ]),
                html.Div(className="col-md-4", children=[
                    html.Div(className="card text-white bg-info mb-3", children=[
                        html.Div(className="card-header", children="Top Employee Today"),
                        html.Div(className="card-body", children=[html.H4(top_employee, className="card-title")])
                    ])
                ]),
            ]),

            # Bar Charts
            html.Div(className="row mt-4", children=[
                html.Div(className="col-md-6", children=[
                    dcc.Graph(figure=top_functions_fig)
                ]),
                html.Div(className="col-md-6", children=[
                    dcc.Graph(figure=top_employees_fig)
                ])
            ]),

            # Donut Chart
            html.Div(className="row mt-4", children=[
                html.Div(className="col-md-8 offset-md-2", children=[
                    dcc.Graph(figure=function_dist_fig)
                ])
            ])
        ])
        return layout

    dash_app.layout = create_layout

    return dash_app.server

@app.route('/admin/daily_analytics/export')
@admin_required
def export_daily_analytics():
    """Exports the daily analytics dashboard to a formatted Excel file."""
    today = datetime.now().date()
    logs = Log.query.filter(Log.date == today).all()

    if not logs:
        flash('No data available for today to export.', 'warning')
        return redirect('/admin/daily_analytics/')

    df = pd.DataFrame([
        {"team_member": log.team_member, "function": log.function, "date": log.date, "status": log.status}
        for log in logs
    ])

    if df.empty:
        flash('No data available to display.', 'warning')
        return redirect('/admin/daily_analytics/')

    # --- 1. Calculate KPIs ---
    total_logs = len(df)
    completed_logs = df[df['status'].isin(['Completed', 'Approved'])].shape[0]
    completion_rate = (completed_logs / total_logs) * 100 if total_logs > 0 else 0
    top_employee_series = df['team_member'].mode()
    top_employee = top_employee_series[0] if not top_employee_series.empty else "N/A"

    # --- 2. Generate Figures ---
    top_functions = df['function'].value_counts().nlargest(10).sort_values(ascending=True)
    top_functions_fig = px.bar(top_functions, x=top_functions.values, y=top_functions.index, orientation='h', title='Top 10 Functions Today', labels={'x': 'Count', 'y': 'Function'})

    top_employees = df['team_member'].value_counts().nlargest(10).sort_values(ascending=True)
    top_employees_fig = px.bar(top_employees, x=top_employees.values, y=top_employees.index, orientation='h', title='Top 10 Employees Today', labels={'x': 'Count', 'y': 'Employee'})

    function_dist = df['function'].value_counts()
    function_dist_fig = px.pie(function_dist, values=function_dist.values, names=function_dist.index, title='Functions Distribution Today', hole=0.4)

    # --- 3. Save Figures to Image Bytes ---
    img_top_funcs = top_functions_fig.to_image(format="png", width=600, height=400)
    img_top_emps = top_employees_fig.to_image(format="png", width=600, height=400)
    img_func_dist = function_dist_fig.to_image(format="png", width=800, height=500)

    # --- 4. Create and Format Excel File in Memory ---
    output = io.BytesIO()
    workbook = Workbook()
    ws = workbook.active
    ws.title = "Daily Analytics"

    # Title
    ws['A1'] = f"Daily Analytics Report for {today.strftime('%Y-%m-%d')}"
    ws['A1'].font = Font(size=20, bold=True)
    ws.merge_cells('A1:F1')

    # KPIs
    ws['A3'] = "Key Performance Indicators"; ws['A3'].font = Font(size=14, bold=True, underline="single")
    ws['A5'] = "Total Logs Today:"; ws['A5'].font = Font(bold=True)
    ws['B5'] = total_logs
    ws['A6'] = "Completion Rate:"; ws['A6'].font = Font(bold=True)
    ws['B6'] = f"{completion_rate:.2f}%"
    ws['A7'] = "Top Employee Today:"; ws['A7'].font = Font(bold=True)
    ws['B7'] = top_employee

    # Graphical Analysis
    ws['A9'] = "Graphical Analysis"; ws['A9'].font = Font(size=14, bold=True, underline="single")
    ws['A10'] = "Top 10 Functions by Log Count"; ws['A10'].font = Font(bold=True)
    ws.add_image(Image(io.BytesIO(img_top_funcs)), 'A11')
    ws['J10'] = "Top 10 Employees by Log Count"; ws['J10'].font = Font(bold=True)
    ws.add_image(Image(io.BytesIO(img_top_emps)), 'J11')
    ws['A34'] = "Overall Function Distribution"; ws['A34'].font = Font(bold=True)
    ws.add_image(Image(io.BytesIO(img_func_dist)), 'A35')

    workbook.save(output)
    output.seek(0)

    # --- 5. Serve the file ---
    filename = f"Daily_Analytics_{today.strftime('%Y-%m-%d')}.xlsx"
    return Response(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

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
        username = request.form.get('username', '').strip()
        password = request.form.get('password')

        # Case-insensitive username lookup
        user = User.query.filter(func.lower(User.username) == username.lower()).first()

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
    current_user = User.query.filter_by(username=session.get('user')).first()
    user_department = current_user.department if current_user else ""

    if request.method == 'POST':
        try:
            date_str = request.form.get('date')
            log_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else None

            team_member = session.get('user', 'Guest')
            file_number = request.form.get('file_number')
            status = request.form.get('status')

            # When trying to log a new task as 'In Progress'
            if status == 'In Progress':
                # Get the latest log entry for this employee
                latest_log = Log.query.filter_by(
                    team_member=team_member,
                ).order_by(Log.id.desc()).first()

                # Check if their latest task is still 'In Progress'
                if latest_log and latest_log.status == 'In Progress':
                    flash(f"You cannot start a new file. Your latest task for file '{latest_log.file_number}' is still 'In Progress'.", 'danger')
                    return redirect(url_for('employee_update'))

            # Handle tasks without a file number, or when status is 'In Progress'
            # These always create a new log entry.
            if not file_number or status == 'In Progress':
                # The check for duplicates is now handled above.
                new_log = Log(
                    team_member=team_member,
                    function=request.form.get('function'),
                    date=log_date,
                    file_number=file_number,
                    status=status,
                    tier1_escalation_reason=request.form.get('tier1_escalation'),
                    im_escalation_reason=request.form.get('im_escalation'),
                    department=user_department,
                    comments=request.form.get('comments')
                )
                db.session.add(new_log)
                db.session.commit()
                flash('Work log added successfully!', 'success')

            # Handle status updates for existing 'In Progress' files
            else:  # file_number exists and status is not 'In Progress'
                log_to_update = Log.query.filter_by(
                    team_member=team_member,
                    file_number=file_number,
                    status='In Progress'
                ).first()

                if log_to_update:
                    # Update the existing log entry
                    log_to_update.status = status
                    log_to_update.date = log_date
                    log_to_update.tier1_escalation_reason = request.form.get('tier1_escalation')
                    log_to_update.im_escalation_reason = request.form.get('im_escalation')
                    log_to_update.comments = request.form.get('comments')
                    db.session.commit()
                    flash(f"Work log for file '{file_number}' updated to '{status}'.", 'success')
                else:
                    # No 'In Progress' log found to update.
                    flash(f"Error: You must first log file '{file_number}' with 'In Progress' status before setting it to '{status}'.", 'danger')
            
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

    functions = [f.name for f in Function.query.order_by(Function.name).all()]

    return render_template('employee/update_work.html', employee_name=session.get('user', 'Guest'), logs=logs, user_department=user_department, functions=functions)

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

    all_functions = [f.name for f in Function.query.order_by(Function.name).all()]
    summary_counts = {func: 0 for func in all_functions}
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
    
    all_functions = [f.name for f in Function.query.order_by(Function.name).all()]
    summary_counts = {func: 0 for func in all_functions}
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

@app.route('/admin/functions', methods=['GET', 'POST'])
@admin_required
def manage_functions():
    if request.method == 'POST':
        function_name = request.form.get('name', '').strip()
        if not function_name:
            flash('Function name cannot be empty.', 'danger')
        elif Function.query.filter(func.lower(Function.name) == function_name.lower()).first():
            flash(f'Function "{function_name}" already exists.', 'danger')
        else:
            new_function = Function(name=function_name)
            db.session.add(new_function)
            db.session.commit()
            flash(f'Function "{function_name}" created successfully.', 'success')
        return redirect(url_for('manage_functions'))

    functions = Function.query.order_by(Function.name).all()
    
    # Get department names from the Department table
    departments_query = Department.query.order_by(Department.dept_name).all()
    departments = [d.dept_name for d in departments_query if d.dept_name and d.dept_name.strip()]
    return render_template('admin/functions.html', functions=functions, departments=departments)

@app.route('/admin/functions/edit/<int:id>', methods=['POST'])
@admin_required
def edit_function(id):
    function_to_edit = Function.query.get_or_404(id)
    new_name = request.form.get('name', '').strip()

    if not new_name:
        flash('Function name cannot be empty.', 'danger')
    else:
        existing_function = Function.query.filter(func.lower(Function.name) == new_name.lower()).first()
        if existing_function and existing_function.id != id:
            flash(f'Function "{new_name}" already exists.', 'danger')
        else:
            old_name = function_to_edit.name
            Log.query.filter_by(function=old_name).update({'function': new_name})
            function_to_edit.name = new_name
            db.session.commit()
            flash(f'Function updated from "{old_name}" to "{new_name}".', 'success')
    return redirect(url_for('manage_functions'))

@app.route('/admin/functions/delete/<int:id>', methods=['POST'])
@admin_required
def delete_function(id):
    function_to_delete = Function.query.get_or_404(id)
    if Log.query.filter_by(function=function_to_delete.name).first():
        flash(f'Cannot delete function "{function_to_delete.name}" because it is in use in logs. Please edit it instead.', 'danger')
    else:
        db.session.delete(function_to_delete)
        db.session.commit()
        flash(f'Function "{function_to_delete.name}" has been deleted.', 'success')
    return redirect(url_for('manage_functions'))

@app.route('/admin/create_employee', methods=['GET', 'POST'])
@admin_required
def create_employee():
    if request.method == 'POST':
        username = request.form.get('team_member', '').strip()
        employee_id = request.form.get('employee_id', '').strip()
        department = request.form.get('department')
        role = request.form.get('role')
        shift = request.form.get('shift')
        location = request.form.get('location')
        password = request.form.get('password')

        if not all([username, employee_id, department, role, shift, location, password]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('create_employee'))

        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return redirect(url_for('create_employee'))

        existing_user = User.query.filter(
            (func.lower(User.username) == username.lower()) | (User.employee_id == employee_id)
        ).first()
        if existing_user:
            flash(f'Employee with name "{username}" or ID "{employee_id}" already exists.', 'danger')
            return redirect(url_for('create_employee'))

        hashed_password = generate_password_hash(password)
        
        new_user = User(
            username=username,
            employee_id=employee_id,
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

    departments = [d.dept_name for d in Department.query.order_by(Department.dept_name).all()]

    return render_template('admin/create_employee.html', departments=departments)

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
            'Employee ID': user.employee_id or 'N/A',
            'Team Member': user.username,
            'Department': user.department,
            'Shift': user.shift,
            'Location': user.location,
            'Status': status,
            'Last_Login': last_date.strftime('%Y-%m-%d') if last_date else 'N/A'
        })
    return render_template('admin/view_employees.html', 
                           employees=employees)

@app.route('/admin/production_report')
@admin_required
def production_report():
    from calendar import monthrange

    # --- Date-wise Production Data ---
    today = datetime.utcnow()
    # Allow overriding month/year via query params for filtering
    try:
        year = int(request.args.get('year', today.year))
        month = int(request.args.get('month', today.month))
        # Basic validation
        if not (1 <= month <= 12):
            month = today.month
        if not (2020 <= year <= today.year):
            year = today.year
    except (ValueError, TypeError):
        year = today.year
        month = today.month

    # Get number of days in the selected month
    num_days = monthrange(year, month)[1]
    days_in_month = list(range(1, num_days + 1))

    # Get all departments
    departments = Department.query.order_by(Department.dept_name).all()
    dept_names = [d.dept_name for d in departments if d.dept_name]

    # Query for logs in the selected month
    daily_counts_query = db.session.query(
        Log.department,
        extract('day', Log.date).label('day'),
        func.count(Log.id).label('count')
    ).filter(
        extract('year', Log.date) == year,
        extract('month', Log.date) == month,
        Log.department.in_(dept_names)
    ).group_by(Log.department, extract('day', Log.date)).all()

    # Process data into a pivot-table like structure
    data = {dept: {day: 0 for day in days_in_month} for dept in dept_names}
    for department, day, count in daily_counts_query:
        if department in data and day in data[department]:
            data[department][int(day)] = count

    # Prepare final list for template, including totals
    production_by_date = []
    for dept_name, daily_counts in data.items():
        production_by_date.append({
            'department': dept_name,
            'days': daily_counts,
            'total': sum(daily_counts.values())
        })

    month_name = datetime(year, month, 1).strftime('%B')
    years = list(range(today.year, 2019, -1))
    months = {i: datetime(2000, i, 1).strftime('%B') for i in range(1, 13)}
    
    return render_template('admin/production_report.html', production_by_date=production_by_date, days_in_month=days_in_month, month_name=month_name, selected_year=year, selected_month=month, years=years, months=months)

@app.route('/admin/production_by_department')
@admin_required
def production_by_department():
    # Get all departments from the master Department table
    departments = Department.query.order_by(Department.dept_name).all()

    # Get total logs per department in a single query
    dept_logs_query = db.session.query(
        Log.department,
        func.count(Log.id)
    ).group_by(Log.department).all()
    dept_logs_map = dict(dept_logs_query)

    # Efficiently get the top function for each department using a window function
    # This avoids making a query for each department inside a loop (N+1 problem)
    
    # Subquery to count functions per department
    log_counts_subquery = db.session.query(
        Log.department,
        Log.function,
        func.count(Log.id).label('function_count')
    ).filter(Log.department.isnot(None)).group_by(Log.department, Log.function).subquery()

    # Window function to rank functions within each department
    ranked_logs_subquery = db.session.query(
        log_counts_subquery.c.department,
        log_counts_subquery.c.function,
        func.row_number().over(
            partition_by=log_counts_subquery.c.department,
            order_by=log_counts_subquery.c.function_count.desc()
        ).label('rn')
    ).subquery()

    # Select only the top-ranked function (rn=1) for each department
    top_functions_query = db.session.query(
        ranked_logs_subquery.c.department,
        ranked_logs_subquery.c.function
    ).filter(ranked_logs_subquery.c.rn == 1).all()
    top_functions_map = dict(top_functions_query)

    department_stats = []
    for dept in departments:
        dept_name = dept.dept_name
        department_stats.append({
            'department': dept_name,
            'total_logs': dept_logs_map.get(dept_name, 0),
            'top_function': top_functions_map.get(dept_name)
        })

    return render_template('admin/production_by_department.html', department_stats=department_stats)

@app.route('/admin/team_member_performance')
@admin_required
def team_member_performance():
    # Get all employee users
    users = User.query.filter(User.role == 'employee').order_by(User.username).all()
    
    # Get performance stats in one subquery
    performance_query = db.session.query(
        Log.team_member,
        func.count(Log.id).label('total_logs'),
        func.count(func.distinct(Log.date)).label('active_days'),
        func.max(Log.date).label('last_log_date')
    ).group_by(Log.team_member).subquery()

    # Create a dictionary for easy lookup
    performance_stats = {
        row.team_member: {
            'total_logs': row.total_logs,
            'active_days': row.active_days,
            'last_log_date': row.last_log_date,
            'avg_per_day': (row.total_logs / row.active_days) if row.active_days > 0 else 0
        }
        for row in db.session.query(performance_query).all()
    }

    performance_data = []
    for user in users:
        stats = performance_stats.get(user.username, {'total_logs': 0, 'avg_per_day': 0, 'last_log_date': None})
        performance_data.append({'username': user.username, 'department': user.department, **stats})

    return render_template('admin/team_member_performance.html', performance_data=performance_data)

@app.route('/admin/tracker')
@admin_required
def track_employee():
    users = User.query.order_by(User.username).all()
    employees = [user.username for user in users]

    selected_employee = request.args.get('employee')
    page = request.args.get('page', 1, type=int)
    
    query = Log.query
    if selected_employee:
        query = query.filter_by(team_member=selected_employee)
        
    # Add pagination to the query
    pagination = query.order_by(Log.id.desc()).paginate(page=page, per_page=100, error_out=False)
    logs_to_display = pagination.items

    # Calculate Statistics if an employee is selected, using SQL aggregations
    stats = {
        'avg_per_day': 0,
        'top_function': 'N/A',
        'function_breakdown': {}
    }

    if selected_employee:
        # 1. Function Breakdown and Top Function (SQL)
        function_breakdown_query = db.session.query(
            Log.function, 
            func.count(Log.id)
        ).filter(
            Log.team_member == selected_employee
        ).group_by(
            Log.function
        ).order_by(
            func.count(Log.id).desc()
        ).all()

        if function_breakdown_query:
            stats['function_breakdown'] = dict(function_breakdown_query)
            stats['top_function'] = function_breakdown_query[0][0]

        # 2. Average files per day (SQL)
        daily_counts_subquery = db.session.query(
            func.count(Log.id).label('daily_count')
        ).filter(Log.team_member == selected_employee).group_by(Log.date).subquery()

        avg_per_day_query = db.session.query(func.avg(daily_counts_subquery.c.daily_count)).scalar()
        
        if avg_per_day_query is not None:
            stats['avg_per_day'] = round(float(avg_per_day_query), 2)

    return render_template('admin/track_employee.html', employees=employees, logs=logs_to_display, selected_employee=selected_employee, stats=stats, pagination=pagination)

@app.route('/admin/tracker/export')
@admin_required
def export_tracker_data():
    selected_employee = request.args.get('employee')
    if not selected_employee:
        flash('Please select an employee to export data.', 'warning')
        return redirect(url_for('track_employee'))

    # Fetch logs for the selected employee, ordered by date
    logs = Log.query.filter_by(team_member=selected_employee).order_by(Log.date.asc()).all()

    if not logs:
        flash(f'No logs found for {selected_employee} to export.', 'info')
        return redirect(url_for('track_employee', employee=selected_employee))

    # Create a pandas DataFrame from the log data
    df = pd.DataFrame(
        [
            {
                "Date": log.date,
                "Function": log.function,
                "File Number": log.file_number,
                "Status": log.status,
                "Department": log.department,
                "Comments": log.comments,
            }
            for log in logs
        ]
    )

    # --- Create Excel Data in Memory ---
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Detailed Logs
        df.to_excel(writer, sheet_name='Detailed Logs', index=False)

        # Sheet 2: Date-wise file count (Daily Summary)
        if 'Date' in df.columns:
            df_date_summary = df.groupby('Date').size().reset_index(name='Files Count')
            df_date_summary.to_excel(writer, sheet_name='Daily Summary', index=False)

        # Sheet 3: Function distribution
        if 'Function' in df.columns:
            df_func_dist = df['Function'].value_counts().reset_index()
            df_func_dist.columns = ['Function', 'Count']
            df_func_dist.to_excel(writer, sheet_name='Function Distribution', index=False)

    output.seek(0)

    # --- Serve the file for download ---
    filename = f"{selected_employee}_Tracker_Report_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    return Response(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

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

        all_functions = [f.name for f in Function.query.order_by(Function.name).all()]
        columns = all_functions + ["Total Hours"] # Total Hours seems unused, keeping for compatibility

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

    if not Function.query.first():
        print("Populating functions table...")
        default_functions = [
            "VI 3D Scan Pro", "VI 3D Desktop Pro", "Full Review", "Full Revision",
            "Short Review", "Short Revision", "VI Second Review",
            "Digital Operations - Sourcing", "Full Reports", "QCF (Underwriter Queue)",
            "Full Review (CI Abridged)", "CMP Client Import", "Text Followup", "ACR",
            "DNU Checklist Update", "PDC Compliance", "Meetings/Training"
        ]
        for func_name in default_functions:
            db.session.add(Function(name=func_name))
        db.session.commit()
        print("Functions table populated.")

    if not Department.query.first():
        print("Populating department table...")
        default_departments = [
            'Alternative Products',
            'Assigning',
            'Bluebird QC',
            'Client Services',
            'Digital',
            'Management',
            'Quality Control',
            'Staff Direct',
            'Training',
            'Vendor Relations'
        ]
        for dept_name in default_departments:
            db.session.add(Department(dept_name=dept_name))
        db.session.commit()
        print("Department table populated.")

@app.cli.command("import-data")
def import_data_command():
    """Deletes and re-imports users from the production report, then imports other data."""
    new_report_file = os.path.join(BASE_DIR, 'Production & Performance Report Till  May 28th 2026.xlsx')
    if not os.path.exists(new_report_file):
        print(f"Report file not found: {new_report_file}. Skipping user import.")
        return

    print(f"--- Starting User Import from: {new_report_file} ---")
    try:
        # 1. Read both sheets from the Excel file
        xls = pd.ExcelFile(new_report_file)
        if 'Team Member Performance' not in xls.sheet_names:
            print("Error: Sheet 'Team Member Performance' not found in the Excel file. Aborting.")
            print(f"Available sheets: {xls.sheet_names}")
            return
        if 'Raw Data' not in xls.sheet_names:
            print("Error: Sheet 'Raw Data' not found in the Excel file. Aborting.")
            print(f"Available sheets: {xls.sheet_names}")
            return
            
        df_performance = pd.read_excel(xls, sheet_name='Team Member Performance')
        df_raw = pd.read_excel(xls, sheet_name='Raw Data')

        # Clean column names
        df_performance.columns = df_performance.columns.str.strip()
        df_raw.columns = df_raw.columns.str.strip()

        # 2. Check for required columns in the performance sheet
        required_cols = ['Branch', 'Team Member (First Last)', 'Employee ID', 'Shift']
        if not all(col in df_performance.columns for col in required_cols):
            print(f"Error: 'Team Member Performance' sheet is missing one of the required columns: {required_cols}.")
            print(f"Columns found: {list(df_performance.columns)}")
            return

        # 3. Create a department mapping from the raw data sheet
        department_map = {}
        # Corrected column names for department mapping
        raw_team_member_col = 'Team Member (First Last)'
        raw_dept_col = 'Department'
        if raw_team_member_col in df_raw.columns and raw_dept_col in df_raw.columns:
            df_departments = df_raw[[raw_team_member_col, raw_dept_col]].dropna(subset=[raw_team_member_col, raw_dept_col])
            df_departments[raw_team_member_col] = df_departments[raw_team_member_col].str.strip()
            department_map = df_departments.drop_duplicates(subset=[raw_team_member_col], keep='first').set_index(raw_team_member_col)[raw_dept_col].to_dict()
            print(f"Created a mapping for {len(department_map)} departments from 'Raw Data' sheet.")
        else:
            print(f"Warning: 'Raw Data' sheet is missing '{raw_team_member_col}' or '{raw_dept_col}' columns. Departments will not be imported.")
            print(f"Columns found in 'Raw Data' sheet: {list(df_raw.columns)}")

        # 4. Filter for Vadodara branch
        df_vadodara = df_performance[df_performance['Branch'] == 'Vadodara'].copy()
        print(f"Found {len(df_vadodara)} users for 'Vadodara' branch.")

        # 5. Delete existing users (preserving the 'admin' user)
        num_deleted = User.query.filter(User.role != 'admin').delete()
        db.session.commit()
        print(f"Deleted {num_deleted} existing non-admin users.")

        # 6. Iterate and create new users
        users_added = 0
        for _, row in df_vadodara.iterrows():
            username = str(row.get('Team Member (First Last)', '')).strip()
            employee_id = str(row.get('Employee ID', '')).strip()

            if not username or not employee_id or username.lower() in ['nan', '']:
                continue
            
            department = department_map.get(username)
            hashed_password = generate_password_hash('password')

            new_user = User(username=username, employee_id=employee_id, password=hashed_password, role='employee', department=department, shift=str(row.get('Shift', '')).strip(), location='Vadodara', created_at=datetime.now())
            db.session.add(new_user)
            users_added += 1
        
        db.session.commit()
        print(f"--- Successfully imported {users_added} new users. ---")

        # --- Import Log Data ---
        print("\n--- Starting Log Data Import from 'Raw Data' sheet ---")
        # 1. Drop and recreate the Log table to ensure the schema is up-to-date with the model.
        # This is a more forceful drop to handle potential stale schema issues.
        print("Synchronizing Log table schema...")
        db.session.execute(text('DROP TABLE IF EXISTS log CASCADE;'))
        db.session.commit()
        db.create_all() # Recreates the table based on the current model definition
        print("Log table schema is up-to-date.")

        # 2. Check for required columns in the raw data sheet
        # Corrected required column names for logs
        required_log_cols = ['Team Member (First Last)', 'Date (mm/dd/yy)', 'Function']
        if not all(col in df_raw.columns for col in required_log_cols):
            print(f"Error: 'Raw Data' sheet is missing one of the required columns for logs: {required_log_cols}.")
            print(f"Columns found: {list(df_raw.columns)}")
            return

        # 3. Replace pandas' NaT/NaN with None for database compatibility
        df_raw_logs = df_raw.where(pd.notnull(df_raw), None)
        
        # 4. Iterate and create new Log objects
        logs_to_add = []
        for _, row in df_raw_logs.iterrows():
            # Basic validation: Skip rows without a team member or date
            # Corrected column names for validation
            if not row['Team Member (First Last)'] or not row['Date (mm/dd/yy)']:
                continue

            # Convert date, handling potential errors
            try:
                # Corrected date column name
                log_date = pd.to_datetime(row['Date (mm/dd/yy)']).date()
            except (ValueError, TypeError):
                print(f"Skipping row for team member '{row['Team Member (First Last)']}' due to invalid date: {row['Date (mm/dd/yy)']}")
                continue

            # Create the Log object, using .get() for optional columns and correct names
            new_log = Log(
                team_member=row.get('Team Member (First Last)'),
                function=row.get('Function'),
                date=log_date,
                # Corrected file number column name (double space)
                file_number=str(row.get('File  Number')) if row.get('File  Number') else None,
                # Explicitly convert status to string to handle mixed types (e.g., 0 and "Approved") from Excel
                status=str(row.get('Status')) if pd.notna(row.get('Status')) else None,
                # Corrected escalation reason column name and ensure it's a string
                tier1_escalation_reason=str(row.get('Escalation Reason')) if pd.notna(row.get('Escalation Reason')) else None,
                # IM Escalation is not in the source file
                im_escalation_reason=None,
                department=row.get('Department'),
                # Comments is not in the source file
                comments=None,
                count=str(row.get('Count')) if row.get('Count') else None,
                bucket=row.get('Bucket'),
                time=str(row.get('Time')) if row.get('Time') else None,
                production_task=row.get('Production Task'),
                month=row.get('Month')
            )
            logs_to_add.append(new_log)
        
        # 5. Bulk add to session and commit in batches to avoid timeouts/memory issues
        if logs_to_add:
            batch_size = 500  # Process 500 records at a time
            total_imported = 0
            for i in range(0, len(logs_to_add), batch_size):
                batch = logs_to_add[i:i + batch_size]
                db.session.bulk_save_objects(batch)
                db.session.commit()
                total_imported += len(batch)
                print(f"Committed batch {i // batch_size + 1}, imported {total_imported}/{len(logs_to_add)} logs...")
            
            print(f"--- Successfully imported {total_imported} new logs. ---")
        else:
            print("No valid log entries found to import.")

    except Exception as e:
        db.session.rollback()
        print(f"An error occurred during data import: {e}")

@app.cli.command("count-rows")
def count_rows_command():
    """Counts and prints the number of rows in key tables."""
    try:
        log_count = Log.query.count()
        user_count = User.query.count()
        print("\n--- Database Row Counts ---")
        print(f"Log table:    {log_count} rows")
        print(f"User table:   {user_count} rows")
        print("---------------------------\n")
    except Exception as e:
        print(f"An error occurred while counting rows: {e}")

init_dashboard(app)
init_daily_dashboard(app)

if __name__ == '__main__':
    print(f"Template folder set to: {os.path.join(BASE_DIR, 'templates')}")
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.environ.get("PORT", 5000))

    # Use the dynamic port and bind to 0.0.0.0
    app.run(host="0.0.0.0", port=port, debug=debug_mode)

