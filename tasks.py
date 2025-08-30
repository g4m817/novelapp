import eventlet
eventlet.monkey_patch(all=False, socket=True)
celery = eventlet.import_patched("celery")
from celery import Celery
import json
from models import db, Story, GenerationLog, Chapter, Character, Location, StoryArc, ChapterGuide
from openai_handler import (
    generate_meta_from_prompt,
    generate_chapter_summaries_from_prompt,
    generate_chapter_content_from_prompt,
    generate_story_arcs_from_prompt,
    generate_image_from_prompt,
    generate_chapter_guide_from_prompt
)
from predictions import ( 
    calculate_actual_meta_cost,
    calculate_actual_summaries_cost,
    calculate_actual_chapter_cost,
    calculate_actual_story_arcs_cost,
    calculate_actual_chapter_guide_cost
)
from api.generation import clear_user_generation_lock
from helpers import get_image_url, spend_credits, notify, put_image
from app import app, socketio
import requests

celery_app = Celery(app.import_name,
                    broker=app.config['CELERY_BROKER_URL'],
                    backend=app.config['CELERY_RESULT_BACKEND'])
celery_app.conf.update(app.config)

class ContextTask(celery_app.Task):
    def __call__(self, *args, **kwargs):
        with app.app_context():
            return self.run(*args, **kwargs)
celery_app.Task = ContextTask

@celery_app.task(name="generate_image_task")
def generate_image_task(story_id, image_key, prompt, user_id, credit_cost, chapter_id=None):
    """
	Generates an image based on a given prompt and associates it with a story or chapter.
    
    Args:
        story_id (int): The ID of the story to which the image will be associated.
        image_key (str): The key under which the generated image will be stored.
        prompt (str): The text prompt used to generate the image.
        user_id (int): The ID of the user requesting the image generation.
        credit_cost (float): The cost in credits for generating the image.
        chapter_id (int, optional): The ID of the chapter to which the image will be associated. If None, the image will be associated with the story.
    
    Returns:
        dict: A dictionary indicating the success or failure of the image generation process. 
              On success, returns {"success": True}. 
              On failure, returns {"status": "error", "error": "<error_message>"}.
    
    Raises:
        Exception: If an error occurs during image generation or database operations.
    """
    task_id = generate_image_task.request.id
    log_entry = GenerationLog.query.filter_by(
        task_id=task_id, user_id=user_id, generation_type="image"
    ).first()
    try:
        result_url = generate_image_from_prompt(prompt, size="1024x1024")
        image_data = requests.get(result_url).content
        
        if chapter_id is None:
            story = Story.query.get(story_id)
            if not story:
                notify("Story not found", user_id)
                return {"status": "error", "error": "Story not found."}
            new_image_url = put_image(image_key, image_data)
            story.cover_image_key = new_image_url
        else:
            chapter = Chapter.query.filter_by(story_id=story_id, id=chapter_id).first()
            if not chapter:
                notify("Chapter not found", user_id)
                return {"status": "error", "error": "Chapter not found."}
            new_image_url = put_image(image_key, image_data)
            chapter.chapter_image_key = new_image_url
        
        db.session.commit()
        spend_credits(user_id, "image", credit_cost)
        if log_entry:
            log_entry.status = "succeeded"
            log_entry.model = "dall-e-3"
            db.session.commit()
        notify("Image Generation Complete", user_id)
        
        socketio.emit(
            "image_generated",
            {
                "story_id": story_id,
                "image": get_image_url(new_image_url),
                "type": "cover" if chapter_id is None else "chapter",
                "chapter_id": chapter_id
            },
            room=user_id
        )
        return {"success": True}
    except Exception as e:
        db.session.rollback()
        if log_entry:
            log_entry.status = "failed"
            log_entry.error_message = str(e)
            db.session.commit()
        notify("Image Generation Failed", user_id)
        socketio.emit("generation_error", {"story_id": story_id, "error": str(e)}, room=user_id)
        return {"status": "error", "error": str(e)}
    finally:
        clear_user_generation_lock(user_id)
        db.session.remove()

@celery_app.task(name="generate_meta_task")
def generate_meta_task(story_id, prompt, user_id, predicted_input_tokens):
    """
	Generates metadata for a story based on the provided prompt and user information.
    
    This function processes a prompt to extract character and location data, updates the database with this information, and handles logging and notifications for the user. It also calculates the cost of the metadata generation and manages user generation locks.
    
    Args:
        story_id (int): The ID of the story for which metadata is being generated.
        prompt (str): The prompt used to generate character and location data.
        user_id (int): The ID of the user requesting the metadata generation.
        predicted_input_tokens (int): The estimated number of input tokens for cost calculation.
    
    Returns:
        dict: A dictionary containing the status of the operation and the generated metadata, or an error message if the operation fails.
    
    Raises:
        Exception: If an error occurs during the metadata generation process, the function will log the error and notify the user.
    """
    task_id = generate_meta_task.request.id
    log_entry = GenerationLog.query.filter_by(
        task_id=task_id, user_id=user_id, generation_type="meta"
    ).first()
    try:
        result_text = generate_meta_from_prompt(prompt)
        try:
            result = json.loads(result_text)
        except Exception:
            result = {"locations": [], "characters": []}
        if len(result.get("locations")) == 0 and len(result.get("characters")) == 0:
            notify("Metadata Generation Failed", user_id)
            clear_user_generation_lock(user_id)
            return

        story = Story.query.get(story_id)
        if story:
            Character.query.filter_by(story_id=story.id).delete()
            Location.query.filter_by(story_id=story.id).delete()
            for char_data in result.get("characters", []):
                new_char = Character(
                    story_id=story.id,
                    name=char_data.get("name"),
                    description=char_data.get("description"),
                    example_dialogue=char_data.get("example_dialogue")
                )
                db.session.add(new_char)
            for loc_data in result.get("locations", []):
                new_loc = Location(
                    story_id=story.id,
                    name=loc_data.get("name"),
                    description=loc_data.get("description")
                )
                db.session.add(new_loc)
            db.session.commit()

        actual_cost = calculate_actual_meta_cost(predicted_input_tokens, result_text)
        real_total_cost = actual_cost.get("total_actual_credit_cost")
        spend_credits(user_id, "text", real_total_cost)
        if log_entry:
            log_entry.real_cost = real_total_cost
            log_entry.status = "succeeded"
            log_entry.input_tokens = actual_cost.get("input_tokens", 0)
            log_entry.output_tokens = actual_cost.get("output_tokens", 0)
            log_entry.model = actual_cost.get("model", "")
            db.session.commit()

        notify("Metadata Generation Successful", user_id)
        meta = {
            "characters": [{"id": c.id, "name": c.name, "description": c.description, "example_dialogue": c.example_dialogue} 
                           for c in Character.query.filter_by(story_id=story.id).all()],
            "locations": [{"id": l.id, "name": l.name, "description": l.description} 
                          for l in Location.query.filter_by(story_id=story.id).all()]
        }
        socketio.emit("meta_generated", {"story_id": story_id, "meta": meta}, room=user_id)
        return {"status": "success", "meta": meta, "actual_cost": actual_cost}
    except Exception as e:
        if log_entry:
            log_entry.status = "failed"
            log_entry.error_message = str(e)
            db.session.commit()
        notify("Metadata Generation Failed", user_id)
        socketio.emit("generation_error", {"story_id": story_id, "error": str(e)}, room=user_id)
        return {"status": "error", "error": str(e)}
    finally:
        clear_user_generation_lock(user_id)
        db.session.remove()

@celery_app.task(name="generate_story_arcs_task")
def generate_story_arcs_task(story_id, prompt, user_id, predicted_input_tokens):
    """
	Generates story arcs based on a given prompt and updates the database with the new arcs.
    
    Args:
        story_id (int): The ID of the story for which arcs are being generated.
        prompt (str): The prompt used to generate the story arcs.
        user_id (int): The ID of the user requesting the story arcs.
        predicted_input_tokens (int): The predicted number of input tokens for cost calculation.
    
    Returns:
        dict: A dictionary containing the status of the operation, the generated arcs, and the actual cost.
            - If successful, returns {"status": "success", "arcs": arcs, "actual_cost": actual_cost}.
            - If failed, returns {"status": "error", "error": error_message}.
    
    Raises:
        Exception: If an error occurs during the generation or database operations, the error is logged and returned.
    """
    task_id = generate_story_arcs_task.request.id
    log_entry = GenerationLog.query.filter_by(
        task_id=task_id, user_id=user_id, generation_type="story_arcs"
    ).first()
    try:
        arcs_text = generate_story_arcs_from_prompt(prompt)
        arcs = json.loads(arcs_text)
        story = Story.query.get(story_id)
        if story:
            StoryArc.query.filter_by(story_id=story.id).delete()
            for index, arc in enumerate(arcs):
                new_arc = StoryArc(story_id=story.id, arc_text=arc, arc_order=index + 1)
                db.session.add(new_arc)
            db.session.commit()
        actual_cost = calculate_actual_story_arcs_cost(predicted_input_tokens, arcs_text)
        real_total_cost = actual_cost.get("total_actual_credit_cost")
        spend_credits(user_id, "text", real_total_cost)
        if log_entry:
            log_entry.real_cost = real_total_cost
            log_entry.status = "succeeded"
            log_entry.input_tokens = actual_cost.get("input_tokens", 0)
            log_entry.output_tokens = actual_cost.get("output_tokens", 0)
            log_entry.model = actual_cost.get("model", "")
            db.session.commit()
        notify("Story Arcs Generation Successful", user_id)
        socketio.emit("arcs_generated", {"story_id": story_id, "arcs": arcs}, room=user_id)
        return {"status": "success", "arcs": arcs, "actual_cost": actual_cost}
    except Exception as e:
        if log_entry:
            log_entry.status = "failed"
            log_entry.error_message = str(e)
            db.session.commit()
        notify("Story Arcs Generation Failed", user_id)
        socketio.emit("generation_error", {"story_id": story_id, "error": str(e)}, room=user_id)
        return {"status": "error", "error": str(e)}
    finally:
        clear_user_generation_lock(user_id)
        db.session.remove()

@celery_app.task(name="generate_summaries_task")
def generate_summaries_task(story_id, prompt, user_id, predicted_input_tokens):
    """
	Generates summaries for a given story based on a prompt and logs the generation process.
    
    Args:
        story_id (int): The ID of the story for which summaries are to be generated.
        prompt (str): The prompt used to generate chapter summaries.
        user_id (int): The ID of the user requesting the summary generation.
        predicted_input_tokens (int): The estimated number of input tokens for cost calculation.
    
    Returns:
        dict: A dictionary containing the status of the operation and the generated summaries, 
              or an error message if the operation fails.
    
    Raises:
        ValueError: If the generated summaries text is empty or cannot be parsed as JSON.
        Exception: For any other errors that occur during the summary generation process.
    
    Notes:
        - The function updates the database with the generated summaries and their associated costs.
        - It emits events to notify the user of the success or failure of the summary generation.
    """
    task_id = generate_summaries_task.request.id
    log_entry = GenerationLog.query.filter_by(
        task_id=task_id, user_id=user_id, generation_type="summaries"
    ).first()
    try:
        story = Story.query.get(story_id)
        generated_summaries_text = generate_chapter_summaries_from_prompt(prompt)
        if not generated_summaries_text.strip():
            raise ValueError("Empty response received for Chapter Summaries.")
        try:
            generated_summaries = json.loads(generated_summaries_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse Chapter Summaries JSON: {e}. Raw output: {generated_summaries_text}")

        for index, chapter_data in enumerate(generated_summaries, start=1):
            chapter = Chapter.query.filter_by(story_id=story.id, chapter_number=index).first()
            if not chapter:
                chapter = Chapter(
                    story_id=story.id,
                    chapter_number=index,
                    title=chapter_data.get("title", f"Chapter {index}"),
                    summary=chapter_data.get("summary", "")
                )
                db.session.add(chapter)
            else:
                chapter.title = chapter_data.get("title", chapter.title)
                chapter.summary = chapter_data.get("summary", chapter.summary)
        db.session.commit()

        actual_cost = calculate_actual_summaries_cost(predicted_input_tokens, generated_summaries_text)
        real_total_cost = actual_cost.get("total_actual_credit_cost")
        spend_credits(user_id, "text", real_total_cost)
        if log_entry:
            log_entry.real_cost = real_total_cost
            log_entry.status = "succeeded"
            log_entry.input_tokens = actual_cost.get("input_tokens", 0)
            log_entry.output_tokens = actual_cost.get("output_tokens", 0)
            log_entry.model = actual_cost.get("model", "")
            db.session.commit()
        notify("Summaries Generation Successful", user_id)
        summaries = [
            {"id": ch.id, "title": ch.title, "summary": ch.summary or ""}
            for ch in sorted(story.chapters, key=lambda c: c.chapter_number)
        ]
        socketio.emit("summaries_generated", {"story_id": story_id, "summaries": summaries}, room=user_id)
        return {"status": "success", "summaries": summaries, "actual_cost": actual_cost}
    except Exception as e:
        if log_entry:
            log_entry.status = "failed"
            log_entry.error_message = str(e)
            db.session.commit()
        notify("Summaries Generation Failed", user_id)
        socketio.emit("generation_error", {"story_id": story_id, "error": str(e)}, room=user_id)
        return {"status": "error", "error": str(e)}
    finally:
        clear_user_generation_lock(user_id)
        db.session.remove()

@celery_app.task(name="generate_chapter_guide_task")
def generate_chapter_guide_task(story_id, full_prompt, user_id, predicted_input_tokens):
    """
	Generates detailed story arcs for a given story based on a full prompt and user input.
    
    Args:
        story_id (int): The unique identifier for the story.
        full_prompt (str): The prompt used to generate the detailed story arcs.
        user_id (int): The unique identifier for the user requesting the generation.
        predicted_input_tokens (int): The estimated number of input tokens for cost calculation.
    
    Returns:
        dict: A dictionary containing the status of the operation, the generated Chapter Guides, and the actual cost incurred.
            - status (str): Indicates whether the operation was successful or encountered an error.
            - chapter_guide (dict): A dictionary of generated story arcs grouped by chapter title.
            - actual_cost (dict): A dictionary containing cost-related information, including total actual credit cost, input tokens, output tokens, and model used.
    
    Raises:
        Exception: If an error occurs during the generation process, the error message will be logged and returned in the response.
    """
    task_id = generate_chapter_guide_task.request.id
    log_entry = GenerationLog.query.filter_by(
        task_id=task_id, user_id=user_id, generation_type="chapter_guide"
    ).first()
    
    try:
        chapter_guide_text = generate_chapter_guide_from_prompt(full_prompt)
        chapter_guide = json.loads(chapter_guide_text)
        
        ChapterGuide.query.filter_by(story_id=story_id).delete()
        
        for chapter_title, arcs_list in chapter_guide.items():
            for arc_obj in arcs_list:
                arc_number = arc_obj.get("arc")
                arc_text = arc_obj.get("arc_text")
                characters = arc_obj.get("characters", [])
                locations = arc_obj.get("locations", [])
                if arc_text is None or arc_number is None:
                    continue
                mapping = ChapterGuide(
                    story_id=story_id,
                    chapter_title=chapter_title,
                    part_index=arc_number,
                    part_text=arc_text,
                    characters=characters,
                    locations=locations
                )
                db.session.add(mapping)
        db.session.commit()
        
        actual_cost = calculate_actual_chapter_guide_cost(predicted_input_tokens, chapter_guide_text)
        real_total_cost = actual_cost.get("total_actual_credit_cost")
        spend_credits(user_id, "text", real_total_cost)
        
        if log_entry:
            log_entry.real_cost = real_total_cost
            log_entry.status = "succeeded"
            log_entry.input_tokens = actual_cost.get("input_tokens", 0)
            log_entry.output_tokens = actual_cost.get("output_tokens", 0)
            log_entry.model = actual_cost.get("model", "")
            db.session.commit()
        
        notify("Detailed Story Arcs Generation Successful", user_id)
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

        socketio.emit("chapter_guide_generated", {"story_id": story_id, "chapter_guide": grouped_arcs}, room=user_id)
        return {"status": "success", "chapter_guide": grouped_arcs, "actual_cost": actual_cost}
    
    except Exception as e:
        if log_entry:
            log_entry.status = "failed"
            log_entry.error_message = str(e)
            db.session.commit()
        notify("Detailed Story Arcs Generation Failed", user_id)
        socketio.emit("generation_error", {"story_id": story_id, "error": str(e)}, room=user_id)
        return {"status": "error", "error": str(e)}
    
    finally:
        clear_user_generation_lock(user_id)
        db.session.remove()

@celery_app.task(name="generate_chapter_task")
def generate_chapter_task(story_id, prompt, chapter_number, user_id, predicted_input_tokens):
    """
	Generates a chapter for a given story based on the provided prompt and updates the database accordingly.
    
    Args:
        story_id (int): The ID of the story to which the chapter belongs.
        prompt (str): The prompt used to generate the chapter content.
        chapter_number (int): The number of the chapter being generated.
        user_id (int): The ID of the user requesting the chapter generation.
        predicted_input_tokens (int): The estimated number of input tokens for cost calculation.
    
    Returns:
        dict: A dictionary containing the status of the operation, the chapter number, and the actual cost if successful.
              In case of an error, it will include an error message.
    
    Raises:
        Exception: If an error occurs during chapter generation or database operations.
    """
    task_id = generate_chapter_task.request.id
    log_entry = GenerationLog.query.filter_by(
        task_id=task_id, user_id=user_id, generation_type="chapter"
    ).first()
    try:
        content = generate_chapter_content_from_prompt(prompt)
        chapter = Chapter.query.filter_by(story_id=story_id, chapter_number=chapter_number).first()
        if chapter:
            chapter.content = content
        db.session.commit()
        actual_cost = calculate_actual_chapter_cost(predicted_input_tokens, content)
        real_total_cost = actual_cost.get("total_actual_credit_cost")
        spend_credits(user_id, "text", real_total_cost)
        if log_entry:
            log_entry.real_cost = real_total_cost
            log_entry.status = "succeeded"
            log_entry.input_tokens = actual_cost.get("input_tokens", 0)
            log_entry.output_tokens = actual_cost.get("output_tokens", 0)
            log_entry.model = actual_cost.get("model", "")
            db.session.commit()
        notify("Chapter Generation Successful", user_id)
        socketio.emit("chapter_generated", {
            "story_id": story_id,
            "title": chapter.title,
            "chapter_number": chapter_number,
            "content": content
        }, room=user_id)
        return {"status": "success", "chapter": chapter_number, "actual_cost": actual_cost}
    except Exception as e:
        if log_entry:
            log_entry.status = "failed"
            log_entry.error_message = str(e)
            db.session.commit()
        notify("Chapter Generation Failed", user_id)
        socketio.emit("generation_error", {
            "story_id": story_id, "chapter_number": chapter_number, "error": str(e)
        }, room=user_id)
        return {"status": "error", "chapter": chapter_number, "error": str(e)}
    finally:
        clear_user_generation_lock(user_id)
        db.session.remove()
