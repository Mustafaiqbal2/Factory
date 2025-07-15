from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
import os

auth_bp = Blueprint('auth', __name__)

# Get password from environment variable for production security
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', "hunainrao123")

def login_required(f):
    """Decorator to require login for protected routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        
        if password == ADMIN_PASSWORD:
            session['logged_in'] = True
            session.permanent = True  # Keep session active
            flash('Successfully logged in!', 'success')
            
            # Redirect to the page they were trying to access, or dashboard
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.index'))
        else:
            flash('Invalid password. Please try again.', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))