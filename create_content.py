"""
Create Content Functions - Extracted from ATSN Agent
Contains construct, complete, and handle functions for content creation.
"""

import os
import logging
import re
import uuid
import base64
from typing import Dict, Any, List
from datetime import datetime, timedelta
import google.genai as genai
import openai
import httpx
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
supabase = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

# Initialize OpenAI client
openai_api_key = os.getenv('OPENAI_API_KEY')
openai_client = openai.OpenAI(api_key=openai_api_key) if openai_api_key else None

# Initialize Gemini client
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Gemini client initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize Gemini client: {e}")
        gemini_client = None

# ==================== CONSTANTS ====================

JSON_ONLY_INSTRUCTION = """

CRITICAL: You MUST respond with ONLY a valid JSON object. Do NOT include any explanatory text, comments, or additional text before or after the JSON.
Your response must start with {{ and end with }}. No other text is allowed.
Return ONLY the JSON object, nothing else."""

FIELD_CLARIFICATIONS = {
    "create_content": {
        "channel": {
            "question": "Let's create some content together.\n\nWhich channel would you like to focus on?",
            "options": [
                {"label": "Social Media", "value": "Social Media"},
                {"label": "Blog", "value": "Blog"}
            ]
        },
        "platform": {
            "question": "Great choice! Now, where would you like to share this content?",
            "options": [
                {"label": "Instagram", "value": "Instagram"},
                {"label": "Facebook", "value": "Facebook"},
                {"label": "LinkedIn", "value": "LinkedIn"},
                {"label": "YouTube", "value": "YouTube"}
            ]
        },
        "content_type": {
            "question": "Perfect! What kind of content are you thinking?",
            "options": [
                {"label": "Static Post", "value": "static_post"},
                {"label": "Carousel", "value": "carousel"},
                {"label": "Short Video/Reel", "value": "short_video or reel"},
                {"label": "Long Video", "value": "long_video"},
                {"label": "Blog Post", "value": "blog"}
            ]
        },
        "content_idea": {
            "question": "Great! Describe what you want to create. What should the content be about? (Tell me your main idea or topic in a few sentences)",
            "options": []
        },
        "media": {
            "question": "Awesome! Should we include some visual elements?",
            "options": [
                {"label": "Yes, Generate", "value": "Generate"},
                {"label": "I will Upload", "value": "Upload"},
                {"label": "Generate Without media", "value": "Without media"}
            ]
        },
        "content_idea": {
            "question": "Love it! Tell me more about what you have in mind. What's the main idea or topic you want to cover?",
            "options": []
        },
        "Post_type": {
            "question": "What kind of post are you thinking of?",
            "options": [],  # No multiple choice options - open-ended
            "full_options": [  # Full list for contextual LLM suggestion
                {"label": "Educational tips", "value": "Educational tips"},
                {"label": "Quote / motivation", "value": "Quote / motivation"},
                {"label": "Promotional offer", "value": "Promotional offer"},
                {"label": "Product showcase", "value": "Product showcase"},
                {"label": "Carousel infographic", "value": "Carousel infographic"},
                {"label": "Announcement", "value": "Announcement"},
                {"label": "Testimonial / review", "value": "Testimonial / review"},
                {"label": "Before–after", "value": "Before–after"},
                {"label": "Behind-the-scenes", "value": "Behind-the-scenes"},
                {"label": "User-generated content", "value": "User-generated content"},
                {"label": "Brand story", "value": "Brand story"},
                {"label": "Meme / humor", "value": "Meme / humor"},
                {"label": "Facts / did-you-know", "value": "Facts / did-you-know"},
                {"label": "Event highlight", "value": "Event highlight"},
                {"label": "Countdown", "value": "Countdown"},
                {"label": "FAQ post", "value": "FAQ post"},
                {"label": "Comparison", "value": "Comparison"},
                {"label": "Case study snapshot", "value": "Case study snapshot"},
                {"label": "Milestone / achievement", "value": "Milestone / achievement"},
                {"label": "Call-to-action post", "value": "Call-to-action post"}
            ]
        },
        "Image_type": {
            "question": "What's the visual style you have in mind for your images?",
            "options": [],  # No multiple choice options - open-ended
            "full_options": [  # Full list for contextual LLM suggestion
                {"label": "Minimal & Clean with Bold Typography", "value": "Minimal & Clean with Bold Typography"},
                {"label": "Modern Corporate / B2B Professional", "value": "Modern Corporate / B2B Professional"},
                {"label": "Luxury Editorial (Black, White, Gold Accents)", "value": "Luxury Editorial (Black, White, Gold Accents)"},
                {"label": "Photography-Led Lifestyle Aesthetic", "value": "Photography-Led Lifestyle Aesthetic"},
                {"label": "Product-Focused Clean Commercial Style", "value": "Product-Focused Clean Commercial Style"},
                {"label": "Flat Illustration with Friendly Characters", "value": "Flat Illustration with Friendly Characters"},
                {"label": "Isometric / Explainer Illustration Style", "value": "Isometric / Explainer Illustration Style"},
                {"label": "Playful & Youthful (Memphis / Stickers / Emojis)", "value": "Playful & Youthful (Memphis / Stickers / Emojis)"},
                {"label": "High-Impact Color-Blocking with Loud Type", "value": "High-Impact Color-Blocking with Loud Type"},
                {"label": "Retro / Vintage Poster Style", "value": "Retro / Vintage Poster Style"},
                {"label": "Futuristic Tech / AI-Inspired Dark Mode", "value": "Futuristic Tech / AI-Inspired Dark Mode"},
                {"label": "Glassmorphism / Neumorphism UI Style", "value": "Glassmorphism / Neumorphism UI Style"},
                {"label": "Abstract Shapes & Fluid Gradient Art", "value": "Abstract Shapes & Fluid Gradient Art"},
                {"label": "Infographic / Data-Driven Educational Layout", "value": "Infographic / Data-Driven Educational Layout"},
                {"label": "Quote Card / Thought-Leadership Typography Post", "value": "Quote Card / Thought-Leadership Typography Post"},
                {"label": "Meme-Style / Social-Native Engagement Post", "value": "Meme-Style / Social-Native Engagement Post"},
                {"label": "Festive / Campaign-Based Creative", "value": "Festive / Campaign-Based Creative"},
                {"label": "Textured Design (Paper, Grain, Handmade Feel)", "value": "Textured Design (Paper, Grain, Handmade Feel)"},
                {"label": "Magazine / Editorial Layout with Strong Hierarchy", "value": "Magazine / Editorial Layout with Strong Hierarchy"},
                {"label": "Experimental / Artistic Concept-Driven Design", "value": "Experimental / Artistic Concept-Driven Design"}
            ]
        },
    }
}

# ==================== IMPORTED FUNCTIONS FROM ATSN ====================

# These functions need to be imported from atsn.py when using this module
# - _extract_payload
# - get_contextual_suggestion
# - generate_clarifying_question
# - generate_personalized_message
# - get_business_context_from_profile
# - generate_image_enhancer_prompt
# - build_brand_color_instructions
# - build_location_context
# - generate_carousel_image_prompts
# - generate_carousel_images
# - get_trends_from_grok
# - generate_content_with_rl_agent
# - extract_hashtags_from_caption

# ==================== FUNCTIONS ====================

def construct_create_content_payload(state) -> Any:
    """Construct payload for create content task"""

    # Use user_query which contains the full conversation context
    conversation = state.user_query

    prompt = f"""You are extracting information to create content. Be EXTREMELY STRICT and CONSERVATIVE in your extraction.

CRITICAL PRINCIPLES:
1. ONLY extract information that is EXPLICITLY and CLEARLY stated
2. NEVER infer, assume, or extrapolate information
3. If uncertain about any field, set it to null
4. Quality over quantity - better to ask questions than make wrong assumptions

EXTRACTION RULES:

channel:
- Set to "Social Media" ONLY if user explicitly mentions social media platforms (Instagram, Facebook, LinkedIn, YouTube)
- Set to "Blog" ONLY if user explicitly mentions blogging, articles, or writing content for websites
- Otherwise: null

platform:
- ONLY extract if user explicitly names exactly one of: "Instagram", "Facebook", "LinkedIn", "YouTube"
- Case sensitive - must match exactly
- If multiple platforms mentioned, set to null (ask user to choose)
- Otherwise: null

content_type:
- ONLY extract if user explicitly uses these exact phrases:
  * "static post" → "static_post"
  * "carousel" → "carousel"
  * "short video" or "reel" → "short_video or reel"
  * "long video" → "long_video"
  * "blog post" or "blog" → "blog"
- Generic terms like "post", "video", "content" are NOT sufficient
- Otherwise: null

media:
- Set to "Generate" ONLY if user explicitly says they want AI-generated images/graphics/visuals
- Set to "Upload" ONLY if user explicitly says they will provide/upload their own images
- Set to "without media" ONLY if user explicitly says no images or text-only
- Otherwise: null

content_idea:
- Must be the main topic/subject explicitly stated by the user
- Must clearly explain what the content is about
- Can be a short phrase or detailed description

CLASSIFICATION (ONLY when content_idea exists and is sufficiently detailed):

Post_type:
- Choose from: Educational tips, Quote / motivation, Promotional offer, Product showcase, Carousel infographic, Announcement, Testimonial / review, Before–after, Behind-the-scenes, User-generated content, Brand story, Meme / humor, Facts / did-you-know, Event highlight, Countdown, FAQ post, Comparison, Case study snapshot, Milestone / achievement, Call-to-action post
- ONLY classify if the content_idea clearly matches one category
- If unclear which category fits best, set to null

Image_type:
- Choose from: Minimal & Clean with Bold Typography, Modern Corporate / B2B Professional, Luxury Editorial (Black, White, Gold Accents), Photography-Led Lifestyle Aesthetic, Product-Focused Clean Commercial Style, Flat Illustration with Friendly Characters, Isometric / Explainer Illustration Style, Playful & Youthful (Memphis / Stickers / Emojis), High-Impact Color-Blocking with Loud Type, Retro / Vintage Poster Style, Futuristic Tech / AI-Inspired Dark Mode, Glassmorphism / Neumorphism UI Style, Abstract Shapes & Fluid Gradient Art, Infographic / Data-Driven Educational Layout, Quote Card / Thought-Leadership Typography Post, Meme-Style / Social-Native Engagement Post, Festive / Campaign-Based Creative, Textured Design (Paper, Grain, Handmade Feel), Magazine / Editorial Layout with Strong Hierarchy, Experimental / Artistic Concept-Driven Design
- ONLY classify if the content_idea suggests a specific visual style
- If no clear visual style is implied, set to null

VALIDATION CHECKLIST:
□ Is every field either properly extracted or null?
□ Does content_idea exist and make sense?
□ Is platform an exact match from allowed values?
□ Is content_type based on explicit user wording?
□ Are classifications truly supported by the content_idea?

If ANY doubt exists, set the uncertain field(s) to null.

User conversation:
{conversation}

Return a JSON object with exactly this structure:
{{
    "channel": "Social Media" | "Blog" | null,
    "platform": "Instagram" | "Facebook" | "LinkedIn" | "YouTube" | null,
    "content_type": "static_post" | "carousel" | "short_video or reel" | "long_video" | "blog" | null,
    "media": "Generate" | "Upload" | "without media" | null,
    "content_idea": "string" | null,
    "Post_type": "one of the allowed post types" | null,
    "Image_type": "one of the allowed image types" | null
}}

IMPORTANT: Return ONLY the JSON object, no additional text or explanation.
{JSON_ONLY_INSTRUCTION}"""

    # Import _extract_payload from atsn
    from .atsn import _extract_payload
    return _extract_payload(state, prompt)


def complete_create_content_payload(state) -> Any:
    """Complete create_content payload"""


    # Import required functions
    from .atsn import (
        get_contextual_suggestion,
        generate_clarifying_question,
    )

    # Define the clarification flow order (media last)
    clarification_flow = ["channel", "platform", "content_type", "content_idea", "Post_type", "media"]

    # Build required fields list based on current state
    required_fields = []

    # Check if all fields before media are complete
    other_fields_complete = True
    for field in clarification_flow[:-1]:  # All fields except media
        if field == "Image_type":
            # Only require Image_type if media is "Generate"
            if state.payload.get("media") == "Generate":
                if field not in state.payload or state.payload.get(field) is None or not state.payload.get(field):
                    other_fields_complete = False
                    break
        elif field == "content_idea":
            # Check if content_idea exists
            content_idea = state.payload.get("content_idea", "")
            if not content_idea:
                other_fields_complete = False
                break
        else:
            # Check if field is missing or empty
            if field not in state.payload or state.payload.get(field) is None or not state.payload.get(field):
                other_fields_complete = False
                break

    for field in clarification_flow:
        if field == "Image_type":
            # Only require Image_type if media is "Generate"
            if state.payload.get("media") == "Generate":
                if field not in state.payload or state.payload.get(field) is None or not state.payload.get(field):
                    required_fields.append(field)
        elif field == "content_idea":
            # Check if content_idea exists
            content_idea = state.payload.get("content_idea", "")
            if not content_idea:
                required_fields.append(field)
        elif field == "media":
            # Only ask for media if all other fields are complete
            if other_fields_complete:
                if field not in state.payload or state.payload.get(field) is None or not state.payload.get(field):
                    required_fields.append(field)
        else:
            # Check if field is missing or empty
            if field not in state.payload or state.payload.get(field) is None or not state.payload.get(field):
                required_fields.append(field)

    clarifications = FIELD_CLARIFICATIONS.get("create_content", {})

    if not required_fields:
        state.payload_complete = True
        state.current_step = "action_execution"
        print("✅ Create content payload complete")
        return state

    # Use LLM to generate a natural conversational message for all missing fields
    try:
        # Create a mapping of field names to user-friendly labels
        field_labels = {
            "channel": "channel (Social Media or Blog)",
            "platform": "platform (like Instagram, Facebook, LinkedIn, YouTube)",
            "content_type": "content type (like static post, carousel, video)",
            "media": "whether to generate images or upload your own",
            "content_idea": "content description or topic",
            "Image_type": "image style preference"
        }

        missing_labels = [field_labels.get(field, field.replace('_', ' ')) for field in required_fields]

        # Create prompt for LLM to generate natural conversational message
        prompt = f"""Generate a single natural conversational message (under 50 words) asking a user for the following missing information to create content:

Missing information: {', '.join(missing_labels)}

CRITICAL RULES:
- DO NOT start with ANY greetings like "Hello", "Hi", "Hey there", "Good morning", etc.
- Start directly with the helpful content
- Be friendly and conversational
- Ask for ALL missing information in one message
- Be under 50 words
- Sound like a helpful assistant

Example: "I can help you create content! Just let me know what platform and the idea you want to convey with that content."

Return only the message, nothing else."""

        # Call LLM to generate the message
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful content creation assistant. Generate natural conversational messages. NEVER start with greetings like 'Hello', 'Hi', 'Hey there', etc."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.7
        )

        natural_message = response.choices[0].message.content.strip()

        # Ensure message is under 50 words
        word_count = len(natural_message.split())
        if word_count > 50:
            # Truncate if too long
            words = natural_message.split()[:45]
            natural_message = ' '.join(words) + '...'

        logger.info(f"🤖 LLM generated natural message: '{natural_message}' (asking for: {', '.join(missing_labels)})")

        state.clarification_question = natural_message
        state.clarification_options = []  # No structured options for natural conversation
        state.result = natural_message
        state.waiting_for_user = True
        state.current_step = "waiting_for_clarification"

        print(f"❓ Natural clarification: {natural_message}")
        return state

    except Exception as e:
        logger.error(f"Failed to generate natural message: {e}")
        # Fallback to basic question
        next_field = required_fields[0]
        missing_fields_text = ', '.join([field.replace('_', ' ') for field in required_fields])
        fallback_message = f"I need some more information to create your content. Please provide: {missing_fields_text}"
        state.clarification_question = fallback_message
        state.clarification_options = []
        state.result = fallback_message
        state.waiting_for_user = True
        state.current_step = "waiting_for_clarification"
        return state


async def handle_create_content(state) -> Any:
    """Generate and create content"""
    # Import required functions
    from .atsn import (
        get_business_context_from_profile,
        generate_image_enhancer_prompt,
        build_brand_color_instructions,
        build_location_context,
        generate_carousel_image_prompts,
        generate_carousel_images,
        get_trends_from_grok,
        generate_content_with_rl_agent,
        extract_hashtags_from_caption,
        generate_personalized_message,
    )

    payload = state.payload
    
    # Set agent name for content creation
    payload['agent_name'] = 'chase'

    if not state.payload_complete:
        state.error = "Payload is not complete"
        return state

    try:
        generated_content = ""
        generated_image_url = None
        content_data = {}  # Store data to save to database
        title = payload.get('title') or payload.get('content_idea', '')

        # Initialize parsed_trends as empty dict (will be populated if trends are fetched)
        parsed_trends = {}

        # Load business context and profile assets from profiles table
        business_context = {}
        profile_assets = {}
        if state.user_id:
            logger.info(f"🔍 Loading profile data for user_id: {state.user_id}")
            try:
                # Fetch comprehensive profile data including all context fields
                profile_fields = [
                    "business_name", "business_description", "brand_tone", "industry", "target_audience",
                    "brand_voice", "unique_value_proposition", "primary_color", "secondary_color",
                    "brand_colors", "logo_url", "timezone", "location_city", "location_state", "location_country"
                ]
                logger.info(f"🔍 Fetching profile fields: {', '.join(profile_fields)}")
                profile_response = supabase.table("profiles").select(", ".join(profile_fields)).eq("id", state.user_id).execute()

                logger.info(f"🔍 Profile query response: {len(profile_response.data) if profile_response.data else 0} records found")

                if profile_response.data and len(profile_response.data) > 0:
                    profile_data = profile_response.data[0]
                    logger.info(f"🔍 Raw profile data: {profile_data}")

                    business_context = get_business_context_from_profile(profile_data)

                    # Extract brand assets for content and image generation
                    profile_assets = {
                        'primary_color': profile_data.get('primary_color'),
                        'secondary_color': profile_data.get('secondary_color'),
                        'brand_colors': profile_data.get('brand_colors') or [],  # Ensure it's always a list
                        'logo': profile_data.get('logo_url'),  # Use correct column name
                        'primary_typography': profile_data.get('primary_typography'),
                        'secondary_typography': profile_data.get('secondary_typography')
                    }

                    logger.info(f"✅ Loaded structured business context for: {business_context.get('business_name', 'Business')}")
                    logger.info(f"   Brand colors: {bool(profile_assets['primary_color'])}/{bool(profile_assets['secondary_color'])}")
                    brand_colors_len = len(profile_assets.get('brand_colors') or [])
                    logger.info(f"   Brand colors array: {brand_colors_len} colors")
                    logger.info(f"   Logo: {bool(profile_assets.get('logo'))}")
                    logger.info(f"   Typography: {bool(profile_assets.get('primary_typography'))}/{bool(profile_assets.get('secondary_typography'))}")
                    logger.info(f"   Industry: {business_context.get('industry', 'N/A')}")
                    logger.info(f"   Target audience: {business_context.get('target_audience', 'N/A')}")
                else:
                    logger.warning(f"❌ No profile data found for user_id: {state.user_id}, using defaults")
                    logger.warning("   This usually means the user hasn't completed their profile onboarding")
                    business_context = get_business_context_from_profile({})
                    profile_assets = {'primary_color': None, 'secondary_color': None, 'brand_colors': [], 'logo': None}
            except Exception as e:
                logger.error(f"❌ Failed to load business context for user_id {state.user_id}: {e}")
                logger.error(f"   Exception type: {type(e).__name__}")
                import traceback
                logger.error(f"   Traceback: {traceback.format_exc()}")
                business_context = get_business_context_from_profile({})
                profile_assets = {'primary_color': None, 'secondary_color': None, 'brand_colors': [], 'logo': None}
        else:
            logger.warning("❌ No user_id provided in state, using defaults")
            business_context = get_business_context_from_profile({})
            profile_assets = {'primary_color': None, 'secondary_color': None, 'brand_colors': [], 'logo': None}

        # Handle different content types
        content_type = payload.get('content_type', '')

        if content_type == 'static_post':
            # Get the content topic/idea
            topic = payload.get('content_idea', '')
            platform = payload.get('platform', 'Instagram').lower()

            # Check if user wants to upload their own image
            if payload.get('media') == 'Upload':
                logger.info("📤 Handling image upload for static post")

                # Check if image file is uploaded
                if not payload.get('media_file'):
                    # No file uploaded yet, set upload flag
                    state.waiting_for_upload = True
                    state.upload_type = 'image'
                    state.result = "Ready to upload your image for the static post. Please select and upload an image file."
                    return state

                # Image is uploaded, process it
                uploaded_image_url = payload.get('media_file')
                if uploaded_image_url:
                    logger.info(f"📤 Processing uploaded image: {uploaded_image_url}")

                    # Step 1: Analyze image with LLM to generate title, caption, and hashtags
                    logger.info("🔍 Analyzing image with LLM for content generation")

                    content_description = topic
                    image_analysis_prompt = f"""
                    Analyze this image and create engaging social media content for {platform}.

                    Content Description: {content_description}
                    Business Context: {business_context.get('business_name', 'Business')} - {business_context.get('industry', 'Industry')}

                    Please provide:
                    1. A compelling title (max 60 characters)
                    2. An engaging caption that incorporates the content description
                    3. Relevant hashtags (5-10 hashtags)

                    Make the content optimized for {platform} and aligned with the business context.
                    """

                    try:
                        # Use OpenAI GPT-4o-mini with vision for image analysis
                        analysis_response = openai_client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": image_analysis_prompt},
                                        {"type": "image_url", "image_url": {"url": uploaded_image_url}}
                                    ]
                                }
                            ],
                            max_tokens=1000,
                            temperature=0.7
                        )

                        analysis_result = analysis_response.choices[0].message.content.strip()
                        logger.info(f"✅ Image analysis completed: {len(analysis_result)} characters")

                        # Parse the analysis result to extract title, caption, and hashtags
                        # Simple parsing - assuming the LLM returns structured text
                        lines = analysis_result.split('\n')
                        title = ""
                        caption = ""
                        hashtags = []

                        for line in lines:
                            line = line.strip()
                            if line.startswith('1.') or 'title' in line.lower():
                                title = line.split(':', 1)[-1].strip().strip('"').strip("'")
                            elif line.startswith('2.') or 'caption' in line.lower():
                                caption = line.split(':', 1)[-1].strip()
                            elif line.startswith('3.') or 'hashtag' in line.lower():
                                hashtags_text = line.split(':', 1)[-1].strip()
                                # Extract hashtags from text
                                import re
                                hashtags = re.findall(r'#\w+', hashtags_text)

                        content_desc = topic
                        if not title:
                            title = f"Post about {content_desc[:50]}"
                        if not caption:
                            caption = f"Check out this amazing content about {content_desc}!"
                        if not hashtags:
                            hashtags = ['#content', '#socialmedia']

                        logger.info(f"📝 Generated title: {title}")
                        logger.info(f"📝 Generated caption: {caption[:100]}...")
                        logger.info(f"🏷️ Generated hashtags: {hashtags}")

                    except Exception as e:
                        logger.error(f"❌ Failed to analyze image: {e}")
                        # Fallback content
                        content_desc = topic
                        title = f"Post about {content_desc[:50]}"
                        caption = f"Great content about {content_desc}!"
                        hashtags = ['#content']

                    # Step 2: Enhance image with Gemini for social media optimization
                    logger.info("🎨 Enhancing image with Gemini for social media optimization")

                    try:
                        # Note: For proper image enhancement, we would need to:
                        # 1. Download the image from uploaded_image_url
                        # 2. Process it with Gemini Vision API
                        # 3. Upload the enhanced version back to Supabase
                        # 4. Use the new enhanced image URL

                        # For now, we'll use the uploaded image directly
                        # TODO: Implement actual image enhancement with Gemini
                        enhanced_image_url = uploaded_image_url
                        logger.info("✅ Image enhancement skipped (using original image)")

                    except Exception as e:
                        logger.error(f"❌ Failed to enhance image: {e}")
                        enhanced_image_url = uploaded_image_url  # Fallback to original

                    # Step 3: Save to database
                    content_data['title'] = title
                    content_data['content'] = caption
                    content_data['hashtags'] = hashtags
                    content_data['images'] = [enhanced_image_url]  # Store as list with single image URL

                    generated_content = f"{title}\n\n{caption}\n\n{' '.join(hashtags)}"

                    logger.info("✅ Uploaded image content created successfully")

            else:
                # Use RL Agent for content generation (existing logic)
                logger.info(f"🤖 Using RL Agent to generate content for topic: '{topic}' on {platform}")

                # Call RL Agent API
                rl_result = await generate_content_with_rl_agent(
                    profile_id=state.user_id,  # Use the business profile ID
                    topic=topic,
                    platform=platform
                )

                if rl_result["success"]:
                    # Use RL-generated content
                    content_data['title'] = f"Post about {topic[:50]}"
                    content_data['content'] = rl_result["caption"]
                    content_data['hashtags'] = extract_hashtags_from_caption(rl_result["caption"])
                    content_data['images'] = [rl_result["image_url"]] if rl_result.get("image_url") else []  # Store the RL-generated image as a list

                    # Store RL metadata for learning
                    content_data['rl_post_id'] = rl_result["post_id"]
                    content_data['rl_action_id'] = rl_result["action_id"]

                    generated_content = f"{content_data['title']}\n\n{content_data['content']}\n\n{' '.join(content_data['hashtags'])}"

                    logger.info("✅ RL Agent generated content successfully")

                else:
                    # RL Agent failed - do not fallback, raise error
                    error_msg = f"RL Agent failed to generate content: {rl_result['error']}"
                    logger.error(f"❌ {error_msg}")
                    raise Exception(error_msg)

        elif content_type == 'carousel':
            # CAROUSEL POST GENERATION
            logger.info("🎠 Starting carousel post generation")

            # Step 1: Determine number of images (default to 4, can be customized)
            num_images = 4  # Default carousel length
            if payload.get('content_idea'):
                # Try to extract number from content idea (e.g., "5 slide carousel")
                import re
                number_match = re.search(r'(\d+)\s*(?:slide|image|photo|card)', payload['content_idea'], re.IGNORECASE)
                if number_match:
                    requested_num = int(number_match.group(1))
                    num_images = max(3, min(6, requested_num))  # Keep between 3-6
                    logger.info(f"📏 User requested {requested_num} images, adjusted to {num_images}")

            # Step 2: Generate complete carousel plan (title, caption, and all image prompts)
            carousel_plan = generate_carousel_image_prompts(
                payload.get('content_idea', ''),
                num_images,
                business_context,
                profile_assets
            )

            # Step 3: Generate all carousel images iteratively
            carousel_image_urls = await generate_carousel_images(
                carousel_plan,
                business_context,
                profile_assets
            )

            if not carousel_image_urls:
                raise Exception("Failed to generate carousel images")

            # Step 4: Extract data from carousel plan and save
            title = carousel_plan["title"]
            content = carousel_plan["caption"]
            hashtags = []  # Extract hashtags from caption if needed

            # Extract hashtags from caption (simple extraction)
            import re
            hashtag_matches = re.findall(r'#\w+', content)
            hashtags = hashtag_matches

            # Save carousel data
            content_data['title'] = title
            content_data['content'] = content
            content_data['hashtags'] = hashtags
            content_data['carousel_images'] = carousel_image_urls  # Save to carousel_images column

            generated_content = f"{title}\n\n{content}\n\n{' '.join(hashtags)}\n\n🎠 Carousel with {len(carousel_image_urls)} images"
            logger.info(f"✅ Generated carousel post with {len(carousel_image_urls)} images from complete plan")

        elif content_type == 'short_video or reel':
            # Check if user wants to upload their own video
            if payload.get('media') == 'Upload':
                # Set flag for upload requirement - user will upload both video and cover
                if not payload.get('media_file'):
                    state.waiting_for_upload = True
                    state.upload_type = 'video'  # They need to upload video file
                    state.result = "Ready to upload your short video/reel. Please select and upload a video file."
                    return state
                else:
                    # File already uploaded, use it
                    generated_image_url = payload.get('media_file')
                    if generated_image_url:
                        content_data['images'] = [generated_image_url]

            # Step 1: Get viral content trends from Grok
            topic = payload.get('content_idea', 'viral content trends')
            trends_data = await get_trends_from_grok(topic, business_context)

            # Step 2: Generate short video script using GPT-4o-mini with trend insights
            viral_content = ""
            if trends_data and 'trends' in trends_data:
                viral_content = "\n\nVIRAL CONTENT INSIGHTS:\n" + "\n".join([
                    f"- {trend.get('trend_name', '')}: {trend.get('description', '')[:100]}..."
                    for trend in trends_data['trends'][:3]  # Top 3 trends
                ])

            prompt = f"""You are a professional short-form video script writer creating viral content for {payload.get('platform', 'social media')} Reels.

BUSINESS CONTEXT:
{business_context.get('business_name', 'Business')}
Industry: {business_context.get('industry', 'General')}
Target Audience: {business_context.get('target_audience', 'General audience')}
Brand Voice: {business_context.get('brand_voice', 'Professional and friendly')}
Business Description: {business_context.get('business_description', 'N/A')}

CONTENT REQUIREMENTS:
- Platform: {payload.get('platform', 'Instagram Reels/TikTok/YouTube Shorts')}
- Content Idea: {payload.get('content_idea', '')}
- Duration: 15-30 seconds (keep script concise and punchy)
- Goal: Create engaging, scroll-stopping content{viral_content}

TASK:
Create a complete 15-30 second video script optimized for virality that includes:
1. STRONG HOOK (0-3 seconds - shock, question, or surprising fact)
2. VALUE DELIVERY (3-20 seconds - solve problem or provide insight)
3. EMOTIONAL CLOSE (20-25 seconds - build connection)
4. CLEAR CTA (25-30 seconds - what to do next)

SCRIPT FORMAT:
🎬 SCENE BREAKDOWN:
[0-3s] HOOK: [One powerful sentence that stops the scroll]
[3-20s] VALUE: [2-3 key points that deliver real value]
[20-25s] STORY/CONNECTION: [Make it relatable, add emotion]
[25-30s] CTA: [Specific action + urgency]

VISUAL CUES:
- Background music suggestions
- Text overlays for key points
- Transitions between sections
- Thumbnail-worthy moments

Make it conversational, authentic, and optimized for the algorithm."""

            if openai_client:
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1000,
                    temperature=0.8
                )
                generated_script = response.choices[0].message.content.strip()
                content_data['short_video_script'] = generated_script  # Save to short_video_script column
                content_data['content'] = generated_script  # Required field for database

                # Step 3: Generate video cover image using Gemini (only if not uploading)
                if payload.get('media') != 'Upload' and not payload.get('media_url'):
                    cover_prompt = f"""Create a professional, eye-catching thumbnail image for a {payload.get('platform', 'social media')} short video about: {payload.get('content_idea', 'viral content')}

Business: {business_context.get('business_name', 'Business')}
Style: Scroll-stopping, viral-worthy, modern and engaging
Visual elements: Bold text overlays, vibrant gradients, clean mobile-first design
Composition: High contrast, clear focal point, optimized for 9:16 aspect ratio
Make it irresistible to click and watch!"""

                logger.info(f"🎨 Complete video cover generation prompt:")
                logger.info("=" * 80)
                logger.info(cover_prompt)
                logger.info("=" * 80)

                # Check if logo is available and prepare to send it to Gemini
                logo_data = None
                if profile_assets and profile_assets.get('logo'):
                    logo_url = profile_assets.get('logo')
                    logger.info(f"📎 Including logo in video cover generation: {logo_url}")
                    try:
                        import httpx
                        async with httpx.AsyncClient(follow_redirects=True) as client:
                            logo_response = await client.get(logo_url)
                            logo_response.raise_for_status()
                            logo_data = logo_response.content
                        logger.info(f"✅ Logo downloaded successfully: {len(logo_data)} bytes")
                    except Exception as e:
                        logger.warning(f"Failed to download logo: {e}")
                        logo_data = None

                # Generate image with Gemini
                logger.info(f"🎨 Generating video cover with Gemini for platform: {payload.get('platform')} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
                logger.info(f"   Logo included: {logo_data is not None}")

                gemini_image_model = 'gemini-2.5-flash-image'

                # Prepare contents for Gemini API
                contents = [cover_prompt]  # Text prompt is always first

                # Add logo as reference image if available
                if logo_data:
                    import base64
                    contents.append({
                        "inline_data": {
                            "mime_type": "image/png",  # Assume PNG for transparency
                            "data": base64.b64encode(logo_data).decode('utf-8')
                        }
                    })

                # Use new client-based API
                if gemini_client:
                    image_response = gemini_client.models.generate_content(
                        model=gemini_image_model,
                        contents=contents
                    )
                else:
                    logger.error("Gemini client not initialized")
                    return state
                logger.info(f"Gemini response received, has candidates: {bool(image_response.candidates)}")

                # Extract image data
                if image_response.candidates and len(image_response.candidates) > 0:
                    candidate = image_response.candidates[0]
                    if candidate.content.parts:
                        for part in candidate.content.parts:
                            if part.inline_data is not None and part.inline_data.data:
                                try:
                                    # Get image data as bytes
                                    image_data = part.inline_data.data
                                    if not isinstance(image_data, bytes):
                                        import base64
                                        image_data = base64.b64decode(image_data)

                                    # Generate unique filename
                                    import uuid
                                    filename = f"video_covers/{uuid.uuid4()}.png"
                                    file_path = filename

                                    logger.info(f"📤 Uploading generated video cover to ai-generated-images bucket: {file_path}")

                                    # Upload to ai-generated-images bucket in generated folder
                                    storage_response = supabase.storage.from_("ai-generated-images").upload(
                                        file_path,
                                        image_data,
                                        file_options={"content-type": "image/png", "upsert": "false"}
                                    )

                                    if hasattr(storage_response, 'error') and storage_response.error:
                                        logger.error(f"Storage upload error: {storage_response.error}")
                                        generated_image_url = None
                                    else:
                                        # Get public URL
                                        generated_image_url = supabase.storage.from_("ai-generated-images").get_public_url(file_path)
                                        logger.info(f"✅ Video cover uploaded successfully: {generated_image_url}")

                                        if generated_image_url and isinstance(generated_image_url, str):
                                            content_data['images'] = [generated_image_url]

                                            # Update metadata for video cover
                                            content_data['metadata'] = {
                                                'video_cover_generated': True,
                                                'cover_prompt': cover_prompt,
                                                'trends_used': trends_data.get('trends', [])[:3] if trends_data else [],
                                                'generated_with': 'gemini'
                                            }
                                        else:
                                            logger.error(f"Invalid public URL returned: {generated_image_url}")

                                except Exception as upload_error:
                                    logger.error(f"Error uploading video cover to storage: {upload_error}")

                                break
                    else:
                        # When uploading, don't generate cover - user will upload their own
                        content_data['metadata'] = {
                            'video_cover_uploaded': True,
                            'trends_used': trends_data.get('trends', [])[:3] if trends_data else [],
                            'generated_with': 'user_upload'
                        }

                # Step 4: Generate compelling title and caption for the reel
                caption_prompt = f"""Based on this short video script, create a compelling title and Instagram caption for the reel.

VIDEO SCRIPT:
{generated_script}

BUSINESS CONTEXT:
{business_context.get('business_name', 'Business')}
Industry: {business_context.get('industry', 'General')}
Target Audience: {business_context.get('target_audience', 'General audience')}

TASK:
Create a viral-worthy Instagram Reel title and caption that will:
1. Hook viewers in the first 3 words
2. Use trending hashtags and emojis naturally
3. Include a strong call-to-action
4. Be optimized for Instagram's algorithm

FORMAT (Return ONLY this format):
TITLE: [Compelling 1-5 word title]
CAPTION: [Scroll-stopping caption with emojis, 100-150 characters]

Make it authentic, engaging, and optimized for maximum engagement!"""

                try:
                    caption_response = openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": caption_prompt}],
                        max_tokens=300,
                        temperature=0.9
                    )
                    caption_result = caption_response.choices[0].message.content.strip()

                    # Parse title and caption
                    title = ""
                    caption = ""
                    for line in caption_result.split('\n'):
                        line = line.strip()
                        if line.startswith('TITLE:'):
                            title = line.replace('TITLE:', '').strip()
                        elif line.startswith('CAPTION:'):
                            caption = line.replace('CAPTION:', '').strip()

                    # Save title and caption
                    content_data['title'] = title if title else f"Reel: {payload.get('content_idea', 'Viral Content')[:30]}"
                    content_data['content'] = caption if caption else generated_script[:200] + "..."

                    logger.info(f"✅ Generated reel title: '{title}' and caption: '{caption[:50]}...'")

                except Exception as caption_error:
                    logger.warning(f"Failed to generate reel caption: {caption_error}")
                    # Fallback: use script as content
                    content_data['title'] = f"Reel: {payload.get('content_idea', 'Viral Content')[:30]}"
                    content_data['content'] = generated_script[:200] + "..."

                generated_content = f"🎬 Short Video Script Generated:\n\n{generated_script}"
            else:
                generated_content = "OpenAI client not configured"
                content_data['short_video_script'] = "Script generation failed - OpenAI client not configured"
                content_data['title'] = "Reel Generation Failed"
                content_data['content'] = generated_content

        elif content_type == 'long_video':
            # Generate long video script using GPT-4o-mini
            prompt = f"""You are a professional video script writer specializing in long-form video content.

BUSINESS CONTEXT:
{business_context.get('business_name', 'Business')}
Industry: {business_context.get('industry', 'General')}
Target Audience: {business_context.get('target_audience', 'General audience')}
Brand Voice: {business_context.get('brand_voice', 'Professional and friendly')}

CONTENT REQUIREMENTS:
- Platform: {payload.get('platform', 'YouTube/Vimeo')}
- Content Idea: {payload.get('content_idea', '')}
- Duration: 5-15 minutes

TASK:
Create a complete long-form video script that includes:
1. Introduction/Hook (30-60 seconds)
2. Main content sections with clear structure
3. Key points and value delivery
4. Conclusion with call-to-action
5. Visual and editing cues

SCRIPT FORMAT:
[0:00-0:30] INTRODUCTION: [Hook and overview]
[0:30-8:00] MAIN CONTENT: [Detailed explanation with sections]
[8:00-10:00] CONCLUSION: [Summary and CTA]

Use professional, engaging language.
Include timing estimates for each section."""

            if openai_client:
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=2000,
                    temperature=0.7
                )
                generated_script = response.choices[0].message.content.strip()
                content_data['long_video_script'] = generated_script  # Save to long_video_script column
                generated_content = f"Long Video Script Generated:\n\n{generated_script}"
            else:
                generated_content = "OpenAI client not configured"
                content_data['long_video_script'] = "Script generation failed - OpenAI client not configured"


        else:
            # For other content types, use original logic
            generated_content = f"Generated {content_type} for {payload.get('platform', 'platform')}"
            content_data['content'] = generated_content

        # RL Agent handles all media generation - no additional generation needed
        logger.info(f"Media handled by RL Agent: {payload.get('media')}")
        # Remove duplicate image generation - RL Agent already generates images

        if payload.get('media') == 'Upload':
            # Set flag for upload requirement
            if not payload.get('media_file'):
                # No file uploaded yet, set upload flag
                state.waiting_for_upload = True
                state.upload_type = 'image'
                state.result = "Ready to upload an image for your content. Please select and upload an image file."
                return state
            else:
                # File already uploaded, use it
                generated_image_url = payload.get('media_file')
                if generated_image_url:
                    content_data['images'] = [generated_image_url]
        # For "without media", no images added

        # Save to Supabase created_content table
        logger.info(f"💾 Preparing to save content_data keys: {list(content_data.keys())}")
        if state.user_id and content_data:
            try:
                # Prepare data for created_content table
                db_data = {
                    'user_id': state.user_id,
                    'platform': payload.get('platform', '').lower(),
                    'content_type': content_type.lower(),
                    'title': content_data.get('title', f"{content_type} for {payload.get('platform', 'Platform').lower()}"),
                    'status': 'generated',
                    'metadata': {
                        'channel': payload.get('channel'),
                        'content_idea': payload.get('content_idea'),
                        'generated_at': datetime.now().isoformat()
                    },
                    **content_data  # This spreads the content-specific data into the correct columns
                }

                # Insert into created_content table
                result = supabase.table('created_content').insert(db_data).execute()
                if result.data and len(result.data) > 0:
                    content_id = result.data[0]['id']
                    state.content_id = str(content_id)
                    logger.info(f"✅ Successfully saved {content_type} content to created_content table with ID: {content_id}")

                    # Log which columns were saved
                    saved_columns = list(content_data.keys())
                    logger.info(f"📝 Saved content to columns: {', '.join(saved_columns)}")
                    logger.info(f"📸 Images in content_data: {'images' in content_data and len(content_data.get('images', []))} image(s)")
                    logger.info(f"🎠 Carousel images in content_data: {'carousel_images' in content_data and len(content_data.get('carousel_images', []))} image(s)")
                    if 'images' in content_data:
                        logger.info(f"📸 Image URLs saved: {len(content_data['images'])} URL(s) in database")
                    if 'carousel_images' in content_data:
                        logger.info(f"🎠 Carousel image URLs saved: {len(content_data['carousel_images'])} URL(s) in database")
                else:
                    logger.warning("Failed to save content to created_content table - no data returned")

            except Exception as e:
                logger.error(f"Error saving content to created_content table: {e}")
                state.error = f"Failed to save content to database: {str(e)}"

        # Generate display content ID
        display_content_id = f"CONTENT_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Create content item for frontend display
        if state.user_id and state.content_id:
            try:
                # Fetch the newly created content from database to get complete data
                content_response = supabase.table('created_content').select('*').eq('id', state.content_id).execute()
                if content_response.data and len(content_response.data) > 0:
                    item = content_response.data[0]

                    # Extract image URL from images array or carousel_images array
                    images = item.get('images', [])
                    carousel_images = item.get('carousel_images', [])
                    media_url = None

                    if carousel_images and len(carousel_images) > 0:
                        # For carousel posts, use first carousel image
                        first_image = carousel_images[0]
                        if isinstance(first_image, str):
                            media_url = first_image
                    elif images and len(images) > 0:
                        # For regular posts, use first image
                        first_image = images[0]
                        if isinstance(first_image, str):
                            media_url = first_image

                    # Format hashtags
                    hashtags = item.get('hashtags', [])
                    hashtag_text = ''
                    if hashtags:
                        if isinstance(hashtags, list):
                            hashtag_text = ' '.join([f"#{tag}" if not tag.startswith('#') else tag for tag in hashtags[:10]])

                    # Format date
                    created_at = item.get('created_at', '')
                    date_display = ''
                    if created_at:
                        try:
                            dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            date_display = dt.strftime('%B %d, %Y at %I:%M %p')
                        except:
                            date_display = created_at[:10] if len(created_at) >= 10 else created_at

                    # Get content text based on content type
                    content_type = item.get('content_type', 'post')
                    content_text = ''
                    if content_type == 'email':
                        if item.get('email_subject') and item.get('email_body'):
                            content_text = f"Subject: {item['email_subject']}\n\n{item['email_body']}"
                        else:
                            content_text = item.get('content', '')
                    elif content_type == 'short_video or reel':
                        content_text = item.get('short_video_script', '')
                    elif content_type == 'long_video':
                        content_text = item.get('long_video_script', '')
                    elif content_type == 'carousel':
                        carousel_images = item.get('carousel_images', [])
                        content_text = f"{item.get('content', '')}\n\n🎠 Carousel Post with {len(carousel_images)} images"
                    elif content_type == 'message':
                        content_text = item.get('message', '')
                    else:
                        content_text = item.get('content', '')

                    # Get title
                    title = item.get('title', f"{content_type.title()} for {item.get('platform', 'Platform')}")

                    # Create structured content item for frontend
                    content_item = {
                        'id': 1,  # Single item
                        'content_id': state.content_id,
                        'platform': item.get('platform', 'Unknown').title(),
                        'content_type': content_type.replace('_', ' ').title(),
                        'status': item.get('status', 'generated').title(),
                        'created_at': date_display,
                        'created_at_raw': created_at,
                        'title': title,
                        'title_display': title,
                        'content_text': content_text,
                        'content_preview': content_text[:150] + '...' if len(content_text) > 150 else content_text,
                        'hashtags': hashtag_text,
                        'hashtags_display': hashtag_text,
                        'media_url': media_url,
                        'has_media': bool(media_url),
                        'images': item.get('images', []),
                        # Additional fields for different content types
                        'email_subject': item.get('email_subject'),
                        'email_body': item.get('email_body'),
                        'short_video_script': item.get('short_video_script'),
                        'long_video_script': item.get('long_video_script'),
                        'message': item.get('message'),
                        # Platform emoji
                        'platform_emoji': {
                            'Instagram': '📸',
                            'Facebook': '👥',
                            'Linkedin': '💼',
                            'Youtube': '🎥',
                            'Gmail': '✉️',
                            'Whatsapp': '💬'
                        }.get(item.get('platform', 'Unknown').title(), '🌐'),
                        # Status emoji and color
                        'status_emoji': {
                            'Generated': '📝',
                            'Scheduled': '⏰',
                            'Published': '✅'
                        }.get(item.get('status', 'generated').title(), '📄'),
                        'status_color': {
                            'Generated': 'blue',
                            'Scheduled': 'orange',
                            'Published': 'green'
                        }.get(item.get('status', 'generated').title(), 'gray'),
                        'metadata': item.get('metadata', {}),
                        'raw_data': item
                    }

                    # Set content_items for frontend display
                    state.content_items = [content_item]

            except Exception as e:
                logger.error(f"Error creating content item for display: {e}")

        # Set intent for frontend to enable action buttons
        state.intent = "created_content"

        # Minimal success response - cards will be displayed by frontend
        base_message = "Content created successfully! Use the action buttons below to manage your content."
        state.result = generate_personalized_message(
            base_message=base_message,
            user_context=state.user_query,
            message_type="success"
        )
        
    except Exception as e:
        state.error = f"Content generation failed: {str(e)}"
        logger.error(f"Content creation error: {e}")
    
    return state
