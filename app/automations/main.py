import time
import random
import os
import logging
import traceback
from datetime import datetime
import subprocess
import signal
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException, StaleElementReferenceException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import chromedriver_autoinstaller
import json
import shutil

from chrome_extension_python import Extension
from app.automations.comments import comment_on_some_tasks
from app import data_manager as dm

# Detect environment
IS_GCP = os.environ.get('IS_GCP', 'false').lower() in ('true', '1', 't')
IS_CLOUD = os.environ.get('IS_CLOUD', 'false').lower() in ('true', '1', 't') or IS_GCP
IS_HEADLESS = os.environ.get('SELENIUM_HEADLESS', 'false').lower() in ('true', '1', 't') 
IS_DOCKER = os.path.exists('/.dockerenv') or os.environ.get('IS_DOCKER', 'false').lower() in ('true', '1', 't')

# Set data directory based on environment
DATA_DIR = os.environ.get('DATA_DIR', '/app/data' if IS_DOCKER else os.path.join(os.getcwd(), 'data'))
LOG_DIR = os.path.join(DATA_DIR, 'logs')
SCREENSHOT_DIR = os.path.join(DATA_DIR, 'screenshots')

# Ensure directories exist
try:
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    print(f"Created directories: LOG_DIR={LOG_DIR}, SCREENSHOT_DIR={SCREENSHOT_DIR}")
except Exception as e:
    print(f"Warning: Could not create directories: {str(e)}")
    # Fallback to current directory if needed
    if not os.path.exists(LOG_DIR):
        LOG_DIR = os.path.join(os.getcwd(), 'logs')
        os.makedirs(LOG_DIR, exist_ok=True)
    if not os.path.exists(SCREENSHOT_DIR):
        SCREENSHOT_DIR = os.path.join(os.getcwd(), 'screenshots')
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Set up logging
try:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(LOG_DIR, 'automation.log'))
        ]
    )
except Exception as e:
    # Fallback to console-only logging if file logging fails
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    print(f"Warning: Could not set up file logging: {str(e)}")

logger = logging.getLogger(__name__)

# Log environment information
logger.info(f"Environment: GCP={IS_GCP}, Cloud={IS_CLOUD}, Headless={IS_HEADLESS}, Docker={IS_DOCKER}")
logger.info(f"Data directory: {DATA_DIR}")
logger.info(f"Log directory: {LOG_DIR}")
logger.info(f"Screenshot directory: {SCREENSHOT_DIR}")

# ------------------------------
# Basic user agents for stealth
# ------------------------------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
]


# ------------------------------
# Helper functions
# ------------------------------
def save_screenshot(driver, name_prefix, group_id=None):
    """
    Save a screenshot to the screenshots directory with timestamp
    """
    try:
        if driver is None:
            logger.error("Cannot save screenshot - driver is None")
            return None
        
        # Get screenshot dir from config or use default
        screenshots_dir = os.environ.get('SCREENSHOTS_DIR', 
                                      os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                                   'data', 'screenshots'))
        os.makedirs(screenshots_dir, exist_ok=True)
        
        # Create filename with timestamp
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"{name_prefix}_{timestamp}.png"
        filepath = os.path.join(screenshots_dir, filename)
        
        # Save screenshot
        driver.save_screenshot(filepath)
        logger.info(f"Screenshot saved: {filename}")
        if group_id:
            dm.add_log(f"Screenshot saved: {filename}", "info", group_id=group_id, category='automation')
        
        return filepath
    except Exception as e:
        logger.error(f"Failed to save screenshot: {str(e)}")
        if group_id:
            dm.add_log(f"Failed to save screenshot: {str(e)}", "error", group_id=group_id, category='automation')
        return None


# ------------------------------
# Clean up Chrome processes
# ------------------------------
def cleanup_chrome_processes():
    """
    Attempt to clean up any lingering Chrome processes
    """
    try:
        if os.name == 'posix':  # Linux/Mac
            logger.info("Checking for Chrome processes to clean up...")
            # ps command for process listing
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            
            # Parse the output to find Chrome processes
            chrome_pids = []
            for line in result.stdout.split('\n'):
                if 'chrome' in line.lower() and 'defunct' not in line:
                    parts = line.split()
                    if len(parts) > 1:
                        try:
                            pid = int(parts[1])
                            chrome_pids.append(pid)
                        except ValueError:
                            continue
            
            # Kill the processes
            for pid in chrome_pids:
                try:
                    logger.info(f"Killing Chrome process with PID {pid}")
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    logger.warning(f"Process {pid} no longer exists")
                except PermissionError:
                    logger.warning(f"No permission to kill process {pid}")
            
            if chrome_pids:
                logger.info(f"Killed {len(chrome_pids)} Chrome processes")
            else:
                logger.info("No Chrome processes found to clean up")
                
        elif os.name == 'nt':  # Windows
            try:
                subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], check=False)
                logger.info("Chrome processes terminated on Windows")
            except Exception as e:
                logger.warning(f"Failed to terminate Chrome processes on Windows: {e}")
    except Exception as e:
        logger.error(f"Error cleaning up Chrome processes: {e}")


# ------------------------------
# Clear Chrome cache files
# ------------------------------
def clear_chrome_cache():
    """
    Clear Chrome cache directories to prevent corruption
    """
    try:
        # Get Chrome cache directories based on platform
        if os.name == 'win32':
            # Windows
            appdata = os.environ.get('LOCALAPPDATA')
            if appdata:
                chrome_cache = os.path.join(appdata, 'Google', 'Chrome', 'User Data', 'Default', 'Cache')
                if os.path.exists(chrome_cache):
                    shutil.rmtree(chrome_cache, ignore_errors=True)
        elif os.name == 'darwin':
            # macOS
            home = os.environ.get('HOME')
            if home:
                chrome_cache = os.path.join(home, 'Library', 'Caches', 'Google', 'Chrome')
                if os.path.exists(chrome_cache):
                    shutil.rmtree(chrome_cache, ignore_errors=True)
        else:
            # Linux
            home = os.environ.get('HOME')
            if home:
                chrome_cache = os.path.join(home, '.cache', 'google-chrome')
                if os.path.exists(chrome_cache):
                    shutil.rmtree(chrome_cache, ignore_errors=True)
                    
        # Also clear /tmp directory Chrome files
        for tmp_dir in ['/tmp', '/var/tmp']:
            if os.path.exists(tmp_dir):
                for filename in os.listdir(tmp_dir):
                    if 'chrome' in filename.lower() or 'chromium' in filename.lower():
                        try:
                            file_path = os.path.join(tmp_dir, filename)
                            if os.path.isdir(file_path):
                                shutil.rmtree(file_path, ignore_errors=True)
                            else:
                                os.remove(file_path)
                        except:
                            pass

        logger.info("Chrome cache cleared")
    except Exception as e:
        logger.warning(f"Error clearing Chrome cache: {str(e)}")


# ------------------------------
# Get Chrome options for current environment
# ------------------------------
def get_chrome_options():
    """
    Configure Chrome options with proper settings for stability
    """
    # Pick a random user agent
    user_agent = random.choice(USER_AGENTS)
    
    # Get additional Chrome arguments from environment, if any
    chrome_args = os.environ.get('CHROME_ARGS', '')
    
    chrome_options = Options()
    # Set user agent
    chrome_options.add_argument(f"--user-agent={user_agent}")
    
    # Anti-detection settings
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-infobars")
    
    # Basic stability options
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    
    # Use a custom temporary directory for crash dumps
    chrome_tmp_dir = '/tmp/chrome'
    if not os.path.exists(chrome_tmp_dir):
        os.makedirs(chrome_tmp_dir, exist_ok=True)
    chrome_options.add_argument(f"--crash-dumps-dir={chrome_tmp_dir}")
    chrome_options.add_argument(f"--user-data-dir={chrome_tmp_dir}/profile")
    
    # Set a fixed window size for consistency
    chrome_options.add_argument("--window-size=1280,800")
    
    # Enable remote debugging on a fixed port
    chrome_options.add_argument("--remote-debugging-port=9222")
    
    # Better memory management
    chrome_options.add_argument("--aggressive-cache-discard")
    chrome_options.add_argument("--disable-application-cache")
    chrome_options.add_argument("--disable-offline-load-stale-cache")
    chrome_options.add_argument("--disk-cache-size=0")
    chrome_options.add_argument("--media-cache-size=0")
    
    # Add arguments from environment
    if chrome_args:
        for arg in chrome_args.split():
            if arg.strip():
                chrome_options.add_argument(arg.strip())
    
    # Check if we should run in headless mode
    headless = os.environ.get('SELENIUM_HEADLESS', 'false').lower() in ('true', '1', 'yes')
    if headless:
        # Use new headless mode for better compatibility
        chrome_options.add_argument("--headless=new")
        logger.info("Chrome configured to run in headless mode")
    
    return chrome_options


# ------------------------------
# Captcha solver extension class
# ------------------------------
class Capsolver(Extension):
    def __init__(self, api_key):
        super().__init__(
            extension_id="pgojnojmmhpofjgdmaebadhbocahppod",  # extension ID from Chrome Webstore
            extension_name="capsolver",
            api_key=api_key,
        )

    def update_files(self, api_key):
        js_files = self.get_js_files()

        def update_js_contents(content):
            to_replace = "return e.defaultConfig"
            replacement = f"return {{ ...e.defaultConfig, apiKey: '{api_key}' }}"
            return content.replace(to_replace, replacement)

        for file in js_files:
            file.update_contents(update_js_contents)

        def update_config_contents(content):
            return content.replace("apiKey: '',", f"apiKey: '{api_key}',")

        config_file = self.get_file("/assets/config.js")
        config_file.update_contents(update_config_contents)


# ------------------------------
# Initialize the Selenium driver
# ------------------------------
def init_driver(group_id=None):
    """
    Initialize the Chrome WebDriver with robust error handling and retries
    """
    # Clear any existing Chrome processes and cache
    cleanup_chrome_processes()
    clear_chrome_cache()
    
    driver = None
    max_retries = 3
    retry_count = 0
    last_exception = None
    
    while retry_count < max_retries:
        try:
            # Log initialization attempt
            logger.info(f"Initializing Chrome driver (attempt {retry_count + 1}/{max_retries})")
            if group_id:
                dm.add_log(f"Initializing Chrome driver (attempt {retry_count + 1}/{max_retries})", "info", group_id=group_id, category="setup")
            
            # Get configured Chrome options
            chrome_options = get_chrome_options()
            
            # Add captcha solver extension
            api_key = os.environ.get('CAPSOLVER_API_KEY', 'CAP-F79C6D0E7A810348A201783E25287C6003CFB45BBDCB670F96E525E7C0132148')
            logger.info("Loading Capsolver extension")
            if group_id:
                dm.add_log("Loading Capsolver extension", "info", group_id=group_id, category="setup")
            chrome_options.add_argument(
                Capsolver(api_key).load()
            )
            
            # Install chromedriver if not present
            chromedriver_path = chromedriver_autoinstaller.install()
            logger.info(f"ChromeDriver installed at: {chromedriver_path}")
            if group_id:
                dm.add_log(f"ChromeDriver installed at: {chromedriver_path}", "info", group_id=group_id, category="setup")
            
            # Create service with longer timeout
            service = Service(chromedriver_path)
            
            # Initialize WebDriver
            logger.info("Creating Chrome WebDriver instance...")
            if group_id:
                dm.add_log("Creating Chrome WebDriver instance...", "info", group_id=group_id, category="setup")
            
            driver = webdriver.Chrome(
                service=service, 
                options=chrome_options
            )
            
            # Set script timeout to avoid hanging
            driver.set_script_timeout(30)
            driver.set_page_load_timeout(60)
            
            # Test driver with a blank page
            logger.info("Testing WebDriver with blank page...")
            if group_id:
                dm.add_log("Testing WebDriver with blank page...", "info", group_id=group_id, category="setup")
            driver.get("about:blank")
            time.sleep(2)
            
            # Success if we reach here
            logger.info("Chrome driver initialized successfully")
            if group_id:
                dm.add_log("Chrome driver initialized successfully", "success", group_id=group_id, category="setup")
            return driver
            
        except Exception as e:
            last_exception = e
            # Handle different error types
            if "DevToolsActivePort file doesn't exist" in str(e):
                error_msg = f"Chrome DevTools error: DevToolsActivePort file doesn't exist. This often happens in Docker containers. Adding additional flags."
                # Add more specific flags to help with this error
                os.environ['CHROME_ARGS'] = '--no-sandbox --disable-dev-shm-usage --remote-debugging-port=9222'
            else:
                error_msg = f"Error initializing Chrome driver: {str(e)}"
            
            logger.error(error_msg)
            if group_id:
                dm.add_log(error_msg, "error", group_id=group_id, category="essential")
            
            # Close driver if it was partially initialized
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            
            logger.info(f"Retrying in 5 seconds...")
            if group_id:
                dm.add_log(f"Retrying in 5 seconds...", "info", group_id=group_id, category="setup")
            time.sleep(5)
            retry_count += 1
    
    # If we reach here, all retries failed
    error_msg = f"Failed to initialize Chrome driver after {max_retries} attempts: {str(last_exception)}"
    logger.error(error_msg)
    if group_id:
        dm.add_log(error_msg, "error", group_id=group_id, category="essential")
        # Add stack trace for detailed debugging
        dm.add_log(f"Detailed error: {traceback.format_exc()}", "error", group_id=group_id, category="essential")
    raise Exception(error_msg)


# ------------------------------
# Login function with robust error handling
# ------------------------------
def login(driver, email, password,
          login_button_xpath,
          email_input_id,
          password_input_id,
          submit_button_xpath,
          group_id=None):
    """
    Enhanced login function with robust captcha handling and detailed logging
    """
    try:
        logger.info("Starting login process...")
        if group_id:
            dm.add_log("Starting login process...", "info", group_id=group_id, category="automation")
        
        # Navigate directly to login page instead of clicking a button
        # This is more reliable in headless mode and different environments
        logger.info("Navigating directly to the login page")
        if group_id:
            dm.add_log("Navigating directly to the login page", "info", group_id=group_id, category="automation")
        driver.get("https://www.airtasker.com/login")
        
        # Wait for login page to fully load
        time.sleep(random.uniform(15, 20))  # Allow more time for Capsolver to initialize
        
        # Take screenshot of login page
        save_screenshot(driver, "login_page", group_id)
        
        # Check if captcha is present by looking for iframe
        captcha_iframes = driver.find_elements(By.XPATH, "//iframe[contains(@src, 'recaptcha') or contains(@src, 'hcaptcha')]")
        if captcha_iframes:
            logger.info(f"Captcha detected ({len(captcha_iframes)} iframes). Waiting for Capsolver...")
            if group_id:
                dm.add_log(f"Captcha detected ({len(captcha_iframes)} iframes). Waiting for Capsolver...", "info", group_id=group_id, category="automation")
            # Wait additional time for Capsolver to handle the captcha
            time.sleep(random.uniform(10, 15))
        
        # Type the email with detailed error handling
        try:
            logger.info(f"Entering email: {email[:3]}...{email[-5:]}")
            if group_id:
                dm.add_log(f"Entering email: {email[:3]}...{email[-5:]}", "info", group_id=group_id, category="automation")
            email_field = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.ID, email_input_id))
            )
            email_field.clear()
            for c in email:
                email_field.send_keys(c)
                time.sleep(random.uniform(0.04, 0.12))
        except Exception as e:
            logger.error(f"Failed to enter email: {str(e)}")
            if group_id:
                dm.add_log(f"Failed to enter email: {str(e)}", "error", group_id=group_id, category="essential")
            save_screenshot(driver, "email_input_error", group_id)
            raise Exception(f"Could not enter email: {str(e)}")
        
        # Type the password with error handling
        try:
            logger.info("Entering password")
            if group_id:
                dm.add_log("Entering password", "info", group_id=group_id, category="automation")
            password_field = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.ID, password_input_id))
            )
            password_field.clear()
            for c in password:
                password_field.send_keys(c)
                time.sleep(random.uniform(0.04, 0.1))
        except Exception as e:
            logger.error(f"Failed to enter password: {str(e)}")
            if group_id:
                dm.add_log(f"Failed to enter password: {str(e)}", "error", group_id=group_id, category="essential")
            save_screenshot(driver, "password_input_error", group_id)
            raise Exception(f"Could not enter password: {str(e)}")
        
        # Additional wait for captcha to be resolved
        logger.info("Waiting for captcha to be resolved by Capsolver...")
        if group_id:
            dm.add_log("Waiting for captcha to be resolved by Capsolver...", "info", group_id=group_id, category="automation")
        time.sleep(random.uniform(5, 10))
        
        # Check if captcha is still present
        captcha_iframes = driver.find_elements(By.XPATH, "//iframe[contains(@src, 'recaptcha') or contains(@src, 'hcaptcha')]")
        if captcha_iframes:
            logger.info("Captcha still present. Waiting additional time...")
            if group_id:
                dm.add_log("Captcha still present. Waiting additional time...", "info", group_id=group_id, category="automation")
            time.sleep(random.uniform(10, 15))
            save_screenshot(driver, "captcha_waiting", group_id)
        
        # Screenshot before clicking submit
        save_screenshot(driver, "before_submit", group_id)
        
        # Submit the login form with error handling
        try:
            logger.info("Clicking submit button")
            if group_id:
                dm.add_log("Clicking submit button", "info", group_id=group_id, category="automation")
            
            # Try standard click first
            try:
                submit_btn = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((By.XPATH, submit_button_xpath))
                )
                submit_btn.click()
            except Exception as e:
                logger.warning(f"Standard click failed: {str(e)}. Trying JavaScript click...")
                if group_id:
                    dm.add_log(f"Standard click failed: {str(e)}. Trying JavaScript click...", "warning", group_id=group_id, category="automation")
                
                # Try JavaScript click as fallback
                try:
                    driver.execute_script("arguments[0].click();", submit_btn)
                    logger.info("JavaScript click succeeded")
                    if group_id:
                        dm.add_log("JavaScript click succeeded", "info", group_id=group_id, category="automation")
                except Exception as js_error:
                    logger.error(f"JavaScript click also failed: {str(js_error)}")
                    if group_id:
                        dm.add_log(f"JavaScript click also failed: {str(js_error)}", "error", group_id=group_id, category="essential")
                    save_screenshot(driver, "submit_click_error", group_id)
        except Exception as outer_e:
            logger.error(f"Error during submit button handling: {str(outer_e)}")
            if group_id:
                dm.add_log(f"Error during submit button handling: {str(outer_e)}", "error", group_id=group_id, category="essential")
            save_screenshot(driver, "submit_handling_error", group_id)
        
        # Wait for post-login redirect
        logger.info("Waiting for post-login redirect...")
        if group_id:
            dm.add_log("Waiting for post-login redirect...", "info", group_id=group_id, category="automation")
        time.sleep(random.uniform(10, 15))
        
        # Take a screenshot of the result
        save_screenshot(driver, "after_login", group_id)
        
        # Check if login was successful by examining URL and elements
        current_url = driver.current_url
        logger.info(f"Current URL after login attempt: {current_url}")
        if group_id:
            dm.add_log(f"Current URL after login attempt: {current_url}", "info", group_id=group_id, category="automation")
        
        # Valid URLs after successful login
        success_url_patterns = [
            "airtasker.com/dashboard",
            "airtasker.com/discover",
            "airtasker.com/tasks",
            "airtasker.com/browse"
        ]
        
        # Check URL and look for avatar element as indication of success
        is_success_url = any(pattern in current_url for pattern in success_url_patterns)
        avatar_element = driver.find_elements(By.XPATH, '//button[contains(@class, "Avatar")]')
        
        if is_success_url and avatar_element:
            logger.info("Login successful: URL matches expected patterns and avatar element found")
            if group_id:
                dm.add_log("Login successful: URL matches expected patterns and avatar element found", "success", group_id=group_id, category="essential")
            return True
        elif is_success_url:
            logger.warning("URL indicates success but avatar element not found. Proceeding with caution.")
            if group_id:
                dm.add_log("URL indicates success but avatar element not found. Proceeding with caution.", "warning", group_id=group_id, category="essential")
            return True
        else:
            # Login failed
            error_message = f"Login failed: URL '{current_url}' does not match any success patterns and/or avatar element not found"
            logger.error(error_message)
            if group_id:
                dm.add_log(error_message, "error", group_id=group_id, category="essential")
            save_screenshot(driver, "login_failed", group_id)
            return False
    
    except Exception as e:
        logger.error(f"Login process failed: {str(e)}")
        if group_id:
            dm.add_log(f"Login process failed: {str(e)}", "error", group_id=group_id, category="essential")
        save_screenshot(driver, "login_exception", group_id)
        return False


# ------------------------------
# Set location filter function
# ------------------------------
def set_location_filter(driver, suburb_name, radius_km=100, group_id=None):
    try:
        dm.add_log(f"Setting location filter for {suburb_name} with radius {radius_km}km", "info", group_id=group_id)
        filter_button_xpath = '//*[@id="airtasker-app"]/nav/nav/div/div/div/div[3]/button'
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, filter_button_xpath))
            )
        except TimeoutException:
            save_screenshot(driver, "filter_button_not_found", group_id)
            dm.add_log("Filter button not found within 15s.", "error", group_id=group_id)
            return False

        driver.find_element(By.XPATH, filter_button_xpath).click()
        time.sleep(random.uniform(2, 4))

        suburb_input_xpath = '//*[@id="label-1"]'
        suburb_input = driver.find_element(By.XPATH, suburb_input_xpath)
        suburb_input.clear()
        for c in suburb_name:
            suburb_input.send_keys(c)
            time.sleep(random.uniform(0.04, 0.2))
        time.sleep(random.uniform(2, 3))

        first_item_xpath = '//*[@id="airtasker-app"]/nav/nav/div/div/div/div[3]/div/div[1]/div/div[4]/div/div/ul/li[1]'
        driver.find_element(By.XPATH, first_item_xpath).click()
        time.sleep(random.uniform(2, 3))

        try:
            slider_thumb_xpath = '//*[@id="airtasker-app"]/nav/nav/div/div/div/div[3]/div/div[1]/div/div[7]/div/div/button'
            slider_thumb = driver.find_element(By.XPATH, slider_thumb_xpath)
            # Example: adjust the slider based on radius (this formula may be refined)
            offset_px = int((radius_km / 100.0) * 100)
            ActionChains(driver).click_and_hold(slider_thumb).move_by_offset(offset_px, 0).release().perform()
            time.sleep(random.uniform(1, 2))
        except NoSuchElementException:
            dm.add_log("Slider not found. Skipping slider adjustment.", "warning", group_id=group_id)

        apply_button_xpath = '//*[@id="airtasker-app"]/nav/nav/div/div/div/div[3]/div/div[2]/button[2]'
        driver.find_element(By.XPATH, apply_button_xpath).click()
        time.sleep(random.uniform(3, 5))
        
        # Take screenshot after setting filter
        save_screenshot(driver, "location_filter_set", group_id)
        dm.add_log(f"Location filter set successfully for {suburb_name}", "info", group_id=group_id)
        return True
    except Exception as e:
        save_screenshot(driver, "filter_error", group_id)
        dm.add_log(f"Error setting location filter: {str(e)}", "error", group_id=group_id)
        return False


# ------------------------------
# Scrape tasks with infinite scroll
# ------------------------------
def scrape_tasks(driver, task_container_xpath, title_xpath, link_xpath, max_scroll=3, group_id=None):
    results = []
    seen_ids = set()
    
    dm.add_log(f"Starting to scrape tasks with max_scroll={max_scroll}", "info", group_id=group_id)
    
    for scroll_count in range(max_scroll):
        dm.add_log(f"Scroll iteration {scroll_count+1}/{max_scroll}", "info", group_id=group_id)
        containers = driver.find_elements(By.XPATH, task_container_xpath)
        dm.add_log(f"Found {len(containers)} task containers", "info", group_id=group_id)
        
        for c in containers:
            data_task_id = c.get_attribute("data-task-id")
            if data_task_id and data_task_id not in seen_ids:
                seen_ids.add(data_task_id)
                try:
                    title_txt = c.find_element(By.XPATH, title_xpath).text.strip()
                except NoSuchElementException:
                    title_txt = "Unknown Title"
                try:
                    link_url = c.find_element(By.XPATH, link_xpath).get_attribute("href")
                except NoSuchElementException:
                    link_url = None
                
                task_data = {
                    "id": data_task_id,
                    "title": title_txt,
                    "link": link_url,
                }
                results.append(task_data)
                dm.add_log(f"Added task: {title_txt}", "info", group_id=group_id)
                
        # Scroll down for more results
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(3, 5))
        
        # Take screenshot of tasks
        if scroll_count == 0:
            save_screenshot(driver, "tasks_view", group_id)
            
        # Check if we've reached the end
        new_containers = driver.find_elements(By.XPATH, task_container_xpath)
        if len(new_containers) == len(containers):
            dm.add_log("No more new tasks loaded. Stopping scroll.", "info", group_id=group_id)
            break
    
    dm.add_log(f"Scraped a total of {len(results)} tasks", "info", group_id=group_id)
    return results


# ------------------------------
# Main execution function
# ------------------------------
def run_airtasker_bot(email, password, city_name="Sydney", max_posts=3, message_content=None, group_id=None, headless=False):
    """
    Robust function to run the Airtasker bot with comprehensive error handling.
    
    Args:
        email: The user's email address
        password: The user's password
        city_name: The city to filter tasks by (default: Sydney)
        max_posts: Maximum number of posts to comment on
        message_content: Custom message to post (optional)
        group_id: Group ID for logging
        headless: Whether to run in headless mode
    
    Returns:
        tuple: (success, message)
    """
    driver = None
    
    try:
        # Log start of bot run
        dm.add_log(f"Starting Airtasker bot for {email} {'in headless mode' if headless else ''}", "info", group_id=group_id)
        
        if message_content:
            dm.add_log(f"Using message content: {message_content}", "info", group_id=group_id)
        
        dm.add_log(f"Starting bot for {email} in {city_name}", "info", group_id=group_id)
        dm.add_log(f"Bot started for {email} in {city_name} with max posts: {max_posts}", "info", group_id=group_id)
        
        # Take initial screenshot
        # We'll create this in the logs directory first since driver isn't available yet
        logs_dir = os.path.join(os.environ.get('DATA_DIR', '/app/data'), 'logs')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(logs_dir, f"startup_{timestamp}.log")
        os.makedirs(logs_dir, exist_ok=True)
        with open(log_file, "w") as f:
            f.write(f"Starting bot for {email} in {city_name} at {timestamp}\n")
        
        # Try to initialize the driver with multiple attempts if needed
        try:
            logger.info("Starting browser initialization...")
            driver = init_driver(group_id)
            logger.info("Browser initialized successfully")
            if group_id:
                dm.add_log("Browser initialized successfully", "info", group_id=group_id)
        except Exception as driver_error:
            error_msg = f"Failed to initialize browser: {str(driver_error)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            if group_id:
                dm.add_log(error_msg, "error", group_id=group_id)
                dm.add_log(f"Detailed error: {traceback.format_exc()}", "error", group_id=group_id)
            return False, error_msg
            
        # Initialize with clear logging
        driver.get("https://www.airtasker.com/")
        time.sleep(random.uniform(5, 8))
        
        # Take screenshot now that we have a driver
        save_screenshot(driver, "initial_page", group_id)
        
        # Credentials and login XPaths
        login_button_xpath = '//*[@id="airtasker-app"]/nav/div[2]/div/div/div/div[2]/a[2]'
        email_input_id = "username"
        password_input_id = "password"
        submit_button_xpath = "/html/body/main/section/div/div/div/form/div[2]/button"
        
        # 1. LOGIN (with URL verification)
        try:
            login_result = login(driver, email, password, login_button_xpath, email_input_id, password_input_id, submit_button_xpath, group_id=group_id)
            if not login_result:
                dm.add_log("Login process returned False", "error", group_id=group_id)
                return False, "Login failed"
            dm.add_log("Login successful", "success", group_id=group_id)
        except Exception as login_error:
            error_msg = f"Login error: {str(login_error)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            if group_id:
                dm.add_log(error_msg, "error", group_id=group_id)
            return False, error_msg
        
        # 2. Navigate to tasks page with retry
        max_retries = 3
        for retry in range(max_retries):
            try:
                tasks_page_url = "https://www.airtasker.com/tasks"
                dm.add_log(f"Navigating to tasks page: {tasks_page_url}", "info", group_id=group_id)
                driver.get(tasks_page_url)
                time.sleep(random.uniform(5, 8))
                current_url = driver.current_url
                dm.add_log(f"Current URL after navigation: {current_url}", "info", group_id=group_id)
                
                if "tasks" in current_url.lower():
                    dm.add_log("Successfully navigated to tasks page", "success", group_id=group_id)
                    break
                else:
                    dm.add_log(f"Unexpected URL after navigation (retry {retry+1}/{max_retries}): {current_url}", "warning", group_id=group_id)
                    if retry == max_retries - 1:
                        return False, "Failed to navigate to tasks page after multiple attempts"
                    time.sleep(random.uniform(3, 5))
            except Exception as nav_error:
                error_msg = f"Navigation error (retry {retry+1}/{max_retries}): {str(nav_error)}"
                dm.add_log(error_msg, "error", group_id=group_id)
                if retry == max_retries - 1:
                    return False, f"Failed to navigate to tasks page: {str(nav_error)}"
                time.sleep(random.uniform(3, 5))
        
        # 3. Set location filter
        try:
            radius_km = 100
            filter_result = set_location_filter(driver, city_name, radius_km, group_id=group_id)
            if not filter_result:
                dm.add_log("Location filter could not be set", "warning", group_id=group_id)
                # We'll continue anyway, as this isn't necessarily fatal
        except Exception as filter_error:
            error_msg = f"Error setting location filter: {str(filter_error)}"
            dm.add_log(error_msg, "warning", group_id=group_id)
            # We'll continue anyway, as this isn't necessarily fatal
        
        # 4. Scrape tasks
        try:
            task_container_xpath = '//a[@data-ui-test="task-list-item" and @data-task-id]'
            title_xpath = './/p[contains(@class,"TaskCard__StyledTitle")]'
            link_xpath = '.'
            
            dm.add_log("Starting to scrape tasks", "info", group_id=group_id)
            tasks = scrape_tasks(driver, task_container_xpath, title_xpath, link_xpath, max_scroll=5, group_id=group_id)
            
            if not tasks:
                dm.add_log("No tasks found to comment on", "warning", group_id=group_id)
                return False, "No tasks found to comment on"
                
            dm.add_log(f"Scraped {len(tasks)} tasks", "success", group_id=group_id)
        except Exception as scrape_error:
            error_msg = f"Error scraping tasks: {str(scrape_error)}"
            dm.add_log(error_msg, "error", group_id=group_id)
            return False, error_msg
        
        # 5. Post comments on a subset of tasks
        try:
            dm.add_log(f"Attempting to post on up to {max_posts} tasks", "info", group_id=group_id)
            posted_count = comment_on_some_tasks(driver, tasks, message_content=message_content, max_to_post=max_posts, image_path=None, group_id=group_id)
            
            if posted_count > 0:
                dm.add_log(f"Successfully posted {posted_count} comments", "success", group_id=group_id)
            else:
                dm.add_log("No comments were posted successfully", "warning", group_id=group_id)
        except Exception as comment_error:
            error_msg = f"Error posting comments: {str(comment_error)}"
            dm.add_log(error_msg, "error", group_id=group_id)
            return False, error_msg
        
        save_screenshot(driver, "completed", group_id)
        dm.add_log("Bot task completed successfully", "success", group_id=group_id)
        return True, "Bot completed successfully"
    
    except Exception as e:
        error_msg = f"Error in bot: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        if group_id:
            dm.add_log(error_msg, "error", group_id=group_id)
        return False, str(e)
    finally:
        # Always ensure the driver is closed properly
        if driver:
            try:
                logger.info("Closing browser")
                driver.quit()
                logger.info("Browser closed successfully")
                if group_id:
                    dm.add_log("Browser closed successfully", "info", group_id=group_id)
            except Exception as quit_error:
                logger.error(f"Error closing browser: {str(quit_error)}")
                if group_id:
                    dm.add_log(f"Error closing browser: {str(quit_error)}", "warning", group_id=group_id)
        
        # Final cleanup
        try:
            cleanup_chrome_processes()
        except:
            pass


# ------------------------------
# Main execution
# ------------------------------
def main():
    group_id = None
    driver = None
    
    try:
        # Setup logging for direct execution
        group_id = str(int(time.time()))  # Use timestamp as group_id
        
        # Initialize driver with the group_id
        driver = init_driver(group_id)
        driver.get("https://www.airtasker.com/")
        time.sleep(random.uniform(5, 8))
        
        try:
            # Credentials and login XPaths
            email = "Donnahartspare2000@gmail.com"
            password = "Cairns@2000"
            login_button_xpath = '//*[@id="airtasker-app"]/nav/div[2]/div/div/div/div[2]/a[2]'
            email_input_id = "username"
            password_input_id = "password"
            submit_button_xpath = "/html/body/main/section/div/div/div/form/div[2]/button"

            # 1. LOGIN (with URL verification)
            login(driver, email, password, login_button_xpath, email_input_id, password_input_id, submit_button_xpath, group_id=group_id)
            logger.info("Login successful.")

            time.sleep(5)
            # 2. Navigate to tasks page
            tasks_page_url = "https://www.airtasker.com/tasks"
            driver.get(tasks_page_url)
            time.sleep(random.uniform(5, 8))

            # 3. Set location filter
            city_name = "Sydney"
            radius_km = 100
            set_location_filter(driver, city_name, radius_km, group_id=group_id)
            logger.info("Location filter set.")

            # 4. Scrape tasks
            task_container_xpath = '//a[@data-ui-test="task-list-item" and @data-task-id]'
            title_xpath = './/p[contains(@class,"TaskCard__StyledTitle")]'
            link_xpath = '.'
            tasks = scrape_tasks(driver, task_container_xpath, title_xpath, link_xpath, max_scroll=5, group_id=group_id)
            logger.info(f"Scraped {len(tasks)} tasks:")
            for t in tasks[:5]:  # Log just the first 5 tasks
                logger.info(f"Task: {t.get('title')} (ID: {t.get('id')})")

            # 5. Post comments on a subset of tasks
            # Use a generic message for testing
            message = "Hey, you might get better quotes posting on the SmartTasker app. The fees are 25% less!"
            comment_on_some_tasks(driver, tasks, message_content=message, max_to_post=3, image_path=None, group_id=group_id)
            logger.info("Comments posted successfully")

        except Exception as e:
            logger.error(f"Error in main workflow: {str(e)}")
            logger.error(traceback.format_exc())
            if group_id:
                dm.add_log(f"Error in main workflow: {str(e)}", "error", group_id=group_id)
    finally:
        logger.info("Closing browser.")
        if driver:
            try:
                driver.quit()
            except:
                logger.error("Error closing browser")
        
        # Final cleanup
        try:
            cleanup_chrome_processes()
        except:
            pass


if __name__ == "__main__":
    main() 