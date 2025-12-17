"""
Conversation Repository - CRUD operations for conversations and messages
"""
from datetime import datetime
from typing import List, Optional
from lib_database.database import Database
from lib_database.models import Conversation, Message, MessageRole


class ConversationRepository:
    """
    Repository for managing conversations and messages in MongoDB.
    """
    
    def __init__(self, database: Database):
        """
        Initialize repository with database connection.
        
        Args:
            database: Connected Database instance
        """
        self.db = database
    
    # ==================== CONVERSATION OPERATIONS ====================
    
    async def create_conversation(
        self,
        session_id: str,
        source: str = "web",
        metadata: Optional[dict] = None
    ) -> Conversation:
        """
        Create a new conversation session.
        
        Args:
            session_id: Unique session identifier (WebSocket guid)
            source: Source of the conversation (web, phone, etc.)
            metadata: Additional metadata
            
        Returns:
            Created Conversation object
        """
        conversation = Conversation(
            session_id=session_id,
            source=source,
            metadata=metadata or {}
        )
        
        await self.db.conversations.insert_one(conversation.to_dict())
        print(f"📝 Created conversation: {conversation.id} for session: {session_id}")
        
        return conversation
    
    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """
        Get conversation by ID.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Conversation object or None
        """
        data = await self.db.conversations.find_one({"id": conversation_id})
        if data:
            return Conversation.from_dict(data)
        return None
    
    async def get_conversation_by_session(self, session_id: str) -> Optional[Conversation]:
        """
        Get active conversation by session ID.
        
        Args:
            session_id: Session ID (WebSocket guid)
            
        Returns:
            Conversation object or None
        """
        data = await self.db.conversations.find_one({
            "session_id": session_id,
            "status": "active"
        })
        if data:
            return Conversation.from_dict(data)
        return None
    
    async def end_conversation(self, conversation_id: str) -> bool:
        """
        Mark conversation as ended.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            True if successful
        """
        result = await self.db.conversations.update_one(
            {"id": conversation_id},
            {
                "$set": {
                    "status": "ended",
                    "ended_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
            }
        )
        
        if result.modified_count > 0:
            print(f"🏁 Ended conversation: {conversation_id}")
            return True
        return False
    
    async def update_conversation_stats(
        self,
        conversation_id: str,
        primary_language: Optional[str] = None
    ):
        """
        Update conversation statistics.
        
        Args:
            conversation_id: Conversation ID
            primary_language: Primary detected language
        """
        update = {"updated_at": datetime.utcnow().isoformat()}
        
        if primary_language:
            update["primary_language"] = primary_language
        
        # Get message count and total duration
        pipeline = [
            {"$match": {"conversation_id": conversation_id}},
            {"$group": {
                "_id": None,
                "total_messages": {"$sum": 1},
                "total_duration_ms": {"$sum": {"$ifNull": ["$audio_duration_ms", 0]}}
            }}
        ]
        
        async for stats in self.db.messages.aggregate(pipeline):
            update["total_messages"] = stats.get("total_messages", 0)
            update["total_duration_ms"] = stats.get("total_duration_ms", 0)
        
        await self.db.conversations.update_one(
            {"id": conversation_id},
            {"$set": update}
        )
    
    # ==================== MESSAGE OPERATIONS ====================
    
    async def add_message(
        self,
        conversation_id: str,
        role: MessageRole,
        content: str,
        language: Optional[str] = None,
        audio_duration_ms: Optional[int] = None
    ) -> Message:
        """
        Add a message to a conversation.
        
        Args:
            conversation_id: Conversation ID
            role: Message role (user/assistant/system)
            content: Message content
            language: Detected language
            audio_duration_ms: Audio duration in milliseconds
            
        Returns:
            Created Message object
        """
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            language=language,
            audio_duration_ms=audio_duration_ms
        )
        
        await self.db.messages.insert_one(message.to_dict())
        
        # Update conversation stats
        await self.db.conversations.update_one(
            {"id": conversation_id},
            {
                "$inc": {"total_messages": 1},
                "$set": {"updated_at": datetime.utcnow().isoformat()}
            }
        )
        
        print(f"💬 Added {role.value} message to conversation: {conversation_id[:8]}...")
        
        return message
    
    async def add_user_message(
        self,
        conversation_id: str,
        content: str,
        language: Optional[str] = None
    ) -> Message:
        """Convenience method to add user message."""
        return await self.add_message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=content,
            language=language
        )
    
    async def add_assistant_message(
        self,
        conversation_id: str,
        content: str,
        language: Optional[str] = None
    ) -> Message:
        """Convenience method to add assistant message."""
        return await self.add_message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=content,
            language=language
        )
    
    async def get_conversation_messages(
        self,
        conversation_id: str,
        limit: int = 100
    ) -> List[Message]:
        """
        Get all messages in a conversation.
        
        Args:
            conversation_id: Conversation ID
            limit: Maximum number of messages to return
            
        Returns:
            List of Message objects
        """
        cursor = self.db.messages.find(
            {"conversation_id": conversation_id}
        ).sort("created_at", 1).limit(limit)
        
        messages = []
        async for data in cursor:
            messages.append(Message.from_dict(data))
        
        return messages
    
    async def get_recent_messages(
        self,
        conversation_id: str,
        count: int = 10
    ) -> List[Message]:
        """
        Get recent messages for context.
        
        Args:
            conversation_id: Conversation ID
            count: Number of recent messages
            
        Returns:
            List of recent Message objects
        """
        cursor = self.db.messages.find(
            {"conversation_id": conversation_id}
        ).sort("created_at", -1).limit(count)
        
        messages = []
        async for data in cursor:
            messages.append(Message.from_dict(data))
        
        # Reverse to get chronological order
        return list(reversed(messages))
    
    # ==================== UTILITY OPERATIONS ====================
    
    async def get_session_history(self, session_id: str) -> List[dict]:
        """
        Get full history for a session including all conversations.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of conversations with their messages
        """
        history = []
        
        cursor = self.db.conversations.find(
            {"session_id": session_id}
        ).sort("created_at", -1)
        
        async for conv_data in cursor:
            conversation = Conversation.from_dict(conv_data)
            messages = await self.get_conversation_messages(conversation.id)
            
            history.append({
                "conversation": conversation.to_dict(),
                "messages": [m.to_dict() for m in messages]
            })
        
        return history
    
    async def delete_conversation(self, conversation_id: str) -> bool:
        """
        Delete a conversation and all its messages.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            True if successful
        """
        # Delete messages first
        await self.db.messages.delete_many({"conversation_id": conversation_id})
        
        # Delete conversation
        result = await self.db.conversations.delete_one({"id": conversation_id})
        
        if result.deleted_count > 0:
            print(f"🗑️ Deleted conversation: {conversation_id}")
            return True
        return False
