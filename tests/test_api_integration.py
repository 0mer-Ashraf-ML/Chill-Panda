#!/usr/bin/env python3
"""
API Integration Tests for Chill Panda
Run these tests against a live server to verify all endpoints are working.

Usage:
    python tests/test_api_integration.py --base-url http://localhost:8000

For CI/CD:
    python tests/test_api_integration.py --base-url http://<server-host>:8000 --wait 60
"""

import argparse
import sys
import time
import uuid
import requests
from typing import Tuple

# Test configuration
TEST_USER_ID = f"test_user_{uuid.uuid4().hex[:8]}"
TEST_SESSION_ID = str(uuid.uuid4())


def log_result(test_name: str, passed: bool, message: str = ""):
    """Log test result with emoji indicators"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {test_name}")
    if message:
        print(f"       └─ {message}")


def test_health_endpoint(base_url: str) -> Tuple[bool, str]:
    """Test the /health endpoint"""
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "healthy":
                return True, f"Database: {data.get('database', 'unknown')}"
            return False, f"Status: {data.get('status')}"
        return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)


def test_api_info_endpoint(base_url: str) -> Tuple[bool, str]:
    """Test the /api/info endpoint"""
    try:
        response = requests.get(f"{base_url}/api/info", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "message" in data and "version" in data:
                return True, f"Version: {data.get('version')}"
            return False, "Missing expected fields"
        return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)


def test_chat_endpoint(base_url: str) -> Tuple[bool, str]:
    """Test the /api/v1/chat endpoint"""
    try:
        payload = {
            "input_text": "Hello, how are you?",
            "session_id": TEST_SESSION_ID,
            "user_id": TEST_USER_ID,
            "language": "en"
        }
        response = requests.post(
            f"{base_url}/api/v1/chat",
            json=payload,
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            if "reply" in data and "session_id" in data:
                reply_preview = data["reply"][:50] + "..." if len(data["reply"]) > 50 else data["reply"]
                return True, f"Reply: {reply_preview}"
            return False, "Missing expected fields"
        return False, f"HTTP {response.status_code}: {response.text[:100]}"
    except Exception as e:
        return False, str(e)


def test_chat_stream_endpoint(base_url: str) -> Tuple[bool, str]:
    """Test the /api/v1/chat/stream endpoint"""
    try:
        payload = {
            "input_text": "Tell me a short joke",
            "session_id": TEST_SESSION_ID,
            "user_id": TEST_USER_ID,
            "language": "en"
        }
        response = requests.post(
            f"{base_url}/api/v1/chat/stream",
            json=payload,
            timeout=30,
            stream=True
        )
        if response.status_code == 200:
            chunk_count = 0
            for line in response.iter_lines():
                if line:
                    chunk_count += 1
                    if chunk_count >= 3:  # Got at least 3 chunks
                        break
            return True, f"Received {chunk_count}+ chunks"
        return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)


def test_get_conversation_endpoint(base_url: str) -> Tuple[bool, str]:
    """Test the /api/v1/conversation/{session_id} endpoint"""
    try:
        response = requests.get(
            f"{base_url}/api/v1/conversation/{TEST_SESSION_ID}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if "session_id" in data and "messages" in data:
                return True, f"Found {len(data['messages'])} messages"
            return False, "Missing expected fields"
        return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)


def test_get_user_sessions_endpoint(base_url: str) -> Tuple[bool, str]:
    """Test the /api/v1/sessions/{user_id} endpoint"""
    try:
        response = requests.get(
            f"{base_url}/api/v1/sessions/{TEST_USER_ID}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return True, f"Found {len(data)} sessions"
            return False, "Expected list response"
        return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)


def test_biometric_ingest_endpoint(base_url: str) -> Tuple[bool, str]:
    """Test the /api/v1/biometric/ingest endpoint"""
    try:
        form_data = {
            "user_id": TEST_USER_ID,
            "session_id": TEST_SESSION_ID,
            "heart_rate": 75,
            "hrv": 45.5
        }
        response = requests.post(
            f"{base_url}/api/v1/biometric/ingest",
            data=form_data,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return True, f"Stress detected: {data.get('stress_event', False)}"
            return False, f"Status: {data.get('status')}"
        return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)


def test_delete_session_endpoint(base_url: str) -> Tuple[bool, str]:
    """Test the /api/v1/session/{session_id} DELETE endpoint"""
    try:
        # Create a temporary session to delete
        temp_session_id = str(uuid.uuid4())
        
        # First, create something in this session
        payload = {
            "input_text": "Test message for deletion",
            "session_id": temp_session_id,
            "user_id": TEST_USER_ID,
            "language": "en"
        }
        requests.post(f"{base_url}/api/v1/chat", json=payload, timeout=30)
        
        # Now delete the session
        response = requests.delete(
            f"{base_url}/api/v1/session/{temp_session_id}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if "message" in data:
                return True, data.get("message", "")
            return False, "Missing message field"
        return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)


def wait_for_server(base_url: str, timeout_seconds: int) -> bool:
    """Wait for server to become available"""
    print(f"⏳ Waiting up to {timeout_seconds}s for server to start...")
    start_time = time.time()
    
    while time.time() - start_time < timeout_seconds:
        try:
            response = requests.get(f"{base_url}/health", timeout=5)
            if response.status_code == 200:
                print(f"✅ Server is ready (took {int(time.time() - start_time)}s)")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(5)
    
    print(f"❌ Server did not become available within {timeout_seconds}s")
    return False


def run_all_tests(base_url: str) -> Tuple[int, int]:
    """Run all API tests and return (passed, total) counts"""
    tests = [
        ("Health Check", test_health_endpoint),
        ("API Info", test_api_info_endpoint),
        ("Chat (POST)", test_chat_endpoint),
        ("Chat Stream (POST)", test_chat_stream_endpoint),
        ("Get Conversation (GET)", test_get_conversation_endpoint),
        ("Get User Sessions (GET)", test_get_user_sessions_endpoint),
        ("Biometric Ingest (POST)", test_biometric_ingest_endpoint),
        ("Delete Session (DELETE)", test_delete_session_endpoint),
    ]
    
    print(f"\n{'='*60}")
    print(f"Running API Integration Tests")
    print(f"Base URL: {base_url}")
    print(f"Test User: {TEST_USER_ID}")
    print(f"Test Session: {TEST_SESSION_ID}")
    print(f"{'='*60}\n")
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            success, message = test_func(base_url)
            log_result(test_name, success, message)
            if success:
                passed += 1
        except Exception as e:
            log_result(test_name, False, f"Exception: {e}")
    
    print(f"\n{'='*60}")
    print(f"Results: {passed}/{total} tests passed")
    print(f"{'='*60}\n")
    
    return passed, total


def main():
    parser = argparse.ArgumentParser(description="API Integration Tests for Chill Panda")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the API server"
    )
    parser.add_argument(
        "--wait",
        type=int,
        default=0,
        help="Seconds to wait for server to start (0 = no wait)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error code if any test fails"
    )
    
    args = parser.parse_args()
    
    # Wait for server if requested
    if args.wait > 0:
        if not wait_for_server(args.base_url, args.wait):
            sys.exit(1)
    
    # Run tests
    passed, total = run_all_tests(args.base_url)
    
    # Exit with appropriate code
    if args.strict and passed < total:
        sys.exit(1)
    elif passed == 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
