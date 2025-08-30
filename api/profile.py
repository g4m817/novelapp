from flask import Blueprint, current_app, flash, request, redirect, url_for, jsonify
from models import User, Role, Revenue, Notification, CreditPackage, db
from helpers import get_current_user, is_authenticated, is_valid_password
import stripe

bp = Blueprint('profile', __name__)

@bp.route("/profile")
@bp.route("/profile/")
@is_authenticated
def profile():
    """
	Redirects the user to the profile details view.
    
    This function handles the redirection to the 'profile.details' endpoint.
    
    Returns:
        werkzeug.wrappers.Response: A redirect response to the profile details view.
    """
    return redirect(url_for('profile_views.details'))

@bp.route('/update_profile', methods=["POST"])
@is_authenticated
def update_profile():
    """
	Update the user's profile information based on the submitted form data.
    
    This function handles updates to the user's email, password, and mature content settings. 
    It retrieves the current user and checks which fields are being updated based on the 
    submitted form. The function performs the necessary validations and updates the user's 
    information in the database, providing feedback through flash messages.
    
    Returns:
        Redirect: Redirects to the profile details view after the update is processed.
    
    Raises:
        Flash messages are displayed for various validation errors, including:
            - Invalid email input
            - Password mismatch
            - Incorrect current password
            - Invalid new password criteria
    """
    user = get_current_user()
    if "update_password" in request.form:
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")
        
        if new_password != confirm_password:
            flash("New passwords do not match.")
        elif not user.check_password(current_password):
            flash("Current password is incorrect.")
        elif not is_valid_password(new_password):
            flash("New password must be at least 8 characters long, include both uppercase and lowercase letters, at least one digit, and one special character.")
        else:
            user.set_password(new_password)
            db.session.commit()
            flash("Password updated successfully.")
    elif "update_mature" in request.form:
        user.show_mature = 'show_mature' in request.form
        db.session.commit()
        flash("Mature content settings updated.")
    return redirect(url_for('profile_views.details'))

@bp.route('/stripe/webhook', methods=['POST'])
def stripe_webhook():
    """
	Handles incoming Stripe webhook events.
    
    This function processes various types of events sent by Stripe, including
    invoice payment success, checkout session completion, and subscription
    deletion. It updates user credits and roles based on the event data.
    
    Returns:
        str: An empty string indicating success or an error message with a status code.
        int: HTTP status code indicating the result of the webhook processing.
    
    Raises:
        ValueError: If the payload is invalid.
        stripe.error.SignatureVerificationError: If the signature verification fails.
    """
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        return "Invalid payload", 400
    except stripe.error.SignatureVerificationError:
        return "Invalid signature", 400

    if event['type'] == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        subscription_id = invoice.get('subscription')
        user = User.query.filter_by(stripe_subscription_id=subscription_id).first()
        if user:
            new_rev = Revenue(amount=invoice['amount_paid'] / 100.0)
            db.session.add(new_rev)
            user.text_credits += user.role.default_text_credits
            user.image_credits += user.role.default_image_credits
            user.audio_credits += user.role.default_audio_credits
            db.session.commit()
    elif event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        metadata = session.get('metadata', {})
        user_id = metadata.get('user_id')
        role_id = metadata.get('role_id')
        if 'package_id' in metadata:
            package_id = metadata.get('package_id')
            credit_type = metadata.get('credit_type')
            user_id = metadata.get('user_id')
            user = User.query.get(user_id)
            package = CreditPackage.query.get(package_id)
            if user and package:
                new_rev = Revenue(amount=session['amount_total'] / 100.0)
                db.session.add(new_rev)
                if credit_type == 'text':
                    user.text_credits += package.credits
                elif credit_type == 'image':
                    user.image_credits += package.credits
                elif credit_type == 'audio':
                    user.audio_credits += package.credits
                db.session.commit()
        else:
            subscription_id = session.get('subscription')
            if user_id and role_id:
                user = User.query.get(user_id)
                new_role = Role.query.get(role_id)
                if user and new_role:
                    user.role = new_role
                    user.stripe_subscription_id = subscription_id
                    db.session.commit()

    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        stripe_customer_id = subscription.get('customer')
        user = User.query.filter_by(stripe_customer_id=stripe_customer_id).first()
        if user:
            default_role = Role.query.filter_by(name='user').first()
            if default_role:
                user.role = default_role
                user.text_credits = default_role.default_text_credits
                user.image_credits = default_role.default_image_credits
                user.audio_credits = default_role.default_audio_credits
                user.stripe_subscription_id = None
                db.session.commit()
    return "", 200

@bp.route('/create-portal-session', methods=["POST"])
@is_authenticated
def create_portal_session():
    """
	Creates a billing portal session for the current user.
    
    This function retrieves the current user and checks if they have an associated 
    Stripe customer ID. If not, it flashes an error message and redirects the user 
    to their subscriptions view. If the user has a Stripe customer ID, it attempts 
    to create a billing portal session using the Stripe API. If successful, it 
    redirects the user to the session URL. In case of an error during session 
    creation, it flashes an error message and redirects the user to their 
    subscriptions view.
    
    Returns:
        Response: A redirect response to the billing portal session URL or the 
        subscriptions view in case of an error.
    
    Raises:
        Exception: If there is an error while creating the billing portal session, 
        an error message is flashed and the user is redirected to the subscriptions 
        view.
    """
    user = get_current_user()
    if not user.stripe_customer_id:
        flash("No Stripe customer associated with your account.", "error")
        return redirect(url_for('profile_views.subscriptions', _external=True))
    url = url_for('profile_views.subscriptions', _external=True)
    try:
        session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=url_for('profile_views.subscriptions', _external=True)
        )
        return redirect(session.url)
    except Exception as e:
        flash(f"Error creating portal session: {str(e)}", "error")
        return redirect(url_for('profile_views.subscriptions', _external=True))

@bp.route('/create-one-time-checkout-session/<int:package_id>', methods=["POST"])
@is_authenticated
def create_one_time_checkout_session(package_id):
    """
	Creates a one-time checkout session for a specified credit package.
    
    This function retrieves the current user and the specified credit package. If the user does not have a Stripe customer ID, it creates a new Stripe customer. Then, it creates a checkout session for the specified package and returns the session ID in JSON format. In case of an error during the session creation, it returns an error message with a 400 status code.
    
    Args:
        package_id (str): The ID of the credit package for which the checkout session is to be created.
    
    Returns:
        Response: A JSON response containing the session ID if successful, or an error message with a 400 status code if an exception occurs.
    """
    user = get_current_user()
    package = CreditPackage.query.get_or_404(package_id)

    if not user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=user.email,
            name=user.username,
            metadata={"user_id": user.id}
        )
        user.stripe_customer_id = customer.id
        db.session.commit()

    success_url = url_for('profile_views.subscriptions', _external=True)
    cancel_url = url_for('profile_views.subscriptions', _external=True)
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            mode='payment',
            customer=user.stripe_customer_id,
            line_items=[{
                'price': package.stripe_price_id,
                'quantity': 1,
            }],
            metadata={
                'user_id': user.id,
                'package_id': package.id,
                'credit_type': package.credit_type
            },
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return jsonify(id=session.id)
    except Exception as e:
        return jsonify(error=str(e)), 400

@bp.route('/create-checkout-session/<int:role_id>', methods=["POST"])
@is_authenticated
def create_checkout_session(role_id):
    """
	Creates a checkout session for a user to subscribe to a specific role.
    
    This function retrieves the current user and checks if the specified role is valid for subscription. 
    If the user does not have a Stripe customer ID, it creates one. Then, it creates a Stripe checkout session 
    for the user to subscribe to the specified role.
    
    Args:
        role_id (int): The ID of the role to subscribe to.
    
    Returns:
        Response: A JSON response containing the session ID if successful, 
                  or redirects to the subscriptions view if the role is invalid 
                  or the user is not eligible for subscription.
    """
    user = get_current_user()
    new_role = Role.query.get_or_404(role_id)
    if not new_role:
        return redirect(url_for('profile_views.subscriptions'))
    if new_role.name.lower() == 'admin' or new_role.name.lower() == 'user':
        return redirect(url_for('profile_views.subscriptions'))

    if not user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=user.email,
            name=user.username,
            metadata={"user_id": user.id}
        )
        user.stripe_customer_id = customer.id
        db.session.commit()

    url = url_for('profile_views.subscriptions', _external=True)
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        mode='subscription',
        customer=user.stripe_customer_id,
        line_items=[{
            'price': new_role.stripe_price_id,
            'quantity': 1,
        }],
        metadata={
            'user_id': user.id,
            'role_id': new_role.id,
        },
        success_url=url_for('profile_views.subscriptions', _external=True),
        cancel_url=url_for('profile_views.subscriptions', _external=True),
    )
    return jsonify(id=session.id)

@bp.route("/profile/notifications/mark_all_read", methods=["POST"])
@is_authenticated
def mark_all_notifications_read():
    """
	Marks all unread notifications for the current user as read.
    
    This function retrieves the current user, fetches all unread notifications associated with that user, 
    marks them as read, and commits the changes to the database. A success message is flashed to the user, 
    and they are redirected to the notifications view of their profile.
    
    Returns:
        werkzeug.wrappers.Response: A redirect response to the notifications view.
    """
    user = get_current_user()
    notifications = Notification.query.filter_by(user_id=user.id, is_read=False).all()
    for n in notifications:
        n.is_read = True
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for('profile_views.notifications'))

@bp.route("/profile/notifications/clear", methods=["POST"])
@is_authenticated
def clear_notifications():
    """
	Clears all notifications for the currently logged-in user.
    
    This function retrieves the current user, fetches all notifications associated with that user, 
    deletes them from the database, and commits the changes. A success message is flashed to the user, 
    and they are redirected to the notifications view of their profile.
    
    Returns:
        werkzeug.wrappers.Response: A redirect response to the notifications view.
    """
    user = get_current_user()
    notifications = Notification.query.filter_by(user_id=user.id).all()
    for n in notifications:
        db.session.delete(n)
    db.session.commit()
    flash("Notifications cleared.", "success")
    return redirect(url_for("profile_views.notifications"))
