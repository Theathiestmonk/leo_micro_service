"""
Content Creation Agent
Intelligent content generation system with strategy planning and personalization
"""

import os
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from supabase import create_client, Client
import openai

logger = logging.getLogger(__name__)


class ContentCreationAgent:
    """Main agent for intelligent content generation with strategy and personalization"""
    
    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        openai_api_key: str,
        update_progress_callback: Optional[Callable] = None
    ):
        """
        Initialize ContentCreationAgent
        
        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase service role key
            openai_api_key: OpenAI API key for content generation
            update_progress_callback: Async function to update progress (user_id, step, percentage, details)
        """
        self.supabase = create_client(supabase_url, supabase_key)
        self.openai_api_key = openai_api_key
        self.update_progress = update_progress_callback
        
        # Initialize OpenAI client
        if openai_api_key:
            self.openai_client = openai.OpenAI(api_key=openai_api_key)
        else:
            logger.warning("OpenAI API key not provided, content generation will be limited")
            self.openai_client = None
        
        # Import ATSN helper functions
        try:
            from agents.atsn import (
                get_business_context_from_profile,
                get_trends_from_grok,
                parse_trends_for_content,
                get_platform_specific_prompt,
                parse_instagram_response,
                build_content_brand_context,
                build_image_enhancer_brand_assets,
                build_location_context
            )
            self.get_business_context = get_business_context_from_profile
            self.get_trends = get_trends_from_grok
            self.parse_trends = parse_trends_for_content
            self.get_platform_prompt = get_platform_specific_prompt
            self.parse_instagram = parse_instagram_response
            self.build_brand_context = build_content_brand_context
            self.build_image_brand_assets = build_image_enhancer_brand_assets
            self.build_location = build_location_context
        except ImportError as e:
            logger.error(f"Failed to import ATSN functions: {e}")
            raise
    
    async def _update_progress(self, user_id: str, step: str, percentage: int, details: str):
        """Internal progress update helper"""
        if self.update_progress:
            try:
                await self.update_progress(user_id, step, percentage, details)
            except Exception as e:
                logger.error(f"Error updating progress: {e}")
    
    async def run_weekly_generation(
        self,
        user_id: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for weekly content generation
        
        Args:
            user_id: User ID to generate content for
            options: Optional generation options (platforms, date_range, etc.)
        
        Returns:
            Dict with success status and generated content info
        """
        try:
            await self._update_progress(
                user_id,
                "initializing",
                5,
                "Starting content generation..."
            )
            
            # Load user profile and business context
            await self._update_progress(
                user_id,
                "loading_profile",
                10,
                "Loading your business profile..."
            )
            
            profile_data = await self._load_user_profile(user_id)
            business_context = self.get_business_context(profile_data)
            
            # Generate content strategy
            await self._update_progress(
                user_id,
                "generating_strategy",
                20,
                "Creating your content strategy..."
            )
            
            # Import strategy engine
            from agents.content_strategy_engine import ContentStrategyEngine
            strategy_engine = ContentStrategyEngine(
                self.supabase,
                self.openai_client,
                business_context
            )
            
            strategy = await strategy_engine.generate_strategy(user_id, options)
            
            # Create content calendar
            await self._update_progress(
                user_id,
                "creating_calendar",
                30,
                "Building your content calendar..."
            )
            
            calendar = await self.create_content_calendar(user_id, strategy, business_context)
            
            # Create campaign
            await self._update_progress(
                user_id,
                "creating_campaign",
                40,
                "Setting up your content campaign..."
            )
            
            campaign_id = await self._create_campaign(user_id, strategy, calendar)
            
            # Generate posts
            await self._update_progress(
                user_id,
                "generating_posts",
                50,
                "Generating your content posts..."
            )
            
            posts = await self.generate_posts_for_campaign(
                campaign_id,
                user_id,
                calendar,
                business_context,
                profile_data
            )
            
            await self._update_progress(
                user_id,
                "completed",
                100,
                f"Successfully generated {len(posts)} content posts!"
            )
            
            return {
                "success": True,
                "campaign_id": campaign_id,
                "posts_generated": len(posts),
                "strategy": strategy,
                "calendar": calendar
            }
            
        except Exception as e:
            logger.error(f"Error in weekly content generation: {e}")
            await self._update_progress(
                user_id,
                "error",
                0,
                f"Content generation failed: {str(e)}"
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _load_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Load user profile from database"""
        try:
            profile_fields = [
                "business_name", "business_description", "brand_tone", "industry",
                "target_audience", "brand_voice", "unique_value_proposition",
                "primary_color", "secondary_color", "brand_colors", "logo_url",
                "timezone", "location_city", "location_state", "location_country", "address",
                "posting_frequency", "preferred_content_types", "content_themes",
                "social_media_platforms", "primary_goals"
            ]
            
            response = self.supabase.table("profiles").select(
                ", ".join(profile_fields)
            ).eq("id", user_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            else:
                logger.warning(f"No profile found for user {user_id}")
                return {}
        except Exception as e:
            logger.error(f"Error loading profile: {e}")
            return {}
    
    async def _create_campaign(
        self,
        user_id: str,
        strategy: Dict[str, Any],
        calendar: List[Dict[str, Any]]
    ) -> str:
        """Create a content campaign in the database"""
        try:
            # Calculate week dates
            today = datetime.now()
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            
            campaign_data = {
                "user_id": user_id,
                "campaign_name": strategy.get("campaign_name", f"Weekly Content - {week_start.strftime('%Y-%m-%d')}"),
                "week_start_date": week_start.date().isoformat(),
                "week_end_date": week_end.date().isoformat(),
                "status": "generating",
                "total_posts": len(calendar),
                "generated_posts": 0,
                "metadata": {
                    "strategy": strategy,
                    "generated_at": datetime.now().isoformat()
                }
            }
            
            response = self.supabase.table("content_campaigns").insert(
                campaign_data
            ).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]["id"]
            else:
                raise Exception("Failed to create campaign")
                
        except Exception as e:
            logger.error(f"Error creating campaign: {e}")
            raise
    
    async def create_content_calendar(
        self,
        user_id: str,
        strategy: Dict[str, Any],
        business_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate content calendar based on strategy
        
        Args:
            user_id: User ID
            strategy: Generated content strategy
            business_context: Business context from profile
        
        Returns:
            List of content calendar items with dates, platforms, and topics
        """
        try:
            # Import strategy engine for calendar generation
            from agents.content_strategy_engine import ContentStrategyEngine
            strategy_engine = ContentStrategyEngine(
                self.supabase,
                self.openai_client,
                business_context
            )
            
            calendar = await strategy_engine.generate_calendar(user_id, strategy)
            return calendar
            
        except Exception as e:
            logger.error(f"Error creating content calendar: {e}")
            # Return default calendar if strategy engine fails
            return self._generate_default_calendar(user_id, strategy)
    
    def _generate_default_calendar(
        self,
        user_id: str,
        strategy: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate a default calendar if strategy engine fails"""
        platforms = strategy.get("platforms", ["Instagram"])
        posts_per_platform = strategy.get("posts_per_platform", 7)
        
        calendar = []
        today = datetime.now()
        
        for day_offset in range(7):
            post_date = today + timedelta(days=day_offset)
            for platform in platforms:
                for post_num in range(posts_per_platform // len(platforms)):
                    calendar.append({
                        "date": post_date.date().isoformat(),
                        "time": "12:00:00",
                        "platform": platform,
                        "content_type": "static_post",
                        "topic": strategy.get("themes", ["General content"])[0],
                        "post_type": "Educational tips"
                    })
        
        return calendar[:posts_per_platform * len(platforms)]
    
    async def generate_posts_for_campaign(
        self,
        campaign_id: str,
        user_id: str,
        calendar: List[Dict[str, Any]],
        business_context: Dict[str, Any],
        profile_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate individual posts for a campaign
        
        Args:
            campaign_id: Campaign ID
            user_id: User ID
            calendar: Content calendar
            business_context: Business context
            profile_data: Full profile data
        
        Returns:
            List of generated post IDs
        """
        generated_posts = []
        total_posts = len(calendar)
        
        # Extract profile assets
        profile_assets = {
            'primary_color': profile_data.get('primary_color'),
            'secondary_color': profile_data.get('secondary_color'),
            'brand_colors': profile_data.get('brand_colors') or [],
            'logo': profile_data.get('logo_url'),
            'primary_typography': profile_data.get('primary_typography'),
            'secondary_typography': profile_data.get('secondary_typography')
        }
        
        for idx, calendar_item in enumerate(calendar):
            try:
                progress = 50 + int((idx / total_posts) * 40)
                await self._update_progress(
                    user_id,
                    "generating_posts",
                    progress,
                    f"Generating post {idx + 1} of {total_posts}..."
                )
                
                # Generate content for this calendar item
                post_data = await self._generate_single_post(
                    calendar_item,
                    business_context,
                    profile_assets,
                    user_id
                )
                
                # Save to database
                post_data["campaign_id"] = campaign_id
                post_data["platform"] = calendar_item.get("platform", "Instagram")
                post_data["post_type"] = calendar_item.get("post_type", "text")
                post_data["scheduled_date"] = calendar_item.get("date")
                post_data["scheduled_time"] = calendar_item.get("time", "12:00:00")
                post_data["status"] = "draft"
                
                response = self.supabase.table("content_posts").insert(
                    post_data
                ).execute()
                
                if response.data and len(response.data) > 0:
                    generated_posts.append(response.data[0])
                    
                    # Update campaign progress
                    self.supabase.table("content_campaigns").update({
                        "generated_posts": len(generated_posts)
                    }).eq("id", campaign_id).execute()
                
            except Exception as e:
                logger.error(f"Error generating post {idx + 1}: {e}")
                continue
        
        # Mark campaign as completed
        self.supabase.table("content_campaigns").update({
            "status": "completed"
        }).eq("id", campaign_id).execute()
        
        return generated_posts
    
    async def _generate_single_post(
        self,
        calendar_item: Dict[str, Any],
        business_context: Dict[str, Any],
        profile_assets: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """Generate a single post based on calendar item"""
        try:
            platform = calendar_item.get("platform", "Instagram")
            topic = calendar_item.get("topic", "")
            content_type = calendar_item.get("content_type", "static_post")
            
            # Get trends for this topic
            trends_data = await self.get_trends(topic, business_context)
            parsed_trends = self.parse_trends(trends_data)
            
            # Build payload for content generation
            payload = {
                "platform": platform,
                "content_type": content_type,
                "content_idea": topic,
                "Post_type": calendar_item.get("post_type", "Educational tips"),
                "channel": platform
            }
            
            # Get platform-specific prompt
            prompt = self.get_platform_prompt(
                platform,
                payload,
                business_context,
                parsed_trends,
                profile_assets
            )
            
            # Generate content with OpenAI
            if self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=600,
                    temperature=0.7
                )
                
                generated_response = response.choices[0].message.content.strip()
                
                # Parse response based on platform
                if platform.lower() == "instagram":
                    parsed_content = self.parse_instagram(generated_response)
                    title = parsed_content.get("title", "")
                    content = parsed_content.get("content", "")
                    hashtags = parsed_content.get("hashtags", [])
                else:
                    # Parse generic format
                    lines = generated_response.split('\n')
                    title = ""
                    content = ""
                    hashtags = []
                    current_section = None
                    
                    for line in lines:
                        line = line.strip()
                        if line.startswith('TITLE:'):
                            title = line.replace('TITLE:', '').strip()
                            current_section = 'title'
                        elif line.startswith('CONTENT:'):
                            content = line.replace('CONTENT:', '').strip()
                            current_section = 'content'
                        elif line.startswith('HASHTAGS:'):
                            hashtags_text = line.replace('HASHTAGS:', '').strip()
                            hashtags = hashtags_text.split() if hashtags_text else []
                            current_section = 'hashtags'
                        elif current_section == 'content' and line:
                            content += ' ' + line
                        elif current_section == 'hashtags' and line:
                            hashtags.extend(line.split())
                
                return {
                    "title": title,
                    "content": content,
                    "hashtags": hashtags,
                    "metadata": {
                        "topic": topic,
                        "trends": parsed_trends,
                        "generated_at": datetime.now().isoformat()
                    }
                }
            else:
                raise Exception("OpenAI client not configured")
                
        except Exception as e:
            logger.error(f"Error generating single post: {e}")
            # Return fallback content
            return {
                "title": f"Content about {calendar_item.get('topic', 'your business')}",
                "content": f"Engaging content about {calendar_item.get('topic', 'your business')}",
                "hashtags": [],
                "metadata": {
                    "error": str(e),
                    "generated_at": datetime.now().isoformat()
                }
            }
    
    async def analyze_performance(self, user_id: str) -> Dict[str, Any]:
        """
        Analyze past content performance
        
        Args:
            user_id: User ID
        
        Returns:
            Performance analysis results
        """
        try:
            # Import performance learner
            from agents.performance_learner import PerformanceLearner
            learner = PerformanceLearner(self.supabase, self.openai_client)
            
            return await learner.analyze_user_performance(user_id)
            
        except Exception as e:
            logger.error(f"Error analyzing performance: {e}")
            return {"error": str(e)}
    
    async def get_personalized_recommendations(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get personalized content recommendations
        
        Args:
            user_id: User ID
        
        Returns:
            Personalized recommendations
        """
        try:
            # Import personalization engine
            from agents.personalization_engine import PersonalizationEngine
            engine = PersonalizationEngine(
                self.supabase,
                self.openai_client
            )
            
            return await engine.get_recommendations(user_id)
            
        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            return {"error": str(e)}

