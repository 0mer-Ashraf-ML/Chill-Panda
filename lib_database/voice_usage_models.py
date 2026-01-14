"""
Voice Usage Data Models for tracking TTS usage limits per user.
"""
from datetime import datetime, date
from typing import Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum
import uuid


class VoiceLimitType(str, Enum):
    """Type of voice limit that was reached."""
    SESSION = "session"
    DAILY = "daily"
    MONTHLY = "monthly"


class AbuseEventType(str, Enum):
    """Type of abuse detection event."""
    EXCESSIVE_CONTINUOUS_USE = "excessive_continuous_use"
    RAPID_RECONNECTION = "rapid_reconnection"
    LONG_SESSION_NO_BREAKS = "long_session_no_breaks"


@dataclass
class VoiceUsageSession:
    """
    Tracks voice usage for a single WebSocket session.
    """
    session_id: str              # WebSocket guid
    user_id: str                 # User identifier
    duration_ms: int = 0         # Total audio duration in milliseconds
    chunk_count: int = 0         # Number of audio chunks sent
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_activity_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    is_active: bool = True
    voice_disabled: bool = False  # True if limit was reached during session
    limit_reached: Optional[VoiceLimitType] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB storage."""
        data = asdict(self)
        data['started_at'] = self.started_at.isoformat() if isinstance(self.started_at, datetime) else self.started_at
        data['last_activity_at'] = self.last_activity_at.isoformat() if isinstance(self.last_activity_at, datetime) else self.last_activity_at
        if self.ended_at:
            data['ended_at'] = self.ended_at.isoformat() if isinstance(self.ended_at, datetime) else self.ended_at
        if self.limit_reached:
            data['limit_reached'] = self.limit_reached.value if isinstance(self.limit_reached, VoiceLimitType) else self.limit_reached
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "VoiceUsageSession":
        """Create VoiceUsageSession from dictionary."""
        data = {k: v for k, v in data.items() if k != '_id'}
        for field_name in ['started_at', 'last_activity_at', 'ended_at']:
            if isinstance(data.get(field_name), str):
                data[field_name] = datetime.fromisoformat(data[field_name])
        if isinstance(data.get('limit_reached'), str):
            data['limit_reached'] = VoiceLimitType(data['limit_reached'])
        return cls(**data)

    @property
    def duration_minutes(self) -> float:
        """Get duration in minutes."""
        return self.duration_ms / 60000.0


@dataclass
class VoiceUsageDaily:
    """
    Tracks daily voice usage for a user.
    """
    user_id: str
    date: str  # ISO date string (YYYY-MM-DD)
    duration_ms: int = 0
    session_count: int = 0
    chunk_count: int = 0
    limit_reached_count: int = 0  # How many times limit was reached today
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
    def from_dict(cls, data: dict) -> "VoiceUsageDaily":
        """Create VoiceUsageDaily from dictionary."""
        data = {k: v for k, v in data.items() if k != '_id'}
        for field_name in ['created_at', 'updated_at']:
            if isinstance(data.get(field_name), str):
                data[field_name] = datetime.fromisoformat(data[field_name])
        return cls(**data)

    @property
    def duration_minutes(self) -> float:
        """Get duration in minutes."""
        return self.duration_ms / 60000.0


@dataclass
class VoiceUsageMonthly:
    """
    Tracks monthly voice usage for a user.
    """
    user_id: str
    year_month: str  # Format: YYYY-MM
    duration_ms: int = 0
    session_count: int = 0
    day_count: int = 0  # Number of unique days with usage
    limit_reached_count: int = 0
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
    def from_dict(cls, data: dict) -> "VoiceUsageMonthly":
        """Create VoiceUsageMonthly from dictionary."""
        data = {k: v for k, v in data.items() if k != '_id'}
        for field_name in ['created_at', 'updated_at']:
            if isinstance(data.get(field_name), str):
                data[field_name] = datetime.fromisoformat(data[field_name])
        return cls(**data)

    @property
    def duration_minutes(self) -> float:
        """Get duration in minutes."""
        return self.duration_ms / 60000.0


@dataclass
class VoiceLimitEvent:
    """
    Records when a voice limit is reached.
    """
    user_id: str
    session_id: str
    limit_type: VoiceLimitType
    limit_value_minutes: float  # The limit that was exceeded
    usage_value_minutes: float  # Actual usage when limit was reached
    timestamp: datetime = field(default_factory=datetime.utcnow)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB storage."""
        data = asdict(self)
        data['limit_type'] = self.limit_type.value if isinstance(self.limit_type, VoiceLimitType) else self.limit_type
        data['timestamp'] = self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "VoiceLimitEvent":
        """Create VoiceLimitEvent from dictionary."""
        data = {k: v for k, v in data.items() if k != '_id'}
        if isinstance(data.get('limit_type'), str):
            data['limit_type'] = VoiceLimitType(data['limit_type'])
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class VoiceAbuseEvent:
    """
    Records suspected abuse patterns.
    """
    user_id: str
    session_id: Optional[str]
    event_type: AbuseEventType
    details: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    reviewed: bool = False
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    action_taken: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB storage."""
        data = asdict(self)
        data['event_type'] = self.event_type.value if isinstance(self.event_type, AbuseEventType) else self.event_type
        data['timestamp'] = self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp
        if self.reviewed_at:
            data['reviewed_at'] = self.reviewed_at.isoformat() if isinstance(self.reviewed_at, datetime) else self.reviewed_at
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "VoiceAbuseEvent":
        """Create VoiceAbuseEvent from dictionary."""
        data = {k: v for k, v in data.items() if k != '_id'}
        if isinstance(data.get('event_type'), str):
            data['event_type'] = AbuseEventType(data['event_type'])
        for field_name in ['timestamp', 'reviewed_at']:
            if isinstance(data.get(field_name), str):
                data[field_name] = datetime.fromisoformat(data[field_name])
        return cls(**data)


@dataclass
class UserVoiceUsageSummary:
    """
    Summary of a user's voice usage across all time periods.
    Used for real-time limit checking.
    """
    user_id: str
    session_duration_ms: int = 0
    daily_duration_ms: int = 0
    monthly_duration_ms: int = 0
    session_limit_ms: int = 0
    daily_limit_ms: int = 0
    monthly_limit_ms: int = 0
    voice_enabled: bool = True
    limit_reached: Optional[VoiceLimitType] = None

    @property
    def session_remaining_ms(self) -> int:
        """Remaining session time in milliseconds."""
        return max(0, self.session_limit_ms - self.session_duration_ms)

    @property
    def daily_remaining_ms(self) -> int:
        """Remaining daily time in milliseconds."""
        return max(0, self.daily_limit_ms - self.daily_duration_ms)

    @property
    def monthly_remaining_ms(self) -> int:
        """Remaining monthly time in milliseconds."""
        return max(0, self.monthly_limit_ms - self.monthly_duration_ms)

    @property
    def remaining_ms(self) -> int:
        """Minimum remaining time across all limits."""
        return min(self.session_remaining_ms, self.daily_remaining_ms, self.monthly_remaining_ms)

    def check_limits(self) -> Optional[VoiceLimitType]:
        """
        Check if any limit has been exceeded.
        Returns the type of limit exceeded, or None if within limits.
        """
        if self.session_duration_ms >= self.session_limit_ms:
            return VoiceLimitType.SESSION
        if self.daily_duration_ms >= self.daily_limit_ms:
            return VoiceLimitType.DAILY
        if self.monthly_duration_ms >= self.monthly_limit_ms:
            return VoiceLimitType.MONTHLY
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "user_id": self.user_id,
            "session_duration_ms": self.session_duration_ms,
            "daily_duration_ms": self.daily_duration_ms,
            "monthly_duration_ms": self.monthly_duration_ms,
            "session_remaining_ms": self.session_remaining_ms,
            "daily_remaining_ms": self.daily_remaining_ms,
            "monthly_remaining_ms": self.monthly_remaining_ms,
            "voice_enabled": self.voice_enabled,
            "limit_reached": self.limit_reached.value if self.limit_reached else None
        }
