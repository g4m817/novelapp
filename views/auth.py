from flask import Blueprint, session, current_app, flash, render_template, request, redirect, url_for
from models import User, Role, db
from flask_jwt_extended import create_access_token, decode_token
from helpers import is_unauthenticated, is_valid_password, generate_verification_token, send_verification_email, send_password_reset_email
from datetime import datetime, timedelta

bp = Blueprint('auth_views', __name__)

@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """
	Handles the password reset request for users.
    
    This function processes a POST request to initiate the password reset 
    process. It retrieves the email from the form, checks if a user with 
    that email exists, and if so, generates a password reset token and 
    sends a reset email. If the email is not found, it flashes an error 
    message. On successful email dispatch, it redirects the user to the 
    login page.
    
    Returns:
        str: Renders the 'forgot_password.html' template for GET requests 
        or redirects to the login page after processing a POST request.
    
    Raises:
        Flash: Displays messages to the user based on the outcome of the 
        password reset request.
    """
    if request.method == "POST":
        email = request.form.get("email")
        user = User.query.filter_by(email=email).first()
        if not user:
            flash("Email address not found.")
            return redirect(url_for("auth_views.forgot_password"))
        reset_token = create_access_token(
            identity=str(user.id),
            expires_delta=timedelta(hours=24),
            additional_claims={"action": "reset_password"}
        )
        send_password_reset_email(user.email, reset_token, user.username)
        flash("A password reset link has been sent to your email.")
        return redirect(url_for("auth_views.login"))
    return render_template("auth/forgot_password.html")

@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """
	Resets the user's password using a provided token.
    
    This function decodes the provided token to verify the password reset action and the associated user. If the token is valid and the user exists, it processes the new password submission. If the password meets the policy requirements, it updates the user's password in the database. Otherwise, it provides appropriate feedback to the user.
    
    Args:
        token (str): The password reset token sent to the user.
    
    Returns:
        Response: A redirect to the appropriate page based on the outcome of the password reset process or renders the password reset template if the request method is GET.
    
    Raises:
        Exception: If the token is invalid or has expired, an error message is flashed and the user is redirected to the forgot password page.
    """
    try:
        data = decode_token(token)
        if data.get("action") != "reset_password":
            flash("Invalid password reset token.")
            return redirect(url_for("auth_views.login"))
        user_id = data.get("sub")
        user = User.query.get(user_id)
        if not user:
            flash("User not found.")
            return redirect(url_for("auth_views.register"))
    except Exception as e:
        flash("The password reset link is invalid or has expired.")
        return redirect(url_for("auth_views.forgot_password"))
    
    if request.method == "POST":
        new_password = request.form.get("password")
        if not is_valid_password(new_password):
            flash("Password must meet the policy requirements.")
            return redirect(url_for("auth_views.reset_password", token=token))
        user.set_password(new_password)
        db.session.commit()
        flash("Your password has been reset. You may now log in.")
        return redirect(url_for("auth_views.login"))
    
    return render_template("auth/reset_password.html", token=token)

@bp.route('/register', methods=['GET', 'POST'])
@is_unauthenticated
def register():
    """
	Registers a new user in the application.
    
    This function handles both GET and POST requests for user registration. 
    If registration is disabled, it renders a disabled registration page. 
    On a POST request, it validates the provided username, email, and password, 
    checks for existing users, and creates a new user if all validations pass. 
    A verification email is sent to the user upon successful registration.
    
    Returns:
        Response: 
            - On GET request: Renders the registration form.
            - On POST request: 
                - If registration is disabled: Renders a disabled registration page with a 503 status.
                - If username already exists: Redirects to the registration page with a flash message.
                - If email already exists: Redirects to the registration page with a flash message.
                - If password is invalid: Redirects to the registration page with a flash message.
                - If user is successfully registered: Redirects to the login page with a success message.
    """
    if current_app.config["REGISTRATION_DISABLED"]:
        return render_template("auth/registration_disabled.html", message="Registration is temporarily closed."), 503
    if request.method == "POST":
        username = request.form.get("username").lower()
        password = request.form.get("password")
        email = request.form.get("email")

        if User.query.filter_by(username=username).first():
            flash("Username already exists")
            return redirect(url_for("auth_views.register"))
        if User.query.filter_by(email=email).first():
            flash("Email already exists")
            return redirect(url_for("auth_views.register"))
        
        if not is_valid_password(password):
            flash("Password must be at least 8 characters long, include both uppercase and lowercase letters, at least one digit, and one special character.")
            return redirect(url_for("auth_views.register"))
        
        default_role = Role.query.filter_by(name="user").first()
        if not default_role:
            flash("Unknown error occurred.")
            return redirect(url_for("auth_views.register"))
        
        user = User(username=username, email=email, role=default_role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        token = generate_verification_token(user)
        send_verification_email(user.email, token, user.username)
        flash("Registration successful! Please check your email to verify your account.")
        return redirect(url_for("auth_views.login"))
    return render_template("auth/register.html")

@bp.route('/login', methods=['GET', 'POST'])
@is_unauthenticated
def login():
    """
	Handles user login functionality.
    
    This function processes login requests. If the request method is POST, it retrieves the username and password from the form. It checks if the user exists, verifies their account status, and handles failed login attempts. If the credentials are correct, it logs the user in, sets a session cookie, and redirects them to the dashboard. If the login fails, it provides appropriate feedback and redirects back to the login page.
    
    Args:
        None
    
    Returns:
        Response: A redirect response to the dashboard upon successful login, or a redirect back to the login page with flash messages for errors.
    """
    if request.method == "POST":
        username = request.form.get("username").lower()
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        now = datetime.utcnow()
        
        if user:
            if not user.is_verified:
                flash("Please verify your account")
                return redirect(url_for("auth_views.login", username=user.username))
            if user.last_failed_attempt and (now - user.last_failed_attempt > timedelta(hours=24)):
                user.failed_attempts = 0
                db.session.commit()

            if user.is_locked or (user.locked_until and now < user.locked_until):
                flash("Your account is locked. Please contact support or try again later.")
                return redirect(url_for("auth_views.login"))
            
            if user.check_password(password):
                user.failed_attempts = 0
                user.last_failed_attempt = None
                user.locked_until = None

                user_ip = request.headers.get('CF-Connecting-IP', request.remote_addr)
                user.last_login_ip = user_ip

                db.session.commit()
                
                session['last_login_ip'] = request.remote_addr

                access_token = create_access_token(identity=str(user.id))
                resp = redirect(url_for('news'))
                resp.set_cookie("access_token", access_token)
                return resp
            else:
                user.failed_attempts += 1
                user.last_failed_attempt = now
                if user.failed_attempts >= 5:
                    user.locked_until = now + timedelta(minutes=15)
                    flash("Your account has been locked for 15 minutes due to too many failed login attempts.")
                else:
                    flash("Login Failed. Please check your credentials.")
                db.session.commit()
                return redirect(url_for("auth_views.login"))
        else:
            flash("Login Failed")
            return redirect(url_for("auth_views.login"))
    
    return render_template("auth/login.html")