"""
Unit tests for the ContentManager module.
"""
import sys
import unittest
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.content.database import Database, Content, ContentStatus, ContentSource, PublishMode
from src.content.manager import ContentManager


class TestContentManager(unittest.TestCase):
    """Test cases for ContentManager."""

    def setUp(self):
        """Set up test database and manager."""
        self.test_db_path = "data/test_manager.db"
        self.db = Database(self.test_db_path)
        self.manager = ContentManager(self.db)

    def test_create_content(self):
        """Test creating content through manager."""
        content_id = self.manager.create_content(
            title="Manager Test",
            body="Test body content",
            images=[],
        )
        self.assertIsNotNone(content_id)
        self.assertGreater(content_id, 0)

    def test_validate_and_create_valid(self):
        """Test validate_and_create with valid content."""
        content_id, error = self.manager.validate_and_create(
            title="Valid Title",
            body="Valid body content that is long enough",
            check_duplicates=False,
        )
        self.assertIsNotNone(content_id)
        self.assertEqual(error, "")

    def test_validate_and_create_empty_title(self):
        """Test validate_and_create with empty title."""
        content_id, error = self.manager.validate_and_create(
            title="",
            body="Some body content",
        )
        self.assertIsNone(content_id)
        self.assertIn("Title", error)

    def test_validate_and_create_empty_body(self):
        """Test validate_and_create with empty body."""
        content_id, error = self.manager.validate_and_create(
            title="Some Title",
            body="",
        )
        self.assertIsNone(content_id)
        self.assertIn("Body", error)

    def test_approve_content(self):
        """Test approving content."""
        content_id = self.manager.create_content(
            title="To Approve",
            body="Content to approve",
        )

        success = self.manager.approve_content(content_id)
        self.assertTrue(success)

        content = self.manager.get_content(content_id)
        self.assertEqual(content.status, ContentStatus.APPROVED)

    def test_reject_content(self):
        """Test rejecting content."""
        content_id = self.manager.create_content(
            title="To Reject",
            body="Content to reject",
        )

        success = self.manager.reject_content(content_id, "Test rejection")
        self.assertTrue(success)

        content = self.manager.get_content(content_id)
        self.assertEqual(content.status, ContentStatus.REJECTED)

    def test_mark_published(self):
        """Test marking content as published."""
        content_id = self.manager.create_content(
            title="To Publish",
            body="Content to publish",
        )
        self.manager.approve_content(content_id)

        success = self.manager.mark_published(content_id)
        self.assertTrue(success)

        content = self.manager.get_content(content_id)
        self.assertEqual(content.status, ContentStatus.PUBLISHED)

    def test_mark_failed(self):
        """Test marking content as failed."""
        content_id = self.manager.create_content(
            title="To Fail",
            body="Content that will fail",
        )

        success = self.manager.mark_failed(content_id, "Test failure")
        self.assertTrue(success)

        content = self.manager.get_content(content_id)
        self.assertEqual(content.status, ContentStatus.FAILED)
        self.assertEqual(content.error_message, "Test failure")

    def test_get_pending_content(self):
        """Test getting pending content."""
        # Create some pending content
        self.manager.create_content(title="Pending 1", body="Body 1")
        self.manager.create_content(title="Pending 2", body="Body 2")

        pending = self.manager.get_pending_content()
        self.assertIsInstance(pending, list)
        # Should have at least the 2 we created (might have more from other tests)
        self.assertGreaterEqual(len(pending), 2)

    def test_get_stats(self):
        """Test getting content statistics."""
        stats = self.manager.get_stats()
        self.assertIsInstance(stats, dict)
        self.assertIn('today_published', stats)

    def test_can_publish_today(self):
        """Test daily publishing limit check."""
        can_publish = self.manager.can_publish_today(max_posts=100)
        self.assertTrue(can_publish)  # Should be true with high limit

    def test_retry_failed_content(self):
        """Test retrying failed content."""
        content_id = self.manager.create_content(
            title="To Retry",
            body="Content to retry",
        )
        self.manager.mark_failed(content_id, "Initial failure")

        success = self.manager.retry_failed_content(content_id)
        self.assertTrue(success)

        content = self.manager.get_content(content_id)
        self.assertEqual(content.status, ContentStatus.APPROVED)

    def test_delete_content(self):
        """Test deleting content."""
        content_id = self.manager.create_content(
            title="To Delete",
            body="Content to delete",
        )

        success = self.manager.delete_content(content_id)
        self.assertTrue(success)

        content = self.manager.get_content(content_id)
        self.assertIsNone(content)

    def test_search_content(self):
        """Test searching content."""
        self.manager.create_content(
            title="Searchable Title",
            body="Searchable body content",
        )

        results = self.manager.search_content("Searchable")
        self.assertGreaterEqual(len(results), 1)

    def test_bulk_approve(self):
        """Test bulk approving content."""
        ids = []
        for i in range(3):
            content_id = self.manager.create_content(
                title=f"Bulk Test {i}",
                body=f"Bulk test body {i}",
            )
            ids.append(content_id)

        count = self.manager.bulk_approve(ids)
        self.assertEqual(count, 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
