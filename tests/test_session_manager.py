import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from session_manager import InMemorySessionManager, RedisSessionManager
import json

# --- Tests for InMemorySessionManager ---

@pytest.fixture
def in_memory_manager():
    """Provides a fresh InMemorySessionManager for each test."""
    return InMemorySessionManager()

def test_store_and_get_session(in_memory_manager: InMemorySessionManager):
    session_id = "test-session-123"
    session_data = {"user": "test", "status": "active"}
    in_memory_manager.store_session(session_id, session_data)
    retrieved_session = in_memory_manager.get_session(session_id)
    assert retrieved_session is not None
    assert retrieved_session == session_data

def test_get_non_existent_session(in_memory_manager: InMemorySessionManager):
    retrieved_session = in_memory_manager.get_session("non-existent-id")
    assert retrieved_session is None

def test_remove_session(in_memory_manager: InMemorySessionManager):
    session_id = "test-session-to-remove"
    session_data = {"data": "some_data"}
    in_memory_manager.store_session(session_id, session_data)
    assert in_memory_manager.get_session(session_id) is not None
    in_memory_manager.remove_session(session_id)
    assert in_memory_manager.get_session(session_id) is None

def test_claim_session(in_memory_manager: InMemorySessionManager):
    """Tests that claiming a session retrieves and removes it."""
    session_id = "test-session-to-claim"
    session_data = {"data": "claim_data"}
    in_memory_manager.store_session(session_id, session_data)

    claimed_session = in_memory_manager.claim_session(session_id)
    assert claimed_session == session_data
    assert in_memory_manager.get_session(session_id) is None

def test_claim_non_existent_session(in_memory_manager: InMemorySessionManager):
    """Tests that claiming a non-existent session returns None."""
    claimed_session = in_memory_manager.claim_session("non-existent")
    assert claimed_session is None

# --- Tests for RedisSessionManager ---

@pytest.fixture
def mock_redis_client(mocker):
    """Mocks the redis.from_url client."""
    return mocker.patch("redis.from_url").return_value

def test_redis_manager_init_success(mock_redis_client):
    manager = RedisSessionManager(redis_url="redis://mock")
    mock_redis_client.ping.assert_called_once()
    assert manager.redis_client == mock_redis_client

def test_redis_manager_store_session(mock_redis_client):
    manager = RedisSessionManager(redis_url="redis://mock")
    session_id = "redis-session-1"
    session_data = {"key": "value"}
    manager.store_session(session_id, session_data)
    mock_redis_client.set.assert_called_once_with(
        session_id, json.dumps(session_data), ex=manager.session_ttl
    )

def test_redis_manager_get_existing_session(mock_redis_client):
    manager = RedisSessionManager(redis_url="redis://mock")
    session_id = "redis-session-2"
    session_data = {"user": "redis_user"}
    mock_redis_client.get.return_value = json.dumps(session_data)
    retrieved = manager.get_session(session_id)
    mock_redis_client.get.assert_called_once_with(session_id)
    assert retrieved == session_data

def test_redis_manager_get_non_existent_session(mock_redis_client):
    manager = RedisSessionManager(redis_url="redis://mock")
    mock_redis_client.get.return_value = None
    retrieved = manager.get_session("non-existent")
    assert retrieved is None

def test_redis_manager_remove_session(mock_redis_client):
    manager = RedisSessionManager(redis_url="redis://mock")
    session_id = "redis-session-to-remove"
    manager.remove_session(session_id)
    mock_redis_client.delete.assert_called_once_with(session_id)

def test_redis_manager_check_connection_healthy(mock_redis_client):
    manager = RedisSessionManager(redis_url="redis://mock")
    mock_redis_client.ping.return_value = True
    assert manager.check_connection() is True

def test_redis_manager_check_connection_unhealthy(mock_redis_client):
    import redis
    manager = RedisSessionManager(redis_url="redis://mock")
    mock_redis_client.ping.side_effect = redis.exceptions.ConnectionError
    assert manager.check_connection() is False

def test_redis_manager_claim_session(mock_redis_client):
    """Tests atomically claiming a session from Redis."""
    manager = RedisSessionManager(redis_url="redis://mock")
    session_id = "redis-session-to-claim"
    session_data = {"key": "claim_value"}

    # Configure the mock to return the session data on GETDEL
    mock_redis_client.getdel.return_value = json.dumps(session_data)

    claimed = manager.claim_session(session_id)

    mock_redis_client.getdel.assert_called_once_with(session_id)
    assert claimed == session_data