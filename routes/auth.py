from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, session, make_response
from flask_login import login_user, logout_user, current_user
from models import db, User, CullyStatistics
from auth import login_required
from werkzeug.security import generate_password_hash, check_password_hash
from session_manager import session_manager
from datetime import datetime, timedelta
import time

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/welcome')
def welcome():
    """Welcome/Home page with Register and Log In buttons and live Cully statistics"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))
    
    # Get live Cully statistics with proper error handling
    try:
        # First ensure the table exists
        try:
            db.create_all()  # This will create missing tables including cully_statistics
        except Exception as create_error:
            current_app.logger.warning(f"Could not ensure tables exist: {create_error}")
        
        # Now try to get statistics
        cully_stats = CullyStatistics.get_current_statistics()
        
        # Check if we need to update statistics (once per day)
        should_update = True
        try:
            stats_record = CullyStatistics.query.first()
            if stats_record and stats_record.last_updated:
                time_since_update = datetime.utcnow() - stats_record.last_updated
                should_update = time_since_update > timedelta(hours=24)
        except Exception:
            # If query fails, we should update
            should_update = True
        
        # If needed, trigger background update (don't wait for it)
        if should_update:
            try:
                # Try to update synchronously with short timeout
                CullyStatistics.fetch_and_update_from_cully()
                cully_stats = CullyStatistics.get_current_statistics()
            except Exception as sync_error:
                current_app.logger.debug(f"Statistics sync failed: {sync_error}")
                # If sync fails, use cached/default data
                pass
                
    except Exception as e:
        current_app.logger.error(f"Error getting Cully statistics: {e}")
        # Use default values if database fails
        cully_stats = {
            'instruments': '22k',
            'engineers': '46',
            'experience': '600+',
            'plants': '250',
            'last_updated': None
        }
    
    return render_template('welcome.html', cully_stats=cully_stats)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        requested_role = request.form.get('requested_role', '')

        # Validation
        if not all([full_name, email, password, requested_role]):
            flash('All fields are required.', 'error')
            return render_template('register.html')

        if requested_role not in ['Engineer', 'Automation Manager', 'PM']:
            flash('Invalid role selection.', 'error')
            return render_template('register.html')

        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please use a different email.', 'error')
            return render_template('register.html')

        # Create new user
        user = User(
            full_name=full_name,
            email=email,
            requested_role=requested_role,
            status='Pending'
        )
        user.set_password(password)

        try:
            db.session.add(user)
            db.session.commit()
            return render_template('register_confirmation.html')
        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'error')
            return render_template('register.html')

    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        client_ip = request.remote_addr
        
        if not email or not password:
            flash('Email and password are required.', 'error')
            return render_template('login.html')

        try:
            user = User.query.filter_by(email=email).first()

            if user and user.check_password(password):
                # Check user status
                if user.status == 'Pending':
                    return render_template('pending_approval.html', user=user)
                elif user.status == 'Disabled':
                    flash('Your account has been disabled. Please contact an administrator.', 'error')
                    return render_template('login.html')
                elif user.status == 'Active':
                    # Create a new tracked session
                    session_id = session_manager.create_session(user.id)
                    
                    # Login the user with Flask-Login
                    login_user(user, remember=False, fresh=True)  # Don't remember user, mark as fresh
                    
                    # Additional session tracking
                    session['user_id'] = user.id  # Store user ID in session
                    session['authenticated'] = True  # Mark as authenticated
                    session['login_time'] = time.time()  # Track login time
                    session.permanent = False  # Don't make session permanent
                    
                    flash('Login successful!', 'success')
                    current_app.logger.info(f"User {user.email} logged in with session {session_id}")

                    # Role-based dashboard redirect
                    if user.role == 'Admin':
                        return redirect(url_for('dashboard.admin'))
                    elif user.role == 'Engineer':
                        return redirect(url_for('dashboard.engineer'))
                    elif user.role == 'Automation Manager':
                        return redirect(url_for('dashboard.automation_manager'))
                    elif user.role == 'PM':
                        return redirect(url_for('dashboard.pm'))
                    else:
                        return redirect(url_for('dashboard.home'))
                else:
                    flash('Account status unknown. Please contact an administrator.', 'error')
                    return render_template('login.html')
            else:
                flash('Invalid email or password', 'error')
                return render_template('login.html')

        except Exception as e:
            current_app.logger.error(f"Login error: {e}")
            flash('System temporarily unavailable. Please try again later.', 'error')
            return render_template('login.html')

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """User logout - fully clear session to prevent back button access"""
    # Get session ID before clearing
    session_id = session.get('session_id')
    user_email = current_user.email if current_user.is_authenticated else 'unknown'
    
    # Revoke the session on server side FIRST
    session_manager.revoke_session(session_id)
    current_app.logger.info(f"Session {session_id} revoked for user {user_email}")
    
    # Clear Flask-Login session
    logout_user()
    
    # Clear ALL session data multiple times to ensure it's gone
    session.clear()
    session.permanent = False
    
    # Double-clear critical keys
    for key in ['user_id', 'authenticated', 'session_id', 'login_time', 'last_activity', 'created_at']:
        session.pop(key, None)
    
    # Force new session generation
    session.modified = True
    session.new = True
    
    flash('You have been logged out successfully.', 'success')
    
    # Create response with aggressive cache control
    response = make_response(redirect(url_for('auth.welcome')))
    
    # Maximum aggressive cache prevention headers
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0, s-maxage=0, proxy-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['Clear-Site-Data'] = '"cache", "cookies", "storage"'  # Clear everything
    
    # Clear ALL possible cookies with various configurations
    cookie_configs = [
        {'name': 'session', 'domain': None},
        {'name': 'sat_session', 'domain': None},
        {'name': 'csrf_token', 'domain': None},
        {'name': current_app.config.get('SESSION_COOKIE_NAME', 'session'), 'domain': None},
        {'name': 'remember_token', 'domain': None},
    ]
    
    for config in cookie_configs:
        # Clear with multiple approaches
        response.set_cookie(config['name'], '', expires=0, max_age=0, path='/',
                          httponly=True, samesite='Lax', secure=False)
        response.set_cookie(config['name'], 'deleted', expires=0, max_age=0, path='/',
                          httponly=True, samesite='Lax', secure=False)
    
    return response

@auth_bp.route('/pending')
def pending_approval():
    """Pending approval page"""
    return render_template('pending_approval.html')

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password - reset user password"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email:
            flash('Email is required.', 'error')
            return render_template('forgot_password.html')

        user = User.query.filter_by(email=email).first()

        if user:
            # For demo purposes, set a default password
            # In production, you'd send an email with reset link
            user.set_password('newpassword123')
            try:
                db.session.commit()
                flash(f'Password reset for {email}. New password: newpassword123', 'success')
                return redirect(url_for('auth.login'))
            except Exception as e:
                db.session.rollback()
                flash('Password reset failed. Please try again.', 'error')
        else:
            # Don't reveal if email exists for security
            flash('If this email exists, a password reset has been sent.', 'info')

    return render_template('forgot_password.html')

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """Reset password using token"""
    token = request.args.get('token')
    if not token:
        flash('Invalid or missing reset token.', 'error')
        return redirect(url_for('auth.forgot_password'))

    user = User.verify_reset_token(token)
    if not user:
        flash('Invalid or expired reset token.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not password or len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('reset_password.html', token=token)

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('reset_password.html', token=token)

        user.password_hash = generate_password_hash(password)
        try:
            db.session.commit()
            flash('Your password has been reset successfully. You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while resetting your password.', 'error')
            return render_template('reset_password.html', token=token)

    return render_template('reset_password.html', token=token)

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change user password"""
    try:
        from models import Notification
        unread_count = Notification.query.filter_by(
            user_email=current_user.email,
            read=False
        ).count()
    except Exception as e:
        current_app.logger.warning(f"Could not get unread count: {e}")
        unread_count = 0

    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # Validate current password
        if not current_user.check_password(current_password):
            flash('Current password is incorrect', 'error')
            return render_template('change_password.html', unread_count=unread_count)

        # Validate new password
        if new_password != confirm_password:
            flash('New passwords do not match', 'error')
            return render_template('change_password.html', unread_count=unread_count)

        if len(new_password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return render_template('change_password.html', unread_count=unread_count)

        try:
            # Update password
            current_user.set_password(new_password)
            db.session.commit()

            flash('Password changed successfully', 'success')
            return redirect(url_for('dashboard.home'))
        except Exception as e:
            current_app.logger.error(f"Error changing password: {e}")
            flash('An error occurred while changing password', 'error')
            return render_template('change_password.html', unread_count=unread_count)

    return render_template('change_password.html', unread_count=unread_count)
