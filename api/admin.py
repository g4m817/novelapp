from flask import Blueprint, flash, current_app, request, redirect, jsonify
from helpers import is_admin, get_current_user, notify
from models import Feedback, Character, Location, ChapterGuide, Tag, News, Role, SiteConfig, CreditPackage, CreditConfig, TokenCostConfig, User, Story, db
from flask import url_for
bp = Blueprint('admin', __name__)
import stripe

@bp.route('/admin/feedback/delete/<int:feedback_id>', methods=["POST"])
@is_admin
def delete_feedback(feedback_id):
    """
	Deletes a feedback item from the database.
    
    This function retrieves a feedback item by its ID, deletes it from the database, 
    and commits the changes. A success message is flashed to the user, and the user 
    is redirected to the feedback list view.
    
    Args:
        feedback_id (int): The ID of the feedback item to be deleted.
    
    Returns:
        werkzeug.wrappers.Response: A redirect response to the feedback list view.
    
    Raises:
        NotFound: If the feedback item with the specified ID does not exist.
    """
    feedback_item = Feedback.query.get_or_404(feedback_id)
    db.session.delete(feedback_item)
    db.session.commit()
    flash("Feedback deleted.", "success")
    return redirect(url_for('admin_views.feedback_list'))

@bp.route('/admin/news/create', methods=["POST"])
@is_admin
def create_news():
    """
	Create a news article from form data.
    
    This function retrieves the title and body of a news article from the request form.
    If either the title or body is missing, it flashes an error message and redirects
    to the news list view. If both fields are provided, it creates a new News object,
    adds it to the database session, commits the session, and flashes a success message
    before redirecting to the news list view.
    
    Returns:
        Redirect: A redirect response to the news list view.
    
    Raises:
        Flash: Displays an error message if title or body is missing.
    """
    title = request.form.get("title")
    body = request.form.get("body")
    if not title or not body:
        flash("Title and body are required.", "error")
        return redirect(url_for('admin_views.news_list'))
    news_item = News(title=title, body=body)
    db.session.add(news_item)
    db.session.commit()
    flash("News article created.", "success")
    return redirect(url_for('admin_views.news_list'))

@bp.route('/admin/news/edit/<int:news_id>', methods=["POST"])
@is_admin
def edit_news(news_id):
    """
	Edit a news article.
    
    This function retrieves a news article by its ID, updates its title and body 
    with the data provided in the request form, and commits the changes to the database. 
    If the title or body is missing, it flashes an error message and redirects to the 
    news list view.
    
    Args:
        news_id (int): The ID of the news article to be edited.
    
    Returns:
        Redirect: A redirect to the news list view after updating the article or 
        flashing an error message.
    
    Raises:
        NotFound: If the news article with the given ID does not exist.
    """
    news_item = News.query.get_or_404(news_id)
    title = request.form.get("title")
    body = request.form.get("body")
    if not title or not body:
        flash("Title and body are required.", "error")
        return redirect(url_for('admin_views.news_list'))
    news_item.title = title
    news_item.body = body
    db.session.commit()
    flash("News article updated.", "success")
    return redirect(url_for('admin_views.news_list'))

@bp.route('/admin/news/delete/<int:news_id>', methods=["POST"])
@is_admin
def delete_news(news_id):
    """
	Deletes a news article from the database.
    
    This function retrieves a news article by its ID, deletes it from the database, 
    and commits the changes. A success message is flashed to the user, and the user 
    is redirected to the news list view.
    
    Args:
        news_id (int): The ID of the news article to be deleted.
    
    Returns:
        werkzeug.wrappers.Response: A redirect response to the news list view.
    
    Raises:
        NotFound: If the news article with the specified ID does not exist.
    """
    news_item = News.query.get_or_404(news_id)
    db.session.delete(news_item)
    db.session.commit()
    flash("News article deleted.", "success")
    return redirect(url_for('admin_views.news_list'))

@bp.route('/admin/credit_packages/create', methods=["POST"])
@is_admin
def create_credit_package():
    """
	Creates a new credit package based on user input from a form.
    
    This function retrieves the credit type, number of credits, and cost from the request form. 
    It checks if a credit package with the same type and credits already exists. If it does, 
    it returns an error response. If not, it creates a new credit package, adds it to the 
    database, and attempts to create a corresponding price in Stripe. If the Stripe price 
    creation fails, the new package is deleted from the database, and an error message is flashed. 
    Finally, it redirects to the credit packages view.
    
    Returns:
        Response: A redirect response to the credit packages view, or an error response if 
        the credit package already exists or if an error occurs during Stripe price creation.
    
    Raises:
        Exception: If there is an error during the Stripe price creation process.
    """
    credit_type = request.form.get("credit_type")
    credits = int(request.form.get("credits"))
    cost = float(request.form.get("cost"))

    if CreditPackage.query.filter_by(credit_type=credit_type, credits=credits).first():
        return jsonify({"error": "Credit package already exists."}), 400

    new_package = CreditPackage(credit_type=credit_type, credits=credits, cost=cost)
    db.session.add(new_package)
    db.session.commit()

    unit_amount = int(cost * 100)
    try:
        stripe_price = stripe.Price.create(
            unit_amount=unit_amount,
            currency="usd",
            product_data={"name": f"{credits} {credit_type.capitalize()} Credits Package"}
        )
        new_package.stripe_price_id = stripe_price.id
        db.session.commit()
    except Exception as e:
        db.session.delete(new_package)
        db.session.commit()
        flash("An error occurred")
        return redirect(url_for('admin_views.credit_packages'))
    flash("Credit Package Created")
    return redirect(url_for('admin_views.credit_packages'))

@bp.route('/admin/credit_packages/delete/<int:package_id>', methods=["DELETE"])
@is_admin
def delete_credit_package(package_id):
    """
	Deletes a credit package by its ID.
    
    This function retrieves a credit package from the database using the provided
    package ID. If the package has an associated Stripe price ID, it attempts to
    deactivate the corresponding Stripe product. After handling any potential
    errors with Stripe, the function deletes the credit package from the database
    and commits the changes.
    
    Args:
        package_id (int): The ID of the credit package to be deleted.
    
    Returns:
        jsonify: A JSON response indicating the success of the deletion.
    
    Raises:
        NotFound: If the credit package with the given ID does not exist.
        Exception: If there is an error while interacting with the Stripe API.
    """
    package = CreditPackage.query.get_or_404(package_id)
    
    if package.stripe_price_id:
        try:
            stripe_price = stripe.Price.retrieve(package.stripe_price_id)
            product_id = stripe_price.product
            stripe.Product.modify(product_id, active=False)
        except Exception as e:
            flash(f"Stripe error deactivating product: {e}", "error")

    db.session.delete(package)
    db.session.commit()
    flash("Credit Package Deleted")
    return jsonify({"message": "Credit Package Deleted"})

@bp.route('/admin/update_credit_package/<int:package_id>', methods=["POST"])
@is_admin
def update_credit_package(package_id):
    """
	Update a credit package with new values for credits, cost, and credit type.
    
    This function retrieves a credit package by its ID, updates its attributes based on the provided form data, and commits the changes to the database. If the cost, credits, or credit type has changed, it also updates the corresponding Stripe price. In case of an error during the Stripe update, an error message is flashed, and the user is redirected to the credit packages view.
    
    Args:
        package_id (int): The ID of the credit package to update.
    
    Returns:
        Response: A redirect response to the credit packages view after the update is processed.
    
    Raises:
        NotFound: If the credit package with the given ID does not exist.
    """
    package = CreditPackage.query.get_or_404(package_id)
    new_credits = int(request.form.get("credits", package.credits))
    new_cost = float(request.form.get("cost", package.cost))
    new_credit_type = request.form.get("credit_type", package.credit_type)

    cost_changed = new_cost != package.cost or new_credits != package.credits or new_credit_type != package.credit_type

    package.credits = new_credits
    package.cost = new_cost
    package.credit_type = new_credit_type
    db.session.commit()

    if cost_changed:
        try:
            unit_amount = int(new_cost * 100)
            stripe_price = stripe.Price.create(
                unit_amount=unit_amount,
                currency="usd",
                product_data={"name": f"{new_credits} {new_credit_type.capitalize()} Credits Package"}
            )
            package.stripe_price_id = stripe_price.id
            db.session.commit()
        except Exception as e:
            flash(f"Stripe error updating package: {e}", "error")
            return redirect(url_for('admin_views.credit_packages'))
    
    flash("Credit Package Updated")
    return redirect(url_for('admin_views.credit_packages'))

@bp.route('/admin/unflag_story/<int:story_id>', methods=["POST"])
@is_admin
def unflag_story(story_id):
    """
	Unflags a story by its ID.
    
    This function retrieves a story from the database using the provided 
    story ID, sets its flagged status to False, and commits the change 
    to the database. It also flashes a success message indicating that 
    the story has been unflagged and redirects the user to the 
    flagged stories view in the admin panel.
    
    Args:
        story_id (int): The ID of the story to be unflagged.
    
    Returns:
        werkzeug.wrappers.Response: A redirect response to the flagged 
        stories view.
    """
    story = Story.query.get_or_404(story_id)
    story.flagged = False
    db.session.commit()
    flash(f"Story '{story.title}' has been unflagged.", "success")
    return redirect(url_for("admin_views.flagged_stories"))

@bp.route('/admin/toggle_under_review/<int:user_id>', methods=["POST"])
@is_admin
def toggle_under_review(user_id):
    """
	Toggle the 'under review' status of a user.
    
    This function retrieves the current user and checks if the user 
    attempting to modify the review status is not the same as the user 
    whose status is being modified. If they are the same, an error message 
    is flashed and the user is redirected to the user management view. 
    If they are different, the function toggles the 'under review' status 
    of the specified user, commits the change to the database, and flashes 
    a success message indicating the new status.
    
    Args:
        user_id (int): The ID of the user whose review status is to be toggled.
    
    Returns:
        Redirect: A redirect to the user management view.
    """
    user = get_current_user()
    user_to_update = User.query.get_or_404(user_id)
    if user_to_update.id == user.id:
        flash("You cannot modify your own review status.", "error")
        return redirect(url_for("admin_views.user_management"))
    
    user_to_update.under_review = not user_to_update.under_review
    db.session.commit()
    status = "under review" if user_to_update.under_review else "not under review"
    flash(f"User {user_to_update.username} is now {status}.", "success")
    return redirect(url_for("admin_views.user_management"))

@bp.route('/admin/toggle_lock/<int:user_id>', methods=["POST"])
@is_admin
def toggle_lock_user(user_id):
    """
	Toggle the lock status of a user account.
    
    This function retrieves the current user and checks if the user attempting to toggle the lock status is the same as the user being modified. If they are the same, an error message is flashed, and the user is redirected to the user management view. If they are different, the lock status of the specified user is toggled, the change is committed to the database, and a success message is flashed indicating the new status of the user account.
    
    Args:
        user_id (int): The ID of the user whose lock status is to be toggled.
    
    Returns:
        Response: A redirect response to the user management view.
    """
    user = get_current_user()
    user_to_update = User.query.get_or_404(user_id)
    if user_to_update.id == user.id:
        flash("You cannot lock/unlock your own account.", "error")
        return redirect(url_for("admin_views.user_management"))
    
    user_to_update.is_locked = not user_to_update.is_locked
    db.session.commit()
    status = "locked" if user_to_update.is_locked else "unlocked"
    flash(f"User {user_to_update.username} has been {status}.", "success")
    return redirect(url_for("admin_views.user_management"))

@bp.route('/admin/delete_story/<int:story_id>', methods=["DELETE"])
@is_admin
def delete_story(story_id):
    """
	Deletes a story and its associated data from the database.
    
    This function retrieves a story by its ID, deletes the story along with its related characters, locations, and detailed story arc mappings. It also removes any images associated with the story and commits the changes to the database. A flash message is displayed to inform the user that the story has been deleted.
    
    Args:
        story_id (int): The ID of the story to be deleted.
    
    Returns:
        werkzeug.wrappers.Response: A redirect response to the stories view page.
    
    Raises:
        NotFound: If the story with the given ID does not exist.
    """
    story = Story.query.get_or_404(story_id)
    db.session.delete(story)
    Character.query.filter_by(story_id=story.id).delete()
    Location.query.filter_by(story_id=story.id).delete()
    ChapterGuide.query.filter_by(story_id=story.id).delete()
    db.session.commit()
    from helpers import delete_images_for_story
    delete_images_for_story(story_id)
    flash("Story Deleted")
    return redirect(url_for('admin_views.stories'));

@bp.route('/admin/update_token_config', methods=['POST'])
@is_admin
def update_token_config():
    """
	Update the token configuration based on user input from a form.
    
    This function retrieves token cost values from the request form, updates the existing 
    token configuration in the database, or creates a new configuration if none exists. 
    It handles input validation and provides feedback to the user through flash messages.
    
    Returns:
        Redirect: A redirect to the token configuration view, with a success or error message 
        displayed to the user.
    
    Raises:
        ValueError: If the input values cannot be converted to float.
        TypeError: If the input values are of an unexpected type.
    """
    try:
        cost_per_credit = float(request.form.get("cost_per_token"))
        cost_per_1m_input = float(request.form.get("cost_per_1m_tokens_input"))
        cost_per_1m_output = float(request.form.get("cost_per_1m_tokens_output"))
        o1_cost_per_credit = float(request.form.get("o1_cost_per_token"))
        o1_cost_per_1m_input = float(request.form.get("o1_cost_per_1m_tokens_input"))
        o1_cost_per_1m_output = float(request.form.get("o1_cost_per_1m_tokens_output"))
        dall_e_price_per_image = float(request.form.get("dall_e_price_per_image"))
    except (TypeError, ValueError):
        flash("Invalid input. Please ensure all values are numbers.", "error")
        return redirect(url_for("admin_views.token_config"))

    token_config = TokenCostConfig.query.first()
    if not token_config:
        token_config = TokenCostConfig(
            cost_per_1m_input=cost_per_1m_input,
            cost_per_1m_output=cost_per_1m_output,
            cost_per_credit=cost_per_credit,
            o1_cost_per_credit=o1_cost_per_token,
            o1_cost_per_1m_input=o1_cost_per_1m_tokens_input,
            o1_cost_per_1m_output=o1_cost_per_1m_tokens_output,
            dall_e_price_per_image=dall_e_price_per_image
        )
        db.session.add(token_config)
    else:
        token_config.cost_per_1m_input = cost_per_1m_input
        token_config.cost_per_1m_output = cost_per_1m_output
        token_config.cost_per_credit = cost_per_credit
        token_config.o1_cost_per_1m_input = o1_cost_per_1m_input
        token_config.o1_cost_per_1m_output = o1_cost_per_1m_output
        token_config.o1_cost_per_credit = o1_cost_per_credit
        token_config.dall_e_price_per_image = dall_e_price_per_image

    try:
        db.session.commit()
        flash("Token configuration updated successfully.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating token configuration: {e}")
        flash("An error occurred while updating the configuration.", "error")
    return redirect(url_for("admin_views.token_config"))

@bp.route('/admin/tags', methods=["POST"])
@is_admin
def tags():
    """
	Creates a new tag based on the provided name and description from the request form.
    
    This function retrieves the 'name' and 'description' fields from the form data. 
    If a name is provided, it creates a new Tag object, adds it to the database session, 
    commits the session, and flashes a success message. Finally, it redirects the user 
    to the tags view in the admin section.
    
    Returns:
        Response: A redirect response to the admin tags view.
    
    Raises:
        Exception: If there is an error during the database commit.
    """
    name = request.form.get("name")
    description = request.form.get("description")
    if name:
        tag = Tag(name=name, description=description)
        db.session.add(tag)
        db.session.commit()
        flash("Tag Created")
    return redirect(url_for('admin_views.tags'))

@bp.route('/admin/tags/edit/<int:tag_id>', methods=["POST"])
@is_admin
def edit_tag(tag_id):
    """
	Edit a tag in the database.
    
    This function retrieves a tag by its ID, updates its name and description 
    with the data provided in the request form, and commits the changes to the 
    database. It also flashes a success message and redirects the user to the 
    tags view page.
    
    Args:
        tag_id (int): The ID of the tag to be edited.
    
    Returns:
        Response: A redirect response to the tags view page.
    
    Raises:
        NotFound: If the tag with the specified ID does not exist.
    """
    tag = Tag.query.get_or_404(tag_id)
    tag.name = request.form.get("name")
    tag.description = request.form.get("description")
    db.session.commit()
    flash("Tag Edited")
    return redirect(url_for('admin_views.tags'))

@bp.route('/admin/tags/delete/<int:tag_id>', methods=["POST"])
@is_admin
def delete_tag(tag_id):
    """
	Deletes a tag from the database.
    
    This function retrieves a tag by its ID, deletes it from the session, 
    commits the changes to the database, and flashes a success message. 
    Finally, it redirects the user to the tags view page.
    
    Args:
        tag_id (int): The ID of the tag to be deleted.
    
    Returns:
        Response: A redirect response to the tags view page.
    
    Raises:
        NotFound: If the tag with the specified ID does not exist.
    """
    tag = Tag.query.get_or_404(tag_id)
    db.session.delete(tag)
    db.session.commit()
    flash("Tag Deleted")
    return redirect(url_for('admin_views.tags'))

@bp.route('/admin/update_site_config', methods=["POST"])
@is_admin
def update_site_config():
    """
	Update the site configuration based on the provided form data.
    
    This function retrieves the first site configuration from the database. If no configuration exists, it creates a new one. It updates the `registration_disabled` and `maintenance_mode` settings based on the values received from the request form. After updating the configuration, it commits the changes to the database, flashes a success message, and redirects the user to the site settings view.
    
    Returns:
        werkzeug.wrappers.Response: A redirect response to the site settings view.
    
    Raises:
        Exception: If there is an issue with the database session or committing changes.
    """
    site_config = SiteConfig.query.first()
    if not site_config:
        site_config = SiteConfig()
        db.session.add(site_config)
    site_config.registration_disabled = bool(request.form.get("registration_disabled"))
    site_config.maintenance_mode = bool(request.form.get("maintenance_mode"))
    db.session.commit()
    flash("Config Updated")
    return redirect(url_for('admin_views.site_settings'))

@bp.route('/admin/delete_user/<int:user_id>', methods=["DELETE"])
@is_admin
def delete_user(user_id):
    """
	Deletes a user from the database.
    
    This function checks if the current user is attempting to delete their own account,
    in which case it returns an error. It also checks if the user to be deleted has an
    active subscription. If both checks pass, the user is deleted from the database,
    and a notification is sent.
    
    Args:
        user_id (int): The ID of the user to be deleted.
    
    Returns:
        Response: A JSON response indicating the result of the deletion operation.
            - If the current user tries to delete their own account, returns a 400 error
              with a message.
            - If the user to be deleted has an active subscription, returns a 400 error
              with a message.
            - If the deletion is successful, returns a success message.
    """
    user = get_current_user()
    if user.id == user_id:
        return jsonify({"error": "You cannot delete your own account."}), 400
    user_to_delete = User.query.get_or_404(user_id)
    if user_to_delete.stripe_subscription_id != None:
        return jsonify({"error": "User has an active subscription."}), 400  
    db.session.delete(user_to_delete)
    db.session.commit()
    notify(f"User {user_to_delete.username} deleted.", user.id)
    return jsonify({"message": f"User {user_to_delete.username} deleted."})

@bp.route('/admin/toggle_spotlight/<int:story_id>', methods=["POST"])
@is_admin
def toggle_spotlight(story_id):
    """
	Toggles the spotlight status of a public story.
    
    This function retrieves the current user and the story associated with the given
    story ID. If the story is not shared publicly, it returns an error message. If the
    story is public, it toggles the spotlight status and commits the change to the
    database. Additionally, it sends a notification to the user indicating that the
    story has been added to the spotlight.
    
    Args:
        story_id (int): The ID of the story to be spotlighted.
    
    Returns:
        flask.Response: A JSON response containing the new spotlight status of the
        story or an error message if the story is not public.
    """
    user = get_current_user()
    story = Story.query.get_or_404(story_id)
    if not story.shared:
        return jsonify({"error": "Story must be public to be spotlighted."}), 400
    story.spotlight = not story.spotlight
    db.session.commit()
    notify("Story Added to Spotlight", user.id)
    return jsonify({"spotlight": story.spotlight})

@bp.route("/admin/update_credit_config", methods=["POST"])
@is_admin
def update_credit_config():
    """
	Update the credit configuration based on the provided action and modifier.
    
    This function retrieves the action and modifier values from the request form. 
    It checks if a credit configuration with the specified action exists. If it does, 
    the modifier is updated; if not, a new configuration is created. The changes are 
    committed to the database, and a success message is flashed to the user. 
    Finally, the user is redirected to the credit management view.
    
    Returns:
        werkzeug.wrappers.Response: A redirect response to the credit management view.
    
    Raises:
        ValueError: If the modifier cannot be converted to a float.
    """
    action = request.form.get("action")
    modifier = float(request.form.get("modifier"))
    config = CreditConfig.query.filter_by(action=action).first()
    if config:
        config.modifier = modifier
    else:
        config = CreditConfig(action=action, modifier=modifier)
        db.session.add(config)
    db.session.commit()
    flash("Credit Config Updated")
    return redirect(url_for("admin_views.credit_management"))

@bp.route('/admin/adjust_credits/<int:user_id>', methods=["POST"])
@is_admin
def adjust_credits(user_id):
    """
	Adjusts the credits for a specified user based on the provided credit type.
    
    Args:
        user_id (int): The ID of the user whose credits are to be adjusted.
    
    Raises:
        NotFound: If the user with the specified user_id does not exist.
    
    Returns:
        Response: A redirect response to the credit management view after adjusting the credits.
    
    This function retrieves the credit type and new credit amount from the request form,
    updates the corresponding credit attribute of the user, and commits the changes to the database.
    A flash message is displayed to indicate that the user credits have been adjusted.
    """
    credit_type = request.form.get("type")
    new_credits = int(request.form.get("credits"))
    user = User.query.get_or_404(user_id)
    if credit_type == "text":
        user.text_credits = new_credits
    elif credit_type == "image":
        user.image_credits = new_credits
    elif credit_type == "audio":
        user.audio_credits = new_credits
    db.session.commit()
    flash("User Credits Adjusted")
    return redirect(url_for('admin_views.credit_management'))

@bp.route('/admin/update_user_role/<int:user_id>', methods=["POST"])
@is_admin
def update_user_role(user_id):
    """
	Update the role of a user.
    
    This function retrieves the current user and the new role name from the request form. 
    It checks if the specified role exists and updates the user's credits if the user 
    is not trying to change their own role. If the role is successfully updated, 
    it commits the changes to the database and redirects to the user management view. 
    If the role is not found or the update cannot be performed, it returns an error 
    message or a flash message indicating the failure.
    
    Args:
        user_id (int): The ID of the user whose role is to be updated.
    
    Returns:
        Response: A redirect response to the user management view or a JSON error 
        response if the role is not found.
    """
    user = get_current_user()
    new_role_name = request.form.get("role")
    new_role = Role.query.filter_by(name=new_role_name).first()
    if not new_role:
        return jsonify({"error": "Role not found."}), 400
    user_to_update = User.query.get_or_404(user_id)
    if user_to_update.role_id != new_role.id and user_to_update.username != user.username:
        user_to_update.text_credits += new_role.default_text_credits
        user_to_update.image_credits += new_role.default_image_credits
        user_to_update.audio_credits += new_role.default_audio_credits
    else:
        flash("Could not update role")
        return redirect(url_for('admin_views.user_management'))
    user_to_update.role = new_role
    db.session.commit()
    flash("User Role Updated")
    return redirect(url_for('admin_views.user_management'))

@bp.route('/admin/create_role', methods=["POST"])
@is_admin
def create_role():
    """
	Creates a new user role and configures a corresponding Stripe price.
    
    This function retrieves role details from the request form, checks if the role already exists, and if not, creates a new role in the database. It also sets up a recurring payment plan in Stripe for the role. If the role creation or Stripe configuration fails, it handles the error appropriately.
    
    Returns:
        Response: A JSON response indicating success or error, along with an HTTP status code.
    
    Raises:
        Exception: If there is an error during the Stripe price creation process, the role is deleted from the database, and the user is redirected to the role management view.
    """
    role_name = request.form.get("role_name")
    default_text = int(request.form.get("default_text", 0))
    default_image = int(request.form.get("default_image", 0))
    default_audio = int(request.form.get("default_audio", 0))
    cost = float(request.form.get("cost", 0))
    
    if Role.query.filter_by(name=role_name).first():
        return jsonify({"error": "Role already exists."}), 400

    new_role = Role(
        name=role_name,
        default_text_credits=default_text,
        default_image_credits=default_image,
        default_audio_credits=default_audio,
        cost=cost,
        protected=False
    )
    db.session.add(new_role)
    db.session.commit()

    unit_amount = int(cost * 100)

    try:
        stripe_price = stripe.Price.create(
            unit_amount=unit_amount,
            currency="usd",
            recurring={"interval": "month"},
            product_data={
                "name": f"{role_name} Subscription"
            }
        )
        new_role.stripe_price_id = stripe_price.id
        db.session.commit()
    except Exception as e:
        flash(f"Stripe error: {str(e)}", "error")
        db.session.delete(new_role)
        db.session.commit()
        return redirect(url_for('admin_views.role_management'))

    flash("User Role Created and Stripe Price configured")
    return redirect(url_for('admin_views.role_management'))

@bp.route('/admin/delete_role/<int:role_id>', methods=["POST"])
@is_admin
def delete_role(role_id):
    """
	Deletes a role identified by the given role_id.
    
    This function checks if the role is protected or if any user currently has the role assigned. 
    If the role is protected or assigned to a user, it displays an appropriate error message and 
    redirects to the role management view. If the role has an associated Stripe price ID, it 
    attempts to archive the corresponding Stripe product before deleting the role from the database. 
    If successful, a success message is flashed; otherwise, an error message is displayed.
    
    Args:
        role_id (int): The ID of the role to be deleted.
    
    Returns:
        Redirect: A redirect to the role management view after attempting to delete the role.
    """
    role = Role.query.get_or_404(role_id)
    if role.protected:
        flash("This role cannot be deleted.", "error")
        return redirect(url_for('admin_views.role_management'))
    
    user_with_role = User.query.filter_by(role_id=role_id).first()
    if user_with_role:
        flash("User currently has role so it cannot be deleted.")
        return redirect(url_for('admin_views.role_management'))
    if role.stripe_price_id:
        try:
            stripe_price = stripe.Price.retrieve(role.stripe_price_id)
            product_id = stripe_price.product
            stripe.Product.modify(product_id, active=False)
            db.session.delete(role)
            db.session.commit()
            flash("User Role Deleted", "success")

        except Exception as e:
            flash(f"Error archiving Stripe product for role {role.id}: {e}")
    else:
        flash("Couldn't find stripe_price_id")
    return redirect(url_for('admin_views.role_management'))

@bp.route('/admin/edit_role/<int:role_id>', methods=["POST"])
@is_admin
def edit_role(role_id):
    """
	Edit an existing role in the database.
    
    This function retrieves a role by its ID, updates its attributes based on form data, 
    and commits the changes to the database. If the role has an associated Stripe price ID, 
    it updates the corresponding Stripe product and price as well.
    
    Args:
        role_id (int): The ID of the role to be edited.
    
    Returns:
        Response: A redirect response to the role management view.
    
    Raises:
        NotFound: If the role with the specified ID does not exist.
        Exception: If there is an error while updating the Stripe product or price.
    """
    role = Role.query.get_or_404(role_id)

    new_name = request.form.get("role_name", role.name)
    default_text = int(request.form.get("default_text", role.default_text_credits))
    default_image = int(request.form.get("default_image", role.default_image_credits))
    default_audio = int(request.form.get("default_audio", role.default_audio_credits))
    new_cost = float(request.form.get("cost", role.cost))

    cost_changed = new_cost != role.cost
    role.name = new_name
    role.default_text_credits = default_text
    role.default_image_credits = default_image
    role.default_audio_credits = default_audio
    role.cost = new_cost
    db.session.commit()

    if role.stripe_price_id:
        try:
            stripe_price = stripe.Price.retrieve(role.stripe_price_id)
            product_id = stripe_price.product

            stripe.Product.modify(product_id, name=f"{new_name} Subscription")

            if cost_changed:
                unit_amount = int(new_cost * 100)
                new_stripe_price = stripe.Price.create(
                    unit_amount=unit_amount,
                    currency="usd",
                    recurring={"interval": "month"},
                    product=product_id
                )
                role.stripe_price_id = new_stripe_price.id
                db.session.commit()

        except Exception as e:
            flash(f"Stripe error updating role: {e}", "error")
            return redirect(url_for('admin_views.role_management'))

    flash("Role updated successfully", "success")
    return redirect(url_for('admin_views.role_management'))
