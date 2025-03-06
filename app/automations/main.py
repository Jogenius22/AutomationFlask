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
    Take a screenshot of the current browser state and save it with a timestamp.
    Returns the filepath of the saved screenshot or None if failed.
    
    Parameters:
        driver: WebDriver - The Selenium WebDriver instance
        name_prefix: str - Prefix for the screenshot filename
        group_id: str - Optional group ID to include in the filename
    
    Returns:
        str or None: Path to the saved screenshot file, or None if it failed
    """
    if driver is None:
        print("Error: Cannot take screenshot - WebDriver is None")
        return None
        
    try:
        # Always use /tmp for screenshot storage in cloud environments
        screenshot_dir = os.environ.get('SCREENSHOT_DIR', '/tmp')
        
        # Ensure the directory exists
        try:
            os.makedirs(screenshot_dir, exist_ok=True)
        except Exception as e:
            print(f"Warning: Could not create screenshot directory: {e}")
            screenshot_dir = '/tmp'  # Fallback to /tmp
        
        # Create a unique filename with timestamp
        timestamp = int(time.time())
        group_suffix = f"_{group_id}" if group_id else ""
        filename = f"{name_prefix}{group_suffix}_{timestamp}.png"
        filepath = os.path.join(screenshot_dir, filename)
        
        # Take the screenshot with error handling
        driver.save_screenshot(filepath)
        print(f"✅ Screenshot saved successfully: {filepath}")
        return filepath
        
    except WebDriverException as e:
        print(f"❌ WebDriver error taking screenshot: {str(e)}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error taking screenshot: {str(e)}")
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
def get_chrome_options(headless=True):
    """
    Configure Chrome options with minimal optimized settings that work reliably in cloud environments.
    """
    options = Options()
    
    # Essential for running in Docker/Cloud environments
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    # Create and use a dedicated tmp directory for Chrome
    chrome_tmp_dir = '/tmp/chrome_data'
    os.makedirs(chrome_tmp_dir, exist_ok=True)
    
    # Set specific Chrome directories to prevent permission issues
    options.add_argument(f'--user-data-dir={chrome_tmp_dir}/profile')
    options.add_argument(f'--disk-cache-dir={chrome_tmp_dir}/cache')
    options.add_argument(f'--homedir={chrome_tmp_dir}')
    options.add_argument(f'--crash-dumps-dir={chrome_tmp_dir}/dumps')
    
    # Randomize user agent for stealth
    user_agent = random.choice(USER_AGENTS)
    options.add_argument(f'--user-agent={user_agent}')
    
    # Anti-detection settings
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Performance optimizations
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-infobars')
    options.add_argument('--mute-audio')
    options.add_argument('--disable-notifications')
    
    # Use classic headless mode instead of "new" headless which has compatibility issues
    if headless:
        options.add_argument('--headless')
    
    # Set window size
    options.add_argument('--window-size=1280,800')
    
    # Debugging settings
    options.add_argument('--disable-logging')
    options.add_argument('--log-level=3')
    options.add_argument('--silent')
    
    # Additional settings to handle cloud environment limitations
    options.page_load_strategy = 'eager'  # Don't wait for all resources to load
    
    return options


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
# Initialize the Selenium driver with robust error handling
# ------------------------------
def init_driver(group_id=None, headless=True):
    """
    Initialize Chrome WebDriver with robust error handling for cloud environments.
    Returns the driver instance or None if initialization fails.
    """
    print("Starting Chrome initialization...")
    driver = None
    
    try:
        # Clean up any existing Chrome processes that might interfere
        cleanup_chrome_processes()
        
        # Configure Chrome options
        chrome_options = get_chrome_options(headless=headless)
        
        # Try to add Capsolver extension - wrap in try/except to continue even if extension fails
        try:
            # Get API key from settings or use default
            api_key = "CAP-F79C6D0E7A810348A201783E25287C6003CFB45BBDCB670F96E525E7C0132148"
            extension_path = Capsolver(api_key).load()
            chrome_options.add_argument(extension_path)
            print("Added Capsolver extension successfully")
        except Exception as e:
            print(f"Warning: Failed to load Capsolver extension: {str(e)}")
            print("Will continue without Capsolver extension")
        
        # Make sure ChromeDriver is installed
        try:
            chromedriver_autoinstaller.install()
            print("ChromeDriver installed/verified")
        except Exception as e:
            print(f"Warning: ChromeDriver installation issue: {str(e)}")
        
        # Initialize Chrome with retry logic
        max_retries = 3
        retry_delay = 2
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            try:
                print(f"Chrome initialization attempt {attempt}/{max_retries}")
                
                # Create a service object with specific log path to avoid permission issues
                service = Service(log_path='/tmp/chromedriver.log')
                
                # Initialize the driver with service and options
                driver = webdriver.Chrome(service=service, options=chrome_options)
                
                # Set reasonable timeouts
                driver.set_page_load_timeout(60)
                driver.set_script_timeout(30)
                
                # Verify the driver is working by accessing a simple page
                driver.get("about:blank")
                
                print(f"✅ Chrome initialized successfully on attempt {attempt}")
                return driver
                
            except Exception as e:
                last_error = e
                print(f"Chrome initialization attempt {attempt} failed: {str(e)}")
                
                # Attempt to quit the driver if it was partially initialized
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                    driver = None
                
                # Sleep before retry with exponential backoff
                if attempt < max_retries:
                    sleep_time = retry_delay * (2 ** (attempt - 1))
                    print(f"Waiting {sleep_time} seconds before next attempt...")
                    time.sleep(sleep_time)
                    
                    # Clean up between attempts
                    cleanup_chrome_processes()
        
        # If we get here, all retries failed
        print(f"❌ Failed to initialize Chrome after {max_retries} attempts")
        print(f"Last error: {str(last_error)}")
        return None
        
    except Exception as e:
        print(f"Unexpected error during driver initialization: {str(e)}")
        # Attempt to quit driver if it was created
        if driver:
            try:
                driver.quit()
            except:
                pass
        return None


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
    Logs into Airtasker with the provided credentials.
    Returns True if login successful, False otherwise.
    
    The function includes multiple verification steps and screenshots
    to help diagnose issues in headless cloud environments.
    """
    if driver is None:
        print("Error: Cannot login - WebDriver is None")
        return False
        
    try:
        # Record start time for operation timeout
        start_time = time.time()
        max_total_time = 180  # Maximum 3 minutes for the entire login process
        
        # Find and click the login button
        print("Step 1: Clicking initial login button...")
        try:
            login_btn = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, login_button_xpath))
            )
            login_btn.click()
            print("✓ Login button clicked successfully")
        except Exception as e:
            print(f"⚠️ Failed to click login button: {str(e)}")
            save_screenshot(driver, "login_button_error", group_id)
            
            # Try an alternative approach - JavaScript click
            try:
                print("Attempting JavaScript click as fallback...")
                driver.execute_script("arguments[0].click();", 
                    driver.find_element(By.XPATH, login_button_xpath))
                print("✓ Login button clicked via JavaScript")
            except Exception as js_error:
                print(f"❌ Failed to click login button via JavaScript: {str(js_error)}")
                return False
        
        # Wait for the login form to appear and take screenshot
        time.sleep(random.uniform(3, 5))
        save_screenshot(driver, "login_form", group_id)
        
        # Check if we've exceeded the time limit
        if time.time() - start_time > max_total_time:
            print(f"❌ Login timed out after {max_total_time} seconds")
            return False
            
        # Enter email with human-like typing
        print(f"Step 2: Entering email: {email[:3]}***{email[-8:]}")
        try:
            email_field = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.ID, email_input_id))
            )
            email_field.clear()
            
            # Type with realistic human-like delays
            for c in email:
                email_field.send_keys(c)
                time.sleep(random.uniform(0.05, 0.15))
            
            print("✓ Email entered successfully")
        except Exception as e:
            print(f"❌ Failed to enter email: {str(e)}")
            save_screenshot(driver, "email_input_error", group_id)
            return False
        
        time.sleep(random.uniform(0.8, 1.5))
        
        # Enter password with human-like typing
        print("Step 3: Entering password...")
        try:
            password_field = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.ID, password_input_id))
            )
            password_field.clear()
            
            # Type with realistic human-like delays
            for c in password:
                password_field.send_keys(c)
                time.sleep(random.uniform(0.05, 0.15))
                
            print("✓ Password entered successfully")
        except Exception as e:
            print(f"❌ Failed to enter password: {str(e)}")
            save_screenshot(driver, "password_input_error", group_id)
            return False
        
        time.sleep(random.uniform(1, 2))
        save_screenshot(driver, "before_submit", group_id)
        
        # Check if we've exceeded the time limit
        if time.time() - start_time > max_total_time:
            print(f"❌ Login timed out after {max_total_time} seconds")
            return False
        
        # Submit the form
        print("Step 4: Submitting login form...")
        try:
            submit_btn = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, submit_button_xpath))
            )
            submit_btn.click()
            print("✓ Submit button clicked")
        except Exception as e:
            print(f"⚠️ Failed to click submit button: {str(e)}")
            save_screenshot(driver, "submit_button_error", group_id)
            
            # Try alternative submit methods
            try:
                print("Attempting JavaScript submit as fallback...")
                driver.execute_script("arguments[0].click();", 
                    driver.find_element(By.XPATH, submit_button_xpath))
                print("✓ Form submitted via JavaScript")
            except Exception as js_error:
                print(f"❌ Failed to submit form via JavaScript: {str(js_error)}")
                return False
        
        # Wait for login to complete - longer wait time for headless mode
        print("Step 5: Waiting for login to complete...")
        wait_time = random.uniform(10, 15)
        print(f"Waiting {wait_time:.1f} seconds for login processing...")
        time.sleep(wait_time)
        
        # Take screenshot after login attempt
        save_screenshot(driver, "after_login_attempt", group_id)
        
        # Check if login was successful by looking for expected elements in URL
        current_url = driver.current_url
        print(f"Current URL after login attempt: {current_url}")
        
        # Return success if URL contains expected post-login patterns
        if 'discover' in current_url or 'tasks' in current_url or 'dashboard' in current_url:
            print("✅ Login successful! Redirected to correct page.")
            save_screenshot(driver, "login_success", group_id)
            return True
        else:
            print(f"⚠️ Login might have failed. Expected URL with 'discover', 'tasks', or 'dashboard'")
            print(f"  Got: {current_url}")
            
            # One final attempt - refresh the page to see if we're actually logged in
            driver.refresh()
            time.sleep(5)
            save_screenshot(driver, "post_refresh", group_id)
            
            # Check URL again after refresh
            if 'discover' in driver.current_url or 'tasks' in driver.current_url:
                print("✅ Login confirmed after page refresh")
                return True
            else:
                print("❌ Login failed - not on expected page after refresh")
                return False
            
    except Exception as e:
        print(f"❌ Unexpected error during login: {str(e)}")
        save_screenshot(driver, "login_error", group_id)
        return False


# ------------------------------
# Set location filter function
# ------------------------------
def set_location_filter(driver, suburb_name, radius_km=100, group_id=None):
    """
    Sets the location filter on Airtasker.
    Returns True if successful, False otherwise.
    """
    try:
        # Locate the filter button
        print("Locating filter button...")
        filter_button_xpath = '//*[@id="airtasker-app"]/nav/nav/div/div/div/div[3]/button'
        
        try:
            filter_button = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, filter_button_xpath))
            )
            filter_button.click()
            print("Clicked filter button")
        except Exception as e:
            print(f"Could not find or click filter button: {str(e)}")
            # Try an alternative xpath
            alt_filter_xpath = '//button[contains(@class, "Filter")]'
            try:
                alt_filter = driver.find_element(By.XPATH, alt_filter_xpath)
                alt_filter.click()
                print("Clicked alternative filter button")
            except:
                print("Could not find any filter button, skipping location filter")
                return False
        
        time.sleep(random.uniform(2, 4))
        
        # Enter suburb name
        print(f"Entering suburb name: {suburb_name}")
        suburb_input_xpath = '//*[@id="label-1"]'
        
        try:
            suburb_input = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, suburb_input_xpath))
            )
            suburb_input.clear()
            for c in suburb_name:
                suburb_input.send_keys(c)
                time.sleep(random.uniform(0.05, 0.15))
            
            time.sleep(random.uniform(2, 3))
        except Exception as e:
            print(f"Could not enter suburb name: {str(e)}")
            return False
        
        # Select the first suggestion
        print("Selecting first suggestion")
        first_item_xpath = '//*[@id="airtasker-app"]/nav/nav/div/div/div/div[3]/div/div[1]/div/div[4]/div/div/ul/li[1]'
        
        try:
            first_item = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, first_item_xpath))
            )
            first_item.click()
            print("Selected first location suggestion")
        except Exception as e:
            print(f"Could not select location suggestion: {str(e)}")
            # Try to click the Apply button anyway
        
        time.sleep(random.uniform(2, 3))
        
        # Set radius by adjusting the slider
        try:
            slider_thumb_xpath = '//*[@id="airtasker-app"]/nav/nav/div/div/div/div[3]/div/div[1]/div/div[7]/div/div/button'
            slider_thumb = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, slider_thumb_xpath))
            )
            
            # Calculate offset based on radius (adjust the formula as needed)
            offset_px = int((radius_km / 100.0) * 100)
            ActionChains(driver).click_and_hold(slider_thumb).move_by_offset(offset_px, 0).release().perform()
            print(f"Adjusted radius slider to approximately {radius_km}km")
            
            time.sleep(random.uniform(1, 2))
        except Exception as e:
            print(f"Could not adjust radius slider: {str(e)}")
            # Continue anyway
        
        # Click Apply button
        print("Clicking Apply button")
        apply_button_xpath = '//*[@id="airtasker-app"]/nav/nav/div/div/div/div[3]/div/div[2]/button[2]'
        
        try:
            apply_button = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, apply_button_xpath))
            )
            apply_button.click()
            print("Applied location filter")
        except Exception as e:
            print(f"Could not click Apply button: {str(e)}")
            return False
        
        time.sleep(random.uniform(3, 5))
        return True
        
    except Exception as e:
        print(f"Error setting location filter: {str(e)}")
        return False


# ------------------------------
# Scrape tasks with infinite scroll
# ------------------------------
def scrape_tasks(driver, task_container_xpath, title_xpath, link_xpath, max_scroll=3, group_id=None):
    """
    Scrape task listings from the current page with infinite scroll support.
    Returns a list of task dictionaries.
    """
    results = []
    seen_ids = set()
    
    try:
        print(f"Starting to scrape tasks (max_scroll={max_scroll})")
        save_screenshot(driver, "before_scraping", group_id)
        
        # Initial page load wait
        time.sleep(random.uniform(3, 5))
        
        # Scroll and collect tasks
        for scroll_num in range(max_scroll):
            print(f"Scroll iteration {scroll_num + 1}/{max_scroll}")
            
            # Try to find task containers
            try:
                print("Looking for task containers...")
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, task_container_xpath))
                )
            except TimeoutException as e:
                print(f"No task containers found: {str(e)}")
                break
                
            # Get all current containers
            containers = driver.find_elements(By.XPATH, task_container_xpath)
            print(f"Found {len(containers)} containers on scroll {scroll_num + 1}")
            
            # Process each container
            new_count = 0
            for container in containers:
                try:
                    # Extract the task ID
                    data_task_id = container.get_attribute("data-task-id")
                    
                    # Skip if we've already processed this task or if ID is missing
                    if not data_task_id or data_task_id in seen_ids:
                        continue
                        
                    # Mark as seen
                    seen_ids.add(data_task_id)
                    new_count += 1
                    
                    # Extract title
                    try:
                        title_element = container.find_element(By.XPATH, title_xpath)
                        title_txt = title_element.text.strip()
                    except Exception:
                        title_txt = "Unknown Title"
                        
                    # Extract link
                    try:
                        link_element = container.find_element(By.XPATH, link_xpath)
                        link_url = link_element.get_attribute("href")
                    except Exception:
                        link_url = container.get_attribute("href")
                    
                    # Add to results
                    results.append({
                        "id": data_task_id,
                        "title": title_txt,
                        "link": link_url,
                    })
                except Exception as e:
                    print(f"Error processing container: {str(e)}")
                    continue
                    
            print(f"Added {new_count} new tasks on scroll {scroll_num + 1}")
            
            # Stop if we already have enough tasks
            if len(results) >= 20:
                print(f"Already found {len(results)} tasks, stopping scrolling")
                break
                
            # Scroll down
            print("Scrolling down for more tasks...")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(3, 5))
            
            # Check if we've reached the end of the scroll
            new_containers = driver.find_elements(By.XPATH, task_container_xpath)
            if len(new_containers) <= len(containers):
                print("No new tasks loaded after scrolling. Stopping.")
                break
        
        print(f"Scraping complete. Found {len(results)} tasks total.")
        return results
        
    except Exception as e:
        print(f"Error scraping tasks: {str(e)}")
        return results  # Return whatever we managed to collect


# ------------------------------
# Main execution function
# ------------------------------
def run_airtasker_bot(email, password, city_name="Sydney", max_posts=3, message_content=None, group_id=None, headless=True):
    """Run the Airtasker bot with the given parameters"""
    driver = None
    status = "error"
    message = "Initialization failed"
    start_time = time.time()

    try:
        # Setup environment
        print(f"Starting Airtasker bot for {email} targeting {city_name}")
        print(f"Headless mode: {'Enabled' if headless else 'Disabled'}")
        
        # Set up directories for logs and screenshots using /tmp for cloud environments
        # This is critical for GCP which has a read-only filesystem except for /tmp
        base_dir = '/tmp'  # Always use /tmp as base directory in cloud environments
        logs_dir = os.path.join(base_dir, 'logs')
        screenshot_dir = os.path.join(base_dir, 'screenshots')
        
        # Export as environment variable for other functions
        os.environ['SCREENSHOT_DIR'] = screenshot_dir
        
        # Create directories with proper error handling
        for directory in [logs_dir, screenshot_dir]:
            try:
                os.makedirs(directory, exist_ok=True)
                print(f"Created directory: {directory}")
            except Exception as e:
                print(f"Warning: Could not create directory {directory}: {str(e)}")
                # Continue anyway as we'll handle failures when saving files
        
        # Initialize Chrome with the updated robust approach
        print("Initializing Chrome driver...")
        driver = init_driver(group_id, headless)
        
        if not driver:
            message = "Failed to initialize Chrome driver after multiple attempts"
            print(message)
            return {"status": "error", "message": message}
            
        # Take initial screenshot to verify Chrome is working
        screenshot_path = save_screenshot(driver, "startup")
        if screenshot_path:
            print(f"Initial screenshot saved: {screenshot_path}")
        
        # Navigate to Airtasker
        try:
            print("Navigating to Airtasker homepage...")
            driver.get("https://www.airtasker.com/")
            time.sleep(random.uniform(5, 8))
            screenshot_path = save_screenshot(driver, "homepage")
            print("Successfully loaded Airtasker homepage")
        except Exception as e:
            message = f"Failed to navigate to Airtasker: {str(e)}"
            print(message)
            save_screenshot(driver, "navigation_error")
            return {"status": "error", "message": message}
        
        # Login credentials
        login_button_xpath = '//*[@id="airtasker-app"]/nav/div[2]/div/div/div/div[2]/a[2]'
        email_input_id = "username"
        password_input_id = "password"
        submit_button_xpath = "/html/body/main/section/div/div/div/form/div[2]/button"
        
        # Attempt login
        print(f"Attempting to login as {email}...")
        login_success = login(driver, email, password, login_button_xpath, email_input_id, password_input_id, submit_button_xpath)
        if not login_success:
            return {"status": "error", "message": "Login failed"}
        
        print("Login successful")
        save_screenshot(driver, "after_login", group_id)
        
        # Navigate to tasks page
        print("Navigating to tasks page...")
        tasks_page_url = "https://www.airtasker.com/tasks"
        driver.get(tasks_page_url)
        time.sleep(random.uniform(5, 8))
        
        # Set location filter
        print(f"Setting location filter to {city_name}...")
        filter_success = set_location_filter(driver, city_name, 100)
        if not filter_success:
            print("Warning: Failed to set location filter, continuing anyway...")
        
        save_screenshot(driver, "location_filter", group_id)
        
        # Scrape tasks
        print("Scraping tasks...")
        task_container_xpath = '//a[@data-ui-test="task-list-item" and @data-task-id]'
        title_xpath = './/p[contains(@class,"TaskCard__StyledTitle")]'
        link_xpath = '.'
        
        tasks = scrape_tasks(driver, task_container_xpath, title_xpath, link_xpath, max_scroll=5)
        
        if not tasks:
            return {"status": "warning", "message": "No tasks found to comment on"}
        
        print(f"Found {len(tasks)} tasks")
        
        # Post comments
        from app.automations.comments import comment_on_some_tasks
        print(f"Posting comments on up to {max_posts} tasks using message: {message_content}")
        
        comment_result = comment_on_some_tasks(
            driver=driver,
            tasks=tasks,
            message_content=message_content,
            max_to_post=max_posts,
            image_path=None
        )
        
        save_screenshot(driver, "after_comments", group_id)
        print("Automation completed successfully")
        
        status = "success"
        message = "Automation completed successfully"
        return {"status": status, "message": message}
        
    except Exception as e:
        error_msg = f"Error in run_airtasker_bot: {str(e)}"
        print(error_msg)
        
        # Try to take error screenshot if driver is active
        if driver:
            try:
                save_screenshot(driver, "error_screenshot", group_id)
            except:
                pass
            
        return {"status": "error", "message": error_msg}
        
    finally:
        # Ensure driver is properly closed
        if driver:
            try:
                driver.quit()
                print("Chrome browser closed successfully")
            except Exception as e:
                print(f"Error closing browser: {str(e)}")
        
        # Always clean up Chrome processes
        cleanup_chrome_processes()


# ------------------------------
# Main execution
# ------------------------------
def main():
    """
    Main function to run the Airtasker bot.
    """
    driver = init_driver()
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
        login(driver, email, password, login_button_xpath, email_input_id, password_input_id, submit_button_xpath)
        print("Login successful.")

        time.sleep(5)
        # 2. Navigate to tasks page
        tasks_page_url = "https://www.airtasker.com/tasks"
        driver.get(tasks_page_url)
        time.sleep(random.uniform(5, 8))

        # 3. Set location filter
        city_name = "Sydney"
        radius_km = 100
        set_location_filter(driver, city_name, radius_km)
        print("Location filter set.")

        # 4. Scrape tasks
        task_container_xpath = '//a[@data-ui-test="task-list-item" and @data-task-id]'
        title_xpath = './/p[contains(@class,"TaskCard__StyledTitle")]'
        link_xpath = '.'
        tasks = scrape_tasks(driver, task_container_xpath, title_xpath, link_xpath, max_scroll=5)
        print(f"Scraped {len(tasks)} tasks:")
        for t in tasks:
            print(t)

        time.sleep(10)
        # 5. Post comments on a subset of tasks (with optional image upload)
        message = "Hey did you know there is another jobs application called SmartTasker (all one word) with less fees. you are more likely to get better quotes."
        from app.automations.comments import comment_on_some_tasks
        comment_on_some_tasks(driver, tasks, message_content=message, max_to_post=3, image_path=None)

    finally:
        print("Closing browser.")
        driver.quit()


if __name__ == "__main__":
    main() 