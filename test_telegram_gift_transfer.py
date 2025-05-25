import pytest
import requests
from unittest.mock import patch, MagicMock
import json
import os
import sys

# Add current directory to path to import modules
sys.path.append(os.path.dirname(os.path.realpath(__file__)))

from config import AppConfig
# Import after mocking config to avoid real API calls
from telegram_gift_transfer import (
    make_api_request, validate_chat_id, get_business_star_balance,
    transfer_stars_to_bot, validate_gift_for_transfer, find_gift_by_id
)

@pytest.fixture
def test_config():
    """Fixture for test configuration"""
    return AppConfig(
        BOT_TOKEN="test_token",
        BUSINESS_CONNECTION_ID="test_business_id",
        TARGET_CHAT_ID=123456789,
        STAR_COUNT=25,
        MAX_RETRIES=1,  # Use 1 for faster tests
        RETRY_DELAY=0.1,  # Short delay for tests
        TRANSFER_WAIT_TIME=0.1,
        BYPASS_BUSINESS_CHECK=True,
        ENABLE_REDUNDANT_TRANSFER=False,
        LOG_DIR="test_logs"
    )

@pytest.fixture
def mock_logger():
    """Fixture for mocked logger"""
    mock = MagicMock()
    mock.handlers = [MagicMock(), MagicMock()]
    mock.handlers[1].baseFilename = "test_log_file.log"
    return mock

@pytest.fixture
def setup_globals(test_config, mock_logger):
    """Set up global variables used by the module"""
    import telegram_gift_transfer
    
    # Save original values
    original_values = {}
    for key in test_config.dict().keys():
        if hasattr(telegram_gift_transfer, key):
            original_values[key] = getattr(telegram_gift_transfer, key)
    
    # Set test values
    for key, value in test_config.dict().items():
        setattr(telegram_gift_transfer, key, value)
    
    # Set API config
    telegram_gift_transfer.API_CONFIG = {
        "BASE_URL": "https://api.telegram.org/bot",
        "ENDPOINTS": {
            "get_me": "getMe",
            "get_chat": "getChat",
            "get_business_star_balance": "getBusinessAccountStarBalance",
            "transfer_business_stars": "transferBusinessAccountStars",
            "get_business_gifts": "getBusinessAccountGifts",
            "transfer_gift": "transferGift"
        }
    }
    
    # Set logger
    original_logger = telegram_gift_transfer.logger
    telegram_gift_transfer.logger = mock_logger
    
    yield
    
    # Restore original values
    for key, value in original_values.items():
        setattr(telegram_gift_transfer, key, value)
    
    # Restore logger
    telegram_gift_transfer.logger = original_logger

# Tests for make_api_request
@patch('requests.post')
def test_make_api_request_success(mock_post, setup_globals, test_config):
    """Test successful API request"""
    # Configure mock
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True, "result": {"id": 123}}
    mock_post.return_value = mock_response
    
    # Call function
    result = make_api_request("get_me")
    
    # Assertions
    assert result["ok"] is True
    assert result["result"]["id"] == 123
    mock_post.assert_called_once_with(
        f"{test_config.BOT_TOKEN}/getMe",
        json=None,
        timeout=10
    )

@patch('requests.post')
def test_make_api_request_failure(mock_post, setup_globals):
    """Test API request failure with retry"""
    # Configure mock to fail
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"ok": False, "description": "Bad Request"}
    mock_post.return_value = mock_response
    
    # Call function
    result = make_api_request("get_me")
    
    # Assertions
    assert result["ok"] is False
    assert "Bad Request" in result["description"]
    assert mock_post.call_count == 1  # Only 1 retry since MAX_RETRIES=1

@patch('requests.post')
def test_make_api_request_rate_limit(mock_post, setup_globals):
    """Test API request with rate limit response"""
    # Configure mock for rate limit
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.headers = {"Retry-After": "1"}
    mock_response.raise_for_status.side_effect = [
        requests.exceptions.HTTPError("429 Too Many Requests"),
        None  # Second call succeeds
    ]
    mock_response.json.return_value = {"ok": True, "result": {"id": 123}}
    mock_post.return_value = mock_response
    
    # Call function
    result = make_api_request("get_me")
    
    # Assertions
    assert result["ok"] is False
    assert "HTTP error" in result["description"]
    assert mock_post.call_count == 1  # MAX_RETRIES=1

# Tests for validate_gift_for_transfer
def test_validate_gift_for_transfer_valid(setup_globals):
    """Test validating a gift that can be transferred"""
    gift = {
        "can_be_transferred": True,
        "transfer_star_count": 20  # Less than STAR_COUNT=25
    }
    
    is_valid, message = validate_gift_for_transfer(gift)
    
    assert is_valid is True
    assert message == ""

def test_validate_gift_for_transfer_cannot_transfer(setup_globals):
    """Test validating a gift that cannot be transferred"""
    gift = {
        "can_be_transferred": False,
        "transfer_star_count": 10
    }
    
    is_valid, message = validate_gift_for_transfer(gift)
    
    assert is_valid is False
    assert "cannot be transferred" in message

def test_validate_gift_for_transfer_insufficient_stars(setup_globals):
    """Test validating a gift with insufficient stars"""
    gift = {
        "can_be_transferred": True,
        "transfer_star_count": 30  # More than STAR_COUNT=25
    }
    
    is_valid, message = validate_gift_for_transfer(gift)
    
    assert is_valid is False
    assert "requires 30 stars" in message

# Tests for find_gift_by_id
def test_find_gift_by_id_exists(setup_globals):
    """Test finding a gift by ID when it exists"""
    gifts = [
        {"owned_gift_id": "gift1", "name": "Gift 1"},
        {"owned_gift_id": "gift2", "name": "Gift 2"},
        {"owned_gift_id": "gift3", "name": "Gift 3"}
    ]
    
    result = find_gift_by_id(gifts, "gift2")
    
    assert result is not None
    assert result["owned_gift_id"] == "gift2"
    assert result["name"] == "Gift 2"

def test_find_gift_by_id_not_exists(setup_globals):
    """Test finding a gift by ID when it doesn't exist"""
    gifts = [
        {"owned_gift_id": "gift1", "name": "Gift 1"},
        {"owned_gift_id": "gift2", "name": "Gift 2"}
    ]
    
    result = find_gift_by_id(gifts, "gift3")
    
    assert result is None

if __name__ == "__main__":
    pytest.main(["-v"]) 