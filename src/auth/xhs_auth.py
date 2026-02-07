"""
Xiaohongshu authentication manager using Selenium.
Handles login via SMS or QR code and session persistence.
"""
import sys
import asyncio
import json
import random
import time
import pickle
from pathlib import Path
from typing import Optional, Literal
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from loguru import logger


class XHSAuthManager:
    """Manages authentication to Xiaohongshu Creator Center using Selenium."""

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

        # Ensure session directory exists
        Path(session_file).parent.mkdir(parents=True, exist_ok=True)
    
    def _random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Add random human-like delay."""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)
    
    def _init_browser(self, headless: bool = False):
        """Initialize Selenium Chrome browser with stealth settings."""
        chrome_options = Options()
        
        if headless:
            chrome_options.add_argument('--headless=new')
        
        # Stealth settings
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Exclude automation flags
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Initialize driver with webdriver-manager
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Execute CDP commands to hide webdriver
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            '''
        })
        
        logger.info("Browser initialized with stealth settings (Selenium)")

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
            logger.info(f"Session saved to {self.cookies_file}")
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
            for cookie in cookies:
                try:
                    self.driver.add_cookie(cookie)
                    loaded_count += 1
                except Exception as e:
                    # Only log debug level for individual cookie failures
                    logger.debug(f"Skipped cookie: {e}")

            if loaded_count > 0:
                logger.info(f"Loaded {loaded_count}/{len(cookies)} cookies from {self.cookies_file}")
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
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div[class*="user"], div[class*="avatar"], a[class*="profile"]'))
                )
                logger.info("Already logged in (found user elements)")
                self._logged_in = True
                return True
            except Exception:
                pass

            logger.info("Not logged in")
            self._logged_in = False
            return False

        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            self._logged_in = False
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
            self._random_delay()
            
            # Click SMS login tab
            try:
                sms_tab = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '//div[contains(@class, "sms")] | //button[contains(text(), "短信登录")] | //a[contains(text(), "手机号登录")]'))
                )
                sms_tab.click()
                self._random_delay()
                logger.info("Clicked SMS login tab")
            except Exception:
                logger.warning("Could not find SMS login tab, assuming already on SMS login")
            
            # Enter phone number
            if self.phone_number:
                phone_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, '//input[@type="tel"] | //input[contains(@placeholder, "手机号")] | //input[contains(@name, "phone")]'))
                )
                phone_input.send_keys(self.phone_number)
                self._random_delay(0.5, 1.0)
                logger.info(f"Entered phone number: {self.phone_number[:3]}****{self.phone_number[-2:]}")
            else:
                logger.info("Waiting for user to enter phone number manually...")
                WebDriverWait(self.driver, 60).until(
                    EC.presence_of_element_located((By.XPATH, '//input[@type="tel" and @value!=""]'))
                )
            
            # Click send verification code button
            send_code_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "获取验证码")] | //button[contains(text(), "发送验证码")] | //button[contains(@class, "send")]'))
            )
            send_code_btn.click()
            self._random_delay(1, 2)
            logger.info("Clicked send verification code button")
            
            # Handle verification code
            if verification_code:
                code_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, '//input[contains(@placeholder, "验证码")] | //input[contains(@name, "code")]'))
                )
                code_input.send_keys(verification_code)
                self._random_delay(0.5, 1.0)
                logger.info("Entered verification code")
                
                # Click login button
                login_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "登录")] | //button[@type="submit"]'))
                )
                login_btn.click()
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
                return True
            else:
                logger.error("SMS login failed - still on login page")
                self._logged_in = False
                return False

        except Exception as e:
            logger.error(f"SMS login error: {e}")
            self._logged_in = False
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
            
            # Click QR login tab
            try:
                qr_tab = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '//div[contains(@class, "qr")] | //button[contains(text(), "二维码登录")] | //a[contains(text(), "扫码登录")]'))
                )
                qr_tab.click()
                self._random_delay()
                logger.info("Clicked QR code login tab")
            except Exception as e:
                logger.warning(f"Could not find QR login tab: {e}")
                logger.info("Assuming already on QR login page")
            
            # Wait for QR code to appear
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, '//img[contains(@class, "qr")] | //canvas[contains(@class, "qr")] | //div[contains(@class, "qrcode")]'))
                )
                logger.info("QR code displayed - please scan with Xiaohongshu mobile app")
            except Exception as e:
                logger.error(f"QR code not found: {e}")
                logger.info("Continuing anyway, user may need to manually navigate")
            
            # Wait for login completion (URL changes)
            logger.info("Waiting for QR code scan (up to 2 minutes)...")
            try:
                WebDriverWait(self.driver, 120).until(
                    lambda d: 'login' not in d.current_url.lower()
                )
                logger.info("URL changed, checking login status")
            except Exception as e:
                logger.warning(f"Timeout or error waiting for QR scan: {e}")
            
            self._random_delay(2, 3)

            # Verify login success by checking URL
            try:
                current_url = self.driver.current_url
                if 'login' not in current_url.lower():
                    logger.info("QR code login successful!")
                    self._logged_in = True
                    self._save_session()
                    return True
                else:
                    logger.error("QR code login failed - still on login page")
                    self._logged_in = False
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
    
    def close(self):
        """Close browser and cleanup."""
        if self.driver:
            self.driver.quit()
            logger.info("Browser closed")
    
    def get_driver(self) -> Optional[webdriver.Chrome]:
        """Get the current driver instance for publishing operations."""
        if self._is_driver_alive():
            return self.driver
        return None
