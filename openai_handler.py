from openai import OpenAI
from app import app
from flask import current_app

client = None
with app.app_context():
    api_key = current_app.config.get("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)

def generate_image_from_prompt(prompt, size="1024x1024"):
    """
	Generates an image from a given text prompt using the DALL-E 3 model.
    
    Args:
        prompt (str): The text prompt to generate the image from.
        size (str, optional): The desired size of the generated image. Defaults to "1024x1024".
    
    Returns:
        str: The URL of the generated image.
    
    Raises:
        Exception: If there is an error during the image generation process.
    """
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size=size
        )
        
        image_url = response.data[0].url
        return image_url
    except Exception as e:
        raise Exception("Error generating image from prompt: " + str(e))


def generate_meta_from_prompt(shot_prompt):
    """
	Generates character and location descriptions based on a given prompt.
    
    Args:
        shot_prompt (str): A prompt provided by the user to guide the generation of characters and locations.
    
    Returns:
        str: A string containing the generated descriptions of characters and locations.
    
    Raises:
        Exception: If there is an error during the generation process, an exception is raised with a descriptive message.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a creative writer skilled in creating rich settings and characters."},
                {"role": "user", "content": shot_prompt}
            ],
            store=True
        )
        result_text = response.choices[0].message.content.strip()
        return result_text
    except Exception as e:
        raise Exception("Error generating characters and locations: " + str(e))


def generate_chapter_summaries_from_prompt(shot_prompt):
    """
	Generates chapter summaries based on a provided prompt using a chat model.
    
    Args:
        shot_prompt (str): A prompt that outlines the key elements or themes for the chapter summaries.
    
    Returns:
        str: The generated chapter summaries based on the provided prompt.
    
    Raises:
        Exception: If there is an error during the generation process, an exception is raised with a descriptive message.
    """
    try:
        response = client.chat.completions.create(
            model="o1-mini",
            messages=[
                {"role": "assistant", "content": "You are an accomplished novelist with a talent for weaving intricate narrative arcs."},
                {"role": "user", "content": shot_prompt}
            ],
            store=True
        )
        result_text = response.choices[0].message.content.strip()
        return result_text
    except Exception as e:
        raise Exception("Error generating chapter summaries: " + str(e))

def generate_story_arcs_from_prompt(shot_prompt):
    """
	Generates story arcs based on a given prompt.
    
    This function takes a user-provided prompt and utilizes a chat model to create cohesive and engaging story arcs. It sends the prompt to the model and retrieves the generated content.
    
    Args:
        shot_prompt (str): A string containing the user's prompt for generating story arcs.
    
    Returns:
        str: A string containing the generated story arcs.
    
    Raises:
        Exception: If there is an error during the generation process.
    """
    try:
        response = client.chat.completions.create(
            model="o1-mini",
            messages=[
                {"role": "assistant", "content": "You are a creative storyteller who can generate cohesive and engaging story arcs based on novel, summaries, and character details."},
                {"role": "user", "content": shot_prompt}
            ],
            store=True
        )
        arcs_text = response.choices[0].message.content.strip()
        return arcs_text
    except Exception as e:
        raise Exception("Error generating story arcs: " + str(e))

def generate_chapter_guide_from_prompt(shot_prompt):
    """
	Generates chapter guides based on a given prompt.
    
    This function takes a user-provided prompt and utilizes a chat model to create chapter guides. It sends the prompt to the model and retrieves the generated content.
    
    Args:
        shot_prompt (str): A string containing the user's prompt for generating chapter guides.
    
    Returns:
        str: A string containing the generated chapter guides.
    
    Raises:
        Exception: If there is an error during the generation process.
    """
    try:
        response = client.chat.completions.create(
            model="o1-mini",
            messages=[
                {"role": "assistant", "content": "You are a creative storyteller who can generate cohesive and engaging breakdowns per chapter based on novel, summaries, and character details."},
                {"role": "user", "content": shot_prompt}
            ],
            store=True
        )
        arcs_text = response.choices[0].message.content.strip()
        return arcs_text
    except Exception as e:
        raise Exception("Error generating story arcs: " + str(e))
    
def generate_chapter_content_from_prompt(shot_prompt):
    """
	Generates chapter content based on a provided prompt.
    
    This function interacts with a chat completion model to create immersive chapter content in Markdown format. It sends a prompt to the model and retrieves the generated content.
    
    Args:
        shot_prompt (str): A brief prompt that guides the content generation for the chapter.
    
    Returns:
        str: The generated chapter content in Markdown format.
    
    Raises:
        Exception: If there is an error during the content generation process.
    """
    try:
        response = client.chat.completions.create(
            model="o1-mini",
            messages=[
                {"role": "assistant", "content": "You are an expert novelist skilled in creating immersive chapters in Markdown."},
                {"role": "user", "content": shot_prompt}
            ],
            store=True
        )
        chapter_content = response.choices[0].message.content.strip()
        return chapter_content
    except Exception as e:
        raise Exception("Error generating content for chapter '{}': ".format(chapter_title) + str(e))