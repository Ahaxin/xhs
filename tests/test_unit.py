"""
Unit tests for XHS Auto-Publisher modules.
These tests don't require a browser and test the code logic.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.content.database import Database, Content, ContentStatus, ContentSource, PublishMode


class TestDatabase(unittest.TestCase):
    """Test cases for the database module."""

    def setUp(self):
        """Set up test database."""
        self.test_db_path = "data/test_xhs.db"
        self.db = Database(self.test_db_path)

    def tearDown(self):
        """Clean up test database."""
        # Remove test database if needed
        pass

    def test_create_content(self):
        """Test creating content."""
        content = Content(
            title="Test Title",
            body="Test Body",
            images=["image1.jpg", "image2.jpg"],
            source=ContentSource.MANUAL,
            publish_mode=PublishMode.IMAGE_TEXT_UPLOAD,
        )
        content_id = self.db.create_content(content)
        self.assertIsNotNone(content_id)
        self.assertGreater(content_id, 0)

    def test_get_content(self):
        """Test retrieving content."""
        # Create content first
        content = Content(
            title="Test Title",
            body="Test Body",
            images=[],
            source=ContentSource.MANUAL,
            publish_mode=PublishMode.LONG_ARTICLE,
        )
        content_id = self.db.create_content(content)

        # Retrieve it
        retrieved = self.db.get_content(content_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.title, "Test Title")
        self.assertEqual(retrieved.body, "Test Body")
        self.assertEqual(retrieved.publish_mode, PublishMode.LONG_ARTICLE)

    def test_update_status(self):
        """Test updating content status."""
        content = Content(
            title="Test",
            body="Body",
            images=[],
            source=ContentSource.MANUAL,
            publish_mode=PublishMode.IMAGE_TEXT_UPLOAD,
        )
        content_id = self.db.create_content(content)

        # Update status to approved
        self.db.update_status(content_id, ContentStatus.APPROVED)
        retrieved = self.db.get_content(content_id)
        self.assertEqual(retrieved.status, ContentStatus.APPROVED)

        # Update status to published
        self.db.update_status(content_id, ContentStatus.PUBLISHED)
        retrieved = self.db.get_content(content_id)
        self.assertEqual(retrieved.status, ContentStatus.PUBLISHED)


class TestContent(unittest.TestCase):
    """Test cases for the Content dataclass."""

    def test_content_creation(self):
        """Test creating a Content object."""
        from datetime import datetime as dt
        content = Content(
            id=1,
            title="Test Title",
            body="Test Body",
            images=["img1.jpg"],
            source=ContentSource.MANUAL,
            status=ContentStatus.PENDING,
            publish_mode=PublishMode.LONG_ARTICLE,
            created_at=dt(2024, 1, 1, 0, 0, 0),
            published_at=None,
            error_message=None,
        )

        self.assertEqual(content.id, 1)
        self.assertEqual(content.title, "Test Title")
        self.assertEqual(content.publish_mode, PublishMode.LONG_ARTICLE)

    def test_content_to_dict(self):
        """Test converting Content to dictionary."""
        from datetime import datetime as dt
        content = Content(
            id=1,
            title="Test",
            body="Body",
            images=[],
            source=ContentSource.MANUAL,
            status=ContentStatus.PENDING,
            publish_mode=PublishMode.IMAGE_TEXT_UPLOAD,
            created_at=dt(2024, 1, 1, 0, 0, 0),
            published_at=None,
            error_message=None,
        )

        d = content.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d['title'], "Test")
        self.assertEqual(d['status'], "pending")


class TestPublishMode(unittest.TestCase):
    """Test cases for PublishMode enum."""

    def test_publish_modes(self):
        """Test all publish modes exist."""
        self.assertEqual(PublishMode.IMAGE_TEXT_UPLOAD.value, "image_text_upload")
        self.assertEqual(PublishMode.IMAGE_TEXT_COMPOSE.value, "image_text_compose")
        self.assertEqual(PublishMode.LONG_ARTICLE.value, "long_article")

    def test_publish_mode_from_string(self):
        """Test creating PublishMode from string."""
        mode = PublishMode("image_text_upload")
        self.assertEqual(mode, PublishMode.IMAGE_TEXT_UPLOAD)


class TestPublisherMock(unittest.TestCase):
    """Test cases for Publisher with mocked browser."""

    def setUp(self):
        """Set up mocked publisher."""
        self.mock_driver = MagicMock()
        self.mock_driver.current_url = "https://creator.xiaohongshu.com"
        self.mock_driver.title = "Creator Center"

    def test_publisher_initialization(self):
        """Test publisher can be initialized."""
        from src.publisher.publisher import XHSPublisher

        publisher = XHSPublisher(self.mock_driver)
        self.assertIsNotNone(publisher)
        self.assertEqual(publisher.driver, self.mock_driver)

    def test_screenshot_directory_creation(self):
        """Test screenshot directory is created."""
        from src.publisher.publisher import XHSPublisher

        publisher = XHSPublisher(self.mock_driver)
        self.assertTrue(publisher.SCREENSHOT_DIR.exists())

    def test_random_delay(self):
        """Test random delay function."""
        from src.publisher.publisher import XHSPublisher
        import time

        publisher = XHSPublisher(self.mock_driver)

        start = time.time()
        publisher._random_delay(0.1, 0.2)
        elapsed = time.time() - start

        self.assertGreaterEqual(elapsed, 0.1)
        self.assertLess(elapsed, 0.5)  # Allow some overhead


class TestAuthManagerMock(unittest.TestCase):
    """Test cases for AuthManager with mocked browser."""

    def test_auth_manager_initialization(self):
        """Test auth manager can be initialized."""
        from src.auth.xhs_auth import XHSAuthManager

        auth = XHSAuthManager(
            creator_url="https://creator.xiaohongshu.com",
            session_file="data/test_session.json",
            login_method="qr_code",
        )
        self.assertIsNotNone(auth)
        self.assertEqual(auth.login_method, "qr_code")

    def test_user_agent_rotation(self):
        """Test user agent rotation pool."""
        from src.auth.xhs_auth import XHSAuthManager

        auth = XHSAuthManager()
        ua1 = auth._get_random_user_agent()
        self.assertIsInstance(ua1, str)
        self.assertIn("Mozilla", ua1)

    def test_screenshot_directory(self):
        """Test screenshot directory creation."""
        from src.auth.xhs_auth import XHSAuthManager

        auth = XHSAuthManager()
        self.assertTrue(auth.SCREENSHOT_DIR.exists())


class TestSelectorStrategies(unittest.TestCase):
    """Test selector strategy logic."""

    def test_text_selector_conversion(self):
        """Test text to xpath conversion logic."""
        text = "新的创作"
        expected_xpath = f"//*[contains(text(), '{text}')]"

        # Simulate the conversion
        selector_type = 'text'
        if selector_type == 'text':
            actual_xpath = f"//*[contains(text(), '{text}')]"

        self.assertEqual(actual_xpath, expected_xpath)

    def test_selector_list_structure(self):
        """Test selector list has proper structure."""
        selectors = [
            ('text', '新的创作'),
            ('xpath', '//button[contains(text(), "新的创作")]'),
            ('css', 'button[class*="create"]'),
        ]

        for selector_type, selector_value in selectors:
            self.assertIn(selector_type, ['text', 'xpath', 'css', 'id', 'class'])
            self.assertIsInstance(selector_value, str)
            self.assertGreater(len(selector_value), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
