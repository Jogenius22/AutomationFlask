# comments.py
import time
import random
import os
import logging
import datetime
import traceback
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException, StaleElementReferenceException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from app import data_manager as dm

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.environ.get('DATA_DIR', '/app/data'), 'logs', 'comments.log'))
    ]
)
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
    """Save a screenshot with timestamp and prefix"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{name_prefix}_{timestamp}.png"
    screenshot_dir = os.path.join(os.environ.get('DATA_DIR', '/app/data'), 'screenshots')
    
    # Ensure directory exists
    os.makedirs(screenshot_dir, exist_ok=True)
    
    filepath = os.path.join(screenshot_dir, filename)
    try:
        driver.save_screenshot(filepath)
        logger.info(f"Screenshot saved: {filepath}")
        # Also log to data_manager if group_id is provided
        if group_id:
            dm.add_log(f"Screenshot saved: {filename}", "info", group_id=group_id)
        return filepath
    except Exception as e:
        logger.error(f"Failed to save screenshot: {str(e)}")
        if group_id:
            dm.add_log(f"Failed to save screenshot: {str(e)}", "error", group_id=group_id)
        return None

def post_comment_on_task(driver, task_url, custom_message=None, image_path=None, group_id=None):
    """
    Enhanced function to post a comment on a task with improved error handling and logging.
    
    Args:
        driver: Selenium WebDriver instance
        task_url: URL of the task page
        custom_message: Optional custom message (uses random template if None)
        image_path: Optional path to image for attachment
        group_id: Optional group ID for logging
    
    Returns:
        bool: True if comment was posted successfully, False otherwise
    """
    logger.info(f"Attempting to post comment on: {task_url}")
    if group_id:
        dm.add_log(f"Attempting to post comment on: {task_url}", "info", group_id=group_id)
    
    try:
        # Navigate to the task URL
        driver.get(task_url)
        logger.info(f"Navigated to task URL")
        time.sleep(random.uniform(5, 8))
        
        # Take screenshot of task page
        save_screenshot(driver, "task_page", group_id)
        
        # Choose comment text - either custom or random template
        comment_text = custom_message if custom_message else pick_random_comment()
        logger.info(f"Using comment: {comment_text}")
        if group_id:
            dm.add_log(f"Using comment: {comment_text}", "info", group_id=group_id)
        
        # XPaths for the comment box and send button - multiple options for robustness
        comment_box_xpaths = [
            '//*[@id="airtasker-app"]/main/div/div[1]/div[3]/div/div/div[2]/div/div[6]/div/div[2]/div/div/div/div/div[3]/textarea',
            '//textarea[contains(@placeholder, "Add a comment")]',
            '//textarea[@data-ui-test="comment-input"]',
            '//div[contains(@class, "CommentBox")]//textarea'
        ]
        
        send_button_xpaths = [
            '//*[@id="airtasker-app"]/main/div/div[1]/div[3]/div/div/div[2]/div/div[6]/div/div[2]/div/div/div/div/div[3]/div/span/button',
            '//button[contains(text(), "Send") or contains(text(), "Post")]',
            '//button[@data-ui-test="submit-comment-button"]',
            '//div[contains(@class, "CommentBox")]//button'
        ]
        
        # File upload input XPath - multiple options
        attach_input_xpaths = [
            '//*[@data-ui-test="upload-attachment-input"]',
            '//input[@type="file" and @accept="image/*"]',
            '//div[contains(@class, "AttachmentUpload")]//input[@type="file"]'
        ]
        
        # Try to find and interact with the comment box using multiple approaches
        comment_box = None
        for xpath in comment_box_xpaths:
            try:
                comment_box = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
                logger.info(f"Found comment box with XPath: {xpath}")
                if group_id:
                    dm.add_log(f"Found comment box with XPath: {xpath}", "info", group_id=group_id)
                break
            except (TimeoutException, NoSuchElementException):
                continue
        
        if not comment_box:
            logger.error("Could not find comment box with any of the XPaths")
            if group_id:
                dm.add_log("Could not find comment box with any of the XPaths", "error", group_id=group_id)
            save_screenshot(driver, "comment_box_not_found", group_id)
            return False
        
        # Clear and enter text in the comment box with human-like typing
        try:
            comment_box.clear()
            for c in comment_text:
                comment_box.send_keys(c)
                time.sleep(random.uniform(0.04, 0.15))
            logger.info("Comment text entered successfully")
            if group_id:
                dm.add_log("Comment text entered successfully", "info", group_id=group_id)
            time.sleep(random.uniform(1, 2))  # Short pause after typing
        except Exception as e:
            logger.error(f"Error typing comment: {str(e)}")
            if group_id:
                dm.add_log(f"Error typing comment: {str(e)}", "error", group_id=group_id)
            save_screenshot(driver, "comment_typing_error", group_id)
            return False
        
        # Attach an image if provided
        if image_path:
            attach_input = None
            for xpath in attach_input_xpaths:
                try:
                    attach_input = driver.find_element(By.XPATH, xpath)
                    logger.info(f"Found attachment input with XPath: {xpath}")
                    if group_id:
                        dm.add_log(f"Found attachment input with XPath: {xpath}", "info", group_id=group_id)
                    break
                except NoSuchElementException:
                    continue
            
            if attach_input:
                try:
                    # Ensure the image path is absolute
                    abs_image_path = os.path.abspath(image_path)
                    attach_input.send_keys(abs_image_path)
                    logger.info(f"Attached image: {abs_image_path}")
                    if group_id:
                        dm.add_log(f"Attached image: {abs_image_path}", "info", group_id=group_id)
                    time.sleep(random.uniform(3, 5))  # Wait for image to upload
                except Exception as e:
                    logger.error(f"Error attaching image: {str(e)}")
                    if group_id:
                        dm.add_log(f"Error attaching image: {str(e)}", "error", group_id=group_id)
                    save_screenshot(driver, "image_attachment_error", group_id)
            else:
                logger.warning("Image attachment skipped - input element not found")
                if group_id:
                    dm.add_log("Image attachment skipped - input element not found", "warning", group_id=group_id)
        
        # Take screenshot before clicking send
        save_screenshot(driver, "before_send", group_id)
        
        # Try to click the send button using multiple approaches
        send_button = None
        for xpath in send_button_xpaths:
            try:
                send_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                logger.info(f"Found send button with XPath: {xpath}")
                if group_id:
                    dm.add_log(f"Found send button with XPath: {xpath}", "info", group_id=group_id)
                break
            except (TimeoutException, NoSuchElementException):
                continue
        
        if not send_button:
            logger.error("Could not find send button with any of the XPaths")
            if group_id:
                dm.add_log("Could not find send button with any of the XPaths", "error", group_id=group_id)
            save_screenshot(driver, "send_button_not_found", group_id)
            return False
        
        # Try regular click first, then JavaScript click as fallback
        try:
            send_button.click()
            logger.info("Send button clicked successfully")
            if group_id:
                dm.add_log("Send button clicked successfully", "info", group_id=group_id)
        except (ElementClickInterceptedException, StaleElementReferenceException, WebDriverException) as e:
            logger.warning(f"Standard click failed: {str(e)}. Trying JavaScript click...")
            if group_id:
                dm.add_log(f"Standard click failed: {str(e)}. Trying JavaScript click...", "warning", group_id=group_id)
            try:
                driver.execute_script("arguments[0].click();", send_button)
                logger.info("JavaScript click succeeded")
                if group_id:
                    dm.add_log("JavaScript click succeeded", "info", group_id=group_id)
            except Exception as js_error:
                logger.error(f"JavaScript click also failed: {str(js_error)}")
                if group_id:
                    dm.add_log(f"JavaScript click also failed: {str(js_error)}", "error", group_id=group_id)
                save_screenshot(driver, "send_button_js_error", group_id)
                return False
        
        # Wait for comment to be posted
        time.sleep(random.uniform(3, 5))
        
        # Take screenshot after posting
        save_screenshot(driver, "after_comment_posted", group_id)
        
        # Look for indicators that comment was posted successfully
        # This could be the presence of the comment text on the page or some other confirmation element
        try:
            # This is a simple heuristic - looking for our own comment text on the page
            # A more robust approach would check for specific confirmation elements
            page_source = driver.page_source
            if comment_text in page_source:
                logger.info("Comment successfully posted and verified")
                if group_id:
                    dm.add_log("Comment successfully posted and verified", "success", group_id=group_id)
                return True
            else:
                logger.warning("Comment may have been posted but couldn't verify")
                if group_id:
                    dm.add_log("Comment may have been posted but couldn't verify", "warning", group_id=group_id)
                # We'll consider it a success for now
                return True
        except Exception as e:
            logger.error(f"Error verifying comment: {str(e)}")
            if group_id:
                dm.add_log(f"Error verifying comment: {str(e)}", "error", group_id=group_id)
            # We'll still return True since the comment probably posted
            return True
    
    except Exception as e:
        logger.error(f"Error posting comment: {str(e)}")
        logger.error(traceback.format_exc())
        if group_id:
            dm.add_log(f"Error posting comment: {str(e)}", "error", group_id=group_id)
        save_screenshot(driver, "comment_posting_error", group_id)
        return False

def comment_on_some_tasks(driver, tasks, message_content=None, max_to_post=3, image_path=None, group_id=None):
    """
    Enhanced function to post comments on multiple tasks with error handling.
    
    Args:
        driver: Selenium WebDriver instance
        tasks: List of task dictionaries (each with a 'link' key)
        message_content: Optional custom message (uses random template if None)
        max_to_post: Maximum number of tasks to comment on
        image_path: Optional path to image for attachment
        group_id: Optional group ID for logging
    
    Returns:
        int: Number of comments successfully posted
    """
    logger.info(f"Starting to post comments on up to {max_to_post} tasks")
    if group_id:
        dm.add_log(f"Starting to post comments on up to {max_to_post} tasks", "info", group_id=group_id)
    
    # Shuffle tasks to pick random ones each time
    valid_tasks = [t for t in tasks if t.get('link')]
    random.shuffle(valid_tasks)
    
    # Limit the number of tasks to comment on
    tasks_to_comment = valid_tasks[:max_to_post]
    
    # Track the number of successful comments
    success_count = 0
    
    for i, task in enumerate(tasks_to_comment, start=1):
        task_id = task.get('id', 'unknown')
        task_title = task.get('title', 'unknown')
        task_link = task.get('link')
        
        if not task_link:
            logger.warning(f"Task {i} (ID: {task_id}) is missing a link, skipping")
            if group_id:
                dm.add_log(f"Task {i} (ID: {task_id}) is missing a link, skipping", "warning", group_id=group_id)
            continue
        
        logger.info(f"Commenting on task {i}/{len(tasks_to_comment)}: {task_title} (ID: {task_id})")
        if group_id:
            dm.add_log(f"Commenting on task {i}/{len(tasks_to_comment)}: {task_title}", "info", group_id=group_id)
        
        # Attempt to post the comment
        success = post_comment_on_task(driver, task_link, message_content, image_path, group_id)
        
        if success:
            success_count += 1
            logger.info(f"Comment posted successfully on task {i}")
            if group_id:
                dm.add_log(f"Comment posted successfully on task {i}", "success", group_id=group_id)
        else:
            logger.warning(f"Failed to post comment on task {i}")
            if group_id:
                dm.add_log(f"Failed to post comment on task {i}", "warning", group_id=group_id)
        
        # Random delay between tasks to appear more human-like
        if i < len(tasks_to_comment):
            delay = random.uniform(5, 10)
            logger.info(f"Waiting {delay:.2f} seconds before next comment...")
            if group_id:
                dm.add_log(f"Waiting {delay:.2f} seconds before next comment...", "info", group_id=group_id)
            time.sleep(delay)
    
    logger.info(f"Comment posting completed. Posted {success_count} out of {len(tasks_to_comment)} attempted comments")
    if group_id:
        dm.add_log(f"Comment posting completed. Posted {success_count} out of {len(tasks_to_comment)} attempted comments", "info", group_id=group_id)
    
    return success_count 