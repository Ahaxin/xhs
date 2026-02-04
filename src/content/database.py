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
    def from_row(cls, row: tuple) -> "Content":
        """Create Content from database row."""
        # Handle both old schema (without publish_mode) and new schema
        publish_mode = PublishMode.IMAGE_TEXT_UPLOAD  # default
        if len(row) > 6:
            try:
                publish_mode = PublishMode(row[6]) if row[6] else PublishMode.IMAGE_TEXT_UPLOAD
            except:
                pass
        
        return cls(
            id=row[0],
            title=row[1],
            body=row[2],
            images=json.loads(row[3]) if row[3] else [],
            source=ContentSource(row[4]),
            status=ContentStatus(row[5]),
            publish_mode=publish_mode,
            created_at=datetime.fromisoformat(row[7]) if len(row) > 7 and row[7] else None,
            published_at=datetime.fromisoformat(row[8]) if len(row) > 8 and row[8] else None,
            error_message=row[9] if len(row) > 9 else None,
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
            except:
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
