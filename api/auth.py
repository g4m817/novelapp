from flask import Blueprint, flash, request, redirect, url_for
from models import User, db
from flask_jwt_extended import decode_token
from helpers import is_unauthenticated, is_authenticated, generate_verification_token, send_verification_email

bp = Blueprint('auth', __name__)

@bp.route('/resend-verification', methods=['GET'])
@is_unauthenticated
def resend_verification():
    """
	Resend a verification email to the user.
    
    This function retrieves the username from the request arguments, checks if the user exists, 
    generates a new verification token, and sends a verification email to the user's registered 
    email address. If the username is not provided or the user is not found, it flashes an error 
    message and redirects to the login page.
    
    Returns:
        Redirect: A redirect to the login page after attempting to resend the verification email.
    
    Raises:
        Flash: Displays messages to the user if no username is provided or if the user is not found.
    """
    username = request.args.get("username")
    if not username:
        flash("No username provided.")
        return redirect(url_for("auth_views.login"))
    
    user = User.query.filter_by(username=username).first()
    if not user:
        flash("User not found.")
        return redirect(url_for("auth_views.login"))
    
    token = generate_verification_token(user)
    send_verification_email(user.email, token, username)
    flash("A new verification email has been sent. Please check your inbox.")
    return redirect(url_for("auth_views.login"))

@bp.route('/verify-email/<token>', methods=['GET'])
def verify_email(token):
    """
	Verify the email address of a user using a verification token.
    
    This function decodes the provided token to extract user information and 
    verifies the user's email address. If the token is valid and corresponds 
    to a user, the user's verification status is updated. In case of an 
    invalid token or user not found, appropriate messages are flashed and 
    the user is redirected to the login or registration page.
    
    Args:
        token (str): The verification token sent to the user's email.
    
    Returns:
        Response: A redirect response to the appropriate page based on the 
        verification outcome.
    """
    try:
        data = decode_token(token)
        if data.get("action") != "verify_email":
            flash("Invalid verification token.")
            return redirect(url_for("auth_views.login"))
        user_id = data.get("sub")
        user = User.query.get(user_id)
        if not user:
            flash("User not found.")
            return redirect(url_for("auth_views.register"))
        user.is_verified = True
        db.session.commit()
        flash("Email verified successfully! You may now log in.")
        return redirect(url_for("auth_views.login"))
    except Exception as e:
        flash("The verification link is invalid.")
        return redirect(url_for("auth_views.login"))

@bp.route('/logout')
@is_authenticated
def logout():
    """
	Logs out the user by redirecting to the login page and deleting the access token cookie.
    
    This function performs the following actions:
    1. Redirects the user to the login page.
    2. Deletes the 'access_token' cookie to log the user out.
    
    Returns:
        Response: A redirect response to the login page.
    """
    resp = redirect(url_for("auth_views.login"))
    resp.delete_cookie("access_token")
    return resp
