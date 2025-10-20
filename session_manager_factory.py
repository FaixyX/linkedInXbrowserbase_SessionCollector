from settings import Settings
from session_manager import InMemorySessionManager, RedisSessionManager

def build_session_manager(settings: Settings):
    if settings.SESSION_BACKEND == "redis":
        return RedisSessionManager(redis_url=settings.REDIS_URL)
    else:
        return InMemorySessionManager()