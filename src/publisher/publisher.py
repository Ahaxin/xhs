"""
Publishing engine for Xiaohongshu Creator Center using Selenium.
Supports multiple publishing modes: 上传图文 (Image-Text) and 写长文 (Long Article).

Enhanced with:
- Multiple click strategies (normal, JavaScript, ActionChains)
- Scroll-into-view before interactions
- Screenshot capture on failure for debugging
- Better element selectors with CSS fallback
- Improved error recovery and retry logic
- Page load verification
"""
import time
import random
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Callable, Tuple
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    TimeoutException,
    ElementClickInterceptedException,
    ElementNotInteractableException,
    StaleElementReferenceException,
    NoSuchElementException,
)
from loguru import logger

from ..content.database import Content, PublishMode


class XHSPublisher:
    """Handles publishing content to Xiaohongshu Creator Center using Selenium."""

    # URLs for different publishing modes
    PUBLISH_IMAGE_TEXT_URL = "https://creator.xiaohongshu.com/publish/publish?from=menu&target=image"
    PUBLISH_LONG_ARTICLE_URL = "https://creator.xiaohongshu.com/publish/publish?from=menu&target=article"
    CREATOR_HOME_URL = "https://creator.xiaohongshu.com"

    # Screenshot directory
    SCREENSHOT_DIR = Path("logs/screenshots")

    # Status overlay CSS and JavaScript
    STATUS_OVERLAY_CSS = """
        #xhs-publish-status {
            position: fixed;
            top: 10px;
            right: 10px;
            z-index: 999999;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 25px;
            border-radius: 12px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 14px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            min-width: 280px;
            transition: all 0.3s ease;
        }
        #xhs-publish-status .status-title {
            font-weight: bold;
            font-size: 16px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        #xhs-publish-status .status-step {
            opacity: 0.95;
            font-size: 13px;
        }
        #xhs-publish-status .status-progress {
            margin-top: 10px;
            background: rgba(255,255,255,0.3);
            border-radius: 4px;
            height: 6px;
            overflow: hidden;
        }
        #xhs-publish-status .status-progress-bar {
            height: 100%;
            background: white;
            border-radius: 4px;
            transition: width 0.5s ease;
        }
        #xhs-publish-status.success {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }
        #xhs-publish-status.error {
            background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
        }
        #xhs-publish-status .spinner {
            width: 16px;
            height: 16px;
            border: 2px solid rgba(255,255,255,0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    """

    def __init__(self, driver: webdriver.Chrome):
        """
        Initialize publisher with authenticated driver.

        Args:
            driver: Selenium Chrome driver instance (already logged in)
        """
        self.driver = driver
        self._overlay_initialized = False
        self._total_steps = 5
        self._current_step = 0

        # Ensure screenshot directory exists
        self.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    # ==================== Screenshot & Debugging ====================

    def _take_screenshot(self, name: str) -> str:
        """Take a screenshot for debugging purposes."""
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

    def _log_page_info(self):
        """Log current page information for debugging."""
        try:
            logger.info(f"Current URL: {self.driver.current_url}")
            logger.info(f"Page title: {self.driver.title}")
        except Exception as e:
            logger.warning(f"Failed to log page info: {e}")

    # ==================== Status Overlay ====================

    def _init_status_overlay(self):
        """Initialize the status overlay in the browser."""
        if self._overlay_initialized:
            return

        try:
            # Inject CSS
            css_js = f"""
                var style = document.createElement('style');
                style.textContent = `{self.STATUS_OVERLAY_CSS}`;
                document.head.appendChild(style);
            """
            self.driver.execute_script(css_js)

            # Create overlay element
            overlay_js = """
                var overlay = document.createElement('div');
                overlay.id = 'xhs-publish-status';
                overlay.innerHTML = `
                    <div class="status-title">
                        <div class="spinner"></div>
                        <span>🤖 自动发布中...</span>
                    </div>
                    <div class="status-step">准备中...</div>
                    <div class="status-progress">
                        <div class="status-progress-bar" style="width: 0%"></div>
                    </div>
                `;
                document.body.appendChild(overlay);
            """
            self.driver.execute_script(overlay_js)
            self._overlay_initialized = True
            logger.info("Status overlay initialized")
        except Exception as e:
            logger.warning(f"Could not initialize status overlay: {e}")

    def _update_status(self, step: str, progress: int = None, status: str = ""):
        """
        Update the status overlay in the browser.

        Args:
            step: Current step description
            progress: Progress percentage (0-100)
            status: Status type ('', 'success', 'error')
        """
        try:
            self._init_status_overlay()

            if progress is None:
                self._current_step += 1
                progress = int((self._current_step / self._total_steps) * 100)

            status_class = f"'{status}'" if status else "''"

            js = f"""
                var overlay = document.getElementById('xhs-publish-status');
                if (overlay) {{
                    overlay.className = {status_class};
                    var titleSpan = overlay.querySelector('.status-title span');
                    var spinner = overlay.querySelector('.spinner');

                    if ('{status}' === 'success') {{
                        titleSpan.textContent = '✅ 发布成功!';
                        if (spinner) spinner.style.display = 'none';
                    }} else if ('{status}' === 'error') {{
                        titleSpan.textContent = '❌ 发布失败';
                        if (spinner) spinner.style.display = 'none';
                    }} else {{
                        titleSpan.textContent = '🤖 自动发布中...';
                        if (spinner) spinner.style.display = 'block';
                    }}

                    overlay.querySelector('.status-step').textContent = '{step}';
                    overlay.querySelector('.status-progress-bar').style.width = '{progress}%';
                }}
            """
            self.driver.execute_script(js)
            logger.info(f"[{progress}%] {step}")
        except Exception as e:
            logger.warning(f"Could not update status overlay: {e}")

    def _remove_status_overlay(self, delay: float = 3.0):
        """Remove the status overlay after a delay."""
        try:
            time.sleep(delay)
            js = """
                var overlay = document.getElementById('xhs-publish-status');
                if (overlay) {
                    overlay.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
                    overlay.style.opacity = '0';
                    overlay.style.transform = 'translateX(100px)';
                    setTimeout(function() { overlay.remove(); }, 500);
                }
            """
            self.driver.execute_script(js)
            self._overlay_initialized = False
        except Exception as e:
            logger.warning(f"Could not remove status overlay: {e}")

    # ==================== Utility Methods ====================

    def _random_delay(self, min_sec: float = 2.0, max_sec: float = 5.0):
        """Add random human-like delay."""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    def _wait_for_page_load(self, timeout: int = 10):
        """Wait for page to be fully loaded."""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            # Additional wait for dynamic content
            time.sleep(1)
        except TimeoutException:
            logger.warning("Page load timeout, continuing anyway")

    def _scroll_to_element(self, element) -> bool:
        """Scroll element into view."""
        try:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                element
            )
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.warning(f"Failed to scroll to element: {e}")
            return False

    # ==================== Enhanced Click Methods ====================

    def _click_element(
        self,
        element,
        description: str = "",
        max_retries: int = 3
    ) -> bool:
        """
        Click an element using multiple strategies with retry logic.

        Args:
            element: The WebElement to click
            description: Description for logging
            max_retries: Maximum retry attempts

        Returns:
            True if click succeeded
        """
        strategies: List[Tuple[str, Callable]] = [
            ("normal click", lambda: element.click()),
            ("JavaScript click", lambda: self.driver.execute_script("arguments[0].click();", element)),
            ("ActionChains click", lambda: ActionChains(self.driver).move_to_element(element).click().perform()),
            ("scroll + click", lambda: (self._scroll_to_element(element), element.click())),
            ("scroll + JS click", lambda: (self._scroll_to_element(element), self.driver.execute_script("arguments[0].click();", element))),
        ]

        for attempt in range(max_retries):
            for strategy_name, click_fn in strategies:
                try:
                    # Verify element is still valid and visible
                    if not element.is_displayed():
                        logger.debug(f"Element not displayed for {strategy_name}")
                        continue

                    click_fn()
                    logger.info(f"Clicked ({strategy_name}): {description}")
                    return True

                except ElementClickInterceptedException:
                    logger.debug(f"{strategy_name} intercepted for '{description}', trying next strategy")
                    continue
                except ElementNotInteractableException:
                    logger.debug(f"{strategy_name} not interactable for '{description}', trying next strategy")
                    continue
                except StaleElementReferenceException:
                    logger.warning(f"Element stale during {strategy_name} for '{description}'")
                    return False  # Need to re-find element
                except Exception as e:
                    logger.debug(f"{strategy_name} failed for '{description}': {str(e)[:50]}")
                    continue

            if attempt < max_retries - 1:
                logger.debug(f"Retrying click for '{description}' (attempt {attempt + 2}/{max_retries})")
                time.sleep(0.5)

        logger.warning(f"All click strategies failed for '{description}'")
        return False

    def _find_and_click(
        self,
        selectors: List[Tuple[str, str]],
        timeout: int = 10,
        description: str = ""
    ) -> bool:
        """
        Find element using multiple selectors and click it.

        Args:
            selectors: List of (selector_type, selector_value) tuples
                       selector_type: 'xpath', 'css', 'id', 'class', 'text'
            timeout: Maximum wait time per selector
            description: Description for logging

        Returns:
            True if element found and clicked
        """
        for selector_type, selector_value in selectors:
            try:
                if selector_type == 'xpath':
                    by = By.XPATH
                elif selector_type == 'css':
                    by = By.CSS_SELECTOR
                elif selector_type == 'id':
                    by = By.ID
                elif selector_type == 'class':
                    by = By.CLASS_NAME
                elif selector_type == 'text':
                    # Convert text search to xpath
                    by = By.XPATH
                    selector_value = f"//*[contains(text(), '{selector_value}')]"
                else:
                    by = By.XPATH

                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((by, selector_value))
                )

                if element.is_displayed():
                    if self._click_element(element, description):
                        return True
                else:
                    logger.debug(f"Element found but not displayed: {selector_value[:50]}")

            except TimeoutException:
                logger.debug(f"Timeout for selector: {selector_value[:50]}")
            except Exception as e:
                logger.debug(f"Error with selector {selector_value[:50]}: {str(e)[:50]}")

        logger.warning(f"Could not find/click: {description}")
        return False

    def _wait_and_click(self, xpath: str, timeout: int = 10, description: str = "") -> bool:
        """
        Wait for element and click it (legacy method, uses enhanced clicking).

        Args:
            xpath: XPath selector
            timeout: Wait timeout
            description: Description for logging

        Returns:
            True if click succeeded
        """
        return self._find_and_click(
            selectors=[('xpath', xpath)],
            timeout=timeout,
            description=description
        )

    def _wait_and_find(self, xpath: str, timeout: int = 10):
        """Wait for element and return it."""
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )

    def _debug_page_elements(self):
        """Debug helper: Log all clickable elements on the current page."""
        try:
            logger.info("=" * 60)
            logger.info(f"DEBUG: Current URL: {self.driver.current_url}")
            logger.info("=" * 60)

            # Find all buttons
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            logger.info(f"Found {len(buttons)} buttons:")
            for i, btn in enumerate(buttons[:20]):  # Limit to first 20
                try:
                    text = btn.text.strip()[:50] if btn.text else "(no text)"
                    classes = btn.get_attribute("class") or "(no class)"
                    is_displayed = btn.is_displayed()
                    logger.info(f"  Button {i+1}: text='{text}' class='{classes[:50]}' displayed={is_displayed}")
                except StaleElementReferenceException:
                    pass

            # Find all links
            links = self.driver.find_elements(By.TAG_NAME, "a")
            logger.info(f"Found {len(links)} links:")
            for i, link in enumerate(links[:15]):  # Limit to first 15
                try:
                    text = link.text.strip()[:50] if link.text else "(no text)"
                    href = link.get_attribute("href") or "(no href)"
                    logger.info(f"  Link {i+1}: text='{text}' href='{href[:50]}'")
                except StaleElementReferenceException:
                    pass

            # Find all divs with text content that might be clickable
            divs = self.driver.find_elements(By.XPATH, "//div[string-length(normalize-space(text())) > 0 and string-length(normalize-space(text())) < 20]")
            logger.info(f"Found {len(divs)} short-text divs:")
            for i, div in enumerate(divs[:20]):  # Limit to first 20
                try:
                    text = div.text.strip()[:30] if div.text else "(no text)"
                    classes = div.get_attribute("class") or "(no class)"
                    logger.info(f"  Div {i+1}: text='{text}' class='{classes[:40]}'")
                except StaleElementReferenceException:
                    pass

            # Find all spans with text
            spans = self.driver.find_elements(By.XPATH, "//span[string-length(normalize-space(text())) > 0 and string-length(normalize-space(text())) < 20]")
            logger.info(f"Found {len(spans)} short-text spans:")
            for i, span in enumerate(spans[:15]):  # Limit to first 15
                try:
                    text = span.text.strip()[:30] if span.text else "(no text)"
                    classes = span.get_attribute("class") or "(no class)"
                    logger.info(f"  Span {i+1}: text='{text}' class='{classes[:40]}'")
                except StaleElementReferenceException:
                    pass

            # Find all input elements
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            logger.info(f"Found {len(inputs)} inputs:")
            for i, inp in enumerate(inputs[:10]):
                try:
                    inp_type = inp.get_attribute("type") or "text"
                    placeholder = inp.get_attribute("placeholder") or "(no placeholder)"
                    logger.info(f"  Input {i+1}: type='{inp_type}' placeholder='{placeholder[:30]}'")
                except StaleElementReferenceException:
                    pass

            # Find contenteditable elements
            editables = self.driver.find_elements(By.XPATH, "//*[@contenteditable='true']")
            logger.info(f"Found {len(editables)} contenteditable elements")

            logger.info("=" * 60)
        except Exception as e:
            logger.error(f"Debug page elements error: {e}")

    # ==================== Navigation Methods ====================

    def _navigate_to_image_text_upload(self) -> bool:
        """
        Navigate to 上传图文 → 上传图片 mode via direct URL.
        """
        try:
            logger.info("Navigating to Image Text Upload page...")
            self.driver.get(self.PUBLISH_IMAGE_TEXT_URL)
            self._wait_for_page_load()
            self._random_delay(2, 3)

            # Debug: show what's on the page
            self._debug_page_elements()
            self._log_page_info()

            # Click 上传图片 tab (should be default, but click to ensure)
            upload_tab_selectors = [
                ('text', '上传图片'),
                ('xpath', '//div[contains(text(), "上传图片")]'),
                ('xpath', '//button[contains(text(), "上传图片")]'),
                ('xpath', '//*[contains(@class, "tab") and contains(text(), "上传图片")]'),
                ('css', '[class*="upload"][class*="tab"]'),
            ]

            self._find_and_click(
                selectors=upload_tab_selectors,
                timeout=5,
                description="上传图片 tab"
            )

            self._random_delay(1, 2)
            logger.info("Navigated to 上传图文 - 上传图片 mode")
            return True

        except Exception as e:
            logger.error(f"Error navigating to image-text upload mode: {e}")
            self._take_screenshot("error_navigate_image_text_upload")
            return False

    def _navigate_to_image_text_compose(self) -> bool:
        """
        Navigate to 上传图文 → 文字配图 mode via direct URL.
        """
        try:
            logger.info("Navigating to Text Compose page...")
            self.driver.get(self.PUBLISH_IMAGE_TEXT_URL)
            self._wait_for_page_load()
            self._random_delay(2, 3)

            # Click 文字配图 tab
            compose_tab_selectors = [
                ('text', '文字配图'),
                ('xpath', '//div[contains(text(), "文字配图")]'),
                ('xpath', '//button[contains(text(), "文字配图")]'),
                ('xpath', '//*[contains(@class, "tab") and contains(text(), "文字配图")]'),
                ('css', '[class*="compose"][class*="tab"]'),
                ('css', '[class*="text"][class*="tab"]'),
            ]

            if not self._find_and_click(
                selectors=compose_tab_selectors,
                timeout=10,
                description="文字配图 tab"
            ):
                logger.error("Could not find 文字配图 tab")
                self._take_screenshot("error_navigate_text_compose")
                return False

            self._random_delay(2, 3)
            logger.info("Navigated to 上传图文 - 文字配图 mode")
            return True

        except Exception as e:
            logger.error(f"Error navigating to text-compose mode: {e}")
            self._take_screenshot("error_navigate_text_compose")
            return False

    def _click_add_another_slide(self) -> bool:
        """Click 再写一张 (Add another slide) button for text-compose mode."""
        try:
            add_slide_selectors = [
                ('text', '再写一张'),
                ('xpath', '//button[contains(text(), "再写一张")]'),
                ('xpath', '//div[contains(text(), "再写一张")]'),
                ('xpath', '//*[contains(text(), "再写一张")]'),
                ('css', '[class*="add"][class*="slide"]'),
                ('css', '[class*="another"]'),
            ]

            if self._find_and_click(
                selectors=add_slide_selectors,
                timeout=5,
                description="再写一张 button"
            ):
                self._random_delay(1, 2)
                logger.info("Clicked 再写一张 (add another slide)")
                return True
            else:
                logger.warning("Could not find 再写一张 button")
                return False
        except Exception as e:
            logger.warning(f"Error clicking add another slide: {e}")
            return False

    def _navigate_to_long_article(self) -> bool:
        """
        Navigate to 写长文 mode via direct URL.
        Then click 新的创作 to start a new article.
        """
        try:
            logger.info("Navigating to Long Article page...")
            self.driver.get(self.PUBLISH_LONG_ARTICLE_URL)
            self._wait_for_page_load()
            self._random_delay(2, 3)

            # Debug: show what's on the page
            self._debug_page_elements()
            self._log_page_info()

            # Comprehensive selectors for 新的创作 button
            new_creation_selectors = [
                # Text-based selectors (most reliable)
                ('text', '新的创作'),
                ('text', '新建创作'),
                ('text', '开始创作'),
                ('text', '新建'),
                ('text', '创建'),
                # XPath selectors
                ('xpath', '//button[contains(text(), "新的创作")]'),
                ('xpath', '//span[contains(text(), "新的创作")]'),
                ('xpath', '//div[contains(text(), "新的创作")]'),
                ('xpath', '//a[contains(text(), "新的创作")]'),
                ('xpath', '//*[contains(text(), "新建")]'),
                ('xpath', '//*[contains(text(), "开始创作")]'),
                ('xpath', '//*[contains(text(), "创建")]'),
                # Class-based selectors
                ('xpath', '//*[contains(@class, "create")]//button'),
                ('xpath', '//*[contains(@class, "new")]//button'),
                ('xpath', '//*[contains(@class, "create-btn")]'),
                ('xpath', '//*[contains(@class, "new-btn")]'),
                ('css', '[class*="create"] button'),
                ('css', '[class*="new"] button'),
                ('css', 'button[class*="create"]'),
                ('css', 'button[class*="primary"]'),
                # Fallback: any primary/action button
                ('css', '.btn-primary'),
                ('css', '.action-btn'),
            ]

            clicked = self._find_and_click(
                selectors=new_creation_selectors,
                timeout=3,
                description="新的创作"
            )

            if not clicked:
                # Check if we're already on editor page (no need to click)
                editor_found = self._check_editor_present()
                if editor_found:
                    logger.info("Already on editor page, no need to click 新的创作")
                else:
                    logger.warning("Could not find 新的创作 button or editor, taking screenshot")
                    self._take_screenshot("warning_new_creation_not_found")

            self._random_delay(2, 3)
            logger.info("Navigated to 写长文 mode")
            return True

        except Exception as e:
            logger.error(f"Error navigating to long article mode: {e}")
            self._take_screenshot("error_navigate_long_article")
            return False

    def _check_editor_present(self, timeout: int = 5) -> bool:
        """Check if we're already on an editor page."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((
                    By.XPATH,
                    '//div[contains(@class, "editor")] | '
                    '//div[@contenteditable="true"] | '
                    '//input[contains(@placeholder, "标题")] | '
                    '//textarea[contains(@placeholder, "标题")] | '
                    '//div[contains(@class, "ql-editor")] | '
                    '//div[contains(@class, "ProseMirror")]'
                ))
            )
            return True
        except TimeoutException:
            return False

    def _click_auto_format(self) -> bool:
        """Click 一键排版 (One-click formatting) button."""
        try:
            # Debug: show what's on the page before looking for format button
            logger.info("Looking for 一键排版 button...")

            format_selectors = [
                ('text', '一键排版'),
                ('xpath', '//button[contains(text(), "一键排版")]'),
                ('xpath', '//span[contains(text(), "一键排版")]'),
                ('xpath', '//div[contains(text(), "一键排版")]'),
                ('xpath', '//*[contains(text(), "排版")]'),
                ('xpath', '//*[contains(@class, "format")]//button'),
                ('xpath', '//*[contains(@class, "auto-format")]'),
                ('css', '[class*="format"] button'),
                ('css', 'button[class*="format"]'),
            ]

            if self._find_and_click(
                selectors=format_selectors,
                timeout=3,
                description="一键排版"
            ):
                self._random_delay(2, 3)
                logger.info("Clicked 一键排版 (auto-format)")
                return True

            logger.warning("Could not find 一键排版 button, skipping (may not be available)")
            return False
        except Exception as e:
            logger.warning(f"Error clicking auto-format: {e}")
            return False

    # ==================== Content Input Methods ====================

    def _fill_title(self, title: str) -> bool:
        """Fill in the post title."""
        try:
            title_selectors = [
                '//input[contains(@placeholder, "标题")]',
                '//input[contains(@name, "title")]',
                '//textarea[contains(@placeholder, "标题")]',
                '//input[contains(@class, "title")]',
                '//input[@type="text"][1]',  # First text input as fallback
            ]

            title_input = None
            for selector in title_selectors:
                try:
                    title_input = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    if title_input.is_displayed():
                        break
                except TimeoutException:
                    continue

            if not title_input:
                logger.error("Could not find title input field")
                self._take_screenshot("error_title_not_found")
                return False

            # Scroll into view and click to focus
            self._scroll_to_element(title_input)
            title_input.click()
            time.sleep(0.3)

            # Clear and fill
            title_input.clear()
            title_input.send_keys(title)
            self._random_delay(0.5, 1.0)
            logger.info(f"Filled title: {title[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Error filling title: {e}")
            self._take_screenshot("error_fill_title")
            return False

    def _fill_description(self, body: str) -> bool:
        """Fill in the post description/body for image-text mode."""
        try:
            # Try different content editor selectors
            content_selectors = [
                '//textarea[contains(@placeholder, "描述")]',
                '//textarea[contains(@placeholder, "说点什么")]',
                '//textarea[contains(@placeholder, "正文")]',
                '//textarea[contains(@placeholder, "内容")]',
                '//div[@contenteditable="true"]',
                '//div[contains(@class, "editor")]//textarea',
                '//div[contains(@class, "desc")]//textarea',
                '//textarea',  # Fallback to any textarea
            ]

            content_input = None
            for selector in content_selectors:
                try:
                    content_input = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    if content_input.is_displayed():
                        break
                except TimeoutException:
                    continue

            if not content_input:
                logger.error("Could not find description input field")
                self._take_screenshot("error_description_not_found")
                return False

            # Scroll into view and click to focus
            self._scroll_to_element(content_input)
            content_input.click()
            time.sleep(0.3)

            # Fill content
            content_input.clear()
            content_input.send_keys(body)
            self._random_delay(1.0, 2.0)
            logger.info(f"Filled description: {len(body)} characters")
            return True

        except Exception as e:
            logger.error(f"Error filling description: {e}")
            self._take_screenshot("error_fill_description")
            return False

    def _fill_long_article_content(self, body: str) -> bool:
        """Fill in the rich text content for long article mode."""
        try:
            # Long article uses a rich text editor (usually Quill or similar)
            editor_selectors = [
                '//div[contains(@class, "ql-editor")]',
                '//div[@contenteditable="true"]',
                '//div[contains(@class, "editor-content")]',
                '//div[contains(@class, "ProseMirror")]',
                '//div[contains(@class, "rich-text")]',
            ]

            editor = None
            for selector in editor_selectors:
                try:
                    editor = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    if editor.is_displayed():
                        break
                except TimeoutException:
                    continue

            if not editor:
                logger.error("Could not find rich text editor")
                self._take_screenshot("error_editor_not_found")
                return False

            # Scroll into view and click to focus
            self._scroll_to_element(editor)
            editor.click()
            self._random_delay(0.5, 1.0)

            # Clear existing content and type new content
            editor.send_keys(Keys.CONTROL + "a")
            editor.send_keys(body)
            self._random_delay(1.0, 2.0)
            logger.info(f"Filled long article content: {len(body)} characters")
            return True

        except Exception as e:
            logger.error(f"Error filling long article content: {e}")
            self._take_screenshot("error_fill_long_article")
            return False

    def _upload_images(self, image_paths: List[str]) -> bool:
        """Upload images to the post."""
        try:
            if not image_paths:
                logger.info("No images to upload")
                return True

            # Find image upload input
            upload_selectors = [
                '//input[@type="file"]',
                '//input[@accept*="image"]',
                '//input[contains(@class, "upload")]',
            ]

            upload_input = None
            for selector in upload_selectors:
                try:
                    upload_input = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    break
                except TimeoutException:
                    continue

            if not upload_input:
                logger.error("Could not find file upload input")
                self._take_screenshot("error_upload_input_not_found")
                return False

            # Upload each image
            for i, image_path in enumerate(image_paths):
                if not Path(image_path).exists():
                    logger.warning(f"Image not found: {image_path}")
                    continue

                upload_input.send_keys(str(Path(image_path).absolute()))
                self._random_delay(2, 3)  # Wait for upload
                logger.info(f"Uploaded image {i+1}/{len(image_paths)}: {Path(image_path).name}")

            # Wait for all uploads to complete
            self._random_delay(3, 5)
            return True

        except Exception as e:
            logger.error(f"Error uploading images: {e}")
            self._take_screenshot("error_upload_images")
            return False

    def _submit_post(self) -> bool:
        """Submit/publish the post."""
        try:
            # Find and click publish button
            publish_selectors = [
                ('text', '发布'),
                ('text', '发布笔记'),
                ('xpath', '//button[contains(text(), "发布")]'),
                ('xpath', '//button[contains(text(), "发布笔记")]'),
                ('xpath', '//button[contains(@class, "publish")]'),
                ('xpath', '//button[contains(@class, "submit")]'),
                ('css', 'button[class*="publish"]'),
                ('css', 'button[class*="submit"]'),
                ('css', '.publish-btn'),
                ('css', '.submit-btn'),
            ]

            if not self._find_and_click(
                selectors=publish_selectors,
                timeout=10,
                description="发布 button"
            ):
                logger.error("Could not find publish button")
                self._take_screenshot("error_publish_button_not_found")
                return False

            self._random_delay(3, 5)

            # Wait for success confirmation
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((
                        By.XPATH,
                        '//div[contains(text(), "发布成功")] | '
                        '//div[contains(text(), "已发布")] | '
                        '//div[contains(@class, "success")] | '
                        '//*[contains(text(), "成功")]'
                    ))
                )
                logger.info("Post published successfully!")
                self._take_screenshot("success_published")
                return True
            except TimeoutException:
                # Check if we're redirected to posts list
                current_url = self.driver.current_url.lower()
                if 'publish' not in current_url or 'success' in current_url:
                    logger.info("Post likely published (redirected away from publish page)")
                    self._take_screenshot("likely_success_redirected")
                    return True
                else:
                    logger.warning("Could not confirm publish success")
                    self._take_screenshot("warning_publish_unconfirmed")
                    return False

        except Exception as e:
            logger.error(f"Error submitting post: {e}")
            self._take_screenshot("error_submit_post")
            return False

    # ==================== Mode-Specific Publish Methods ====================

    def _publish_image_text_upload(self, content: Content) -> bool:
        """
        Publish using 上传图文 → 上传图片 mode.
        Workflow: 发布笔记 → 上传图文 → 上传图片 → 选择本地图片 → 标题 → 正文 → 发布
        """
        logger.info("Publishing with IMAGE_TEXT_UPLOAD mode (上传图文 - 上传图片)")
        self._current_step = 0
        self._total_steps = 6

        # Step 1: Navigate to upload page
        self._update_status("正在打开上传图文页面...", 10)
        if not self._navigate_to_image_text_upload():
            self._update_status("无法打开发布页面", status="error")
            self._remove_status_overlay(5)
            return False

        # Step 2: Upload images (选择本地图片)
        self._update_status(f"正在选择本地图片 ({len(content.images)} 张)...", 25)
        if content.images:
            if not self._upload_images(content.images):
                self._update_status("图片上传失败", status="error")
                self._remove_status_overlay(5)
                return False
        else:
            logger.warning("No images provided for image-text upload mode")

        # Step 3: Wait for images to finish uploading
        self._update_status("正在等待图片上传完成...", 45)
        self._random_delay(3, 5)

        # Step 4: Fill title
        self._update_status("正在填写标题...", 60)
        if not self._fill_title(content.title):
            self._update_status("标题填写失败", status="error")
            self._remove_status_overlay(5)
            return False

        # Step 5: Fill description/body
        self._update_status("正在填写正文内容...", 75)
        if not self._fill_description(content.body):
            self._update_status("正文填写失败", status="error")
            self._remove_status_overlay(5)
            return False

        # Step 6: Submit/Publish
        self._update_status("正在提交发布...", 90)
        success = self._submit_post()
        if success:
            self._update_status("发布成功！笔记已提交", 100, status="success")
        else:
            self._update_status("发布提交失败", status="error")
        self._remove_status_overlay(5)
        return success

    def _fill_compose_slide(self, text: str, slide_index: int = 0) -> bool:
        """Fill text into a text-compose slide (文字配图模式的一张图)."""
        try:
            # Find the text input area for the current slide
            # Each slide has its own text editor
            editor_selectors = [
                f'(//div[@contenteditable="true"])[{slide_index + 1}]',
                f'(//textarea)[{slide_index + 1}]',
                '//div[@contenteditable="true"]',
                '//textarea',
            ]

            editor = None
            for selector in editor_selectors:
                try:
                    editor = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    if editor.is_displayed():
                        break
                except TimeoutException:
                    continue

            if not editor:
                logger.error(f"Could not find text editor for slide {slide_index + 1}")
                return False

            self._scroll_to_element(editor)
            editor.click()
            self._random_delay(0.3, 0.5)
            editor.send_keys(text)
            self._random_delay(0.5, 1.0)
            logger.info(f"Filled slide {slide_index + 1} with {len(text)} characters")
            return True

        except Exception as e:
            logger.error(f"Error filling compose slide {slide_index + 1}: {e}")
            return False

    def _publish_image_text_compose(self, content: Content) -> bool:
        """
        Publish using 上传图文 → 文字配图 mode.
        Workflow: 发布笔记 → 上传图文 → 文字配图 → 自然分段(每段一张图, 多段点再写一张) → 发布
        """
        logger.info("Publishing with IMAGE_TEXT_COMPOSE mode (上传图文 - 文字配图)")
        self._current_step = 0

        # Split body into paragraphs (natural segmentation)
        paragraphs = [p.strip() for p in content.body.split('\n') if p.strip()]
        if not paragraphs:
            paragraphs = [content.body]

        self._total_steps = 4 + len(paragraphs)  # navigate + paragraphs + title + submit

        # Step 1: Navigate to text-compose page
        self._update_status("正在打开文字配图页面...", 10)
        if not self._navigate_to_image_text_compose():
            self._update_status("无法打开文字配图页面", status="error")
            self._remove_status_overlay(5)
            return False

        self._random_delay(2, 3)

        # Step 2: Fill each paragraph into a slide (自然分段)
        for i, paragraph in enumerate(paragraphs):
            progress = 20 + int((i / len(paragraphs)) * 40)
            self._update_status(f"正在填写第 {i + 1}/{len(paragraphs)} 张图片文字...", progress)

            if i > 0:
                # Click 再写一张 to add another slide
                if not self._click_add_another_slide():
                    logger.warning(f"Could not add slide {i + 1}, trying to continue")
                self._random_delay(1, 2)

            # Fill text for this slide
            if not self._fill_compose_slide(paragraph, i):
                logger.warning(f"Failed to fill slide {i + 1}")

            self._random_delay(1, 2)

        # Step 3: Fill title
        self._update_status("正在填写标题...", 70)
        if not self._fill_title(content.title):
            self._update_status("标题填写失败", status="error")
            self._remove_status_overlay(5)
            return False

        # Step 4: Submit/Publish
        self._update_status("正在提交发布...", 90)
        success = self._submit_post()
        if success:
            self._update_status("发布成功！笔记已提交", 100, status="success")
        else:
            self._update_status("发布提交失败", status="error")
        self._remove_status_overlay(5)
        return success

    def _publish_long_article(self, content: Content) -> bool:
        """
        Publish using 写长文 mode.
        Workflow: 发布笔记 → 写长文 → 新的创作 → 标题 → 正文 → 图片 → 一键排版 → 发布
        """
        logger.info("Publishing with LONG_ARTICLE mode (写长文)")
        self._current_step = 0
        self._total_steps = 7

        # Step 1: Navigate to long article editor
        self._update_status("正在打开长文编辑器...", 10)
        if not self._navigate_to_long_article():
            self._update_status("无法打开长文编辑器", status="error")
            self._remove_status_overlay(5)
            return False

        self._random_delay(2, 3)

        # Step 2: Fill title
        self._update_status("正在填写标题...", 25)
        if not self._fill_title(content.title):
            self._update_status("标题填写失败", status="error")
            self._remove_status_overlay(5)
            return False

        # Step 3: Paste/fill rich text content
        self._update_status("正在粘贴正文内容...", 40)
        if not self._fill_long_article_content(content.body):
            self._update_status("正文内容填写失败", status="error")
            self._remove_status_overlay(5)
            return False

        # Step 4: Insert images if any
        if content.images:
            self._update_status(f"正在插入 {len(content.images)} 张图片...", 55)
            logger.info("Long article mode: inserting images")
            if not self._upload_images(content.images):
                logger.warning("Failed to insert images in long article mode")
                self._update_status("图片插入失败，继续...", 60)

        # Step 5: Click 一键排版 (auto-format)
        self._update_status("正在点击一键排版...", 70)
        self._click_auto_format()  # Non-critical, continue even if fails

        self._random_delay(1, 2)

        # Step 6: Submit/Publish
        self._update_status("正在提交发布...", 90)
        success = self._submit_post()
        if success:
            self._update_status("发布成功！长文已提交", 100, status="success")
        else:
            self._update_status("发布提交失败", status="error")
        self._remove_status_overlay(5)
        return success

    # ==================== Main Publish Method ====================

    def publish(self, content: Content) -> bool:
        """
        Publish content to Xiaohongshu using the specified mode.

        Args:
            content: Content object to publish (includes publish_mode)

        Returns:
            True if published successfully
        """
        try:
            logger.info(f"Starting publish for content #{content.id}: {content.title}")
            logger.info(f"Publish mode: {content.publish_mode.value}")

            # Reset overlay state for new publish
            self._overlay_initialized = False
            self._current_step = 0

            # Route to appropriate publish method based on mode
            if content.publish_mode == PublishMode.IMAGE_TEXT_UPLOAD:
                return self._publish_image_text_upload(content)
            elif content.publish_mode == PublishMode.IMAGE_TEXT_COMPOSE:
                return self._publish_image_text_compose(content)
            elif content.publish_mode == PublishMode.LONG_ARTICLE:
                return self._publish_long_article(content)
            else:
                logger.error(f"Unknown publish mode: {content.publish_mode}")
                self._update_status(f"未知发布模式: {content.publish_mode}", status="error")
                self._remove_status_overlay(5)
                return False

        except Exception as e:
            logger.error(f"Error publishing content #{content.id}: {e}")
            self._update_status(f"发布出错: {str(e)[:30]}", status="error")
            self._take_screenshot(f"error_publish_content_{content.id}")
            self._remove_status_overlay(5)
            return False

    def publish_with_retry(
        self,
        content: Content,
        max_attempts: int = 3,
        retry_delay: int = 60,
    ) -> bool:
        """
        Publish content with retry logic.

        Args:
            content: Content to publish
            max_attempts: Maximum retry attempts
            retry_delay: Delay between retries in seconds

        Returns:
            True if published successfully
        """
        for attempt in range(1, max_attempts + 1):
            logger.info(f"Publish attempt {attempt}/{max_attempts}")

            if self.publish(content):
                return True

            if attempt < max_attempts:
                logger.info(f"Retrying in {retry_delay} seconds...")
                # Show retry countdown in browser
                try:
                    self._overlay_initialized = False
                    self._init_status_overlay()
                    for remaining in range(retry_delay, 0, -1):
                        self._update_status(
                            f"第 {attempt} 次尝试失败，{remaining} 秒后重试 ({attempt}/{max_attempts})...",
                            progress=int((1 - remaining / retry_delay) * 100),
                            status=""
                        )
                        time.sleep(1)
                except Exception:
                    time.sleep(retry_delay)

        logger.error(f"Failed to publish after {max_attempts} attempts")
        self._update_status(f"发布失败，已尝试 {max_attempts} 次", status="error")
        self._take_screenshot(f"final_failure_content_{content.id}")
        self._remove_status_overlay(5)
        return False
