#!/usr/bin/env python3
"""
Content Generation Cron Job
Processes calendar_entries where content = false and generates content using Gemini Nano for images
"""

import os
import logging
import asyncio
import base64
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv
import openai
import google.generativeai as genai
from content_creation_agent import ContentCreationAgent

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ContentGenerationCron:
    """Cron job for processing calendar entries and generating content"""

    def __init__(self):
        # Initialize Supabase
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        self.supabase = create_client(self.supabase_url, self.supabase_key)

        # Initialize OpenAI (for content generation)
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.openai_client = openai.OpenAI(api_key=self.openai_api_key) if self.openai_api_key else None

        # Initialize Gemini client for image generation
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.gemini_client = None
        if gemini_api_key:
            try:
                genai.configure(api_key=gemini_api_key)
                self.gemini_client = genai.GenerativeModel('gemini-1.5-flash')
                logger.info("Gemini client initialized successfully for image generation")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini client: {e}")
                self.gemini_client = None

        # Load image enhancer prompts
        self.image_enhancer_prompts = {}
        try:
            with open('image_enhancer_prompts.json', 'r') as f:
                data = json.load(f)
                self.image_enhancer_prompts = data.get('image_enhancer_prompts', {})
            logger.info(f"Loaded {len(self.image_enhancer_prompts)} image enhancer prompts")
        except Exception as e:
            logger.warning(f"Failed to load image enhancer prompts: {e}")

        # Initialize ContentCreationAgent (commented out due to missing dependencies)
        # self.content_agent = ContentCreationAgent(
        #     supabase_url=self.supabase_url,
        #     supabase_key=self.supabase_key,
        #     openai_api_key=self.openai_api_key
        # )
        self.content_agent = None  # Will use mock functionality

        # Removed local directory creation - everything is now saved directly to Supabase

    async def _load_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Load business context from user profile with fallback"""
        try:
            # Start with basic fields that are most likely to exist
            basic_fields = [
                "business_name", "business_description", "brand_tone", "brand_voice",
                "industry", "target_audience", "unique_value_proposition",
                "social_media_platforms", "primary_goals", "content_themes",
                "name", "avatar_url", "onboarding_completed",
                "primary_color", "secondary_color", "brand_colors"
            ]

            # Try to load basic profile first
            response = self.supabase.table("profiles").select(
                ", ".join(basic_fields)
            ).eq("id", user_id).execute()

            if response.data and len(response.data) > 0:
                profile_data = response.data[0]
                logger.info(f"Loaded business context for user {user_id}: {profile_data.get('business_name', 'Unknown')}")
                logger.info(f"User brand colors - Primary: {profile_data.get('primary_color', 'NOT SET')}, Secondary: {profile_data.get('secondary_color', 'NOT SET')}")

                # Provide default values for missing fields
                defaults = {
                    'brand_tone': profile_data.get('brand_tone', 'professional'),
                    'business_name': profile_data.get('business_name', 'Our Business'),
                    'industry': profile_data.get('industry', ['general']),
                    'target_audience': profile_data.get('target_audience', ['our audience']),
                    'unique_value': profile_data.get('unique_value_proposition', 'providing value'),
                    'brand_voice': profile_data.get('brand_voice', 'professional and helpful'),
                    'content_themes': profile_data.get('content_themes', ['business', 'growth']),
                    'primary_color': profile_data.get('primary_color', '#007bff'),
                    'secondary_color': profile_data.get('secondary_color', '#6c757d'),
                    'brand_colors': profile_data.get('brand_colors', ['#007bff', '#6c757d'])
                }

                # Merge defaults with actual data
                profile_data.update({k: v for k, v in defaults.items() if k not in profile_data or profile_data[k] is None})

                return profile_data
            else:
                logger.warning(f"No profile found for user {user_id}")
                return {}
        except Exception as e:
            logger.error(f"Error loading business context from profiles table: {e}")
            # Return minimal defaults so content generation can still work
            return {
                'business_name': 'Our Business',
                'brand_tone': 'professional',
                'brand_voice': 'helpful and engaging',
                'industry': ['general'],
                'target_audience': ['our audience'],
                'unique_value_proposition': 'providing value',
                'content_themes': ['business'],
                'primary_color': '#007bff',
                'secondary_color': '#6c757d',
                'brand_colors': ['#007bff', '#6c757d']
            }

    async def process_calendar_entries(self):
        """Main function to process calendar entries that need content generation"""
        try:
            logger.info("Starting content generation cron job...")

            # Query calendar_entries where content = false
            response = self.supabase.table('calendar_entries').select(
                'id, calendar_id, entry_date, content_type, content_theme, topic, platform, '
                'hook_type, hook_length, tone, creativity, text_in_image, visual_style, status'
            ).eq('content', False).execute()

            if not response.data:
                logger.info("No calendar entries found that need content generation")
                return

            logger.info(f"Found {len(response.data)} calendar entries to process")

            for entry in response.data:
                try:
                    await self.process_single_entry(entry)
                except Exception as e:
                    logger.error(f"Error processing entry {entry['id']}: {e}")
                    continue

            logger.info("Content generation cron job completed")

        except Exception as e:
            logger.error(f"Error in content generation cron: {e}")

    async def process_single_entry(self, entry: Dict[str, Any]):
        """Process a single calendar entry"""
        entry_id = entry['id']
        calendar_id = entry['calendar_id']

        logger.info(f"Processing calendar entry {entry_id} for calendar {calendar_id}")

        # Get user_id from calendar
        calendar_response = self.supabase.table('social_media_calendars').select('user_id').eq('id', calendar_id).execute()

        if not calendar_response.data:
            logger.error(f"No calendar found for calendar_id {calendar_id}")
            return

        user_id = calendar_response.data[0]['user_id']
        logger.info(f"Processing for user {user_id}")

        # Load user profile/business context
        business_context = await self._load_user_profile(user_id)

        if not business_context:
            logger.warning(f"No business context found for user {user_id}")
            return

        # Generate content
        content_data = await self.generate_content(entry, business_context, user_id)

        if content_data:
            generated_image_url = None
            generated_caption = None
            
            # Generate images only for specific content types
            if content_data.get('generate_image', True):
                logger.info(f"Starting image generation for {content_data.get('content_type')} content type")
                result = await self.generate_and_save_images(entry, content_data, user_id)
                if result:
                    generated_image_url = result.get('image_url')
                    generated_caption = result.get('caption')
                    logger.info(f"Completed image generation for {content_data.get('content_type')} content type")
                    logger.info(f"Generated image URL: {generated_image_url}")
                    logger.info(f"Generated caption: {generated_caption[:100] if generated_caption else 'None'}...")

            # Scripts are now saved directly to database in save_to_created_content method
            # No need to save scripts to local files anymore

            # Save to created_content table
            await self.save_to_created_content(
                entry=entry,
                content_data=content_data,
                user_id=user_id,
                image_url=generated_image_url,
                caption=generated_caption
            )

            # Update calendar entry to mark content as generated
            self.supabase.table('calendar_entries').update({
                'content': True,
                'status': 'content_generated',
                'updated_at': datetime.now().isoformat()
            }).eq('id', entry_id).execute()

            logger.info(f"Successfully processed entry {entry_id} with content type: {content_data.get('content_type')}")

    def _identify_content_theme_and_select_prompt(self, content_theme: str, topic: str, business_context: Dict[str, Any], visual_style: str) -> str:
        """Identify content theme and select the best image enhancer prompt from image_enhancer_prompts.json"""
        try:
            # Analyze content theme and business context to select optimal visual style
            selected_visual_style = self._analyze_content_for_visual_style(content_theme, topic, business_context, visual_style)

            logger.info(f"Selected visual style '{selected_visual_style}' for content theme '{content_theme}' and topic '{topic}'")

            # Get the prompt template for the selected visual style
            prompt_data = self.image_enhancer_prompts.get(selected_visual_style, {})
            if not prompt_data or 'prompts' not in prompt_data:
                logger.warning(f"No prompt found for visual style: {selected_visual_style}, falling back to minimal_clean_bold_typography")
                prompt_data = self.image_enhancer_prompts.get('minimal_clean_bold_typography', {})

            prompt_template = prompt_data['prompts'][0] if prompt_data.get('prompts') else ""

            # Prepare context variables for the prompt template
            context_vars = self._prepare_prompt_context_variables(content_theme, topic, business_context)

            # Fill in the template variables
            filled_prompt = self._fill_prompt_template(prompt_template, context_vars)

            logger.info(f"Generated enhanced prompt using {selected_visual_style} style for theme: {content_theme}")
            return filled_prompt

        except Exception as e:
            logger.error(f"Error identifying content theme and selecting prompt: {e}")
            # Return a fallback prompt
            return self._get_fallback_prompt(content_theme, business_context)

    def _analyze_content_for_visual_style(self, content_theme: str, topic: str, business_context: Dict[str, Any], requested_visual_style: str) -> str:
        """Analyze content to determine the best visual style from image_enhancer_prompts.json"""

        # If a specific visual style is requested and exists, use it
        if requested_visual_style and requested_visual_style in self.image_enhancer_prompts:
            return requested_visual_style

        # Content theme analysis
        content_theme_lower = content_theme.lower()
        topic_lower = topic.lower()

        # Business context analysis
        industry = business_context.get('industry', [])
        if isinstance(industry, list):
            industry = industry[0] if industry else 'general'
        industry_lower = str(industry).lower()

        brand_tone = business_context.get('brand_tone', '').lower()

        # Decision logic based on content analysis
        if any(word in content_theme_lower for word in ['business', 'corporate', 'professional', 'enterprise', 'b2b']):
            return 'modern_corporate_b2b'

        elif any(word in content_theme_lower for word in ['luxury', 'premium', 'elegant', 'high-end']):
            return 'luxury_editorial'

        elif any(word in content_theme_lower for word in ['lifestyle', 'daily', 'personal', 'authentic']):
            return 'photography_led_lifestyle'

        elif any(word in content_theme_lower for word in ['product', 'commercial', 'advertising', 'marketing']):
            return 'product_focused_commercial'

        elif any(word in content_theme_lower for word in ['educational', 'how-to', 'tutorial', 'explain']):
            return 'isometric_explainer'

        elif any(word in content_theme_lower for word in ['fun', 'youthful', 'playful', 'creative']):
            return 'playful_youthful_memphis'

        elif any(word in content_theme_lower for word in ['data', 'infographic', 'statistics', 'analytics']):
            return 'infographic_data_driven'

        elif any(word in content_theme_lower for word in ['quote', 'inspiration', 'motivation', 'thought']):
            return 'quote_card_typography'

        elif any(word in content_theme_lower for word in ['meme', 'viral', 'social', 'engagement']):
            return 'meme_style_engagement'

        elif any(word in content_theme_lower for word in ['tech', 'ai', 'future', 'innovation', 'digital']):
            return 'futuristic_tech_dark'

        elif any(word in content_theme_lower for word in ['retro', 'vintage', 'classic', 'nostalgic']):
            return 'retro_vintage_poster'

        elif any(word in content_theme_lower for word in ['modern', 'clean', 'minimal', 'simple']):
            return 'minimal_clean_bold_typography'

        elif any(word in content_theme_lower for word in ['artistic', 'abstract', 'creative', 'experimental']):
            return 'experimental_artistic_concept'

        elif any(word in content_theme_lower for word in ['illustration', 'cartoon', 'characters', 'fun']):
            return 'flat_illustration_characters'

        elif any(word in content_theme_lower for word in ['editorial', 'magazine', 'publication']):
            return 'magazine_editorial_layout'

        elif any(word in content_theme_lower for word in ['impact', 'bold', 'attention', 'striking']):
            return 'high_impact_color_blocking'

        elif any(word in content_theme_lower for word in ['glass', 'modern', 'ui', 'interface']):
            return 'glassmorphism_neumorphism'

        elif any(word in content_theme_lower for word in ['texture', 'paper', 'handmade', 'organic']):
            return 'textured_design_paper'

        elif any(word in content_theme_lower for word in ['abstract', 'shapes', 'fluid', 'gradient']):
            return 'abstract_shapes_gradients'

        elif any(word in content_theme_lower for word in ['festive', 'celebration', 'holiday', 'seasonal']):
            return 'festive_campaign_creative'

        # Industry-based selection
        elif 'fashion' in industry_lower or 'beauty' in industry_lower:
            return 'luxury_editorial'

        elif 'tech' in industry_lower or 'software' in industry_lower:
            return 'futuristic_tech_dark'

        elif 'food' in industry_lower or 'restaurant' in industry_lower:
            return 'photography_led_lifestyle'

        elif 'finance' in industry_lower or 'consulting' in industry_lower:
            return 'modern_corporate_b2b'

        # Brand tone based selection
        elif 'luxurious' in brand_tone or 'elegant' in brand_tone:
            return 'luxury_editorial'

        elif 'professional' in brand_tone or 'corporate' in brand_tone:
            return 'modern_corporate_b2b'

        elif 'playful' in brand_tone or 'fun' in brand_tone:
            return 'playful_youthful_memphis'

        # Default fallback
        return 'minimal_clean_bold_typography'

    def _prepare_prompt_context_variables(self, content_theme: str, topic: str, business_context: Dict[str, Any]) -> Dict[str, str]:
        """Prepare context variables for prompt template filling"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%H:%M:%S")

        # Brand assets context with primary colors
        brand_assets_context = f"Primary Color: {business_context.get('primary_color', '#007bff')}, Secondary Color: {business_context.get('secondary_color', '#6c757d')}"

        # Location context (can be expanded later)
        location_context = "Business location context not available"

        # Industry and audience handling
        industry = business_context.get('industry', ['General'])
        if isinstance(industry, list):
            industry = industry[0] if industry else 'General'

        target_audience = business_context.get('target_audience', ['General audience'])
        if isinstance(target_audience, list):
            target_audience = target_audience[0] if target_audience else 'General audience'

        # Generated post content
        generated_post = {
            'title': f"{business_context.get('business_name', 'Business')} - {topic}",
            'content': f"Content about {content_theme}: {topic} for {business_context.get('business_name', 'our business')}"
        }

        return {
            'current_date': current_date,
            'current_time': current_time,
            'business_context.get(\'industry\', \'General\')': industry,
            'business_context.get(\'target_audience\', \'General audience\')': target_audience,
            'business_context.get(\'brand_tone\', \'Approachable\')': business_context.get('brand_tone', 'Approachable'),
            'business_context.get(\'brand_voice\', \'Professional and friendly\')': business_context.get('brand_voice', 'Professional and friendly'),
            'brand_assets_context': brand_assets_context,
            'location_context': location_context,
            'generated_post.get(\'title\', \'\')': generated_post['title'],
            'generated_post.get(\'content\', \'\')': generated_post['content']
        }

    def _fill_prompt_template(self, template: str, context_vars: Dict[str, str]) -> str:
        """Fill in the prompt template with context variables"""
        filled_prompt = template
        for placeholder, value in context_vars.items():
            filled_prompt = filled_prompt.replace(f"{{{placeholder}}}", str(value))
        return filled_prompt

    def _get_fallback_prompt(self, content_theme: str, business_context: Dict[str, Any]) -> str:
        """Get a fallback prompt when enhanced prompt selection fails"""
        business_name = business_context.get('business_name', 'Business')
        primary_color = business_context.get('primary_color', '#007bff')

        return f"""Create a professional image for {business_name} about {content_theme}.
Use primary brand color {primary_color}.
Make it suitable for social media with high quality and engaging design."""

    async def generate_content(self, entry: Dict[str, Any], business_context: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Generate content based on content_type with comprehensive business context"""
        try:
            topic = entry.get('topic', 'Sample Topic')
            platform = entry.get('platform', 'Instagram')
            content_type = entry.get('content_type', 'static_post')
            content_theme = entry.get('content_theme', 'business')
            visual_style = entry.get('visual_style', 'minimal_clean_bold_typography')

            # Extract business context information
            business_name = business_context.get('business_name', 'Our Business')
            brand_tone = business_context.get('brand_tone', 'professional')
            brand_voice = business_context.get('brand_voice', 'confident and innovative')
            industry = business_context.get('industry', ['general'])
            if isinstance(industry, list):
                industry = industry[0] if industry else 'general'
            target_audience = business_context.get('target_audience', ['our audience'])
            if isinstance(target_audience, list):
                target_audience = target_audience[0] if target_audience else 'our audience'
            unique_value = business_context.get('unique_value_proposition', 'providing value')
            primary_color = business_context.get('primary_color', '#007bff')
            secondary_color = business_context.get('secondary_color', '#6c757d')

            # Generate content based on content_type
            content_data = {
                'platform': platform,
                'topic': topic,
                'content_type': content_type,
                'content_theme': content_theme,
                'visual_style': visual_style,
                'tone': brand_tone,
                'business_name': business_name,
                'industry': industry,
                'target_audience': target_audience,
                'brand_voice': brand_voice,
                'unique_value': unique_value,
                'primary_color': primary_color,
                'secondary_color': secondary_color
            }

            # Handle different content types
            if content_type == 'static_post':
                # Single image post with caption
                content_data.update({
                    'title': f"{business_name}: {topic}",
                    'content': f"Discover how {business_name} helps {target_audience} with {topic}. Our {unique_value} makes us the perfect partner for your {industry} needs. #BusinessExcellence",
                    'image_type': 'single_image',
                    'aspect_ratio': '1:1',  # Square for Instagram posts
                    'text_overlay': True,
                    'generate_image': True
                })

            elif content_type == 'image_post':
                # Single image post (similar to static_post but focused on image)
                content_data.update({
                    'title': f"{business_name}: {topic}",
                    'content': f"Visual insights about {topic} from {business_name}. Perfect for {target_audience} in {industry}.",
                    'image_type': 'single_image',
                    'aspect_ratio': '1:1',
                    'text_overlay': False,
                    'generate_image': True
                })

            elif content_type == 'carousel':
                # Multi-slide carousel post - generate images for each slide
                content_data.update({
                    'title': f"{topic} - Complete Guide by {business_name}",
                    'content': f"📱 Swipe through our complete guide to {topic}! Our expertise in {industry} helps {target_audience} achieve better results. Follow along for valuable insights! 📈",
                    'carousel_images': [
                        {'slide': 1, 'focus': 'Introduction', 'description': f'Why {topic} matters for {target_audience}'},
                        {'slide': 2, 'focus': 'Key Benefits', 'description': f'Benefits of {topic} in {industry}'},
                        {'slide': 3, 'focus': 'Our Approach', 'description': f'How {business_name} helps with {topic}'},
                        {'slide': 4, 'focus': 'Call to Action', 'description': f'Next steps for {target_audience}'}
                    ],
                    'image_type': 'carousel',
                    'aspect_ratio': '1:1',
                    'slide_count': 4,
                    'generate_image': True
                })

            elif content_type == 'story':
                # Vertical story format - generate image
                content_data.update({
                    'title': f"Quick Tip: {topic}",
                    'content': f"💡 {topic} hack for {target_audience} in {industry}! At {business_name}, we believe in {brand_voice} communication. Tap to learn more! 👆",
                    'image_type': 'story',
                    'aspect_ratio': '9:16',  # Vertical for stories
                    'duration': '15 seconds',
                    'interactive_elements': ['tap_to_learn_more', 'swipe_up'],
                    'generate_image': True
                })

            elif content_type == 'reel':
                # Short-form video content - generate script only
                content_data.update({
                    'title': f"{topic} Explained",
                    'content': f"🎬 Watch: How {business_name} helps {target_audience} with {topic}. Our {industry} expertise makes {unique_value} possible!",
                    'reel_script': {
                        'hook': f"Did you know {topic} can transform your {industry} business?",
                        'value': f"At {business_name}, we help {target_audience} achieve better results with {topic}",
                        'story': f"Here's how {unique_value} makes the difference",
                        'cta': f"Learn more about our {industry} solutions!"
                    },
                    'image_type': 'video_thumbnail',
                    'aspect_ratio': '9:16',  # Vertical for Reels
                    'duration': '15-30 seconds',
                    'video_elements': ['hook_clip', 'explanation', 'testimonial', 'call_to_action'],
                    'generate_image': False,  # Scripts only for reels
                    'generate_script': True
                })

            elif content_type == 'video':
                # Full-length video content - generate script only
                content_data.update({
                    'title': f"Complete Guide: {topic}",
                    'content': f"🎥 Full video: Everything you need to know about {topic}. Our {industry} experts at {business_name} break it down for {target_audience}!",
                    'video_script': {
                        'introduction': f'Welcome to {business_name}s complete guide to {topic}',
                        'main_content': f'Detailed explanation of {topic} for {target_audience} in {industry}',
                        'expert_insights': f'Why {unique_value} matters',
                        'conclusion': f'How {business_name} can help you with {topic}'
                    },
                    'image_type': 'video_thumbnail',
                    'aspect_ratio': '16:9',  # Horizontal for YouTube
                    'duration': '5-15 minutes',
                    'video_elements': ['title_card', 'expert_interview', 'demonstration', 'q_and_a'],
                    'generate_image': False,  # Scripts only for videos
                    'generate_script': True
                })

            else:
                # Default fallback for unknown content types
                content_data.update({
                    'title': f"{business_name} - {topic}",
                    'content': f"Exciting news from {business_name}! We're sharing insights about {topic} that matter to {target_audience} in {industry}.",
                    'image_type': 'single_image',
                    'aspect_ratio': '1:1',
                    'generate_image': True
                })

            # Generate relevant hashtags from business context
            hashtags = []
            if business_context.get('hashtags_that_work_well'):
                hashtags.extend(business_context['hashtags_that_work_well'].split(','))
            else:
                base_hashtags = ['#Business', '#Success', f'#{industry.replace(" ", "")}', f'#{topic.replace(" ", "").capitalize()}']
                if content_type == 'short_video or reel':
                    base_hashtags.extend(['#Reels', '#ShortVideo'])
                elif content_type == 'carousel':
                    base_hashtags.extend(['#Carousel', '#Swipe'])
                elif content_type == 'story':
                    base_hashtags.extend(['#Stories', '#BehindTheScenes'])
                hashtags.extend(base_hashtags)

            content_data['hashtags'] = hashtags

            logger.info(f"Generated {content_type} content for {business_name} about: {topic}")
            logger.debug(f"Content structure: {list(content_data.keys())}")

            return content_data

        except Exception as e:
            logger.error(f"Error generating content for entry {entry['id']}: {e}")
            return None

    async def generate_and_save_images(self, entry: Dict[str, Any], content_data: Dict[str, Any], user_id: str) -> Optional[Dict[str, str]]:
        """Generate and save images based on the content using Gemini Nano. Returns dict with image_url and caption."""
        try:
            topic = entry.get('topic', 'content')
            topic_sanitized = topic.replace(' ', '_').replace('/', '_')
            visual_style = entry.get('visual_style', 'minimal_clean_bold_typography')
            platform = entry.get('platform', 'Instagram')
            content_theme = entry.get('content_theme', 'business')

            # Get business context for the image prompt
            business_context = await self._load_user_profile(user_id)

            # Log the actual colors being used
            primary_color = business_context.get('primary_color', '#007bff')
            secondary_color = business_context.get('secondary_color', '#6c757d')
            logger.info(f"Using user colors for image generation - Primary: {primary_color}, Secondary: {secondary_color}")

            # Generate enhanced image prompt using content theme identification and image enhancer prompts
            enhanced_prompt = self._identify_content_theme_and_select_prompt(content_theme, topic, business_context, visual_style)

            # Create final image prompt that incorporates business context and colors
            image_prompt = self.create_gemini_image_prompt(content_data, visual_style, platform, business_context, enhanced_prompt)

            # Generate image using OpenAI DALL-E with Gemini-enhanced prompt
            if self.openai_client and image_prompt:
                try:
                    logger.info(f"Using Gemini-enhanced prompt for image generation: {image_prompt[:100]}...")

                    response = self.openai_client.images.generate(
                        model="dall-e-3",
                        prompt=image_prompt,
                        size="1024x1024",
                        quality="standard",
                        n=1
                    )

                    dall_e_image_url = response.data[0].url
                    logger.info(f"Generated image from DALL-E: {dall_e_image_url}")

                    # Download image and upload to Supabase Storage
                    uploaded_image_url = await self.upload_image_to_supabase(
                        image_url=dall_e_image_url,
                        topic=topic_sanitized,
                        entry_id=entry['id'],
                        user_id=user_id
                    )

                    if uploaded_image_url:
                        # Generate caption for the image
                        caption = await self.generate_caption_for_image(
                            image_url=uploaded_image_url,
                            topic=topic,
                            content_data=content_data,
                            business_context=business_context
                        )

                        logger.info(f"Generated and uploaded image for topic: {topic} using Gemini-enhanced prompt with OpenAI DALL-E")
                        return {
                            'image_url': uploaded_image_url,
                            'caption': caption
                        }
                    else:
                        logger.error("Failed to upload image to Supabase Storage")
                        return None

                except Exception as e:
                    logger.error(f"Error with OpenAI image generation: {e}")
                    # Try basic prompt as fallback
                    try:
                        basic_prompt = f"Create a professional {visual_style} image for {platform} about {topic} for {business_context.get('business_name', 'a business')} in the {business_context.get('industry', 'general')} industry"
                        response = self.openai_client.images.generate(
                            model="dall-e-3",
                            prompt=basic_prompt,
                            size="1024x1024",
                            quality="standard",
                            n=1
                        )

                        dall_e_image_url = response.data[0].url
                        
                        # Upload to Supabase Storage
                        uploaded_image_url = await self.upload_image_to_supabase(
                            image_url=dall_e_image_url,
                            topic=topic_sanitized,
                            entry_id=entry['id'],
                            user_id=user_id
                        )

                        if uploaded_image_url:
                            # Generate caption
                            caption = await self.generate_caption_for_image(
                                image_url=uploaded_image_url,
                                topic=topic,
                                content_data=content_data,
                                business_context=business_context
                            )

                            logger.info(f"Generated and uploaded image for topic: {topic} using basic fallback prompt")
                            return {
                                'image_url': uploaded_image_url,
                                'caption': caption
                            }
                        else:
                            logger.error("Failed to upload image to Supabase Storage")
                            return None
                    except Exception as fallback_error:
                        logger.error(f"Error with fallback image generation: {fallback_error}")
                        return None
            else:
                logger.warning("OpenAI client not available for image generation")
                return None

        except Exception as e:
            logger.error(f"Error generating/saving image for entry {entry['id']}: {e}")
            return None

    def create_gemini_image_prompt(self, content_data: Dict[str, Any], visual_style: str, platform: str, business_context: Dict[str, Any], enhanced_prompt: str) -> str:
        """Create an image generation prompt for Gemini Nano based on content type and business context"""
        try:
            topic = content_data.get('topic', '')
            content_type = content_data.get('content_type', 'static_post')
            content_theme = content_data.get('content_theme', 'business')
            aspect_ratio = content_data.get('aspect_ratio', '1:1')
            business_name = content_data.get('business_name', 'business')
            primary_color = content_data.get('primary_color', '#007bff')
            secondary_color = content_data.get('secondary_color', '#6c757d')

            # Use the enhanced prompt as the base, which is already intelligently selected
            if enhanced_prompt and len(enhanced_prompt) > 50:  # Ensure it's a real enhanced prompt
                prompt = enhanced_prompt
                logger.info(f"Using intelligently selected enhanced prompt for {content_theme} theme")
            else:
                # Fallback if enhanced prompt is not available
                prompt = f"Create a professional {visual_style} image for {platform} about {topic} in {content_theme} theme"

            # Add specific content instructions based on type
            content_specific_addition = self._get_content_specific_prompt_addition(content_data)

            # Add brand color reinforcement
            brand_color_addition = f"""

CRITICAL BRAND COLOR REQUIREMENTS:
- Primary Brand Color: {primary_color} (USE THIS AS THE DOMINANT COLOR)
- Secondary Brand Color: {secondary_color} (USE FOR ACCENTS AND SECONDARY ELEMENTS)
- Business: {business_name}
- Content Theme: {content_theme}
- Platform: {platform}
- Aspect Ratio: {aspect_ratio}

ENSURE THE GENERATED IMAGE INCORPORATES THESE BRAND COLORS PROMINENTLY.

VERIFICATION: These colors come from the user's profile in Supabase (user_id: {business_context.get('id', 'unknown')})."""

            return prompt.strip()

        except Exception as e:
            logger.error(f"Error creating Gemini image prompt: {e}")
            return f"Create a professional image about {topic} for {business_name} in {industry} industry, using primary color {primary_color}"

    def _get_content_specific_prompt_addition(self, content_data: Dict[str, Any]) -> str:
        """Get content-type specific prompt additions"""
        content_type = content_data.get('content_type', 'static_post')
        topic = content_data.get('topic', '')
        content_theme = content_data.get('content_theme', 'business')

        if content_type == 'carousel':
            slide_count = content_data.get('slide_count', 4)
            return f"\n\nCONTENT SPECIFIC: This is part of a {slide_count}-slide carousel series about '{topic}' in '{content_theme}' theme. Design as a cohesive carousel image."

        elif content_type == 'story':
            return f"\n\nCONTENT SPECIFIC: Vertical story format optimized for mobile viewing about '{topic}' in '{content_theme}' theme."

        elif content_type in ['static_post', 'image_post']:
            return f"\n\nCONTENT SPECIFIC: Single image post about '{topic}' in '{content_theme}' theme, perfect for Instagram feed."

        else:
            return f"\n\nCONTENT SPECIFIC: Content about '{topic}' in '{content_theme}' theme."

    async def upload_image_to_supabase(self, image_url: str, topic: str, entry_id: str, user_id: str) -> Optional[str]:
        """Download image from URL and upload to Supabase Storage. Returns public URL."""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(image_url)
                response.raise_for_status()
                image_bytes = response.content

                # Create filename (sanitize topic to remove invalid characters)
                import re
                sanitized_topic = re.sub(r'[<>:"/\\|?*\'"]', '', topic)  # Remove invalid Windows filename characters
                sanitized_topic = sanitized_topic.replace(' ', '_')[:50]  # Replace spaces with underscores, limit length
                
                # Generate unique filename for Supabase Storage
                unique_id = str(uuid.uuid4())[:8]
                filename = f"cron_generated/{sanitized_topic}_{entry_id[:8]}_{unique_id}.png"
                
                logger.info(f"📤 Uploading image to Supabase Storage: {filename}")

                # Upload to ai-generated-images bucket
                storage_response = self.supabase.storage.from_("ai-generated-images").upload(
                    filename,
                    image_bytes,
                    file_options={"content-type": "image/png", "upsert": "false"}
                )

                if hasattr(storage_response, 'error') and storage_response.error:
                    logger.error(f"Storage upload error: {storage_response.error}")
                    return None

                # Get public URL
                public_url = self.supabase.storage.from_("ai-generated-images").get_public_url(filename)
                logger.info(f"✅ Image uploaded successfully to Supabase Storage: {public_url}")

                return public_url

        except Exception as e:
            logger.error(f"Error uploading image to Supabase: {e}")
            return None

    # Removed download_and_save_image method - images are now only saved to Supabase Storage

    # Removed save_image_from_base64 method - images are now only saved to Supabase Storage

    async def generate_caption_for_image(self, image_url: str, topic: str, content_data: Dict[str, Any], business_context: Dict[str, Any]) -> str:
        """Generate a compelling caption for the generated image using OpenAI"""
        try:
            platform = content_data.get('platform', 'Instagram')
            content_type = content_data.get('content_type', 'static_post')
            business_name = content_data.get('business_name', 'Business')
            industry = content_data.get('industry', 'general')
            target_audience = content_data.get('target_audience', 'our audience')
            brand_voice = content_data.get('brand_voice', 'professional and friendly')
            
            caption_prompt = f"""Create a compelling social media caption for this image.

IMAGE CONTEXT:
- Topic: {topic}
- Platform: {platform}
- Content Type: {content_type}
- Business: {business_name}
- Industry: {industry}
- Target Audience: {target_audience}
- Brand Voice: {brand_voice}

REQUIREMENTS:
1. Create an engaging caption (100-200 characters) that hooks the audience
2. Include relevant hashtags (5-8 hashtags)
3. Match the brand voice: {brand_voice}
4. Optimize for {platform} algorithm
5. Include a call-to-action if appropriate

FORMAT (Return ONLY this format):
CAPTION: [Your engaging caption here with emojis]

Make it authentic, engaging, and optimized for maximum engagement!"""

            if self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": caption_prompt}],
                    max_tokens=300,
                    temperature=0.8
                )
                caption_result = response.choices[0].message.content.strip()
                
                # Parse caption from response
                caption = ""
                for line in caption_result.split('\n'):
                    line = line.strip()
                    if line.startswith('CAPTION:'):
                        caption = line.replace('CAPTION:', '').strip()
                        break
                
                if not caption:
                    # Fallback if parsing fails
                    caption = f"Check out this amazing content about {topic}! Perfect for {target_audience} in {industry}. #Business #Success"
                
                logger.info(f"✅ Generated caption: {caption[:100]}...")
                return caption
            else:
                # Fallback caption if OpenAI is not available
                logger.warning("OpenAI client not available, using fallback caption")
                return f"Exciting content about {topic} from {business_name}! Perfect for {target_audience} in {industry}. #Business #Success"
                
        except Exception as e:
            logger.error(f"Error generating caption: {e}")
            # Fallback caption
            return f"Great content about {topic}! #Business #Success"

    async def save_to_created_content(
        self,
        entry: Dict[str, Any],
        content_data: Dict[str, Any],
        user_id: str,
        image_url: Optional[str] = None,
        caption: Optional[str] = None
    ):
        """Save generated content to created_content table"""
        try:
            platform = entry.get('platform', 'Instagram')
            content_type = entry.get('content_type', 'static_post')
            topic = entry.get('topic', '')
            entry_date = entry.get('entry_date')
            scheduled_time = entry.get('scheduled_time')
            
            # Prepare data for created_content table
            db_data = {
                'user_id': user_id,
                'platform': platform.lower() if platform else None,
                'content_type': content_type.lower(),
                'title': content_data.get('title', f"{content_data.get('business_name', 'Business')}: {topic}"),
                'content': caption or content_data.get('content', f"Content about {topic}"),
                'status': 'generated',
                'channel': 'Social Media',  # Default channel
                'hashtags': content_data.get('hashtags', []),
                'metadata': {
                    'calendar_entry_id': entry.get('id'),
                    'content_theme': entry.get('content_theme'),
                    'visual_style': entry.get('visual_style'),
                    'topic': topic,
                    'generated_at': datetime.now().isoformat(),
                    'generated_by': 'content_generation_cron'
                }
            }
            
            # Add images if available
            if image_url:
                db_data['images'] = [image_url]
                db_data['media_url'] = image_url  # Also set media_url field
            
            # Add carousel images if available
            if content_data.get('carousel_images'):
                carousel_urls = []
                for carousel_item in content_data.get('carousel_images', []):
                    if isinstance(carousel_item, dict) and carousel_item.get('image_url'):
                        carousel_urls.append(carousel_item['image_url'])
                    elif isinstance(carousel_item, str):
                        carousel_urls.append(carousel_item)
                if carousel_urls:
                    db_data['carousel_images'] = carousel_urls
            
            # Add scripts if available
            if content_data.get('reel_script'):
                reel_script_text = self._format_reel_script(content_data.get('reel_script', {}))
                db_data['short_video_script'] = reel_script_text
                
            if content_data.get('video_script'):
                video_script_text = self._format_video_script(content_data.get('video_script', {}))
                db_data['long_video_script'] = video_script_text
            
            # Add scheduling information if available
            if entry_date:
                db_data['scheduled_date'] = entry_date
            if scheduled_time:
                db_data['scheduled_time'] = scheduled_time
            
            # Add additional fields from content_data
            if content_data.get('hook_type'):
                db_data['hook_type'] = content_data.get('hook_type')
            if content_data.get('call_to_action'):
                db_data['call_to_action'] = content_data.get('call_to_action')
            
            logger.info(f"💾 Saving to created_content table with keys: {list(db_data.keys())}")
            
            # Insert into created_content table
            result = self.supabase.table('created_content').insert(db_data).execute()
            
            if result.data and len(result.data) > 0:
                content_id = result.data[0]['id']
                logger.info(f"✅ Successfully saved content to created_content table with ID: {content_id}")
                logger.info(f"📸 Images saved: {len(db_data.get('images', []))} image(s)")
                logger.info(f"🎠 Carousel images saved: {len(db_data.get('carousel_images', []))} image(s)")
                if db_data.get('short_video_script'):
                    logger.info(f"🎬 Short video script saved: {len(db_data['short_video_script'])} characters")
                if db_data.get('long_video_script'):
                    logger.info(f"🎥 Long video script saved: {len(db_data['long_video_script'])} characters")
            else:
                logger.warning("Failed to save content to created_content table - no data returned")
                
        except Exception as e:
            logger.error(f"Error saving content to created_content table: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _format_reel_script(self, reel_script: Dict[str, Any]) -> str:
        """Format reel script dictionary into text"""
        script_parts = []
        if reel_script.get('hook'):
            script_parts.append(f"HOOK: {reel_script['hook']}")
        if reel_script.get('value'):
            script_parts.append(f"VALUE: {reel_script['value']}")
        if reel_script.get('story'):
            script_parts.append(f"STORY: {reel_script['story']}")
        if reel_script.get('cta'):
            script_parts.append(f"CTA: {reel_script['cta']}")
        return "\n\n".join(script_parts) if script_parts else ""

    def _format_video_script(self, video_script: Dict[str, Any]) -> str:
        """Format video script dictionary into text"""
        script_parts = []
        if video_script.get('introduction'):
            script_parts.append(f"INTRODUCTION: {video_script['introduction']}")
        if video_script.get('main_content'):
            script_parts.append(f"MAIN CONTENT: {video_script['main_content']}")
        if video_script.get('expert_insights'):
            script_parts.append(f"EXPERT INSIGHTS: {video_script['expert_insights']}")
        if video_script.get('conclusion'):
            script_parts.append(f"CONCLUSION: {video_script['conclusion']}")
        return "\n\n".join(script_parts) if script_parts else ""

    # Removed save_script_to_file and _format_script_content methods - scripts are now only saved to database

async def main():
    """Main function to run the cron job"""
    cron = ContentGenerationCron()
    await cron.process_calendar_entries()

if __name__ == "__main__":
    # Run the cron job
    asyncio.run(main())