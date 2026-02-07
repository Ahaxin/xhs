"""
Publishing engine for Xiaohongshu Creator Center using Selenium.
Supports multiple publishing modes: 上传图文 (Image-Text) and 写长文 (Long Article).
"""
import time
import random
from pathlib import Path
from typing import List, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from loguru import logger

from ..content.database import Content, PublishMode


class XHSPublisher:
    """Handles publishing content to Xiaohongshu Creator Center using Selenium."""

    # URLs for different publishing modes
    PUBLISH_IMAGE_TEXT_URL = "https://creator.xiaohongshu.com/publish/publish?from=menu&target=image"
    PUBLISH_LONG_ARTICLE_URL = "https://creator.xiaohongshu.com/publish/publish?from=menu&target=article"
    CREATOR_HOME_URL = "https://creator.xiaohongshu.com"

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

    def _random_delay(self, min_sec: float = 2.0, max_sec: float = 5.0):
        """Add random human-like delay."""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

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
                text = btn.text.strip()[:50] if btn.text else "(no text)"
                classes = btn.get_attribute("class") or "(no class)"
                logger.info(f"  Button {i+1}: text='{text}' class='{classes[:50]}'")

            # Find all links
            links = self.driver.find_elements(By.TAG_NAME, "a")
            logger.info(f"Found {len(links)} links:")
            for i, link in enumerate(links[:15]):  # Limit to first 15
                text = link.text.strip()[:50] if link.text else "(no text)"
                href = link.get_attribute("href") or "(no href)"
                logger.info(f"  Link {i+1}: text='{text}' href='{href[:50]}'")

            # Find all divs with text content that might be clickable
            divs = self.driver.find_elements(By.XPATH, "//div[string-length(normalize-space(text())) > 0 and string-length(normalize-space(text())) < 20]")
            logger.info(f"Found {len(divs)} short-text divs:")
            for i, div in enumerate(divs[:20]):  # Limit to first 20
                text = div.text.strip()[:30] if div.text else "(no text)"
                classes = div.get_attribute("class") or "(no class)"
                logger.info(f"  Div {i+1}: text='{text}' class='{classes[:40]}'")

            # Find all spans with text
            spans = self.driver.find_elements(By.XPATH, "//span[string-length(normalize-space(text())) > 0 and string-length(normalize-space(text())) < 20]")
            logger.info(f"Found {len(spans)} short-text spans:")
            for i, span in enumerate(spans[:15]):  # Limit to first 15
                text = span.text.strip()[:30] if span.text else "(no text)"
                classes = span.get_attribute("class") or "(no class)"
                logger.info(f"  Span {i+1}: text='{text}' class='{classes[:40]}'")

            # Find all input elements
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            logger.info(f"Found {len(inputs)} inputs:")
            for i, inp in enumerate(inputs[:10]):
                inp_type = inp.get_attribute("type") or "text"
                placeholder = inp.get_attribute("placeholder") or "(no placeholder)"
                logger.info(f"  Input {i+1}: type='{inp_type}' placeholder='{placeholder[:30]}'")

            # Find contenteditable elements
            editables = self.driver.find_elements(By.XPATH, "//*[@contenteditable='true']")
            logger.info(f"Found {len(editables)} contenteditable elements")

            logger.info("=" * 60)
        except Exception as e:
            logger.error(f"Debug page elements error: {e}")

    def _wait_and_click(self, xpath: str, timeout: int = 10, description: str = "") -> bool:
        """Wait for element and click it."""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            element.click()
            if description:
                logger.info(f"Clicked: {description}")
            return True
        except Exception as e:
            logger.warning(f"Could not click element ({description}): {e}")
            return False

    def _wait_and_find(self, xpath: str, timeout: int = 10):
        """Wait for element and return it."""
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )

    # ==================== Navigation Methods ====================

    def _navigate_to_image_text_upload(self) -> bool:
        """
        Navigate to 上传图文 → 上传图片 mode via direct URL.
        """
        try:
            self.driver.get(self.PUBLISH_IMAGE_TEXT_URL)
            self._random_delay(2, 3)

            # Debug: show what's on the page
            self._debug_page_elements()

            # Click 上传图片 tab (should be default, but click to ensure)
            self._wait_and_click(
                '//div[contains(text(), "上传图片")] | //button[contains(text(), "上传图片")] | //*[contains(@class, "tab") and contains(text(), "上传图片")]',
                timeout=5,
                description="上传图片 tab"
            )

            self._random_delay(1, 2)
            logger.info("Navigated to 上传图文 - 上传图片 mode")
            return True

        except Exception as e:
            logger.error(f"Error navigating to image-text upload mode: {e}")
            return False

    def _navigate_to_image_text_compose(self) -> bool:
        """
        Navigate to 上传图文 → 文字配图 mode via direct URL.
        """
        try:
            self.driver.get(self.PUBLISH_IMAGE_TEXT_URL)
            self._random_delay(2, 3)

            # Click 文字配图 tab
            if not self._wait_and_click(
                '//div[contains(text(), "文字配图")] | //button[contains(text(), "文字配图")] | //*[contains(@class, "tab") and contains(text(), "文字配图")]',
                timeout=10,
                description="文字配图 tab"
            ):
                logger.error("Could not find 文字配图 tab")
                return False

            self._random_delay(2, 3)
            logger.info("Navigated to 上传图文 - 文字配图 mode")
            return True

        except Exception as e:
            logger.error(f"Error navigating to text-compose mode: {e}")
            return False

    def _click_add_another_slide(self) -> bool:
        """Click 再写一张 (Add another slide) button for text-compose mode."""
        try:
            if self._wait_and_click(
                '//button[contains(text(), "再写一张")] | //div[contains(text(), "再写一张")] | //*[contains(text(), "再写一张")]',
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
            self.driver.get(self.PUBLISH_LONG_ARTICLE_URL)
            self._random_delay(2, 3)

            # Debug: show what's on the page
            self._debug_page_elements()

            # Try multiple selectors for 新的创作 button
            new_creation_selectors = [
                '//button[contains(text(), "新的创作")]',
                '//span[contains(text(), "新的创作")]',
                '//div[contains(text(), "新的创作")]',
                '//a[contains(text(), "新的创作")]',
                '//*[contains(text(), "新建")]',
                '//*[contains(text(), "开始创作")]',
                '//*[contains(@class, "create")]//button',
                '//*[contains(@class, "new")]//button',
            ]

            clicked = False
            for selector in new_creation_selectors:
                if self._wait_and_click(selector, timeout=3, description="新的创作"):
                    clicked = True
                    break

            if not clicked:
                # Check if we're already on editor page (no need to click)
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((
                            By.XPATH,
                            '//div[contains(@class, "editor")] | //div[@contenteditable="true"] | //input[contains(@placeholder, "标题")]'
                        ))
                    )
                    logger.info("Already on editor page, no need to click 新的创作")
                except Exception:
                    logger.warning("Could not find editor, continuing anyway")

            self._random_delay(2, 3)
            logger.info("Navigated to 写长文 mode")
            return True

        except Exception as e:
            logger.error(f"Error navigating to long article mode: {e}")
            return False

    def _click_auto_format(self) -> bool:
        """Click 一键排版 (One-click formatting) button."""
        try:
            # Debug: show what's on the page before looking for format button
            logger.info("Looking for 一键排版 button...")
            self._debug_page_elements()

            # Try multiple selectors for 一键排版 button
            format_selectors = [
                '//button[contains(text(), "一键排版")]',
                '//span[contains(text(), "一键排版")]',
                '//div[contains(text(), "一键排版")]',
                '//*[contains(text(), "排版")]',
                '//*[contains(@class, "format")]//button',
                '//*[contains(@class, "auto-format")]',
            ]

            for selector in format_selectors:
                if self._wait_and_click(selector, timeout=3, description="一键排版"):
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
            title_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((
                    By.XPATH,
                    '//input[contains(@placeholder, "标题")] | '
                    '//input[contains(@name, "title")] | '
                    '//textarea[contains(@placeholder, "标题")] | '
                    '//input[contains(@class, "title")]'
                ))
            )
            title_input.clear()
            title_input.send_keys(title)
            self._random_delay(0.5, 1.0)
            logger.info(f"Filled title: {title[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Error filling title: {e}")
            return False

    def _fill_description(self, body: str) -> bool:
        """Fill in the post description/body for image-text mode."""
        try:
            # Try different content editor selectors
            content_selectors = [
                '//textarea[contains(@placeholder, "描述")] | //textarea[contains(@placeholder, "说点什么")]',
                '//textarea[contains(@placeholder, "正文")] | //textarea[contains(@placeholder, "内容")]',
                '//div[@contenteditable="true"]',
                '//div[contains(@class, "editor")]//textarea',
                '//div[contains(@class, "desc")]//textarea',
            ]

            content_input = None
            for selector in content_selectors:
                try:
                    content_input = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    break
                except Exception:
                    continue

            if not content_input:
                logger.error("Could not find description input field")
                return False

            # Fill content
            content_input.clear()
            content_input.send_keys(body)
            self._random_delay(1.0, 2.0)
            logger.info(f"Filled description: {len(body)} characters")
            return True

        except Exception as e:
            logger.error(f"Error filling description: {e}")
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
            ]

            editor = None
            for selector in editor_selectors:
                try:
                    editor = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    break
                except Exception:
                    continue

            if not editor:
                logger.error("Could not find rich text editor")
                return False

            # Click to focus
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
            return False

    def _upload_images(self, image_paths: List[str]) -> bool:
        """Upload images to the post."""
        try:
            if not image_paths:
                logger.info("No images to upload")
                return True

            # Find image upload input
            upload_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((
                    By.XPATH,
                    '//input[@type="file"]'
                ))
            )

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
            return False

    def _submit_post(self) -> bool:
        """Submit/publish the post."""
        try:
            # Find and click publish button
            publish_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    '//button[contains(text(), "发布")] | '
                    '//button[contains(text(), "发布笔记")] | '
                    '//button[contains(@class, "publish")] | '
                    '//button[contains(@class, "submit")]'
                ))
            )
            publish_btn.click()
            self._random_delay(3, 5)

            # Wait for success confirmation
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((
                        By.XPATH,
                        '//div[contains(text(), "发布成功")] | '
                        '//div[contains(text(), "已发布")] | '
                        '//div[contains(@class, "success")]'
                    ))
                )
                logger.info("Post published successfully!")
                return True
            except Exception:
                # Check if we're redirected to posts list
                current_url = self.driver.current_url.lower()
                if 'publish' not in current_url or 'success' in current_url:
                    logger.info("Post likely published (redirected away from publish page)")
                    return True
                else:
                    logger.warning("Could not confirm publish success")
                    return False

        except Exception as e:
            logger.error(f"Error submitting post: {e}")
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
                f'(//textarea[contains(@placeholder, "")])[{slide_index + 1}]',
                '//div[@contenteditable="true"]',
                '//textarea',
            ]

            editor = None
            for selector in editor_selectors:
                try:
                    editor = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    break
                except Exception:
                    continue

            if not editor:
                logger.error(f"Could not find text editor for slide {slide_index + 1}")
                return False

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
        self._remove_status_overlay(5)
        return False
