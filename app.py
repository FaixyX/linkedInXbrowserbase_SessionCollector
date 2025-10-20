import uuid
import logging
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from playwright.async_api import Page
import httpx
import redis

from config import Settings
from dependencies import get_settings, get_session_manager, create_session_manager_from_settings
from session_manager import BaseSessionManager
from session_processor import SessionProcessor, SessionNotFoundError, ServiceUnavailableError
from linkedin_session import create_new_session, extract_session_data, send_to_bubble, check_browserbase_api
from browserbase import BrowserbaseError

# --- Central Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)



# Define the Pydantic model for the request body
class FinalizeRequest(BaseModel):
    session_id: str

# Initialize the FastAPI application
app = FastAPI(
    title="LinkedIn Session Capture API",
    description="An API to manage remote browser sessions for capturing LinkedIn login data.",
    version="5.0.0" # Final architectural version
)

@app.on_event("startup")
async def startup_event():
    """Create a singleton session manager instance on application startup."""
    logger.info("FastAPI server is starting up.")
    app.state.session_manager = create_session_manager_from_settings()

@app.get("/")
def read_root():
    """A root endpoint to confirm the API is running."""
    return {"status": "LinkedIn Session Capture API is running."}

@app.post("/start-session")
async def start_session_endpoint(
    settings: Settings = Depends(get_settings),
    session_manager: BaseSessionManager = Depends(get_session_manager)
 ):
    """
    Creates a new Browserbase session and stores its details.
    """
    try:
        session_details = await create_new_session(settings)
        internal_session_id = str(uuid.uuid4())
        session_manager.store_session(internal_session_id, session_details)
        print(f"Storing session: {internal_session_id}")
        return {
            "message": "Session created. Please use the debugger URL to log in.",
            "session_id": internal_session_id,
            "debugger_url": session_details["debugger_url"]
        }
    except (BrowserbaseError, redis.exceptions.RedisError):
        logger.error("Service error during session start.", exc_info=True)
        raise HTTPException(status_code=503, detail="A required external service is unavailable.")
    except Exception:
        logger.error("Unexpected error during session start.", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

@app.post("/finalize-session")
async def finalize_session_endpoint(
    request: FinalizeRequest,
    settings: Settings = Depends(get_settings),
    session_manager: BaseSessionManager = Depends(get_session_manager)
 ):
    """
    Uses the SessionProcessor context manager to finalize the session.
    """
    try:
        async with SessionProcessor(settings, session_manager, request.session_id) as page:
            await page.goto("https://www.linkedin.com/feed/")
            captured_data = await extract_session_data(page)
            await send_to_bubble(settings, captured_data)

            return {
                "message": "Session finalized successfully.",
                "captured_data": {
                    "li_at_present": "li_at" in captured_data,
                    "userAgent_length": len(captured_data.get("userAgent", ""))
                }
            }
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except (BrowserbaseError, httpx.RequestError, ValueError) as e:
        logger.error("Error during session processing for %s.", request.session_id, exc_info=True)
        raise HTTPException(status_code=502, detail=f"An external service or data processing error occurred: {e}")
    except Exception:
        logger.error("Unexpected error during finalization for session %s.", request.session_id, exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred during finalization.")

@app.get("/health")
async def health_check_endpoint(
    settings: Settings = Depends(get_settings),
    session_manager: BaseSessionManager = Depends(get_session_manager)
 ):
    """
    Checks the health of the application and its dependencies.
    """
    redis_healthy = session_manager.check_connection()
    browserbase_healthy = check_browserbase_api(settings)

    if redis_healthy and browserbase_healthy:
        return {"status": "ok", "dependencies": {"redis": "healthy", "browserbase": "healthy"}}
    else:
        logger.warning(
            "Health check failed. Redis healthy: %s, Browserbase healthy: %s",
            redis_healthy,
            browserbase_healthy
        )
        raise HTTPException(
            status_code=503,
            detail={
                "status": "error",
                "dependencies": {
                    "redis": "healthy" if redis_healthy else "unhealthy",
                    "browserbase": "healthy" if browserbase_healthy else "unhealthy",
                }
            }
        )
