# lib_database - MongoDB Database Module

This module provides MongoDB integration for storing user conversations.

## Usage

```python
from lib_database.database import Database
from lib_database.conversation_repository import ConversationRepository

# Initialize database
db = Database()
await db.connect()

# Use repository
repo = ConversationRepository(db)
await repo.create_conversation(session_id="...", user_message="Hello", assistant_response="Hi!")

# Don't forget to close
await db.disconnect()
```
