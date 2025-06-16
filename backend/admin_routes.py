from flask import Blueprint, render_template, request, redirect, url_for, session

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Basic hardcoded credentials for demonstration
        if username == 'admin' and password == 'password':
            session['admin_logged_in'] = True
            return redirect(url_for('admin.dashboard'))
        else:
            return "Invalid credentials", 401
    return render_template('admin_login.html')

@admin_bp.route('/dashboard')
def dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.login'))
    # Placeholder for user statistics
    user_stats = {
        'total_users': 100,
        'active_users': 75,
        'new_users_today': 5
    }
    return render_template('admin_dashboard.html', user_stats=user_stats)

@admin_bp.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin.login'))