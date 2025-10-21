import httpx
import logging
import json
from browserbase import Browserbase
from playwright.async_api import Page, async_playwright
from typing import Dict, Any
from config import Settings
from browserbase import BrowserbaseError

logger = logging.getLogger(__name__)

def _sanitize_error_response(response_text: str) -> str:
    """
    Parses a string as JSON and removes the 'li_at' key if it exists.
    Returns the sanitized data as a string.
    """
    try:
        data = json.loads(response_text)
        if isinstance(data, dict) and "li_at" in data:
            data["li_at"] = "[REDACTED]"

        # For nested error objects
        if isinstance(data, dict) and "offending_payload" in data and isinstance(data["offending_payload"], dict) and "li_at" in data["offending_payload"]:
             data["offending_payload"]["li_at"] = "[REDACTED]"

        return json.dumps(data)
    except json.JSONDecodeError:
        # If the response isn't valid JSON, return it as-is
        return response_text

# --- Browserbase Interaction ---

async def create_new_session(settings: Settings) -> Dict[str, Any]:
    """
    Creates a new Browserbase session and returns its connection details.
    """
    try:
        browserbase = Browserbase(api_key=settings.BROWSERBASE_API_KEY)

        browser_settings = {
            "viewport": {"width": 1920, "height": 1080},
            "advanced_stealth": False,
            "keep_alive": True,
            "record_session": True,
            "log_session": True,
            "block_ads": True,
            "solve_captchas": True,
        }

        session = browserbase.sessions.create(
            project_id=settings.BROWSERBASE_PROJECT_ID,
            browser_settings=browser_settings,
            proxies=True
        )

        logger.info("New Browserbase session created with ID: %s", session.id)

        debug_links = browserbase.sessions.debug(session.id)

        return {
            "browserbase_session_id": session.id,
            "debugger_url": debug_links.debuggerFullscreenUrl
        }
    except BrowserbaseError as e:
        logger.error("Browserbase API Error during session creation.", exc_info=True)
        raise

async def get_session_connect_url(settings: Settings, browserbase_session_id: str) -> str:
    """
    Fetches the connection URL for an existing Browserbase session.
    """
    try:
        browserbase = Browserbase(api_key=settings.BROWSERBASE_API_KEY)
        session = browserbase.sessions.retrieve(browserbase_session_id)
        return session.connect_url
    except BrowserbaseError as e:
        logger.error("Browserbase API Error getting session connect URL for %s.", browserbase_session_id, exc_info=True)
        raise

async def extract_session_data(page: Page) -> Dict[str, Any]:
    """
    Extracts the 'li_at' cookie and user agent from the given page.
    """
    cookies = await page.context.cookies()
    li_at_cookie = next((c for c in cookies if c['name'] == 'li_at'), None)

    if not li_at_cookie:
        logger.warning("Cookies retrieved: %s", [c["name"] for c in cookies])
        raise ValueError("Could not find 'li_at' cookie. Login may have failed or timed out.")

    user_agent = await page.evaluate("() => navigator.userAgent")

    logger.info("Successfully extracted session data from page.")

    return {
        "li_at": li_at_cookie['value'],
        "userAgent": user_agent
    }

# --- Bubble.io Integration ---

async def check_browserbase_api(settings: Settings) -> bool:
    """
    Checks if the Browserbase API is available and the credentials are valid.
    """
    try:
        browserbase = Browserbase(api_key=settings.BROWSERBASE_API_KEY)
        await browserbase.sessions.list()
        return True
    except BrowserbaseError:
        return False

async def delete_browserbase_session(settings: Settings, browserbase_session_id: str):
    """
    Keep the Browserbase session alive - it will terminate itself when user logs in.
    This function is kept for compatibility but does nothing.
    """
    logger.info("Keeping Browserbase session alive: %s (will terminate automatically on user login)", browserbase_session_id)

from tenacity import retry, stop_after_attempt, wait_exponential

def _log_after_retry(retry_state):
    """A custom callback to log after retries are exhausted."""
    logger.error(
        "All %d attempts to send data to Bubble failed. Last exception: %s",
        retry_state.attempt_number,
        retry_state.outcome.exception()
    )

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry_error_callback=_log_after_retry
)
async def send_to_bubble(settings: Settings, session_data: dict):
    """
    Sends the captured session data to the Bubble.io workflow asynchronously,
    using tenacity for robust retries.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.BUBBLE_API_KEY}"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(settings.BUBBLE_WORKFLOW_URL, headers=headers, json=session_data)
            response.raise_for_status()
            logger.info("Session data successfully sent to Bubble.")
    except httpx.HTTPStatusError as e:
        if 400 <= e.response.status_code < 500:
            # For client errors, log and do not retry
            sanitized_response = _sanitize_error_response(e.response.text)
            logger.error(
                "Client error sending data to Bubble. Status: %s, Response: %s. No retry.",
                e.response.status_code, sanitized_response
            )
            # Re-raise to prevent tenacity from retrying
            raise
        # For server errors (5xx), let tenacity handle the retry
        logger.warning("Server error sending data to Bubble. Status: %s. Retrying...", e.response.status_code)
        raise
    except httpx.RequestError as e:
        logger.warning("Network error sending data to Bubble. Retrying...")
        raise