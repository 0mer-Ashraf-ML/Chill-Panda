"""
Voice Usage Repository - CRUD operations for voice usage tracking
"""
from datetime import datetime
from typing import List, Optional
from lib_database.database import Database
from lib_database.voice_usage_model import VoiceUsage, VoiceSession


class VoiceUsageRepository:
    """
    Repository for managing voice usage records in MongoDB.
    Tracks daily and monthly voice usage per user.
    """
    
    def __init__(self, database: Database):
        """
        Initialize repository with database connection.
        
        Args:
            database: Connected Database instance
        """
        self.db = database
    
    @property
    def voice_usage_collection(self):
        """Get voice_usage collection from MongoDB."""
        return self.db.db["voice_usage"]
    
    @property
    def voice_sessions_collection(self):
        """Get voice_sessions collection from MongoDB."""
        return self.db.db["voice_sessions"]
    
    # ==================== DAILY USAGE OPERATIONS ====================
    
    async def get_or_create_daily_usage(
        self,
        user_id: str,
        date: Optional[str] = None
    ) -> VoiceUsage:
        """
        Get or create daily voice usage record for a user.
        
        Args:
            user_id: User identifier
            date: Date in YYYY-MM-DD format (defaults to today)
            
        Returns:
            VoiceUsage record for the day
        """
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")
        month = date[:7]  # Extract YYYY-MM
        
        # Try to find existing record
        existing = await self.voice_usage_collection.find_one({
            "user_id": user_id,
            "date": date
        })
        
        if existing:
            return VoiceUsage.from_dict(existing)
        
        # Create new record
        usage = VoiceUsage(
            user_id=user_id,
            date=date,
            month=month
        )
        
        await self.voice_usage_collection.insert_one(usage.to_dict())
        print(f"📊 Created voice usage record for user {user_id} on {date}")
        
        return usage
    
    async def add_voice_seconds(
        self,
        user_id: str,
        seconds: float,
        is_long_session: bool = False,
        date: Optional[str] = None
    ) -> VoiceUsage:
        """
        Add voice seconds to user's daily usage.
        
        Args:
            user_id: User identifier
            seconds: Seconds of voice to add
            is_long_session: Whether this qualifies as a long session
            date: Date in YYYY-MM-DD format (defaults to today)
            
        Returns:
            Updated VoiceUsage record
        """
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")
        
        # Ensure record exists
        await self.get_or_create_daily_usage(user_id, date)
        
        # Update with new seconds
        update_fields = {
            "voice_seconds_used": seconds,
            "session_count": 1
        }
        
        if is_long_session:
            update_fields["long_session_count"] = 1
        
        result = await self.voice_usage_collection.find_one_and_update(
            {"user_id": user_id, "date": date},
            {
                "$inc": update_fields,
                "$set": {"updated_at": datetime.utcnow().isoformat()}
            },
            return_document=True
        )
        
        return VoiceUsage.from_dict(result)
    
    async def get_daily_total(
        self,
        user_id: str,
        date: Optional[str] = None
    ) -> float:
        """
        Get total voice seconds used today.
        
        Args:
            user_id: User identifier
            date: Date in YYYY-MM-DD format (defaults to today)
            
        Returns:
            Total seconds used today
        """
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")
        
        usage = await self.voice_usage_collection.find_one({
            "user_id": user_id,
            "date": date
        })
        
        if usage:
            return usage.get("voice_seconds_used", 0.0)
        return 0.0
    
    async def get_monthly_total(
        self,
        user_id: str,
        month: Optional[str] = None
    ) -> float:
        """
        Get total voice seconds used this month.
        
        Args:
            user_id: User identifier
            month: Month in YYYY-MM format (defaults to current month)
            
        Returns:
            Total seconds used this month
        """
        if month is None:
            month = datetime.utcnow().strftime("%Y-%m")
        
        pipeline = [
            {"$match": {"user_id": user_id, "month": month}},
            {"$group": {
                "_id": None,
                "total_seconds": {"$sum": "$voice_seconds_used"}
            }}
        ]
        
        async for result in self.voice_usage_collection.aggregate(pipeline):
            return result.get("total_seconds", 0.0)
        
        return 0.0
    
    async def get_long_session_count(
        self,
        user_id: str,
        date: Optional[str] = None
    ) -> int:
        """
        Get count of long sessions for abuse detection.
        
        Args:
            user_id: User identifier
            date: Date in YYYY-MM-DD format (defaults to today)
            
        Returns:
            Count of long sessions today
        """
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")
        
        usage = await self.voice_usage_collection.find_one({
            "user_id": user_id,
            "date": date
        })
        
        if usage:
            return usage.get("long_session_count", 0)
        return 0
    
    # ==================== ABUSE TRACKING ====================
    
    async def add_abuse_flag(
        self,
        user_id: str,
        flag_type: str,
        date: Optional[str] = None
    ) -> None:
        """
        Add an abuse flag to user's daily record.
        
        Args:
            user_id: User identifier
            flag_type: Type of abuse detected (e.g., "continuous_usage", "session_spam")
            date: Date in YYYY-MM-DD format (defaults to today)
        """
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")
        
        # Ensure record exists
        await self.get_or_create_daily_usage(user_id, date)
        
        await self.voice_usage_collection.update_one(
            {"user_id": user_id, "date": date},
            {
                "$addToSet": {"abuse_flags": flag_type},
                "$set": {"updated_at": datetime.utcnow().isoformat()}
            }
        )
        
        print(f"⚠️ Added abuse flag '{flag_type}' for user {user_id}")
    
    async def get_abuse_flags(
        self,
        user_id: str,
        date: Optional[str] = None
    ) -> List[str]:
        """
        Get abuse flags for a user on a specific date.
        
        Args:
            user_id: User identifier
            date: Date in YYYY-MM-DD format (defaults to today)
            
        Returns:
            List of abuse flag types
        """
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")
        
        usage = await self.voice_usage_collection.find_one({
            "user_id": user_id,
            "date": date
        })
        
        if usage:
            return usage.get("abuse_flags", [])
        return []
    
    # ==================== SESSION TRACKING ====================
    
    async def create_voice_session(
        self,
        session_id: str,
        user_id: str
    ) -> VoiceSession:
        """
        Create a new voice session record.
        
        Args:
            session_id: WebSocket session GUID
            user_id: User identifier
            
        Returns:
            Created VoiceSession
        """
        session = VoiceSession(
            session_id=session_id,
            user_id=user_id
        )
        
        await self.voice_sessions_collection.insert_one(session.to_dict())
        return session
    
    async def update_voice_session(
        self,
        session_id: str,
        voice_seconds: float,
        speech_segments: int = 0,
        continuous_seconds: float = 0.0,
        is_voice_disabled: bool = False,
        limit_reached: Optional[str] = None,
        abuse_detected: bool = False,
        abuse_type: Optional[str] = None
    ) -> Optional[VoiceSession]:
        """
        Update a voice session with latest stats.
        
        Args:
            session_id: WebSocket session GUID
            voice_seconds: Total voice seconds in session
            speech_segments: Number of speech segments
            continuous_seconds: Longest continuous speech
            is_voice_disabled: Whether voice was disabled
            limit_reached: Which limit was reached
            abuse_detected: Whether abuse was detected
            abuse_type: Type of abuse detected
            
        Returns:
            Updated VoiceSession or None
        """
        update_data = {
            "voice_seconds_used": voice_seconds,
            "speech_segments": speech_segments,
            "continuous_seconds": continuous_seconds,
            "is_voice_disabled": is_voice_disabled
        }
        
        if limit_reached:
            update_data["limit_reached"] = limit_reached
        if abuse_detected:
            update_data["abuse_detected"] = abuse_detected
            update_data["abuse_type"] = abuse_type
        
        result = await self.voice_sessions_collection.find_one_and_update(
            {"session_id": session_id},
            {"$set": update_data},
            return_document=True
        )
        
        if result:
            return VoiceSession.from_dict(result)
        return None
    
    async def end_voice_session(self, session_id: str) -> None:
        """
        Mark a voice session as ended.
        
        Args:
            session_id: WebSocket session GUID
        """
        await self.voice_sessions_collection.update_one(
            {"session_id": session_id},
            {"$set": {"ended_at": datetime.utcnow().isoformat()}}
        )
    
    async def get_voice_session(self, session_id: str) -> Optional[VoiceSession]:
        """
        Get a voice session by ID.
        
        Args:
            session_id: WebSocket session GUID
            
        Returns:
            VoiceSession or None
        """
        result = await self.voice_sessions_collection.find_one({
            "session_id": session_id
        })
        
        if result:
            return VoiceSession.from_dict(result)
        return None
