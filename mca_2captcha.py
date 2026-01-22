import sys
import time
import requests
import base64
import io
from PIL import Image
from playwright.sync_api import sync_playwright

API_KEY = "8072198a4b4327511362993564821984" 

def get_robust_locator(page_or_frame, selector_list):

    try:
        # Playwright allows comma-separated CSS for "OR" logic
        element = page_or_frame.locator(selector_list).first
        element.wait_for(state="visible", timeout=5000)
        return element
    except:
        return None

from twocaptcha import TwoCaptcha

def solve_with_2captcha(frame):
    print(" keying in on CAPTCHA image for 2Captcha...")
    try:
        # Locate the CAPTCHA image
        captcha_img = get_robust_locator(frame, 'img[id*="captcha"], img[src*="captcha"], #captcha')
        
        if not captcha_img:
            print(" Could not find CAPTCHA image element.")
            return ""

        # Save image locally as requested
        img_path = "captcha.png"
        captcha_img.screenshot(path=img_path)
        print(f" Saved '{img_path}' locally.")

        print("Sending CAPTCHA to 2Captcha...")
        
        solver = TwoCaptcha(API_KEY)
        
        # Valid parameters for Normal Captcha (ImageToTextTask)
        # numeric: 4 (Both numbers and letters), min_len: 6, max_len: 6, case: 1 (True)
        result = solver.normal(img_path, numeric=6, minLength=6, maxLength=6, caseSensitive=1)
        
        if 'code' in result:
             print(f"CAPTCHA Solved: {result['code']}")
             return result['code']
        else:
             print(f"2Captcha Error: Result format unexpected {result}")
             return ""

    except Exception as e:
        print(f"2Captcha Helper Error: {e}")
    return ""

def run():
    print(f" Python Executable: {sys.executable}")
    

    with sync_playwright() as p:
        print(" Launching Firefox...")
        browser = p.firefox.launch(headless=False)
        context = browser.new_context(viewport={'width': 1366, 'height': 768})
        page = context.new_page()

        print(" Navigating to MCA Login...")
        page.goto('https://www.mca.gov.in', wait_until='networkidle')
        page.wait_for_timeout(3000)

        # CHECK IF WE NEED TO CLICK SIGN IN
        signin_btn = page.locator('#signin, a[href*="fologin.html"], button:has-text("Sign In"), span:has-text("Sign In")').first
        if signin_btn.count() > 0 and signin_btn.is_visible():
            print(" Clicking 'Sign In' button to trigger modal/form...")
            signin_btn.click()
            page.wait_for_timeout(3000) 

        # We try to find the inputs on the main page first (or frames)
        target_frame = page
        
        print(" Looking for User ID field...")
        user_input = get_robust_locator(target_frame, '#userName, input[name="userName"], input[placeholder*="User"], input[aria-label*="User ID"], input[type="text"]:visible')
        
        if not user_input:
            print(" Inputs not found on main page. Checking frames...")
            for frame in page.frames:
                user_input = get_robust_locator(frame, '#userName, input[name="userName"], input[placeholder*="User"], input[aria-label*="User ID"], input[type="text"]:visible')
                if user_input:
                    target_frame = frame
                    print(f" Found User Input in frame: {frame.name}")
                    break
        
        if user_input:
            print(" Found User Input!")
            try:
                user_input.fill('kevinraj20@gmail.com')
            except Exception as e:
                print(f" Error filling user input: {e}")
            
            print(" Looking for Password field...")
            pass_input = get_robust_locator(target_frame, '#password, input[name="password"], input[type="password"]')
            if pass_input:
                try:
                    pass_input.fill('TbT@629002')
                    print(" Password filled.")
                except Exception as e:
                    print(f" Error filling password: {e}")
            
            # SOLVE CAPTCHA WITH 2CAPTCHA
            text = solve_with_2captcha(target_frame)
            
            if text:
                print(f" Entering Captcha: {text}")
                captcha_input = get_robust_locator(target_frame, 'input[id*="captcha" i], input[placeholder*="Enter"], input[name*="captcha" i]')
                if captcha_input:
                    try:
                        captcha_input.fill(text)
                        print(" Captcha filled.")
                    except Exception as e:
                         print(f"Error filling captcha: {e}")
                    
                    # Click Login
                    login_btn = get_robust_locator(target_frame, 'input[value="Sign In"], button:has-text("Sign In")')
                    if login_btn:
                        print(" Clicking 'Sign In' button...")
                        login_btn.click()
                        
                        # Wait for navigation or error
                        page.wait_for_timeout(5000)
                        
                        # Check for success
                        if "dashboard" in page.url or "my-workspace" in page.url:
                             print(" Login Successful! Redirected to Dashboard.")
                        elif page.locator('div:has-text("Wrong Captcha"), div:has-text("Invalid")').count() > 0:
                             print(" Login Failed: Wrong Captcha or Invalid Credentials.")
                        else:
                             print(f"ℹ Login Clicked. Current URL: {page.url}")
                             page.screenshot(path="login_2captcha_result.png")
            
            print("Execution finished.")
            page.screenshot(path="final_2captcha_state.png")
            page.wait_for_timeout(2000)
            
        else:
            print(" Could not find login fields even with robust locators.")
            page.screenshot(path="debug_not_found_2captcha.png")

        browser.close()

if __name__ == "__main__":
    run()
