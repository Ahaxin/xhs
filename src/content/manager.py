"""
Content manager for handling content operations.
"""
from typing import List, Optional
from .database import Database, Content, ContentStatus, ContentSource, PublishMode
from loguru import logger


class ContentManager:
    """Manages content creation, approval, and publishing workflow."""

    def __init__(self, db: Database):
        self.db = db

    def create_content(
        self,
        title: str,
        body: str,
        images: Optional[List[str]] = None,
        source: ContentSource = ContentSource.MANUAL,
        publish_mode: PublishMode = PublishMode.IMAGE_TEXT_UPLOAD,
    ) -> int:
        """Create new content entry."""
        content = Content(
            title=title,
            body=body,
            images=images or [],
            source=source,
            status=ContentStatus.PENDING,
            publish_mode=publish_mode,
        )
        content_id = self.db.create_content(content)
        logger.info(f"Created content #{content_id}: {title[:50]}... (mode: {publish_mode.value})")
        return content_id
    
    def get_pending_content(self) -> List[Content]:
        """Get all pending content for approval."""
        return self.db.get_all_content(status=ContentStatus.PENDING)
    
    def get_approved_content(self) -> List[Content]:
        """Get all approved content ready for publishing."""
        return self.db.get_all_content(status=ContentStatus.APPROVED)
    
    def approve_content(self, content_id: int) -> bool:
        """Approve content for publishing."""
        success = self.db.update_status(content_id, ContentStatus.APPROVED)
        if success:
            logger.info(f"Approved content #{content_id}")
        return success
    
    def reject_content(self, content_id: int, reason: str = "") -> bool:
        """Reject content."""
        success = self.db.update_status(
            content_id,
            ContentStatus.REJECTED,
            error_message=reason,
        )
        if success:
            logger.info(f"Rejected content #{content_id}: {reason}")
        return success
    
    def mark_published(self, content_id: int) -> bool:
        """Mark content as published."""
        success = self.db.update_status(content_id, ContentStatus.PUBLISHED)
        if success:
            logger.info(f"Marked content #{content_id} as published")
        return success
    
    def mark_failed(self, content_id: int, error: str) -> bool:
        """Mark content as failed to publish."""
        success = self.db.update_status(
            content_id,
            ContentStatus.FAILED,
            error_message=error,
        )
        if success:
            logger.error(f"Content #{content_id} failed: {error}")
        return success
    
    def get_content(self, content_id: int) -> Optional[Content]:
        """Get content by ID."""
        return self.db.get_content(content_id)
    
    def get_all_content(self, limit: int = 100, offset: int = 0) -> List[Content]:
        """Get all content."""
        return self.db.get_all_content(limit=limit, offset=offset)
    
    def delete_content(self, content_id: int) -> bool:
        """Delete content."""
        success = self.db.delete_content(content_id)
        if success:
            logger.info(f"Deleted content #{content_id}")
        return success
    
    def get_stats(self) -> dict:
        """Get content statistics."""
        return self.db.get_stats()
    
    def can_publish_today(self, max_posts: int = 3) -> bool:
        """Check if we can publish more content today."""
        stats = self.get_stats()
        today_count = stats.get('today_published', 0)
        return today_count < max_posts
