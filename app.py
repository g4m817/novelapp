import os
from flask import Flask, jsonify, render_template, get_flashed_messages, redirect, url_for, request
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO, join_room
from models import db, Story, Tag, News, Notification, SiteConfig, TokenCostConfig, User, CreditConfig, Role
from helpers import is_unauthenticated, is_authenticated, get_current_user, get_image_url
from flask import jsonify
from flask_jwt_extended import decode_token
import stripe

env = os.environ.get('env')
port = 80
if env == "development":
    port = 5000
app = Flask(__name__)
app.config.from_pyfile('config.py')

db.init_app(app)
jwt = JWTManager(app)
socketio = SocketIO(app, cors_allowed_origins='*', message_queue='redis://localhost:6379/1')

from api.generation import bp as generation_bp
from api.story import bp as story_bp
from api.admin import bp as admin_bp
from api.auth import bp as auth_bp
from api.profile import bp as profile_bp
from views.admin import bp as admin_views_bp
from views.auth import bp as auth_views_bp
from views.story import bp as story_views_bp
from views.profile import bp as profile_views_bp

app.register_blueprint(generation_bp)
app.register_blueprint(story_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(profile_bp)

app.register_blueprint(admin_views_bp)
app.register_blueprint(auth_views_bp)
app.register_blueprint(story_views_bp)
app.register_blueprint(profile_views_bp)

@socketio.on("connect")
def on_connect():
    """
	Handles the connection of a user by processing the access token from cookies.
    
    This function retrieves the access token from the request cookies, decodes it to extract the user ID, 
    and allows the user to join their designated room. If the token is missing or invalid, appropriate 
    messages are printed to indicate the issue.
    
    Raises:
        Exception: If there is an error during the token decoding process.
    
    Returns:
        None
    """
    token = request.cookies.get("access_token")
    if token:
        try:
            decoded_token = decode_token(token)
            user_id = decoded_token.get("sub")
            if user_id:
                join_room(int(user_id))
                print(f"User {user_id} has connected and joined their room.")
            else:
                print("Token decoded but no user id found.")
        except Exception as e:
            print(f"Failed to decode token: {e}")
    else:
        print("No access token provided.")

with app.app_context():
    stripe.api_key = app.config.get('STRIPE_SECRET_KEY')
    db.create_all()
    if TokenCostConfig.query.count() == 0:
        config = TokenCostConfig(
            cost_per_credit=0.000999,
            cost_per_1m_input=0.150,
            cost_per_1m_output=0.600,
            o1_cost_per_credit=0.000999,
            o1_cost_per_1m_input=15.00,
            o1_cost_per_1m_output=60.00,
            dall_e_price_per_image=0.08
        )
        db.session.add(config)
        print("Default OpenAI costs added.")
    if CreditConfig.query.count() == 0:
        defaults = [
            {"action": "image", "type": "image", "modifier": 50},
            {"action": "meta_input", "type": "text", "modifier": 50},
            {"action": "meta_output", "type": "text", "modifier": 50},
            {"action": "summary_input", "type": "text", "modifier": 2},
            {"action": "summary_output", "type": "text", "modifier": 2},
            {"action": "arcs_input", "type": "text", "modifier": 2},
            {"action": "arcs_output", "type": "text", "modifier": 2},
            {"action": "chapter_guide_input", "type": "text", "modifier": 2},
            {"action": "chapter_guide_output", "type": "text", "modifier": 2},
            {"action": "chapter_input", "type": "text", "modifier": 2},
            {"action": "chapter_output", "type": "text", "modifier": 2},
        ]
        for conf in defaults:
            config = CreditConfig(action=conf["action"], type=conf["type"], modifier=conf["modifier"])
            db.session.add(config)
        print("Default credit configurations added.")
    admin_role = Role.query.filter_by(name="admin").first()
    if not admin_role:
        admin_role = Role(name="admin", default_text_credits=1000, default_image_credits=1000, default_audio_credits=1000, protected=True)
        db.session.add(admin_role)
        print("Created admin role")
    user_role = Role.query.filter_by(name="user").first()
    if not user_role:
        user_role = Role(name="user", default_text_credits=0, default_image_credits=0, default_audio_credits=0)
        db.session.add(user_role)
        print("Created user role")
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username=app.config["ADMIN_USERNAME"], is_verified=True, role=admin_role, email='admin@example.com', text_credits=10000, image_credits=1000, audio_credits=1000)
        admin.set_password(app.config["ADMIN_PASSWORD"])
        db.session.add(admin)
        print("Default admin user created.")
    db.session.commit()

@app.template_filter('fromjson')
def fromjson_filter(s):
    """
	Converts a JSON string to a Python object.
    
    This function attempts to parse a JSON string and return the corresponding Python object.
    If the input string is not a valid JSON, it returns an empty list.
    
    Args:
        s (str): The JSON string to be parsed.
    
    Returns:
        object: The Python object represented by the JSON string, or an empty list if parsing fails.
    """
    try:
        return json.loads(s)
    except Exception:
        return []

@app.context_processor
def inject_flashed_messages():
    """
	Injects flashed messages into a dictionary.
    
    This function retrieves flashed messages from the session and returns them
    as a dictionary with the key 'messages'.
    
    Returns:
        dict: A dictionary containing the flashed messages under the key 'messages'.
    """
    messages = get_flashed_messages()
    return dict(messages=messages)

@app.context_processor
def inject_unread_notifications():
    """
	Injects the count of unread notifications for the current user.
    
    This function retrieves the current user and counts the number of unread notifications
    associated with that user. If the user is not found, the unread notification count will be zero.
    
    Returns:
        dict: A dictionary containing the count of unread notifications under the key 
        'unread_notifications'.
    """
    user = get_current_user()
    unread_count = 0
    if user:
        unread_count = Notification.query.filter_by(user_id=user.id, is_read=False).count()
    return dict(unread_notifications=unread_count)

@app.before_request
def check_maintenance_mode():
    """
	Checks and updates the application's maintenance mode and registration status based on the site configuration.
    
    This function retrieves the current user and the first site configuration from the database. It updates the application's configuration for registration and maintenance mode based on the retrieved site configuration. If the site is in maintenance mode and the current user is not an admin, it handles requests accordingly by allowing access to specific paths (logout, login, API) and redirecting to a maintenance page for other requests.
    
    Returns:
        None: This function does not return a value but may redirect or return a JSON response based on the application's state.
    
    Raises:
        None: This function does not raise exceptions but may handle requests differently based on the application's configuration.
    """
    user = get_current_user()
    site_config = SiteConfig.query.first()
    if site_config:
        app.config["REGISTRATION_DISABLED"] = site_config.registration_disabled
        app.config["MAINTENANCE_MODE"] = site_config.maintenance_mode
    else:
        app.config["REGISTRATION_DISABLED"] = False
        app.config["MAINTENANCE_MODE"] = False
    is_admin = user and user.role.name.lower() == "admin"
    
    if app.config["MAINTENANCE_MODE"] and not is_admin:
        if request.path.startswith("/logout"):
            return
        if request.path.startswith("/login"):
            return
        if request.path.startswith("/api"):
            return jsonify({"error": "Site is under maintenance."}), 503
        if request.endpoint != "maintenance" and not request.path.startswith('/static'):
            return redirect(url_for("maintenance"))
        
@app.route('/maintenance')
def maintenance():
    """
	Handles the maintenance mode of the application.
    
    If the application is not in maintenance mode, it redirects the user to the index page.
    If the application is in maintenance mode, it renders a maintenance page with a message.
    
    Returns:
        Response: A redirect response to the index page if not in maintenance mode,
                  or a rendered maintenance page with a 503 status code if in maintenance mode.
    """
    if not app.config["MAINTENANCE_MODE"]:
        return redirect(url_for("index"))
    message = "The site is currently undergoing maintenance. Please check back later."
    return render_template("maintenance.html", message=message), 503

@app.route('/')
@is_unauthenticated
def index():
    """
	Render the index page.
    
    This function renders the 'index.html' template when called.
    
    Returns:
        Response: The rendered HTML page for the index.
    """
    return render_template("index.html")

@app.route('/cookie_policy')
def cookie_policy():
    return render_template("policies/cookie_policy.html")

@app.route('/acceptable_use')
def acceptable_use():
    return render_template("policies/acceptable_use.html")

@app.route('/copyright')
def copyright():
    return render_template("policies/copyright.html")

@app.route('/dmca')
def dmca():
    return render_template("policies/dmca.html")

@app.route('/privacy_policy')
def privacy_policy():
    return render_template("policies/privacy_policy.html")

@app.route('/refund_policy')
def refund_policy():
    return render_template("policies/refund_policy.html")

@app.route('/terms_of_use')
def terms_of_use():
    return render_template("policies/terms_of_use.html")

@app.route('/dashboard')
@is_authenticated
def dashboard():
    """
	Render the user dashboard with stories and favorite stories.
    
    This function retrieves the current user, paginates the user's stories and favorite stories, 
    and renders the dashboard template with the relevant data.
    
    Args:
        None
    
    Returns:
        str: Rendered HTML of the dashboard template with stories and favorites.
    """
    user = get_current_user()
    
    stories_page = request.args.get('stories_page', 1, type=int)
    favorites_page = request.args.get('favorites_page', 1, type=int)
    
    stories_pagination = Story.query.filter_by(user_id=user.id)\
        .order_by(Story.created_at.desc())\
        .paginate(page=stories_page, per_page=10, error_out=False)
    stories = stories_pagination.items
    for story in stories:
        story.presigned_cover_url = get_image_url(story.cover_image_key)

    favorites_pagination = user.favorite_stories\
        .order_by(Story.created_at.desc())\
        .paginate(page=favorites_page, per_page=10, error_out=False)
    favorites = favorites_pagination.items

    for story in favorites:
        story.author = User.query.get(story.user_id).username
        story.presigned_cover_url = get_image_url(story.cover_image_key)

    return render_template("dashboard.html", 
                           stories=stories,
                           stories_pagination=stories_pagination,
                           favorites=favorites,
                           favorites_pagination=favorites_pagination,
                           user=user)

@app.route('/feedback', methods=["GET", "POST"])
@is_authenticated
def feedback():
    """
	Handles user feedback submission.
    
    This function processes feedback submitted by users. It checks if the request method is POST and retrieves the feedback message from the form. If the message is empty, it flashes an error message and redirects the user back to the feedback page. If the message is valid, it creates a new Feedback entry, adds it to the database, and commits the transaction. A success message is flashed, and the user is redirected to the dashboard. If the request method is not POST, it renders the feedback template.
    
    Returns:
        str: Rendered HTML template for feedback or redirects to another page based on the request method.
    
    Raises:
        Exception: If there is an issue with database operations.
    """
    from models import Feedback
    from flask import flash
    user = get_current_user()
    if request.method == "POST":
        message = request.form.get("message")
        if not message:
            flash("Message cannot be empty.", "error")
            return redirect(url_for('feedback'))
        feedback_entry = Feedback(
            user_id=user.id,
            username=user.username,
            email=user.email,
            message=message
        )
        db.session.add(feedback_entry)
        db.session.commit()
        flash("Thank you for your feedback!", "success")
        return redirect(url_for('dashboard'))
    return render_template("feedback.html", user=user)

@app.route('/news')
@is_authenticated
def news():
    """
	Fetches and displays news items for the current user.
    
    This function retrieves the current user, fetches news items from the database, 
    and paginates the results. It then renders the news items in a template.
    
    Args:
        None
    
    Returns:
        str: Rendered HTML template containing news items and pagination information.
    """
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    news_pagination = News.query.order_by(News.created_at.desc()).paginate(page=page, per_page=5, error_out=False)
    news_items = news_pagination.items
    return render_template("news.html", news_items=news_items, pagination=news_pagination, user=user)

@app.route('/explore')
@is_authenticated
def explore():
    """
	Explores and retrieves public and spotlight stories based on user preferences and query parameters.
    
    This function fetches stories that are shared and not marked as spotlight, applying filters based on user settings, tags, and sorting preferences. It also retrieves spotlight stories separately. The results are paginated for both public and spotlight stories.
    
    Args:
        user (User): The current user object, used to determine preferences such as mature content visibility.
        spotlight_page (int, optional): The page number for spotlight stories pagination. Defaults to 1.
    
    Returns:
        str: The rendered HTML template for the explore page, including public and spotlight stories along with pagination information.
    """
    user = get_current_user()
    spotlight_page = request.args.get('spotlight_page', 1, type=int)
    show_mature = user.show_mature

    spotlight_query = Story.query.filter_by(shared=True, spotlight=True)
    if not show_mature:
        spotlight_query = spotlight_query.filter(Story.is_mature == False)
    spotlight_pagination = spotlight_query.order_by(Story.created_at.desc()).paginate(page=spotlight_page, per_page=4, error_out=False)
    spotlight_stories = spotlight_pagination.items
    for story in spotlight_stories:
        author = User.query.get(story.user_id)
        story.presigned_cover_url = get_image_url(story.cover_image_key)
        story.author = author.username if author else "Unknown"

    return render_template(
        "explore.html",
        spotlight_stories=spotlight_stories,
        spotlight_pagination=spotlight_pagination,
        user=user
    )

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=port)
