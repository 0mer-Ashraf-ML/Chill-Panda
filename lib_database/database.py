"""
MongoDB Database Connection Module
"""
import os
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Database:
    """
    MongoDB database connection manager using Motor (async driver).
    """
    
    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize database connection.
        
        Args:
            connection_string: MongoDB connection string. If not provided, 
                              reads from MONGODB_URI environment variable.
        """
        self.connection_string = connection_string or os.getenv("MONGODB_URI")
        if not self.connection_string:
            raise ValueError("MONGODB_URI environment variable is required")
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        self.database_name = "chill_panda"  # Main database name
        
    async def connect(self):
        """
        Establish connection to MongoDB.
        """
        try:
            self.client = AsyncIOMotorClient(self.connection_string)
            self.db = self.client[self.database_name]
            
            # Verify connection
            await self.client.admin.command('ping')
            print(f"✅ Connected to MongoDB database: {self.database_name}")
            
            # Create indexes for better performance
            await self._create_indexes()
            
            return True
        except Exception as e:
            print(f"❌ MongoDB connection failed: {e}")
            return False
    
    async def _create_indexes(self):
        """
        Create necessary indexes for optimal query performance.
        """
        try:
            # Conversations collection indexes
            conversations = self.db.conversations
            await conversations.create_index("session_id")
            await conversations.create_index("created_at")
            await conversations.create_index([("session_id", 1), ("created_at", -1)])
            
            # Messages collection indexes
            messages = self.db.messages
            await messages.create_index("conversation_id")
            await messages.create_index("created_at")
            await messages.create_index([("conversation_id", 1), ("created_at", 1)])
            
            print("✅ MongoDB indexes created")
        except Exception as e:
            print(f"⚠️ Index creation warning: {e}")
    
    async def disconnect(self):
        """
        Close MongoDB connection.
        """
        if self.client:
            self.client.close()
            print("🔌 MongoDB connection closed")
    
    def get_collection(self, collection_name: str):
        """
        Get a collection from the database.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            MongoDB collection object
        """
        if self.db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self.db[collection_name]
    
    @property
    def conversations(self):
        """Get conversations collection."""
        return self.get_collection("conversations")
    
    @property
    def messages(self):
        """Get messages collection."""
        return self.get_collection("messages")
