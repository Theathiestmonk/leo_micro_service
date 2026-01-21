from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from dotenv import load_dotenv
from typing import Dict, Any, Optional
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import functions with error handling
try:
    from create_content import construct_create_content_payload, complete_create_content_payload, handle_create_content
    CREATE_CONTENT_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import create_content functions: {e}")
    CREATE_CONTENT_AVAILABLE = False

    # Mock functions
    async def construct_create_content_payload(data):
        return {"message": "construct_create_content_payload not available", "data": data}

    async def complete_create_content_payload(data):
        return {"message": "complete_create_content_payload not available", "data": data}

    async def handle_create_content(data):
        return {"message": "handle_create_content not available", "data": data}

# Initialize FastAPI app
app = FastAPI(
    title="Leo Micro Service - Content Creation API",
    description="AI-powered content creation and social media management service",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize ContentCreationAgent (commented out due to missing dependencies)
# content_agent = ContentCreationAgent(
#     supabase_url=os.getenv('SUPABASE_URL'),
#     supabase_key=os.getenv('SUPABASE_SERVICE_ROLE_KEY'),
#     openai_api_key=os.getenv('OPENAI_API_KEY')
# )

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Leo Micro Service - Content Creation API", "status": "running"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.post("/api/content/create")
async def create_content_endpoint(data: Dict[str, Any]):
    """Create content using the content creation agent"""
    try:
        # Mock response for now - ContentCreationAgent has missing dependencies
        user_id = data.get("user_id", "unknown")
        result = {
            "user_id": user_id,
            "message": "Content creation endpoint - ContentCreationAgent not fully configured",
            "status": "mock_response",
            "generated_at": "2024-01-20T12:00:00Z"
        }
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error creating content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/content/construct")
async def construct_content_endpoint(data: Dict[str, Any]):
    """Construct content using your existing function"""
    try:
        result = construct_create_content_payload(data)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error constructing content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/content/complete")
async def complete_content_endpoint(data: Dict[str, Any]):
    """Complete content using your existing function"""
    try:
        result = complete_create_content_payload(data)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error completing content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/content/handle")
async def handle_content_creation_endpoint(data: Dict[str, Any], background_tasks: BackgroundTasks):
    """Handle content creation using your existing function"""
    try:
        result = await handle_create_content(data)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error handling content creation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/calendar/generate")
async def generate_calendar_endpoint(data: Dict[str, Any]):
    """Generate content calendar for a user"""
    try:
        user_id = data.get("user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        # Mock calendar response for now
        calendar = [
            {
                "date": "2024-01-21",
                "platform": "Instagram",
                "topic": "Sample content topic",
                "content_type": "static_post",
                "status": "scheduled"
            },
            {
                "date": "2024-01-22",
                "platform": "LinkedIn",
                "topic": "Business growth tips",
                "content_type": "carousel",
                "status": "scheduled"
            }
        ]

        return {"success": True, "calendar": calendar}
    except Exception as e:
        logger.error(f"Error generating calendar: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )