"""
CAPTCHA Solver Module for MCA Automation
Handles 2Captcha integration with retry logic
"""

import time
import os
from PIL import Image
from twocaptcha import TwoCaptcha
from .config import CAPTCHA_CONFIG, CAPTCHA_PARAMS, MAX_CAPTCHA_RETRIES, SCREENSHOTS_DIR
from .utils import get_robust_locator



def solve_captcha(frame, canvas_selector='#new-captcha-canvas, canvas', filename_prefix='captcha'):
    """
    Solve CAPTCHA using 2Captcha service with robust retry logic.
    
    Args:
        frame: Playwright frame object containing the CAPTCHA
        canvas_selector: CSS selector for the CAPTCHA canvas element
        filename_prefix: Prefix for screenshot filenames
        
    Returns:
        Solved CAPTCHA text or empty string if failed
    """
    print(" Keying in on CAPTCHA image for 2Captcha...")
    try:
        # Locate the CAPTCHA canvas
        captcha_element = get_robust_locator(frame, canvas_selector)
        
        if not captcha_element:
            print(" Could not find CAPTCHA element.")
            frame.screenshot(path=f"{SCREENSHOTS_DIR}/debug_no_captcha_found.png")
            return ""

        # Define file paths
        raw_filename = f"{SCREENSHOTS_DIR}/{filename_prefix}_original.png"
        
        # Screenshot the CAPTCHA
        captcha_element.screenshot(path=raw_filename)
        print(f" Saved raw CAPTCHA to {raw_filename}")
        
        # Retry loop for 2Captcha API
        for attempt in range(MAX_CAPTCHA_RETRIES):
            try:
                print(f" Attempt {attempt+1}/{MAX_CAPTCHA_RETRIES}: Sending CAPTCHA to 2Captcha...")
                
                # Convert to JPG to avoid PNG alpha issues
                jpg_filename = raw_filename.replace(".png", ".jpg")
                img = Image.open(raw_filename)
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                img.save(jpg_filename, "JPEG", quality=90)

                # Initialize solver with config
                solver = TwoCaptcha(**CAPTCHA_CONFIG)

                # Attempt to solve with strict parameters
                print(f" DEBUG: calling solver with params: {CAPTCHA_PARAMS}")
                result = solver.normal(jpg_filename, **CAPTCHA_PARAMS)
                print(f" DEBUG: Raw 2Captcha Response: {result}")
                
                if 'code' in result:
                    solved_text = result['code']
                    print(f" CAPTCHA Solved: {solved_text}")
                    
                    # Save solved CAPTCHA for debugging
                    final_log_path = f"{SCREENSHOTS_DIR}/solved_{filename_prefix}_{solved_text}.png"
                    if os.path.exists(final_log_path):
                        os.remove(final_log_path)
                    os.rename(raw_filename, final_log_path)
                    print(f" Saved debug image to: {final_log_path}")
                    return solved_text
                else:
                    print(f" No code received: {result}")
            
            except Exception as loop_e:
                print(f" Attempt {attempt+1} failed: {loop_e}")
                time.sleep(5)  # Wait before retry
        
        print(" All retry attempts failed.")
        raise Exception("Failed to solve CAPTCHA after retries")

    except Exception as e:
        print(f" 2Captcha Helper Error: {e}")
        return ""
