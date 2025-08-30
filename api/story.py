import subprocess
from flask import Blueprint, send_file, flash, request, redirect, url_for, jsonify
from helpers import notify, get_current_user, is_authenticated, is_story_author_or_admin, is_comment_author_or_admin, get_image_url
from models import User, Story, Comment, Chapter, Notification, Tag, db, StoryArc, ChapterGuide, Character, Location
import json
import io

bp = Blueprint('story', __name__)

@bp.route('/api/update_arc_combined/<int:mapping_id>', methods=["PUT"])
@is_story_author_or_admin
def update_arc_combined(mapping_id):
    """
	Update the detailed story arc mapping with new text, characters, and locations.
    
    This function retrieves the current user's information and updates the specified 
    story arc mapping based on the provided JSON data. It validates the input data 
    for the story ID, characters, and locations before committing the changes to the 
    database. If any validation fails, it returns an appropriate error message.
    
    Args:
        mapping_id (int): The ID of the story arc mapping to be updated.
    
    Returns:
        Response: A JSON response indicating the success or failure of the update 
        operation, along with an appropriate HTTP status code.
        
    Raises:
        400: If no new arc text is provided, if there is a story ID mismatch, or if 
        any character or location names are invalid.
    """
    user = get_current_user()
    data = request.json
    story_id = data.get("story_id")
    new_text = data.get("part_text")
    new_characters = data.get("characters", [])
    print(new_characters)
    new_locations = data.get("locations", [])
    
    if not new_text:
        return jsonify({"error": "No new arc text provided."}), 400

    mapping = ChapterGuide.query.get_or_404(mapping_id)
    if mapping.story_id != int(story_id):
        return jsonify({"error": "Story ID mismatch."}), 400

    valid_chars = [c.name for c in Character.query.filter_by(story_id=story_id).all()]
    for ch in new_characters:
        if ch not in valid_chars:
            return jsonify({"error": f"Invalid character name: {ch}"}), 400

    valid_locs = [l.name for l in Location.query.filter_by(story_id=story_id).all()]
    for loc in new_locations:
        if loc not in valid_locs:
            return jsonify({"error": f"Invalid location name: {loc}"}), 400

    mapping.part_text = new_text
    mapping.characters = new_characters
    mapping.locations = new_locations
    db.session.commit()
    notify("Detailed Arc Mapping Updated", user.id)
    return jsonify({"message": "Detailed arc mapping updated."})


@bp.route('/api/delete_detailed_arc_mapping/<int:mapping_id>', methods=["DELETE"])
@is_story_author_or_admin
def delete_detailed_arc_mapping(mapping_id):
    """
	Deletes a detailed story arc mapping from the database.
    
    This function retrieves the current user, extracts the story ID from the request JSON, 
    and deletes the specified detailed story arc mapping identified by the given mapping ID. 
    It commits the changes to the database and sends a notification about the deletion.
    
    Args:
        mapping_id (int): The ID of the detailed story arc mapping to be deleted.
    
    Returns:
        flask.Response: A JSON response indicating the success of the deletion.
    
    Raises:
        NotFound: If the mapping with the specified ID does not exist.
    """
    user = get_current_user()
    data = request.json
    story_id = data.get("story_id")
    mapping = ChapterGuide.query.get_or_404(mapping_id)
    db.session.delete(mapping)
    db.session.commit()
    notify("Detailed Arc Mapping Deleted", user.id)
    return jsonify({"message": "Detailed arc mapping deleted."})

@bp.route('/api/save_new_arc_part', methods=["POST"])
@is_story_author_or_admin
def save_new_arc_part():
    """
	Saves a new arc part to the database.
    
    This function retrieves the current user and the JSON data from the request. It extracts the `story_id`, `chapter_title`, and `part_text` from the data. If any of these values are missing, it returns a 400 error response. If all required data is present, it checks for existing parts in the database for the specified story and chapter, determines the next index for the new part, and creates a new `ChapterGuide` entry. Finally, it commits the new mapping to the database and sends a notification about the addition.
    
    Returns:
        Response: A JSON response indicating the success of the operation, including the new mapping ID if successful, or an error message if data is missing.
    """
    user = get_current_user()
    data = request.json
    story_id = data.get("story_id")
    chapter_title = data.get("chapter_title")
    part_text = data.get("part_text")
    if not story_id or not chapter_title or not part_text:
        return jsonify({"error": "Missing data for new arc part."}), 400
    current_parts = ChapterGuide.query.filter_by(story_id=story_id, chapter_title=chapter_title).all()
    new_index = max([part.part_index for part in current_parts], default=0) + 1
    mapping = ChapterGuide(
        story_id=story_id,
        chapter_title=chapter_title,
        part_index=new_index,
        part_text=part_text,
        characters=[],
        locations=[]
    )
    db.session.add(mapping)
    db.session.commit()
    notify("New Detailed Arc Part Added", user.id)
    return jsonify({"message": "New arc part added.", "new_mapping_id": mapping.id})

@bp.route('/api/update_arc_order', methods=["POST"])
@is_story_author_or_admin
def update_arc_order():
    """
	Updates the order of chapters in a detailed story arc based on the provided data.
    
    This function retrieves the current user and processes a JSON request to update the order of chapters in a story arc. It validates the input data, updates the chapter order in the database, and commits the changes. If any errors occur during the process, appropriate error messages are returned.
    
    Args:
        None
    
    Returns:
        flask.Response: A JSON response indicating the success or failure of the update operation.
    
    Raises:
        ValueError: If the provided story_id is not a valid integer.
        KeyError: If required data fields are missing from the request.
    
    Example:
        {
            "story_id": 1,
            "chapter_title": "Chapter One",
            "new_order": [
                {"mapping_id": 1, "new_index": 0},
                {"mapping_id": 2, "new_index": 1}
            ]
        }
    """
    user = get_current_user()
    data = request.json
    try:
        story_id = int(data.get("story_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid story_id."}), 400

    chapter_title = data.get("chapter_title", "").strip()
    new_order = data.get("new_order")
    if not story_id or not chapter_title or not new_order:
        return jsonify({"error": "Missing data for updating order."}), 400

    for order in new_order:
        mapping_id = order.get("mapping_id")
        new_index = order.get("new_index")
        mapping = ChapterGuide.query.get(mapping_id)
        if mapping and mapping.story_id == story_id and mapping.chapter_title.strip() == chapter_title:
            print(f"Updating mapping {mapping_id}: {mapping.part_index} -> {new_index}")
            mapping.part_index = new_index
        else:
            print(f"Mapping {mapping_id} not found or does not match chapter/story.")
    db.session.commit()
    notify("Detailed Arc Order Updated", user.id)
    return jsonify({"message": "Arc order updated successfully."})

@bp.route('/api/update_story_arc_order', methods=["POST"])
@is_story_author_or_admin
def update_story_arc_order():
    """
	Updates the order of story arcs for a given story.
    
    This function retrieves the current user and the JSON data from the request. It attempts to extract the `story_id` and `new_order` from the data. If the `story_id` is invalid or missing, or if the `new_order` is not provided, it returns an error response. For each order in `new_order`, it updates the `arc_order` of the corresponding `StoryArc` if it belongs to the specified story. Finally, it commits the changes to the database and sends a notification about the update.
    
    Returns:
        Response: A JSON response indicating the success or failure of the operation.
        
    Raises:
        ValueError: If the `story_id` cannot be converted to an integer.
        TypeError: If the `story_id` or `new_order` is missing from the request data.
    """
    user = get_current_user()
    data = request.json
    try:
        story_id = int(data.get("story_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid story_id."}), 400

    new_order = data.get("new_order")
    if not story_id or not new_order:
        return jsonify({"error": "Missing data for updating order."}), 400

    for order in new_order:
        arc_id = order.get("arc_id")
        new_index = order.get("new_index")
        arc = StoryArc.query.get(arc_id)
        if arc and arc.story_id == story_id:
            print(f"Updating arc {arc_id}: {arc.arc_order} -> {new_index}")
            arc.arc_order = new_index
        else:
            print(f"Arc {arc_id} not found or does not belong to story {story_id}.")
    db.session.commit()
    notify("Story Arc Order Updated", user.id)
    return jsonify({"message": "Arc order updated successfully."})

@bp.route('/api/update_chapter_order', methods=["POST"])
@is_story_author_or_admin
def update_chapter_order():
    """
	Update the order of chapters in a story.
    
    This function retrieves the current user and the JSON data from the request to update the order of chapters based on the provided `story_id` and `new_order`. It validates the input data and updates the chapter numbers accordingly. If the chapter does not belong to the specified story or if the input data is invalid, appropriate error messages are returned.
    
    Returns:
        Response: A JSON response indicating the success or failure of the operation.
    
    Raises:
        ValueError: If the `story_id` cannot be converted to an integer.
        TypeError: If the `story_id` or `new_order` is missing from the request data.
    """
    user = get_current_user()
    data = request.json
    try:
        story_id = int(data.get("story_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid story_id."}), 400

    new_order = data.get("new_order")
    if not story_id or not new_order:
        return jsonify({"error": "Missing data for updating order."}), 400

    for order in new_order:
        chapter_id = order.get("chapter_id")
        new_index = order.get("new_index")
        chapter = Chapter.query.get(chapter_id)
        if chapter and chapter.story_id == story_id:
            print(f"Updating chapter {chapter_id}: {chapter.chapter_number} -> {new_index}")
            chapter.chapter_number = new_index
        else:
            print(f"Chapter {chapter_id} not found or does not belong to story {story_id}.")
    db.session.commit()
    notify("Chapter Order Updated", user.id)
    return jsonify({"message": "Chapter order updated successfully."})

@bp.route('/api/list_characters/<int:story_id>', methods=["GET"])
@is_story_author_or_admin
def list_characters(story_id):
    """
	Retrieve a list of character names associated with a specific story.
    
    Args:
        story_id (int): The unique identifier of the story for which to retrieve characters.
    
    Returns:
        flask.Response: A JSON response containing a list of character names.
    """
    characters = Character.query.filter_by(story_id=story_id).all()
    data = [c.name for c in characters]
    return jsonify(data)

@bp.route('/api/list_locations/<int:story_id>', methods=["GET"])
@is_story_author_or_admin
def list_locations(story_id):
    """
	Retrieve a list of location names associated with a specific story.
    
    Args:
        story_id (int): The ID of the story for which to retrieve locations.
    
    Returns:
        flask.Response: A JSON response containing a list of location names.
    """
    locations = Location.query.filter_by(story_id=story_id).all()
    data = [l.name for l in locations]
    return jsonify(data)

@bp.route('/story/<int:story_id>', methods=["POST"])
@is_story_author_or_admin
def edit_story(story_id):
    """
	Edit an existing story with the provided details.
    
    This function retrieves the current user and the story specified by the 
    story_id. It updates the story's title, details, writing style, inspirations, 
    chapters count, maturity status, and shared status based on the form data 
    submitted by the user. It also manages the story's tags by adding new tags 
    and removing any that are no longer associated with the story. If the user 
    is under review, the story will not be marked as shared.
    
    Args:
        story_id (int): The unique identifier of the story to be edited.
    
    Returns:
        Response: A redirect to the overview view of the edited story.
    
    Raises:
        NotFound: If the story with the given story_id does not exist.
    """
    user = get_current_user()
    story = Story.query.get_or_404(story_id)
    story.title = request.form.get("title")
    story.details = request.form.get("details")
    story.writing_style = request.form.get("writing_style")
    story.inspirations = request.form.get("inspirations")
    story.chapters_count = int(request.form.get("chapters_count") or 20)
    story.is_mature = True if request.form.get("mature") == "on" else False
    story.shared = True if request.form.get("shared") == "on" else False
    if user.under_review:
        story.shared = False
    tags_json = request.form.get("tags")
    try:
        tag_items = json.loads(tags_json) if tags_json else []
    except Exception:
        tag_items = []
    new_tag_ids = {int(item.get("id")) for item in tag_items if item.get("id")}
    current_tag_ids = {tag.id for tag in story.tags}
    if new_tag_ids:
        new_tags_dict = {tag.id: tag for tag in Tag.query.filter(Tag.id.in_(new_tag_ids)).all()}
    else:
        new_tags_dict = {}
    for tag_id in new_tag_ids - current_tag_ids:
        tag = new_tags_dict.get(tag_id)
        if tag:
            story.tags.append(tag)
    for tag in list(story.tags):
        if tag.id not in new_tag_ids:
            story.tags.remove(tag)
    db.session.commit()
    flash("Story Saved")
    return redirect(url_for("story_views.overview", story_id=story.id))
    
@bp.route('/api/delete_story/<int:story_id>', methods=["DELETE"])
@is_story_author_or_admin
def delete_story(story_id):
    """
	Deletes a story and its associated data from the database.
    
    This function retrieves a story by its ID, deletes the story along with its related characters, locations, and detailed story arc mappings. It also removes any images associated with the story. If the deletion is successful, a success message is flashed to the user.
    
    Args:
        story_id (int): The ID of the story to be deleted.
    
    Returns:
        jsonify: A JSON response indicating the deletion status.
    
    Raises:
        HTTPException: If the story with the given ID is not found.
        Exception: If an error occurs during the deletion process.
    """
    try:
        from helpers import delete_images_for_story
        story = Story.query.get_or_404(story_id)
        db.session.delete(story)
        Character.query.filter_by(story_id=story.id).delete()
        Location.query.filter_by(story_id=story.id).delete()
        ChapterGuide.query.filter_by(story_id=story.id).delete()
        db.session.commit()
        delete_images_for_story(story_id)
    except:
        print("error")
    flash("Story Deleted")
    return jsonify({"deleted": True})

@bp.route('/story/new', methods=["POST"])
@is_authenticated
def new_story():
    """
	Creates a new story based on user input from a web form.
    
    This function retrieves the current user and gathers various details 
    about the story, including the title, details, writing style, inspirations, 
    number of chapters, and tags. It checks if the story is mature and whether 
    it should be shared based on user preferences and status. The function 
    also handles the parsing of tags from JSON format and associates them 
    with the new story. Finally, it saves the story to the database and 
    redirects the user to the edit page for the newly created story.
    
    Returns:
        Redirect: A redirect response to the edit page of the newly created story.
    
    Raises:
        Exception: If there is an error while parsing the tags JSON.
    """
    user = get_current_user()
    title = request.form.get("title")
    details = request.form.get("details")
    writing_style = request.form.get("writing_style")
    inspirations = request.form.get("inspirations")
    chapters_count = int(request.form.get("chapters_count") or 3)
    is_mature = True if request.form.get("mature") == "on" else False
    shared = True if request.form.get("shared") == "on" else False
    if user.under_review:
        shared = False
    tags_json = request.form.get("tags")
    try:
        tag_items = json.loads(tags_json)
    except Exception:
        tag_items = []
    tag_list = []
    for item in tag_items:
        tag_id = item.get("id")
        if tag_id:
            tag = Tag.query.get(tag_id)
            if tag:
                tag_list.append(tag)
    story = Story(title=title, is_mature=is_mature, writing_style=writing_style, inspirations=inspirations, shared=shared, details=details, chapters_count=chapters_count, user_id=user.id)
    story.tags = tag_list
    db.session.add(story)
    db.session.commit()
    flash("Story Created")
    return redirect(url_for("story.edit_story", story_id=story.id))

@bp.route('/api/update_meta', methods=["POST"])
@is_story_author_or_admin
def update_meta():
    """
	Updates the metadata for a story by adding or modifying characters and locations.
    
    This function retrieves the current user and the JSON data from the request, which should include
    the story ID, a list of characters, and a list of locations. It deletes existing characters and
    locations associated with the story and then adds the new ones provided in the request.
    
    Args:
        None
    
    Returns:
        flask.Response: A JSON response indicating the success of the update operation.
    
    Raises:
        NotFound: If the story with the given ID does not exist.
    
    Side Effects:
        Modifies the database by deleting existing characters and locations and adding new ones.
        Sends a notification to the current user indicating that the metadata has been saved.
    """
    user = get_current_user()
    data = request.json
    story_id = data.get("story_id")
    characters_data = data.get("characters", [])
    locations_data = data.get("locations", [])
    
    story = Story.query.get_or_404(story_id)
    
    Character.query.filter_by(story_id=story_id).delete()
    Location.query.filter_by(story_id=story_id).delete()
    
    for char in characters_data:
        name = char.get("name")
        description = char.get("description", "")
        example_dialogue = char.get("example_dialogue", "")
        if name:
            new_char = Character(story_id=story_id, name=name, description=description, example_dialogue=example_dialogue)
            db.session.add(new_char)
    
    for loc in locations_data:
        name = loc.get("name")
        description = loc.get("description", "")
        if name:
            new_loc = Location(story_id=story_id, name=name, description=description)
            db.session.add(new_loc)
    
    db.session.commit()
    notify("Meta saved", user.id)
    return jsonify({"message": "Characters and locations updated."})

@bp.route('/api/save_arcs', methods=["POST"])
@is_story_author_or_admin
def save_arcs():
    """
	Saves story arcs for a given story.
    
    This function retrieves the current user and the JSON data from the request,
    which includes the story ID and an array of arcs. It deletes any existing arcs
    for the specified story and adds the new arcs provided in the request. After
    committing the changes to the database, it sends a notification to the user
    and returns a success message.
    
    Args:
        None
    
    Returns:
        flask.Response: A JSON response indicating that the story arcs have been saved.
    
    Raises:
        NotFound: If the story with the given story_id does not exist.
    """
    user = get_current_user()
    data = request.json
    story_id = data.get("story_id")
    arcs_array = data.get("arcs", [])
    
    story = Story.query.get_or_404(story_id)
    
    StoryArc.query.filter_by(story_id=story_id).delete()
    
    for arc_text in arcs_array:
        if arc_text.strip():
            new_arc = StoryArc(story_id=story_id, arc_text=arc_text.strip())
            db.session.add(new_arc)
    
    db.session.commit()
    notify("Story arcs saved", user.id)
    return jsonify({"message": "Story arcs saved."})

@bp.route('/api/save_field', methods=["POST"])
@is_story_author_or_admin
def api_save_field():
    """
	Saves field data for a story, specifically handling Chapter Summaries.
    
    This function retrieves the current user and the JSON data from the request. 
    It updates or creates chapters for a story based on the provided field and value. 
    If the field is 'chapter_summaries', it expects a JSON array of chapter data, 
    validates it, and updates the corresponding chapters in the database. 
    If the field is anything else, it updates the specified field of the story directly.
    
    Args:
        None
    
    Returns:
        flask.Response: A JSON response indicating the success or failure of the operation.
        
    Raises:
        400: If the provided JSON for Chapter Summaries is invalid.
        404: If the story with the given story_id does not exist.
    """
    user = get_current_user()
    data = request.json
    story_id = data.get("story_id")
    field = data.get("field")
    value = data.get("value")
    story = Story.query.get_or_404(story_id)

    if field == 'chapter_summaries':
        try:
            new_data = json.loads(value) if isinstance(value, str) else value
        except Exception as e:
            return jsonify({"error": "Invalid JSON for chapter_summaries."}), 400

        for index, item in enumerate(new_data, start=1):
            chapter_id = item.get("id")
            title = item.get("name")
            summary = item.get("description", "")
            if chapter_id:
                chapter = Chapter.query.filter_by(id=chapter_id, story_id=story.id).first()
                if chapter:
                    chapter.title = title
                    chapter.summary = summary
                    chapter.chapter_number = index
                else:
                    chapter = Chapter(story_id=story.id, title=title, summary=summary, chapter_number=index)
                    db.session.add(chapter)
            else:
                chapter = Chapter(story_id=story.id, title=title, summary=summary, chapter_number=index)
                db.session.add(chapter)
        new_ids = {item.get("id") for item in new_data if item.get("id")}
        existing_chapters = Chapter.query.filter_by(story_id=story.id).all()
        for ch in existing_chapters:
            if new_ids and ch.id not in new_ids:
                db.session.delete(ch)
        story.chapters_count = len(new_data)
        db.session.commit()
        notify("Chapter Summaries Saved!", user.id)
        return jsonify({"message": "Chapter Summaries saved."})
    else:
        setattr(story, field, value)
        db.session.commit()
    notify("Saved!", user.id)
    return jsonify({"message": f"{field} saved."})

@bp.route('/api/update_chapter_summaries', methods=["POST"])
@is_story_author_or_admin
def update_chapter_summaries():
    """
	Update Chapter Summaries for a given story.
    
    This function retrieves the current user's information and updates the Chapter Summaries 
    for a specified story based on the provided JSON payload. It handles both updating existing 
    chapters and creating new ones. If any chapters are not included in the payload, they will 
    be deleted from the database. The function also updates the chapter count for the story.
    
    Returns:
        flask.Response: A JSON response indicating the success or failure of the operation.
    
    Raises:
        400: If the story_id is missing from the request data.
        404: If the story with the given story_id does not exist.
    """
    user = get_current_user()
    data = request.json
    story_id = data.get("story_id")
    chapters_payload = data.get("chapters", [])
    
    if not story_id:
        return jsonify({"error": "Missing story_id."}), 400
    
    story = Story.query.get_or_404(story_id)
    
    updated_chapter_ids = set()
    
    for index, chapter_data in enumerate(chapters_payload, start=1):
        title = chapter_data.get("title")
        summary = chapter_data.get("summary", "")
        chapter_id = chapter_data.get("id")
        if not title:
            continue
        
        if chapter_id:
            chapter = Chapter.query.filter_by(id=chapter_id, story_id=story_id).first()
            if chapter:
                chapter.title = title
                chapter.summary = summary
                chapter.chapter_number = index
                updated_chapter_ids.add(chapter.id)
            else:
                new_chapter = Chapter(story_id=story_id, title=title, summary=summary, chapter_number=index)
                db.session.add(new_chapter)
                db.session.flush()
                updated_chapter_ids.add(new_chapter.id)
        else:
            new_chapter = Chapter(story_id=story_id, title=title, summary=summary, chapter_number=index)
            db.session.add(new_chapter)
            db.session.flush()
            updated_chapter_ids.add(new_chapter.id)
    
    existing_chapters = Chapter.query.filter_by(story_id=story_id).all()
    for chapter in existing_chapters:
        if chapter.id not in updated_chapter_ids:
            db.session.delete(chapter)
    
    story.chapters_count = len(chapters_payload)
    db.session.commit()
    notify("Chapter Summaries Saved!", user.id)
    return jsonify({"message": "Chapter Summaries saved."})


@bp.route('/api/save_chapter', methods=["POST"])
@is_story_author_or_admin
def save_chapter():
    """
	Saves a chapter to the database. If a chapter with the specified story ID and chapter number already exists, it updates the content of that chapter. Otherwise, it creates a new chapter entry.
    
    Args:
        story_id (str): The ID of the story to which the chapter belongs.
        chapter_number (int): The number of the chapter to be saved or updated.
        content (str): The content of the chapter.
    
    Returns:
        flask.Response: A JSON response indicating the success of the operation.
    
    Raises:
        ValueError: If chapter_number is not convertible to an integer.
    """
    data = request.json
    story_id = data.get("story_id")
    chapter_number = int(data.get("chapter_number"))
    content = data.get("content")
    chapter = Chapter.query.filter_by(story_id=story_id, chapter_number=chapter_number).first()
    
    if chapter:
        chapter.content = content
    else:
        chapter = Chapter(story_id=story_id, chapter_number=chapter_number, content=content)
        db.session.add(chapter)
    db.session.commit()
    notify("Chapter Saved", user.id)
    return jsonify({"success": True})

@bp.route('/api/toggle_favorite/<int:story_id>', methods=["POST"])
@is_authenticated
def toggle_favorite(story_id):
    """
	Toggle the favorite status of a story for the current user.
    
    This function allows a user to add or remove a story from their list of favorite stories. 
    It checks if the user is trying to favorite their own story or if the story is shared. 
    If the story is already favorited, it will be removed; otherwise, it will be added to the user's favorites.
    
    Args:
        story_id (int): The ID of the story to be favorited or unfavorited.
    
    Returns:
        flask.Response: A JSON response indicating the new favorite status and the updated favorites count.
        
    Raises:
        HTTPException: If the story is not found or if the user does not have permission to favorite the story.
    """
    user = get_current_user()
    story = Story.query.get_or_404(story_id)
    if user.id == story.user_id:
        return jsonify({"error": "You cannot favorite your own story."}), 403
    if not story.shared:
        return jsonify({"error": "You do not have permission to favorite this story."}), 403
    
    if user.favorite_stories.filter_by(id=story.id).first():
        user.favorite_stories.remove(story)
        story.favorites_count = (story.favorites_count or 0) - 1
        status = False
        notify("Removed from favorites", user.id)
    else:
        user.favorite_stories.append(story)
        story.favorites_count = (story.favorites_count or 0) + 1
        status = True
        notify("Added to favorites", user.id)
    
    db.session.commit()
    return jsonify({"favorite": status, "favorites_count": story.favorites_count})

@bp.route('/story/flag/<int:story_id>', methods=['POST'])
@is_authenticated
def flag_story(story_id):
    """
	Flag or unflag a story based on the user's action.
    
    This function allows a user to flag a story as inappropriate or to remove their flag from a story they previously flagged. It checks if the story is publicly shared, ensures that the user is not flagging their own story, and manages the flagging status accordingly. If a story receives five flags, it will be marked as not shared and flagged for review.
    
    Args:
        story_id (int): The ID of the story to be flagged or unflagged.
    
    Returns:
        Response: A JSON response indicating the result of the flagging action, including any error messages or the current flag count.
    """
    user = get_current_user()
    story = Story.query.get_or_404(story_id)
    
    if not story.shared:
        return jsonify({"error": "This story is not shared publicly."}), 403

    if story.user_id == user.id:
        return jsonify({"error": "You cannot flag your own story."}), 403

    if story.flaggers.filter_by(id=user.id).first():
        story.flaggers.remove(user)
        db.session.commit()
        return jsonify({"message": "Flag removed.", "flag_count": story.flaggers.count()})
    
    story.flaggers.append(user)
    db.session.commit()
    
    flag_count = story.flaggers.count()
    
    if flag_count >= 5:
        story.shared = False
        story.flagged = True
        
        story.flaggers = []
        
        author = User.query.get(story.user_id)
        if author:
            author.under_review = True
        
        db.session.commit()
        return jsonify({"message": "Story has been flagged and removed from public view.", "flag_count": 0})
    
    return jsonify({"message": "Story flagged.", "flag_count": flag_count})

@bp.route('/story/<int:story_id>/comments', methods=["POST"])
@is_authenticated
def new_comment(story_id):
    """
	Adds a new comment to a story.
    
    This function retrieves the current user and the specified story by its ID. 
    It checks if the story is private and whether the user has permission to comment. 
    If the comment message is empty, it flashes an error message and redirects the user 
    to the story comments view. If the comment is valid, it creates a new comment 
    and saves it to the database. If the comment is made by a user other than the story owner, 
    a notification is created for the story owner.
    
    Args:
        story_id (int): The ID of the story to which the comment is being added.
    
    Returns:
        tuple: A redirect response to the story comments view or an error message 
               with a status code if the user is not authorized to comment or if the 
               comment message is empty.
    """
    user = get_current_user()
    story = Story.query.get_or_404(story_id)
    if not story.shared and (user.id != story.user_id and user.role.name.lower() != 'admin'):
        return "This story is private.", 403

    message = request.form.get("message")
    if not message:
        flash("Comment cannot be empty.", "error")
        return redirect(url_for("story_views.story_comments", story_id=story.id))
    
    comment = Comment(story_id=story.id, user_id=user.id, username=user.username, message=message)
    db.session.add(comment)
    db.session.commit()
    
    if story.user_id != user.id:
        notif_message = f"{user.username} commented on your story '{story.title}'."
        notification = Notification(user_id=story.user_id, story_id=story_id, message=notif_message)
        db.session.add(notification)
        db.session.commit()
    
    flash("Comment posted.", "success")
    return redirect(url_for("story_views.story_comments", story_id=story.id))

@bp.route('/comment/<int:comment_id>/edit', methods=["POST"])
@is_comment_author_or_admin
def edit_comment(comment_id):
    """
	Edit a comment by its ID.
    
    This function retrieves the current user and the comment specified by the 
    provided comment ID. It updates the comment's message with the new message 
    from the request form. If the new message is empty, it flashes an error 
    message and redirects the user back to the comments view. If the update is 
    successful, it flashes a success message and redirects to the comments view.
    
    Args:
        comment_id (int): The ID of the comment to be edited.
    
    Returns:
        Response: A redirect response to the comments view of the associated story.
    
    Raises:
        NotFound: If the comment with the specified ID does not exist.
    """
    user = get_current_user()
    comment = Comment.query.get_or_404(comment_id)
    
    new_message = request.form.get("message")
    if not new_message:
        flash("Comment cannot be empty.", "error")
        return redirect(url_for("story_views.story_comments", story_id=comment.story_id))
    
    comment.message = new_message
    db.session.commit()
    flash("Comment updated.", "success")
    return redirect(url_for("story_views.story_comments", story_id=comment.story_id))

@bp.route('/comment/<int:comment_id>/delete', methods=["POST"])
@is_comment_author_or_admin
def delete_comment(comment_id):
    """
	Deletes a comment from the database.
    
    This function retrieves the current user, fetches the comment by its ID, 
    deletes the comment from the database, and commits the changes. 
    It then flashes a success message and redirects the user to the 
    story comments view associated with the deleted comment.
    
    Args:
        comment_id (int): The ID of the comment to be deleted.
    
    Returns:
        werkzeug.wrappers.Response: A redirect response to the story comments view.
    
    Raises:
        NotFound: If the comment with the specified ID does not exist.
    """
    user = get_current_user()
    comment = Comment.query.get_or_404(comment_id)
    
    story_id = comment.story_id
    db.session.delete(comment)
    db.session.commit()
    flash("Comment deleted.", "success")
    return redirect(url_for("story_views.story_comments", story_id=story_id))

@bp.route('/api/search_public_stories', methods=["GET"])
@is_authenticated
def api_search_public_stories():
    """
	Search for public stories based on user-defined filters and return paginated results.
    
    This function retrieves public stories that are shared and not marked as spotlight. It allows filtering by tags, sorting by favorites or creation date, and pagination. The function also checks the user's preference for mature content and adjusts the query accordingly.
    
    Args:
        tags (str): A comma-separated string of tags to filter the stories. Default is an empty string.
        page (int): The page number for pagination. Default is 1.
        sort_by (str): The field to sort the results by. Can be 'favorites' or 'date'. Default is 'date'.
        order (str): The order of sorting. Can be 'asc' for ascending or 'desc' for descending. Default is 'desc'.
    
    Returns:
        flask.Response: A JSON response containing the paginated list of stories, along with pagination metadata.
            - stories (list): A list of dictionaries representing the stories, each including the author's username.
            - page (int): The current page number.
            - total_pages (int): The total number of pages available.
            - has_next (bool): Indicates if there is a next page.
            - has_prev (bool): Indicates if there is a previous page.
            - next_page (int or None): The next page number if available, otherwise None.
            - prev_page (int or None): The previous page number if available, otherwise None.
    """
    user = get_current_user()
    tags = request.args.get('tags', '')
    page = request.args.get('page', 1, type=int)
    sort_by = request.args.get('sort_by', 'date')
    order = request.args.get('order', 'desc')
    show_mature = user.show_mature

    query = Story.query.filter_by(shared=True)
    query = query.filter(Story.chapters.any())
    if not show_mature:
        query = query.filter(Story.is_mature == False)
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        for t in tag_list:
            query = query.filter(Story.tags.any(Tag.name.ilike(f"%{t}%")))
    
    if sort_by == 'favorites':
        order_column = Story.favorites_count
    elif sort_by == 'chapters':
        order_column = Story.chapters_count  # assumes you have this column in your model
    else:
        order_column = Story.created_at
    order_clause = order_column.asc() if order == 'asc' else order_column.desc()

    pagination = query.order_by(order_clause).paginate(page=page, per_page=9, error_out=False)
    stories = pagination.items
    for story in stories:
        author = User.query.get(story.user_id)
        story.author = author.username if author else "Unknown"
        story.presigned_cover_url = get_image_url(story.cover_image_key)

    data = {
        "stories": [dict(story.to_dict(), author=story.author, presigned_cover_url=story.presigned_cover_url) for story in stories],
        "page": pagination.page,
        "total_pages": pagination.pages,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
        "next_page": pagination.next_num if pagination.has_next else None,
        "prev_page": pagination.prev_num if pagination.has_prev else None,
    }
    return jsonify(data)

@bp.route('/api/tags', methods=["GET"])
@is_authenticated
def tags():
    """
	Retrieve a list of tags based on a search query.
    
    This function checks for a query parameter in the request. If a query is provided, it filters the tags whose names match the query (case-insensitive). If no query is provided, it retrieves all tags. The result is returned as a JSON response containing a list of tag objects with their IDs and names.
    
    Returns:
        flask.Response: A JSON response containing a list of dictionaries, each representing a tag with its 'id' and 'value' (name).
    """
    query = request.args.get("query", "").strip()
    if query:
        tags = Tag.query.filter(Tag.name.ilike(f"%{query}%")).all()
    else:
        tags = Tag.query.all()
    suggestions = [{"id": tag.id, "value": tag.name} for tag in tags]
    return jsonify(suggestions)

@bp.route('/api/generate_epub', methods=["POST"])
@is_authenticated
def api_generate_epub():
    """
	Generates an EPUB file from a story's content and sends it as a downloadable file.
    
    This function retrieves the current user and the story ID from the request JSON. It checks if the user has permission to access the story, either by verifying if the story is shared or if the user is the owner. If the user does not have permission, a 403 error is returned. 
    
    If the story has final markdown, it uses that; otherwise, it compiles the markdown from the story's chapters. The function then uses Pandoc to convert the markdown to an EPUB format. If the conversion fails, a 500 error is returned with the error message. If successful, the EPUB file is sent to the user as a downloadable attachment.
    
    Returns:
        Response: A Flask response object containing the EPUB file or an error message.
    """
    user = get_current_user()
    data = request.json
    story_id = data.get("story_id")
    story = Story.query.get_or_404(story_id)
    
    if not (story.shared or story.user_id == user.id):
        return jsonify({"error": "You do not have permission to access this story."}), 403

    if story.final_markdown:
        combined_md = story.final_markdown
    else:
        chapters = Chapter.query.filter_by(story_id=story.id).order_by(Chapter.chapter_number).all()
        combined_md = (
            f"# {story.title}\n\n"
            f"**Date:** {story.created_at.strftime('%B %d, %Y')}\n\n"
        )
        for chapter in chapters:
            combined_md += (
                f"# Chapter {chapter.chapter_number}: {chapter.title}\n\n"
                f"{chapter.content}\n\n"
            )

    cmd = [
        "pandoc",
        "--from", "markdown",
        "--to", "epub",
        "--epub-chapter-level=2",
        "--metadata", f"title={story.title}",
        "--metadata", "language=English",
        "-"
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    epub_data, err = proc.communicate(input=combined_md.encode("utf-8"))

    if proc.returncode != 0:
        return jsonify({"error": err.decode("utf-8")}), 500

    return send_file(
        io.BytesIO(epub_data),
        mimetype="application/epub+zip",
        as_attachment=True,
        download_name="novel.epub"
    )