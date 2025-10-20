import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from linkedin_session import _sanitize_error_response, extract_session_data, check_browserbase_api
from config import Settings
import json

# --- Tests for _sanitize_error_response ---

def test_sanitize_finds_and_redacts_li_at():
    """Tests that the 'li_at' key is redacted from a simple JSON object."""
    sensitive_data = {"li_at": "sensitive_cookie_value", "other_key": "other_value"}
    sanitized = _sanitize_error_response(json.dumps(sensitive_data))
    result = json.loads(sanitized)
    assert result["li_at"] == "[REDACTED]"
    assert result["other_key"] == "other_value"

def test_sanitize_finds_and_redacts_nested_li_at():
    """Tests that 'li_at' is redacted from a nested JSON object."""
    sensitive_data = {
        "error": "processing_failed",
        "offending_payload": {
            "li_at": "sensitive_cookie_value",
            "userAgent": "test-agent"
        }
    }
    sanitized = _sanitize_error_response(json.dumps(sensitive_data))
    result = json.loads(sanitized)
    assert result["offending_payload"]["li_at"] == "[REDACTED]"
    assert result["offending_payload"]["userAgent"] == "test-agent"

def test_sanitize_handles_no_li_at():
    """Tests that the function doesn't change data without the sensitive key."""
    safe_data = {"other_key": "other_value"}
    sanitized = _sanitize_error_response(json.dumps(safe_data))
    assert sanitized == json.dumps(safe_data)

def test_sanitize_handles_non_json_string():
    """Tests that a non-JSON string is returned as-is."""
    non_json = "This is just a plain text error message."
    sanitized = _sanitize_error_response(non_json)
    assert sanitized == non_json

# --- Mock Settings Fixture ---
@pytest.fixture
def mock_settings():
    """Provides a mock Settings object."""
    return Settings(
        BROWSERBASE_API_KEY="test", BROWSERBASE_PROJECT_ID="test",
        BUBBLE_API_KEY="test", BUBBLE_WORKFLOW_URL="https://test.com",
        REDIS_URL="redis://test", SESSION_BACKEND="memory"
    )

# --- Mock Playwright Page Fixture ---
@pytest.fixture
def mock_page(mocker):
    """Mocks the Playwright Page object."""
    mock = mocker.AsyncMock()

    # Mock the evaluate method
    mock.evaluate.return_value = "test-user-agent"

    # Mock the context and its cookies method
    mock_context = mocker.AsyncMock()
    mock_context.cookies.return_value = [
        {"name": "other_cookie", "value": "other_value"},
        {"name": "li_at", "value": "test-li-at-cookie"}
    ]
    mock.context = mock_context

    return mock

# --- Tests for extract_session_data ---

@pytest.mark.asyncio
async def test_extract_session_data_success(mock_page):
    """Tests successful extraction of session data."""
    data = await extract_session_data(mock_page)

    assert data["li_at"] == "test-li-at-cookie"
    assert data["userAgent"] == "test-user-agent"
    mock_page.context.cookies.assert_awaited_once()
    mock_page.evaluate.assert_awaited_once_with("() => navigator.userAgent")

@pytest.mark.asyncio
async def test_extract_session_data_no_cookie(mock_page):
    """Tests that a ValueError is raised if the 'li_at' cookie is missing."""
    # Override the mock to return no 'li_at' cookie
    mock_page.context.cookies.return_value = [{"name": "other", "value": "data"}]

    with pytest.raises(ValueError, match="Could not find 'li_at' cookie"):
        await extract_session_data(mock_page)

# --- Tests for check_browserbase_api ---

@pytest.mark.asyncio
async def test_check_browserbase_api_healthy(mocker, mock_settings):
    """Tests the Browserbase health check when the API is responsive."""
    mock_bb_client = mocker.patch("browserbase.Browserbase").return_value
    mock_bb_client.sessions.list.return_value = [] # Mock a successful API call

    is_healthy = await check_browserbase_api(mock_settings)

    assert is_healthy is True
    mock_bb_client.sessions.list.assert_awaited_once_with(limit=1)

@pytest.mark.asyncio
async def test_check_browserbase_api_unhealthy(mocker, mock_settings):
    """Tests the Browserbase health check when the API raises an error."""
    from browserbase import BrowserbaseError

    mock_bb_client = mocker.patch("browserbase.Browserbase").return_value
    mock_bb_client.sessions.list.side_effect = BrowserbaseError("API is down")

    is_healthy = await check_browserbase_api(mock_settings)

    assert is_healthy is False