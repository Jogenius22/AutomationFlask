# comments.py
import time
import random
import os
import logging
from datetime import datetime
import traceback
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException, StaleElementReferenceException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from app import data_manager as dm

# Set up logging
try:
    # Make sure logs directory exists
    log_dir = os.path.join(os.environ.get('DATA_DIR', os.path.join(os.getcwd(), 'data')), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Set up logging with file handler
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(log_dir, 'comments.log'))
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

# ------------------------------
# 1) COMMENT TEMPLATES
# ------------------------------
RAW_MESSAGES = [
    # Message 1
    "Hey did you know there is another jobs application called ?????Tasker (Replace ????? with Smart, all one word with less fees. you are more likely to get better quotes.",
    # Message 2
    "Hey just thought I would mention that you will likely find better quotes on the new S___Tasker application (insert the word Smart, all one word). fees are 25% less.",
    # Message 3
    "Hi for this task you might want to post on *****Tasker ( Insert the word *Smart*, all one word). The fees are less so we can give you better quotes",
    # Message 4
    "Hey probably a good idea to poston the new Smart______ application. (insert the word Tasker, all one word.) You will get more quotes. And the fees are much less!",
    # Message 5
    "By the way you might get better quotes with posting to the Smart/ / / / / / application. (Replace / / / / / with Tasker, all one word) better fees for all users and more options."
]

def pick_random_comment():
    """
    Picks a random comment template and does placeholder replacements.
    """
    template = random.choice(RAW_MESSAGES)
    final = (template
             .replace("?????", "Smart")
             .replace("___", "mart")
             .replace("*****", "Smart")
             .replace("______", "Tasker")
             .replace("/ / / / / /", "Tasker")
             )
    return final

# ------------------------------
# Helper function for screenshots
# ------------------------------
def save_screenshot(driver, name_prefix, group_id=None):
    """
    Save a screenshot of the current browser window with a timestamp.
    
    Args:
        driver: Selenium WebDriver instance
        name_prefix: Prefix for the screenshot filename
        group_id: Optional group ID for logging
    """
    if not driver:
        return
        
    # Get the screenshot directory from environment variable or use current directory
    screenshot_dir = os.environ.get('SCREENSHOT_DIR', os.getcwd())
    
    try:
        # Create the directory if it doesn't exist
        os.makedirs(screenshot_dir, exist_ok=True)
        
        # Generate unique filename with timestamp
        timestamp = int(time.time())
        filename = f"{name_prefix}_{timestamp}.png"
        filepath = os.path.join(screenshot_dir, filename)
        
        # Save the screenshot
        driver.save_screenshot(filepath)
        print(f"Screenshot saved: {filepath}")
        return filename
    except Exception as e:
        print(f"Error saving screenshot {name_prefix}: {str(e)}")
        return None

def post_comment_on_task(driver, task_url, custom_message=None, image_path=None, group_id=None):
    """
    Navigates to the given task URL, posts the specified message (or a random one),
    optionally attaches an image, and clicks 'Send'.
    """
    print(f"\n--- Posting comment on: {task_url} ---")
    driver.get(task_url)
    time.sleep(random.uniform(5, 8))
    
    # Take a screenshot when we arrive at the task page
    save_screenshot(driver, "task_page", group_id)

    # Choose message - use custom_message if provided, otherwise pick a random one
    comment_text = custom_message if custom_message else pick_random_comment()
    print(f"Message to post: {comment_text}")

    # XPaths for the comment textarea and the 'Send' button
    comment_box_xpath = '//*[@id="airtasker-app"]/main/div/div[1]/div[3]/div/div/div[2]/div/div[6]/div/div[2]/div/div/div/div/div[3]/textarea'
    send_button_xpath = '//*[@id="airtasker-app"]/main/div/div[1]/div[3]/div/div/div[2]/div/div[6]/div/div[2]/div/div/div/div/div[3]/div/span/button'
    # XPath for file upload input (for optional image attachment)
    attach_input_xpath = '//*[@data-ui-test="upload-attachment-input"]'

    # Wait up to 15 seconds for the comment textarea to appear
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, comment_box_xpath))
        )
    except TimeoutException:
        print("Could not find the comment textarea within 15s. Skipping this task.")
        return False

    try:
        # Take screenshot before commenting
        save_screenshot(driver, "before_send_comment", group_id)
        
        comment_box = driver.find_element(By.XPATH, comment_box_xpath)
        comment_box.clear()
        for c in comment_text:
            comment_box.send_keys(c)
            time.sleep(random.uniform(0.04, 0.15))
        time.sleep(random.uniform(2, 4))

        # Attach an image if provided
        if image_path:
            try:
                attach_input = driver.find_element(By.XPATH, attach_input_xpath)
                attach_input.send_keys(image_path)
                print(f"Attached image: {image_path}")
                time.sleep(random.uniform(4, 6))
            except NoSuchElementException:
                print("Attachment input not found. Skipping image attachment.")

        # Click the 'Send' button
        driver.find_element(By.XPATH, send_button_xpath).click()
        print("Comment posted!")
        
        # Take screenshot after sending
        save_screenshot(driver, "after_send_comment", group_id)
        
        time.sleep(random.uniform(3, 6))
        return True
    except NoSuchElementException as e:
        print(f"Element not found: {str(e)}")
        return False
    except Exception as e:
        print(f"Error posting comment: {str(e)}")
        return False

def comment_on_some_tasks(driver, tasks, message_content=None, max_to_post=3, image_path=None, group_id=None):
    """
    Given a list of task dicts (each with a 'link'),
    posts random comments on up to 'max_to_post' tasks.
    Optionally attaches an image.
    
    Parameters:
    - driver: Selenium WebDriver instance
    - tasks: List of task dictionaries with 'link' keys
    - message_content: Optional custom message to post (if None, a random one is picked)
    - max_to_post: Maximum number of tasks to post on
    - image_path: Optional path to an image file to attach
    - group_id: Optional group ID for logging
    """
    if not tasks:
        print("No tasks provided to comment on")
        return
    
    # Make a copy of the tasks list to avoid modifying the original
    tasks_copy = tasks.copy()
    random.shuffle(tasks_copy)
    
    # Limit to max_to_post
    tasks_to_comment = tasks_copy[:max_to_post]
    
    success_count = 0
    for i, task in enumerate(tasks_to_comment, start=1):
        link = task.get("link")
        if not link:
            print(f"Task {i} missing link; skipping.")
            continue
        
        try:
            print(f"\n--- Posting comment on task {i}/{len(tasks_to_comment)}: {link} ---")
            # Use the custom message if provided, otherwise use a random one
            post_comment_on_task(driver, link, custom_message=message_content, image_path=image_path, group_id=group_id)
            success_count += 1
            time.sleep(random.uniform(3, 6))  # Add delay between posts
        except Exception as e:
            print(f"Error posting on task {i}: {str(e)}")
    
    print(f"\nDone posting on {success_count} out of {len(tasks_to_comment)} tasks.")
    return success_count > 0 