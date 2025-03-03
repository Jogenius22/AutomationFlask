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
    try:
        dm.add_log(f"Posting comment on: {task_url}", "info", group_id=group_id)
        
        # Check if the driver is still active before proceeding
        try:
            current_url = driver.current_url
            dm.add_log(f"Current URL before navigation: {current_url}", "debug", group_id=group_id)
        except Exception as e:
            dm.add_log(f"Driver session check failed: {str(e)}", "error", group_id=group_id)
            raise Exception("Invalid driver session") from e
        
        # Use a try-except block for the navigation to catch timeouts
        try:
            driver.get(task_url)
        except Exception as e:
            dm.add_log(f"Navigation to task failed: {str(e)}", "error", group_id=group_id)
            raise Exception(f"Failed to navigate to task: {str(e)}") from e
            
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
            comment_box = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, comment_box_xpath))
            )
            dm.add_log("Comment box found successfully", "info", group_id=group_id)
        except TimeoutException:
            dm.add_log("Could not find the comment textarea within 15s. Skipping this task.", "warning", group_id=group_id)
            save_screenshot(driver, "comment_box_not_found", group_id)
            return
        except Exception as e:
            dm.add_log(f"Unexpected error waiting for comment box: {str(e)}", "error", group_id=group_id)
            save_screenshot(driver, "comment_box_error", group_id)
            raise Exception(f"Error finding comment box: {str(e)}") from e

        try:
            # Clear and enter text with error handling
            try:
                comment_box.clear()
                dm.add_log("Comment box cleared", "debug", group_id=group_id)
            except Exception as e:
                dm.add_log(f"Error clearing comment box: {str(e)}", "warning", group_id=group_id)
                # Try to continue anyway
            
            # Type text with human-like delays, with error handling for each keystroke
            for c in comment_text:
                try:
                    comment_box.send_keys(c)
                    time.sleep(random.uniform(0.03, 0.12))  # Slightly faster typing to reduce chances of timeout
                except Exception as e:
                    dm.add_log(f"Error typing character '{c}': {str(e)}", "error", group_id=group_id)
                    raise Exception(f"Error typing comment text: {str(e)}") from e
                    
            time.sleep(random.uniform(1, 2))  # Reduced wait time
            
            dm.add_log("Comment text entered successfully", "info", group_id=group_id)

            # Attach an image if provided
            if image_path:
                try:
                    attach_input = driver.find_element(By.XPATH, attach_input_xpath)
                    attach_input.send_keys(image_path)
                    dm.add_log(f"Attached image: {image_path}", "info", group_id=group_id)
                    time.sleep(random.uniform(3, 5))  # Slightly reduced wait time
                except NoSuchElementException:
                    dm.add_log("Attachment input not found. Skipping image attachment.", "warning", group_id=group_id)
                except Exception as e:
                    dm.add_log(f"Error attaching image: {str(e)}", "error", group_id=group_id)
                    # Continue without the image rather than failing

            # Take screenshot before sending comment
            save_screenshot(driver, "before_send_comment", group_id)
            
            # Find the send button with wait
            try:
                send_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, send_button_xpath))
                )
                dm.add_log("Send button is ready to click", "debug", group_id=group_id)
            except Exception as e:
                dm.add_log(f"Error finding clickable send button: {str(e)}", "error", group_id=group_id)
                save_screenshot(driver, "send_button_error", group_id)
                raise Exception(f"Send button not clickable: {str(e)}") from e
            
            # Click with error handling
            try:
                send_button.click()
                dm.add_log("Comment posted successfully!", "info", group_id=group_id)
            except Exception as e:
                dm.add_log(f"Error clicking send button: {str(e)}", "error", group_id=group_id)
                save_screenshot(driver, "send_click_error", group_id)
                raise Exception(f"Error sending comment: {str(e)}") from e
            
            # Take screenshot after posting comment
            time.sleep(random.uniform(2, 3))
            save_screenshot(driver, "after_send_comment", group_id)
            
            time.sleep(random.uniform(2, 4))  # Slightly reduced wait time
            
        except NoSuchElementException as e:
            dm.add_log(f"Element not found while posting comment: {str(e)}", "error", group_id=group_id)
            save_screenshot(driver, "comment_element_error", group_id)
            raise Exception(f"Missing element for commenting: {str(e)}") from e
            
    except Exception as e:
        # Add comprehensive error diagnostics
        error_str = str(e)
        if "invalid session id" in error_str or "no such session" in error_str:
            dm.add_log("Browser session has been invalidated during comment posting", "error", group_id=group_id)
            # This will be caught by the outer retry mechanism in run_airtasker_bot
        else:
            dm.add_log(f"Error posting comment: {error_str}", "error", group_id=group_id)
            try:
                save_screenshot(driver, "comment_general_error", group_id)
            except:
                pass  # Screenshot saving might also fail in severe error cases
        
        # Re-raise the exception to be handled by the calling function
        raise

def comment_on_some_tasks(driver, tasks, comment_text, max_to_post=3, image_path=None, group_id=None):
    """
    Given a list of task dicts (each with a 'link'),
    posts the provided comment on up to 'max_to_post' tasks.
    Optionally attaches an image.
    """
    dm.add_log(f"Preparing to comment on up to {max_to_post} tasks", "info", group_id=group_id)
    
    # Safety check for empty task list
    if not tasks:
        dm.add_log("No tasks provided to comment on", "warning", group_id=group_id)
        return
    
    # Shuffle and limit tasks
    random.shuffle(tasks)
    tasks_to_comment = tasks[:max_to_post]
    
    dm.add_log(f"Selected {len(tasks_to_comment)} tasks for commenting", "info", group_id=group_id)
    
    # Counter for successful comments
    successful_comments = 0
    
    for i, t in enumerate(tasks_to_comment, start=1):
        link = t.get("link")
        if not link:
            dm.add_log(f"Task {i} missing link; skipping.", "warning", group_id=group_id)
            continue
            
        dm.add_log(f"Starting comment {i}/{len(tasks_to_comment)}: {t.get('title', 'Unknown Title')}", "info", group_id=group_id)
        
        try:
            post_comment_on_task(driver, link, comment_text, image_path=image_path, group_id=group_id)
            successful_comments += 1
            
            # Wait between commenting on tasks
            if i < len(tasks_to_comment):
                wait_time = random.uniform(5, 8)  # Slightly reduced wait time
                dm.add_log(f"Waiting {wait_time:.1f} seconds before next comment", "info", group_id=group_id)
                time.sleep(wait_time)
                
        except Exception as e:
            error_str = str(e)
            dm.add_log(f"Failed to comment on task {i}: {error_str}", "error", group_id=group_id)
            
            # If this is a session-related error, propagate it up for restart
            if "invalid session id" in error_str or "no such session" in error_str or "Invalid driver session" in error_str:
                dm.add_log("Browser session error detected, stopping comment process", "error", group_id=group_id)
                raise  # This will trigger the session restart in run_airtasker_bot
            
            # For other errors, try to continue with next task
            continue
    
    dm.add_log(f"Completed commenting on {successful_comments} out of {len(tasks_to_comment)} tasks", "info", group_id=group_id) 