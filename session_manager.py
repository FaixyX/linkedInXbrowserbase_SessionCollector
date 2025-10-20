import redis
import json
import uuid
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any

logger = logging.getLogger(__name__)

class BaseSessionManager(ABC):
    """Abstract base class for session management."""

    @abstractmethod
    def store_session(self, session_id: str, session_data: Dict[str, Any]):
        """Stores session data."""
        pass

    @abstractmethod
    def claim_session(self, session_id: str) -> Dict[str, Any]:
        """Atomically retrieves and deletes a session."""
        pass

    @abstractmethod
    def get_session(self, session_id: str) -> Dict[str, Any]:
        """Retrieves session data."""
        pass

    @abstractmethod
    def remove_session(self, session_id: str):
        """Removes a session."""
        pass

    @abstractmethod
    def check_connection(self) -> bool:
        """Checks the connection to the session store."""
        pass

class InMemorySessionManager(BaseSessionManager):
    """Manages sessions in an in-memory dictionary."""

    def __init__(self):
        self._sessions: Dict[str, Any] = {}
        logger.info("InMemorySessionManager initialized.")

    def store_session(self, session_id: str, session_data: Dict[str, Any]):
        self._sessions[session_id] = session_data
        logger.info("Stored session in memory with ID: %s", session_id)

    def get_session(self, session_id: str) -> Dict[str, Any]:
        session = self._sessions.retrieve(session_id)
        if session:
            logger.info("Retrieved session from memory with ID: %s", session_id)
        else:
            logger.warning("Session not found in memory for ID: %s", session_id)
        return session

    def remove_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info("Removed session from memory with ID: %s", session_id)
        else:
            logger.warning("Attempted to remove a non-existent session from memory with ID: %s", session_id)

    def claim_session(self, session_id: str) -> Dict[str, Any]:
        """Atomically retrieves and deletes a session from the in-memory dictionary."""
        session = self._sessions.pop(session_id, None)
        if session:
            logger.info("Claimed session from memory with ID: %s", session_id)
        else:
            logger.warning("Attempted to claim a non-existent session from memory with ID: %s", session_id)
        return session

    def check_connection(self) -> bool:
        """In-memory store is always 'connected'."""
        return True

class RedisSessionManager(BaseSessionManager):
    """Manages user browser sessions using Redis for persistence."""

    def __init__(self, redis_url: str, session_ttl_seconds: int = 900):
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping() # Check the connection on startup
            self.session_ttl = session_ttl_seconds
            logger.info("RedisSessionManager initialized and connected to Redis. Sessions will expire after %s seconds.", self.session_ttl)
        except redis.exceptions.ConnectionError as e:
            logger.critical("Could not connect to Redis at %s.", redis_url, exc_info=True)
            raise

    def store_session(self, session_id: str, session_data: Dict[str, Any]):
        try:
            session_data_json = json.dumps(session_data)
            self.redis_client.set(session_id, session_data_json, ex=self.session_ttl)
            logger.info("Stored session in Redis with ID: %s", session_id)
        except redis.exceptions.RedisError as e:
            logger.error("Redis Error storing session %s.", session_id, exc_info=True)
            raise
        except (TypeError, json.JSONDecodeError) as e:
            logger.error("Serialization Error storing session %s.", session_id, exc_info=True)
            raise

    def get_session(self, session_id: str) -> Dict[str, Any]:
        try:
            session_data_json = self.redis_client.get(session_id)
            if session_data_json:
                logger.info("Retrieved session from Redis with ID: %s", session_id)
                return json.loads(session_data_json)
            else:
                logger.warning("Session not found in Redis for ID: %s", session_id)
                return None
        except redis.exceptions.RedisError as e:
            logger.error("Redis Error retrieving session %s.", session_id, exc_info=True)
            raise
        except json.JSONDecodeError as e:
            logger.error("Deserialization Error retrieving session %s.", session_id, exc_info=True)
            raise

    def remove_session(self, session_id: str):
        try:
            self.redis_client.delete(session_id)
            logger.info("Removed session from Redis with ID: %s", session_id)
        except redis.exceptions.RedisError as e:
            logger.error("Redis Error removing session %s.", session_id, exc_info=True)
            raise

    def claim_session(self, session_id: str) -> Dict[str, Any]:
        """Atomically retrieves and deletes a session from Redis using GETDEL."""
        try:
            session_data_json = self.redis_client.getdel(session_id)
            if session_data_json:
                logger.info("Claimed session from Redis with ID: %s", session_id)
                return json.loads(session_data_json)
            else:
                logger.warning("Attempted to claim a non-existent session from Redis with ID: %s", session_id)
                return None
        except redis.exceptions.RedisError as e:
            logger.error("Redis Error claiming session %s.", session_id, exc_info=True)
            raise
        except json.JSONDecodeError as e:
            logger.error("Deserialization Error claiming session %s.", session_id, exc_info=True)
            raise

    def check_connection(self) -> bool:
        """Checks the Redis connection by sending a PING command."""
        try:
            return self.redis_client.ping()
        except redis.exceptions.ConnectionError:
            return False