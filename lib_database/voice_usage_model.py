"""
Voice Usage Data Models for tracking voice minutes per user
"""
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, field, asdict
import uuid


@dataclass
class VoiceUsage:
    """
    Tracks voice usage for a user on a specific date.
    Aggregates voice seconds across all sessions for daily/monthly tracking.
    """
    user_id: str
    date: str  # YYYY-MM-DD format for daily tracking
    month: str  # YYYY-MM format for monthly tracking
    voice_seconds_used: float = 0.0  # Accumulated voice seconds for the day
    session_count: int = 0  # Number of voice sessions
    long_session_count: int = 0  # Sessions exceeding threshold
    abuse_flags: List[str] = field(default_factory=list)  # Detected abuse patterns
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB storage."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at
        data['updated_at'] = self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "VoiceUsage":
        """Create VoiceUsage from dictionary."""
        # Remove MongoDB's internal _id field
        data = {k: v for k, v in data.items() if k != '_id'}
        for field_name in ['created_at', 'updated_at']:
            if isinstance(data.get(field_name), str):
                data[field_name] = datetime.fromisoformat(data[field_name])
        return cls(**data)


@dataclass
class VoiceSession:
    """
    Tracks a single voice session within a WebSocket connection.
    Used for per-session limit enforcement.
    """
    session_id: str  # WebSocket guid
    user_id: str
    voice_seconds_used: float = 0.0
    speech_segments: int = 0  # Number of speech start/end cycles
    continuous_seconds: float = 0.0  # Longest continuous speech segment
    is_voice_disabled: bool = False
    limit_reached: Optional[str] = None  # "session" | "daily" | "monthly" | None
    abuse_detected: bool = False
    abuse_type: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB storage."""
        data = asdict(self)
        data['started_at'] = self.started_at.isoformat() if isinstance(self.started_at, datetime) else self.started_at
        if self.ended_at:
            data['ended_at'] = self.ended_at.isoformat() if isinstance(self.ended_at, datetime) else self.ended_at
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "VoiceSession":
        """Create VoiceSession from dictionary."""
        # Remove MongoDB's internal _id field
        data = {k: v for k, v in data.items() if k != '_id'}
        for field_name in ['started_at', 'ended_at']:
            if isinstance(data.get(field_name), str):
                data[field_name] = datetime.fromisoformat(data[field_name])
        return cls(**data)
