from flask import Blueprint, current_app, render_template, request
from models import Role, GenerationLog, Notification, CreditPackage, db
from helpers import get_current_user, is_authenticated

bp = Blueprint('profile_views', __name__)

@bp.route("/profile/details")
@is_authenticated
def details():
    """
	Render the details view for the current user's profile.
    
    This function retrieves the current user and renders the details 
    template with the user's information.
    
    Returns:
        str: The rendered HTML template for the user's profile details.
    """
    user = get_current_user()
    return render_template("profile/details.html", user=user)


@bp.route("/profile/subscriptions")
@is_authenticated
def subscriptions():
    """
	Render the subscriptions view for the current user.
    
    This function retrieves the current user, fetches all roles excluding the admin role, 
    and retrieves all available credit packages. It then renders the subscriptions 
    template with the gathered data and the Stripe publishable key.
    
    Returns:
        Response: The rendered HTML template for the subscriptions view.
    """
    user = get_current_user()
    roles = Role.query.filter(Role.name != "admin").all()
    credit_packages = CreditPackage.query.all()
    return render_template("profile/subscriptions.html", user=user, roles=roles, credit_packages=credit_packages, stripe_key=current_app.config.get("STRIPE_PUBLISHABLE_KEY"))

@bp.route("/profile/history")
@is_authenticated
def history():
    """
	Render the history view for the current user.
    
    This function retrieves the current user, fetches their generation logs from the database, 
    and renders the history page with pagination.
    
    Args:
        None
    
    Returns:
        str: Rendered HTML template for the user's history page.
    """
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = GenerationLog.query.filter_by(user_id=user.id)\
        .order_by(GenerationLog.timestamp.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    generation_logs = pagination.items
    return render_template("profile/history.html", user=user, pagination=pagination, generation_logs=generation_logs)

@bp.route("/profile/notifications")
@is_authenticated
def notifications():
    """
	Render the notifications view for the current user.
    
    This function retrieves the current user, fetches their notifications from the database, 
    and renders the notifications page with the relevant data. It supports pagination to 
    display a limited number of notifications per page.
    
    Args:
        None
    
    Returns:
        str: Rendered HTML template for the notifications page.
    """
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = Notification.query.filter_by(user_id=user.id)\
                      .order_by(Notification.created_at.desc())\
                      .paginate(page=page, per_page=per_page, error_out=False)
    notifications = pagination.items
    return render_template("profile/notifications.html", user=user, notifications=notifications, pagination=pagination)
