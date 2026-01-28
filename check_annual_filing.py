import sys
import time
import os
from playwright.sync_api import sync_playwright
import pandas as pd

# Import shared modules from mca_utils package
from mca_utils.config import MCA_URLS, BROWSER_CONFIG, DEFAULT_CIN, SCREENSHOTS_DIR, MAX_VERIFICATION_ATTEMPTS
from mca_utils.captcha_solver import solve_captcha
from mca_utils.utils import get_robust_locator, type_slowly



def run():
    print(f" Python Executable: {sys.executable}")
    
    # CIN to check
    CIN_NUMBER = DEFAULT_CIN
    
    # Ensure screenshots directory exists
    if not os.path.exists(SCREENSHOTS_DIR):
        os.makedirs(SCREENSHOTS_DIR)

    with sync_playwright() as p:
        print(" Launching Firefox...")
        browser = p.firefox.launch(headless=BROWSER_CONFIG['headless'])
        context = browser.new_context(viewport=BROWSER_CONFIG['viewport'])
        page = context.new_page()

        url = MCA_URLS['check_annual_filing']
        print(f" Navigating to {url}...")
        page.goto(url, wait_until='networkidle')
        page.wait_for_timeout(3000)

        target_frame = page
        
        print(" Looking for CIN field (#masterdata-search-box)...")
        cin_input = get_robust_locator(target_frame, '#masterdata-search-box')
        
        if cin_input:
            print(" Found CIN Input!")
            try:
                # Type CIN slowly
                type_slowly(cin_input, CIN_NUMBER)
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
                
                error_text_locator = target_frame.locator(".errormsg").or_(
                     target_frame.locator(".alert-danger")
                ).or_(
                     target_frame.locator("text='Incorrect Captcha'")
                ).or_(
                     target_frame.locator("text='Enter valid text'")
                ).or_(
                     target_frame.locator("text='Captcha match failed'")
                ).or_(
                     target_frame.locator("text='The captcha entered is incorrect'")
                )

                try:
                    captcha_modal.wait_for(state="visible", timeout=10000)
                    print(" CAPTCHA Modal appeared.")
                    
                    # Verification loop
                    for verify_attempt in range(MAX_VERIFICATION_ATTEMPTS):
                         print(f"--- Verification Attempt {verify_attempt+1}/{MAX_VERIFICATION_ATTEMPTS} ---")
                         
                         captcha_canvas = target_frame.locator('#captchaCanvas, canvas').first
                         if captcha_canvas.count() > 0:
                             print(" Found CAPTCHA Canvas. Waiting for render...")
                             page.wait_for_timeout(1000)
                             
                             # Solve CAPTCHA using shared module
                             text = solve_captcha(target_frame, '#captchaCanvas, canvas', 'annual')
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
                                 
                                 # Check if we are at the Search Results stage (Company list)
                                 # The previous run showed we land here after the first captcha (or sometimes no captcha if session active?)
                                 # We need to find the CIN link and click it.
                                 
                                 print(" Checking for Search Results (Company Selection)...")
                                 # User provided specific locator strategy
                                 company_link = target_frame.locator(f"//a[normalize-space()='{CIN_NUMBER}']").or_(
                                     target_frame.locator(f"text={CIN_NUMBER}")
                                 ).first
                                 
                                 if company_link.count() > 0:
                                     print(f" Found Company Link for {CIN_NUMBER}. Clicking...")
                                     company_link.click()
                                     
                                     # Now we expect a SECOND Captcha or the result page
                                     print(" Waiting for Second CAPTCHA Modal or Result Page...")
                                     page.wait_for_timeout(2000)
                                     
                                     # Reuse logic to handle potential second captcha
                                     # We can wrap the captcha solving in a loop or function if we want to be cleaner, 
                                     # but for now, let's look for the modal again.
                                     
                                     # Explicitly wait for the NEW modal to attach and be visible
                                     print(" Waiting for Second CAPTCHA Modal...")
                                     # Use a specific wait to ensure we aren't seeing the old one
                                     try:
                                         target_frame.locator('#captchaModal').wait_for(state="hidden", timeout=3000) 
                                     except: 
                                         pass # It might already be visible or not present, proceed
                                         
                                     captcha_modal.wait_for(state="visible", timeout=10000)

                                     # CRITICAL FIX: Wait for the captcha image/canvas to actually update/repaint
                                     page.wait_for_timeout(3000) 

                                     # Verification Loop 2
                                     for verify_attempt_2 in range(MAX_VERIFICATION_ATTEMPTS):
                                         print(f"--- 2nd Verification Attempt {verify_attempt_2+1}/{MAX_VERIFICATION_ATTEMPTS} ---")
                                         
                                         # SCOPE THE LOCATOR: Only look for canvas INSIDE the visible modal
                                         active_modal = target_frame.locator('#captchaModal').first
                                         captcha_canvas = active_modal.locator('#captchaCanvas, canvas').first
                                         
                                         if captcha_canvas.count() > 0 and captcha_canvas.is_visible():
                                             print(" Found 2nd CAPTCHA Canvas. Solving...")
                                             
                                             text_2 = solve_captcha(target_frame, '#captchaCanvas, canvas', f'annual_2nd_{verify_attempt_2}')
                                             
                                             # FILTERING: If solver returns < 6 chars, reject immediately
                                             if not text_2 or len(text_2) != 6:
                                                  print(f" Solved text '{text_2}' is invalid length. Retrying...")
                                                  refresh_btn = active_modal.locator('#captchaRefresh').first
                                                  if refresh_btn.is_visible(): refresh_btn.click()
                                                  page.wait_for_timeout(2000)
                                                  continue

                                             print(f" Filling 2nd CAPTCHA with: {text_2}")
                                             
                                             captcha_input = active_modal.locator('#customCaptchaInput')
                                             captcha_input.clear()
                                             # Type naturally
                                             captcha_input.fill(text_2) 
                                             
                                             submit_btn = active_modal.locator('#check')
                                             submit_btn.click()
                                             print(" Clicked Submit (2nd time).")
                                             
                                             # Wait for Error or Success
                                             page.wait_for_timeout(3000) 
                                             
                                             # Check error using the locally defined locator but scoped if needed or use general
                                             if error_text_locator.count() > 0 and error_text_locator.first.is_visible():
                                                  print(" FAILURE: Incorrect 2nd Captcha.")
                                                  # Refresh logic
                                                  active_modal.locator('#captchaRefresh').click()
                                                  page.wait_for_timeout(3000) 
                                                  continue
                                             else:
                                                  # Assume success if no error immediately found, loop exits
                                                  print(" No error detected immediately. checking for results...")
                                                  break
                                             
                                         else:
                                             print(" Canvas not found in second modal.")
                                             break

                                 # Now checks for the Final Result Table (#screenone or .annual_filing_table)
                                 # The HTML dump showed id="screenone" hidden initially, so it should be visible now
                                 success_indicator = target_frame.locator("#screenone").or_(
                                     target_frame.locator(".annual_filing_table")
                                 ).or_(
                                     target_frame.locator("#annualFilingTable")
                                 )
                                 
                                 success_indicator.wait_for(state="visible", timeout=20000)
                                 
                                 if success_indicator.count() > 0 and success_indicator.first.is_visible():
                                     print(" SUCCESS: Annual Filing History Page loaded!")
                                     page.screenshot(path=f"{SCREENSHOTS_DIR}/annual_filing_history.png")
                                     
                                     # Dump HTML to verify table structure for extraction
                                     try:
                                         with open(f"{SCREENSHOTS_DIR}/debug_history_page.html", "w", encoding="utf-8") as f:
                                             f.write(target_frame.content())
                                     except: pass
                                     
                                     # PROCEED TO EXTRACTION
                                     print(" Ready to extract Filing History...")
                                     
                                     # Scrape the main table
                                     try:
                                         history_rows = []
                                         # The table class seen in debug HTML is 'tab-table' inside 'enquireFees tableComponent'
                                         # But let's use the robust headers we found
                                         table = target_frame.locator("table.tab-table").first
                                         
                                         # Wait for rows
                                         table.locator("tr").first.wait_for(state="visible", timeout=10000)
                                         
                                         rows = table.locator("tr").all()
                                         print(f" Found {len(rows)} rows in table.")
                                         
                                         # Skip header row (usually index 0)
                                         # We'll take the first data row to probe Challan
                                         for i, row in enumerate(rows):
                                             if i == 0: continue # Header
                                             
                                             cells = row.locator("td").all()
                                             if len(cells) >= 4:
                                                 srn = cells[0].inner_text()
                                                 form_name = cells[1].inner_text()
                                                 event_date = cells[2].inner_text()
                                                 
                                                 print(f" Row {i}: SRN={srn}, Form={form_name}, Date={event_date}")
                                                 
                                                 item = {
                                                     "SRN": srn,
                                                     "Form Filed": form_name,
                                                     "Filing Period": event_date,
                                                     "Date of Filing": "N/A",
                                                     "Amount Paid": "N/A",
                                                     "Late Fee": "N/A"
                                                 }
                                                 
                                                 # PROBE CHALLAN (Only for the first valid row for now to test)
                                                 # Find link in 4th column (index 3)
                                                 challan_link = cells[3].locator("a").first
                                                 if challan_link.count() > 0:
                                                     print(" Found Challan link. Clicking to probe...")
                                                     
                                                     # Check if it opens in new tab
                                                     with context.expect_page() as new_page_info:
                                                         challan_link.click()
                                                     
                                                     print(" Waiting for new page/tab...")
                                                     challan_page = new_page_info.value
                                                     challan_page.wait_for_load_state()
                                                     print(f" Challan Page Loaded: {challan_page.url}")
                                                     
                                                     challan_page.wait_for_timeout(3000)
                                                     challan_page.screenshot(path=f"{SCREENSHOTS_DIR}/challan_preview_{srn}.png")
                                                     
                                                     # Dump Challan HTML
                                                     with open(f"{SCREENSHOTS_DIR}/debug_challan_{srn}.html", "w", encoding="utf-8") as f:
                                                         f.write(challan_page.content())
                                                     
                                                     print(" Captured Challan debug info. Closing tab.")
                                                     challan_page.close()
                                                 else:
                                                     print(" No Challan link found in this row.")
                                                 
                                                 history_rows.append(item)
                                                 
                                                 # For this run, let's stop after 1 row to report back
                                                 break 
                                         
                                         print(f" Scraped {len(history_rows)} rows.")
                                         
                                         # Save partial
                                         if history_rows:
                                             df = pd.DataFrame(history_rows)
                                             df.to_excel("annual_filing_details_partial.xlsx", index=False)
                                             print(" Saved partial Excel.")
                                             
                                     except Exception as extract_e:
                                         print(f" Extraction Error: {extract_e}")
                                         
                                     return

                                 
                                 # Check for Errors (locator defined above)
                                 
                                 if error_text_locator.count() > 0 and error_text_locator.first.is_visible():
                                      print(" FAILURE: Incorrect Captcha detected.")
                                      page.screenshot(path=f"{SCREENSHOTS_DIR}/failed_annual_attempt_{verify_attempt}.png")
                                      # Refresh
                                      refresh_btn = target_frame.locator('#captchaRefresh, .captcha-refresh')
                                      if refresh_btn.count() > 0:
                                          refresh_btn.click()
                                          page.wait_for_timeout(2000)
                                      continue
                                 
                                 print(" Status unclear, taking final screenshot.")
                                 page.screenshot(path=f"{SCREENSHOTS_DIR}/annual_filing_final.png")
                                 
                                 # Dump HTML for debugging structure even if success not detected
                                 try:
                                     with open(f"{SCREENSHOTS_DIR}/debug_annual_final.html", "w", encoding="utf-8") as f:
                                         f.write(target_frame.content())
                                     print(" Saved debug HTML to screenshots/debug_annual_final.html")
                                 except Exception as e:
                                     print(f" Failed to save debug HTML: {e}")
                                     
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
                page.screenshot(path=f"{SCREENSHOTS_DIR}/debug_annual_error.png")
        else:
             print(" CIN input not found.")

if __name__ == "__main__":
    run()
