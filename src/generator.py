# FILE: src/generator.py
# FINAL, CLEAN VERSION: Compatible with per-slide audio sync, dynamic slides, and GitHub Actions.

import os
import json
import time
import random
import requests
from io import BytesIO
from google import genai
from gtts import gTTS
from gtts.tts import GTTSError
from moviepy.editor import AudioFileClip, ImageClip, CompositeAudioClip, concatenate_videoclips, vfx
from moviepy.config import change_settings
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
from pydub import AudioSegment

# --- Configuration ---
ASSETS_PATH = Path("assets")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")

try:
    from moviepy.config import get_setting
    imagemagick_path = get_setting("IMAGEMAGICK_BINARY")
    if not imagemagick_path or imagemagick_path == "unset":
        change_settings({"IMAGEMAGICK_BINARY": "convert"})
except Exception as e:
    print(f"Warning: Could not check or set ImageMagick configuration: {e}")

# --- Helper Functions ---

def get_pexels_image(query, video_type):
    if not PEXELS_API_KEY:
        print("PEXELS_API_KEY not set. Skipping image fetch.")
        return None
    
    headers = {"Authorization": PEXELS_API_KEY}
    orientation = "portrait" if video_type == "short" else "landscape"
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=15&orientation={orientation}"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        if data.get("photos"):
            photo = random.choice(data["photos"])
            image_url = photo["src"]["large2x"] if orientation == "landscape" else photo["src"]["large"]
            img_response = requests.get(image_url)
            img_response.raise_for_status()
            return Image.open(BytesIO(img_response.content))
        else:
            print(f"No Pexels images found for query: '{query}'")
            return None
    except Exception as e:
        print(f"Error fetching image from Pexels: {e}")
        return None

def create_text_image(text, font_size, text_color, bg_color, size, is_title=False, font_name="arial.ttf"):
    img = Image.new('RGBA', size, bg_color)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(font_name, font_size)
    except IOError:
        font = ImageFont.load_default()

    margin = 80
    max_width = size[0] - 2 * margin
    
    words = text.split()
    lines = []
    current_line = []
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line.append(word)
        else:
            lines.append(' '.join(current_line))
            current_line = [word]
    lines.append(' '.join(current_line))

    line_height = font.getbbox("A")[3] - font.getbbox("A")[1] + 20
    total_text_height = len(lines) * line_height
    y = (size[1] - total_text_height) / 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_width = bbox[2] - bbox[0]
        x = (size[0] - line_width) / 2
        
        shadow_color = (0, 0, 0, 180)
        draw.text((x+2, y+2), line, font=font, fill=shadow_color)
        draw.text((x, y), line, font=font, fill=text_color)
        y += line_height

    return img

def generate_curriculum(previous_titles=None):
    """Generates a list of lesson titles for the series."""
    print("Generating curriculum using Gemini...")
    try:
        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        prompt = f"""
You are creating a curriculum for a YouTube series called 'AI for Developers by {{YOUR_NAME}}'.
The goal is to teach beginner developers how to build with AI from scratch.
Provide a JSON array of 5 unique, engaging, and sequential lesson titles for this series.
Ensure titles are actionable and clear.

Example output format:
[
  "Lesson 1: Introduction to AI for Developers",
  "Lesson 2: Understanding Prompt Engineering",
  "Lesson 3: Building Your First LLM App"
]

Previous titles to avoid repeating: {previous_titles or []}
Return ONLY valid JSON.
"""
        response = client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
        json_string = response.text.strip().replace("```json", "").replace("```", "")
        titles = json.loads(json_string)
        print(f"Curriculum generated: {len(titles)} lessons.")
        return titles
    except Exception as e:
        print(f"X ERROR: Failed to generate curriculum: {e}")
        raise

def generate_lesson_content(lesson_title):
    """Generates the content for one long-form lesson and its promotional short."""
    print(f"Generating content for lesson: '{lesson_title}'...")
    try:
        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        prompt = f"""
You are creating a lesson for the 'AI for Developers by {{YOUR_NAME}}' series. The topic is '{lesson_title}'.
The style is: Assume the viewer is a beginner developer or non-tech person who wants to learn AI from scratch.
Use analogies and clear, simple language. Each concept must be explained from a developer's perspective, assuming no prior AI or ML knowledge.

Generate a JSON response with three keys:
1. "long_form_slides": A list of 7 to 8 slide objects for a longer, more detailed main video. Each object needs a "title" and "content" key.
2. "short_form_highlight": A single, punchy, 1-2 sentence summary for a YouTube Short.
3. "hashtags": A string of 5-7 relevant, space-separated hashtags for this lesson (e.g., "#GenerativeAI #LLM #Developer", "#NeuralNetworks #BeginnerAI #AIforDevelopers").

Return only valid JSON.
"""
        response = client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
        json_string = response.text.strip().replace("```json", "").replace("```", "")
        content = json.loads(json_string)
        print("Lesson content generated successfully.")
        return content
    except Exception as e:
        print(f"X ERROR: Failed to generate lesson content: {e}")
        raise
