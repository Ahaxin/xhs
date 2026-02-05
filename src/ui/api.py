"""
FastAPI backend for XHS auto-publishing agent.
"""
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
import shutil
import asyncio

from ..content.database import Database, Content, ContentStatus, ContentSource
from ..content.manager import ContentManager
from ..auth.xhs_auth import XHSAuthManager
from ..publisher.publisher import XHSPublisher
from ..utils.config import get_config
from ..utils.logger import setup_logging
from loguru import logger


# Initialize
config = get_config()
setup_logging(
    log_file=config.logging.file,
    level=config.logging.level,
    rotation=config.logging.rotation,
    retention=config.logging.retention,
)

db = Database(config.database.path)
content_manager = ContentManager(db)

# Global auth manager and publisher
auth_manager: Optional[XHSAuthManager] = None
publisher: Optional[XHSPublisher] = None

# Initialize auth manager on startup to restore session
def init_auth_manager():
    """Initialize auth manager and try to restore saved session."""
    global auth_manager, publisher
    try:
        auth_manager = XHSAuthManager(
            creator_url=config.xiaohongshu.creator_center_url,
            session_file=config.xiaohongshu.session_file,
            login_method=config.xiaohongshu.login_method,
            phone_number=config.xiaohongshu.phone_number,
        )
        # Try to restore session in background
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(_restore_session)
            # Don't wait for completion, let it run in background
    except Exception as e:
        logger.error(f"Error initializing auth manager: {e}")

def _restore_session():
    """Restore saved session if available."""
    global auth_manager, publisher
    try:
        if not auth_manager:
            return
        
        # Initialize browser
        auth_manager._init_browser(headless=True)
        
        # Try to load session
        if auth_manager._load_session():
            # Check if session is still valid
            if auth_manager.is_logged_in():
                logger.info("Session restored successfully")
                # Initialize publisher
                driver = auth_manager.get_driver()
                if driver:
                    publisher = XHSPublisher(driver)
                return True
            else:
                logger.info("Saved session expired")
        return False
    except Exception as e:
        logger.error(f"Error restoring session: {e}")
        return False

app = FastAPI(title="XHS Auto-Publishing Agent", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create uploads directory
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# Pydantic models
class ContentCreate(BaseModel):
    title: str
    body: str
    images: Optional[List[str]] = None


class ContentResponse(BaseModel):
    id: int
    title: str
    body: str
    images: List[str]
    source: str
    status: str
    created_at: str
    published_at: Optional[str]
    error_message: Optional[str]


class StatsResponse(BaseModel):
    total: int
    pending: int
    approved: int
    published: int
    rejected: int
    failed: int
    today_published: int


class LoginRequest(BaseModel):
    method: str  # "sms" or "qr_code"
    phone_number: Optional[str] = None
    verification_code: Optional[str] = None


# API Routes

@app.get("/")
async def root():
    """Serve the main UI."""
    return FileResponse("src/ui/index.html")


@app.get("/api/status")
async def get_status():
    """Get system status."""
    global auth_manager, publisher
    logged_in = False
    
    # Initialize auth manager if not already done
    if not auth_manager:
        init_auth_manager()
    
    if auth_manager and auth_manager.driver:
        # Run sync is_logged_in in thread pool
        import concurrent.futures
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(auth_manager.is_logged_in)
                logged_in = future.result(timeout=10)
                
                # Initialize publisher if logged in but publisher not set
                if logged_in and not publisher:
                    driver = auth_manager.get_driver()
                    if driver:
                        publisher = XHSPublisher(driver)
        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            logged_in = False
    
    return {
        "status": "running",
        "logged_in": logged_in,
        "config": {
            "login_method": config.xiaohongshu.login_method,
            "max_posts_per_day": config.publishing.max_posts_per_day,
            "mode": config.publishing.mode,
        }
    }


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats():
    """Get content statistics."""
    stats = content_manager.get_stats()
    return StatsResponse(
        total=sum(stats.get(s.value, 0) for s in ContentStatus),
        pending=stats.get(ContentStatus.PENDING.value, 0),
        approved=stats.get(ContentStatus.APPROVED.value, 0),
        published=stats.get(ContentStatus.PUBLISHED.value, 0),
        rejected=stats.get(ContentStatus.REJECTED.value, 0),
        failed=stats.get(ContentStatus.FAILED.value, 0),
        today_published=stats.get('today_published', 0),
    )


@app.post("/api/content/create")
async def create_content(
    title: str = Form(...),
    body: str = Form(...),
    images: List[UploadFile] = File(default=[]),
):
    """Create new content with optional images."""
    try:
        # Save uploaded images
        image_paths = []
        for image in images:
            if image.filename:
                file_path = UPLOAD_DIR / f"{int(asyncio.get_event_loop().time() * 1000)}_{image.filename}"
                with open(file_path, "wb") as f:
                    shutil.copyfileobj(image.file, f)
                image_paths.append(str(file_path.absolute()))
        
        # Create content
        content_id = content_manager.create_content(
            title=title,
            body=body,
            images=image_paths,
            source=ContentSource.MANUAL,
        )
        
        return {"success": True, "content_id": content_id}
    except Exception as e:
        logger.error(f"Error creating content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/content/pending", response_model=List[ContentResponse])
async def get_pending_content():
    """Get all pending content."""
    content_list = content_manager.get_pending_content()
    return [ContentResponse(**c.to_dict()) for c in content_list]


@app.get("/api/content/all", response_model=List[ContentResponse])
async def get_all_content(limit: int = 100, offset: int = 0):
    """Get all content."""
    content_list = content_manager.get_all_content(limit=limit, offset=offset)
    return [ContentResponse(**c.to_dict()) for c in content_list]


@app.get("/api/content/{content_id}", response_model=ContentResponse)
async def get_content(content_id: int):
    """Get content by ID."""
    content = content_manager.get_content(content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    return ContentResponse(**content.to_dict())


@app.post("/api/content/{content_id}/approve")
async def approve_content(content_id: int):
    """Approve content for publishing."""
    success = content_manager.approve_content(content_id)
    if not success:
        raise HTTPException(status_code=404, detail="Content not found")
    return {"success": True}


@app.post("/api/content/{content_id}/reject")
async def reject_content(content_id: int, reason: str = ""):
    """Reject content."""
    success = content_manager.reject_content(content_id, reason)
    if not success:
        raise HTTPException(status_code=404, detail="Content not found")
    return {"success": True}


@app.delete("/api/content/{content_id}")
async def delete_content(content_id: int):
    """Delete content."""
    success = content_manager.delete_content(content_id)
    if not success:
        raise HTTPException(status_code=404, detail="Content not found")
    return {"success": True}


@app.post("/api/auth/login")
async def login(request: LoginRequest):
    """Login to Xiaohongshu Creator Center."""
    global auth_manager, publisher
    
    try:
        # Reinitialize auth manager with requested method
        auth_manager = XHSAuthManager(
            creator_url=config.xiaohongshu.creator_center_url,
            session_file=config.xiaohongshu.session_file,
            login_method=request.method,
            phone_number=request.phone_number or config.xiaohongshu.phone_number,
        )
        
        # Run sync login in thread pool to avoid blocking
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(auth_manager.login, request.verification_code)
            success = future.result(timeout=180)  # 3 minute timeout
        
        if success:
            # Initialize publisher
            driver = auth_manager.get_driver()
            if driver:
                publisher = XHSPublisher(driver)
            logger.info("Login successful, session saved")
            return {"success": True, "message": "Login successful"}
        else:
            logger.warning("Login failed")
            return {"success": False, "message": "Login failed"}
            
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/publish/{content_id}")
async def publish_content(content_id: int):
    """Publish approved content to Xiaohongshu."""
    global publisher, auth_manager
    
    # Check if logged in
    if not auth_manager or not publisher:
        raise HTTPException(status_code=401, detail="Not logged in to Xiaohongshu")
    
    # Get content
    content = content_manager.get_content(content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    
    # Check if approved
    if content.status != ContentStatus.APPROVED:
        raise HTTPException(status_code=400, detail="Content not approved")
    
    # Check daily limit
    if not content_manager.can_publish_today(config.publishing.max_posts_per_day):
        raise HTTPException(status_code=429, detail="Daily publishing limit reached")
    
    try:
        # Publish with retry in thread pool
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                publisher.publish_with_retry,
                content,
                config.publishing.retry_attempts,
                config.publishing.retry_delay,
            )
            success = future.result(timeout=300)  # 5 minute timeout
        
        if success:
            content_manager.mark_published(content_id)
            return {"success": True, "message": "Content published successfully"}
        else:
            content_manager.mark_failed(content_id, "Publishing failed after retries")
            return {"success": False, "message": "Publishing failed"}
            
    except Exception as e:
        logger.error(f"Publishing error: {e}")
        content_manager.mark_failed(content_id, str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    global auth_manager
    if auth_manager:
        auth_manager.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=config.ui.host,
        port=config.ui.port,
        log_level="info",
    )
