"""
Publishing engine for Xiaohongshu Creator Center using Selenium.
"""
import time
import random
from pathlib import Path
from typing import List, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from loguru import logger

from ..content.database import Content


class XHSPublisher:
    """Handles publishing content to Xiaohongshu Creator Center using Selenium."""
    
    def __init__(self, driver: webdriver.Chrome):
        """
        Initialize publisher with authenticated driver.
        
        Args:
            driver: Selenium Chrome driver instance (already logged in)
        """
        self.driver = driver
    
    def _random_delay(self, min_sec: float = 2.0, max_sec: float = 5.0):
        """Add random human-like delay."""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)
    
    def _navigate_to_publish_page(self) -> bool:
        """Navigate to the content publishing page."""
        try:
            # Common XHS creator center publish URLs
            publish_urls = [
                "https://creator.xiaohongshu.com/publish/publish",
                "https://creator.xiaohongshu.com/creator/post",
            ]
            
            # Try navigating to publish page
            for url in publish_urls:
                try:
                    self.driver.get(url)
                    self._random_delay(2, 3)
                    
                    # Check if we're on the publish page
                    try:
                        WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, '//textarea | //input[contains(@placeholder, "标题")] | //div[contains(@class, "editor")]'))
                        )
                        logger.info(f"Successfully navigated to publish page: {url}")
                        return True
                    except:
                        continue
                except:
                    continue
            
            # If direct URLs don't work, try finding publish button in navigation
            try:
                publish_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '//a[contains(text(), "发布")] | //button[contains(text(), "发布笔记")] | //a[contains(@href, "publish")]'))
                )
                publish_btn.click()
                self._random_delay(2, 3)
                logger.info("Clicked publish button in navigation")
                return True
            except:
                pass
            
            logger.error("Could not navigate to publish page")
            return False
            
        except Exception as e:
            logger.error(f"Error navigating to publish page: {e}")
            return False
    
    def _fill_title(self, title: str) -> bool:
        """Fill in the post title."""
        try:
            title_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//input[contains(@placeholder, "标题")] | //input[contains(@name, "title")] | //textarea[contains(@placeholder, "标题")]'))
            )
            title_input.send_keys(title)
            self._random_delay(0.5, 1.0)
            logger.info(f"Filled title: {title[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Error filling title: {e}")
            return False
    
    def _fill_content(self, body: str) -> bool:
        """Fill in the post content/body."""
        try:
            # Try different content editor selectors
            content_selectors = [
                '//textarea[contains(@placeholder, "正文")] | //textarea[contains(@placeholder, "内容")]',
                '//div[@contenteditable="true"]',
                '//div[contains(@class, "editor")]//textarea',
                '//div[contains(@class, "content")]//textarea',
            ]
            
            content_input = None
            for selector in content_selectors:
                try:
                    content_input = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    break
                except:
                    continue
            
            if not content_input:
                logger.error("Could not find content input field")
                return False
            
            # Fill content
            content_input.send_keys(body)
            self._random_delay(1.0, 2.0)
            logger.info(f"Filled content: {len(body)} characters")
            return True
            
        except Exception as e:
            logger.error(f"Error filling content: {e}")
            return False
    
    def _upload_images(self, image_paths: List[str]) -> bool:
        """Upload images to the post."""
        try:
            if not image_paths:
                logger.info("No images to upload")
                return True
            
            # Find image upload input
            upload_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//input[@type="file" and contains(@accept, "image")]'))
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
                EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "发布")] | //button[contains(text(), "提交")] | //button[contains(@class, "publish")] | //button[contains(@class, "submit")]'))
            )
            publish_btn.click()
            self._random_delay(3, 5)
            
            # Wait for success confirmation
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, '//div[contains(text(), "发布成功")] | //div[contains(text(), "已发布")] | //div[contains(@class, "success")]'))
                )
                logger.info("Post published successfully!")
                return True
            except:
                # Check if we're redirected to posts list
                if 'publish' not in self.driver.current_url.lower():
                    logger.info("Post likely published (redirected away from publish page)")
                    return True
                else:
                    logger.warning("Could not confirm publish success")
                    return False
                    
        except Exception as e:
            logger.error(f"Error submitting post: {e}")
            return False
    
    def publish(self, content: Content) -> bool:
        """
        Publish content to Xiaohongshu.
        
        Args:
            content: Content object to publish
        
        Returns:
            True if published successfully
        """
        try:
            logger.info(f"Starting publish process for content #{content.id}: {content.title}")
            
            # Navigate to publish page
            if not self._navigate_to_publish_page():
                return False
            
            # Fill title
            if not self._fill_title(content.title):
                return False
            
            # Upload images first (XHS typically requires images before content)
            if content.images:
                if not self._upload_images(content.images):
                    return False
            
            # Fill content
            if not self._fill_content(content.body):
                return False
            
            # Submit post
            if not self._submit_post():
                return False
            
            logger.info(f"Successfully published content #{content.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error publishing content #{content.id}: {e}")
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
                time.sleep(retry_delay)
        
        logger.error(f"Failed to publish after {max_attempts} attempts")
        return False
