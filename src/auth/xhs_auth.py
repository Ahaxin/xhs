"""
Xiaohongshu authentication manager using Selenium.
Handles login via SMS or QR code and session persistence.

Enhanced with:
- Better stealth settings to avoid detection
- Improved error handling and recovery
- Screenshot capture for debugging
- More robust cookie management
- Browser fingerprint randomization
"""
import sys
import asyncio
import json
import random
import time
import pickle
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal, List, Dict
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchElementException,
    StaleElementReferenceException,
)
from webdriver_manager.chrome import ChromeDriverManager
from loguru import logger


class XHSAuthManager:
    """Manages authentication to Xiaohongshu Creator Center using Selenium."""

    # Screenshot directory
    SCREENSHOT_DIR = Path("logs/screenshots")

    # User agents rotation pool
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    def __init__(
        self,
        creator_url: str = "https://creator.xiaohongshu.com",
        session_file: str = "data/xhs_session.json",
        login_method: Literal["sms", "qr_code"] = "sms",
        phone_number: str = "",
    ):
        self.creator_url = creator_url
        self.session_file = session_file
        self.cookies_file = session_file.replace('.json', '_cookies.pkl')
        self.login_method = login_method
        self.phone_number = phone_number
        self.driver: Optional[webdriver.Chrome] = None
        self._logged_in: bool = False  # Cached login state

        # Ensure directories exist
        Path(session_file).parent.mkdir(parents=True, exist_ok=True)
        self.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    def _take_screenshot(self, name: str) -> str:
        """Take a screenshot for debugging purposes."""
        if not self.driver:
            return ""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_auth_{name}.png"
            filepath = self.SCREENSHOT_DIR / filename
            self.driver.save_screenshot(str(filepath))
            logger.info(f"Screenshot saved: {filepath}")
            return str(filepath)
        except Exception as e:
            logger.warning(f"Failed to save screenshot: {e}")
            return ""

    def _random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Add random human-like delay."""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    def _get_random_user_agent(self) -> str:
        """Get a random user agent from the pool."""
        return random.choice(self.USER_AGENTS)

    def _init_browser(self, headless: bool = False):
        """Initialize Selenium Chrome browser with enhanced stealth settings."""
        chrome_options = Options()

        if headless:
            chrome_options.add_argument('--headless=new')

        # Enhanced stealth settings
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--start-maximized')

        # Randomized user agent
        user_agent = self._get_random_user_agent()
        chrome_options.add_argument(f'user-agent={user_agent}')

        # Additional stealth options
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--disable-popup-blocking')
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--allow-running-insecure-content')

        # Language and locale
        chrome_options.add_argument('--lang=zh-CN')
        chrome_options.add_experimental_option('prefs', {
            'intl.accept_languages': 'zh-CN,zh,en-US,en',
            'profile.default_content_setting_values.notifications': 2,
        })

        # Exclude automation flags
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # Initialize driver with webdriver-manager
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            logger.error(f"Failed to initialize Chrome driver: {e}")
            raise

        # Execute CDP commands to hide webdriver detection
        self._apply_stealth_scripts()

        logger.info(f"Browser initialized with stealth settings (UA: {user_agent[:50]}...)")

    def _apply_stealth_scripts(self):
        """Apply JavaScript to hide automation detection."""
        if not self.driver:
            return

        stealth_scripts = [
            # Hide webdriver property
            '''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            ''',
            # Hide automation-related properties
            '''
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            ''',
            # Hide languages
            '''
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en-US', 'en']
            });
            ''',
            # Override permissions query
            '''
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            ''',
            # Hide Chrome runtime
            '''
            window.chrome = {
                runtime: {}
            };
            ''',
            # Fix hairline feature
            '''
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8
            });
            ''',
            # Fix platform
            '''
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32'
            });
            ''',
        ]

        try:
            for script in stealth_scripts:
                self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                    'source': script
                })
        except Exception as e:
            logger.warning(f"Failed to apply some stealth scripts: {e}")

    def _is_driver_alive(self) -> bool:
        """Check if the WebDriver session is still valid."""
        if not self.driver:
            return False
        try:
            # Try a simple operation to verify connection
            _ = self.driver.current_url
            return True
        except Exception:
            return False

    def _ensure_driver(self, headless: bool = False):
        """Ensure driver is initialized and alive, reinitialize if needed."""
        if not self._is_driver_alive():
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None
            self._init_browser(headless=headless)

    def _save_session(self):
        """Save browser session (cookies)."""
        if not self.driver:
            logger.warning("No driver to save")
            return

        try:
            # Save cookies
            cookies = self.driver.get_cookies()
            with open(self.cookies_file, 'wb') as f:
                pickle.dump(cookies, f)

            # Also save as JSON for debugging
            json_file = self.cookies_file.replace('.pkl', '.json')
            cookies_json = []
            for cookie in cookies:
                # Make a serializable copy
                cookie_copy = {k: v for k, v in cookie.items() if k != 'expiry' or isinstance(v, (int, float))}
                cookies_json.append(cookie_copy)

            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(cookies_json, f, indent=2, ensure_ascii=False)

            logger.info(f"Session saved to {self.cookies_file} ({len(cookies)} cookies)")
        except Exception as e:
            logger.error(f"Failed to save session: {e}")

    def _load_session(self) -> bool:
        """Load saved browser session."""
        cookies_path = Path(self.cookies_file)
        if not cookies_path.exists():
            logger.info("No saved session found")
            return False

        # Check if driver is alive before attempting to load cookies
        if not self._is_driver_alive():
            logger.warning("Driver not alive, cannot load session")
            return False

        try:
            # Load cookies
            with open(cookies_path, 'rb') as f:
                cookies = pickle.load(f)

            if not cookies:
                logger.warning("Session file has no cookies")
                return False

            # Navigate to domain first
            self.driver.get(self.creator_url)
            self._random_delay(1, 2)

            # Add cookies (skip failures silently for non-critical cookies)
            loaded_count = 0
            failed_count = 0
            for cookie in cookies:
                try:
                    # Some cookies may have expired or be invalid
                    self.driver.add_cookie(cookie)
                    loaded_count += 1
                except Exception as e:
                    failed_count += 1
                    # Only log debug level for individual cookie failures
                    logger.debug(f"Skipped cookie {cookie.get('name', 'unknown')}: {e}")

            if loaded_count > 0:
                logger.info(f"Loaded {loaded_count}/{len(cookies)} cookies (skipped {failed_count})")
                return True
            else:
                logger.warning("No cookies could be loaded")
                return False
        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return False

    def is_logged_in(self, force_check: bool = False) -> bool:
        """
        Check if currently logged in to XHS Creator Center.

        Args:
            force_check: If True, navigate to check actual login status.
                        If False, return cached status (default).
        """
        # Check if driver is alive
        if not self._is_driver_alive():
            self._logged_in = False
            return False

        # Return cached status unless force_check is requested
        if not force_check:
            return self._logged_in

        try:
            # Navigate to creator center
            self.driver.get(self.creator_url)
            self._random_delay(2, 3)

            # Check URL (logged in users typically don't see login page)
            current_url = self.driver.current_url
            if 'login' not in current_url.lower():
                logger.info("Already logged in (no login page)")
                self._logged_in = True
                return True

            # Check for user-specific elements
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR,
                        'div[class*="user"], div[class*="avatar"], a[class*="profile"], [class*="account"]'
                    ))
                )
                logger.info("Already logged in (found user elements)")
                self._logged_in = True
                return True
            except TimeoutException:
                pass

            logger.info("Not logged in")
            self._logged_in = False
            return False

        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            self._logged_in = False
            return False

    def _wait_and_click(self, xpath: str, timeout: int = 10, description: str = "") -> bool:
        """Wait for element and click it with multiple strategies."""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )

            # Try normal click first
            try:
                element.click()
                if description:
                    logger.info(f"Clicked: {description}")
                return True
            except Exception:
                pass

            # Try JavaScript click as fallback
            try:
                self.driver.execute_script("arguments[0].click();", element)
                if description:
                    logger.info(f"Clicked (JS): {description}")
                return True
            except Exception:
                pass

            logger.warning(f"Could not click: {description}")
            return False

        except TimeoutException:
            logger.warning(f"Timeout waiting for: {description}")
            return False
        except Exception as e:
            logger.warning(f"Error clicking {description}: {e}")
            return False

    def _find_and_click_any(self, selectors: List[str], timeout: int = 10, description: str = "") -> bool:
        """Try multiple selectors and click the first one found."""
        for selector in selectors:
            if self._wait_and_click(selector, timeout=timeout, description=description):
                return True
        return False

    def login_sms(self, verification_code: Optional[str] = None) -> bool:
        """
        Login using SMS verification.

        Args:
            verification_code: If provided, will auto-fill. Otherwise, waits for user input.

        Returns:
            True if login successful
        """
        try:
            # Ensure browser is ready
            self._ensure_driver(headless=False)

            logger.info("Starting SMS login flow")
            self.driver.get(self.creator_url)
            self._random_delay(2, 4)

            # Take initial screenshot
            self._take_screenshot("sms_login_start")

            # Click SMS login tab - try multiple selectors
            sms_tab_selectors = [
                '//div[contains(@class, "sms")]',
                '//button[contains(text(), "短信登录")]',
                '//a[contains(text(), "手机号登录")]',
                '//div[contains(text(), "短信登录")]',
                '//span[contains(text(), "短信登录")]',
                '//*[contains(text(), "手机号")]',
            ]

            if not self._find_and_click_any(sms_tab_selectors, timeout=10, description="SMS login tab"):
                logger.warning("Could not find SMS login tab, assuming already on SMS login")

            self._random_delay(1, 2)

            # Enter phone number
            if self.phone_number:
                phone_selectors = [
                    '//input[@type="tel"]',
                    '//input[contains(@placeholder, "手机号")]',
                    '//input[contains(@name, "phone")]',
                    '//input[contains(@class, "phone")]',
                ]

                phone_input = None
                for selector in phone_selectors:
                    try:
                        phone_input = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, selector))
                        )
                        if phone_input.is_displayed():
                            break
                    except TimeoutException:
                        continue

                if phone_input:
                    phone_input.clear()
                    phone_input.send_keys(self.phone_number)
                    self._random_delay(0.5, 1.0)
                    logger.info(f"Entered phone number: {self.phone_number[:3]}****{self.phone_number[-2:]}")
                else:
                    logger.warning("Could not find phone input field")
            else:
                logger.info("Waiting for user to enter phone number manually...")
                WebDriverWait(self.driver, 60).until(
                    EC.presence_of_element_located((By.XPATH, '//input[@type="tel" and @value!=""]'))
                )

            # Click send verification code button
            send_code_selectors = [
                '//button[contains(text(), "获取验证码")]',
                '//button[contains(text(), "发送验证码")]',
                '//button[contains(@class, "send")]',
                '//span[contains(text(), "获取验证码")]',
                '//*[contains(text(), "获取")]',
            ]

            if not self._find_and_click_any(send_code_selectors, timeout=10, description="Send verification code"):
                logger.warning("Could not click send verification code button")

            self._random_delay(1, 2)
            logger.info("Clicked send verification code button")

            # Handle verification code
            if verification_code:
                code_selectors = [
                    '//input[contains(@placeholder, "验证码")]',
                    '//input[contains(@name, "code")]',
                    '//input[contains(@class, "code")]',
                ]

                code_input = None
                for selector in code_selectors:
                    try:
                        code_input = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, selector))
                        )
                        if code_input.is_displayed():
                            break
                    except TimeoutException:
                        continue

                if code_input:
                    code_input.send_keys(verification_code)
                    self._random_delay(0.5, 1.0)
                    logger.info("Entered verification code")

                # Click login button
                login_selectors = [
                    '//button[contains(text(), "登录")]',
                    '//button[@type="submit"]',
                    '//button[contains(@class, "login")]',
                ]
                self._find_and_click_any(login_selectors, timeout=5, description="Login button")
            else:
                logger.info("Waiting for user to enter verification code and click login...")
                # Wait for URL change (away from login page)
                WebDriverWait(self.driver, 120).until(
                    lambda d: 'login' not in d.current_url.lower()
                )

            self._random_delay(2, 3)

            # Verify login success by checking URL
            current_url = self.driver.current_url
            if 'login' not in current_url.lower():
                logger.info("SMS login successful!")
                self._logged_in = True
                self._save_session()
                self._take_screenshot("sms_login_success")
                return True
            else:
                logger.error("SMS login failed - still on login page")
                self._logged_in = False
                self._take_screenshot("sms_login_failed")
                return False

        except Exception as e:
            logger.error(f"SMS login error: {e}")
            self._logged_in = False
            self._take_screenshot("sms_login_error")
            return False

    def login_qr(self) -> bool:
        """
        Login using QR code.
        User must scan QR code with Xiaohongshu mobile app.

        Returns:
            True if login successful
        """
        try:
            # Ensure browser is ready
            self._ensure_driver(headless=False)

            logger.info("Starting QR code login flow")
            self.driver.get(self.creator_url)
            self._random_delay(2, 4)

            # Take initial screenshot
            self._take_screenshot("qr_login_start")

            # Click QR login tab - try multiple selectors
            qr_tab_selectors = [
                '//div[contains(@class, "qr")]',
                '//button[contains(text(), "二维码登录")]',
                '//a[contains(text(), "扫码登录")]',
                '//div[contains(text(), "二维码")]',
                '//span[contains(text(), "扫码")]',
                '//*[contains(text(), "二维码")]',
            ]

            if not self._find_and_click_any(qr_tab_selectors, timeout=10, description="QR code login tab"):
                logger.warning("Could not find QR login tab, assuming already on QR login")

            self._random_delay(1, 2)

            # Wait for QR code to appear
            qr_selectors = [
                '//img[contains(@class, "qr")]',
                '//canvas[contains(@class, "qr")]',
                '//div[contains(@class, "qrcode")]',
                '//img[contains(@src, "qr")]',
                '//*[contains(@class, "qr-code")]',
            ]

            qr_found = False
            for selector in qr_selectors:
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    qr_found = True
                    break
                except TimeoutException:
                    continue

            if qr_found:
                logger.info("QR code displayed - please scan with Xiaohongshu mobile app")
                self._take_screenshot("qr_code_displayed")
            else:
                logger.warning("QR code not found, continuing anyway")
                self._take_screenshot("qr_code_not_found")

            # Wait for login completion (URL changes)
            logger.info("Waiting for QR code scan (up to 2 minutes)...")
            try:
                WebDriverWait(self.driver, 120).until(
                    lambda d: 'login' not in d.current_url.lower()
                )
                logger.info("URL changed, checking login status")
            except TimeoutException:
                logger.warning("Timeout waiting for QR scan")
                self._take_screenshot("qr_scan_timeout")

            self._random_delay(2, 3)

            # Verify login success by checking URL
            try:
                current_url = self.driver.current_url
                if 'login' not in current_url.lower():
                    logger.info("QR code login successful!")
                    self._logged_in = True
                    self._save_session()
                    self._take_screenshot("qr_login_success")
                    return True
                else:
                    logger.error("QR code login failed - still on login page")
                    self._logged_in = False
                    self._take_screenshot("qr_login_failed")
                    return False
            except Exception as e:
                logger.error(f"Error verifying login status: {e}")
                self._logged_in = False
                return False

        except Exception as e:
            logger.error(f"QR code login error: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            self._logged_in = False
            self._take_screenshot("qr_login_error")
            return False

    def login(self, verification_code: Optional[str] = None) -> bool:
        """
        Login using configured method (SMS or QR code).

        Args:
            verification_code: For SMS login only

        Returns:
            True if login successful
        """
        # Ensure browser is initialized and alive
        self._ensure_driver(headless=False)

        # Try loading existing session first
        session_loaded = self._load_session()

        if session_loaded:
            # Check if session is still valid (force check since we just loaded session)
            if self.is_logged_in(force_check=True):
                logger.info("Logged in using saved session")
                self._logged_in = True
                return True
            else:
                logger.info("Saved session expired, need fresh login")

        # Perform fresh login
        if self.login_method == "sms":
            return self.login_sms(verification_code)
        elif self.login_method == "qr_code":
            return self.login_qr()
        else:
            logger.error(f"Unknown login method: {self.login_method}")
            return False

    def refresh_page(self):
        """Refresh the current page."""
        if self._is_driver_alive():
            self.driver.refresh()
            self._random_delay(2, 3)

    def navigate_to(self, url: str):
        """Navigate to a specific URL."""
        if self._is_driver_alive():
            self.driver.get(url)
            self._random_delay(2, 3)

    def close(self):
        """Close browser and cleanup."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Browser closed")
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")
            finally:
                self.driver = None
                self._logged_in = False

    def get_driver(self) -> Optional[webdriver.Chrome]:
        """Get the current driver instance for publishing operations."""
        if self._is_driver_alive():
            return self.driver
        return None

    def get_current_url(self) -> str:
        """Get the current page URL."""
        if self._is_driver_alive():
            return self.driver.current_url
        return ""

    def get_page_source(self) -> str:
        """Get the current page source for debugging."""
        if self._is_driver_alive():
            return self.driver.page_source
        return ""
