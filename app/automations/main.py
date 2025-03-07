import time
import random
import os
import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import chromedriver_autoinstaller
import json

from chrome_extension_python import Extension
from app.automations.comments import comment_on_some_tasks
from app import data_manager as dm
from config import Config, SCREENSHOTS_DIR

# ------------------------------
# Basic user agents for stealth
# ------------------------------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
]


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
# Helper function for screenshots
# ------------------------------
def save_screenshot(driver, prefix, group_id):
    try:
        timestamp = int(time.time())
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        filename = f"{prefix}_{timestamp}.png"
        filepath = os.path.join(SCREENSHOTS_DIR, filename)
        driver.save_screenshot(filepath)
        # Log the screenshot
        dm.add_log(f"Screenshot saved: {filename}", "info", group_id=group_id)
        return filename
    except Exception as e:
        dm.add_log(f"Failed to save screenshot: {str(e)}", "error", group_id=group_id)
        return None


# ------------------------------
# Initialize the Selenium driver
# ------------------------------
def init_driver(headless=False):
    user_agent = random.choice(USER_AGENTS)
    chrome_options = Options()
    chrome_options.add_argument(f"--user-agent={user_agent}")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-infobars")
    
    # Extension support settings
    chrome_options.add_argument("--enable-extensions")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--allow-running-insecure-content")
    
    # Add headless mode and related flags only if specified
    if headless:
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        
        # Add environment Chrome args if available
        chrome_args = os.environ.get('CHROME_ARGS', '')
        if chrome_args:
            for arg in chrome_args.split():
                if arg not in chrome_options.arguments:
                    chrome_options.add_argument(arg)
    
    # Load the captcha solver extension
    capsolver_api_key = os.environ.get('CAPSOLVER_API_KEY', 'CAP-F79C6D0E7A810348A201783E25287C6003CFB45BBDCB670F96E525E7C0132148')
    dm.add_log(f"Initializing Capsolver extension (API key length: {len(capsolver_api_key)})", "info")
    chrome_options.add_argument(
        Capsolver(capsolver_api_key).load()
    )

    # Install chromedriver if not present
    chromedriver_autoinstaller.install()
    driver = webdriver.Chrome(options=chrome_options)
    
    # Set window size if not headless
    if not headless:
        driver.set_window_size(1280, 800)
        
    # Additional stealth settings that work in both headless and regular mode
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    # Set page load timeout
    driver.set_page_load_timeout(60)
    
    return driver


# ------------------------------
# Login function with better verification
# ------------------------------
def login(driver, email, password,
          login_button_xpath,
          email_input_id,
          password_input_id,
          submit_button_xpath,
          group_id=None):
    max_retries = 3
    retry_count = 0
    
    # XPath for the avatar that appears when logged in (kept for verification)
    avatar_xpath = '//*[@id="overlay-provider"]/nav/div[2]/div/div/div/div[2]/button/div/div'
    
    # XPath for the reCAPTCHA iframe
    recaptcha_iframe_xpath = "//iframe[contains(@title, 'recaptcha')]"
    
    while retry_count < max_retries:
        try:
            if retry_count > 0:
                dm.add_log(f"Retry login attempt {retry_count}/{max_retries}", "info", group_id=group_id)
                driver.delete_all_cookies()
                driver.get("about:blank")
                time.sleep(random.uniform(2, 3))
                
            # Navigate directly to login page instead of clicking login button
            dm.add_log(f"Navigating to login page for {email}", "info", group_id=group_id)
            driver.get("https://www.airtasker.com/login")
            time.sleep(random.uniform(5, 8))
            
            # Take screenshot of login page
            save_screenshot(driver, "login_page", group_id)
            
            # IMPORTANT: Wait for Capsolver to begin working by giving it time to detect the captcha
            dm.add_log("Waiting for Capsolver to detect captcha before entering credentials", "info", group_id=group_id)
            time.sleep(random.uniform(10, 15))
            
            # Type the email
            dm.add_log(f"Typing email", "info", group_id=group_id)
            email_field = driver.find_element(By.ID, email_input_id)
            time.sleep(random.uniform(1, 2))
            email_field.clear()
            for c in email:
                email_field.send_keys(c)
                time.sleep(random.uniform(0.04, 0.2))

            # Type the password
            dm.add_log("Typing password", "info", group_id=group_id)
            password_field = driver.find_element(By.ID, password_input_id)
            time.sleep(random.uniform(1, 2))
            password_field.clear()
            for c in password:
                password_field.send_keys(c)
                time.sleep(random.uniform(0.04, 0.15))

            # Captcha should be solved automatically by the extension
            # We need to explicitly wait for the captcha to be solved
            dm.add_log("Waiting for captcha to be solved by Capsolver...", "info", group_id=group_id)
            captcha_wait_time = 30  # Give up to 30 seconds for solving
            captcha_solved = False
            start_time = time.time()
            
            while time.time() - start_time < captcha_wait_time:
                # Check if the reCAPTCHA iframe is still present
                try:
                    recaptcha_frames = driver.find_elements(By.XPATH, recaptcha_iframe_xpath)
                    if not recaptcha_frames:
                        dm.add_log("Captcha appears to be solved (iframe no longer present)", "info", group_id=group_id)
                        captcha_solved = True
                        break
                except:
                    # If error finding frames, we'll assume it might be solved
                    pass
                
                # Take periodic screenshots to monitor captcha progress
                if (time.time() - start_time) % 10 < 1:  # Every ~10 seconds
                    save_screenshot(driver, "captcha_progress", group_id)
                
                time.sleep(1)  # Check every second
            
            if not captcha_solved:
                dm.add_log("WARNING: Not certain if captcha was solved. Will try to continue.", "warning", group_id=group_id)
            
            # Wait a bit more before clicking submit to ensure captcha is completely processed
            time.sleep(random.uniform(3, 5))
            save_screenshot(driver, "before_submit", group_id)
            
            # Submit the login form
            dm.add_log("Submitting login form", "info", group_id=group_id)
            try:
                # Use WebDriverWait to wait for the submit button to be clickable
                submit_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, submit_button_xpath))
                )
                submit_btn.click()
                dm.add_log("Clicked submit button", "info", group_id=group_id)
            except Exception as e:
                dm.add_log(f"Error clicking submit button: {str(e)}", "error", group_id=group_id)
                save_screenshot(driver, "submit_error", group_id)
                
                # Try JavaScript click as fallback
                try:
                    dm.add_log("Trying JavaScript click as fallback", "info", group_id=group_id)
                    submit_btn = driver.find_element(By.XPATH, submit_button_xpath)
                    driver.execute_script("arguments[0].click();", submit_btn)
                    dm.add_log("JavaScript click successful", "info", group_id=group_id)
                except Exception as js_error:
                    dm.add_log(f"JavaScript click also failed: {str(js_error)}", "error", group_id=group_id)
                    raise
            
            # Wait for post-login redirect
            time.sleep(random.uniform(15, 20))
            
            # Take screenshot after login
            save_screenshot(driver, "post_login", group_id)
            
            # Check for avatar element to verify login success
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, avatar_xpath))
                )
                dm.add_log("Login successful - avatar element found", "info", group_id=group_id)
                return True
            except Exception as e:
                # If avatar not found, check URL as a fallback
                if "airtasker.com" in driver.current_url and ("/login" not in driver.current_url):
                    dm.add_log(f"Login seems successful based on URL: {driver.current_url}", "info", group_id=group_id)
                    return True
                else:
                    save_screenshot(driver, "login_verification_error", group_id)
                    error_msg = f"Login failed verification. Current URL: {driver.current_url}, error: {str(e)}"
                    dm.add_log(error_msg, "error", group_id=group_id)
                    
                    if retry_count < max_retries - 1:
                        retry_count += 1
                        continue
                    else:
                        raise Exception(error_msg)
            
        except Exception as e:
            save_screenshot(driver, "login_error", group_id)
            dm.add_log(f"Login error: {str(e)}", "error", group_id=group_id)
            
            if retry_count < max_retries - 1:
                retry_count += 1
                time.sleep(random.uniform(5, 10))  # Wait before retrying
            else:
                raise  # Re-raise the last exception after all retries fail


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
    """Main function to run the Airtasker bot with extensive logging and screenshots.
    
    Args:
        email: User's email for login
        password: User's password
        city_name: City name for location filter (default: Sydney)
        max_posts: Maximum number of posts to comment on (default: 3)
        message_content: Custom message to post (if None, a default will be used)
        group_id: Group ID for logging purposes
        headless: Whether to run in headless mode (default: False)
    """
    if not message_content:
        dm.add_log("Warning: No message content provided. Using default message.", "warning", group_id=group_id)
        message_content = "Hey, you might get better quotes posting on the SmartTasker app. The fees are 25% less!"
        
    driver = None
    try:
        dm.add_log(f"Starting Airtasker bot for {email} in {'headless' if headless else 'visible'} mode", "info", group_id=group_id)
        
        # Initialization with headless parameter
        driver = init_driver(headless=headless)
        driver.get("https://www.airtasker.com/")
        time.sleep(random.uniform(5, 8))
        
        # Take initial screenshot
        save_screenshot(driver, "initial_page", group_id)
        
        # Credentials and login XPaths
        login_button_xpath = '//*[@id="airtasker-app"]/nav/div[2]/div/div/div/div[2]/a[2]'
        email_input_id = "username"
        password_input_id = "password"
        submit_button_xpath = "/html/body/main/section/div/div/div/form/div[2]/button"

        # 1. LOGIN (with URL verification)
        login(driver, email, password, login_button_xpath, email_input_id, password_input_id, submit_button_xpath, group_id)
        dm.add_log("Login successful.", "info", group_id=group_id)

        time.sleep(5)
        # 2. Navigate to tasks page
        tasks_page_url = "https://www.airtasker.com/tasks"
        dm.add_log(f"Navigating to tasks page: {tasks_page_url}", "info", group_id=group_id)
        driver.get(tasks_page_url)
        time.sleep(random.uniform(5, 8))

        # 3. Set location filter
        set_location_filter(driver, city_name, 100, group_id)
        dm.add_log("Location filter set.", "info", group_id=group_id)

        # 4. Scrape tasks
        task_container_xpath = '//a[@data-ui-test="task-list-item" and @data-task-id]'
        title_xpath = './/p[contains(@class,"TaskCard__StyledTitle")]'
        link_xpath = '.'
        tasks = scrape_tasks(driver, task_container_xpath, title_xpath, link_xpath, max_scroll=5, group_id=group_id)
        
        if not tasks:
            dm.add_log("No tasks found to comment on", "warning", group_id=group_id)
            return True, "Completed with no tasks to comment on"

        time.sleep(random.uniform(5, 10))
        
        # 5. Post comments on a subset of tasks (with optional image upload)
        # Use the message content passed from the dashboard
        comment_on_some_tasks(driver, tasks, message_content, max_to_post=max_posts, image_path=None, group_id=group_id)
        
        save_screenshot(driver, "completed", group_id)
        dm.add_log("Bot completed successfully", "success", group_id=group_id)
        return True, "Bot completed successfully"

    except Exception as e:
        if driver:
            save_screenshot(driver, "error", group_id)
        dm.add_log(f"Error in bot: {str(e)}", "error", group_id=group_id)
        return False, str(e)
    finally:
        if driver:
            dm.add_log("Closing browser.", "info", group_id=group_id)
            driver.quit()


# ------------------------------
# Main execution
# ------------------------------
def main():
    driver = init_driver(headless=False)  # False by default but explicitly set for clarity
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
        # 5. Post comments on a subset of tasks
        # Use a default message for this test run
        message = "Hey you might get better quotes on SmartTasker app. Fees are 25% less!"
        comment_on_some_tasks(driver, tasks, message, max_to_post=3)

    finally:
        print("Closing browser.")
        driver.quit()


if __name__ == "__main__":
    main() 