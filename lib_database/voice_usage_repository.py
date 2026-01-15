"""
Voice Usage Repository - CRUD operations for voice usage tracking.
"""
from datetime import datetime, timedelta
from typing import Optional, List
from lib_database.database import Database
from lib_database.voice_usage_models import (
    VoiceUsageSession,
    VoiceUsageDaily,
    VoiceUsageMonthly,
    VoiceLimitEvent,
    VoiceAbuseEvent,
    VoiceLimitType,
    AbuseEventType,
    UserVoiceUsageSummary
)
from app.config import (
    VOICE_LIMIT_SESSION_MINUTES,
    VOICE_LIMIT_DAILY_MINUTES,
    VOICE_LIMIT_MONTHLY_MINUTES
)


class VoiceUsageRepository:
    """
    Repository for managing voice usage data in MongoDB.
    """

    def __init__(self, database: Database):
        """
        Initialize repository with database connection.

        Args:
            database: Connected Database instance
        """
        self.db = database

    # ==================== COLLECTION ACCESSORS ====================

    @property
    def voice_sessions(self):
        """Get voice usage sessions collection."""
        return self.db.get_collection("voice_usage_sessions")

    @property
    def voice_daily(self):
        """Get daily voice usage collection."""
        return self.db.get_collection("voice_usage_daily")

    @property
    def voice_monthly(self):
        """Get monthly voice usage collection."""
        return self.db.get_collection("voice_usage_monthly")

    @property
    def voice_limit_events(self):
        """Get voice limit events collection."""
        return self.db.get_collection("voice_limit_events")

    @property
    def voice_abuse_events(self):
        """Get voice abuse events collection."""
        return self.db.get_collection("voice_abuse_events")

    # ==================== SESSION OPERATIONS ====================

    async def create_session(self, session_id: str, user_id: str) -> VoiceUsageSession:
        """
        Create a new voice usage session.

        Args:
            session_id: WebSocket session GUID
            user_id: User identifier

        Returns:
            Created VoiceUsageSession object
        """
        session = VoiceUsageSession(
            session_id=session_id,
            user_id=user_id
        )

        await self.voice_sessions.insert_one(session.to_dict())
        print(f"[VoiceUsage] Created session for user: {user_id}, session: {session_id[:8]}...")

        return session

    async def get_session(self, session_id: str) -> Optional[VoiceUsageSession]:
        """
        Get a voice usage session by session ID.

        Args:
            session_id: WebSocket session GUID

        Returns:
            VoiceUsageSession object or None
        """
        data = await self.voice_sessions.find_one({"session_id": session_id})
        if data:
            return VoiceUsageSession.from_dict(data)
        return None

    async def get_active_session(self, session_id: str) -> Optional[VoiceUsageSession]:
        """
        Get active voice usage session.

        Args:
            session_id: WebSocket session GUID

        Returns:
            VoiceUsageSession object or None
        """
        data = await self.voice_sessions.find_one({
            "session_id": session_id,
            "is_active": True
        })
        if data:
            return VoiceUsageSession.from_dict(data)
        return None

    async def update_session_usage(
        self,
        session_id: str,
        duration_ms_increment: int,
        chunk_count_increment: int = 1
    ) -> Optional[VoiceUsageSession]:
        """
        Update session usage with new audio duration.

        Args:
            session_id: WebSocket session GUID
            duration_ms_increment: Duration to add in milliseconds
            chunk_count_increment: Number of chunks to add

        Returns:
            Updated VoiceUsageSession or None
        """
        result = await self.voice_sessions.find_one_and_update(
            {"session_id": session_id, "is_active": True},
            {
                "$inc": {
                    "duration_ms": duration_ms_increment,
                    "chunk_count": chunk_count_increment
                },
                "$set": {
                    "last_activity_at": datetime.utcnow().isoformat()
                }
            },
            return_document=True
        )

        if result:
            return VoiceUsageSession.from_dict(result)
        return None

    async def end_session(self, session_id: str) -> bool:
        """
        Mark a session as ended.

        Args:
            session_id: WebSocket session GUID

        Returns:
            True if successful
        """
        result = await self.voice_sessions.update_one(
            {"session_id": session_id, "is_active": True},
            {
                "$set": {
                    "is_active": False,
                    "ended_at": datetime.utcnow().isoformat()
                }
            }
        )

        if result.modified_count > 0:
            print(f"[VoiceUsage] Ended session: {session_id[:8]}...")
            return True
        return False

    async def mark_session_limit_reached(
        self,
        session_id: str,
        limit_type: VoiceLimitType
    ) -> bool:
        """
        Mark session as having reached a limit.

        Args:
            session_id: WebSocket session GUID
            limit_type: Type of limit reached

        Returns:
            True if successful
        """
        result = await self.voice_sessions.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "voice_disabled": True,
                    "limit_reached": limit_type.value
                }
            }
        )
        return result.modified_count > 0

    # ==================== DAILY USAGE OPERATIONS ====================

    async def get_or_create_daily(self, user_id: str, date_str: Optional[str] = None) -> VoiceUsageDaily:
        """
        Get or create daily usage record for a user.

        Args:
            user_id: User identifier
            date_str: Date string (YYYY-MM-DD), defaults to today

        Returns:
            VoiceUsageDaily object
        """
        if date_str is None:
            date_str = datetime.utcnow().strftime("%Y-%m-%d")

        data = await self.voice_daily.find_one({
            "user_id": user_id,
            "date": date_str
        })

        if data:
            return VoiceUsageDaily.from_dict(data)

        # Create new daily record
        daily = VoiceUsageDaily(
            user_id=user_id,
            date=date_str
        )
        await self.voice_daily.insert_one(daily.to_dict())
        return daily

    async def update_daily_usage(
        self,
        user_id: str,
        duration_ms_increment: int,
        chunk_count_increment: int = 1,
        date_str: Optional[str] = None
    ) -> VoiceUsageDaily:
        """
        Update daily usage for a user.

        Args:
            user_id: User identifier
            duration_ms_increment: Duration to add in milliseconds
            chunk_count_increment: Number of chunks to add
            date_str: Date string (YYYY-MM-DD), defaults to today

        Returns:
            Updated VoiceUsageDaily
        """
        if date_str is None:
            date_str = datetime.utcnow().strftime("%Y-%m-%d")

        result = await self.voice_daily.find_one_and_update(
            {"user_id": user_id, "date": date_str},
            {
                "$inc": {
                    "duration_ms": duration_ms_increment,
                    "chunk_count": chunk_count_increment
                },
                "$set": {
                    "updated_at": datetime.utcnow().isoformat()
                },
                "$setOnInsert": {
                    "id": str(__import__('uuid').uuid4()),
                    "user_id": user_id,
                    "date": date_str,
                    "session_count": 0,
                    "limit_reached_count": 0,
                    "created_at": datetime.utcnow().isoformat()
                }
            },
            upsert=True,
            return_document=True
        )

        return VoiceUsageDaily.from_dict(result)

    async def increment_daily_session_count(self, user_id: str, date_str: Optional[str] = None):
        """
        Increment session count for daily usage.

        Args:
            user_id: User identifier
            date_str: Date string (YYYY-MM-DD), defaults to today
        """
        if date_str is None:
            date_str = datetime.utcnow().strftime("%Y-%m-%d")

        await self.voice_daily.update_one(
            {"user_id": user_id, "date": date_str},
            {
                "$inc": {"session_count": 1},
                "$set": {"updated_at": datetime.utcnow().isoformat()},
                "$setOnInsert": {
                    "id": str(__import__('uuid').uuid4()),
                    "user_id": user_id,
                    "date": date_str,
                    "duration_ms": 0,
                    "chunk_count": 0,
                    "limit_reached_count": 0,
                    "created_at": datetime.utcnow().isoformat()
                }
            },
            upsert=True
        )

    async def increment_daily_limit_reached(self, user_id: str, date_str: Optional[str] = None):
        """
        Increment limit reached count for daily usage.

        Args:
            user_id: User identifier
            date_str: Date string (YYYY-MM-DD), defaults to today
        """
        if date_str is None:
            date_str = datetime.utcnow().strftime("%Y-%m-%d")

        await self.voice_daily.update_one(
            {"user_id": user_id, "date": date_str},
            {
                "$inc": {"limit_reached_count": 1},
                "$set": {"updated_at": datetime.utcnow().isoformat()}
            },
            upsert=True
        )

    # ==================== MONTHLY USAGE OPERATIONS ====================

    async def get_or_create_monthly(self, user_id: str, year_month: Optional[str] = None) -> VoiceUsageMonthly:
        """
        Get or create monthly usage record for a user.

        Args:
            user_id: User identifier
            year_month: Year-month string (YYYY-MM), defaults to current month

        Returns:
            VoiceUsageMonthly object
        """
        if year_month is None:
            year_month = datetime.utcnow().strftime("%Y-%m")

        data = await self.voice_monthly.find_one({
            "user_id": user_id,
            "year_month": year_month
        })

        if data:
            return VoiceUsageMonthly.from_dict(data)

        # Create new monthly record
        monthly = VoiceUsageMonthly(
            user_id=user_id,
            year_month=year_month
        )
        await self.voice_monthly.insert_one(monthly.to_dict())
        return monthly

    async def update_monthly_usage(
        self,
        user_id: str,
        duration_ms_increment: int,
        year_month: Optional[str] = None
    ) -> VoiceUsageMonthly:
        """
        Update monthly usage for a user.

        Args:
            user_id: User identifier
            duration_ms_increment: Duration to add in milliseconds
            year_month: Year-month string (YYYY-MM), defaults to current month

        Returns:
            Updated VoiceUsageMonthly
        """
        if year_month is None:
            year_month = datetime.utcnow().strftime("%Y-%m")

        result = await self.voice_monthly.find_one_and_update(
            {"user_id": user_id, "year_month": year_month},
            {
                "$inc": {"duration_ms": duration_ms_increment},
                "$set": {"updated_at": datetime.utcnow().isoformat()},
                "$setOnInsert": {
                    "id": str(__import__('uuid').uuid4()),
                    "user_id": user_id,
                    "year_month": year_month,
                    "session_count": 0,
                    "day_count": 0,
                    "limit_reached_count": 0,
                    "created_at": datetime.utcnow().isoformat()
                }
            },
            upsert=True,
            return_document=True
        )

        return VoiceUsageMonthly.from_dict(result)

    async def increment_monthly_session_count(self, user_id: str, year_month: Optional[str] = None):
        """
        Increment session count for monthly usage.

        Args:
            user_id: User identifier
            year_month: Year-month string (YYYY-MM), defaults to current month
        """
        if year_month is None:
            year_month = datetime.utcnow().strftime("%Y-%m")

        await self.voice_monthly.update_one(
            {"user_id": user_id, "year_month": year_month},
            {
                "$inc": {"session_count": 1},
                "$set": {"updated_at": datetime.utcnow().isoformat()},
                "$setOnInsert": {
                    "id": str(__import__('uuid').uuid4()),
                    "user_id": user_id,
                    "year_month": year_month,
                    "duration_ms": 0,
                    "day_count": 0,
                    "limit_reached_count": 0,
                    "created_at": datetime.utcnow().isoformat()
                }
            },
            upsert=True
        )

    # ==================== LIMIT EVENT OPERATIONS ====================

    async def record_limit_event(
        self,
        user_id: str,
        session_id: str,
        limit_type: VoiceLimitType,
        limit_value_minutes: float,
        usage_value_minutes: float
    ) -> VoiceLimitEvent:
        """
        Record when a voice limit is reached.

        Args:
            user_id: User identifier
            session_id: WebSocket session GUID
            limit_type: Type of limit reached
            limit_value_minutes: The limit value in minutes
            usage_value_minutes: Actual usage in minutes

        Returns:
            Created VoiceLimitEvent
        """
        event = VoiceLimitEvent(
            user_id=user_id,
            session_id=session_id,
            limit_type=limit_type,
            limit_value_minutes=limit_value_minutes,
            usage_value_minutes=usage_value_minutes
        )

        await self.voice_limit_events.insert_one(event.to_dict())
        print(f"[VoiceUsage] Limit reached - User: {user_id}, Type: {limit_type.value}, "
              f"Limit: {limit_value_minutes}min, Usage: {usage_value_minutes:.2f}min")

        return event

    async def get_user_limit_events(
        self,
        user_id: str,
        limit: int = 50,
        since: Optional[datetime] = None
    ) -> List[VoiceLimitEvent]:
        """
        Get limit events for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of events to return
            since: Only get events since this datetime

        Returns:
            List of VoiceLimitEvent objects
        """
        query = {"user_id": user_id}
        if since:
            query["timestamp"] = {"$gte": since.isoformat()}

        cursor = self.voice_limit_events.find(query).sort("timestamp", -1).limit(limit)

        events = []
        async for data in cursor:
            events.append(VoiceLimitEvent.from_dict(data))

        return events

    # ==================== ABUSE EVENT OPERATIONS ====================

    async def record_abuse_event(
        self,
        user_id: str,
        session_id: Optional[str],
        event_type: AbuseEventType,
        details: dict
    ) -> VoiceAbuseEvent:
        """
        Record a suspected abuse event.

        Args:
            user_id: User identifier
            session_id: WebSocket session GUID (if applicable)
            event_type: Type of abuse detected
            details: Additional details about the event

        Returns:
            Created VoiceAbuseEvent
        """
        event = VoiceAbuseEvent(
            user_id=user_id,
            session_id=session_id,
            event_type=event_type,
            details=details
        )

        await self.voice_abuse_events.insert_one(event.to_dict())
        print(f"[VoiceUsage] ABUSE DETECTED - User: {user_id}, Type: {event_type.value}, "
              f"Details: {details}")

        return event

    async def get_pending_abuse_events(self, limit: int = 100) -> List[VoiceAbuseEvent]:
        """
        Get abuse events that haven't been reviewed.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of VoiceAbuseEvent objects
        """
        cursor = self.voice_abuse_events.find(
            {"reviewed": False}
        ).sort("timestamp", -1).limit(limit)

        events = []
        async for data in cursor:
            events.append(VoiceAbuseEvent.from_dict(data))

        return events

    # ==================== USAGE SUMMARY OPERATIONS ====================

    async def get_user_usage_summary(
        self,
        user_id: str,
        session_id: str
    ) -> UserVoiceUsageSummary:
        """
        Get a complete usage summary for a user including all limits.

        Args:
            user_id: User identifier
            session_id: Current WebSocket session GUID

        Returns:
            UserVoiceUsageSummary with current usage and limits
        """
        # Get current date/month
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        year_month = datetime.utcnow().strftime("%Y-%m")

        # Get session usage
        session = await self.get_active_session(session_id)
        session_duration_ms = session.duration_ms if session else 0

        # Get daily usage
        daily = await self.get_or_create_daily(user_id, date_str)
        daily_duration_ms = daily.duration_ms

        # Get monthly usage
        monthly = await self.get_or_create_monthly(user_id, year_month)
        monthly_duration_ms = monthly.duration_ms

        # Convert limits to milliseconds
        session_limit_ms = VOICE_LIMIT_SESSION_MINUTES * 60 * 1000
        daily_limit_ms = VOICE_LIMIT_DAILY_MINUTES * 60 * 1000
        monthly_limit_ms = VOICE_LIMIT_MONTHLY_MINUTES * 60 * 1000

        summary = UserVoiceUsageSummary(
            user_id=user_id,
            session_duration_ms=session_duration_ms,
            daily_duration_ms=daily_duration_ms,
            monthly_duration_ms=monthly_duration_ms,
            session_limit_ms=session_limit_ms,
            daily_limit_ms=daily_limit_ms,
            monthly_limit_ms=monthly_limit_ms
        )

        # Check if any limit is exceeded
        summary.limit_reached = summary.check_limits()
        summary.voice_enabled = summary.limit_reached is None

        return summary

    async def get_recent_session_count(
        self,
        user_id: str,
        window_seconds: int = 300
    ) -> int:
        """
        Get count of sessions started in the recent time window.
        Used for rapid reconnection abuse detection.

        Args:
            user_id: User identifier
            window_seconds: Time window in seconds (default 5 minutes)

        Returns:
            Number of sessions in the window
        """
        since = datetime.utcnow() - timedelta(seconds=window_seconds)

        count = await self.voice_sessions.count_documents({
            "user_id": user_id,
            "started_at": {"$gte": since.isoformat()}
        })

        return count

    # ==================== CLEANUP OPERATIONS ====================

    async def cleanup_old_sessions(self, days: int = 30):
        """
        Clean up old ended sessions.

        Args:
            days: Delete sessions older than this many days
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        result = await self.voice_sessions.delete_many({
            "is_active": False,
            "ended_at": {"$lt": cutoff.isoformat()}
        })

        if result.deleted_count > 0:
            print(f"[VoiceUsage] Cleaned up {result.deleted_count} old sessions")


async def create_voice_usage_indexes(database: Database):
    """
    Create necessary indexes for voice usage collections.

    Args:
        database: Connected Database instance
    """
    try:
        # Voice sessions indexes
        sessions = database.get_collection("voice_usage_sessions")
        await sessions.create_index("session_id", unique=True)
        await sessions.create_index("user_id")
        await sessions.create_index([("user_id", 1), ("is_active", 1)])
        await sessions.create_index("started_at")

        # Daily usage indexes
        daily = database.get_collection("voice_usage_daily")
        await daily.create_index([("user_id", 1), ("date", 1)], unique=True)
        await daily.create_index("date")

        # Monthly usage indexes
        monthly = database.get_collection("voice_usage_monthly")
        await monthly.create_index([("user_id", 1), ("year_month", 1)], unique=True)
        await monthly.create_index("year_month")

        # Limit events indexes
        limit_events = database.get_collection("voice_limit_events")
        await limit_events.create_index("user_id")
        await limit_events.create_index("timestamp")
        await limit_events.create_index([("user_id", 1), ("timestamp", -1)])

        # Abuse events indexes
        abuse_events = database.get_collection("voice_abuse_events")
        await abuse_events.create_index("user_id")
        await abuse_events.create_index("reviewed")
        await abuse_events.create_index([("reviewed", 1), ("timestamp", -1)])

        print("[VoiceUsage] Database indexes created successfully")
    except Exception as e:
        print(f"[VoiceUsage] Warning: Index creation failed: {e}")
