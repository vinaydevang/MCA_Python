"""
Configuration file for MCA Automation Scripts
Store all credentials, API keys, and constants here
"""

# 2Captcha API Configuration
CAPTCHA_API_KEY = "06624a60934afbdc38c74dd259505ec9"

# 2Captcha Settings
CAPTCHA_CONFIG = {
    'server': '2captcha.com',
    'apiKey': CAPTCHA_API_KEY,
    'defaultTimeout': 120,
    'pollingInterval': 5
}

# CAPTCHA Solving Parameters
CAPTCHA_PARAMS = {
    'caseSensitive': 1,
    'case': 1,
    'minLength': 6,
    'maxLength': 6
}

# Retry Configuration
MAX_CAPTCHA_RETRIES = 5
MAX_VERIFICATION_ATTEMPTS = 3

# Screenshot Directory
SCREENSHOTS_DIR = "screenshots"

# MCA Portal URLs
MCA_URLS = {
    'enquire_din_status': 'https://www.mca.gov.in/content/mca/global/en/mca/fo-llp-services/enquire-din-status.html',
    'check_annual_filing': 'https://www.mca.gov.in/content/mca/global/en/mca/fo-llp-services/check-annual-filing-status.html',
    'verify_din': 'https://www.mca.gov.in/content/mca/global/en/mca/fo-llp-services/verify-din-pan-details.html'
}

# Browser Configuration
BROWSER_CONFIG = {
    'headless': False,
    'viewport': {'width': 1366, 'height': 768}
}

# Default Test Data
DEFAULT_DIN = "08560072"
DEFAULT_CIN = "U45400DL2007PTC171129"
