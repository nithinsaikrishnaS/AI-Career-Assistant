from playwright.sync_api import sync_playwright
import logging

logger = logging.getLogger("BrowserUtil")

def get_optimized_page(playwright_instance, user_agent=None):
    """
    Returns a Playwright page configured for high-performance scraping.
    Blocks non-essential resources (images, css, fonts) to reduce load time.
    """
    browser = playwright_instance.chromium.launch(headless=True)
    # Standard context with realistic user agent
    ua = user_agent or "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    context = browser.new_context(user_agent=ua)
    page = context.new_page()

    # --- RESOURCE BLOCKING (Requirement 7) ---
    def handle_route(route):
        if route.request.resource_type in ["image", "stylesheet", "font", "media"]:
            logger.debug(f"Blocking {route.request.resource_type}: {route.request.url[:50]}...")
            route.abort()
        else:
            route.continue_()

    page.route("**/*", handle_route)
    
    return browser, page

def safe_run_playwright(func):
    """Wrapper to handle lifecycle of playwright resources."""
    with sync_playwright() as p:
        browser, page = get_optimized_page(p)
        try:
            return func(page)
        finally:
            browser.close()
