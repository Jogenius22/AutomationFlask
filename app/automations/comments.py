# comments.py
import time
import random
import os
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException, StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from app import data_manager as dm

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

# Helper function to save screenshots
def save_screenshot(driver, prefix, group_id):
    """Helper function to save screenshots to a consistent location"""
    try:
        timestamp = int(time.time())
        screenshots_dir = os.path.join(os.getcwd(), 'screenshots')
        os.makedirs(screenshots_dir, exist_ok=True)
        filename = f"{prefix}_{timestamp}.png"
        filepath = os.path.join(screenshots_dir, filename)
        driver.save_screenshot(filepath)
        # Log the screenshot
        dm.add_log(f"Screenshot saved: {filename}", "info", group_id=group_id)
        return filename
    except Exception as e:
        dm.add_log(f"Failed to save screenshot: {str(e)}", "error", group_id=group_id)
        return None

def post_comment_on_task(driver, task_url, comment_text=None, image_path=None, group_id=None):
    """
    Navigates to the given task URL, posts the provided comment,
    optionally attaches an image, and clicks 'Send'.
    """
    dm.add_log(f"Posting comment on: {task_url}", "info", group_id=group_id)
    
    try:
        driver.get(task_url)
        time.sleep(random.uniform(5, 8))
        
        # Take screenshot of task page
        save_screenshot(driver, "task_page", group_id)
    
        # If no comment text provided, use random template
        if not comment_text:
            comment_text = pick_random_comment()
            dm.add_log("Using randomly selected comment template", "info", group_id=group_id)
        
        dm.add_log(f"Comment to post: {comment_text}", "info", group_id=group_id)
    
        # XPaths for the comment textarea and the 'Send' button - updated to be more robust
        comment_box_xpaths = [
            '//*[@id="airtasker-app"]/main/div/div[1]/div[3]/div/div/div[2]/div/div[6]/div/div[2]/div/div/div/div/div[3]/textarea',
            '//textarea[contains(@placeholder, "Comment")]',
            '//div[contains(@class, "CommentBox")]//textarea'
        ]
        
        send_button_xpaths = [
            '//*[@id="airtasker-app"]/main/div/div[1]/div[3]/div/div/div[2]/div/div[6]/div/div[2]/div/div/div/div/div[3]/div/span/button',
            '//button[text()="Send"]',
            '//button[contains(@class, "SendButton")]'
        ]
        
        # XPath for file upload input (for optional image attachment)
        attach_input_xpath = '//*[@data-ui-test="upload-attachment-input"]'
    
        # Find comment box using multiple potential XPaths
        comment_box = None
        for xpath in comment_box_xpaths:
            try:
                comment_box = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
                dm.add_log(f"Found comment box using xpath: {xpath}", "info", group_id=group_id)
                break
            except (TimeoutException, NoSuchElementException):
                continue
                
        if not comment_box:
            dm.add_log("Could not find comment box after trying all XPaths", "error", group_id=group_id)
            save_screenshot(driver, "comment_box_not_found", group_id)
            return False
    
        # Clear and enter text in comment box
        try:
            comment_box.clear()
            # Type with human-like delays
            for c in comment_text:
                comment_box.send_keys(c)
                time.sleep(random.uniform(0.03, 0.12))
            time.sleep(random.uniform(2, 4))
            dm.add_log("Comment text entered successfully", "info", group_id=group_id)
        except Exception as e:
            dm.add_log(f"Error entering comment text: {str(e)}", "error", group_id=group_id)
            save_screenshot(driver, "comment_text_error", group_id)
            return False
    
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
        
        # Find and click send button using multiple potential XPaths
        send_button = None
        for xpath in send_button_xpaths:
            try:
                send_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                dm.add_log(f"Found send button using xpath: {xpath}", "info", group_id=group_id)
                break
            except (TimeoutException, NoSuchElementException):
                continue
                
        if not send_button:
            dm.add_log("Could not find send button after trying all XPaths", "error", group_id=group_id)
            save_screenshot(driver, "send_button_not_found", group_id)
            return False
            
        # Try to click the button with multiple strategies
        try:
            send_button.click()
            dm.add_log("Clicked send button", "info", group_id=group_id)
        except (ElementClickInterceptedException, StaleElementReferenceException) as e:
            dm.add_log(f"Error clicking send button: {str(e)}", "warning", group_id=group_id)
            try:
                # Try using JavaScript to click
                driver.execute_script("arguments[0].click();", send_button)
                dm.add_log("Used JavaScript to click send button", "info", group_id=group_id)
            except Exception as js_e:
                dm.add_log(f"JavaScript click failed: {str(js_e)}", "error", group_id=group_id)
                save_screenshot(driver, "send_button_js_error", group_id)
                return False
        
        # Take screenshot after posting comment
        time.sleep(random.uniform(2, 3))
        save_screenshot(driver, "after_send_comment", group_id)
        
        dm.add_log("Comment posted successfully!", "success", group_id=group_id)
        time.sleep(random.uniform(3, 6))
        return True
        
    except Exception as e:
        dm.add_log(f"Unexpected error posting comment: {str(e)}", "error", group_id=group_id)
        save_screenshot(driver, "comment_error", group_id)
        return False

def comment_on_some_tasks(driver, tasks, message_content=None, max_to_post=3, image_path=None, group_id=None):
    """
    Given a list of task dicts (each with a 'link'),
    posts the provided comment on up to 'max_to_post' tasks.
    Optionally attaches an image.
    """
    if not tasks:
        dm.add_log("No tasks provided to comment on", "warning", group_id=group_id)
        return 0
        
    dm.add_log(f"Preparing to comment on up to {max_to_post} tasks", "info", group_id=group_id)
    
    # Ensure tasks is a list and has 'link' attribute
    valid_tasks = [t for t in tasks if isinstance(t, dict) and t.get('link')]
    
    if not valid_tasks:
        dm.add_log("No valid tasks with links found", "warning", group_id=group_id)
        return 0
    
    # Shuffle to randomize order and limit to max_to_post
    random.shuffle(valid_tasks)
    tasks_to_comment = valid_tasks[:max_to_post]
    
    dm.add_log(f"Selected {len(tasks_to_comment)} tasks for commenting", "info", group_id=group_id)
    
    success_count = 0
    for i, t in enumerate(tasks_to_comment, start=1):
        link = t.get("link")
        title = t.get('title', 'Unknown Title')
            
        dm.add_log(f"Starting comment {i}/{len(tasks_to_comment)}: {title}", "info", group_id=group_id)
        
        # Log the actual message content being used
        if message_content:
            dm.add_log(f"Using custom message", "info", group_id=group_id)
        else:
            dm.add_log("Using randomly generated message", "info", group_id=group_id)
            
        if post_comment_on_task(driver, link, message_content, image_path=image_path, group_id=group_id):
            success_count += 1
        
        # Wait between commenting on tasks
        if i < len(tasks_to_comment):
            wait_time = random.uniform(5, 10)
            dm.add_log(f"Waiting {wait_time:.1f} seconds before next comment", "info", group_id=group_id)
            time.sleep(wait_time)
    
    dm.add_log(f"Completed commenting on {success_count}/{len(tasks_to_comment)} tasks successfully", "info", group_id=group_id)
    return success_count 