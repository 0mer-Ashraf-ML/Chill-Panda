"""
Voice Usage Handler - Tracks voice usage and enforces limits
"""
import asyncio
import time
from datetime import datetime
from typing import Optional, Dict, Any

from lib_infrastructure.dispatcher import Dispatcher, MessageType, Message, MessageHeader
from lib_database.voice_usage_repository import VoiceUsageRepository


class VoiceUsageHandler:
    """
    Tracks voice usage by subscribing to SPEECH_DETECTED/SPEECH_ENDED events.
    Broadcasts VOICE_LIMIT_REACHED when limits are exceeded.
    """
    
    def __init__(
        self,
        guid: str,
        dispatcher: Dispatcher,
        repository: VoiceUsageRepository,
        user_id: str,
        config: Dict[str, Any]
    ):
        self.guid = guid
        self.dispatcher = dispatcher
        self.repository = repository
        self.user_id = user_id
        self.config = config
        
        # Session state
        self.session_voice_seconds = 0.0
        self.speech_start_time: Optional[float] = None
        self.is_speaking = False
        self.speech_segments = 0
        self.longest_continuous_seconds = 0.0
        
        # Enforcement state
        self.is_voice_disabled = False
        self.limit_reached_type: Optional[str] = None
        self.abuse_detected = False
        self.abuse_type: Optional[str] = None
        
        # Daily/Monthly totals (cached)
        self.daily_seconds = 0.0
        self.monthly_seconds = 0.0
        
        # Limits from config
        self.LIMIT_SESSION = config.get("session_limit", 30)
        self.LIMIT_DAY = config.get("daily_limit", 60)
        self.LIMIT_MONTH = config.get("monthly_limit", 600)
        self.ABUSE_CONTINUOUS = config.get("abuse_continuous_threshold", 300)
        self.ABUSE_SESSION_COUNT = config.get("abuse_session_count", 10)
        self.ABUSE_LONG_SESSION_THRESHOLD = config.get("abuse_long_session_threshold", 180)

    async def run_async(self):
        """Start tracking voice usage."""
        # Initialize usage stats from DB
        await self._load_initial_stats()
        
        # Create session record
        await self.repository.create_voice_session(self.guid, self.user_id)
        
        # Start listeners
        await asyncio.gather(
            self.handle_speech_detected(),
            self.handle_speech_ended(),
            self.monitor_continuous_speech()
        )

    async def _load_initial_stats(self):
        """Load daily and monthly totals from database."""
        self.daily_seconds = await self.repository.get_daily_total(self.user_id)
        self.monthly_seconds = await self.repository.get_monthly_total(self.user_id)
        
        # Check if already over limit (e.g., from previous sessions today)
        await self.check_limits()

    async def handle_speech_detected(self):
        """Handle SPEECH_DETECTED event."""
        async with await self.dispatcher.subscribe(
            self.guid, MessageType.SPEECH_DETECTED
        ) as subscriber:
            async for event in subscriber:
                if self.is_voice_disabled:
                    continue
                    
                self.is_speaking = True
                self.speech_start_time = time.time()
                # print(f"🎤 Speech started for {self.guid[:8]}")

    async def handle_speech_ended(self):
        """Handle SPEECH_ENDED event."""
        async with await self.dispatcher.subscribe(
            self.guid, MessageType.SPEECH_ENDED
        ) as subscriber:
            async for event in subscriber:
                if not self.is_speaking or not self.speech_start_time:
                    continue
                
                # Calculate duration
                end_time = time.time()
                duration = end_time - self.speech_start_time
                
                self.is_speaking = False
                self.speech_start_time = None
                self.speech_segments += 1
                
                # Update continuous max
                if duration > self.longest_continuous_seconds:
                    self.longest_continuous_seconds = duration
                
                # Update totals
                await self._add_usage(duration)
                
                # print(f"🎤 Speech ended. Duration: {duration:.2f}s. Total Session: {self.session_voice_seconds:.2f}s")

    async def monitor_continuous_speech(self):
        """Monitor for excessive continuous speech while speaking."""
        while True:
            if self.is_speaking and self.speech_start_time:
                current_duration = time.time() - self.speech_start_time
                
                # Check abuse threshold (continuous)
                if current_duration > self.ABUSE_CONTINUOUS and not self.abuse_detected:
                    await self._flag_abuse("continuous_usage", "Excessive continuous voice usage detected")
                
                # Check session limit in real-time
                if (self.session_voice_seconds + current_duration) > self.LIMIT_SESSION:
                    # Force end speech processing if possible, or just disable for future
                    await self._enforce_limit("session")
            
            await asyncio.sleep(1)  # Check every second

    async def _add_usage(self, seconds: float):
        """Add usage seconds and update DB/Check limits."""
        self.session_voice_seconds += seconds
        self.daily_seconds += seconds
        self.monthly_seconds += seconds
        
        is_long = seconds > self.ABUSE_LONG_SESSION_THRESHOLD
        
        # Update DB
        await self.repository.add_voice_seconds(self.user_id, seconds, is_long)
        await self.repository.update_voice_session(
            self.guid,
            self.session_voice_seconds,
            self.speech_segments,
            self.longest_continuous_seconds,
            self.is_voice_disabled
        )
        
        # Check if long session counts constitute abuse
        if is_long:
            count = await self.repository.get_long_session_count(self.user_id)
            if count >= self.ABUSE_SESSION_COUNT:
                await self._flag_abuse("session_spam", "Too many long voice sessions detected today")

        await self.check_limits()
        await self._broadcast_update()

    async def check_limits(self):
        """Check if any limits have been reached."""
        if self.is_voice_disabled:
            return

        limit_type = None
        
        if self.session_voice_seconds >= self.LIMIT_SESSION:
            limit_type = "session"
        elif self.daily_seconds >= self.LIMIT_DAY:
            limit_type = "daily"
        elif self.monthly_seconds >= self.LIMIT_MONTH:
            limit_type = "monthly"
            
        if limit_type:
            await self._enforce_limit(limit_type)

    async def _enforce_limit(self, limit_type: str):
        """Enforce a specific limit."""
        self.is_voice_disabled = True
        self.limit_reached_type = limit_type
        
        print(f"🛑 Voice limit reached: {limit_type} for user {self.user_id}")
        
        # Update session in DB
        await self.repository.update_voice_session(
            self.guid,
            self.session_voice_seconds,
            self.speech_segments,
            self.longest_continuous_seconds,
            self.is_voice_disabled,
            limit_reached=limit_type
        )
        
        # Get usage data
        usage_data = self._get_usage_data()
        usage_data["limit_type"] = limit_type
        
        # Broadcast limit reached event
        await self.dispatcher.broadcast(
            self.guid,
            Message(MessageHeader(MessageType.VOICE_LIMIT_REACHED), usage_data)
        )

    async def _flag_abuse(self, abuse_type: str, message: str):
        """Flag abuse and notify."""
        self.abuse_detected = True
        self.abuse_type = abuse_type
        
        print(f"⚠️ Abuse detected: {abuse_type} - {message}")
        
        # Record in DB
        await self.repository.add_abuse_flag(self.user_id, abuse_type)
        await self.repository.update_voice_session(
            self.guid,
            self.session_voice_seconds, 
            abuse_detected=True,
            abuse_type=abuse_type
        )
        
        # Broadcast abuse event
        abuse_data = {
            "abuse_type": abuse_type,
            "message": message
        }
        await self.dispatcher.broadcast(
            self.guid,
            Message(MessageHeader(MessageType.VOICE_ABUSE_DETECTED), abuse_data)
        )

    async def _broadcast_update(self):
        """Broadcast current usage stats."""
        usage_data = self._get_usage_data()
        
        await self.dispatcher.broadcast(
            self.guid,
            Message(MessageHeader(MessageType.VOICE_USAGE_UPDATE), usage_data)
        )

    def _get_usage_data(self) -> dict:
        """Construct usage data dictionary."""
        return {
            "session_seconds": round(self.session_voice_seconds, 1),
            "daily_seconds": round(self.daily_seconds, 1),
            "monthly_seconds": round(self.monthly_seconds, 1),
            "session_limit": self.LIMIT_SESSION,
            "daily_limit": self.LIMIT_DAY,
            "monthly_limit": self.LIMIT_MONTH,
            "session_remaining": max(0, self.LIMIT_SESSION - self.session_voice_seconds),
            "daily_remaining": max(0, self.LIMIT_DAY - self.daily_seconds),
            "monthly_remaining": max(0, self.LIMIT_MONTH - self.monthly_seconds),
            "is_voice_disabled": self.is_voice_disabled,
            "limit_reached": self.limit_reached_type,
            "upgrade_required": self.is_voice_disabled,  # Simple logic: if disabled -> upgrade needed
            "abuse_detected": self.abuse_detected,
            "abuse_type": self.abuse_type
        }
