"""
Database models and operations for content management.
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from enum import Enum
import json


class ContentStatus(str, Enum):
    """Content status enum."""
    PENDING = "pending"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"
    FAILED = "failed"


class ContentSource(str, Enum):
    """Content source enum."""
    MANUAL = "manual"
    FETCHED = "fetched"


class PublishMode(str, Enum):
    """Xiaohongshu publish mode enum."""
    IMAGE_TEXT_UPLOAD = "image_text_upload"  # 上传图文 - 上传图片 (images first)
    IMAGE_TEXT_COMPOSE = "image_text_compose"  # 上传图文 - 文字配图 (text first)
    LONG_ARTICLE = "long_article"  # 写长文


class Content:
    """Content model."""
    
    def __init__(
        self,
        id: Optional[int] = None,
        title: str = "",
        body: str = "",
        images: Optional[List[str]] = None,
        source: ContentSource = ContentSource.MANUAL,
        status: ContentStatus = ContentStatus.PENDING,
        publish_mode: PublishMode = PublishMode.IMAGE_TEXT_UPLOAD,
        created_at: Optional[datetime] = None,
        published_at: Optional[datetime] = None,
        error_message: Optional[str] = None,
    ):
        self.id = id
        self.title = title
        self.body = body
        self.images = images or []
        self.source = source
        self.status = status
        self.publish_mode = publish_mode
        self.created_at = created_at or datetime.now()
        self.published_at = published_at
        self.error_message = error_message

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "images": self.images,
            "source": self.source.value,
            "status": self.status.value,
            "publish_mode": self.publish_mode.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "error_message": self.error_message,
        }

    @classmethod
    def from_row(cls, row) -> "Content":
        """Create Content from database row (sqlite3.Row or tuple)."""
        # Use column names if available (sqlite3.Row), otherwise use indexes
        # This handles both old and new schemas correctly

        def get_value(row, name: str, index: int, default=None):
            """Get value by column name or index."""
            try:
                # Try column name first (sqlite3.Row)
                return row[name]
            except (KeyError, TypeError):
                # Fall back to index (tuple)
                try:
                    return row[index] if len(row) > index else default
                except (TypeError, IndexError):
                    return default

        # Parse publish_mode with fallback
        publish_mode_str = get_value(row, 'publish_mode', 6)
        try:
            publish_mode = PublishMode(publish_mode_str) if publish_mode_str else PublishMode.IMAGE_TEXT_UPLOAD
        except (ValueError, KeyError):
            publish_mode = PublishMode.IMAGE_TEXT_UPLOAD

        # Parse created_at
        created_at_str = get_value(row, 'created_at', 7)
        created_at = None
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str)
            except (ValueError, TypeError):
                pass

        # Parse published_at
        published_at_str = get_value(row, 'published_at', 8)
        published_at = None
        if published_at_str:
            try:
                published_at = datetime.fromisoformat(published_at_str)
            except (ValueError, TypeError):
                pass

        # Parse images
        images_str = get_value(row, 'images', 3)
        try:
            images = json.loads(images_str) if images_str else []
        except (json.JSONDecodeError, TypeError):
            images = []

        return cls(
            id=get_value(row, 'id', 0),
            title=get_value(row, 'title', 1, ""),
            body=get_value(row, 'body', 2, ""),
            images=images,
            source=ContentSource(get_value(row, 'source', 4, ContentSource.MANUAL.value)),
            status=ContentStatus(get_value(row, 'status', 5, ContentStatus.PENDING.value)),
            publish_mode=publish_mode,
            created_at=created_at,
            published_at=published_at,
            error_message=get_value(row, 'error_message', 9),
        )


class Database:
    """Database manager for content storage."""
    
    def __init__(self, db_path: str = "data/xhs.db"):
        self.db_path = db_path
        self._ensure_db_exists()
        self._init_schema()
    
    def _ensure_db_exists(self):
        """Ensure database directory exists."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_schema(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS content (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    images TEXT,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    publish_mode TEXT DEFAULT 'image_text_upload',
                    created_at TIMESTAMP NOT NULL,
                    published_at TIMESTAMP,
                    error_message TEXT
                )
            """)
            
            # Add publish_mode column if it doesn't exist (migration for existing databases)
            try:
                conn.execute("ALTER TABLE content ADD COLUMN publish_mode TEXT DEFAULT 'image_text_upload'")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Create indexes for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status 
                ON content(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at 
                ON content(created_at DESC)
            """)
            conn.commit()
    
    def create_content(self, content: Content) -> int:
        """Create new content entry."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO content (title, body, images, source, status, publish_mode, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                content.title,
                content.body,
                json.dumps(content.images),
                content.source.value,
                content.status.value,
                content.publish_mode.value,
                content.created_at.isoformat(),
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_content(self, content_id: int) -> Optional[Content]:
        """Get content by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM content WHERE id = ?", (content_id,))
            row = cursor.fetchone()
            return Content.from_row(row) if row else None
    
    def get_all_content(
        self,
        status: Optional[ContentStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Content]:
        """Get all content, optionally filtered by status."""
        with self._get_connection() as conn:
            if status:
                cursor = conn.execute("""
                    SELECT * FROM content 
                    WHERE status = ? 
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                """, (status.value, limit, offset))
            else:
                cursor = conn.execute("""
                    SELECT * FROM content 
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                """, (limit, offset))
            
            return [Content.from_row(row) for row in cursor.fetchall()]
    
    def update_status(
        self,
        content_id: int,
        status: ContentStatus,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update content status."""
        with self._get_connection() as conn:
            published_at = datetime.now().isoformat() if status == ContentStatus.PUBLISHED else None
            conn.execute("""
                UPDATE content 
                SET status = ?, published_at = ?, error_message = ?
                WHERE id = ?
            """, (status.value, published_at, error_message, content_id))
            conn.commit()
            return conn.total_changes > 0
    
    def delete_content(self, content_id: int) -> bool:
        """Delete content by ID."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM content WHERE id = ?", (content_id,))
            conn.commit()
            return conn.total_changes > 0
    
    def get_stats(self) -> dict:
        """Get content statistics."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT status, COUNT(*) as count 
                FROM content 
                GROUP BY status
            """)
            stats = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Get today's published count
            cursor = conn.execute("""
                SELECT COUNT(*) FROM content 
                WHERE status = ? AND DATE(published_at) = DATE('now')
            """, (ContentStatus.PUBLISHED.value,))
            stats['today_published'] = cursor.fetchone()[0]
            
            return stats
