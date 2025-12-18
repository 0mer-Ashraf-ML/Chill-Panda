import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()

class MongoDBManager:
    def __init__(self):
        self.client = None
        self.db = None
        self.chats_collection = None
        self.sessions_collection = None
        self.connect()
    
    def connect(self):
        """Connect to MongoDB"""
        try:
            self.client = MongoClient(
                os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
                serverSelectionTimeoutMS=5000
            )
            # Test connection
            self.client.admin.command('ping')
            
            db_name = os.getenv("MONGODB_DATABASE", "chillpanda_db")
            self.db = self.client[db_name]
            
            self.chats_collection = self.db[os.getenv("MONGODB_CHATS_COLLECTION", "chat_history")]
            self.sessions_collection = self.db[os.getenv("MONGODB_SESSIONS_COLLECTION", "user_sessions")]
            
            # Create indexes
            self.chats_collection.create_index([("session_id", 1), ("timestamp", -1)])
            self.sessions_collection.create_index([("session_id", 1)], unique=True)
            self.sessions_collection.create_index([("user_id", 1)])
            self.sessions_collection.create_index([("last_activity", -1)])
            
            
        except ConnectionFailure as e:
            raise
    
    def save_message(self, session_id: str, user_id: str, role: str, content: str, metadata: Dict = None) -> str:
        """Save a single message to chat history"""
        try:
            message = {
                "session_id": session_id,
                "user_id": user_id,
                "role": role,  # "user" or "assistant"
                "content": content,
                "timestamp": datetime.utcnow(),
                "metadata": metadata or {}
            }
            
            result = self.chats_collection.insert_one(message)
            
            # Update session activity
            self.update_session_activity(session_id, user_id)
            
            return str(result.inserted_id)
            
        except Exception as e:
            return ""
    
    def get_conversation_history(self, session_id: str, limit: int = 20) -> List[Dict]:
        """Get conversation history for a session"""
        try:
            messages = list(self.chats_collection.find(
                {"session_id": session_id},
                {"_id": 0, "role": 1, "content": 1, "timestamp": 1}
            ).sort("timestamp", 1).limit(limit))
            
            return messages
            
        except Exception as e:
            return []
    
    def update_session_activity(self, session_id: str, user_id: str):
        """Update or create session record"""
        try:
            self.sessions_collection.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "user_id": user_id,
                        "last_activity": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    },
                    "$setOnInsert": {
                        "created_at": datetime.utcnow(),
                        "message_count": 0
                    }
                },
                upsert=True
            )
            
            # Increment message count
            self.sessions_collection.update_one(
                {"session_id": session_id},
                {"$inc": {"message_count": 1}}
            )
            
        except Exception as e:
            pass
    def get_user_sessions(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get all sessions for a user"""
        try:
            sessions = list(self.sessions_collection.find(
                {"user_id": user_id},
                {"_id": 0, "session_id": 1, "created_at": 1, "last_activity": 1, "message_count": 1}
            ).sort("last_activity", -1).limit(limit))
            
            return sessions
            
        except Exception as e:
            return []
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages"""
        try:
            # Delete all messages in the session
            self.chats_collection.delete_many({"session_id": session_id})
            
            # Delete the session record
            self.sessions_collection.delete_one({"session_id": session_id})
            
            return True
            
        except Exception as e:
            return False
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()

# Global MongoDB manager instance
mongodb_manager = MongoDBManager()