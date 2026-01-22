import sys
import time
import requests
import base64
import io
import os
from PIL import Image
from playwright.sync_api import sync_playwright
from twocaptcha import TwoCaptcha

API_KEY = "06624a60934afbdc38c74dd259505ec9" 

def get_robust_locator(page_or_frame, selector_list):
    try:
        # Playwright allows comma-separated CSS for "OR" logic
        element = page_or_frame.locator(selector_list).first
        element.wait_for(state="visible", timeout=5000)
        return element
    except:
        return None


def solve_with_2captcha(frame):
    print(" Keying in on CAPTCHA image for 2Captcha...")
    try:
        # Locate the canvas or image
        # Provide a broader list of potential selectors
        # PRIORITY: specific canvas ID. Avoid generic 'img[id*="captcha"]' as it matches the refresh button ('captcha-refresh-img')
        captcha_element = get_robust_locator(frame, '#new-captcha-canvas, canvas')
        
        if not captcha_element:
            print(" Could not find CAPTCHA element.")
            frame.screenshot(path="debug_no_captcha_found.png")
            return ""

        # 1. Define paths
        raw_filename = "screenshots/captcha_original.png"
        processed_filename = "screenshots/captcha_processed.png"
        
        # 2. Screenshot the raw CAPTCHA
        captcha_element.screenshot(path=raw_filename)
        print(f" Saved raw CAPTCHA to {raw_filename}")
        
        # 3. Create a copy for processing so we keep the original for debugging
        original_img = Image.open(raw_filename)
        original_img.save(processed_filename)
        
        # 4. Clean the copy - DISABLED (User requested raw image)
        # clean_image(processed_filename)

        # 5. Send to 2Captcha with RETRY Logic
        solver = TwoCaptcha(API_KEY)
        max_retries = 5
        
        for attempt in range(max_retries):
            try:
                print(f" Attempt {attempt+1}/{max_retries}: Sending CAPTCHA to 2Captcha...")
                
                # Option: Convert to JPG to avoid PNG alpha issues/size
                jpg_filename = raw_filename.replace(".png", ".jpg")
                img = Image.open(raw_filename)
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                img.save(jpg_filename, "JPEG", quality=90)

                # Config for this attempt
                config = {
                    'server':           '2captcha.com',
                    'apiKey':           API_KEY,
                    'defaultTimeout':    120,
                    'pollingInterval':   5
                }
                solver = TwoCaptcha(**config)

                # Attempt solve
                result = solver.normal(jpg_filename, caseSensitive=1, case=1, minLength=6, maxLength=6)
                print(f" DEBUG: Raw 2Captcha Response: {result}")
                
                if 'code' in result:
                    solved_text = result['code']
                    print(f" CAPTCHA Solved: {solved_text}")
                    
                    # Logging
                    final_log_path = f"screenshots/solved_{solved_text}.png"
                    if os.path.exists(final_log_path):
                        os.remove(final_log_path)
                    os.rename(raw_filename, final_log_path)
                    print(f" Saved debug image to: {final_log_path}")
                    return solved_text
                else:
                    print(f" No code received: {result}")
            
            except Exception as loop_e:
                print(f" Attempt {attempt+1} failed: {loop_e}")
                time.sleep(5) # Wait before retry
        
        print(" All retry attempts failed.")
        raise Exception("Failed to solve CAPTCHA after retries")

    except Exception as e:
        print(f" 2Captcha Helper Error: {e}")
        return ""

def run():
    print(f" Python Executable: {sys.executable}")
    
    # Placeholder DIN
    DIN_NUMBER = "08560072" 
    

    # Ensure screenshots directory exists
    if not os.path.exists("screenshots"):
        os.makedirs("screenshots")

    with sync_playwright() as p:
        print(" Launching Firefox...")
        browser = p.firefox.launch(headless=False)
        context = browser.new_context(viewport={'width': 1366, 'height': 768})
        page = context.new_page()

        url = "https://www.mca.gov.in/content/mca/global/en/mca/fo-llp-services/enquire-din-status.html"
        print(f" Navigating to {url}...")
        page.goto(url, wait_until='networkidle')
        page.wait_for_timeout(3000)

        # We try to find the inputs on the main page first (or frames)
        target_frame = page
        
        print(" Looking for DIN/DPIN field...")
        # Locators for DIN input - Corrected Playwright OR logic
        din_input = target_frame.locator("input[placeholder='Enter Here']").or_(
            target_frame.locator("#din")
        ).or_(
            target_frame.locator("xpath=//label[contains(text(),'DIN')]/following::input[1]")
        ).first
        
        if din_input.count() > 0:
            print(" Found DIN Input!")
            try:
                # Clear and fill - accessing valid DIN
                din_input.click()
                din_input.fill("")
                # Type character by character to trigger any onkeyup/oninput events
                for char in DIN_NUMBER:
                    din_input.type(char, delay=100)
                
                print(f" Typed DIN: {DIN_NUMBER}")
                
                # Wait for validation to enable submit button
                page.wait_for_timeout(2000)
                
                # Submit DIN - Corrected Playwright OR logic
                print(" Clicking Submit...")
                submit_din_btn = target_frame.locator("button:has-text('Submit')").or_(
                    target_frame.locator("#submitdin")
                ).or_(
                    target_frame.locator("input[value='Submit']")
                ).or_(
                    target_frame.locator("xpath=//button[normalize-space()='Submit']")
                ).first
                
                if submit_din_btn.count() > 0:
                    submit_din_btn.click()
                    print(" Clicked Submit.")
                else:
                    print(" Submit button not visible/found.")
                
                page.wait_for_timeout(2000)

                # Wait for CAPTCHA Modal
                print(" Waiting for CAPTCHA modal...")
                # The modal id is newCaptchaModal
                captcha_modal = target_frame.locator('#newCaptchaModal')
                try:
                    captcha_modal.wait_for(state="visible", timeout=10000)
                    print(" CAPTCHA Modal appeared.")
                    
                    # Canvas locator
                    captcha_canvas = target_frame.locator('#new-captcha-canvas')
                    
                    max_verification_attempts = 3
                    for verify_attempt in range(max_verification_attempts):
                        print(f"--- Verification Attempt {verify_attempt+1}/{max_verification_attempts} ---")
                        
                        if captcha_canvas.count() > 0:
                            print(" Found CAPTCHA Canvas. Waiting for render...")
                            page.wait_for_timeout(1000)
                            
                            # Call the robust solver function
                            text = solve_with_2captcha(target_frame)
                            time.sleep(2) # Wait for fill
                            
                            if text:
                                captcha_input = target_frame.locator('#captcha-input')
                                captcha_input.fill(text)
                                print(" Captcha filled.")
                                
                                # Click Validate Captcha
                                validate_btn = target_frame.locator('#validate-captcha')
                                validate_btn.click()
                                print(" Clicked Validate Captcha.")
                                
                                # Wait for results or error
                                page.wait_for_timeout(5000)
                                
                                # Use text matching to see if we got the result page
                                # Screenshot for debug
                                page.screenshot(path="screenshots/din_verification_check.png")
                                
                                # Check for Success (Director Name or similar)
                                # The user's screenshot shows "DIN Details" as a header
                                success_indicator = target_frame.get_by_text("DIN Details")
                                if success_indicator.count() > 0:
                                    print(" SUCCESS: Result page loaded!")
                                    
                                    # Data Extraction Logic
                                    print(" Extracting data for Excel...")
                                    try:
                                        import pandas as pd
                                        
                                        # Wait for the result panel to be populated and shown
                                        result_panel = target_frame.locator('#resultPanel')
                                        result_panel.wait_for(state="visible", timeout=15000)
                                        print(" Result Panel is now visible. Waiting 3s for data population...")
                                        page.wait_for_timeout(3000)
                                        
                                        # Function to get value by ID using direct JS evaluate for disabled fields
                                        def get_val_by_id(element_id):
                                            try:
                                                # Sometimes .input_value() fails on disabled/populated-by-js fields
                                                # .evaluate() is more reliable for raw DOM value
                                                val = target_frame.locator(f"#{element_id}").first.evaluate("el => el.value")
                                                print(f"  Scraped #{element_id}: '{val}'")
                                                return val if val and val.strip() != "" else "N/A"
                                            except Exception as e:
                                                print(f"  Debug: Failed to get #{element_id}: {e}")
                                                return "N/A"

                                        row = {
                                            "DIN": get_val_by_id("DIN"),
                                            "Director Name": get_val_by_id("directorName"),
                                            "DIN Status": get_val_by_id("DINstatus"),
                                            "Non-compliant status": get_val_by_id("DINactive"),
                                            "Date of Approval": get_val_by_id("approvalDate")
                                        }
                                        
                                        print(f" Final Extracted Data Row: {row}")
                                        
                                        # Save to Excel
                                        df = pd.DataFrame([row])
                                        excel_path = "din_status_results.xlsx"
                                        df.to_excel(excel_path, index=False)
                                        print(f" Data successfully saved to {excel_path}")
                                        
                                    except Exception as ex:
                                        print(f" Error during data extraction: {ex}")
                                        # Fallback screenshot
                                        page.screenshot(path="screenshots/din_verification_result.png")

                                    print("Execution finished.")
                                    return
                                
                                # Check for Error
                                error_text_locator = target_frame.locator(".errormsg").or_(
                                    target_frame.locator(".alert-danger")
                                ).or_(
                                    target_frame.locator("text='Incorrect Captcha'")
                                ).or_(
                                    target_frame.locator("text='Enter valid text'")
                                ).or_(
                                    target_frame.locator("text='Captcha match failed'")
                                )
                                
                                if error_text_locator.count() > 0 and error_text_locator.first.is_visible():
                                     print(" FAILURE: Incorrect Captcha detected.")
                                     page.screenshot(path=f"screenshots/failed_attempt_{verify_attempt}.png")
                                     refresh_btn = target_frame.locator('#captcha-refresh-img')
                                     if refresh_btn.is_visible():
                                         refresh_btn.click()
                                         print(" Clicked Refresh Button.")
                                         page.wait_for_timeout(2000)
                                     continue
                                
                                print(" Status unclear, assuming success or taking final screenshot.")
                                page.screenshot(path="screenshots/din_verification_result.png")
                                return

                            else:
                                print(" Failed to solve CAPTCHA logic.")
                        else:
                            print(" Could not find CAPTCHA canvas.")
                            break
                    
                    print(" Failed to verify DIN after multiple attempts.")
                except Exception as e:
                    print(f" Verification flow error: {e}")
                    page.screenshot(path="screenshots/debug_verification_error.png")
                    with open("screenshots/debug_no_modal.html", "w", encoding="utf-8") as f:
                        f.write(page.content())

            except Exception as e:
                print(f" Error during flow: {e}")
                page.screenshot(path="screenshots/debug_error.png")

        else:
            print(" Could not find DIN/DPIN input field.")
            page.screenshot(path="screenshots/debug_din_not_found.png")
            with open("screenshots/debug_din_page.html", "w", encoding="utf-8") as f:
                f.write(page.content())

if __name__ == "__main__":
    run()
