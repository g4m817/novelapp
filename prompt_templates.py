
import tiktoken
def count_tokens(prompt, model="gpt-4o-mini"):
    """
    Counts the number of tokens in a given prompt using the specified model.
    
    Args:
        prompt (str): The input text for which to count the tokens.
        model (str, optional): The model to use for encoding. Defaults to "gpt-4o-mini".
    
    Returns:
        int: The number of tokens in the encoded prompt.
    
    Raises:
        Exception: If the model is not recognized, it falls back to the default encoding.
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except Exception:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(prompt))


def build_meta_prompt(title, details, tags, inspirations, total_chapters):
    """
    Generates a prompt for creating characters and locations for a story using XML structure.
    
    This version includes an XML instruction block to clearly separate metadata and contextual instructions,
    and encourages creative, human-like responses.
    
    Args:
        title (str): The title of the story.
        details (str): A brief description of the story.
        tags (str): Tags associated with the story.
        inspirations (str): Sources of inspiration for the story (optional).
        total_chapters (int): The total number of chapters in the story.
    
    Returns:
        str: A formatted prompt with XML instructions.
    """
    inspirations_prompt = f"<inspirations>{inspirations}</inspirations>" if inspirations else ""
    template = (
        "You are a creative, experienced novelist tasked with establishing the foundational world of a new novel. "
        "Please avoid clichéd or generic phrases and focus on rich, bursty narrative details.\n\n"
        "<story>\n"
        "  <title>{title}</title>\n"
        "  <details>{details}</details>\n"
        "  <tags>{tags}</tags>\n"
        "  {inspirations_prompt}\n"
        "  <structure totalChapters='{total_chapters}' />\n"
        "</story>\n\n"
        "Your task: Generate a JSON object with two keys: 'locations' and 'characters'. Each key must map to an array of objects. "
        "Each object in 'locations' must include 'name' and 'description'. Each object in 'characters' must include 'name', "
        "'description', and an 'example_dialogue' field. "
        "Ensure your response is creative, contextually rich, and strictly in JSON format with no markdown formatting."
    )
    return template.format(
        title=title,
        details=details,
        tags=tags,
        inspirations_prompt=inspirations_prompt,
        total_chapters=total_chapters
    )


def build_chapter_summaries_prompt(title, details, tags, meta, arcs, inspirations, total_chapters):
    """
    Generates a prompt for creating Chapter Summaries using both natural language instructions and XML-based context.
    
    Args:
        title (str): The title of the story.
        details (str): A brief description of the story.
        tags (str): Tags associated with the story.
        meta (dict): Metadata containing characters and locations.
        arcs (list of str): A list of story arcs relevant to the narrative.
        inspirations (str or None): Inspirations for the story, if any.
        total_chapters (int): The total number of chapters to generate.
    
    Returns:
        str: A formatted prompt for generating chapter summaries, integrating XML instructions.
    """
    inspirations_prompt = f"<inspirations>{inspirations}</inspirations>" if inspirations else ""
    meta_characters = "\n".join(f"    <character name='{c['name']}'>{c['description']}</character>" for c in meta.get("characters", []))
    meta_locations = "\n".join(f"    <location name='{l['name']}'>{l['description']}</location>" for l in meta.get("locations", []))
    arcs_str = "\n".join(f"    <arc>{arc}</arc>" for arc in arcs) if arcs else ""
    template = (
        "You are a master storyteller tasked with outlining the structure for a novel. Avoid common AI clichés; be vibrant and human-like.\n\n"
        "<storyContext>\n"
        "  <title>{title}</title>\n"
        "  <details>{details}</details>\n"
        "  <tags>{tags}</tags>\n"
        "  <metadata>\n"
        "    <characters>\n{meta_characters}\n    </characters>\n"
        "    <locations>\n{meta_locations}\n    </locations>\n"
        "  </metadata>\n"
        "  <arcs>\n{arcs}</arcs>\n"
        "  {inspirations_prompt}\n"
        "  <chapters total='{total_chapters}' />\n"
        "</storyContext>\n\n"
        "Task: Generate an array of JSON objects, each with a 'title' and 'summary' for every chapter. "
        "Each chapter summary should be concise yet evocative, hinting at key emotional beats and events, without revealing every detail. "
        "Respond solely with valid JSON (no markdown formatting)."
    )
    return template.format(
        title=title,
        details=details,
        tags=tags,
        meta_characters=meta_characters,
        meta_locations=meta_locations,
        arcs=arcs_str,
        inspirations_prompt=inspirations_prompt,
        total_chapters=total_chapters
    )


def build_story_arcs_prompt(title, details, total_chapters, tags, meta):
    """
    Generates a prompt for creating overall story arcs with XML-enhanced instructions.
    
    Args:
        title (str): The title of the story.
        details (str): A brief description of the story.
        total_chapters (int): The total number of chapters in the story.
        tags (str): Tags associated with the story.
        meta (dict): Metadata containing characters and locations.
    
    Returns:
        str: A formatted prompt for generating story arcs as a JSON array.
    """
    meta_characters = ", ".join(f"{c['name']}" for c in meta.get("characters", []))
    meta_locations = ", ".join(f"{l['name']}" for l in meta.get("locations", []))
    template = (
        "As an imaginative novelist, you are to conceive a series of cohesive story arcs for the following tale. "
        "Aim for a natural, human tone that avoids overly mechanical phrasing.\n\n"
        "<novel>\n"
        "  <title>{title}</title>\n"
        "  <details>{details}</details>\n"
        "  <tags>{tags}</tags>\n"
        "  <metadata characters='{meta_characters}' locations='{meta_locations}' />\n"
        "  <structure chapters='{total_chapters}' />\n"
        "</novel>\n\n"
        "Instructions: Generate an unstructured list (JSON array of strings) of overarching story arcs. "
        "Do not assign arcs to specific chapters in this step. Output must be valid JSON with no markdown formatting."
    )
    return template.format(
        title=title,
        details=details,
        tags=tags,
        meta_characters=meta_characters,
        meta_locations=meta_locations,
        total_chapters=total_chapters
    )


def build_chapter_guide_prompt(title, details, tags, meta, chapters, summaries, arcs):
    """
    Generates a detailed prompt for breaking down narrative arcs for each chapter using XML for context.
    
    Args:
        title (str): The title of the story.
        details (str): A brief description of the story.
        tags (str): Tags associated with the story.
        meta (dict): Metadata containing characters and locations.
        chapters (list of str): A list of chapter titles.
        summaries (list of str): A list of chapter summaries (fallback to chapter titles if empty).
        arcs (list of str): A list of overall story arcs.
    
    Returns:
        str: A formatted prompt instructing the breakdown of each chapter into detailed arc parts, returned as a JSON object.
    """
    chapters_list = "\n".join(f"    <chapter>{ct}</chapter>" for ct in chapters)
    summaries_list = "\n".join(f"    <summary>{s}</summary>" for s in (summaries if summaries else chapters))
    meta_characters = ", ".join(f"{c['name']}" for c in meta.get("characters", []))
    meta_locations = ", ".join(f"{l['name']}" for l in meta.get("locations", []))
    arcs_str = ", ".join(arcs)
    
    template = (
        "You are a seasoned narrative architect. Using the XML framework below, decompose the story into detailed arc segments for each chapter. "
        "Ensure your language is dynamic, varied, and avoids the repetitive phrasing often seen in generic AI outputs.\n\n"
        "<novel>\n"
        "  <title>{title}</title>\n"
        "  <details>{details}</details>\n"
        "  <tags>{tags}</tags>\n"
        "  <metadata characters='{meta_characters}' locations='{meta_locations}' />\n"
        "  <overallArcs>{arcs_str}</overallArcs>\n"
        "  <chapters>\n{chapters_list}\n  </chapters>\n"
        "  <chapterSummaries>\n{summaries_list}\n  </chapterSummaries>\n"
        "</novel>\n\n"
        "For each chapter, break down the narrative into a series of arc objects. Each object should include:\n"
        "  - 'arc': a sequence number\n"
        "  - 'arc_text': a descriptive narrative segment\n"
        "  - 'characters': a list of referenced character names\n"
        "  - 'locations': a list of referenced location names\n\n"
        "Output your answer as a JSON object where each key is a chapter title and its value is an array of arc objects. "
        "The response must be valid JSON with no markdown formatting."
    )
    
    return template.format(
        title=title,
        details=details,
        tags=tags,
        meta_characters=meta_characters,
        meta_locations=meta_locations,
        arcs_str=arcs_str,
        chapters_list=chapters_list,
        summaries_list=summaries_list
    )


def build_chapter_content_prompt(chapter_title, chapter_summary, book_title, details, tags,
                                 detailed_arc_parts, prev_summary, next_summary,
                                 inspirations, writing_style, character_details, location_details):
    """
    Builds a detailed prompt for generating chapter content that flows naturally, using XML to define context and structure.
    
    The prompt is designed to guide the output to be engaging, varied in tone, and narrative-driven.
    
    Args:
        chapter_title (str): The title of the chapter.
        chapter_summary (str): A brief summary of the chapter.
        book_title (str): The title of the book.
        details (str): Additional details for the chapter.
        tags (str): Tags for the chapter.
        detailed_arc_parts (list): A list of dictionaries with arc details.
        prev_summary (str): Summary of the previous chapter.
        next_summary (str): Summary of the next chapter.
        inspirations (str): Inspirations for the chapter.
        writing_style (str): Desired writing style.
        character_details (dict): Mapping of character names to metadata.
        location_details (dict): Mapping of location names to descriptions.
    
    Returns:
        str: A formatted prompt string in Markdown that instructs the generation of chapter content.
    """
    # Build the detailed arc breakdown as bullet points.
    arc_lines = []
    for idx, arc in enumerate(detailed_arc_parts, start=1):
        line = f"{idx}. {arc.get('arc_text', '')}"
        chars = arc.get("characters", [])
        locs = arc.get("locations", [])
        if chars:
            line += f" (Characters: {', '.join(chars)})"
        if locs:
            line += f" (Locations: {', '.join(locs)})"
        arc_lines.append(line)
    arcs_prompt = "Detailed Arc Breakdown:\n" + "\n".join(arc_lines) + "\n" if arc_lines else ""
    inspirations_prompt = f"<inspirations>{inspirations}</inspirations>\n" if inspirations else ""
    writing_style_prompt = f"<writingStyle>{writing_style}</writingStyle>\n" if writing_style else ""
    
    if character_details:
        character_mapping = "Character Metadata:\n" + "\n".join(
            f"- {name}: {info['description']} (Dialogue: {info['example_dialogue']})"
            for name, info in character_details.items()
        ) + "\n"
    else:
        character_mapping = ""
    
    if location_details:
        location_mapping = "Location Metadata:\n" + "\n".join(
            f"- {name}: {desc}" for name, desc in location_details.items()
        ) + "\n"
    else:
        location_mapping = ""
    
    template = (
        "You are a highly skilled storyteller with a talent for crafting immersive and emotionally charged chapters. "
        "Your language should be vivid, dynamic, and avoid formulaic phrasing. Below is the XML-structured context for this chapter.\n\n"
        "<chapterContext>\n"
        "  <bookTitle>{book_title}</bookTitle>\n"
        "  <chapterTitle>{chapter_title}</chapterTitle>\n"
        "  <chapterSummary>{chapter_summary}</chapterSummary>\n"
        "  <previousSummary>{prev_summary}</previousSummary>\n"
        "  <nextSummary>{next_summary}</nextSummary>\n"
        "  <details>{details}</details>\n"
        "  <tags>{tags}</tags>\n"
        "  {inspirations_prompt}\n"
        "  {writing_style_prompt}\n"
        "  <metadata>\n"
        "    <characters>\n{character_mapping}\n    </characters>\n"
        "    <locations>\n{location_mapping}\n    </locations>\n"
        "  </metadata>\n"
        "</chapterContext>\n\n"
        "{arcs_prompt}\n"
        "Instructions: Using the above context and detailed arc breakdown, craft a complete, cohesive chapter in Markdown format. "
        "Ensure the narrative has a clear beginning, middle, and end, and flows naturally from the previous chapter while setting up the next. "
        "Do not include the chapter title as a header in the final output."
    )
    
    return template.format(
        book_title=book_title,
        chapter_title=chapter_title,
        chapter_summary=chapter_summary,
        prev_summary=prev_summary,
        next_summary=next_summary,
        details=details,
        tags=tags,
        inspirations_prompt=inspirations_prompt,
        writing_style_prompt=writing_style_prompt,
        character_mapping=character_mapping,
        location_mapping=location_mapping,
        arcs_prompt=arcs_prompt
    )