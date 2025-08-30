from flask import Blueprint, render_template, flash, request, redirect, url_for
from helpers import get_image_url, get_current_user, is_authenticated, is_story_author_or_admin
from models import db, User, Story, Comment, Chapter, ChapterGuide, Character, Location

bp = Blueprint('story_views', __name__)

@bp.route('/story/new', methods=["GET"])
@is_authenticated
def new_story():
    """
	Render the overview page for a new story.
    
    This function retrieves the current user and renders the story overview template,
    passing the user information and a placeholder for the story.
    
    Returns:
        str: The rendered HTML template for the story overview.
    """
    user = get_current_user()
    return render_template("story/overview.html", user=user, story=None)

@bp.route('/story/<int:story_id>', methods=["GET"])
@is_story_author_or_admin
def overview(story_id):
    """
	Overview view for displaying a story.
    
    This function retrieves the current user and a story based on the provided
    story ID. It fetches the author's username and renders the story overview
    template with the user and story information.
    
    Args:
        story_id (int): The ID of the story to be retrieved.
    
    Returns:
        Response: The rendered HTML template for the story overview.
    """
    user = get_current_user()
    story = Story.query.get_or_404(story_id)
    story.author = User.query.get(story.user_id).username
    return render_template("story/overview.html", user=user, story=story)

@bp.route('/story/<int:story_id>/meta', methods=["GET"])
@is_story_author_or_admin
def meta(story_id):
    """
	Retrieve and render the metadata view for a specific story.
    
    This function checks if the current user has sufficient credits to view the story's metadata. If the user has negative credits, they are redirected to the dashboard with a flash message prompting them to top up their credits. If the user has sufficient credits, the function retrieves the story, its author, characters, and locations, and renders the metadata template.
    
    Args:
        story_id (int): The ID of the story for which metadata is to be retrieved.
    
    Returns:
        Response: A rendered HTML template of the story's metadata or a redirect response to the dashboard.
    """
    from helpers import is_last_generation_and_negative_creds
    user = get_current_user()
    if is_last_generation_and_negative_creds(user, "meta"):
        flash("Top up your credits to see generation")
        return redirect(url_for("dashboard"))
    story = Story.query.get_or_404(story_id)
    story.author = User.query.get(story.user_id).username
    characters = Character.query.filter_by(story_id=story.id).all()
    locations = Location.query.filter_by(story_id=story.id).all()
    return render_template("story/meta.html", user=user, story=story, characters=characters, locations=locations)

@bp.route('/story/<int:story_id>/summaries', methods=["GET"])
@is_story_author_or_admin
def summaries(story_id):
    """
	Summaries view for a specific story.
    
    This function retrieves the summaries of a story identified by the given `story_id`. 
    It checks if the current user has sufficient credits to view the summaries. If the user 
    does not have enough credits, they are redirected to the dashboard with a flash message 
    to top up their credits. If the user has sufficient credits, the function fetches the 
    story and its associated chapters, and renders the summaries template.
    
    Args:
        story_id (int): The ID of the story for which summaries are to be retrieved.
    
    Returns:
        Response: A rendered HTML template of the story summaries or a redirect response 
        to the dashboard if the user lacks sufficient credits.
    """
    from helpers import is_last_generation_and_negative_creds
    user = get_current_user()
    if is_last_generation_and_negative_creds(user, "summaries"):
        flash("Top up your credits to see generation")
        return redirect(url_for("dashboard"))
    story = Story.query.get_or_404(story_id)
    story.author = User.query.get(story.user_id).username
    chapters = Chapter.query.filter_by(story_id=story.id).order_by(Chapter.chapter_number).all()
    return render_template("story/summaries.html", user=user, story=story, chapters=chapters)

@bp.route('/story/<int:story_id>/arcs', methods=["GET"])
@is_story_author_or_admin
def arcs(story_id):
    """
	Fetches and displays the arcs of a specific story.
    
    This function retrieves the arcs associated with a given story identified by 
    the `story_id`. It checks if the current user has sufficient credits to view 
    the arcs. If the user has negative credits and is on the last generation, 
    they are redirected to the dashboard with a flash message prompting them to 
    top up their credits. If the user has sufficient credits, the function 
    retrieves the story and its associated arcs, sorts the arcs by their order, 
    and renders the arcs in the specified template.
    
    Args:
        story_id (int): The unique identifier of the story whose arcs are to be fetched.
    
    Returns:
        Response: A rendered HTML template displaying the story arcs or a redirect 
        response to the dashboard if the user lacks sufficient credits.
    """
    from helpers import is_last_generation_and_negative_creds
    user = get_current_user()
    if is_last_generation_and_negative_creds(user, "story_arcs"):
        flash("Top up your credits to see generation")
        return redirect(url_for("dashboard"))
    story = Story.query.get_or_404(story_id)
    story.author = User.query.get(story.user_id).username
    arcs = sorted(story.arcs, key=lambda arc: arc.arc_order)
    return render_template("story/arcs.html", user=user, story=story, arcs=arcs)

@bp.route('/story/<int:story_id>/chapter_guide', methods=["GET"])
@is_story_author_or_admin
def chapter_guide(story_id):
    """
	Retrieve and display detailed story arcs for a given story.
    
    This function checks if the current user has sufficient credits to view the detailed story arcs. If the user has negative credits, they are redirected to the dashboard with a flash message prompting them to top up their credits. If the user has sufficient credits, the function retrieves the specified story and its associated detailed story arc mappings, groups them by chapter title, and sorts the arcs within each chapter. Finally, it renders the Chapter Guides in a specified HTML template.
    
    Args:
        story_id (int): The ID of the story for which Chapter Guides are to be retrieved.
    
    Returns:
        Response: The rendered HTML template displaying the detailed story arcs.
    """
    from helpers import is_last_generation_and_negative_creds
    user = get_current_user()
    if is_last_generation_and_negative_creds(user, "chapter_guide"):
        flash("Top up your credits to see generation")
        return redirect(url_for("dashboard"))
    story = Story.query.get_or_404(story_id)
    mappings = ChapterGuide.query.filter_by(story_id=story_id).all()
    
    grouped_arcs = {}
    for mapping in mappings:
        mapping_dict = {
            "id": mapping.id,
            "story_id": mapping.story_id,
            "arc": mapping.part_index,
            "arc_text": mapping.part_text,
            "chapter_title": mapping.chapter_title,
            "characters": mapping.characters,
            "locations": mapping.locations
        }
        grouped_arcs.setdefault(mapping.chapter_title, []).append(mapping_dict)

    for chapter_title, parts in grouped_arcs.items():
        grouped_arcs[chapter_title] = sorted(parts, key=lambda x: x["arc"])
    
    return render_template("story/chapter_guide.html", user=user, story=story, chapter_guide=grouped_arcs)


@bp.route('/story/<int:story_id>/chapters', methods=["GET"])
@is_story_author_or_admin
def chapters(story_id):
    """
	Fetches and displays the chapters of a specific story.
    
    This function retrieves the chapters associated with a given story ID. It checks if the current user has sufficient credits to view the chapters. If the user has negative credits and is on the last generation, they are redirected to the dashboard with a flash message prompting them to top up their credits. If the user has sufficient credits, the function retrieves the story and its chapters from the database and renders the chapters view template.
    
    Args:
        story_id (int): The ID of the story for which chapters are to be retrieved.
    
    Returns:
        Response: A rendered template displaying the chapters of the story or a redirect to the dashboard if the user lacks sufficient credits.
    """
    from helpers import is_last_generation_and_negative_creds
    user = get_current_user()
    if is_last_generation_and_negative_creds(user, "chapter"):
        flash("Top up your credits to see generation")
        return redirect(url_for("dashboard"))
    story = Story.query.get_or_404(story_id)
    story.author = User.query.get(story.user_id).username
    chapters = Chapter.query.filter_by(story_id=story.id).order_by(Chapter.chapter_number).all()
    return render_template("story/chapters.html", user=user, story=story, chapters=chapters)

@bp.route('/story/<int:story_id>/images', methods=["GET"])
@is_story_author_or_admin
def images(story_id):
    """
	View function to display images for a specific story.
    
    This function retrieves the story by its ID, checks if the user has sufficient credits to view the images, and prepares the necessary URLs for the story's cover image and its chapters' images. If the user does not have enough credits, they are redirected to the dashboard with a flash message.
    
    Args:
        story_id (int): The ID of the story to retrieve.
    
    Returns:
        Response: The rendered HTML template for the story images or a redirect response to the dashboard if the user lacks credits.
    """
    from helpers import is_last_generation_and_negative_creds
    user = get_current_user()
    if is_last_generation_and_negative_creds(user, "image"):
        flash("Top up your credits to see generation")
        return redirect(url_for("dashboard"))
    story = Story.query.get_or_404(story_id)
    story.presigned_cover_url = get_image_url(story.cover_image_key)
    for chapter in story.chapters:
        chapter.presigned_chapter_url = get_image_url(chapter.chapter_image_key)

    return render_template("story/images.html", user=user, story=story)


@bp.route('/story/<int:story_id>/read')
@is_authenticated
def read_story(story_id):
    """
	Reads a story by its ID and prepares it for rendering.
    
    This function retrieves a story from the database using the provided story ID. It checks the user's permissions to access the story, including whether the story is private and if the user is the author or an admin. It also fetches the author's username and generates presigned URLs for the story's cover image and its chapters.
    
    Args:
        story_id (int): The ID of the story to be read.
    
    Returns:
        tuple: A tuple containing the rendered HTML template for the story if the user has access, 
               or a tuple with a message and a 403 status code if the story is private.
    """
    user = get_current_user()
    story = Story.query.get_or_404(story_id)
    story.author = User.query.get(story.user_id).username
    story.presigned_cover_url = get_image_url(story.cover_image_key)
    for chapter in story.chapters:
        chapter.presigned_chapter_url = get_image_url(chapter.chapter_image_key)
    if not story.shared and (user.id != story.user_id and user.role.name.lower() != 'admin'):
        return "This story is private.", 403

    chapters = Chapter.query.filter_by(story_id=story.id).order_by(Chapter.chapter_number).all()
    return render_template("story/read.html", story=story, user=user, chapters=chapters)

@bp.route('/story/<int:story_id>/comments', methods=["GET"])
@is_authenticated
def story_comments(story_id):
    """
	Retrieve and render comments for a specific story.
    
    This function fetches the story identified by the given `story_id`, retrieves the current user, and paginates the comments associated with the story. It then renders the comments in a specified template.
    
    Args:
        story_id (int): The unique identifier of the story for which comments are to be retrieved.
    
    Returns:
        Response: The rendered HTML template containing the story and its comments, along with pagination information.
    """
    user = get_current_user()
    story = Story.query.get_or_404(story_id)
    story.author = User.query.get(story.user_id).username
    page = request.args.get('page', 1, type=int)
    per_page = 5
    pagination = Comment.query.filter_by(story_id=story.id).order_by(Comment.created_at.desc())\
                     .paginate(page=page, per_page=per_page, error_out=False)
    comments = pagination.items
    return render_template("story/story_comments.html", story=story, comments=comments, pagination=pagination, user=user)
