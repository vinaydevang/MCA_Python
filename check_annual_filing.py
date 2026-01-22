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
        captcha_element = get_robust_locator(frame, '#captchaCanvas, canvas')
        
        if not captcha_element:
            print(" Could not find CAPTCHA element.")
            frame.screenshot(path="debug_no_captcha_found.png")
            return ""

        # 1. Define paths
        raw_filename = "screenshots/captcha_annual_original.png"
        
        # 2. Screenshot the raw CAPTCHA
        captcha_element.screenshot(path=raw_filename)
        print(f" Saved raw CAPTCHA to {raw_filename}")
        
        # 3. Send to 2Captcha with RETRY Logic
        solver = TwoCaptcha(API_KEY)
        max_retries = 5
        
        for attempt in range(max_retries):
            try:
                print(f" Attempt {attempt+1}/{max_retries}: Sending CAPTCHA to 2Captcha...")
                
                # Convert to JPG
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

                # Attempt solve - Using the same strict logic as verify_din
                result = solver.normal(jpg_filename, caseSensitive=1, case=1, minLength=6, maxLength=6)
                print(f" DEBUG: Raw 2Captcha Response: {result}")
                
                if 'code' in result:
                    solved_text = result['code']
                    print(f" CAPTCHA Solved: {solved_text}")
                    
                    # Logging
                    final_log_path = f"screenshots/solved_annual_{solved_text}.png"
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
    
    # Placeholder CIN
    CIN_NUMBER = "L01100KA2021PTC147817" # Replace with user's desired CIN if needed
    
    # Ensure screenshots directory exists
    if not os.path.exists("screenshots"):
        os.makedirs("screenshots")

    with sync_playwright() as p:
        print(" Launching Firefox...")
        # Headed mode so user can see
        browser = p.firefox.launch(headless=False)
        context = browser.new_context(viewport={'width': 1366, 'height': 768})
        page = context.new_page()

        url = "https://www.mca.gov.in/content/mca/global/en/mca/fo-llp-services/check-annual-filing-status.html"
        print(f" Navigating to {url}...")
        page.goto(url, wait_until='networkidle')
        page.wait_for_timeout(3000)

        target_frame = page
        
        print(" Looking for CIN field (#masterdata-search-box)...")
        cin_input = get_robust_locator(target_frame, '#masterdata-search-box')
        
        if cin_input:
            print(" Found CIN Input!")
            try:
                # Clear and fill
                cin_input.click()
                cin_input.fill("")
                for char in CIN_NUMBER:
                    cin_input.type(char, delay=100)
                print(f" Typed CIN: {CIN_NUMBER}")
                
                # Click Search Icon
                print(" Clicking Search Icon (#searchicon)...")
                search_icon = get_robust_locator(target_frame, '#searchicon')
                if search_icon:
                    search_icon.click()
                else:
                    cin_input.press("Enter")
                
                page.wait_for_timeout(2000)

                # Wait for CAPTCHA Modal
                print(" Waiting for CAPTCHA modal (#captchaModal)...")
                captcha_modal = target_frame.locator('#captchaModal')
                try:
                    captcha_modal.wait_for(state="visible", timeout=10000)
                    print(" CAPTCHA Modal appeared.")
                    
                    # Outer Verification Loop
                    max_verification_attempts = 3
                    for verify_attempt in range(max_verification_attempts):
                         print(f"--- Verification Attempt {verify_attempt+1}/{max_verification_attempts} ---")
                         
                         captcha_canvas = target_frame.locator('#captchaCanvas, canvas').first
                         if captcha_canvas.count() > 0:
                             print(" Found CAPTCHA Canvas. Waiting for render...")
                             page.wait_for_timeout(1000)
                             
                             # Solve
                             text = solve_with_2captcha(target_frame)
                             time.sleep(2)
                             
                             if text:
                                 captcha_input = target_frame.locator('#customCaptchaInput')
                                 captcha_input.fill(text)
                                 print(f" Filled CAPTCHA with: {text}")
                                 
                                 # Submit
                                 submit_btn = target_frame.locator('#check')
                                 submit_btn.click()
                                 print(" Clicked Submit.")
                                 
                                 page.wait_for_timeout(5000)
                                 
                                 # Check for Success (Table appearance)
                                 success_indicator = target_frame.locator(".annual_filing_table, #annualFilingTable")
                                 if success_indicator.count() > 0:
                                     print(" SUCCESS: Result page loaded!")
                                     page.screenshot(path="screenshots/annual_filing_result.png")
                                     
                                     # Data Extraction Logic
                                     print(" Extracting data for Excel...")
                                     try:
                                         import pandas as pd
                                         
                                         # Scrape table data
                                         # MCA annual filing tables usually have rows of data
                                         # This is a generic table scraper for the results
                                         rows = []
                                         table = target_frame.locator(".annual_filing_table, #annualFilingTable").first
                                         headers = table.locator("th").all_inner_texts()
                                         
                                         data_rows = table.locator("tr").all()
                                         for dr in data_rows:
                                             cells = dr.locator("td").all_inner_texts()
                                             if len(cells) > 0:
                                                 rows.append(dict(zip(headers, cells)))
                                         
                                         if not rows:
                                             # Fallback for the 5-field style or single row
                                             # Let's try to get all inputs/labels if it's not a table
                                             def get_val_by_label(label):
                                                 try:
                                                     return target_frame.locator(f"//div[contains(., '{label}')]/following::input[1]").evaluate("el => el.value")
                                                 except: return "N/A"
                                             
                                             row = {
                                                 "CIN": CIN_NUMBER,
                                                 "Company Name": get_val_by_label("Company Name"),
                                                 "Company Status": get_val_by_label("Company Status"),
                                                 "Annual Return Date": get_val_by_label("Annual Return"),
                                                 "Balance Sheet Date": get_val_by_label("Balance Sheet")
                                             }
                                             rows = [row]

                                         print(f" Extracted Data: {rows}")
                                         
                                         # Save to Excel
                                         df = pd.DataFrame(rows)
                                         excel_path = "annual_filing_results.xlsx"
                                         df.to_excel(excel_path, index=False)
                                         print(f" Data saved to {excel_path}")
                                         
                                     except Exception as ex:
                                         print(f" Error during data extraction: {ex}")

                                     print("Execution finished.")
                                     return
                                 
                                 # Check for Errors
                                 error_text = target_frame.locator(".errormsg, .alert-danger, text='Incorrect Captcha', text='Enter valid text'").first
                                 if error_text.count() > 0 and error_text.is_visible():
                                      print(" FAILURE: Incorrect Captcha detected.")
                                      page.screenshot(path=f"screenshots/failed_annual_attempt_{verify_attempt}.png")
                                      # Refresh
                                      refresh_btn = target_frame.locator('#captchaRefresh, .captcha-refresh')
                                      if refresh_btn.count() > 0:
                                          refresh_btn.click()
                                          page.wait_for_timeout(2000)
                                      continue
                                 
                                 print(" Status unclear, taking final screenshot.")
                                 page.screenshot(path="screenshots/annual_filing_final.png")
                                 return
                             else:
                                 print(" Failed to solve CAPTCHA.")
                         else:
                             print(" Canvas not found.")
                             break
                    
                    print(" Failed verification after retries.")
                except Exception as e:
                    print(f" Verification flow error: {e}")
            
            except Exception as e:
                print(f" Error: {e}")
                page.screenshot(path="screenshots/debug_annual_error.png")
        else:
             print(" CIN input not found.")

if __name__ == "__main__":
    run()
