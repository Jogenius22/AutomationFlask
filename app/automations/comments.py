# comments.py
import time
import random
import os
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from app import data_manager as dm
from config import SCREENSHOTS_DIR

# Helper function to save screenshots
def save_screenshot(driver, prefix, group_id):
    """Helper function to save screenshots to a consistent location"""
    timestamp = int(time.time())
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    filename = f"{prefix}_{timestamp}.png"
    filepath = os.path.join(SCREENSHOTS_DIR, filename)
    try:
        driver.save_screenshot(filepath)
        # Log the screenshot
        dm.add_log(f"Screenshot saved: {filename}", "info", group_id=group_id)
    except Exception as e:
        dm.add_log(f"Failed to save screenshot: {str(e)}", "error", group_id=group_id)
    return filename

def post_comment_on_task(driver, task_url, comment_text, image_path=None, group_id=None):
    """
    Navigates to the given task URL, posts the provided comment,
    optionally attaches an image, and clicks 'Send'.
    """
    dm.add_log(f"Posting comment on: {task_url}", "info", group_id=group_id)
    driver.get(task_url)
    time.sleep(random.uniform(5, 8))
    
    # Take screenshot of task page
    save_screenshot(driver, "task_page", group_id)

    dm.add_log(f"Using comment: {comment_text}", "info", group_id=group_id)

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
        dm.add_log("Could not find the comment textarea within 15s. Skipping this task.", "warning", group_id=group_id)
        save_screenshot(driver, "comment_box_not_found", group_id)
        return

    try:
        comment_box = driver.find_element(By.XPATH, comment_box_xpath)
        comment_box.clear()
        for c in comment_text:
            comment_box.send_keys(c)
            time.sleep(random.uniform(0.04, 0.15))
        time.sleep(random.uniform(2, 4))
        
        dm.add_log("Comment text entered successfully", "info", group_id=group_id)

        # Attach an image if provided
        if image_path:
            try:
                attach_input = driver.find_element(By.XPATH, attach_input_xpath)
                attach_input.send_keys(image_path)
                dm.add_log(f"Attached image: {image_path}", "info", group_id=group_id)
                time.sleep(random.uniform(4, 6))
            except NoSuchElementException:
                dm.add_log("Attachment input not found. Skipping image attachment.", "warning", group_id=group_id)

        # Take screenshot before sending comment
        save_screenshot(driver, "before_send_comment", group_id)
        
        # Click the 'Send' button
        driver.find_element(By.XPATH, send_button_xpath).click()
        dm.add_log("Comment posted successfully!", "info", group_id=group_id)
        
        # Take screenshot after posting comment
        time.sleep(random.uniform(2, 3))
        save_screenshot(driver, "after_send_comment", group_id)
        
        time.sleep(random.uniform(3, 6))
    except NoSuchElementException as e:
        dm.add_log(f"Comment box or Send button not found: {str(e)}", "error", group_id=group_id)
        save_screenshot(driver, "comment_error", group_id)

def comment_on_some_tasks(driver, tasks, comment_text, max_to_post=3, image_path=None, group_id=None):
    """
    Given a list of task dicts (each with a 'link'),
    posts the provided comment on up to 'max_to_post' tasks.
    Optionally attaches an image.
    """
    dm.add_log(f"Preparing to comment on up to {max_to_post} tasks", "info", group_id=group_id)
    
    random.shuffle(tasks)
    tasks_to_comment = tasks[:max_to_post]
    
    dm.add_log(f"Selected {len(tasks_to_comment)} tasks for commenting", "info", group_id=group_id)
    
    for i, t in enumerate(tasks_to_comment, start=1):
        link = t.get("link")
        if not link:
            dm.add_log(f"Task {i} missing link; skipping.", "warning", group_id=group_id)
            continue
            
        dm.add_log(f"Starting comment {i}/{len(tasks_to_comment)}: {t.get('title', 'Unknown Title')}", "info", group_id=group_id)
        post_comment_on_task(driver, link, comment_text, image_path=image_path, group_id=group_id)
        
        # Wait between commenting on tasks
        if i < len(tasks_to_comment):
            wait_time = random.uniform(5, 10)
            dm.add_log(f"Waiting {wait_time:.1f} seconds before next comment", "info", group_id=group_id)
            time.sleep(wait_time)
    
    dm.add_log(f"Completed commenting on {len(tasks_to_comment)} tasks", "info", group_id=group_id) 