import eventlet
eventlet.monkey_patch(all=False, socket=True)
import redis
from flask import Blueprint, request, jsonify
from helpers import notify, get_current_user, is_story_author_or_admin, can_spend_credits
from predictions import (
    calculate_predicted_story_arcs_cost,
    calculate_predicted_meta_cost,
    calculate_predicted_summaries_cost,
    calculate_predicted_chapter_cost,
    calculate_predicted_all_chapters_cost,
    calculate_predicted_chapter_guide_cost,
    calculate_predicted_story_arcs_cost,
    calculate_image_cost
)
from models import Story, Chapter, GenerationLog, db, Character, Location, ChapterGuide
from prompt_templates import (
    build_meta_prompt,
    build_story_arcs_prompt,
    build_chapter_guide_prompt,
    build_chapter_summaries_prompt,
    build_chapter_content_prompt
)
import json

bp = Blueprint('generation', __name__)
locking_queue = redis.StrictRedis(host='localhost', port=6379, db=2, decode_responses=True)

def set_user_generation_lock(user_id, expire=2000):
    """
	Sets a generation lock for a user.
    
    This function attempts to set a lock for a user identified by `user_id` to prevent 
    concurrent generation processes. The lock will expire after a specified duration.
    
    Args:
        user_id (str): The unique identifier of the user for whom the lock is being set.
        expire (int, optional): The expiration time for the lock in seconds. Defaults to 2000.
    
    Returns:
        bool: True if the lock was successfully set, False otherwise.
    """
    key = f"generation_lock:{user_id}"
    was_set = locking_queue.set(key, "1", ex=expire, nx=True)
    return was_set

def clear_user_generation_lock(user_id):
    """
	Clears the generation lock for a specified user.
    
    This function removes the generation lock associated with the given user ID
    from the locking queue, allowing the user to initiate a new generation process.
    
    Args:
        user_id (str): The unique identifier of the user whose generation lock
            is to be cleared.
    
    Returns:
        None
    """
    key = f"generation_lock:{user_id}"
    locking_queue.delete(key)

@bp.route('/api/predict_meta_cost/<int:story_id>', methods=["GET"])
@is_story_author_or_admin
def predict_meta_cost(story_id):
    """
	Predicts the meta cost for a given story.
    
    Args:
        story_id (int): The unique identifier of the story for which the meta cost is to be predicted.
    
    Returns:
        flask.Response: A JSON response containing the total predicted credit cost if the story is found,
                        or a 404 error message if the story is not found.
    """
    story = Story.query.get(story_id)
    if not story:
        return jsonify({"error": "Story not found."}), 404
    prediction = calculate_predicted_meta_cost(story)
    return jsonify({
        "total_predicted_credit_cost": prediction.get('total_predicted_credit_cost')
    })

@bp.route('/api/predict_arcs_cost/<int:story_id>', methods=["GET"])
@is_story_author_or_admin
def predict_arcs_cost(story_id):
    """
	Predicts the total credit cost for story arcs based on the given story ID.
    
    Args:
        story_id (int): The unique identifier of the story for which the cost prediction is to be made.
    
    Returns:
        flask.Response: A JSON response containing the total predicted credit cost if the story is found,
                        or a 404 error message if the story is not found.
    
    Raises:
        NotFound: If the story with the given ID does not exist in the database.
    """
    story = Story.query.get(story_id)
    if not story:
        return jsonify({"error": "Story not found."}), 404
    prediction = calculate_predicted_story_arcs_cost(story)
    return jsonify({
        "total_predicted_credit_cost": prediction.get('total_predicted_credit_cost')
    })

@bp.route('/api/predict_chapter_guide_cost/<int:story_id>', methods=["GET"])
@is_story_author_or_admin
def predict_chapter_guide_cost(story_id):
    """
	Predicts the Chapter Guides cost for a given story.
    
    Args:
        story_id (int): The unique identifier of the story for which the cost is to be predicted.
    
    Returns:
        flask.Response: A JSON response containing the total predicted credit cost if the story is found,
                        or a 404 error message if the story is not found.
    
    Raises:
        NotFound: If the story with the given story_id does not exist.
    """
    story = Story.query.get(story_id)
    if not story:
        return jsonify({"error": "Story not found."}), 404
    prediction = calculate_predicted_chapter_guide_cost(story)
    return jsonify({
        "total_predicted_credit_cost": prediction.get('total_predicted_credit_cost')
    })

@bp.route('/api/predict_summaries_cost/<int:story_id>', methods=["GET"])
@is_story_author_or_admin
def predict_summaries_cost(story_id):
    """
	Predicts the total credit cost for summaries of a given story.
    
    Args:
        story_id (int): The unique identifier of the story for which the 
        predicted summaries cost is to be calculated.
    
    Returns:
        flask.Response: A JSON response containing the total predicted credit 
        cost if the story is found, or a 404 error response if the story 
        does not exist.
    
    Raises:
        None
    """
    story = Story.query.get(story_id)
    if not story:
        return jsonify({"error": "Story not found."}), 404
    prediction = calculate_predicted_summaries_cost(story)
    return jsonify({
        "total_predicted_credit_cost": prediction.get('total_predicted_credit_cost')
    })

@bp.route('/api/predict_chapter_cost/<int:story_id>/<int:chapter_number>', methods=["GET"])
@is_story_author_or_admin
def predict_chapter_cost(story_id, chapter_number):
    """
	Predicts the cost of a specific chapter in a story.
    
    Args:
        story_id (int): The unique identifier of the story.
        chapter_number (int): The chapter number for which the cost is to be predicted.
    
    Returns:
        flask.Response: A JSON response containing the total predicted credit cost of the chapter,
                        or an error message if the story is not found.
    
    Raises:
        404: If the story with the given story_id does not exist.
    """
    story = Story.query.get(story_id)
    if not story:
        return jsonify({"error": "Story not found."}), 404
    chapter_index = chapter_number - 1
    prediction = calculate_predicted_chapter_cost(story, chapter_index)
    return jsonify({
        "total_predicted_credit_cost": prediction.get('total_predicted_credit_cost')
    })

@bp.route('/api/predict_all_chapters_cost/<int:story_id>', methods=["GET"])
@is_story_author_or_admin
def predict_all_chapters_cost(story_id):
    """
	Predicts the total credit cost for all chapters of a given story.
    
    Args:
        story_id (int): The unique identifier of the story for which the cost is to be predicted.
    
    Returns:
        flask.Response: A JSON response containing the total predicted credit cost if the story is found,
                        or a 404 error message if the story is not found.
    
    Raises:
        NotFound: If the story with the given story_id does not exist.
    """
    story = Story.query.get(story_id)
    if not story:
        return jsonify({"error": "Story not found."}), 404
    prediction = calculate_predicted_all_chapters_cost(story)
    return jsonify({
        "total_predicted_credit_cost": prediction.get('total_predicted_credit_cost')
    })

@bp.route('/api/predict_image_cost/<int:story_id>', methods=["GET"])
@is_story_author_or_admin
def predict_image_cost(story_id):
    """
	Predicts the image cost for a given story.
    
    Args:
        story_id (int): The ID of the story for which to predict the image cost.
    
    Returns:
        flask.Response: A JSON response containing the total predicted credit cost 
        if the story is found, or an error message with a 404 status code if the 
        story is not found.
    """
    story = Story.query.get(story_id)
    if not story:
        return jsonify({"error": "Story not found."}), 404
    prediction = calculate_image_cost()
    return jsonify({
        "total_predicted_credit_cost": prediction.get('total_credit_cost')
    })

@bp.route('/api/generate_cover_image', methods=["POST"])
@is_story_author_or_admin
def api_generate_cover_image():
    """
	Generates a cover image for a story based on the provided prompt and story ID.
    
    This function checks the user's credit balance and whether they are eligible to generate an image. 
    If the user has insufficient credits, a notification is sent, and an error response is returned. 
    If the user has enough credits, a background task is initiated to generate the image, and a log entry 
    is created to track the generation process.
    
    Args:
        None
    
    Returns:
        Flask Response: A JSON response indicating the status of the image generation process. 
        If successful, it returns a status of "queued" along with the predicted cost. 
        If there are errors, it returns an error message and appropriate HTTP status codes.
    """
    from helpers import is_last_generation_and_negative_creds
    user = get_current_user()
    if is_last_generation_and_negative_creds(user, "image"):
        notify("Top up your credits to see generation", user.id)
        return jsonify({"error": True})
    from tasks import generate_image_task
    data = request.json
    story_id = data.get("story_id")
    cover_prompt = data.get("cover_prompt")
    story = Story.query.get_or_404(story_id)
    
    story.cover_image_prompt = cover_prompt
    db.session.commit()

    prediction = calculate_image_cost().get('total_credit_cost')
    if not can_spend_credits(user, "image", prediction):
        notify("You don't have enough credits!", user.id)
        return jsonify({
            "error": "Not enough credits.",
            "required": prediction
        }), 400
    try:
        image_key = f"stories/{story_id}/cover.jpg"
        cover_task = generate_image_task.delay(story.id, image_key, cover_prompt, user.id, prediction)
        
        log_entry = GenerationLog(
            user_id=user.id,
            task_id=cover_task.id,
            generation_type="image",
            predicted_cost=prediction,
            real_cost=prediction,
            status="pending"
        )
        db.session.add(log_entry)
        db.session.commit()
        notify("Generating Cover Image...", user.id)
        return jsonify({
            "status": "queued",
            "predicted_cost": prediction
        })
    except Exception as e:
        notify("Cover Image Generation Failed", user.id)
        clear_user_generation_lock(user.id)
        return jsonify({"error": str(e)}), 500


@bp.route('/api/generate_chapter_image', methods=["POST"])
@is_story_author_or_admin
def api_generate_chapter_image():
    """
	Generates an image for a chapter in a story.
    
    This function checks the user's credit balance and generates an image based on the provided chapter prompt. If the user has insufficient credits, a notification is sent, and an error response is returned. The function also logs the generation task and notifies the user about the status of the image generation.
    
    Returns:
        json: A JSON response indicating the status of the image generation. 
              If successful, it returns the status as "queued" along with the predicted cost. 
              If there are errors (e.g., insufficient credits or generation failure), it returns an error message.
    
    Raises:
        Exception: If there is an error during the image generation process.
    """
    from helpers import is_last_generation_and_negative_creds
    user = get_current_user()
    if is_last_generation_and_negative_creds(user, "image"):
        notify("Top up your credits to see generation", user.id)
        return jsonify({"error": True})
    from tasks import generate_image_task
    data = request.json
    story_id = data.get("story_id")
    chapter_id = data.get("chapter_id")
    chapter_prompt = data.get("chapter_prompt")
    
    chapter = Chapter.query.filter_by(story_id=story_id, id=chapter_id).first_or_404()
    
    chapter.chapter_image_prompt = chapter_prompt
    db.session.commit()

    prediction = calculate_image_cost().get('total_credit_cost')
    if not can_spend_credits(user, "image", prediction):
        notify("You don't have enough credits!", user.id)
        return jsonify({
            "error": "Not enough credits.",
            "required": prediction
        }), 400
    try:
        image_key = f"stories/{story_id}/chapters/{chapter_id}.jpg"
        chap_task = generate_image_task.delay(story_id, image_key, chapter_prompt, user.id, prediction, chapter_id)
        
        log_entry = GenerationLog(
            user_id=user.id,
            task_id=chap_task.id,
            generation_type="image",
            predicted_cost=prediction,
            status="pending"
        )
        db.session.add(log_entry)
        db.session.commit()
        notify("Generating Chapter Image...", user.id)
        return jsonify({
            "status": "queued",
            "predicted_cost": prediction
        })
    except Exception as e:
        notify("Chapter Image Generation Failed", user.id)
        clear_user_generation_lock(user.id)
        return jsonify({"error": str(e)}), 500

@bp.route('/api/generate_meta', methods=["POST"])
@is_story_author_or_admin
def api_generate_meta():
    """
	Generates metadata for a story based on the provided story ID and user credentials.
    
    This function checks if the user has enough credits to generate metadata. If the user has insufficient credits or if the story is not found, appropriate error messages are returned. If the generation is successful, a task is queued for processing, and a log entry is created.
    
    Returns:
        flask.Response: A JSON response containing either the task ID and status of the queued task or an error message.
    
    Raises:
        Exception: If there is an error during the metadata generation process.
    """
    from helpers import is_last_generation_and_negative_creds
    user = get_current_user()
    if is_last_generation_and_negative_creds(user, "meta"):
        notify("Top up your credits to see generation", user.id)
        return jsonify({"error": True})
    from tasks import generate_meta_task
    data = request.json
    story_id = data.get("story_id")
    story = Story.query.get(story_id)
    if not story:
        return jsonify({"error": "Story not found."}), 404
    prediction = calculate_predicted_meta_cost(story)
    total_predicted_cost = prediction.get("total_predicted_credit_cost")
    if not can_spend_credits(user, "text", total_predicted_cost):
        notify("You Don't Have Enough Credits!", user.id)
        return jsonify({
            "error": "Not enough credits.",
            "required": total_predicted_cost,
            "available": user.text_credits
        }), 400
    tags = ", ".join([tag.name for tag in story.tags]) if story.tags else ""
    inspirations = story.inspirations
    full_prompt = build_meta_prompt(story.title, story.details, tags, inspirations, story.chapters_count)
    try:
        task = generate_meta_task.delay(int(story_id), full_prompt, user.id, prediction["input_tokens"])
        log_entry = GenerationLog(
            user_id=user.id,
            task_id=task.id,
            generation_type="meta",
            predicted_cost=total_predicted_cost,
            status="pending"
        )
        db.session.add(log_entry)
        db.session.commit()
        notify("Generating Metadata...", user.id)
        return jsonify({
            "task_id": task.id,
            "status": "queued",
            "predicted_cost": prediction
        })
    except Exception as e:
        notify("Metadata Generation Failed", user.id)
        clear_user_generation_lock(user.id)
        return jsonify({"error": str(e)}), 500

@bp.route('/api/generate_arcs', methods=["POST"])
@is_story_author_or_admin
def api_generate_arcs():
    """
	Generates story arcs for a given story based on user input and available credits.
    
    This function checks if the user has enough credits to generate story arcs. If the user has insufficient credits, a notification is sent, and an error response is returned. It retrieves the story details, including chapters, characters, and locations, and constructs a prompt for story arc generation. The function then calculates the predicted cost of generating the story arcs and checks if the user can afford it. If all conditions are met, it queues a background task to generate the story arcs and logs the generation request.
    
    Returns:
        Response: A JSON response containing either the task ID and status if successful, or an error message if unsuccessful.
    
    Raises:
        Exception: If there is an error during the generation process, an error message is returned with a 500 status code.
    """
    from helpers import is_last_generation_and_negative_creds
    user = get_current_user()
    if is_last_generation_and_negative_creds(user, "story_arcs"):
        notify("Top up your credits to see generation", user.id)
        return jsonify({"error": True})
    from tasks import generate_story_arcs_task
    data = request.json
    story_id = data.get("story_id")
    story = Story.query.get(story_id)
    if not story:
        return jsonify({"error": "Story not found."}), 404
    num_chapters = story.chapters_count
    characters = Character.query.filter_by(story_id=story.id).all()
    locations = Location.query.filter_by(story_id=story.id).all()
    meta = {
        "characters": [{"name": c.name, "description": c.description} for c in characters],
        "locations": [{"name": l.name, "description": l.description} for l in locations]
    }
    tags = ", ".join([tag.name for tag in story.tags]) if story.tags else ""
    full_prompt = build_story_arcs_prompt(
        title=story.title,
        details=story.details,
        total_chapters=num_chapters,
        tags=tags,
        meta=meta
    )
    prediction = calculate_predicted_story_arcs_cost(story)
    total_predicted_cost = prediction.get("total_predicted_credit_cost")
    if not can_spend_credits(user, "text", total_predicted_cost):
        notify("You Don't Have Enough Credits!", user.id)
        return jsonify({
            "error": "Not enough credits.",
            "required": total_predicted_cost,
            "available": user.text_credits
        }), 400
    try:
        task = generate_story_arcs_task.delay(int(story_id), full_prompt, user.id, prediction["input_tokens"])
        log_entry = GenerationLog(
            user_id=user.id,
            task_id=task.id,
            generation_type="story_arcs",
            predicted_cost=total_predicted_cost,
            status="pending"
        )
        db.session.add(log_entry)
        db.session.commit()
        notify("Generating Story Arcs...", user.id)
        return jsonify({
            "task_id": task.id,
            "status": "queued",
            "predicted_cost": prediction
        })
    except Exception as e:
        notify("Story Arcs Generation Failed", user.id)
        clear_user_generation_lock(user.id)
        return jsonify({"error": str(e)}), 500

@bp.route('/api/generate_summaries', methods=["POST"])
@is_story_author_or_admin
def api_generate_summaries():
    """
	Generates summaries for a specified story by processing user requests and managing credit usage.
    
    This function checks if the user has enough credits to generate summaries and if a generation task is already in progress. It retrieves the story details, constructs a prompt for summary generation, and initiates an asynchronous task to generate the summaries. It also logs the generation request and handles any errors that may occur during the process.
    
    Returns:
        Flask Response: A JSON response containing either the task ID and status if the generation is queued, or an error message with an appropriate HTTP status code.
    
    Raises:
        HTTPException: If the story is not found or if there are insufficient credits.
    """
    from helpers import is_last_generation_and_negative_creds
    user = get_current_user()
    if is_last_generation_and_negative_creds(user, "summaries"):
        notify("Top up your credits to see generation", user.id)
        return jsonify({"error": True})
    from tasks import generate_summaries_task
    data = request.json
    story_id = data.get("story_id")
    story = Story.query.get(story_id)
    if not story:
        return jsonify({"error": "Story not found."}), 404
    if not set_user_generation_lock(user.id):
        notify("A generation task is already in progress", user.id)
        return jsonify({"error": "A generation task is already in progress."}), 400
    tags = ", ".join([tag.name for tag in story.tags]) if story.tags else ""
    meta = {
        "characters": [{"name": c.name, "description": c.description} for c in Character.query.filter_by(story_id=story.id).all()],
        "locations": [{"name": l.name, "description": l.description} for l in Location.query.filter_by(story_id=story.id).all()]
    }
    arcs = [arc.arc_text for arc in story.arcs]
    full_prompt = build_chapter_summaries_prompt(story.title, story.details, tags, meta, arcs, story.inspirations, story.chapters_count)
    prediction = calculate_predicted_summaries_cost(story)
    total_predicted_cost = prediction.get("total_predicted_credit_cost")
    if not can_spend_credits(user, "text", total_predicted_cost):
        notify("You Don't Have Enough Credits!", user.id)
        return jsonify({
            "error": "Not enough credits.",
            "required": total_predicted_cost,
            "available": user.text_credits
        }), 400
    try:
        task = generate_summaries_task.delay(int(story_id), full_prompt, user.id, prediction["input_tokens"])
        log_entry = GenerationLog(
            user_id=user.id,
            task_id=task.id,
            generation_type="summaries",
            predicted_cost=total_predicted_cost,
            status="pending"
        )
        db.session.add(log_entry)
        db.session.commit()
        notify("Generating Summaries...", user.id)
        return jsonify({
            "task_id": task.id,
            "status": "queued",
            "predicted_cost": prediction
        })
    except Exception as e:
        notify("Summaries Generation Failed", user.id)
        clear_user_generation_lock(user.id)
        return jsonify({"error": str(e)}), 500

@bp.route('/api/generate_chapter_guide', methods=["POST"])
@is_story_author_or_admin
def api_generate_chapter_guide():
    """
	Generates detailed story arcs for a given story based on user input and available credits.
    
    This function checks if the user has enough credits to generate detailed story arcs. If the user has insufficient credits, a notification is sent, and an error response is returned. It retrieves the story and its associated characters, locations, chapters, and tags, constructs a prompt for generating the arcs, and calculates the predicted cost. If the user can afford the generation, a background task is initiated to generate the arcs, and a log entry is created. If any errors occur during the process, an error response is returned.
    
    Returns:
        Response: A JSON response containing either the task ID and status of the generation or an error message.
    
    Raises:
        Exception: If there is an error during the generation process.
    """
    from helpers import is_last_generation_and_negative_creds
    user = get_current_user()
    if is_last_generation_and_negative_creds(user, "chapter_guide"):
        notify("Top up your credits to see generation", user.id)
        return jsonify({"error": True})
    from tasks import generate_chapter_guide_task
    data = request.json
    story_id = data.get("story_id")
    
    story = Story.query.get(story_id)
    if not story:
        return jsonify({"error": "Story not found."}), 404    

    characters = Character.query.filter_by(story_id=story.id).all()
    locations = Location.query.filter_by(story_id=story.id).all()
    meta = {
        "characters": [{"name": char.name, "description": char.description or ""} for char in characters],
        "locations": [{"name": loc.name, "description": loc.description or ""} for loc in locations]
    }
    sorted_chapters = sorted(story.chapters, key=lambda c: c.chapter_number)
    chapters = [ch.title for ch in sorted_chapters]
    summaries = [ch.summary or "" for ch in sorted_chapters]
    overall_arcs = [arc.arc_text for arc in story.arcs] if story.arcs else []
    tags_str = ", ".join([tag.name for tag in story.tags]) if story.tags else ""
    
    full_prompt = build_chapter_guide_prompt(
        story.title,
        story.details or "",
        tags_str,
        meta,
        chapters,
        summaries,
        overall_arcs
    )
    
    prediction = calculate_predicted_chapter_guide_cost(story)
    total_predicted_cost = prediction.get("total_predicted_credit_cost")
    if not can_spend_credits(user, "text", total_predicted_cost):
        notify("You Don't Have Enough Credits!", user.id)
        return jsonify({
            "error": "Not enough credits.",
            "required": total_predicted_cost,
            "available": user.text_credits
        }), 400
    
    try:
        task = generate_chapter_guide_task.delay(story_id, full_prompt, user.id, prediction["input_tokens"])
        log_entry = GenerationLog(
            user_id=user.id,
            task_id=task.id,
            generation_type="chapter_guide",
            predicted_cost=total_predicted_cost,
            status="pending"
        )
        db.session.add(log_entry)
        db.session.commit()
        notify("Generating Detailed Story Arcs...", user.id)
        return jsonify({
            "task_id": task.id,
            "status": "queued",
            "predicted_cost": prediction
        })
    except Exception as e:
        notify("Detailed Story Arcs Generation Failed", user.id)
        clear_user_generation_lock(user.id)
        return jsonify({"error": str(e)}), 500

@bp.route('/api/generate_chapter', methods=["POST"])
@is_story_author_or_admin
def api_generate_chapter():
    """
	Generates a chapter for a given story based on user input and current credits.
    
    This function checks if the user has enough credits to generate a chapter. It retrieves the story and chapter details, including summaries and character/location information, and constructs a prompt for chapter generation. If the user has sufficient credits, it queues a background task to generate the chapter and logs the generation request.
    
    Returns:
        json: A JSON response containing either the task ID and status if the generation is queued successfully, or an error message with an appropriate HTTP status code.
    
    Raises:
        Exception: If there is an error during the chapter generation process.
    """
    from helpers import is_last_generation_and_negative_creds
    user = get_current_user()
    if is_last_generation_and_negative_creds(user, "chapter"):
        notify("Top up your credits to see generation", user.id)
        return jsonify({"error": True})
    user = get_current_user()
    from tasks import generate_chapter_task
    data = request.json
    story_id = data.get("story_id")
    chapter_number = int(data.get("chapter_number"))
    story = Story.query.get(story_id)
    if not story:
        return jsonify({"error": "Story not found."}), 404
    if not set_user_generation_lock(user.id):
        notify("A generation task is already in progress", user.id)
        return jsonify({"error": "A generation task is already in progress."}), 400

    chapters = Chapter.query.filter_by(story_id=story.id).order_by(Chapter.chapter_number).all()
    if not chapters or len(chapters) < chapter_number:
        clear_user_generation_lock(user.id)
        return jsonify({"error": "Chapter data not found."}), 400

    chapter_obj = chapters[chapter_number - 1]
    chapter_title = chapter_obj.title
    chapter_summary = chapter_obj.summary if chapter_obj.summary else ""
    previous_summary = chapters[chapter_number - 2].summary if chapter_number - 2 >= 0 else ""
    next_summary = chapters[chapter_number].summary if chapter_number < len(chapters) else ""

    tags = ", ".join([tag.name for tag in story.tags]) if story.tags else ""
    chapter_mappings = ChapterGuide.query.filter_by(
        story_id=story_id, chapter_title=chapter_title
    ).order_by(ChapterGuide.part_index).all()
    
    detailed_arc_parts = [{
        "arc_text": mapping.part_text,
        "characters": mapping.characters,
        "locations": mapping.locations
    } for mapping in chapter_mappings]
    
    unique_characters = set()
    unique_locations = set()
    for part in detailed_arc_parts:
        for char in part.get("characters", []):
            unique_characters.add(char)
        for loc in part.get("locations", []):
            unique_locations.add(loc)

    character_objs = Character.query.filter(
        Character.story_id == story_id,
        Character.name.in_(list(unique_characters))
    ).all()

    location_objs = Location.query.filter(
        Location.story_id == story_id,
        Location.name.in_(list(unique_locations))
    ).all()

    character_details = {
        character.name: {
            "description": character.description,
            "example_dialogue": character.example_dialogue
        }
        for character in character_objs
    }
    location_details = {location.name: location.description for location in location_objs}

    full_prompt = build_chapter_content_prompt(
        chapter_title, chapter_summary,
        story.title, story.details, tags, detailed_arc_parts,
        previous_summary, next_summary,
        story.inspirations, story.writing_style,
        character_details, location_details
    )
    prediction = calculate_predicted_chapter_cost(story, chapter_number - 1)
    total_predicted_cost = prediction.get("total_predicted_credit_cost")
    if not can_spend_credits(user, "text", total_predicted_cost):
        notify("You Don't Have Enough Credits!", user.id)
        clear_user_generation_lock(user.id)
        return jsonify({
            "error": "Not enough credits.",
            "required": total_predicted_cost,
            "available": user.text_credits
        }), 400
    try:
        task = generate_chapter_task.delay(
            int(story_id), full_prompt, chapter_number, user.id,
            prediction["input_tokens"]
        )
        log_entry = GenerationLog(
            user_id=user.id,
            task_id=task.id,
            generation_type="chapter",
            predicted_cost=total_predicted_cost,
            status="pending"
        )
        db.session.add(log_entry)
        db.session.commit()
        notify("Generating Chapter...", user.id)
        return jsonify({
            "task_id": task.id,
            "status": "queued",
            "predicted_cost": prediction
        })
    except Exception as e:
        notify("Chapter Generation Failed", user.id)
        clear_user_generation_lock(user.id)
        return jsonify({"error": str(e)}), 500

@bp.route('/api/generate_all_chapters', methods=["POST"])
@is_story_author_or_admin
def api_generate_all_chapters():
    """
	Generates all chapters for a given story and queues the generation tasks.
    
    This function checks the user's credit balance, verifies the existence of the story, 
    and ensures that no other generation tasks are in progress. It retrieves the chapters 
    of the story, calculates the predicted costs for generating each chapter, and 
    queues the generation tasks for processing. Notifications are sent to the user 
    regarding the status of their credits and the generation process.
    
    Returns:
        flask.Response: A JSON response indicating the status of the generation process.
            - If successful, returns a message indicating that chapters are being generated.
            - If there are issues (e.g., insufficient credits, story not found), 
              returns an error message with appropriate HTTP status codes.
    """
    from helpers import is_last_generation_and_negative_creds
    user = get_current_user()
    if is_last_generation_and_negative_creds(user, "chapter"):
        notify("Top up your credits to see generation", user.id)
        return jsonify({"error": True})
    user = get_current_user()
    from tasks import generate_chapter_task
    data = request.json
    story_id = data.get("story_id")
    story = Story.query.get(story_id)
    if not story:
        return jsonify({"error": "Story not found."}), 404
    if not set_user_generation_lock(user.id):
        notify("A generation task is already in progress", user.id)
        return jsonify({"error": "A generation task is already in progress."}), 400

    tags = ", ".join([tag.name for tag in story.tags]) if story.tags else ""
    chapters = Chapter.query.filter_by(story_id=story.id).order_by(Chapter.chapter_number).all()
    total_chapters = len(chapters)

    prediction_all = calculate_predicted_all_chapters_cost(story)
    total_predicted_cost = prediction_all.get("total_predicted_credit_cost")
    if not can_spend_credits(user, "text", total_predicted_cost):
        notify("You Don't Have Enough Credits!", user.id)
        clear_user_generation_lock(user.id)
        return jsonify({
            "error": "Not enough credits.",
            "required": total_predicted_cost,
            "available": user.text_credits
        }), 400

    for i in range(total_chapters):
        chapter_obj = chapters[i]
        chapter_title = chapter_obj.title
        chapter_summary = chapter_obj.summary if chapter_obj.summary else ""
        previous_summary = chapters[i - 1].summary if i - 1 >= 0 else ""
        next_summary = chapters[i + 1].summary if i + 1 < total_chapters else ""
        chapter_mappings = ChapterGuide.query.filter_by(
            story_id=story_id, chapter_title=chapter_title
        ).order_by(ChapterGuide.part_index).all()
        detailed_arc_parts = [{
            "arc_text": mapping.part_text,
            "characters": mapping.characters,
            "locations": mapping.locations
        } for mapping in chapter_mappings]

        unique_characters = set()
        unique_locations = set()
        for part in detailed_arc_parts:
            for char in part.get("characters", []):
                unique_characters.add(char)
            for loc in part.get("locations", []):
                unique_locations.add(loc)

        character_objs = Character.query.filter(
            Character.story_id == story_id,
            Character.name.in_(list(unique_characters))
        ).all()

        location_objs = Location.query.filter(
            Location.story_id == story_id,
            Location.name.in_(list(unique_locations))
        ).all()

        character_details = {
            character.name: {
                "description": character.description,
                "example_dialogue": character.example_dialogue
            }
            for character in character_objs
        }
        location_details = {location.name: location.description for location in location_objs}

        full_prompt = build_chapter_content_prompt(
            chapter_title, chapter_summary,
            story.title, story.details, tags, detailed_arc_parts,
            previous_summary, next_summary,
            story.inspirations, story.writing_style,
            character_details, location_details
        )
        chapter_prediction = calculate_predicted_chapter_cost(story, i)
        task = generate_chapter_task.delay(
            story_id, full_prompt, i + 1, user.id,
            chapter_prediction["input_tokens"]
        )
        log_entry = GenerationLog(
            user_id=user.id,
            task_id=task.id,
            generation_type="chapter",
            predicted_cost=chapter_prediction.get("total_predicted_credit_cost"),
            status="pending"
        )
        db.session.add(log_entry)
        db.session.commit()
    notify("Generating All Chapters...", user.id)
    return jsonify({
        "status": "queued",
        "message": "Chapters are being generated in the background.",
        "predicted_cost": prediction_all
    })
