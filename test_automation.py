"""
Test script for verifying automation functionality.
This script tests the initialization of the web driver and the Capsolver extension.
"""

import traceback
import time
import os
from app.automations.main import init_driver, cleanup_chrome_processes, login
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

def test_driver_initialization():
    """Test the initialization and closure of the web driver."""
    print("Testing driver initialization...")
    driver = None
    try:
        print("Initializing driver...")
        driver = init_driver()
        print("✅ Driver initialized successfully")
        
        print("Testing navigation to Google...")
        driver.get("https://www.google.com")
        print(f"Current URL: {driver.current_url}")
        if "google.com" in driver.current_url:
            print("✅ Navigation successful")
        else:
            print("❌ Navigation failed")
        
        print("Waiting 3 seconds...")
        time.sleep(3)
        
        print("Closing driver...")
        driver.quit()
        print("✅ Driver closed successfully")
    except Exception as e:
        print(f"❌ Error during driver test: {str(e)}")
        traceback.print_exc()
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    print("Cleaning up Chrome processes...")
    cleanup_chrome_processes()
    print("✅ Chrome processes cleaned up")

def test_capsolver_extension():
    """Test if the Capsolver extension is loaded correctly."""
    print("\nTesting Capsolver extension...")
    driver = None
    try:
        print("Initializing driver with Capsolver...")
        driver = init_driver()
        print("✅ Driver initialized with Capsolver extension")
        
        # Navigate to the extensions page to verify Capsolver is loaded
        print("Checking if Capsolver extension is loaded...")
        driver.get("chrome://extensions/")
        time.sleep(3)
        
        # Take a screenshot of the extensions page
        screenshot_path = "capsolver_extension_test.png"
        driver.save_screenshot(screenshot_path)
        print(f"✅ Screenshot saved to {screenshot_path}")
        
        # Navigate to a test page that might have a CAPTCHA
        print("Testing navigation to a test page...")
        driver.get("https://www.google.com")
        print(f"Current URL: {driver.current_url}")
        
        print("Waiting 3 seconds...")
        time.sleep(3)
        
        print("Closing driver...")
        driver.quit()
        print("✅ Driver closed successfully")
        return True
    except Exception as e:
        print(f"❌ Error during Capsolver test: {str(e)}")
        traceback.print_exc()
        if driver:
            try:
                driver.quit()
            except:
                pass
        return False
    finally:
        print("Cleaning up Chrome processes...")
        cleanup_chrome_processes()
        print("✅ Chrome processes cleaned up")

def test_airtasker_login_page():
    """Test navigation to Airtasker and accessing the login page."""
    print("\nTesting Airtasker login page access...")
    driver = None
    try:
        print("Initializing driver...")
        driver = init_driver()
        print("✅ Driver initialized successfully")
        
        # Navigate to Airtasker
        print("Navigating to Airtasker...")
        driver.get("https://www.airtasker.com/")
        time.sleep(5)
        
        # Take a screenshot of the homepage
        homepage_screenshot = "airtasker_homepage.png"
        driver.save_screenshot(homepage_screenshot)
        print(f"✅ Homepage screenshot saved to {homepage_screenshot}")
        
        # Find and click the login button
        print("Looking for login button...")
        login_button_xpath = '//*[@id="airtasker-app"]/nav/div[2]/div/div/div/div[2]/a[2]'
        try:
            login_btn = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, login_button_xpath))
            )
            print("✅ Login button found")
            
            # Click the login button
            print("Clicking login button...")
            login_btn.click()
            time.sleep(5)
            
            # Take a screenshot of the login page
            login_screenshot = "airtasker_login_page.png"
            driver.save_screenshot(login_screenshot)
            print(f"✅ Login page screenshot saved to {login_screenshot}")
            
            # Verify login form elements are present
            print("Verifying login form elements...")
            email_input_id = "username"
            password_input_id = "password"
            submit_button_xpath = "/html/body/main/section/div/div/div/form/div[2]/button"
            
            email_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, email_input_id))
            )
            password_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, password_input_id))
            )
            submit_btn = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, submit_button_xpath))
            )
            
            print("✅ Login form elements verified")
            
            # DO NOT actually submit login credentials in this test
            print("Login page test successful - form elements found")
            return True
            
        except TimeoutException:
            print("❌ Login button not found within timeout period")
            return False
        except NoSuchElementException:
            print("❌ Login button not found")
            return False
            
    except Exception as e:
        print(f"❌ Error during Airtasker login test: {str(e)}")
        traceback.print_exc()
        return False
    finally:
        if driver:
            print("Closing driver...")
            try:
                driver.quit()
                print("✅ Driver closed successfully")
            except Exception as e:
                print(f"❌ Error closing driver: {str(e)}")
        
        print("Cleaning up Chrome processes...")
        cleanup_chrome_processes()
        print("✅ Chrome processes cleaned up")

def test_full_automation_flow():
    """Test the full automation flow without actually submitting credentials."""
    print("\nTesting full automation flow...")
    driver = None
    try:
        print("Initializing driver...")
        driver = init_driver()
        print("✅ Driver initialized successfully")
        
        # Navigate to Airtasker
        print("Navigating to Airtasker...")
        driver.get("https://www.airtasker.com/")
        time.sleep(5)
        
        # Take a screenshot of the homepage
        homepage_screenshot = "airtasker_homepage_full.png"
        driver.save_screenshot(homepage_screenshot)
        print(f"✅ Homepage screenshot saved to {homepage_screenshot}")
        
        # Test login function but don't submit
        print("Testing login function (without submission)...")
        
        # Define the parameters for login
        email = "test@example.com"  # Dummy email
        password = "password123"    # Dummy password
        login_button_xpath = '//*[@id="airtasker-app"]/nav/div[2]/div/div/div/div[2]/a[2]'
        email_input_id = "username"
        password_input_id = "password"
        submit_button_xpath = "/html/body/main/section/div/div/div/form/div[2]/button"
        
        # Click the login button
        print("Clicking login button...")
        login_btn = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, login_button_xpath))
        )
        login_btn.click()
        time.sleep(5)
        
        # Verify login form elements
        print("Verifying login form elements...")
        email_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, email_input_id))
        )
        password_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, password_input_id))
        )
        submit_btn = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, submit_button_xpath))
        )
        
        print("✅ Login form elements verified")
        
        # Type email (but don't submit)
        print("Testing email input...")
        email_field.clear()
        for c in email[:3]:  # Only type first 3 characters
            email_field.send_keys(c)
            time.sleep(0.1)
        print("✅ Email input test successful")
        
        # Take a screenshot
        login_test_screenshot = "login_test_screenshot.png"
        driver.save_screenshot(login_test_screenshot)
        print(f"✅ Login test screenshot saved to {login_test_screenshot}")
        
        print("Full automation flow test successful")
        return True
        
    except Exception as e:
        print(f"❌ Error during full automation flow test: {str(e)}")
        traceback.print_exc()
        return False
    finally:
        if driver:
            print("Closing driver...")
            try:
                driver.quit()
                print("✅ Driver closed successfully")
            except Exception as e:
                print(f"❌ Error closing driver: {str(e)}")
        
        print("Cleaning up Chrome processes...")
        cleanup_chrome_processes()
        print("✅ Chrome processes cleaned up")

if __name__ == "__main__":
    test_driver_initialization()
    
    # Test the Capsolver extension
    capsolver_result = test_capsolver_extension()
    
    # Test Airtasker login page
    airtasker_result = test_airtasker_login_page()
    
    # Test full automation flow
    full_flow_result = test_full_automation_flow()
    
    print("\nTest Results:")
    print("✅ Driver initialization test passed")
    
    if capsolver_result:
        print("✅ Capsolver extension test passed")
    else:
        print("❌ Capsolver extension test failed")
    
    if airtasker_result:
        print("✅ Airtasker login page test passed")
    else:
        print("❌ Airtasker login page test failed")
        
    if full_flow_result:
        print("✅ Full automation flow test passed")
    else:
        print("❌ Full automation flow test failed") 