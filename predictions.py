from prompt_templates import (
    build_meta_prompt,
    build_chapter_summaries_prompt,
    build_chapter_content_prompt,
    build_story_arcs_prompt,
    build_chapter_guide_prompt,
    count_tokens
)
from models import TokenCostConfig, CreditConfig, Character, ChapterGuide, Location, StoryArc

def calculate_image_cost():
    """
	Calculates the cost of generating an image based on the configured token prices and modifiers.
    
    This function retrieves the base credit cost per image from the `TokenCostConfig` and applies a modifier 
    from the `CreditConfig` to calculate the total credit cost. If no modifier is found, a default value of 2 
    is used.
    
    Returns:
        dict: A dictionary containing the following keys:
            - base_credit_cost (float): The base cost in credits for generating a single image.
            - modifier (float): The modifier applied to the base cost.
            - total_credit_cost (float): The total cost in credits for generating a single image after applying the modifier.
    """
    tokenCostConfig = TokenCostConfig.query.first()
    base_credit_cost = tokenCostConfig.dall_e_price_per_image  
    config = CreditConfig.query.filter_by(action="image").first()
    modifier = config.modifier if config else 2

    
    total_credit_cost = base_credit_cost * modifier

    return {
        "base_credit_cost": base_credit_cost,
        "modifier": modifier,
        "total_credit_cost": total_credit_cost
    }

def calculate_predicted_meta_cost(story, model='gpt-4o-mini'):
    """
	Calculate the predicted meta cost for a given story based on input and output token counts.
    
    Args:
        story (Story): The story object containing details such as title, details, tags, inspirations, and chapter count.
        model (str, optional): The model to be used for token counting. Defaults to 'gpt-4o-mini'.
    
    Returns:
        dict: A dictionary containing the following keys:
            - input_tokens (int): The number of input tokens calculated from the full prompt.
            - predicted_output_tokens (int): The predicted number of output tokens (default is 200).
            - input_tokens_per_credit (float): The number of input tokens that can be processed per credit.
            - output_tokens_per_credit (float): The number of output tokens that can be processed per credit.
            - base_credit_cost_input (int): The base credit cost for input tokens.
            - modified_credit_cost_input (int): The modified credit cost for input tokens after applying any modifiers.
            - base_credit_cost_output (int): The base credit cost for output tokens.
            - modified_credit_cost_output (int): The modified credit cost for output tokens after applying any modifiers.
            - total_predicted_credit_cost (int): The total predicted credit cost combining both input and output costs.
    """
    tags = ", ".join([tag.name for tag in story.tags]) if story.tags else ""
    full_prompt = build_meta_prompt(story.title, story.details, tags, story.inspirations, story.chapters_count)
    input_token_count = count_tokens(full_prompt, model)
    
    tokenCostConfig = TokenCostConfig.query.first()
    cost_per_million_input = tokenCostConfig.cost_per_1m_input
    cost_per_million_output = tokenCostConfig.cost_per_1m_output
    credit_cost_dollar = tokenCostConfig.cost_per_credit

    input_tokens_per_credit = round((credit_cost_dollar * 1_000_000) / cost_per_million_input, 2)
    output_tokens_per_credit = round((credit_cost_dollar * 1_000_000) / cost_per_million_output, 2)
    base_credit_cost_input = max(1, round(input_token_count / input_tokens_per_credit))
    
    predicted_output_tokens = 200
    base_credit_cost_output = max(1, round(predicted_output_tokens / output_tokens_per_credit))
    
    config_in = CreditConfig.query.filter_by(action="meta_input").first()
    modifier_input = config_in.modifier if config_in else 2
    config_out = CreditConfig.query.filter_by(action="meta_output").first()
    modifier_output = config_out.modifier if config_out else 2
    
    modified_credit_cost_input = round(base_credit_cost_input * modifier_input)
    modified_credit_cost_output = round(base_credit_cost_output * modifier_output)
    total_predicted_credit_cost = modified_credit_cost_input + modified_credit_cost_output

    return {
        "input_tokens": input_token_count,
        "predicted_output_tokens": predicted_output_tokens,
        "input_tokens_per_credit": input_tokens_per_credit,
        "output_tokens_per_credit": output_tokens_per_credit,
        "base_credit_cost_input": base_credit_cost_input,
        "modified_credit_cost_input": modified_credit_cost_input,
        "base_credit_cost_output": base_credit_cost_output,
        "modified_credit_cost_output": modified_credit_cost_output,
        "total_predicted_credit_cost": total_predicted_credit_cost
    }

def calculate_actual_meta_cost(input_token_count, meta_text, model='gpt-4o-mini'):
    """
	Calculates the actual meta cost based on input token count and meta text.
    
    Args:
        input_token_count (int): The number of input tokens.
        meta_text (str): The text for which the meta cost is calculated.
        model (str, optional): The model to be used for token counting. Defaults to 'gpt-4o-mini'.
    
    Returns:
        dict: A dictionary containing the following keys:
            - input_tokens (int): The number of input tokens.
            - output_tokens (int): The number of output tokens calculated from the meta text.
            - model (str): The model used for the calculation.
            - input_tokens_per_credit (float): The number of input tokens that can be covered by one credit.
            - output_tokens_per_credit (float): The number of output tokens that can be covered by one credit.
            - base_credit_cost_input (int): The base credit cost for the input tokens.
            - modified_credit_cost_input (int): The modified credit cost for the input tokens after applying any modifiers.
            - base_credit_cost_output (int): The base credit cost for the output tokens.
            - modified_credit_cost_output (int): The modified credit cost for the output tokens after applying any modifiers.
            - total_actual_credit_cost (int): The total actual credit cost combining both input and output costs.
    """
    output_token_count = count_tokens(meta_text, model)
    
    tokenCostConfig = TokenCostConfig.query.first()
    cost_per_million_input = tokenCostConfig.cost_per_1m_input
    cost_per_million_output = tokenCostConfig.cost_per_1m_output
    credit_cost_dollar = tokenCostConfig.cost_per_credit

    input_tokens_per_credit = round((credit_cost_dollar * 1_000_000) / cost_per_million_input, 2)
    output_tokens_per_credit = round((credit_cost_dollar * 1_000_000) / cost_per_million_output, 2)
    
    base_credit_cost_input = max(1, round(input_token_count / input_tokens_per_credit))
    base_credit_cost_output = max(1, round(output_token_count / output_tokens_per_credit))
    
    config_in = CreditConfig.query.filter_by(action="meta_input").first()
    modifier_input = config_in.modifier if config_in else 2
    config_out = CreditConfig.query.filter_by(action="meta_output").first()
    modifier_output = config_out.modifier if config_out else 2
    
    modified_credit_cost_input = round(base_credit_cost_input * modifier_input)
    modified_credit_cost_output = round(base_credit_cost_output * modifier_output)
    total_actual_credit_cost = modified_credit_cost_input + modified_credit_cost_output

    return {
        "input_tokens": input_token_count,
        "output_tokens": output_token_count,
        "model": model,
        "input_tokens_per_credit": input_tokens_per_credit,
        "output_tokens_per_credit": output_tokens_per_credit,
        "base_credit_cost_input": base_credit_cost_input,
        "modified_credit_cost_input": modified_credit_cost_input,
        "base_credit_cost_output": base_credit_cost_output,
        "modified_credit_cost_output": modified_credit_cost_output,
        "total_actual_credit_cost": total_actual_credit_cost
    }

def calculate_predicted_summaries_cost(story, model='o1-mini'):
    """
	Calculate the predicted cost of generating summaries for a given story.
    
    Args:
        story (Story): The story object containing details such as title, details, tags, inspirations, and chapters count.
        model (str, optional): The model to be used for token counting. Defaults to 'o1-mini'.
    
    Returns:
        dict: A dictionary containing the following keys:
            - input_tokens (int): The number of input tokens calculated from the full prompt.
            - predicted_output_tokens (int): The predicted number of output tokens based on the chapters count.
            - input_tokens_per_credit (float): The number of input tokens that can be processed per credit.
            - output_tokens_per_credit (float): The number of output tokens that can be processed per credit.
            - base_credit_cost_input (int): The base credit cost for input tokens.
            - modified_credit_cost_input (int): The modified credit cost for input tokens after applying any modifiers.
            - base_credit_cost_output (int): The base credit cost for output tokens.
            - modified_credit_cost_output (int): The modified credit cost for output tokens after applying any modifiers.
            - total_predicted_credit_cost (int): The total predicted credit cost for both input and output tokens.
    """
    tags = ", ".join([tag.name for tag in story.tags]) if story.tags else ""
    inspirations = story.inspirations
    meta_characters = [{"name": c.name, "description": c.description} for c in Character.query.filter_by(story_id=story.id).all()]
    meta_locations = [{"name": l.name, "description": l.description} for l in Location.query.filter_by(story_id=story.id).all()]
    meta = {"characters": meta_characters, "locations": meta_locations}
    arcs = [arc.arc_text for arc in story.arcs] if hasattr(story, 'arcs') else []

    full_prompt = build_chapter_summaries_prompt(story.title, story.details, tags, meta, arcs, inspirations, story.chapters_count)
    
    input_token_count = count_tokens(full_prompt, model)
    predicted_output_tokens = story.chapters_count * 50

    tokenCostConfig = TokenCostConfig.query.first()
    cost_per_million_input = tokenCostConfig.o1_cost_per_1m_input
    cost_per_million_output = tokenCostConfig.o1_cost_per_1m_output
    credit_cost_dollar = tokenCostConfig.o1_cost_per_credit

    input_tokens_per_credit = round((credit_cost_dollar * 1_000_000) / cost_per_million_input, 2)
    output_tokens_per_credit = round((credit_cost_dollar * 1_000_000) / cost_per_million_output, 2)

    base_credit_cost_input = round(input_token_count / input_tokens_per_credit)
    base_credit_cost_output = round(predicted_output_tokens / output_tokens_per_credit)

    config_in = CreditConfig.query.filter_by(action="summary_input").first()
    modifier_input = config_in.modifier if config_in else 2
    config_out = CreditConfig.query.filter_by(action="summary_output").first()
    modifier_output = config_out.modifier if config_out else 2

    modified_credit_cost_input = round(base_credit_cost_input * modifier_input)
    modified_credit_cost_output = round(base_credit_cost_output * modifier_output)
    total_predicted_credit_cost = modified_credit_cost_input + modified_credit_cost_output

    return {
        "input_tokens": input_token_count,
        "predicted_output_tokens": predicted_output_tokens,
        "input_tokens_per_credit": input_tokens_per_credit,
        "output_tokens_per_credit": output_tokens_per_credit,
        "base_credit_cost_input": base_credit_cost_input,
        "modified_credit_cost_input": modified_credit_cost_input,
        "base_credit_cost_output": base_credit_cost_output,
        "modified_credit_cost_output": modified_credit_cost_output,
        "total_predicted_credit_cost": total_predicted_credit_cost
    }

def calculate_actual_summaries_cost(input_token_count, summaries_text, model='o1-mini'):
    """
	Calculates the actual cost of summaries based on input token count and summaries text.
    
    Args:
        input_token_count (int): The number of input tokens.
        summaries_text (str): The text of the summaries for which the cost is calculated.
        model (str, optional): The model used for token counting. Defaults to 'o1-mini'.
    
    Returns:
        dict: A dictionary containing the following keys:
            - input_tokens (int): The number of input tokens.
            - output_tokens (int): The number of output tokens calculated from summaries text.
            - model (str): The model used for the calculation.
            - input_tokens_per_credit (float): The number of input tokens per credit.
            - output_tokens_per_credit (float): The number of output tokens per credit.
            - base_credit_cost_input (int): The base credit cost for input tokens.
            - modified_credit_cost_input (int): The modified credit cost for input tokens after applying any modifiers.
            - base_credit_cost_output (int): The base credit cost for output tokens.
            - modified_credit_cost_output (int): The modified credit cost for output tokens after applying any modifiers.
            - total_actual_credit_cost (int): The total actual credit cost for both input and output tokens.
    """
    output_token_count = count_tokens(summaries_text, model)
    
    tokenCostConfig = TokenCostConfig.query.first()
    cost_per_million_input = tokenCostConfig.o1_cost_per_1m_input
    cost_per_million_output = tokenCostConfig.o1_cost_per_1m_output
    credit_cost_dollar = tokenCostConfig.o1_cost_per_credit

    input_tokens_per_credit = round((credit_cost_dollar * 1_000_000) / cost_per_million_input, 2)
    output_tokens_per_credit = round((credit_cost_dollar * 1_000_000) / cost_per_million_output, 2)
    
    base_credit_cost_input = round(input_token_count / input_tokens_per_credit)
    base_credit_cost_output = round(output_token_count / output_tokens_per_credit)
    
    config_in = CreditConfig.query.filter_by(action="summary_input").first()
    modifier_input = config_in.modifier if config_in else 2
    config_out = CreditConfig.query.filter_by(action="summary_output").first()
    modifier_output = config_out.modifier if config_out else 2
    
    modified_credit_cost_input = round(base_credit_cost_input * modifier_input)
    modified_credit_cost_output = round(base_credit_cost_output * modifier_output)
    total_actual_credit_cost = modified_credit_cost_input + modified_credit_cost_output

    return {
        "input_tokens": input_token_count,
        "output_tokens": output_token_count,
        "model": model,
        "input_tokens_per_credit": input_tokens_per_credit,
        "output_tokens_per_credit": output_tokens_per_credit,
        "base_credit_cost_input": base_credit_cost_input,
        "modified_credit_cost_input": modified_credit_cost_input,
        "base_credit_cost_output": base_credit_cost_output,
        "modified_credit_cost_output": modified_credit_cost_output,
        "total_actual_credit_cost": total_actual_credit_cost
    }

def calculate_predicted_story_arcs_cost(story, model='o1-mini'):
    """
	Calculate the predicted cost of story arcs based on the provided story and model.
    
    Args:
        story (Story): The story object containing details such as title, chapters, characters, and locations.
        model (str, optional): The model to be used for token counting. Defaults to 'o1-mini'.
    
    Returns:
        dict: A dictionary containing the following keys:
            - input_tokens (int): The number of input tokens calculated from the story prompt.
            - predicted_output_tokens (int): The predicted number of output tokens (fixed at 250).
            - input_tokens_per_credit (float): The number of input tokens that can be processed per credit.
            - output_tokens_per_credit (float): The number of output tokens that can be processed per credit.
            - base_credit_cost_input (int): The base credit cost for input tokens.
            - modified_credit_cost_input (int): The modified credit cost for input tokens after applying any modifiers.
            - base_credit_cost_output (int): The base credit cost for output tokens.
            - modified_credit_cost_output (int): The modified credit cost for output tokens after applying any modifiers.
            - total_predicted_credit_cost (int): The total predicted credit cost for processing the story arcs.
    """
    num_chapters = story.chapters_count
    characters = Character.query.filter_by(story_id=story.id).all()
    locations = Location.query.filter_by(story_id=story.id).all()
    full_prompt = build_story_arcs_prompt(story.title, story.details, num_chapters,
                                          ", ".join([tag.name for tag in story.tags]) if story.tags else "",
                                          {"characters": [{"name": c.name, "description": c.description} for c in characters],
                                           "locations": [{"name": l.name, "description": l.description} for l in locations]})
    input_token_count = count_tokens(full_prompt, model)

    tokenCostConfig = TokenCostConfig.query.first()
    cost_per_million_input = tokenCostConfig.o1_cost_per_1m_input
    cost_per_million_output = tokenCostConfig.o1_cost_per_1m_output
    credit_cost_dollar = tokenCostConfig.o1_cost_per_credit

    input_tokens_per_credit = round((credit_cost_dollar * 1_000_000) / cost_per_million_input, 2)
    output_tokens_per_credit = round((credit_cost_dollar * 1_000_000) / cost_per_million_output, 2)

    base_credit_cost_input = max(1, round(input_token_count / input_tokens_per_credit))
    predicted_output_tokens = 250
    base_credit_cost_output = max(1, round(predicted_output_tokens / output_tokens_per_credit))

    config_in = CreditConfig.query.filter_by(action="arcs_input").first()
    modifier_input = config_in.modifier if config_in else 2
    config_out = CreditConfig.query.filter_by(action="arcs_output").first()
    modifier_output = config_out.modifier if config_out else 2

    modified_credit_cost_input = round(base_credit_cost_input * modifier_input)
    modified_credit_cost_output = round(base_credit_cost_output * modifier_output)
    total_predicted_credit_cost = modified_credit_cost_input + modified_credit_cost_output

    return {
        "input_tokens": input_token_count,
        "predicted_output_tokens": predicted_output_tokens,
        "input_tokens_per_credit": input_tokens_per_credit,
        "output_tokens_per_credit": output_tokens_per_credit,
        "base_credit_cost_input": base_credit_cost_input,
        "modified_credit_cost_input": modified_credit_cost_input,
        "base_credit_cost_output": base_credit_cost_output,
        "modified_credit_cost_output": modified_credit_cost_output,
        "total_predicted_credit_cost": total_predicted_credit_cost
    }

def calculate_actual_story_arcs_cost(input_token_count, arcs_text, model='o1-mini'):
    """
	Calculates the actual cost of story arcs based on input token count and arcs text.
    
    Args:
        input_token_count (int): The number of input tokens.
        arcs_text (str): The text of the story arcs for which the cost is being calculated.
        model (str, optional): The model to be used for token counting. Defaults to 'o1-mini'.
    
    Returns:
        dict: A dictionary containing the following keys:
            - input_tokens (int): The number of input tokens.
            - output_tokens (int): The number of output tokens calculated from arcs_text.
            - model (str): The model used for the calculation.
            - input_tokens_per_credit (float): The number of input tokens that can be purchased per credit.
            - output_tokens_per_credit (float): The number of output tokens that can be purchased per credit.
            - base_credit_cost_input (int): The base credit cost for input tokens.
            - modified_credit_cost_input (int): The modified credit cost for input tokens after applying any modifiers.
            - base_credit_cost_output (int): The base credit cost for output tokens.
            - modified_credit_cost_output (int): The modified credit cost for output tokens after applying any modifiers.
            - total_actual_credit_cost (int): The total actual credit cost for both input and output tokens.
    """
    output_token_count = count_tokens(arcs_text, model)

    tokenCostConfig = TokenCostConfig.query.first()
    cost_per_million_input = tokenCostConfig.o1_cost_per_1m_input
    cost_per_million_output = tokenCostConfig.o1_cost_per_1m_output
    credit_cost_dollar = tokenCostConfig.o1_cost_per_credit

    input_tokens_per_credit = round((credit_cost_dollar * 1_000_000) / cost_per_million_input, 2)
    output_tokens_per_credit = round((credit_cost_dollar * 1_000_000) / cost_per_million_output, 2)

    base_credit_cost_input = max(1, round(input_token_count / input_tokens_per_credit))
    base_credit_cost_output = max(1, round(output_token_count / output_tokens_per_credit))

    config_in = CreditConfig.query.filter_by(action="arcs_input").first()
    modifier_input = config_in.modifier if config_in else 2
    config_out = CreditConfig.query.filter_by(action="arcs_output").first()
    modifier_output = config_out.modifier if config_out else 2

    modified_credit_cost_input = round(base_credit_cost_input * modifier_input)
    modified_credit_cost_output = round(base_credit_cost_output * modifier_output)
    total_actual_credit_cost = modified_credit_cost_input + modified_credit_cost_output

    return {
        "input_tokens": input_token_count,
        "output_tokens": output_token_count,
        "model": model,
        "input_tokens_per_credit": input_tokens_per_credit,
        "output_tokens_per_credit": output_tokens_per_credit,
        "base_credit_cost_input": base_credit_cost_input,
        "modified_credit_cost_input": modified_credit_cost_input,
        "base_credit_cost_output": base_credit_cost_output,
        "modified_credit_cost_output": modified_credit_cost_output,
        "total_actual_credit_cost": total_actual_credit_cost
    }

def calculate_predicted_chapter_guide_cost(story, model='o1-mini'):
    """
	Calculate the predicted cost of Chapter Guides for a given story.
    
    Args:
        story (Story): The story object containing details such as title, tags, chapters, and arcs.
        model (str, optional): The model to be used for token counting. Defaults to 'o1-mini'.
    
    Returns:
        dict: A dictionary containing the following keys:
            - input_tokens (int): The number of input tokens calculated from the prompt.
            - predicted_output_tokens (int): The predicted number of output tokens.
            - input_tokens_per_credit (float): The number of input tokens that can be processed per credit.
            - output_tokens_per_credit (float): The number of output tokens that can be generated per credit.
            - base_credit_cost_input (int): The base credit cost for input tokens.
            - modified_credit_cost_input (int): The modified credit cost for input tokens after applying any modifiers.
            - base_credit_cost_output (int): The base credit cost for output tokens.
            - modified_credit_cost_output (int): The modified credit cost for output tokens after applying any modifiers.
            - total_predicted_credit_cost (int): The total predicted credit cost combining both input and output costs.
    """
    tags = ", ".join([tag.name for tag in story.tags]) if story.tags else ""
    meta = {
        "characters": [{"name": c.name, "description": c.description or ""} 
                       for c in Character.query.filter_by(story_id=story.id).all()],
        "locations": [{"name": l.name, "description": l.description or ""} 
                      for l in Location.query.filter_by(story_id=story.id).all()]
    }
    chapters = sorted(story.chapters, key=lambda c: c.chapter_number)
    chapter_titles = [ch.title for ch in chapters]
    summaries = [ch.summary or "" for ch in chapters]
    overall_arcs = [arc.arc_text for arc in story.arcs] if story.arcs else []
    
    prompt = build_chapter_guide_prompt(
        story.title,
        story.details or "",
        tags,
        meta,
        chapter_titles,
        summaries,
        overall_arcs
    )
    input_token_count = count_tokens(prompt, model)
    
    tokenCostConfig = TokenCostConfig.query.first()
    cost_per_million_input = tokenCostConfig.o1_cost_per_1m_input
    cost_per_million_output = tokenCostConfig.o1_cost_per_1m_output
    credit_cost_dollar = tokenCostConfig.o1_cost_per_credit

    input_tokens_per_credit = round((credit_cost_dollar * 1_000_000) / cost_per_million_input, 2)
    output_tokens_per_credit = round((credit_cost_dollar * 1_000_000) / cost_per_million_output, 2)
    
    base_credit_cost_input = max(1, round(input_token_count / input_tokens_per_credit))
    predicted_output_tokens = 250
    base_credit_cost_output = max(1, round(predicted_output_tokens / output_tokens_per_credit))
    
    config_in = CreditConfig.query.filter_by(action="chapter_guide_input").first()
    modifier_input = config_in.modifier if config_in else 2
    config_out = CreditConfig.query.filter_by(action="chapter_guide_output").first()
    modifier_output = config_out.modifier if config_out else 2
    
    modified_credit_cost_input = round(base_credit_cost_input * modifier_input)
    modified_credit_cost_output = round(base_credit_cost_output * modifier_output)
    total_predicted_credit_cost = modified_credit_cost_input + modified_credit_cost_output
    
    return {
        "input_tokens": input_token_count,
        "predicted_output_tokens": predicted_output_tokens,
        "input_tokens_per_credit": input_tokens_per_credit,
        "output_tokens_per_credit": output_tokens_per_credit,
        "base_credit_cost_input": base_credit_cost_input,
        "modified_credit_cost_input": modified_credit_cost_input,
        "base_credit_cost_output": base_credit_cost_output,
        "modified_credit_cost_output": modified_credit_cost_output,
        "total_predicted_credit_cost": total_predicted_credit_cost
    }

def calculate_actual_chapter_guide_cost(input_token_count, chapter_guide_text, model='o1-mini'):
    """
	Calculates the actual Chapter Guides cost based on input token count and Chapter Guides text.
    
    Args:
        input_token_count (int): The number of input tokens.
        chapter_guide_text (str): The text containing Chapter Guides for which the cost is to be calculated.
        model (str, optional): The model to be used for token counting. Defaults to 'o1-mini'.
    
    Returns:
        dict: A dictionary containing the following keys:
            - input_tokens (int): The number of input tokens.
            - output_tokens (int): The number of output tokens calculated from the Chapter Guides text.
            - model (str): The model used for the calculation.
            - input_tokens_per_credit (float): The number of input tokens that can be purchased per credit.
            - output_tokens_per_credit (float): The number of output tokens that can be purchased per credit.
            - base_credit_cost_input (int): The base credit cost for input tokens.
            - modified_credit_cost_input (int): The modified credit cost for input tokens after applying any modifiers.
            - base_credit_cost_output (int): The base credit cost for output tokens.
            - modified_credit_cost_output (int): The modified credit cost for output tokens after applying any modifiers.
            - total_actual_credit_cost (int): The total actual credit cost combining both input and output costs.
    """
    output_token_count = count_tokens(chapter_guide_text, model)
    
    tokenCostConfig = TokenCostConfig.query.first()
    cost_per_million_input = tokenCostConfig.o1_cost_per_1m_input
    cost_per_million_output = tokenCostConfig.o1_cost_per_1m_output
    credit_cost_dollar = tokenCostConfig.o1_cost_per_credit

    input_tokens_per_credit = round((credit_cost_dollar * 1_000_000) / cost_per_million_input, 2)
    output_tokens_per_credit = round((credit_cost_dollar * 1_000_000) / cost_per_million_output, 2)
    
    base_credit_cost_input = max(1, round(input_token_count / input_tokens_per_credit))
    base_credit_cost_output = max(1, round(output_token_count / output_tokens_per_credit))
    
    config_in = CreditConfig.query.filter_by(action="chapter_guide_input").first()
    modifier_input = config_in.modifier if config_in else 2
    config_out = CreditConfig.query.filter_by(action="chapter_guide_output").first()
    modifier_output = config_out.modifier if config_out else 2
    
    modified_credit_cost_input = round(base_credit_cost_input * modifier_input)
    modified_credit_cost_output = round(base_credit_cost_output * modifier_output)
    total_actual_credit_cost = modified_credit_cost_input + modified_credit_cost_output
    
    return {
        "input_tokens": input_token_count,
        "output_tokens": output_token_count,
        "model": model,
        "input_tokens_per_credit": input_tokens_per_credit,
        "output_tokens_per_credit": output_tokens_per_credit,
        "base_credit_cost_input": base_credit_cost_input,
        "modified_credit_cost_input": modified_credit_cost_input,
        "base_credit_cost_output": base_credit_cost_output,
        "modified_credit_cost_output": modified_credit_cost_output,
        "total_actual_credit_cost": total_actual_credit_cost
    }

def calculate_predicted_chapter_cost(story, chapter_index, model='o1-mini'):
    """
	Calculate the predicted cost of generating a chapter based on the provided story and chapter index.
    
    Args:
        story (Story): The story object containing details about the chapters, title, inspirations, writing style, and tags.
        chapter_index (int): The index of the chapter for which the cost is to be calculated.
        model (str, optional): The model to be used for token counting. Defaults to 'o1-mini'.
    
    Returns:
        dict: A dictionary containing the following keys:
            - input_tokens (int): The number of input tokens required.
            - predicted_output_tokens (int): The predicted number of output tokens.
            - input_tokens_per_credit (float): The number of input tokens that can be generated per credit.
            - output_tokens_per_credit (float): The number of output tokens that can be generated per credit.
            - base_credit_cost_input (int): The base credit cost for input tokens.
            - modified_credit_cost_input (int): The modified credit cost for input tokens after applying any modifiers.
            - base_credit_cost_output (int): The base credit cost for output tokens.
            - modified_credit_cost_output (int): The modified credit cost for output tokens after applying any modifiers.
            - total_predicted_credit_cost (int): The total predicted credit cost for generating the chapter.
    """
    chapters = sorted(story.chapters, key=lambda c: c.chapter_number) if story.chapters else []
    if chapter_index < len(chapters):
        chapter_obj = chapters[chapter_index]
    else:
        chapter_obj = None
    chapter_title = chapter_obj.title if chapter_obj else ""
    chapter_summary = chapter_obj.summary if (chapter_obj and chapter_obj.summary) else ""
    
    details = story.details or ""
    book_title = story.title
    inspirations = story.inspirations or ""
    writing_style = story.writing_style or ""
    tags = ", ".join([tag.name for tag in story.tags]) if story.tags else ""
    
    previous_summary = chapters[chapter_index - 1].summary if chapter_index - 1 >= 0 else ""
    next_summary = chapters[chapter_index + 1].summary if chapter_index + 1 < len(chapters) else ""
    
    chapter_mappings = ChapterGuide.query.filter_by(
        story_id=story.id, chapter_title=chapter_title
    ).order_by(ChapterGuide.part_index).all()
    detailed_arc_parts = [{
         "arc": mapping.part_index,
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
        Character.story_id == story.id,
        Character.name.in_(list(unique_characters))
    ).all()

    location_objs = Location.query.filter(
        Location.story_id == story.id,
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
        chapter_title, chapter_summary, book_title, details, tags,
        detailed_arc_parts,
        previous_summary, next_summary,
        inspirations, writing_style,
        character_details, location_details
    )
    input_token_count = count_tokens(full_prompt, model)
    predicted_output_tokens = 300

    tokenCostConfig = TokenCostConfig.query.first()
    cost_per_million_input = tokenCostConfig.o1_cost_per_1m_input
    cost_per_million_output = tokenCostConfig.o1_cost_per_1m_output
    credit_cost_dollar = tokenCostConfig.o1_cost_per_credit

    input_tokens_per_credit = round((credit_cost_dollar * 1_000_000) / cost_per_million_input, 2)
    output_tokens_per_credit = round((credit_cost_dollar * 1_000_000) / cost_per_million_output, 2)
    base_credit_cost_input = round(input_token_count / input_tokens_per_credit)
    base_credit_cost_output = round(predicted_output_tokens / output_tokens_per_credit)

    config_in = CreditConfig.query.filter_by(action="chapter_input").first()
    modifier_input = config_in.modifier if config_in else 2
    config_out = CreditConfig.query.filter_by(action="chapter_output").first()
    modifier_output = config_out.modifier if config_out else 2

    modified_credit_cost_input = round(base_credit_cost_input * modifier_input)
    modified_credit_cost_output = round(base_credit_cost_output * modifier_output)
    total_predicted_credit_cost = modified_credit_cost_input + modified_credit_cost_output

    return {
        "input_tokens": input_token_count,
        "predicted_output_tokens": predicted_output_tokens,
        "input_tokens_per_credit": input_tokens_per_credit,
        "output_tokens_per_credit": output_tokens_per_credit,
        "base_credit_cost_input": base_credit_cost_input,
        "modified_credit_cost_input": modified_credit_cost_input,
        "base_credit_cost_output": base_credit_cost_output,
        "modified_credit_cost_output": modified_credit_cost_output,
        "total_predicted_credit_cost": total_predicted_credit_cost
    }


def calculate_actual_chapter_cost(input_token_count, chapter_text, model='o1-mini'):
    """
	Calculates the actual cost of processing a chapter based on input and output token counts.
    
    Args:
        input_token_count (int): The number of input tokens for the chapter.
        chapter_text (str): The text of the chapter to be processed.
        model (str, optional): The model used for token counting. Defaults to 'o1-mini'.
    
    Returns:
        dict: A dictionary containing the following keys:
            - input_tokens (int): The number of input tokens.
            - output_tokens (int): The number of output tokens calculated from the chapter text.
            - model (str): The model used for the calculation.
            - input_tokens_per_credit (float): The number of input tokens that can be processed per credit.
            - output_tokens_per_credit (float): The number of output tokens that can be processed per credit.
            - base_credit_cost_input (int): The base credit cost for input tokens.
            - modified_credit_cost_input (int): The modified credit cost for input tokens after applying any modifiers.
            - base_credit_cost_output (int): The base credit cost for output tokens.
            - modified_credit_cost_output (int): The modified credit cost for output tokens after applying any modifiers.
            - total_actual_credit_cost (int): The total actual credit cost for processing the chapter.
    """
    output_token_count = count_tokens(chapter_text, model)
    
    tokenCostConfig = TokenCostConfig.query.first()
    cost_per_million_input = tokenCostConfig.o1_cost_per_1m_input
    cost_per_million_output = tokenCostConfig.o1_cost_per_1m_output
    credit_cost_dollar = tokenCostConfig.o1_cost_per_credit
    
    input_tokens_per_credit = round((credit_cost_dollar * 1_000_000) / cost_per_million_input, 2)
    output_tokens_per_credit = round((credit_cost_dollar * 1_000_000) / cost_per_million_output, 2)
    base_credit_cost_input = round(input_token_count / input_tokens_per_credit)
    base_credit_cost_output = round(output_token_count / output_tokens_per_credit)
    
    config_in = CreditConfig.query.filter_by(action="chapter_input").first()
    modifier_input = config_in.modifier if config_in else 2
    config_out = CreditConfig.query.filter_by(action="chapter_output").first()
    modifier_output = config_out.modifier if config_out else 2
    
    modified_credit_cost_input = round(base_credit_cost_input * modifier_input)
    modified_credit_cost_output = round(base_credit_cost_output * modifier_output)
    total_actual_credit_cost = modified_credit_cost_input + modified_credit_cost_output
    
    return {
        "input_tokens": input_token_count,
        "output_tokens": output_token_count,
        "model": model,
        "input_tokens_per_credit": input_tokens_per_credit,
        "output_tokens_per_credit": output_tokens_per_credit,
        "base_credit_cost_input": base_credit_cost_input,
        "modified_credit_cost_input": modified_credit_cost_input,
        "base_credit_cost_output": base_credit_cost_output,
        "modified_credit_cost_output": modified_credit_cost_output,
        "total_actual_credit_cost": total_actual_credit_cost
    }

def calculate_predicted_all_chapters_cost(story, model='o1-mini'):
    """
	Calculates the predicted total cost for all chapters in a story using a specified model.
    
    Args:
        story (Story): The story object containing chapters to be evaluated.
        model (str, optional): The model to use for cost prediction. Defaults to 'o1-mini'.
    
    Returns:
        dict: A dictionary containing the total predicted credit cost and a breakdown of costs for each chapter.
            - total_predicted_credit_cost (float): The total predicted cost for all chapters.
            - chapters (list): A list of dictionaries, each containing:
                - chapter_index (int): The index of the chapter.
                - predicted_cost (float): The predicted cost for the chapter.
                - details (dict): Additional details about the cost prediction for the chapter.
    """
    chapters = sorted(story.chapters, key=lambda c: c.chapter_number) if story.chapters else []
    total_cost = 0
    breakdown = []
    for i in range(len(chapters)):
        cost_info = calculate_predicted_chapter_cost(story, i, model)
        breakdown.append({
            "chapter_index": i,
            "predicted_cost": cost_info["total_predicted_credit_cost"],
            "details": cost_info
        })
        total_cost += cost_info["total_predicted_credit_cost"]
    return {
        "total_predicted_credit_cost": total_cost,
        "chapters": breakdown
    }