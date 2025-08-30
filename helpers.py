import logging
from functools import wraps
from datetime import timedelta
from flask import request, redirect, url_for, jsonify, current_app
from models import User, Story, GenerationLog, Comment, db
from flask_jwt_extended import decode_token, create_access_token
import re
import requests
from sqlalchemy import desc
import boto3
from config import S3_REGION, S3_ENDPOINT, S3_IMAGE_ACCESS_KEY_ID, S3_IMAGE_SECRET_KEY

s3_client = boto3.client('s3',
    region_name=S3_REGION,
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_IMAGE_ACCESS_KEY_ID,
    aws_secret_access_key=S3_IMAGE_SECRET_KEY)

active_streaming_tasks = {}

def send_password_reset_email(email, token, username):
    """
	Send a password reset email to the specified user.
    
    This function constructs a password reset email containing a reset URL and sends it using the Mailgun API. It logs the success or failure of the email sending process.
    
    Args:
        email (str): The recipient's email address to which the password reset email will be sent.
        token (str): The token used to authenticate the password reset request.
        username (str): The username of the user requesting the password reset.
    
    Returns:
        None
    
    Raises:
        Exception: If there is an error in sending the email, an error message will be logged.
    """
    reset_url = url_for("auth_views.reset_password", token=token, _external=True)
    mailgun_domain = current_app.config.get("MAILGUN_DOMAIN")
    mailgun_api_key = current_app.config.get("MAILGUN_API_KEY")
    from_email = current_app.config.get("MAILGUN_FROM_EMAIL")
    
    html_content = f"""
    <html>
      <head>
        <meta charset="utf-8">
        <style>
          body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
          }}
          .button {{
            display: inline-block;
            padding: 10px 15px;
            background-color: #dfeaf8;
            color: #fff;
            text-decoration: none;
            border-radius: 5px;
          }}
        </style>
      </head>
      <body>
        <p>Hello {username},</p>
        <p>You recently requested to reset your password. Click the button below to proceed:</p>
        <p><a href="{reset_url}" class="button">Reset Your Password</a></p>
        <p>If you did not request this, please ignore this email.</p>
        <p>Thank you,<br>example.com</p>
      </body>
    </html>
    """
    
    data = {
        "from": from_email,
        "to": email,
        "subject": "[example.com] Password Reset Request",
        "html": html_content,
    }
    
    response = requests.post(
        f"https://api.mailgun.net/v3/{mailgun_domain}/messages",
        auth=("api", mailgun_api_key),
        data=data
    )
    
    if response.status_code == 200:
        current_app.logger.info("Password reset email sent successfully.")
    else:
        current_app.logger.error(f"Mailgun error: {response.text}")

def send_verification_email(email, token, username):
    """
	Send a verification email to the specified user.
    
    This function constructs a verification email containing a unique token and sends it to the user's email address using the Mailgun API. It logs the result of the email sending operation.
    
    Args:
        email (str): The recipient's email address.
        token (str): The unique token for email verification.
        username (str): The username of the recipient (not used in the current implementation).
    
    Returns:
        None
    
    Raises:
        Exception: If there is an error in sending the email, an error message is logged.
    """
    verification_url = url_for("auth.verify_email", token=token, _external=True)
    mailgun_domain = current_app.config.get("MAILGUN_DOMAIN")
    mailgun_api_key = current_app.config.get("MAILGUN_API_KEY")
    from_email = current_app.config.get("MAILGUN_FROM_EMAIL")
    
    html_content = f"""
    <html>
      <head>
        <meta charset="utf-8">
        <style>
          body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
          }}
          .button {{
            display: inline-block;
            padding: 10px 15px;
            background-color: #dfeaf8;
            color: #fff;
            text-decoration: none;
            border-radius: 5px;
          }}
        </style>
      </head>
      <body>
        <p>Hello {username},</p>
        <p>Thank you for registering with us. Please verify your email address by clicking the button below:</p>
        <p><a href="{verification_url}" class="button">Verify Email Address</a></p>
        <p>If you did not create an account, please disregard this email.</p>
        <p>Best regards,<br>example.com</p>
      </body>
    </html>
    """
    
    data = {
        "from": from_email,
        "to": email,
        "subject": "[example.com] Verify your email address",
        "html": html_content,
    }
    
    response = requests.post(
        f"https://api.mailgun.net/v3/{mailgun_domain}/messages",
        auth=("api", mailgun_api_key),
        data=data
    )
    
    if response.status_code == 200:
        current_app.logger.info("Verification email sent successfully.")
    else:
        current_app.logger.error(f"Mailgun error: {response.text}")

def is_last_generation_and_negative_creds(user, _type):
    """
	Determines if the last generation log entry for a user is of a specified type and if the user's credits for that type are negative.
    
    Args:
        user (User): The user object containing credit information.
        _type (str): The type of generation to check against the last log entry.
    
    Returns:
        bool: True if the last generation log entry matches the specified type and the user's credits for that type are negative, otherwise False.
    """
    log_entry = GenerationLog.query.filter_by(
        user_id=user.id
    ).order_by(desc(GenerationLog.id)).first()

    if not log_entry:
        return False
    
    generation_type = log_entry.generation_type

    if generation_type != _type:
        return False

    
    isCreditNegative = False
    if generation_type == "meta":
        if user.text_credits <= 0:
            isCreditNegative = True
    elif generation_type == "story_arcs":
        if user.text_credits <= 0:
            isCreditNegative = True
    elif generation_type == "summaries":
        if user.text_credits <= 0:
            isCreditNegative = True
    elif generation_type == "chapter_guide":
        if user.text_credits <= 0:
            isCreditNegative = True
    elif generation_type == "chapter":
        if user.text_credits <= 0:
            isCreditNegative = True
    elif generation_type == "chapter":
        if user.text_credits <= 0:
            isCreditNegative = True
    elif generation_type == "image":
        if user.image_credits <= 0:
            isCreditNegative = True
    return isCreditNegative

def delete_images_for_story(story_id):
    """
	Deletes all images associated with a specific story from an S3 bucket.
    
    Args:
        story_id (str): The unique identifier of the story whose images are to be deleted.
    
    Returns:
        dict or None: A dictionary containing the response from the S3 delete operation if images were deleted, 
                      or None if there were no images to delete.
                      
    Raises:
        Exception: Raises an exception if there is an error during the S3 operations.
    """    

    prefix = f"stories/{story_id}"
    response = s3_client.list_objects_v2(Bucket=current_app.config.get("S3_IMAGE_BUCKET"), Prefix=prefix)
    if 'Contents' in response:
        objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]
        delete_response = s3_client.delete_objects(
            Bucket=current_app.config.get("S3_IMAGE_BUCKET"),
            Delete={'Objects': objects_to_delete}
        )
        return delete_response
    return None

def put_image(image_key, image_data):
    """
	Uploads an image to an S3 bucket.
    
    Args:
        image_key (str): The key under which the image will be stored in the S3 bucket.
        image_data (bytes): The binary data of the image to be uploaded.
    
    Returns:
        str: The key of the uploaded image.
    
    Raises:
        botocore.exceptions.ClientError: If the upload fails due to an S3 client error.
    """
    s3_client.put_object(
        Bucket=current_app.config.get("S3_IMAGE_BUCKET"),
        Key=image_key,
        Body=image_data,
        ContentType='image/jpeg'
    )

    return image_key

def get_image_url(image_key):
    """
	Generates a presigned URL for an image stored in an S3 bucket.
    
    This function uses the provided image key to create a presigned URL that allows
    temporary access to the specified image in the S3 bucket. The URL will expire
    after one hour.
    
    Args:
        image_key (str): The key of the image in the S3 bucket.
    
    Returns:
        str or bool: A presigned URL as a string if successful, or False if an
        error occurs during URL generation.
    """
    try:
        return s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': current_app.config.get("S3_IMAGE_BUCKET"), 'Key': image_key},
            ExpiresIn=3600
        )
    except:
        return False

def generate_verification_token(user):
    """
	Generates a verification token for a given user.
    
    This function creates a time-limited access token that can be used to verify
    the user's email address. The token is valid for 48 hours and includes
    additional claims specifying the action as "verify_email".
    
    Args:
        user (User): The user object for whom the verification token is being generated.
    
    Returns:
        str: A JWT token that can be used for email verification.
    """
    token = create_access_token(
        identity=str(user.id),
        expires_delta=timedelta(hours=48),
        additional_claims={"action": "verify_email"}
    )
    return token

def is_valid_password(password: str) -> bool:
    """
	Checks if the provided password is valid based on specific criteria.
    
    A valid password must:
    - Be at least 8 characters long.
    - Contain at least one lowercase letter.
    - Contain at least one uppercase letter.
    - Contain at least one digit.
    - Contain at least one special character (non-alphanumeric).
    
    Args:
        password (str): The password string to be validated.
    
    Returns:
        bool: True if the password is valid, False otherwise.
    """
    pattern = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).{8,}$")
    return pattern.match(password) is not None

def notify(message, user_id):
    """
	Notify a user with a message via WebSocket.
    
    This function sends a notification message to a specific user identified by their user ID using Flask-SocketIO.
    
    Args:
        message (str): The notification message to be sent.
        user_id (str): The ID of the user to whom the notification will be sent.
    
    Returns:
        None
    """
    from flask_socketio import SocketIO
    from app import app, socketio
    socketio.emit("notification", {"message": message}, room=user_id)

def get_current_user():
    """
	Retrieves the current user based on the access token stored in the cookies.
    
    This function checks for an access token in the request cookies. If the token is found, it attempts to decode it to extract the user ID. If successful, it retrieves the corresponding user from the database. If the token is missing, invalid, or does not contain a user ID, the function returns None.
    
    Returns:
        User or None: The current user object if found, otherwise None.
    
    Logs:
        - A warning if the token is decoded but no user ID is found.
        - An error if the token decoding fails.
    """
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        decoded_token = decode_token(token)
        user_id = decoded_token.get("sub")
        if not user_id:
            logging.warning("Token decoded but no user id found.")
            return None
        return User.query.get(user_id)
    except Exception as e:
        logging.error(f"Failed to decode token: {e}")
        return None

def is_unauthenticated(func):
    """
	Decorator to restrict access to unauthenticated users.
    
    This decorator checks if the current user is authenticated. If the user is
    authenticated, they are redirected to the dashboard. If not, the original
    function is executed.
    
    Args:
        func (Callable): The function to be wrapped.
    
    Returns:
        Callable: The wrapped function that either redirects to the dashboard
        or calls the original function.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if user:
            return redirect(url_for("dashboard"))
        return func(*args, **kwargs)
    return wrapper

def is_authenticated(func):
    """
	Decorator to check if a user is authenticated before executing a function.
    
    This decorator retrieves the current user and checks if the user is authenticated.
    If the user is not authenticated, they are redirected to the login page. 
    If the user is authenticated, the original function is executed.
    
    Args:
        func (Callable): The function to be wrapped.
    
    Returns:
        Callable: The wrapped function that includes authentication check.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect(url_for("auth_views.login"))
        return func(*args, **kwargs)
    return wrapper

def is_admin(func):
    """
	Decorator to restrict access to admin users only.
    
    This decorator checks the current user's role and allows access to the
    decorated function only if the user has an 'admin' role. If the user
    is not an admin, they are redirected to the index page.
    
    Args:
        func (Callable): The function to be decorated.
    
    Returns:
        Callable: The wrapped function that enforces admin access.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user or user.role.name != "admin":
            return redirect(url_for("index"))
        return func(*args, **kwargs)
    return wrapper

def is_comment_author_or_admin(func):
    """
	Checks if the current user is the author of a comment or an admin.
    
    This decorator function wraps around a given function to enforce authorization
    for actions related to comments. It ensures that the user is logged in, that a
    valid comment ID is provided, and that the user is either the author of the
    comment or has an admin role. If any of these conditions are not met, it
    returns an appropriate error response.
    
    Args:
        func (Callable): The function to be wrapped.
    
    Returns:
        Callable: The wrapped function that includes authorization checks.
    
    Raises:
        Redirect: If the user is not logged in, redirects to the login page.
        jsonify: Returns a JSON response with an error message if the comment ID
                 is not provided, the comment is not found, or the user is
                 unauthorized.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect(url_for("auth_views.login"))
        comment_id = kwargs.get("comment_id")
        if not comment_id:
            json_data = request.get_json() or {}
            comment_id = json_data.get("comment_id")
        if not comment_id:
            return jsonify({"error": "comment_id not provided"}), 400
        comment = Comment.query.get(comment_id)
        if not comment:
            return jsonify({"error": "Story not found"}), 404
        if comment.user_id != user.id and user.role.name != "admin":
            return jsonify({"error": "Unauthorized"}), 403
        return func(*args, **kwargs)
    return wrapper

def is_story_author_or_admin(func):
    """
	Checks if the current user is the author of a story or an admin.
    
    This decorator function wraps around a view function to ensure that the user
    has the necessary permissions to access the story. It verifies that the user
    is logged in, checks for the presence of a `story_id`, and confirms that the
    user is either the author of the story or has an admin role.
    
    Args:
        func (Callable): The view function to be wrapped.
    
    Returns:
        Callable: The wrapped function that includes permission checks.
    
    Raises:
        Redirect: If the user is not logged in, redirects to the login page.
        jsonify: Returns a JSON response with an error message if the `story_id`
                 is not provided, the story is not found, or the user is unauthorized.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect(url_for("auth_views.login"))
        story_id = kwargs.get("story_id")
        if not story_id:
            json_data = request.get_json() or {}
            story_id = json_data.get("story_id")
        if not story_id:
            return jsonify({"error": "story_id not provided"}), 400
        story = Story.query.get(story_id)
        if not story:
            return jsonify({"error": "Story not found"}), 404
        if story.user_id != user.id and user.role.name != "admin":
            return jsonify({"error": "Unauthorized"}), 403
        return func(*args, **kwargs)
    return wrapper

def can_spend_credits(user, credit_type, cost):
    """
	Determine if a user can spend a specified amount of credits of a given type.
    
    Args:
        user (User): The user object containing credit information.
        credit_type (str): The type of credit to check ('text', 'image', or 'audio').
        cost (int): The amount of credits to spend.
    
    Returns:
        bool: True if the user has enough credits of the specified type to cover the cost, 
              False otherwise.
    """
    if credit_type == "text":
        return user.text_credits >= cost
    elif credit_type == "image":
        return user.image_credits >= cost
    elif credit_type == "audio":
        return user.audio_credits >= cost
    return False

def spend_credits(user_id, credit_type, cost):
    """
	Spends credits for a specified user and credit type.
    
    Args:
        user_id (int): The ID of the user whose credits are to be spent.
        credit_type (str): The type of credit to spend. Must be one of 'text', 'image', or 'audio'.
        cost (int): The amount of credits to spend.
    
    Raises:
        ValueError: If the credit_type is not one of the allowed types.
        Exception: If there is an issue with the database session or user retrieval.
    
    Returns:
        None
    """
    user = User.query.filter_by(id=user_id).first()
    if credit_type == "text":
        user.text_credits -= cost
    elif credit_type == "image":
        user.image_credits -= cost
    elif credit_type == "audio":
        user.audio_credits -= cost
    db.session.commit()
