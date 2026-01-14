"""
Unit tests for Voice Usage Monitoring logic
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch

from lib_database.voice_usage_model import VoiceUsage, VoiceSession
from lib_voice_usage.voice_usage_handler import VoiceUsageHandler
from lib_infrastructure.dispatcher import MessageType, Message


@pytest.fixture
def mock_dispatcher():
    dispatcher = AsyncMock()
    # Mock subscribe to return an async context manager that yields an async iterator
    # This simulates "async with await dispatcher.subscribe() as subscriber: async for event in subscriber:"
    
    mock_subscriber = AsyncMock()
    mock_subscriber.__aiter__.return_value = [] # Default empty
    
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_subscriber
    
    dispatcher.subscribe.return_value = mock_context_manager
    return dispatcher

@pytest.fixture
def mock_repository():
    repo = AsyncMock()
    # Setup default returns
    repo.get_daily_total.return_value = 0.0
    repo.get_monthly_total.return_value = 0.0
    repo.get_long_session_count.return_value = 0
    return repo

@pytest.fixture
def voice_config():
    return {
        "session_limit": 30,
        "daily_limit": 60,
        "monthly_limit": 600,
        "abuse_continuous_threshold": 300,
        "abuse_session_count": 10,
        "abuse_long_session_threshold": 180
    }

@pytest.mark.asyncio
async def test_initialization(mock_dispatcher, mock_repository, voice_config):
    """Test that handler initializes and loads stats."""
    handler = VoiceUsageHandler(
        guid="test-session",
        dispatcher=mock_dispatcher,
        repository=mock_repository,
        user_id="test-user",
        config=voice_config
    )
    
    # Mock return values for DB stats
    mock_repository.get_daily_total.return_value = 10.0
    mock_repository.get_monthly_total.return_value = 100.0
    
    await handler._load_initial_stats()
    
    assert handler.daily_seconds == 10.0
    assert handler.monthly_seconds == 100.0
    mock_repository.create_voice_session.assert_not_called() # Only called in run_async

@pytest.mark.asyncio
async def test_add_usage(mock_dispatcher, mock_repository, voice_config):
    """Test adding usage updates limits and broadcasting."""
    handler = VoiceUsageHandler(
        guid="test-session",
        dispatcher=mock_dispatcher,
        repository=mock_repository,
        user_id="test-user",
        config=voice_config
    )
    
    await handler._add_usage(5.0)
    
    assert handler.session_voice_seconds == 5.0
    assert handler.daily_seconds == 5.0
    
    # Check DB update
    mock_repository.add_voice_seconds.assert_called_with("test-user", 5.0, False)
    mock_repository.update_voice_session.assert_called()
    
    # Check broadcast
    mock_dispatcher.broadcast.assert_called()
    call_args = mock_dispatcher.broadcast.call_args[0]
    assert call_args[1].message_header.message_type == MessageType.VOICE_USAGE_UPDATE

@pytest.mark.asyncio
async def test_session_limit_enforcement(mock_dispatcher, mock_repository, voice_config):
    """Test that session limit triggers enforcement."""
    voice_config["session_limit"] = 10
    handler = VoiceUsageHandler(
        guid="test-session",
        dispatcher=mock_dispatcher,
        repository=mock_repository,
        user_id="test-user",
        config=voice_config
    )
    
    # Add usage up to limit
    await handler._add_usage(10.0)
    
    assert handler.is_voice_disabled is True
    assert handler.limit_reached_type == "session"
    
    # Check broadcast of limit reached
    # broadcast called twice: once for usage update, once for limit reached
    assert mock_dispatcher.broadcast.call_count >= 2
    
    # Verify the limit reached message
    calls = mock_dispatcher.broadcast.call_args_list
    limit_msg = next(c[0][1] for c in calls if c[0][1].message_header.message_type == MessageType.VOICE_LIMIT_REACHED)
    assert limit_msg.data["limit_type"] == "session"
    assert limit_msg.data["is_voice_disabled"] is True

@pytest.mark.asyncio
async def test_daily_limit_enforcement(mock_dispatcher, mock_repository, voice_config):
    """Test that daily limit triggers enforcement."""
    voice_config["daily_limit"] = 10
    handler = VoiceUsageHandler(
        guid="test-session",
        dispatcher=mock_dispatcher,
        repository=mock_repository,
        user_id="test-user",
        config=voice_config
    )
    
    # Set initial daily usage
    handler.daily_seconds = 8.0
    
    # Add usage to cross limit
    await handler._add_usage(3.0)
    
    assert handler.daily_seconds == 11.0
    assert handler.is_voice_disabled is True
    assert handler.limit_reached_type == "daily"

@pytest.mark.asyncio
async def test_abuse_detection_long_sessions(mock_dispatcher, mock_repository, voice_config):
    """Test abuse detection for too many long sessions."""
    voice_config["abuse_session_count"] = 2
    voice_config["abuse_long_session_threshold"] = 5
    
    mock_repository.get_long_session_count.return_value = 2 # Already at limit
    
    handler = VoiceUsageHandler(
        guid="test-session",
        dispatcher=mock_dispatcher,
        repository=mock_repository,
        user_id="test-user",
        config=voice_config
    )
    
    # Add usage that qualifies as long session
    await handler._add_usage(6.0)
    
    assert handler.abuse_detected is True
    assert handler.abuse_type == "session_spam"
    
    # Check broadcast
    calls = mock_dispatcher.broadcast.call_args_list
    abuse_msg = next(c[0][1] for c in calls if c[0][1].message_header.message_type == MessageType.VOICE_ABUSE_DETECTED)
    assert abuse_msg.data["abuse_type"] == "session_spam"

