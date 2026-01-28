import sys
import time
import os
from playwright.sync_api import sync_playwright
import pandas as pd

# Import shared modules from mca_utils package
from mca_utils.config import MCA_URLS, BROWSER_CONFIG, DEFAULT_DIN, SCREENSHOTS_DIR, MAX_VERIFICATION_ATTEMPTS
from mca_utils.captcha_solver import solve_captcha
from mca_utils.utils import get_robust_locator, type_slowly, wait_for_result_panel, get_value_by_id



def run():
    print(f" Python Executable: {sys.executable}")
    
    # DIN to verify
    DIN_NUMBER = DEFAULT_DIN
    
    # Ensure screenshots directory exists
    if not os.path.exists(SCREENSHOTS_DIR):
        os.makedirs(SCREENSHOTS_DIR)

    with sync_playwright() as p:
        print(" Launching Firefox...")
        browser = p.firefox.launch(headless=BROWSER_CONFIG['headless'])
        context = browser.new_context(viewport=BROWSER_CONFIG['viewport'])
        page = context.new_page()

        url = MCA_URLS['enquire_din_status']
        print(f" Navigating to {url}...")
        page.goto(url, wait_until='networkidle')
        page.wait_for_timeout(3000)

        target_frame = page
        
        print(" Looking for DIN/DPIN field...")
        # Robust locators for DIN input
        din_input = target_frame.locator("input[placeholder='Enter Here']").or_(
            target_frame.locator("#din")
        ).or_(
            target_frame.locator("xpath=//label[contains(text(),'DIN')]/following::input[1]")
        ).first
        
        if din_input.count() > 0:
            print(" Found DIN Input!")
            try:
                # Type DIN slowly to trigger validation
                type_slowly(din_input, DIN_NUMBER)
                print(f" Typed DIN: {DIN_NUMBER}")
                
                page.wait_for_timeout(2000)
                
                # Submit DIN
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
                captcha_modal = target_frame.locator('#newCaptchaModal')
                try:
                    captcha_modal.wait_for(state="visible", timeout=10000)
                    print(" CAPTCHA Modal appeared.")
                    
                    # Verification loop
                    for verify_attempt in range(MAX_VERIFICATION_ATTEMPTS):
                        print(f"--- Verification Attempt {verify_attempt+1}/{MAX_VERIFICATION_ATTEMPTS} ---")
                        
                        captcha_canvas = target_frame.locator('#new-captcha-canvas')
                        if captcha_canvas.count() > 0:
                            print(" Found CAPTCHA Canvas. Waiting for render...")
                            page.wait_for_timeout(1000)
                            
                            # Solve CAPTCHA using shared module
                            text = solve_captcha(target_frame, '#new-captcha-canvas', 'din')
                            time.sleep(2)
                            
                            if text:
                                captcha_input = target_frame.locator('#captcha-input')
                                captcha_input.fill(text)
                                print(" Captcha filled.")
                                
                                # Validate CAPTCHA
                                validate_btn = target_frame.locator('#validate-captcha')
                                validate_btn.click()
                                print(" Clicked Validate Captcha.")
                                
                                page.wait_for_timeout(5000)
                                # page.screenshot(path=f"{SCREENSHOTS_DIR}/din_verification_check.png")
                                
                                # Check for success
                                success_indicator = target_frame.get_by_text("DIN Details")
                                if success_indicator.count() > 0:
                                    print(" SUCCESS: Result page loaded!")
                                    
                                    # Data Extraction
                                    print(" Extracting data for Excel...")
                                    try:
                                        # Wait for result panel
                                        if wait_for_result_panel(target_frame, '#resultPanel'):
                                            print(" Result Panel is now visible. Waiting for data population...")
                                            
                                            # Extract data using utility function
                                            row = {
                                                "DIN": get_value_by_id(target_frame, "DIN"),
                                                "Director Name": get_value_by_id(target_frame, "directorName"),
                                                "DIN Status": get_value_by_id(target_frame, "DINstatus"),
                                                "Non-compliant status": get_value_by_id(target_frame, "DINactive"),
                                                "Date of Approval": get_value_by_id(target_frame, "approvalDate")
                                            }
                                            
                                            print(f" Final Extracted Data Row: {row}")
                                            
                                            # Save to Excel
                                            df = pd.DataFrame([row])
                                            excel_path = "din_status_results.xlsx"
                                            df.to_excel(excel_path, index=False)
                                            print(f" Data successfully saved to {excel_path}")
                                        
                                    except Exception as ex:
                                        print(f" Error during data extraction: {ex}")
                                        # page.screenshot(path=f"{SCREENSHOTS_DIR}/din_verification_result.png")

                                    print("Execution finished.")
                                    return
                                
                                # Check for errors
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
                                     page.screenshot(path=f"{SCREENSHOTS_DIR}/failed_attempt_{verify_attempt}.png")
                                     refresh_btn = target_frame.locator('#captcha-refresh-img')
                                     if refresh_btn.is_visible():
                                         refresh_btn.click()
                                         print(" Clicked Refresh Button.")
                                         page.wait_for_timeout(2000)
                                     continue
                                
                                print(" Status unclear, assuming success or taking final screenshot.")
                                page.screenshot(path=f"{SCREENSHOTS_DIR}/din_verification_result.png")
                                return

                            else:
                                print(" Failed to solve CAPTCHA logic.")
                        else:
                            print(" Could not find CAPTCHA canvas.")
                            break
                    
                    print(" Failed to verify DIN after multiple attempts.")
                except Exception as e:
                    print(f" Verification flow error: {e}")
                    page.screenshot(path=f"{SCREENSHOTS_DIR}/debug_verification_error.png")
                    with open(f"{SCREENSHOTS_DIR}/debug_no_modal.html", "w", encoding="utf-8") as f:
                        f.write(page.content())

            except Exception as e:
                print(f" Error during flow: {e}")
                page.screenshot(path=f"{SCREENSHOTS_DIR}/debug_error.png")

        else:
            print(" Could not find DIN/DPIN input field.")
            page.screenshot(path=f"{SCREENSHOTS_DIR}/debug_din_not_found.png")
            with open(f"{SCREENSHOTS_DIR}/debug_din_page.html", "w", encoding="utf-8") as f:
                f.write(page.content())

if __name__ == "__main__":
    run()
