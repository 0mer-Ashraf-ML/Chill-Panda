# lib_database - MongoDB Database Module

This module provides MongoDB integration for storing user conversations and chat history.

## 📦 Components

| File | Description |
|------|-------------|
| `database.py` | MongoDB connection management |
| `conversation_repository.py` | CRUD operations for conversations |
| `models.py` | Pydantic models for data structures |

## 🚀 Quick Start

```python
from lib_database.database import Database
from lib_database.conversation_repository import ConversationRepository

# Initialize and connect
db = Database()
await db.connect()

# Create repository instance
repo = ConversationRepository(db)

# Create a new conversation
conversation = await repo.create_conversation(
    session_id="your-uuid-here",
    source="web"
)

# Add messages
await repo.add_user_message(conversation.id, "Hello Panda!")
await repo.add_assistant_message(conversation.id, "Hello friend! How are you feeling today?")

# Retrieve recent messages (for context window)
messages = await repo.get_recent_messages(conversation.id, count=10)

# Clean up
await db.disconnect()
```

## 📚 Available Methods

### ConversationRepository

| Method | Description |
|--------|-------------|
| `create_conversation(session_id, source, metadata)` | Create new conversation session |
| `get_conversation(conversation_id)` | Get conversation by ID |
| `get_conversation_by_session(session_id)` | Get active conversation by session |
| `end_conversation(conversation_id)` | Mark conversation as ended |
| `add_message(conversation_id, role, content, ...)` | Add a message |
| `add_user_message(conversation_id, content, language)` | Add user message |
| `add_assistant_message(conversation_id, content, language)` | Add assistant message |
| `get_conversation_messages(conversation_id, limit)` | Get all messages |
| `get_recent_messages(conversation_id, count)` | Get recent N messages |
| `get_session_history(session_id)` | Get full session history |
| `delete_conversation(conversation_id)` | Delete conversation |

## 🗄️ Data Models

### Conversation
```python
{
    "id": "64a...",           # MongoDB ObjectId
    "session_id": "uuid",     # WebSocket session UUID
    "source": "web",          # web, phone, device
    "is_active": True,
    "created_at": datetime,
    "updated_at": datetime,
    "message_count": 10,
    "metadata": {}
}
```

### Message
```python
{
    "id": "64b...",
    "conversation_id": "64a...",
    "role": "user",           # user, assistant, system
    "content": "Hello!",
    "language": "en",
    "audio_duration_ms": 1500,
    "created_at": datetime
}
```

## ⚙️ Configuration

Set the following environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGODB_URI` | `mongodb://localhost:27017` | Connection string |
| `MONGODB_DATABASE` | `chillpanda_db` | Database name |
