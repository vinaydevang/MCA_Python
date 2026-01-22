import sys
import pytesseract
from PIL import Image
import io
from playwright.sync_api import sync_playwright

# 1. SETUP TESSERACT
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def get_robust_locator(page_or_frame, selector_list):
    """
    Tries to find a locator from a comma-separated string of selectors.
    Waits up to 5 seconds for one of them to appear.
    """
    try:
        # Playwright allows comma-separated CSS for "OR" logic
        element = page_or_frame.locator(selector_list).first
        element.wait_for(state="visible", timeout=5000)
        return element
    except:
        return None

def solve_captcha(frame):
    print("📸 Attempting to solve CAPTCHA...")
    try:
        # Try multiple common ID patterns for the MCA captcha image
        captcha_img = get_robust_locator(frame, 'img[id*="captcha"], img[src*="captcha"], #captcha')
        
        if captcha_img:
            # Take screenshot of just the element
            img_bytes = captcha_img.screenshot()
            img = Image.open(io.BytesIO(img_bytes))
            
            # Pre-processing for better OCR accuracy
            img = img.convert('L')  # Grayscale
            # You could add thresholding here if needed
            
            captcha_text = pytesseract.image_to_string(img, config='--psm 8').strip()
            # Clean non-alphanumeric chars if MCA is strictly alphanumeric
            captcha_text = "".join(filter(str.isalnum, captcha_text))
            
            print(f"🤖 OCR detected: {captcha_text}")
            return captcha_text
    except Exception as e:
        print(f"❌ OCR Error: {e}")
    return ""

def run():
    print(f"🐍 Python Executable: {sys.executable}")
    with sync_playwright() as p:
        print("🦊 Launching Browser...")
        # Use specific args to mimic a real user (Optional but recommended for MCA)
        browser = p.firefox.launch(headless=False)
        context = browser.new_context(viewport={'width': 1366, 'height': 768})
        page = context.new_page()

        print("🌐 Navigating to MCA Login...")
        # Direct link sometimes fails to show form without interaction
        page.goto('https://www.mca.gov.in/content/mca/global/en/foportal/fologin.html', wait_until='networkidle')
        page.wait_for_timeout(3000)

        # CHECK IF WE NEED TO CLICK SIGN IN
        signin_btn = page.locator('#signin, a[href*="fologin.html"], button:has-text("Sign In"), span:has-text("Sign In")').first
        if signin_btn.count() > 0 and signin_btn.is_visible():
            print("👇 Clicking 'Sign In' button to trigger modal/form...")
            signin_btn.click()
            page.wait_for_timeout(3000) 

        # MCA Login often loads inside a frame or is a standalone page depending on the link.
        # We try to find the inputs on the main page first.
        target_frame = page
        
        print("📝 Looking for User ID field...")
        # STRATEGY: Try all possible User ID locators at once
        user_input = get_robust_locator(target_frame, '#userName, input[name="userName"], input[placeholder*="User"], input[aria-label*="User ID"], input[type="text"]:visible')
        
        if not user_input:
            print("⚠️ Inputs not found on main page. Checking frames...")
            # Fallback: Check frames if main page fails
            for frame in page.frames:
                print(f"Checking frame: {frame.name} - {frame.url}")
                user_input = get_robust_locator(frame, '#userName, input[name="userName"], input[placeholder*="User"], input[aria-label*="User ID"], input[type="text"]:visible')
                if user_input:
                    target_frame = frame
                    print(f"✅ Found User Input in frame: {frame.name}")
                    break
        
        if user_input:
            print("✅ Found User Input!")
            try:
                user_input.fill('kevinraj20@gmail.com')
            except Exception as e:
                print(f"❌ Error filling user input: {e}")
            
            print("📝 Looking for Password field...")
            pass_input = get_robust_locator(target_frame, '#password, input[name="password"], input[type="password"]')
            if pass_input:
                try:
                    pass_input.fill('TbT@629002')
                    print("✅ Password filled.")
                except Exception as e:
                    print(f"❌ Error filling password: {e}")
            
            # SOLVE CAPTCHA
            text = solve_captcha(target_frame)
            if text:
                print(f"⌨️ Entering Captcha: {text}")
                # Locator for the "Enter the Value" box
                captcha_input = get_robust_locator(target_frame, 'input[id*="captcha" i], input[placeholder*="Enter"], input[name*="captcha" i]')
                if captcha_input:
                    try:
                        captcha_input.fill(text)
                        print("✅ Captcha filled.")
                    except Exception as e:
                         print(f"❌ Error filling captcha: {e}")
                    
                    # Click Login (Uncomment to enable)
                    login_btn = get_robust_locator(target_frame, 'input[value="Sign In"], button:has-text("Sign In")')
                    if login_btn:
                        print("🚀 Clicking 'Sign In' button...")
                        login_btn.click()
                        
                        # Wait for navigation or error
                        page.wait_for_timeout(5000)
                        
                        # Check for success (URL change or specific element)
                        if "dashboard" in page.url or "my-workspace" in page.url:
                             print("✅ Login Successful! Redirected to Dashboard.")
                        elif page.locator('div:has-text("Wrong Captcha"), div:has-text("Invalid")').count() > 0:
                             print("❌ Login Failed: Wrong Captcha or Invalid Credentials.")
                        else:
                             print(f"ℹ️ Login Clicked. Current URL: {page.url}")
                             # Take screenshot to see what happened
                             page.screenshot(path="login_attempt_result.png")
            
            # Take success screenshot
            # Take success screenshot
            print("📸 Execution finished.")
            page.screenshot(path="final_result.png")
            print("📸 Saved 'final_result.png'")
            
            page.wait_for_timeout(2000) # Wait to see result
            
        else:
            print("❌ Could not find login fields even with robust locators.")
            page.screenshot(path="debug_not_found_robust.png")
            with open("debug_page_robust.html", "w", encoding="utf-8") as f:
                 f.write(page.content())

        browser.close()


if __name__ == "__main__":
    run()
