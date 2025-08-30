from flask import Blueprint, request, render_template
from helpers import is_admin, get_current_user
from models import Feedback, Tag, News, Role, SiteConfig, Revenue, CreditPackage, CreditConfig, TokenCostConfig, GenerationLog, User, Story, db
bp = Blueprint('admin_views', __name__)

@bp.route('/admin/analytics', methods=["GET"])
@is_admin
def analytics():
    """
	Generates and renders an analytics view for user activity and costs associated with different models.
    
    This function retrieves the current user and optional year and month parameters from the request. 
    It queries the GenerationLog database to calculate total input and output tokens for specific models 
    ('gpt-4o-mini' and 'o1-mini'), as well as the associated costs based on a token cost configuration. 
    Additionally, it calculates the cost of successful image generations and audio listening time. 
    Finally, it retrieves total revenue for the specified time period and renders the analytics template 
    with all calculated values.
    
    Args:
        year (int, optional): The year for which to filter the analytics data. Defaults to None.
        month (int, optional): The month for which to filter the analytics data. Defaults to None.
    
    Returns:
        str: Rendered HTML template for the analytics view.
    """
    user = get_current_user()
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    
    gen_query = GenerationLog.query
    if year:
        gen_query = gen_query.filter(db.extract('year', GenerationLog.timestamp) == year)
    if month:
        gen_query = gen_query.filter(db.extract('month', GenerationLog.timestamp) == month)
    
    gpt_query = gen_query.filter(GenerationLog.model == 'gpt-4o-mini')
    gpt_totals = gpt_query.with_entities(
        db.func.sum(GenerationLog.input_tokens).label('total_input'),
        db.func.sum(GenerationLog.output_tokens).label('total_output')
    ).first()
    gpt_total_input = gpt_totals.total_input or 0
    gpt_total_output = gpt_totals.total_output or 0

    o1_query = gen_query.filter(GenerationLog.model == 'o1-mini')
    o1_totals = o1_query.with_entities(
        db.func.sum(GenerationLog.input_tokens).label('total_input'),
        db.func.sum(GenerationLog.output_tokens).label('total_output')
    ).first()
    o1_total_input = o1_totals.total_input or 0
    o1_total_output = o1_totals.total_output or 0

    total_input = gpt_total_input + o1_total_input
    total_output = gpt_total_output + o1_total_output
    
    token_config = TokenCostConfig.query.first()
    if token_config:
        gpt_input_cost = (gpt_total_input / 1e6) * token_config.cost_per_1m_input
        gpt_output_cost = (gpt_total_output / 1e6) * token_config.cost_per_1m_output
        o1_input_cost = (o1_total_input / 1e6) * token_config.o1_cost_per_1m_input
        o1_output_cost = (o1_total_output / 1e6) * token_config.o1_cost_per_1m_output
    else:
        gpt_input_cost = gpt_output_cost = o1_input_cost = o1_output_cost = 0

    image_query = gen_query.filter(GenerationLog.model == 'dall-e-3')
    successful_images = image_query.filter(GenerationLog.status == 'succeeded').count()
    image_cost = successful_images * token_config.dall_e_price_per_image

    total_input_cost = gpt_input_cost + o1_input_cost
    total_output_cost = gpt_output_cost + o1_output_cost
    total_token_cost = total_input_cost + total_output_cost


    revenue_query = Revenue.query
    if year:
        revenue_query = revenue_query.filter(db.extract('year', Revenue.timestamp) == year)
    if month:
        revenue_query = revenue_query.filter(db.extract('month', Revenue.timestamp) == month)
    total_revenue = revenue_query.with_entities(db.func.sum(Revenue.amount)).scalar() or 0
    realized_revenue = total_revenue - (total_token_cost + image_cost)
    return render_template("admin/analytics.html",
                        total_input=total_input,
                        total_output=total_output,
                        total_input_cost=total_input_cost,
                        total_output_cost=total_output_cost,
                        total_token_cost=total_token_cost,
                        total_revenue=total_revenue,
                        gpt_total_input=gpt_total_input,
                        gpt_total_output=gpt_total_output,
                        gpt_input_cost=gpt_input_cost,
                        gpt_output_cost=gpt_output_cost,
                        o1_total_input=o1_total_input,
                        o1_total_output=o1_total_output,
                        o1_input_cost=o1_input_cost,
                        o1_output_cost=o1_output_cost,
                        image_cost=image_cost,
                        realized_revenue=realized_revenue,
                        year=year,
                        month=month,
                        user=user)

@bp.route('/admin', methods=["GET"])
@is_admin
def dashboard():
    """
	Render the admin dashboard view.
    
    This function retrieves the current user and renders the dashboard template
    for the admin interface.
    
    Returns:
        str: The rendered HTML of the admin dashboard.
    """
    user = get_current_user()
    return render_template("admin/dashboard.html",
                           user=user)

@bp.route('/admin/site_settings', methods=["GET"])
@is_admin
def site_settings():
    """
	Render the site settings view for the admin panel.
    
    This function retrieves the current user and the first site configuration from the database,
    then renders the site settings template with the retrieved data.
    
    Returns:
        str: Rendered HTML of the site settings page.
    """
    user = get_current_user()
    site_config = SiteConfig.query.first()
    return render_template("admin/site_settings.html", site_config=site_config, user=user)

@bp.route('/admin/tags', methods=["GET"])
@is_admin
def tags():
    """
	Render the tags view for the admin panel.
    
    This function retrieves the current user and a list of tags ordered by their name,
    then renders the 'admin/tags.html' template with the retrieved data.
    
    Returns:
        str: Rendered HTML of the tags view.
    """
    user = get_current_user()
    tags = Tag.query.order_by(Tag.name).all()
    return render_template("admin/tags.html", tags=tags, user=user)

@bp.route('/admin/stories', methods=["GET"])
@is_admin
def stories():
    """
	Render the stories view for the admin panel.
    
    This function retrieves the current user, fetches a paginated list of stories 
    from the database, and renders the stories in the admin stories template.
    
    Args:
        None
    
    Returns:
        str: Rendered HTML template for the stories view.
    """
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    stories_pagination = Story.query.order_by(Story.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    stories = stories_pagination.items
    return render_template("admin/stories.html", stories=stories, pagination=stories_pagination, user=user)


@bp.route('/admin/token_config', methods=["GET"])
@is_admin
def token_config():
    """
	Render the token configuration view for the admin panel.
    
    This function retrieves the current user and the first token cost configuration from the database,
    then renders the token configuration template with the retrieved data.
    
    Returns:
        str: Rendered HTML template for the token configuration view.
    """
    user = get_current_user()
    tokenCostConfigs = TokenCostConfig.query.first()
    return render_template("admin/token_config.html", tokenCostConfigs=tokenCostConfigs, user=user)

@bp.route('/admin/credit_management', methods=["GET"])
@is_admin
def credit_management():
    """
	Render the credit management view for the admin panel.
    
    This function retrieves the current user, all credit configurations, and all users from the database, 
    then renders the credit management template with the retrieved data.
    
    Returns:
        str: Rendered HTML template for credit management.
    """
    user = get_current_user()
    configs = CreditConfig.query.all()
    users = User.query.all()
    return render_template("admin/credit_management.html", configs=configs, users=users, user=user)

@bp.route('/admin/role_management', methods=["GET"])
@is_admin
def role_management():
    """
	Render the role management view for the admin panel.
    
    This function retrieves the current user and a list of roles from the database, 
    then renders the role management template with the retrieved data.
    
    Returns:
        str: Rendered HTML template for role management.
    """
    user = get_current_user()
    roles = Role.query.order_by(Role.id).all()
    return render_template("admin/role_management.html", roles=roles, user=user)

@bp.route('/admin/user_management', methods=["GET"])
@is_admin
def user_management():
    """
	Render the user management view for the admin panel.
    
    This function retrieves the current user, paginates the list of users, and fetches all roles from the database. 
    It then renders the user management template with the relevant data.
    
    Args:
        None
    
    Returns:
        str: Rendered HTML template for user management.
    """
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    users_pagination = User.query.order_by(User.username.asc()).paginate(page=page, per_page=20, error_out=False)
    users = users_pagination.items
    roles = Role.query.order_by(Role.id).all()
    return render_template("admin/user_management.html", users=users, roles=roles, pagination=users_pagination, user=user)

@bp.route('/admin/flagged_stories', methods=["GET"])
@is_admin
def flagged_stories():
    """
	Render the flagged stories view for the admin panel.
    
    This function retrieves the current user and all stories that have been flagged.
    It then renders the 'flagged_stories.html' template, passing the flagged stories
    and the current user as context.
    
    Returns:
        str: Rendered HTML template for the flagged stories view.
    """
    user = get_current_user()
    flagged_stories = Story.query.filter_by(flagged=True).all()
    return render_template("admin/flagged_stories.html", stories=flagged_stories, user=user)

@bp.route('/admin/generation_logs', methods=["GET"])
@is_admin
def generation_logs():
    """
	Generates and renders the generation logs view for the admin panel.
    
    This function retrieves the current user, processes query parameters for searching
    generation logs, and paginates the results. It filters logs based on the provided
    username or task ID, orders them by timestamp in descending order, and renders
    the results in the specified template.
    
    Args:
        None
    
    Returns:
        flask.Response: The rendered HTML template containing the generation logs
        and pagination information.
    """
    user = get_current_user()
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    
    query = GenerationLog.query

    if q:
        searched_user = User.query.filter_by(username=q).first()
        if searched_user:
            query = query.filter(GenerationLog.user_id == searched_user.id)
        else:
            query = query.filter(GenerationLog.task_id.ilike(f"%{q}%"))
    
    query = query.order_by(GenerationLog.timestamp.desc())
    
    pagination = query.paginate(page=page, per_page=20, error_out=False)
    logs = pagination.items

    return render_template(
        "admin/generation_logs.html",
        logs=logs,
        pagination=pagination,
        q=q,
        user=user
    )

@bp.route('/admin/credit_packages', methods=["GET"])
@is_admin
def credit_packages():
    """
	Render the credit packages view for the admin panel.
    
    This function retrieves the current user and all available credit packages from the database,
    then renders the 'credit_packages.html' template with the retrieved data.
    
    Returns:
        str: Rendered HTML of the credit packages view.
    """
    user = get_current_user()
    packages = CreditPackage.query.all()
    return render_template("admin/credit_packages.html", packages=packages, user=user)

@bp.route('/admin/feedback', methods=["GET"])
@is_admin
def feedback_list():
    """
	Render the feedback list view for the admin panel.
    
    This function retrieves the current user and a list of feedback items ordered by their creation date in descending order. It then renders the feedback list template with the retrieved user and feedback items.
    
    Returns:
        str: Rendered HTML template for the feedback list view.
    """
    user = get_current_user()
    feedback_items = Feedback.query.order_by(Feedback.created_at.desc()).all()
    return render_template("admin/feedback_list.html", user=user, feedback_items=feedback_items)


@bp.route('/admin/news', methods=["GET"])
@is_admin
def news_list():
    """
	Render a paginated list of news items for the admin interface.
    
    This function retrieves the current user, fetches a specific page of news items from the database, 
    and renders them in the 'admin/news_list.html' template. The news items are ordered by their creation date 
    in descending order.
    
    Args:
        None
    
    Returns:
        str: Rendered HTML template containing the list of news items and pagination information.
    """
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    news_pagination = News.query.order_by(News.created_at.desc()).paginate(page=page, per_page=10, error_out=False)
    news_items = news_pagination.items
    return render_template("admin/news_list.html", user=user, news_items=news_items, pagination=news_pagination)