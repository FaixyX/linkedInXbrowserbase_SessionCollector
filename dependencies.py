from functools import lru_cache
from fastapi import Request
from config import Settings
from session_manager import BaseSessionManager, RedisSessionManager, InMemorySessionManager

@lru_cache()
def get_settings() -> Settings:
    """
    Dependency provider for the application settings.
    Uses lru_cache to ensure the Settings object is created only once.
    """
    return Settings()

def create_session_manager_from_settings() -> BaseSessionManager:
    """
    Factory function to create the session manager instance based on settings.
    This is called once at application startup.
    """
    settings = get_settings() # Gets the cached settings object
    if settings.SESSION_BACKEND == "redis":
        return RedisSessionManager(redis_url=settings.REDIS_URL)
    elif settings.SESSION_BACKEND == "memory":
        return InMemorySessionManager()
    else:
        raise ValueError(f"Invalid SESSION_BACKEND: {settings.SESSION_BACKEND}")

def get_session_manager(request: Request) -> BaseSessionManager:
    """
    Dependency to retrieve the singleton session manager from app state.
    """
    
    return request.app.state.session_manager

# The SessionProcessor is now a context manager and is not injected as a dependency.