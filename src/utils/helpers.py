"""
Utility helper functions for the XHS Auto-Publisher.
"""
import re
import hashlib
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime
from loguru import logger


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing invalid characters.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename safe for filesystem use
    """
    # Remove/replace invalid characters
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '_', filename)

    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip('. ')

    # Limit length
    if len(sanitized) > 200:
        sanitized = sanitized[:200]

    # Ensure not empty
    if not sanitized:
        sanitized = 'unnamed'

    return sanitized


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def format_datetime(dt: Optional[datetime], format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format a datetime object to string.

    Args:
        dt: Datetime object
        format_str: Format string

    Returns:
        Formatted string or empty string if dt is None
    """
    if dt is None:
        return ""
    return dt.strftime(format_str)


def parse_datetime(dt_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> Optional[datetime]:
    """
    Parse a datetime string.

    Args:
        dt_str: Datetime string
        format_str: Format string

    Returns:
        Datetime object or None if parsing fails
    """
    try:
        return datetime.strptime(dt_str, format_str)
    except (ValueError, TypeError):
        return None


def generate_content_hash(title: str, body: str) -> str:
    """
    Generate a hash for content to detect duplicates.

    Args:
        title: Content title
        body: Content body

    Returns:
        MD5 hash string
    """
    combined = f"{title}:{body}"
    return hashlib.md5(combined.encode('utf-8')).hexdigest()


def split_into_paragraphs(text: str, min_length: int = 10) -> List[str]:
    """
    Split text into paragraphs.

    Args:
        text: Text to split
        min_length: Minimum paragraph length to include

    Returns:
        List of paragraphs
    """
    # Split by double newlines or single newlines
    paragraphs = re.split(r'\n\s*\n|\n', text)

    # Filter out short/empty paragraphs
    return [p.strip() for p in paragraphs if len(p.strip()) >= min_length]


def get_image_extension(filename: str) -> str:
    """
    Get the image extension from filename.

    Args:
        filename: Image filename

    Returns:
        Lowercase extension without dot, or empty string
    """
    path = Path(filename)
    return path.suffix.lower().lstrip('.')


def is_valid_image(filename: str) -> bool:
    """
    Check if file is a valid image by extension.

    Args:
        filename: Filename to check

    Returns:
        True if valid image extension
    """
    valid_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'}
    ext = get_image_extension(filename)
    return ext in valid_extensions


def validate_content(title: str, body: str) -> Tuple[bool, str]:
    """
    Validate content before publishing.

    Args:
        title: Content title
        body: Content body

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check title
    if not title or len(title.strip()) == 0:
        return False, "Title cannot be empty"

    if len(title) > 100:
        return False, "Title too long (max 100 characters)"

    # Check body
    if not body or len(body.strip()) == 0:
        return False, "Body cannot be empty"

    if len(body) > 10000:
        return False, "Body too long (max 10000 characters)"

    # Check for spam patterns (basic)
    spam_patterns = [
        r'(.)\1{10,}',  # Same character repeated 10+ times
        r'[\u0000-\u001F]',  # Control characters
    ]

    for pattern in spam_patterns:
        if re.search(pattern, title + body):
            return False, "Content contains invalid patterns"

    return True, ""


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string like "1.5 MB"
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def retry_on_exception(
    func,
    max_retries: int = 3,
    delay: float = 1.0,
    exceptions: Tuple = (Exception,),
    on_retry=None,
):
    """
    Retry a function on exception.

    Args:
        func: Function to call
        max_retries: Maximum retry attempts
        delay: Delay between retries in seconds
        exceptions: Tuple of exceptions to catch
        on_retry: Callback function called on each retry (receives attempt number)

    Returns:
        Function result

    Raises:
        Last exception if all retries fail
    """
    import time

    last_exception = None

    for attempt in range(1, max_retries + 1):
        try:
            return func()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                if on_retry:
                    on_retry(attempt)
                logger.warning(f"Attempt {attempt} failed: {e}, retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"All {max_retries} attempts failed")

    raise last_exception


def extract_hashtags(text: str) -> List[str]:
    """
    Extract hashtags from text.

    Args:
        text: Text containing hashtags

    Returns:
        List of hashtags (without # symbol)
    """
    pattern = r'#(\w+)'
    return re.findall(pattern, text)


def add_hashtags(text: str, hashtags: List[str]) -> str:
    """
    Add hashtags to the end of text.

    Args:
        text: Original text
        hashtags: List of hashtags to add (with or without #)

    Returns:
        Text with hashtags appended
    """
    # Clean hashtags (ensure single #)
    cleaned = []
    for tag in hashtags:
        tag = tag.strip().lstrip('#')
        if tag:
            cleaned.append(f"#{tag}")

    if not cleaned:
        return text

    # Add hashtags on new line
    return text.rstrip() + "\n\n" + " ".join(cleaned)


def estimate_read_time(text: str, words_per_minute: int = 200) -> int:
    """
    Estimate reading time in minutes.

    Args:
        text: Text content
        words_per_minute: Average reading speed

    Returns:
        Estimated minutes (minimum 1)
    """
    # Count words (Chinese characters count as 2 words)
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    other_words = len(re.findall(r'\b[a-zA-Z]+\b', text))

    total_words = chinese_chars * 0.5 + other_words
    minutes = max(1, int(total_words / words_per_minute))

    return minutes
