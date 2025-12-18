"""
Test script for MongoDB database module.
Run this to verify the database connection and operations work correctly.

Usage:
    python lib_database/test_database.py
"""
import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib_database.database import Database
from lib_database.models import MessageRole
from lib_database.conversation_repository import ConversationRepository


async def test_database():
    """Test database connection and basic operations."""
    
    print("=" * 60)
    print("🧪 Testing MongoDB Database Module")
    print("=" * 60)
    
    # Initialize database
    db = Database()
    
    # Test 1: Connection
    print("\n📌 Test 1: Database Connection")
    connected = await db.connect()
    if not connected:
        print("❌ FAILED: Could not connect to database")
        return False
    print("✅ PASSED: Database connected successfully")
    
    # Initialize repository
    repo = ConversationRepository(db)
    
    # Test 2: Create Conversation
    print("\n📌 Test 2: Create Conversation")
    try:
        conversation = await repo.create_conversation(
            session_id="test-session-123",
            source="test",
            metadata={"test": True, "version": "1.0"}
        )
        print(f"✅ PASSED: Created conversation with ID: {conversation.id}")
    except Exception as e:
        print(f"❌ FAILED: {e}")
        await db.disconnect()
        return False
    
    # Test 3: Add User Message
    print("\n📌 Test 3: Add User Message")
    try:
        user_msg = await repo.add_user_message(
            conversation_id=conversation.id,
            content="Hello, how are you?",
            language="en"
        )
        print(f"✅ PASSED: Added user message with ID: {user_msg.id}")
    except Exception as e:
        print(f"❌ FAILED: {e}")
    
    # Test 4: Add Assistant Message
    print("\n📌 Test 4: Add Assistant Message")
    try:
        assistant_msg = await repo.add_assistant_message(
            conversation_id=conversation.id,
            content="I'm doing great! How can I help you today?",
            language="en"
        )
        print(f"✅ PASSED: Added assistant message with ID: {assistant_msg.id}")
    except Exception as e:
        print(f"❌ FAILED: {e}")
    
    # Test 5: Add multilingual messages
    print("\n📌 Test 5: Add Multilingual Messages")
    try:
        await repo.add_user_message(
            conversation_id=conversation.id,
            content="你好，今天天气怎么样？",
            language="zh"
        )
        await repo.add_assistant_message(
            conversation_id=conversation.id,
            content="今天天气很好！阳光明媚。",
            language="zh"
        )
        await repo.add_user_message(
            conversation_id=conversation.id,
            content="آپ کیسے ہیں؟",
            language="ur"
        )
        await repo.add_assistant_message(
            conversation_id=conversation.id,
            content="میں ٹھیک ہوں، شکریہ!",
            language="ur"
        )
        print("✅ PASSED: Added multilingual messages (Chinese, Urdu)")
    except Exception as e:
        print(f"❌ FAILED: {e}")
    
    # Test 6: Get Conversation Messages
    print("\n📌 Test 6: Retrieve Conversation Messages")
    try:
        messages = await repo.get_conversation_messages(conversation.id)
        print(f"✅ PASSED: Retrieved {len(messages)} messages")
        for msg in messages:
            print(f"   [{msg.role.value.upper()}] ({msg.language}): {msg.content[:50]}...")
    except Exception as e:
        print(f"❌ FAILED: {e}")
    
    # Test 7: Get Conversation by Session
    print("\n📌 Test 7: Get Conversation by Session ID")
    try:
        found_conv = await repo.get_conversation_by_session("test-session-123")
        if found_conv:
            print(f"✅ PASSED: Found conversation: {found_conv.id}")
        else:
            print("❌ FAILED: Conversation not found")
    except Exception as e:
        print(f"❌ FAILED: {e}")
    
    # Test 8: End Conversation
    print("\n📌 Test 8: End Conversation")
    try:
        ended = await repo.end_conversation(conversation.id)
        if ended:
            print("✅ PASSED: Conversation ended successfully")
        else:
            print("❌ FAILED: Could not end conversation")
    except Exception as e:
        print(f"❌ FAILED: {e}")
    
    # Test 9: Get Session History
    print("\n📌 Test 9: Get Session History")
    try:
        history = await repo.get_session_history("test-session-123")
        print(f"✅ PASSED: Retrieved {len(history)} conversation(s) in history")
    except Exception as e:
        print(f"❌ FAILED: {e}")
    
    # Test 10: Cleanup - Delete Test Conversation
    print("\n📌 Test 10: Cleanup (Delete Test Data)")
    try:
        deleted = await repo.delete_conversation(conversation.id)
        if deleted:
            print("✅ PASSED: Test conversation deleted")
        else:
            print("⚠️ WARNING: Could not delete test conversation")
    except Exception as e:
        print(f"❌ FAILED: {e}")
    
    # Disconnect
    await db.disconnect()
    
    print("\n" + "=" * 60)
    print("🎉 All tests completed!")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    asyncio.run(test_database())
