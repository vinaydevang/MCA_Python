"""
Utility functions for MCA Automation Scripts
Common helper functions used across multiple scripts
"""

def get_robust_locator(page_or_frame, selector_list, timeout=5000):
    """
    Find an element using multiple selectors with timeout.
    
    Args:
        page_or_frame: Playwright page or frame object
        selector_list: CSS selector string (can be comma-separated for OR logic)
        timeout: Maximum wait time in milliseconds
        
    Returns:
        Element if found, None otherwise
    """
    try:
        element = page_or_frame.locator(selector_list).first
        element.wait_for(state="visible", timeout=timeout)
        return element
    except:
        return None


def type_slowly(element, text, delay=100):
    """
    Type text character by character to trigger validation events.
    
    Args:
        element: Playwright element to type into
        text: Text to type
        delay: Delay between characters in milliseconds
    """
    element.click()
    element.fill("")
    for char in text:
        element.type(char, delay=delay)


def wait_for_result_panel(frame, panel_selector, timeout=15000, stabilization_delay=3000):
    """
    Wait for a result panel to appear and stabilize.
    
    Args:
        frame: Playwright frame object
        panel_selector: CSS selector for the result panel
        timeout: Maximum wait time for panel to appear
        stabilization_delay: Additional wait for data population
        
    Returns:
        True if panel appeared, False otherwise
    """
    try:
        result_panel = frame.locator(panel_selector)
        result_panel.wait_for(state="visible", timeout=timeout)
        frame.page.wait_for_timeout(stabilization_delay)
        return True
    except:
        return False


def get_value_by_id(frame, element_id):
    """
    Get value from an input field by ID using JavaScript evaluation.
    More reliable for disabled/readonly fields.
    
    Args:
        frame: Playwright frame object
        element_id: ID of the input element
        
    Returns:
        Value string or "N/A" if not found
    """
    try:
        val = frame.locator(f"#{element_id}").first.evaluate("el => el.value")
        return val if val and val.strip() != "" else "N/A"
    except Exception as e:
        print(f"  Debug: Failed to get #{element_id}: {e}")
        return "N/A"


def get_value_by_label(frame, label_text):
    """
    Get value from an input field by finding it relative to a label.
    
    Args:
        frame: Playwright frame object
        label_text: Text content of the label
        
    Returns:
        Value string or "N/A" if not found
    """
    try:
        xpath = f"//div[contains(., '{label_text}')]/following::input[1]"
        val = frame.locator(xpath).first.evaluate("el => el.value")
        return val if val and val.strip() != "" else "N/A"
    except:
        return "N/A"
