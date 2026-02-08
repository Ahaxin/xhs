"""
Test script for XHS Publisher - Debug element selectors and click strategies.
Run this to identify actual UI elements on Xiaohongshu pages.
"""
import sys
import os
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.auth.xhs_auth import XHSAuthManager
from src.publisher.publisher import XHSPublisher
from src.content.database import Content, ContentStatus, ContentSource, PublishMode
from src.utils.config import get_config
from loguru import logger


def setup_logging():
    """Setup test logging."""
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="DEBUG"
    )
    logger.add(
        "logs/test_publisher.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB"
    )


def test_login_and_navigate():
    """Test login and navigate to various publishing pages."""
    config = get_config()

    auth_manager = XHSAuthManager(
        creator_url=config.xiaohongshu.creator_center_url,
        session_file=config.xiaohongshu.session_file,
        login_method=config.xiaohongshu.login_method,
        phone_number=config.xiaohongshu.phone_number,
    )

    try:
        logger.info("=" * 60)
        logger.info("Starting login test...")
        logger.info("=" * 60)

        # Login
        success = auth_manager.login()
        if not success:
            logger.error("Login failed!")
            return None

        logger.info("Login successful!")

        driver = auth_manager.get_driver()
        if not driver:
            logger.error("Could not get driver!")
            return None

        publisher = XHSPublisher(driver)
        return publisher, auth_manager

    except Exception as e:
        logger.error(f"Error during login test: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def test_element_discovery(publisher: XHSPublisher):
    """Discover elements on different publishing pages."""
    driver = publisher.driver

    pages = [
        ("Image Text Upload", XHSPublisher.PUBLISH_IMAGE_TEXT_URL),
        ("Long Article", XHSPublisher.PUBLISH_LONG_ARTICLE_URL),
    ]

    for page_name, url in pages:
        logger.info("=" * 60)
        logger.info(f"Testing page: {page_name}")
        logger.info(f"URL: {url}")
        logger.info("=" * 60)

        driver.get(url)
        time.sleep(3)

        # Take screenshot
        screenshot_path = f"logs/screenshot_{page_name.replace(' ', '_').lower()}.png"
        driver.save_screenshot(screenshot_path)
        logger.info(f"Screenshot saved: {screenshot_path}")

        # Debug page elements
        publisher._debug_page_elements()

        # Extra element discovery
        discover_clickable_elements(driver)

        time.sleep(2)


def discover_clickable_elements(driver):
    """Find all potentially clickable elements and log them."""
    from selenium.webdriver.common.by import By

    logger.info("-" * 40)
    logger.info("Discovering clickable elements...")
    logger.info("-" * 40)

    # Find elements with Chinese text that might be the "新的创作" button
    target_texts = ["新的创作", "新建", "创建", "开始创作", "新增", "添加"]

    for text in target_texts:
        logger.info(f"Searching for elements with text: {text}")

        # XPath search
        try:
            elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{text}')]")
            if elements:
                logger.info(f"  Found {len(elements)} elements via XPath:")
                for i, el in enumerate(elements[:5]):
                    tag = el.tag_name
                    classes = el.get_attribute("class") or ""
                    is_displayed = el.is_displayed()
                    is_enabled = el.is_enabled()
                    rect = el.rect
                    logger.info(f"    [{i+1}] <{tag}> class='{classes[:60]}' displayed={is_displayed} enabled={is_enabled} rect={rect}")
        except Exception as e:
            logger.debug(f"  XPath search failed: {e}")

    # Find all buttons
    logger.info("\nAll visible buttons:")
    try:
        buttons = driver.find_elements(By.TAG_NAME, "button")
        visible_buttons = [b for b in buttons if b.is_displayed()]
        for i, btn in enumerate(visible_buttons[:20]):
            text = btn.text.strip()[:40] if btn.text else "(no text)"
            classes = btn.get_attribute("class") or ""
            logger.info(f"  Button {i+1}: '{text}' class='{classes[:50]}'")
    except Exception as e:
        logger.error(f"Error finding buttons: {e}")

    # Find elements with specific class patterns
    class_patterns = ["create", "new", "add", "publish", "btn", "button", "action"]
    logger.info("\nElements with action-related classes:")
    for pattern in class_patterns:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, f"[class*='{pattern}']")
            clickable = [e for e in elements if e.is_displayed() and e.tag_name in ['button', 'a', 'div', 'span']]
            if clickable:
                logger.info(f"  Pattern '{pattern}': {len(clickable)} clickable elements")
                for el in clickable[:3]:
                    text = el.text.strip()[:30] if el.text else ""
                    logger.info(f"    - <{el.tag_name}> '{text}'")
        except Exception:
            pass


def test_click_strategies(publisher: XHSPublisher, selector: str, description: str):
    """Test different click strategies for an element."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.action_chains import ActionChains

    driver = publisher.driver

    logger.info(f"\nTesting click strategies for: {description}")
    logger.info(f"Selector: {selector}")

    strategies = [
        ("Normal click", lambda el: el.click()),
        ("JavaScript click", lambda el: driver.execute_script("arguments[0].click();", el)),
        ("Action chains click", lambda el: ActionChains(driver).move_to_element(el).click().perform()),
        ("Scroll + click", lambda el: (driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", el), time.sleep(0.5), el.click())),
    ]

    for strategy_name, click_fn in strategies:
        try:
            element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, selector))
            )

            if element.is_displayed():
                logger.info(f"  [{strategy_name}] Element found, attempting click...")
                click_fn(element)
                logger.info(f"  [{strategy_name}] Click successful!")
                time.sleep(1)
                return True
            else:
                logger.warning(f"  [{strategy_name}] Element found but not displayed")
        except Exception as e:
            logger.warning(f"  [{strategy_name}] Failed: {str(e)[:100]}")

    return False


def test_publish_flow(publisher: XHSPublisher, mode: PublishMode):
    """Test a full publish flow (without actually publishing)."""
    logger.info("=" * 60)
    logger.info(f"Testing publish flow: {mode.value}")
    logger.info("=" * 60)

    # Create test content
    test_content = Content(
        id=999,
        title="测试标题 - Test Title",
        body="这是测试正文内容。\n\n第二段测试内容。\n\n第三段测试内容。",
        images=[],
        source=ContentSource.MANUAL,
        status=ContentStatus.APPROVED,
        publish_mode=mode,
        created_at="2024-01-01T00:00:00",
        published_at=None,
        error_message=None,
    )

    # Navigate to the appropriate page
    if mode == PublishMode.IMAGE_TEXT_UPLOAD:
        result = publisher._navigate_to_image_text_upload()
    elif mode == PublishMode.IMAGE_TEXT_COMPOSE:
        result = publisher._navigate_to_image_text_compose()
    elif mode == PublishMode.LONG_ARTICLE:
        result = publisher._navigate_to_long_article()
    else:
        logger.error(f"Unknown mode: {mode}")
        return False

    if not result:
        logger.error(f"Navigation failed for mode: {mode}")
        # Take screenshot for debugging
        publisher.driver.save_screenshot(f"logs/failed_navigation_{mode.value}.png")
        return False

    logger.info(f"Navigation successful for mode: {mode.value}")

    # Try to fill title
    logger.info("Attempting to fill title...")
    if publisher._fill_title(test_content.title):
        logger.info("Title filled successfully!")
    else:
        logger.warning("Failed to fill title")
        publisher.driver.save_screenshot(f"logs/failed_title_{mode.value}.png")

    # Take success screenshot
    publisher.driver.save_screenshot(f"logs/success_{mode.value}.png")

    return True


def main():
    """Main test function."""
    setup_logging()

    logger.info("=" * 60)
    logger.info("XHS Publisher Test Suite")
    logger.info("=" * 60)

    # Ensure logs directory exists
    Path("logs").mkdir(exist_ok=True)

    result = test_login_and_navigate()
    if not result:
        logger.error("Login/navigation test failed!")
        return

    publisher, auth_manager = result

    try:
        # Test element discovery
        test_element_discovery(publisher)

        # Test publish flows for each mode
        for mode in [PublishMode.IMAGE_TEXT_UPLOAD, PublishMode.LONG_ARTICLE]:
            test_publish_flow(publisher, mode)
            time.sleep(2)

        logger.info("=" * 60)
        logger.info("Test suite completed!")
        logger.info("Check logs/screenshot_*.png for visual debugging")
        logger.info("=" * 60)

        # Keep browser open for manual inspection
        input("Press Enter to close browser...")

    finally:
        auth_manager.close()


if __name__ == "__main__":
    main()
