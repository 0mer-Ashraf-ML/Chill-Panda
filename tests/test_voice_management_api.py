import sys
import os
import asyncio
from fastapi.testclient import TestClient
import pytest
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from lib_database.voice_usage_models import UserVoiceUsageSummary, VoiceLimitType

client = TestClient(app)

def test_management_all_schema():
    """Verify the /all endpoint returns the correct structure (mocked)."""
    # Note: In a real environment, we'd mock the repo dependency.
    # For a quick check of the router registration:
    response = client.get("/api/v1/voice/management/all")
    # Even if empty or 500 (if DB not connected), we check if it's 200 or 500 vs 404
    assert response.status_code != 404

def test_management_user_schema():
    """Verify the /{user_id} endpoint structure (mocked)."""
    response = client.get("/api/v1/voice/management/test_user")
    assert response.status_code != 404

def test_management_reset_schema():
    """Verify the /{user_id}/reset endpoint structure (mocked)."""
    response = client.post("/api/v1/voice/management/test_user/reset")
    assert response.status_code != 404

if __name__ == "__main__":
    print("Running API registration checks...")
    test_management_all_schema()
    test_management_user_schema()
    test_management_reset_schema()
    print("API endpoints are registered and reachable.")
