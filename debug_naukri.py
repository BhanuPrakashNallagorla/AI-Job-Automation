# Ultra-simple version for testing
from playwright.sync_api import sync_playwright
import time
import os

def simple_scrape():
    print("Starting simple scrape...")
    try:
        with sync_playwright() as p:
            print("Launching browser...")
            browser = p.chromium.launch(headless=True)  # Changed to headless=True for server environment
            page = browser.new_page()
            
            print("Opening Naukri...")
            page.goto("https://www.naukri.com/python-developer-jobs-in-bangalore", timeout=60000)
            
            print("Waiting 5 seconds...")
            time.sleep(5)
            
            print("Taking screenshot...")
            page.screenshot(path='naukri_page.png')
            
            print("Getting page content...")
            content = page.content()
            with open('page_source.html', 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("Trying to find ANY div with 'job' in class name...")
            divs = page.query_selector_all('div[class*="job"]')
            print(f"Found {len(divs)} divs with 'job' in class")
            
            print("\nDone. Check naukri_page.png and page_source.html")
            browser.close()
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    simple_scrape()
