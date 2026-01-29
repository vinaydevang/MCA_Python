import sys
import time
import os
import requests
import pdfplumber
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
                     target_frame.locator("*:has-text('The captcha entered is incorrect')")
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
                                             
                                             # Define success indicator early
                                             success_indicator = target_frame.locator("#screenone").or_(
                                                 target_frame.locator(".annual_filing_table")
                                             ).or_(
                                                 target_frame.locator("#annualFilingTable")
                                             )

                                             # Polling Loop for Result (Error or Success) - Up to 10 seconds
                                             print(" Checking validation result (Polling)...")
                                             validation_start_time = time.time()
                                             validation_status = "unknown"
                                             
                                             while time.time() - validation_start_time < 10:
                                                 # Debug visibility
                                                 err_count = error_text_locator.count()
                                                 succ_count = success_indicator.count()
                                                 
                                                 # Check for Error first
                                                 if err_count > 0:
                                                     is_vis = error_text_locator.first.is_visible()
                                                     if is_vis:
                                                         print(f" DEBUG: Error found! Text: {error_text_locator.first.inner_text()}")
                                                         print(" FAILURE: Incorrect 2nd Captcha.")
                                                         validation_status = "error"
                                                         # Refresh logic
                                                         active_modal.locator('#captchaRefresh').click()
                                                         page.wait_for_timeout(3000) 
                                                         break # Break polling, continue outer retry loop
                                                 
                                                 # Check for Success
                                                 if succ_count > 0:
                                                     is_vis = success_indicator.first.is_visible()
                                                     # print(f" DEBUG: Success indicator count={succ_count}, visible={is_vis}") # Too noisy?
                                                     if is_vis:
                                                         print(" SUCCESS: 2nd Captcha passed!")
                                                         validation_status = "success"
                                                         break # Break polling, break outer retry loop
                                                 
                                                 page.wait_for_timeout(500)
                                             
                                             if validation_status == "error":
                                                 continue # Retry next attempt
                                             elif validation_status == "success":
                                                 break # Exit retry loop
                                             else:
                                                 print(" Timeout waiting for validation result. Assuming check failed or stuck.")
                                                 # If we timed out without error or success, we might want to retry or just continue to final check
                                                 # Let's try to scrape anyway or break if we think it failed.
                                                 # For robustness, let's treat as 'unknown' and break to check final page.
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
                                 
                                 success_indicator.wait_for(state="visible", timeout=60000)
                                 
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
                                                
                                                 # DEBUG: Print exact HTML of the Challan cell
                                                 try:
                                                     print(f" DEBUG: Cell[3] HTML: {cells[3].inner_html()}")
                                                 except:
                                                     print(" DEBUG: Could not print cell HTML")

                                                 # Handle Direct Download
                                                 challan_saved = False
                                                 pdf_filename = f"{srn}.pdf"
                                                 pdf_path = os.path.join("challan_pdfs", pdf_filename)
                                                 
                                                 download_btn = cells[3].locator(".downloadDoc, img").first
                                                 if download_btn.count() > 0:
                                                     print(f" Found Download Button for {srn}. Clicking...")
                                                     try:
                                                         # Setup download handler
                                                         with page.expect_download(timeout=30000) as download_info:
                                                             download_btn.click()
                                                         
                                                         download = download_info.value
                                                         # Save to specific path
                                                         if not os.path.exists("challan_pdfs"): os.makedirs("challan_pdfs")
                                                         download.save_as(pdf_path)
                                                         print(f" Downloaded Challan to: {pdf_path}")
                                                         challan_saved = True
                                                     except Exception as e:
                                                         print(f" Download failed for {srn}: {e}")
                                                         challan_saved = False
                                                 else:
                                                     print(" No download button found.")
                                                  
                                                 item = {
                                                     "SRN": srn,
                                                     "Form Name": form_name,
                                                     "Event Date": event_date,
                                                     "PDF Path": pdf_path if challan_saved else "N/A"
                                                 }
                                                 
                                                 history_rows.append(item)
                                         
                                         
                                         print(f" Scraped {len(history_rows)} rows.")
                                         
                                         # Save intermediate data WITH Challan URLs for standalone script
                                         if history_rows:
                                             df_temp = pd.DataFrame(history_rows)
                                             df_temp.to_excel("annual_filing_with_urls.xlsx", index=False)
                                             print(f" Saved intermediate data with Challan URLs to annual_filing_with_urls.xlsx")
                                         
                                         # Phase 2: Extract payment details from LOCAL PDFs
                                         print("\n Phase 2: Extracting payment details from downloaded PDFs...")
                                         
                                         for i, row in enumerate(history_rows):
                                             pdf_path = row.get('PDF Path', 'N/A')
                                             srn = row['SRN']
                                             
                                             # Initialize with N/A defaults
                                             row['Date of Filing'] = "N/A"
                                             row['Amount Paid'] = "N/A"
                                             row['Late Fee'] = "N/A"
                                             
                                             if pdf_path != "N/A" and os.path.exists(pdf_path):
                                                 print(f" [{i+1}/{len(history_rows)}] Processing PDF for SRN {srn}...")
                                                 
                                                 try:
                                                     # Extract text from PDF
                                                     with pdfplumber.open(pdf_path) as pdf:
                                                         text = ""
                                                         for page_pdf in pdf.pages:
                                                             text += page_pdf.extract_text() or ""
                                                     
                                                     # Parse text to find payment details
                                                     lines = text.split('\n')
                                                     
                                                     for line in lines:
                                                         # Find Service Request Date
                                                         if 'Service Request Date' in line and ':' in line:
                                                             parts = line.split(':', 1)
                                                             if len(parts) == 2:
                                                                 date_of_filing = parts[1].strip()
                                                                 row['Date of Filing'] = date_of_filing
                                                         
                                                         # Find Total amount
                                                         if 'Total' in line:
                                                             # Extract numeric value from line
                                                             parts = line.split()
                                                             for part in reversed(parts):
                                                                 if part.replace('.', '', 1).replace(',', '').isdigit():
                                                                     row['Amount Paid'] = part
                                                                     break
                                                         
                                                         # Find Additional (Late Fee)
                                                         if 'Additional' in line:
                                                             parts = line.split()
                                                             for part in reversed(parts):
                                                                 if part.replace('.', '', 1).replace(',', '').isdigit():
                                                                     row['Late Fee'] = part
                                                                     break
                                                     
                                                     # If no Additional fee found, set to 0.00
                                                     if row['Late Fee'] == "N/A":
                                                         row['Late Fee'] = "0.00"
                                                     
                                                     print(f"   Date: {row['Date of Filing']}, Amount: {row['Amount Paid']}, Late Fee: {row['Late Fee']}")
                                                     
                                                 except Exception as e:
                                                     print(f"   Error parsing PDF {pdf_path}: {e}")
                                             else:
                                                 print(f"   Skipping {srn} (No PDF found)")
                                         
                                         # Save all rows with payment details
                                         if history_rows:
                                             df = pd.DataFrame(history_rows)
                                             # Reorder columns (exclude Challan URL) - done AFTER Phase 2
                                             column_order = ['SRN', 'Form Name', 'Event Date', 'Date of Filing', 'Amount Paid', 'Late Fee']
                                             df = df[column_order]
                                             df.to_excel("annual_filing_details.xlsx", index=False)
                                             print(f"\n Saved {len(history_rows)} records with payment details to annual_filing_details.xlsx")
                                             
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
