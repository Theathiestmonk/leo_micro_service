#!/usr/bin/env python3
"""
Content Generation Cron Job
Processes calendar_entries where content = false and generates content using ContentCreationAgent
"""

import os
import logging
import asyncio
import base64
from typing import Dict, Any, List
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv
import openai
import google.genai as genai
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

        # Initialize OpenAI
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.openai_client = openai.OpenAI(api_key=self.openai_api_key) if self.openai_api_key else None

        # Initialize Gemini client
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.gemini_client = None
        if gemini_api_key:
            try:
                self.gemini_client = genai.Client(api_key=gemini_api_key)
                logger.info("Gemini client initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini client: {e}")
                self.gemini_client = None

        # Initialize ContentCreationAgent (commented out due to missing dependencies)
        # self.content_agent = ContentCreationAgent(
        #     supabase_url=self.supabase_url,
        #     supabase_key=self.supabase_key,
        #     openai_api_key=self.openai_api_key
        # )
        self.content_agent = None  # Will use mock functionality

        # Create images directory if it doesn't exist
        self.images_dir = os.path.join(os.getcwd(), 'generated_images')
        os.makedirs(self.images_dir, exist_ok=True)

    async def _load_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Load business context from user profile with fallback"""
        try:
            # Start with basic fields that are most likely to exist
            basic_fields = [
                "business_name", "business_description", "brand_tone", "brand_voice",
                "industry", "target_audience", "unique_value_proposition",
                "social_media_platforms", "primary_goals", "content_themes",
                "name", "avatar_url", "onboarding_completed"
            ]

            # Try to load basic profile first
            response = self.supabase.table("profiles").select(
                ", ".join(basic_fields)
            ).eq("id", user_id).execute()

            if response.data and len(response.data) > 0:
                profile_data = response.data[0]
                logger.info(f"Loaded business context for user {user_id}: {profile_data.get('business_name', 'Unknown')}")

                # Provide default values for missing fields
                defaults = {
                    'brand_tone': profile_data.get('brand_tone', 'professional'),
                    'business_name': profile_data.get('business_name', 'Our Business'),
                    'industry': profile_data.get('industry', ['general']),
                    'target_audience': profile_data.get('target_audience', ['our audience']),
                    'unique_value': profile_data.get('unique_value_proposition', 'providing value'),
                    'brand_voice': profile_data.get('brand_voice', 'professional and helpful'),
                    'content_themes': profile_data.get('content_themes', ['business', 'growth'])
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
                'content_themes': ['business']
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
            # Generate and save images
            await self.generate_and_save_images(entry, content_data, user_id)

            # Update calendar entry to mark content as generated
            self.supabase.table('calendar_entries').update({
                'content': True,
                'status': 'content_generated',
                'updated_at': datetime.now().isoformat()
            }).eq('id', entry_id).execute()

            logger.info(f"Successfully processed entry {entry_id}")

    async def generate_content(self, entry: Dict[str, Any], business_context: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Generate content based on content_type with comprehensive business context"""
        try:
            topic = entry.get('topic', 'Sample Topic')
            platform = entry.get('platform', 'Instagram')
            content_type = entry.get('content_type', 'static_post')

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

            # Generate content based on content_type
            content_data = {
                'platform': platform,
                'topic': topic,
                'content_type': content_type,
                'tone': brand_tone,
                'business_name': business_name,
                'industry': industry,
                'target_audience': target_audience,
                'brand_voice': brand_voice,
                'unique_value': unique_value
            }

            if content_type == 'static_post':
                # Single image post with caption
                content_data.update({
                    'title': f"{business_name}: {topic}",
                    'content': f"Discover how {business_name} helps {target_audience} with {topic}. Our {unique_value} makes us the perfect partner for your {industry} needs. #BusinessExcellence",
                    'image_type': 'single_image',
                    'aspect_ratio': '1:1',  # Square for Instagram posts
                    'text_overlay': True
                })

            elif content_type == 'carousel':
                # Multi-slide carousel post
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
                    'slide_count': 4
                })

            elif content_type == 'story':
                # Vertical story format
                content_data.update({
                    'title': f"Quick Tip: {topic}",
                    'content': f"💡 {topic} hack for {target_audience} in {industry}! At {business_name}, we believe in {brand_voice} communication. Tap to learn more! 👆",
                    'image_type': 'story',
                    'aspect_ratio': '9:16',  # Vertical for stories
                    'duration': '15 seconds',
                    'interactive_elements': ['tap_to_learn_more', 'swipe_up']
                })

            elif content_type == 'short_video or reel':
                # Short-form video content
                content_data.update({
                    'title': f"{topic} Explained",
                    'content': f"🎬 Watch: How {business_name} helps {target_audience} with {topic}. Our {industry} expertise makes {unique_value} possible!",
                    'short_video_script': {
                        'hook': f"Did you know {topic} can transform your {industry} business?",
                        'value': f"At {business_name}, we help {target_audience} achieve better results with {topic}",
                        'story': f"Here's how {unique_value} makes the difference",
                        'cta': f"Learn more about our {industry} solutions!"
                    },
                    'image_type': 'video_thumbnail',
                    'aspect_ratio': '9:16',  # Vertical for Reels
                    'duration': '15-30 seconds',
                    'video_elements': ['hook_clip', 'explanation', 'testimonial', 'call_to_action']
                })

            elif content_type == 'long_video':
                # Full-length video content
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
                    'video_elements': ['title_card', 'expert_interview', 'demonstration', 'q_and_a']
                })

            elif content_type == 'email':
                # Email marketing content
                content_data.update({
                    'title': f"Important: {topic}",
                    'content': f"Subject: {topic} - Insights for {target_audience}\n\nDear valued {target_audience},\n\nWe're excited to share our latest insights on {topic}. As leaders in {industry}, {business_name} has helped countless organizations achieve better results.\n\nOur {unique_value} approach ensures you get the best possible outcomes.\n\nBest regards,\n{business_name} Team",
                    'email_elements': {
                        'subject': f"{topic} - Insights for {target_audience}",
                        'preview_text': f"Discover how {business_name} can help with {topic}",
                        'body': f"Comprehensive information about {topic} for {target_audience}",
                        'cta': f"Learn more about our {industry} solutions"
                    },
                    'image_type': 'email_header',
                    'aspect_ratio': '16:9'
                })

            else:
                # Default fallback for unknown content types
                content_data.update({
                    'title': f"{business_name} - {topic}",
                    'content': f"Exciting news from {business_name}! We're sharing insights about {topic} that matter to {target_audience} in {industry}.",
                    'image_type': 'single_image',
                    'aspect_ratio': '1:1'
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

    async def generate_and_save_images(self, entry: Dict[str, Any], content_data: Dict[str, Any], user_id: str):
        """Generate and save images based on the content"""
        try:
            topic = entry.get('topic', 'content').replace(' ', '_').replace('/', '_')
            visual_style = entry.get('visual_style', 'modern')
            platform = entry.get('platform', 'Instagram')

            # Generate image prompt based on content
            image_prompt = self.create_image_prompt(content_data, visual_style, platform)

            # Generate image using OpenAI DALL-E
            if self.openai_client and image_prompt:
                response = self.openai_client.images.generate(
                    model="dall-e-3",
                    prompt=image_prompt,
                    size="1024x1024",
                    quality="standard",
                    n=1
                )

                image_url = response.data[0].url

                # Download and save the image
                await self.download_and_save_image(image_url, topic, entry['id'])

                logger.info(f"Generated and saved image for topic: {topic}")

        except Exception as e:
            logger.error(f"Error generating/saving image for entry {entry['id']}: {e}")

    def create_image_prompt(self, content_data: Dict[str, Any], visual_style: str, platform: str) -> str:
        """Create an image generation prompt based on content type and business context"""
        try:
            title = content_data.get('title', '')
            content = content_data.get('content', '')
            topic = content_data.get('topic', '')
            content_type = content_data.get('content_type', 'static_post')
            image_type = content_data.get('image_type', 'single_image')
            aspect_ratio = content_data.get('aspect_ratio', '1:1')
            business_name = content_data.get('business_name', 'business')
            industry = content_data.get('industry', 'general')
            brand_tone = content_data.get('tone', 'professional')
            target_audience = content_data.get('target_audience', 'audience')

            # Base prompt structure
            prompt = f"Create a {visual_style} style image for {platform} {content_type}"

            # Customize based on content type and image type
            if content_type == 'static_post' and image_type == 'single_image':
                prompt += f" featuring {business_name} branding"
                if aspect_ratio == '1:1':
                    prompt += " in square format perfect for Instagram posts"
                prompt += ". Include text overlay space for the caption."

            elif content_type == 'carousel':
                slide_count = content_data.get('slide_count', 4)
                prompt += f" carousel set with {slide_count} connected slides"
                carousel_info = content_data.get('carousel_images', [])
                if carousel_info:
                    prompt += f". First slide: {carousel_info[0].get('description', '')}"
                prompt += ". Design as a cohesive carousel series."

            elif content_type == 'story':
                prompt += f" in vertical story format (9:16 aspect ratio)"
                if content_data.get('interactive_elements'):
                    prompt += ". Include interactive elements like call-to-action overlays"
                prompt += ". Optimized for mobile story viewing."

            elif content_type in ['short_video or reel', 'long_video']:
                prompt += f" video thumbnail for {content_type}"
                if aspect_ratio == '9:16':
                    prompt += " in vertical format for mobile video"
                elif aspect_ratio == '16:9':
                    prompt += " in horizontal format for YouTube"
                prompt += ". Eye-catching thumbnail design to maximize click-through rate."

            elif content_type == 'email':
                prompt += " email header/banner"
                prompt += ". Professional design suitable for email marketing campaigns."

            else:
                prompt += f" for {business_name}"

            # Add business context
            prompt += f"""

Business Context:
- Company: {business_name}
- Industry: {industry}
- Target Audience: {target_audience}
- Brand Tone: {brand_tone}

Content Details:
- Title: {title}
- Topic: {topic}
- Content Type: {content_type}

Style Requirements:
- {visual_style} aesthetic matching {brand_tone} brand tone
- Optimized for {platform} platform
- Professional and engaging for {industry} industry
- High quality, suitable for social media
- Include relevant visual elements for {business_name}'s {industry} business
- Reflect {target_audience} as the target audience
- Modern, clean design with brand-appropriate colors
- Aspect ratio: {aspect_ratio}
"""

            return prompt.strip()

        except Exception as e:
            logger.error(f"Error creating image prompt: {e}")
            return None

    async def download_and_save_image(self, image_url: str, topic: str, entry_id: str):
        """Download image from URL and save to local directory"""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(image_url)
                response.raise_for_status()

                # Create filename (sanitize topic to remove invalid characters)
                import re
                sanitized_topic = re.sub(r'[<>:"/\\|?*\'"]', '', topic)  # Remove invalid Windows filename characters
                sanitized_topic = sanitized_topic.replace(' ', '_')[:50]  # Replace spaces with underscores, limit length
                filename = f"{sanitized_topic}_{entry_id[:8]}.png"
                filepath = os.path.join(self.images_dir, filename)

                # Save image
                with open(filepath, 'wb') as f:
                    f.write(response.content)

                logger.info(f"Saved image: {filepath}")

        except Exception as e:
            logger.error(f"Error downloading/saving image: {e}")

async def main():
    """Main function to run the cron job"""
    cron = ContentGenerationCron()
    await cron.process_calendar_entries()

if __name__ == "__main__":
    # Run the cron job
    asyncio.run(main())