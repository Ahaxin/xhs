"""
Content manager for handling content operations.
Enhanced with content validation and duplicate detection.
"""
from typing import List, Optional, Tuple
from .database import Database, Content, ContentStatus, ContentSource, PublishMode
from ..utils.helpers import validate_content, generate_content_hash, is_valid_image
from loguru import logger


class ContentManager:
    """Manages content creation, approval, and publishing workflow."""

    def __init__(self, db: Database):
        self.db = db
        self._content_hashes: set = set()  # Cache for duplicate detection
        self._load_content_hashes()

    def _load_content_hashes(self):
        """Load existing content hashes for duplicate detection."""
        try:
            all_content = self.db.get_all_content(limit=1000)
            for content in all_content:
                hash_val = generate_content_hash(content.title, content.body)
                self._content_hashes.add(hash_val)
            logger.debug(f"Loaded {len(self._content_hashes)} content hashes")
        except Exception as e:
            logger.warning(f"Could not load content hashes: {e}")

    def validate_and_create(
        self,
        title: str,
        body: str,
        images: Optional[List[str]] = None,
        source: ContentSource = ContentSource.MANUAL,
        publish_mode: PublishMode = PublishMode.IMAGE_TEXT_UPLOAD,
        check_duplicates: bool = True,
    ) -> Tuple[Optional[int], str]:
        """
        Validate and create new content entry.

        Args:
            title: Content title
            body: Content body
            images: List of image paths
            source: Content source
            publish_mode: Publishing mode
            check_duplicates: Whether to check for duplicates

        Returns:
            Tuple of (content_id or None, error_message)
        """
        # Validate content
        is_valid, error = validate_content(title, body)
        if not is_valid:
            logger.warning(f"Content validation failed: {error}")
            return None, error

        # Validate images if provided
        if images:
            for img in images:
                if not is_valid_image(img):
                    error = f"Invalid image file: {img}"
                    logger.warning(error)
                    return None, error

        # Check for duplicates
        if check_duplicates:
            content_hash = generate_content_hash(title, body)
            if content_hash in self._content_hashes:
                error = "Duplicate content detected"
                logger.warning(error)
                return None, error

        # Create content
        try:
            content_id = self.create_content(
                title=title,
                body=body,
                images=images,
                source=source,
                publish_mode=publish_mode,
            )

            # Update hash cache
            content_hash = generate_content_hash(title, body)
            self._content_hashes.add(content_hash)

            return content_id, ""
        except Exception as e:
            error = f"Failed to create content: {str(e)}"
            logger.error(error)
            return None, error

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
        # Get content before deletion for hash removal
        content = self.db.get_content(content_id)
        success = self.db.delete_content(content_id)
        if success:
            logger.info(f"Deleted content #{content_id}")
            # Remove from hash cache
            if content:
                content_hash = generate_content_hash(content.title, content.body)
                self._content_hashes.discard(content_hash)
        return success

    def get_stats(self) -> dict:
        """Get content statistics."""
        return self.db.get_stats()

    def can_publish_today(self, max_posts: int = 3) -> bool:
        """Check if we can publish more content today."""
        stats = self.get_stats()
        today_count = stats.get('today_published', 0)
        return today_count < max_posts

    def get_publishable_content(self, limit: int = 10) -> List[Content]:
        """
        Get content that is ready to be published.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of approved content ready for publishing
        """
        approved = self.get_approved_content()
        return approved[:limit]

    def retry_failed_content(self, content_id: int) -> bool:
        """
        Reset a failed content back to approved status for retry.

        Args:
            content_id: Content ID to retry

        Returns:
            True if successful
        """
        content = self.get_content(content_id)
        if not content or content.status != ContentStatus.FAILED:
            return False

        success = self.db.update_status(content_id, ContentStatus.APPROVED)
        if success:
            logger.info(f"Reset content #{content_id} for retry")
        return success

    def bulk_approve(self, content_ids: List[int]) -> int:
        """
        Approve multiple content items.

        Args:
            content_ids: List of content IDs to approve

        Returns:
            Number of successfully approved items
        """
        count = 0
        for content_id in content_ids:
            if self.approve_content(content_id):
                count += 1
        logger.info(f"Bulk approved {count}/{len(content_ids)} items")
        return count

    def search_content(self, query: str, limit: int = 50) -> List[Content]:
        """
        Search content by title or body.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            Matching content items
        """
        all_content = self.get_all_content(limit=500)  # Get more for searching
        query_lower = query.lower()

        results = []
        for content in all_content:
            if query_lower in content.title.lower() or query_lower in content.body.lower():
                results.append(content)
                if len(results) >= limit:
                    break

        return results
