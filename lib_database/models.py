"""
MongoDB Data Models for Conversations
"""
from datetime import datetime
from typing import List, Optional, Literal
from dataclasses import dataclass, field, asdict
from enum import Enum
import uuid


class MessageRole(str, Enum):
    """Role of the message sender."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """
    Represents a single message in a conversation.
    """
    role: MessageRole
    content: str
    conversation_id: str
    language: Optional[str] = None  # Detected language
    audio_duration_ms: Optional[int] = None  # Duration of audio if applicable
    created_at: datetime = field(default_factory=datetime.utcnow)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB storage."""
        data = asdict(self)
        data['role'] = self.role.value if isinstance(self.role, MessageRole) else self.role
        data['created_at'] = self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """Create Message from dictionary."""
        # Remove MongoDB's internal _id field
        data = {k: v for k, v in data.items() if k != '_id'}
        data['role'] = MessageRole(data['role']) if isinstance(data['role'], str) else data['role']
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)


@dataclass
class Conversation:
    """
    Represents a conversation session.
    """
    session_id: str  # Unique session identifier (e.g., WebSocket guid)
    source: str = "web"  # Source of conversation (web, phone, etc.)
    status: Literal["active", "ended"] = "active"
    primary_language: Optional[str] = None  # Primary detected language
    total_messages: int = 0
    total_duration_ms: int = 0  # Total audio duration
    metadata: dict = field(default_factory=dict)  # Additional metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB storage."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at
        data['updated_at'] = self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at
        if self.ended_at:
            data['ended_at'] = self.ended_at.isoformat() if isinstance(self.ended_at, datetime) else self.ended_at
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "Conversation":
        """Create Conversation from dictionary."""
        # Remove MongoDB's internal _id field
        data = {k: v for k, v in data.items() if k != '_id'}
        for field_name in ['created_at', 'updated_at', 'ended_at']:
            if isinstance(data.get(field_name), str):
                data[field_name] = datetime.fromisoformat(data[field_name])
        return cls(**data)
