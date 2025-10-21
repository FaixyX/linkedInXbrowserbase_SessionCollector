import logging
from config import Settings
from session_manager import BaseSessionManager
from linkedin_session import get_session_connect_url
from playwright.async_api import async_playwright, Browser, Page
import redis

logger = logging.getLogger(__name__)

class SessionProcessor:
    """
    Acts as an async context manager to handle the lifecycle of a browser
    connection for a given session, providing a usable Page object.
    """

    def __init__(self, settings: Settings, session_manager: BaseSessionManager, session_id: str):
        self.settings = settings
        self.session_manager = session_manager
        self.session_id = session_id
        self.session_details = None
        self.browser: Browser = None

    async def __aenter__(self) -> Page:
        """
        Enters the context: claims the session, gets the connection URL,
        connects to the remote browser, and returns the Page object.
        """
        try:
            self.session_details = self.session_manager.claim_session(self.session_id)
            if not self.session_details:
                raise SessionNotFoundError(f"Session not found or already processed: {self.session_id}")

            connect_url = await get_session_connect_url(self.settings, self.session_details["browserbase_session_id"])

            self.playwright = async_playwright()
            pw_instance = await self.playwright.__aenter__()
            self.browser = await pw_instance.chromium.connect_over_cdp(connect_url)

            return self.browser.contexts[0].pages[0]
        except redis.exceptions.RedisError as e:
            raise ServiceUnavailableError("Session store is unavailable.") from e
        except Exception as e:
            logger.error("Failed to enter session context for %s", self.session_id, exc_info=True)
            # Ensure cleanup is attempted even if __aenter__ fails midway
            await self.__aexit__(type(e), e, e.__traceback__)
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Exits the context, ensuring all resources are cleaned up robustly.
        """
        if self.browser:
            try:
                # await self.browser.close()
                logger.info("I am here")
                # logger.info("Playwright browser connection closed for session: %s", self.session_details['browserbase_session_id'])
            except Exception:
                logger.error("Failed to close Playwright connection for session %s.", self.session_details.get('browserbase_session_id', 'N/A'), exc_info=True)

        if hasattr(self, 'playwright'):
            await self.playwright.__aexit__(exc_type, exc_val, exc_tb)

        if self.session_details:
            # Keep Browserbase session alive - it will terminate automatically when user logs in
            logger.info("Keeping Browserbase session alive: %s (will terminate automatically on user login)", self.session_details.get('browserbase_session_id', 'N/A'))

# --- Custom Exceptions for the Processor ---
class SessionProcessorError(Exception):
    """Base exception for the session processor."""
    pass

class SessionNotFoundError(SessionProcessorError):
    """Raised when a session cannot be found or has already been claimed."""
    pass

class ServiceUnavailableError(SessionProcessorError):
    """Raised when a dependent service (like Redis) is unavailable."""
    pass