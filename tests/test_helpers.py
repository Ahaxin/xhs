"""
Unit tests for the helpers module.
"""
import sys
import unittest
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.helpers import (
    sanitize_filename,
    truncate_text,
    format_datetime,
    parse_datetime,
    generate_content_hash,
    split_into_paragraphs,
    is_valid_image,
    validate_content,
    format_file_size,
    extract_hashtags,
    add_hashtags,
    estimate_read_time,
)


class TestSanitizeFilename(unittest.TestCase):
    """Test cases for sanitize_filename."""

    def test_normal_filename(self):
        """Test with normal filename."""
        self.assertEqual(sanitize_filename("test.txt"), "test.txt")

    def test_invalid_characters(self):
        """Test removal of invalid characters."""
        self.assertEqual(sanitize_filename("file<>:name.txt"), "file___name.txt")

    def test_empty_result(self):
        """Test empty input becomes 'unnamed'."""
        self.assertEqual(sanitize_filename(""), "unnamed")

    def test_long_filename(self):
        """Test truncation of long filename."""
        long_name = "a" * 250
        result = sanitize_filename(long_name)
        self.assertLessEqual(len(result), 200)


class TestTruncateText(unittest.TestCase):
    """Test cases for truncate_text."""

    def test_short_text(self):
        """Test text shorter than limit."""
        self.assertEqual(truncate_text("short", 10), "short")

    def test_long_text(self):
        """Test text longer than limit."""
        result = truncate_text("this is a long text", 10)
        self.assertEqual(len(result), 10)
        self.assertTrue(result.endswith("..."))

    def test_custom_suffix(self):
        """Test with custom suffix."""
        result = truncate_text("long text here", 10, suffix="…")
        self.assertTrue(result.endswith("…"))


class TestDatetimeFunctions(unittest.TestCase):
    """Test cases for datetime functions."""

    def test_format_datetime(self):
        """Test datetime formatting."""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = format_datetime(dt)
        self.assertEqual(result, "2024-01-15 10:30:00")

    def test_format_datetime_none(self):
        """Test with None input."""
        self.assertEqual(format_datetime(None), "")

    def test_parse_datetime(self):
        """Test datetime parsing."""
        result = parse_datetime("2024-01-15 10:30:00")
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 15)

    def test_parse_datetime_invalid(self):
        """Test with invalid input."""
        self.assertIsNone(parse_datetime("invalid"))


class TestGenerateContentHash(unittest.TestCase):
    """Test cases for generate_content_hash."""

    def test_same_content_same_hash(self):
        """Test same content produces same hash."""
        hash1 = generate_content_hash("title", "body")
        hash2 = generate_content_hash("title", "body")
        self.assertEqual(hash1, hash2)

    def test_different_content_different_hash(self):
        """Test different content produces different hash."""
        hash1 = generate_content_hash("title1", "body")
        hash2 = generate_content_hash("title2", "body")
        self.assertNotEqual(hash1, hash2)


class TestSplitIntoParagraphs(unittest.TestCase):
    """Test cases for split_into_paragraphs."""

    def test_double_newline_split(self):
        """Test splitting by double newlines."""
        text = "Paragraph 1.\n\nParagraph 2."
        result = split_into_paragraphs(text)
        self.assertEqual(len(result), 2)

    def test_filter_short_paragraphs(self):
        """Test filtering short paragraphs."""
        text = "Hi\n\nThis is a longer paragraph."
        result = split_into_paragraphs(text, min_length=5)
        self.assertEqual(len(result), 1)


class TestIsValidImage(unittest.TestCase):
    """Test cases for is_valid_image."""

    def test_valid_extensions(self):
        """Test valid image extensions."""
        self.assertTrue(is_valid_image("test.jpg"))
        self.assertTrue(is_valid_image("test.PNG"))
        self.assertTrue(is_valid_image("test.gif"))

    def test_invalid_extensions(self):
        """Test invalid image extensions."""
        self.assertFalse(is_valid_image("test.txt"))
        self.assertFalse(is_valid_image("test.pdf"))


class TestValidateContent(unittest.TestCase):
    """Test cases for validate_content."""

    def test_valid_content(self):
        """Test with valid content."""
        is_valid, error = validate_content("Test Title", "Test body content")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")

    def test_empty_title(self):
        """Test with empty title."""
        is_valid, error = validate_content("", "Body")
        self.assertFalse(is_valid)
        self.assertIn("Title", error)

    def test_empty_body(self):
        """Test with empty body."""
        is_valid, error = validate_content("Title", "")
        self.assertFalse(is_valid)
        self.assertIn("Body", error)

    def test_long_title(self):
        """Test with too long title."""
        long_title = "a" * 150
        is_valid, error = validate_content(long_title, "Body")
        self.assertFalse(is_valid)
        self.assertIn("long", error)


class TestFormatFileSize(unittest.TestCase):
    """Test cases for format_file_size."""

    def test_bytes(self):
        """Test bytes formatting."""
        self.assertEqual(format_file_size(500), "500.0 B")

    def test_kilobytes(self):
        """Test kilobytes formatting."""
        self.assertEqual(format_file_size(1024), "1.0 KB")

    def test_megabytes(self):
        """Test megabytes formatting."""
        self.assertEqual(format_file_size(1024 * 1024), "1.0 MB")


class TestHashtagFunctions(unittest.TestCase):
    """Test cases for hashtag functions."""

    def test_extract_hashtags(self):
        """Test hashtag extraction."""
        text = "Check out #Python and #coding today!"
        result = extract_hashtags(text)
        self.assertEqual(result, ["Python", "coding"])

    def test_add_hashtags(self):
        """Test adding hashtags."""
        text = "My post"
        result = add_hashtags(text, ["tag1", "#tag2"])
        self.assertIn("#tag1", result)
        self.assertIn("#tag2", result)


class TestEstimateReadTime(unittest.TestCase):
    """Test cases for estimate_read_time."""

    def test_short_text(self):
        """Test with short text."""
        result = estimate_read_time("Hello world")
        self.assertEqual(result, 1)

    def test_chinese_text(self):
        """Test with Chinese text."""
        # 100 Chinese characters
        text = "你好" * 50
        result = estimate_read_time(text)
        self.assertGreaterEqual(result, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
