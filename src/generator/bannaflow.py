"""
BannaFlow Integration Module.

Integrates with BannaFlow content generation app to automate:
1. Topic discovery
2. Content generation
3. Image selection
4. Importing generated content to local publisher

BannaFlow URL: https://bannaflow-xhs-homestay-automation-expert-1081139732426.us-west1.run.app/
"""
import json
import time
import random
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from loguru import logger


@dataclass
class GeneratedContent:
    """Represents content generated from BannaFlow."""
    title: str
    body: str
    tags: List[str]
    images: List[str]  # URLs or local paths
    topic: str
    generated_at: datetime
    source: str = "bannaflow"

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "body": self.body,
            "tags": self.tags,
            "images": self.images,
            "topic": self.topic,
            "generated_at": self.generated_at.isoformat(),
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GeneratedContent":
        return cls(
            title=data.get("title", ""),
            body=data.get("body", ""),
            tags=data.get("tags", []),
            images=data.get("images", []),
            topic=data.get("topic", ""),
            generated_at=datetime.fromisoformat(data.get("generated_at", datetime.now().isoformat())),
            source=data.get("source", "bannaflow"),
        )


class BannaFlowIntegration:
    """
    Integrates with BannaFlow for automated content generation.

    BannaFlow is a web-based content generation tool that uses AI to:
    - Discover trending topics
    - Generate XHS-optimized titles
    - Create engaging content
    - Suggest relevant images
    """

    BANNAFLOW_URL = "https://bannaflow-xhs-homestay-automation-expert-1081139732426.us-west1.run.app/"
    SCREENSHOT_DIR = Path("logs/screenshots/bannaflow")
    CONTENT_CACHE_DIR = Path("data/generated_content")

    # LocalStorage keys used by BannaFlow
    LS_PUBLISHED_HISTORY = "banna_published_history"
    LS_AI_PROVIDER = "banna_ai_provider"
    LS_CUSTOM_API_KEY = "banna_custom_api_key"

    def __init__(self, headless: bool = False):
        """
        Initialize BannaFlow integration.

        Args:
            headless: Run browser in headless mode (default: False for debugging)
        """
        self.driver: Optional[webdriver.Chrome] = None
        self.headless = headless

        # Ensure directories exist
        self.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        self.CONTENT_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Add random human-like delay."""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    def _take_screenshot(self, name: str) -> str:
        """Take a screenshot for debugging."""
        if not self.driver:
            return ""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{name}.png"
            filepath = self.SCREENSHOT_DIR / filename
            self.driver.save_screenshot(str(filepath))
            logger.info(f"Screenshot saved: {filepath}")
            return str(filepath)
        except Exception as e:
            logger.warning(f"Failed to save screenshot: {e}")
            return ""

    def _init_browser(self):
        """Initialize Chrome browser with appropriate settings."""
        chrome_options = Options()

        if self.headless:
            chrome_options.add_argument('--headless=new')

        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--lang=zh-CN')

        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)

        logger.info("BannaFlow browser initialized")

    def _ensure_browser(self):
        """Ensure browser is ready."""
        if not self.driver:
            self._init_browser()
        try:
            _ = self.driver.current_url
        except Exception:
            self._init_browser()

    def open_bannaflow(self) -> bool:
        """
        Open BannaFlow in browser.

        Returns:
            True if successfully opened
        """
        try:
            self._ensure_browser()
            self.driver.get(self.BANNAFLOW_URL)
            self._random_delay(2, 4)

            # Wait for page to load
            WebDriverWait(self.driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )

            logger.info(f"Opened BannaFlow: {self.driver.current_url}")
            self._take_screenshot("bannaflow_opened")
            return True

        except Exception as e:
            logger.error(f"Failed to open BannaFlow: {e}")
            self._take_screenshot("bannaflow_open_error")
            return False

    def get_published_history(self) -> List[Dict[str, Any]]:
        """
        Get published content history from BannaFlow's localStorage.

        Returns:
            List of published content items
        """
        if not self.driver:
            logger.warning("Browser not initialized")
            return []

        try:
            # Get localStorage data
            history_json = self.driver.execute_script(
                f"return localStorage.getItem('{self.LS_PUBLISHED_HISTORY}')"
            )

            if not history_json:
                logger.info("No published history in BannaFlow")
                return []

            history = json.loads(history_json)
            logger.info(f"Retrieved {len(history)} items from BannaFlow history")
            return history

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse BannaFlow history: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to get BannaFlow history: {e}")
            return []

    def set_api_provider(self, provider: str, api_key: Optional[str] = None) -> bool:
        """
        Set the AI provider in BannaFlow.

        Args:
            provider: Provider name (GEMINI, DEEPSEEK, QWEN, GPT, CLAUDE, MINIMAX)
            api_key: Optional API key override

        Returns:
            True if successfully set
        """
        if not self.driver:
            return False

        try:
            # Set provider
            self.driver.execute_script(
                f"localStorage.setItem('{self.LS_AI_PROVIDER}', '{provider}')"
            )

            # Set API key if provided
            if api_key:
                self.driver.execute_script(
                    f"localStorage.setItem('{self.LS_CUSTOM_API_KEY}', '{api_key}')"
                )

            # Refresh to apply changes
            self.driver.refresh()
            self._random_delay(2, 3)

            logger.info(f"Set BannaFlow AI provider to: {provider}")
            return True

        except Exception as e:
            logger.error(f"Failed to set AI provider: {e}")
            return False

    def _wait_and_click(self, selector: str, by: By = By.CSS_SELECTOR, timeout: int = 10, description: str = "") -> bool:
        """Wait for element and click it."""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, selector))
            )

            # Scroll into view
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                element
            )
            self._random_delay(0.3, 0.5)

            # Try normal click
            try:
                element.click()
            except Exception:
                # Fallback to JS click
                self.driver.execute_script("arguments[0].click();", element)

            if description:
                logger.info(f"Clicked: {description}")
            return True

        except TimeoutException:
            logger.warning(f"Timeout waiting for element: {selector}")
            return False
        except Exception as e:
            logger.warning(f"Click failed for '{description}': {e}")
            return False

    def _input_text(self, selector: str, text: str, by: By = By.CSS_SELECTOR, clear: bool = True) -> bool:
        """Input text into a field."""
        try:
            element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((by, selector))
            )

            if clear:
                element.clear()

            element.send_keys(text)
            self._random_delay(0.3, 0.5)
            return True

        except Exception as e:
            logger.warning(f"Failed to input text: {e}")
            return False

    def discover_topics(self, location: str = "西双版纳", keywords: str = "") -> bool:
        """
        Trigger topic discovery in BannaFlow.

        Args:
            location: Location for topic discovery
            keywords: Additional keywords

        Returns:
            True if discovery started successfully
        """
        try:
            self._take_screenshot("before_discover")

            # Look for Discovery section/button
            discover_selectors = [
                "button:contains('发现')",
                "button:contains('Discover')",
                "[class*='discover']",
                "button[class*='discover']",
            ]

            # Try clicking discover button
            for selector in discover_selectors:
                if self._wait_and_click(selector, timeout=5, description="Discover button"):
                    break

            self._random_delay(2, 4)

            # Input location if field exists
            location_selectors = [
                "input[placeholder*='location']",
                "input[placeholder*='位置']",
                "input[name*='location']",
            ]

            for selector in location_selectors:
                if self._input_text(selector, location):
                    logger.info(f"Set location: {location}")
                    break

            self._random_delay(1, 2)
            self._take_screenshot("after_discover")
            return True

        except Exception as e:
            logger.error(f"Topic discovery failed: {e}")
            self._take_screenshot("discover_error")
            return False

    def generate_content_interactive(self) -> Optional[GeneratedContent]:
        """
        Interactive content generation - opens BannaFlow and waits for user
        to complete content generation, then retrieves the result.

        This method is useful when you want manual control over the generation process.

        Returns:
            Generated content or None
        """
        logger.info("=" * 60)
        logger.info("Interactive Content Generation Mode")
        logger.info("=" * 60)
        logger.info("1. BannaFlow will open in a browser window")
        logger.info("2. Use the app to generate your content")
        logger.info("3. After publishing in BannaFlow, return here")
        logger.info("=" * 60)

        if not self.open_bannaflow():
            return None

        # Get initial history count
        initial_history = self.get_published_history()
        initial_count = len(initial_history)

        logger.info(f"Initial history count: {initial_count}")
        logger.info("Waiting for you to generate content in BannaFlow...")
        logger.info("Press Ctrl+C when done, or content will be auto-detected")

        # Poll for new content
        try:
            max_wait = 600  # 10 minutes
            check_interval = 5  # Check every 5 seconds
            waited = 0

            while waited < max_wait:
                time.sleep(check_interval)
                waited += check_interval

                current_history = self.get_published_history()
                if len(current_history) > initial_count:
                    # New content detected!
                    new_item = current_history[0]  # Most recent
                    logger.info("New content detected in BannaFlow!")

                    content = GeneratedContent(
                        title=new_item.get("title", ""),
                        body=new_item.get("content", ""),
                        tags=new_item.get("tags", []),
                        images=new_item.get("images", []),
                        topic=new_item.get("topic", ""),
                        generated_at=datetime.now(),
                    )

                    self._save_content_to_cache(content)
                    return content

        except KeyboardInterrupt:
            logger.info("Manual interrupt - checking for content...")
            current_history = self.get_published_history()
            if len(current_history) > initial_count:
                new_item = current_history[0]
                content = GeneratedContent(
                    title=new_item.get("title", ""),
                    body=new_item.get("content", ""),
                    tags=new_item.get("tags", []),
                    images=new_item.get("images", []),
                    topic=new_item.get("topic", ""),
                    generated_at=datetime.now(),
                )
                self._save_content_to_cache(content)
                return content

        logger.warning("No new content detected")
        return None

    def import_from_bannaflow(self) -> List[GeneratedContent]:
        """
        Import all published content from BannaFlow.

        Returns:
            List of GeneratedContent objects
        """
        if not self.open_bannaflow():
            return []

        history = self.get_published_history()

        contents = []
        for item in history:
            try:
                content = GeneratedContent(
                    title=item.get("title", ""),
                    body=item.get("content", ""),
                    tags=item.get("tags", []),
                    images=item.get("images", []),
                    topic=item.get("topic", ""),
                    generated_at=datetime.fromisoformat(item.get("publishedAt", datetime.now().isoformat())),
                )
                contents.append(content)
            except Exception as e:
                logger.warning(f"Failed to parse content item: {e}")

        logger.info(f"Imported {len(contents)} content items from BannaFlow")
        return contents

    def _save_content_to_cache(self, content: GeneratedContent):
        """Save generated content to local cache."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"content_{timestamp}.json"
            filepath = self.CONTENT_CACHE_DIR / filename

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(content.to_dict(), f, ensure_ascii=False, indent=2)

            logger.info(f"Content cached: {filepath}")
        except Exception as e:
            logger.error(f"Failed to cache content: {e}")

    def load_cached_content(self) -> List[GeneratedContent]:
        """Load all cached content from local storage."""
        contents = []

        try:
            for filepath in self.CONTENT_CACHE_DIR.glob("content_*.json"):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    contents.append(GeneratedContent.from_dict(data))
                except Exception as e:
                    logger.warning(f"Failed to load {filepath}: {e}")

            logger.info(f"Loaded {len(contents)} cached content items")
        except Exception as e:
            logger.error(f"Failed to load cached content: {e}")

        return contents

    def close(self):
        """Close browser and cleanup."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("BannaFlow browser closed")
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")
            finally:
                self.driver = None


def create_content_from_bannaflow(content: GeneratedContent) -> Tuple[str, str, List[str]]:
    """
    Convert BannaFlow generated content to format suitable for XHS publisher.

    Args:
        content: GeneratedContent from BannaFlow

    Returns:
        Tuple of (title, body, images)
    """
    # Format body with hashtags
    body = content.body

    # Add tags as hashtags if not already present
    if content.tags:
        existing_tags = set(tag.lower() for tag in content.tags)
        hashtags = [f"#{tag}" for tag in content.tags if f"#{tag.lower()}" not in body.lower()]
        if hashtags:
            body = body.rstrip() + "\n\n" + " ".join(hashtags)

    return content.title, body, content.images
