<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Update Work Log</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --bg-color: #f4f6f9;
            --text-color: #333;
            --sidebar-bg: #ffffff;
            --sidebar-border: #dee2e6;
            --card-bg: #ffffff;
            --card-border: #dee2e6;
            --item-hover: #e9ecef;
            --text-muted: #6c757d;
        }
        [data-theme="dark"] {
            --bg-color: #121212;
            --text-color: #ffffff;
            --sidebar-bg: #1e1e1e;
            --sidebar-border: #333;
            --card-bg: #1e1e1e;
            --card-border: #333;
            --item-hover: #2c2c2c;
            --text-muted: #adb5bd;
        }
        [data-theme="dark"] .form-control-plaintext {
            color: var(--text-color);
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            overflow-x: hidden;
            transition: background-color 0.3s, color 0.3s;
        }
        .brand-green { color: #28a745; }
        .brand-blue { color: #0d6efd; }
        
        #wrapper {
            display: flex;
            width: 100%;
            min-height: 100vh;
        }
        
        #sidebar-wrapper {
            min-height: 100vh;
            width: 260px;
            background-color: var(--sidebar-bg);
            border-right: 1px solid var(--sidebar-border);
            display: flex;
            flex-direction: column;
        }
        
        .sidebar-heading {
            padding: 1.5rem;
            font-size: 1.2rem;
            text-align: center;
            border-bottom: 1px solid var(--sidebar-border);
        }
        
        .list-group-item {
            background-color: transparent;
            color: var(--text-muted);
            border: none;
            padding: 1rem 1.5rem;
            font-weight: 500;
            transition: all 0.3s;
            text-decoration: none;
            display: block;
        }
        
        .list-group-item:hover, .list-group-item.active {
            background-color: var(--item-hover);
            color: var(--text-color);
            border-left: 4px solid #0d6efd;
        }
        
        .list-group-item i {
            width: 25px;
            text-align: center;
            margin-right: 10px;
        }
        
        #page-content-wrapper {
            flex: 1;
            padding: 30px;
        }
        
        .card {
            background-color: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            transition: transform 0.3s;
            color: var(--text-color);
        }
        
        .theme-toggle {
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(128, 128, 128, 0.2);
            border: none;
            border-radius: 50%;
            width: 45px;
            height: 45px;
            cursor: pointer;
            color: var(--text-color);
            font-size: 1.2rem;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            backdrop-filter: blur(5px);
            z-index: 1000;
        }
        .theme-toggle:hover {
            background: rgba(128, 128, 128, 0.4);
            transform: rotate(15deg);
        }
        
        table { color: var(--text-color); }
        .table>:not(caption)>*>* {
            background-color: transparent;
            color: var(--text-color);
            border-color: var(--card-border);
        }
    </style>
</head>
<body>
    <button class="theme-toggle" onclick="toggleTheme()" title="Toggle Theme"><i class="fas fa-moon"></i></button>

    <div id="wrapper">
        <!-- Sidebar -->
        <div id="sidebar-wrapper">
            <div class="sidebar-heading">
                <img src="/logo.png" alt="Logo" height="30" class="me-2"><span class="brand-green">Class</span><span class="brand-blue">Valuation</span>
            </div>
            <div class="list-group list-group-flush mt-3">
                <a href="/employee/dashboard" class="list-group-item">
                    <i class="fas fa-tachometer-alt"></i> Dashboard
                </a>
                <a href="/summary" class="list-group-item">
                    <i class="fas fa-chart-bar"></i> View Work Summary
                </a>
                <a href="/employee/update" class="list-group-item active">
                    <i class="fas fa-edit"></i> Update Work Log
                </a>
                <div style="margin-top: auto;">
                    <a href="{{ url_for('logout') }}" class="list-group-item text-danger mb-4">
                        <i class="fas fa-sign-out-alt"></i> Log Out
                    </a>
                </div>
            </div>
        </div>

        <!-- Page Content -->
        <div id="page-content-wrapper">
            <div class="container-fluid">
                <h2 class="mb-4">Update Work Log</h2>
                
                {% with messages = get_flashed_messages(with_categories=true) %}
                  {% if messages %}
                    {% for category, message in messages %}
                      <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                      </div>
                    {% endfor %}
                  {% endif %}
                {% endwith %}

                <div class="card shadow mb-4">
                    <div class="card-header bg-transparent border-secondary">
                        <i class="fas fa-edit me-2"></i>Log New Work
                    </div>
                    <div class="card-body">
                        <form method="POST" action="/employee/update">
                            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                            <div class="row g-3">
                                <div class="col-md-6">
                                    <label class="form-label">Team Member</label>
                                    <p class="form-control-plaintext fw-bold fs-5">{{ employee_name }}</p>
                                </div>
                                <div class="col-md-6">
                                    <label for="date" class="form-label">Date</label>
                                    <input type="date" class="form-control" id="date" name="date" required>
                                </div>
                                <div class="col-md-6">
                                    <label for="function" class="form-label">Function</label>
                                    <select class="form-select" id="function" name="function" required>
                                        <option value="" selected disabled>Select Function</option>
                                        <option value="VI 3D Scan Pro">VI 3D Scan Pro</option>
                                        <option value="VI 3D Desktop Pro">VI 3D Desktop Pro</option>
                                        <option value="Full Review">Full Review</option>
                                        <option value="Full Revision">Full Revision</option>
                                        <option value="Short Review">Short Review</option>
                                        <option value="Short Revision">Short Revision</option>
                                        <option value="VI Second Review">VI Second Review</option>
                                        <option value="Digital Operations - Sourcing">Digital Operations - Sourcing</option>
                                        <option value="Full Reports">Full Reports</option>
                                        <option value="QCF (Underwriter Queue)">QCF (Underwriter Queue)</option>
                                        <option value="Full Review (CI Abridged)">Full Review (CI Abridged)</option>
                                        <option value="CMP Client Import">CMP Client Import</option>
                                        <option value="Text Followup">Text Followup</option>
                                        <option value="ACR">ACR</option>
                                        <option value="DNU Checklist Update">DNU Checklist Update</option>
                                        <option value="PDC Compliance">PDC Compliance</option>
                                        <option value="Meetings/Training">Meetings/Training</option>
                                    </select>
                                </div>
                                <div class="col-md-6">
                                    <label for="department" class="form-label">Department</label>
                                    <input type="text" class="form-control" id="department" name="department" placeholder="e.g. Operations">
                                </div>
                                <div class="col-md-6">
                                    <label for="file_number" class="form-label">File Number</label>
                                    <input type="text" class="form-control" id="file_number" name="file_number" placeholder="Enter File Number">
                                </div>
                                <div class="col-md-6">
                                    <label for="status" class="form-label">Status</label>
                                    <select class="form-select" id="status" name="status">
                                        <option value="Completed">Completed</option>
                                        <option value="In Progress">In Progress</option>
                                        <option value="Pending">Pending</option>
                                    </select>
                                </div>
                                <div class="col-md-6">
                                    <label for="tier1_escalation" class="form-label">Tier 1 Escalation Reason</label>
                                    <input type="text" class="form-control" id="tier1_escalation" name="tier1_escalation">
                                </div>
                                <div class="col-md-6">
                                    <label for="im_escalation" class="form-label">IM Escalation Reason</label>
                                    <input type="text" class="form-control" id="im_escalation" name="im_escalation">
                                </div>
                                <div class="col-12">
                                    <label for="comments" class="form-label">Comments</label>
                                    <textarea class="form-control" id="comments" name="comments" rows="2"></textarea>
                                </div>
                                <div class="col-12 text-end">
                                    <button type="submit" class="btn btn-primary"><i class="fas fa-plus me-2"></i>Add Log</button>
                                </div>
                            </div>
                        </form>
                    </div>
                </div>

                <!-- Log Table -->
                <div class="card shadow">
                    <div class="card-header bg-transparent border-secondary">
                        <i class="fas fa-list me-2"></i>Recent Logs
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-hover">
                                <thead>
                                    <tr>
                                        <th>Date</th>
                                        <th>Team Member</th>
                                        <th>Function</th>
                                        <th>File Number</th>
                                        <th>Status</th>
                                        <th>Department</th>
                                        <th>Comments</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for log in logs %}
                                    <tr>
                                        <td>{{ log.date.strftime('%Y-%m-%d') if log.date }}</td>
                                        <td>{{ log.team_member }}</td>
                                        <td>{{ log.function }}</td>
                                        <td>{{ log.file_number }}</td>
                                        <td>{{ log.status }}</td>
                                        <td>{{ log.department }}</td>
                                        <td>{{ log.comments }}</td>
                                    </tr>
                                    {% else %}
                                    <tr>
                                        <td colspan="7" class="text-center py-3">No logs found.</td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    </div>

    <script>
        // Set default date to today
        document.addEventListener('DOMContentLoaded', () => {
            const dateInput = document.getElementById('date');
            if (dateInput) {
                const today = new Date().toISOString().split('T')[0];
                dateInput.value = today;
            }

            const savedTheme = localStorage.getItem('theme');
            if (savedTheme === 'dark') {
                document.body.setAttribute('data-theme', 'dark');
                document.querySelector('.theme-toggle i').classList.replace('fa-moon', 'fa-sun');
            }
        });

        function toggleTheme() {
            const body = document.body;
            const icon = document.querySelector('.theme-toggle i');
            if (body.getAttribute('data-theme') === 'dark') {
                body.removeAttribute('data-theme');
                icon.classList.replace('fa-sun', 'fa-moon');
                localStorage.setItem('theme', 'light');
            } else {
                body.setAttribute('data-theme', 'dark');
                icon.classList.replace('fa-moon', 'fa-sun');
                localStorage.setItem('theme', 'dark');
            }
        }
    </script>
</body>
</html>
