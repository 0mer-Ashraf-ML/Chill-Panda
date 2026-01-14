"""
Voice Usage Tracker Service

Real-time tracking of TTS audio usage with session, daily, and monthly limits.
Integrates with the dispatcher system to intercept audio chunks and enforce limits.
"""

import asyncio
import base64
from datetime import datetime
from typing import Optional, Callable, Awaitable

from lib_infrastructure.dispatcher import (
    Dispatcher, Message, MessageHeader, MessageType
)
from lib_database.database import Database
from lib_database.voice_usage_repository import VoiceUsageRepository
from lib_database.voice_usage_models import (
    VoiceLimitType,
    UserVoiceUsageSummary
)
from app.config import (
    VOICE_USAGE_ENABLED,
    VOICE_ABUSE_DETECTION_ENABLED,
    VOICE_LIMIT_SESSION_MINUTES,
    VOICE_LIMIT_DAILY_MINUTES,
    VOICE_LIMIT_MONTHLY_MINUTES,
    AUDIO_BYTES_PER_MS
)


class VoiceUsageTracker:
    """
    Tracks voice usage for a WebSocket session and enforces limits.

    This service:
    1. Intercepts audio chunks before they're sent to the client
    2. Calculates audio duration from chunk size
    3. Updates session/daily/monthly usage in database
    4. Stops TTS and notifies client when limits are reached
    """

    def __init__(
        self,
        guid: str,
        user_id: str,
        dispatcher: Dispatcher,
        database: Database
    ):
        """
        Initialize the voice usage tracker.

        Args:
            guid: WebSocket session GUID
            user_id: User identifier
            dispatcher: Dispatcher instance for event handling
            database: Database instance for persistence
        """
        self.guid = guid
        self.user_id = user_id
        self.dispatcher = dispatcher
        self.database = database
        self.repository = VoiceUsageRepository(database)

        # State tracking
        self.voice_enabled = True
        self.limit_reached: Optional[VoiceLimitType] = None
        self.session_duration_ms = 0
        self.daily_duration_ms = 0
        self.monthly_duration_ms = 0

        # Limits in milliseconds
        self.session_limit_ms = VOICE_LIMIT_SESSION_MINUTES * 60 * 1000
        self.daily_limit_ms = VOICE_LIMIT_DAILY_MINUTES * 60 * 1000
        self.monthly_limit_ms = VOICE_LIMIT_MONTHLY_MINUTES * 60 * 1000

        # Warning thresholds (80% of limit)
        self.session_warning_ms = int(self.session_limit_ms * 0.8)
        self.daily_warning_ms = int(self.daily_limit_ms * 0.8)
        self.monthly_warning_ms = int(self.monthly_limit_ms * 0.8)

        # Warning flags (to avoid repeated warnings)
        self._session_warning_sent = False
        self._daily_warning_sent = False
        self._monthly_warning_sent = False

        # Lock for thread-safe updates
        self._lock = asyncio.Lock()

        # Enabled flag
        self.enabled = VOICE_USAGE_ENABLED

        # Abuse detection (lazy loaded)
        self._abuse_detector = None
        self._abuse_detection_enabled = VOICE_ABUSE_DETECTION_ENABLED

    async def initialize(self) -> UserVoiceUsageSummary:
        """
        Initialize the tracker by loading current usage from database.
        Creates session record and loads daily/monthly usage.

        Returns:
            UserVoiceUsageSummary with current state
        """
        if not self.enabled:
            return self._create_unlimited_summary()

        try:
            # Initialize abuse detector if enabled
            if self._abuse_detection_enabled:
                from lib_voice_usage.abuse_detector import VoiceAbuseDetector
                self._abuse_detector = VoiceAbuseDetector(
                    self.user_id,
                    self.guid,
                    self.database
                )
                # Check for abuse patterns on connection
                await self._abuse_detector.check_on_connection()

            # Create session record
            await self.repository.create_session(self.guid, self.user_id)

            # Increment session counts
            await self.repository.increment_daily_session_count(self.user_id)
            await self.repository.increment_monthly_session_count(self.user_id)

            # Load current usage
            summary = await self.repository.get_user_usage_summary(
                self.user_id,
                self.guid
            )

            # Update local state
            self.session_duration_ms = summary.session_duration_ms
            self.daily_duration_ms = summary.daily_duration_ms
            self.monthly_duration_ms = summary.monthly_duration_ms
            self.voice_enabled = summary.voice_enabled
            self.limit_reached = summary.limit_reached

            print(f"[VoiceUsage] Initialized for user {self.user_id[:8]}... - "
                  f"Session: {self.session_duration_ms/60000:.2f}min, "
                  f"Daily: {self.daily_duration_ms/60000:.2f}min, "
                  f"Monthly: {self.monthly_duration_ms/60000:.2f}min")

            # Check if already at limit
            if self.limit_reached:
                await self._handle_limit_reached(self.limit_reached)

            return summary

        except Exception as e:
            print(f"[VoiceUsage] Error initializing: {e}")
            # On error, allow voice to prevent breaking the session
            return self._create_unlimited_summary()

    async def track_audio_chunk(self, audio_data: str) -> bool:
        """
        Track an audio chunk being sent to the client.

        Args:
            audio_data: Base64 encoded audio data

        Returns:
            True if audio should be sent, False if limit reached
        """
        if not self.enabled:
            return True

        if not self.voice_enabled:
            return False

        try:
            # Decode base64 to get actual byte count
            audio_bytes = base64.b64decode(audio_data)
            bytes_count = len(audio_bytes)

            # Calculate duration in milliseconds
            # For 16kHz, 16-bit mono PCM: 32 bytes = 1ms
            duration_ms = bytes_count // AUDIO_BYTES_PER_MS if AUDIO_BYTES_PER_MS > 0 else bytes_count // 32

            return await self._add_usage(duration_ms)

        except Exception as e:
            print(f"[VoiceUsage] Error tracking chunk: {e}")
            # On error, allow the audio through
            return True

    async def _add_usage(self, duration_ms: int) -> bool:
        """
        Add usage duration and check limits.

        Args:
            duration_ms: Duration to add in milliseconds

        Returns:
            True if within limits, False if limit reached
        """
        async with self._lock:
            # Update local counters
            self.session_duration_ms += duration_ms
            self.daily_duration_ms += duration_ms
            self.monthly_duration_ms += duration_ms

            # Check for warnings first
            await self._check_warnings()

            # Check limits
            limit_type = self._check_limits()

            if limit_type:
                self.voice_enabled = False
                self.limit_reached = limit_type
                await self._handle_limit_reached(limit_type)
                return False

            # Update database (async, non-blocking)
            asyncio.create_task(self._update_database(duration_ms))

            # Track activity for abuse detection (async, non-blocking)
            if self._abuse_detector:
                asyncio.create_task(self._abuse_detector.track_activity(duration_ms))

            return True

    def _check_limits(self) -> Optional[VoiceLimitType]:
        """
        Check if any limit has been exceeded.

        Returns:
            VoiceLimitType if exceeded, None otherwise
        """
        if self.session_duration_ms >= self.session_limit_ms:
            return VoiceLimitType.SESSION
        if self.daily_duration_ms >= self.daily_limit_ms:
            return VoiceLimitType.DAILY
        if self.monthly_duration_ms >= self.monthly_limit_ms:
            return VoiceLimitType.MONTHLY
        return None

    async def _check_warnings(self):
        """Check and send warnings when approaching limits."""
        if not self._session_warning_sent and self.session_duration_ms >= self.session_warning_ms:
            self._session_warning_sent = True
            await self._send_warning("session", self.session_limit_ms, self.session_duration_ms)

        if not self._daily_warning_sent and self.daily_duration_ms >= self.daily_warning_ms:
            self._daily_warning_sent = True
            await self._send_warning("daily", self.daily_limit_ms, self.daily_duration_ms)

        if not self._monthly_warning_sent and self.monthly_duration_ms >= self.monthly_warning_ms:
            self._monthly_warning_sent = True
            await self._send_warning("monthly", self.monthly_limit_ms, self.monthly_duration_ms)

    async def _send_warning(self, limit_type: str, limit_ms: int, usage_ms: int):
        """Send a warning that a limit is being approached."""
        remaining_ms = limit_ms - usage_ms
        remaining_minutes = remaining_ms / 60000

        warning_data = {
            "limit_type": limit_type,
            "limit_minutes": limit_ms / 60000,
            "used_minutes": usage_ms / 60000,
            "remaining_minutes": remaining_minutes,
            "message": f"You have approximately {remaining_minutes:.1f} minutes of voice time remaining for this {limit_type} limit."
        }

        await self.dispatcher.broadcast(
            self.guid,
            Message(
                MessageHeader(MessageType.VOICE_USAGE_WARNING),
                data=warning_data
            )
        )

        print(f"[VoiceUsage] Warning sent - {limit_type}: {remaining_minutes:.1f} min remaining")

    async def _handle_limit_reached(self, limit_type: VoiceLimitType):
        """
        Handle when a limit is reached.

        Args:
            limit_type: Type of limit that was reached
        """
        # Get limit value for the type
        limit_minutes = {
            VoiceLimitType.SESSION: VOICE_LIMIT_SESSION_MINUTES,
            VoiceLimitType.DAILY: VOICE_LIMIT_DAILY_MINUTES,
            VoiceLimitType.MONTHLY: VOICE_LIMIT_MONTHLY_MINUTES
        }.get(limit_type, 0)

        usage_minutes = {
            VoiceLimitType.SESSION: self.session_duration_ms / 60000,
            VoiceLimitType.DAILY: self.daily_duration_ms / 60000,
            VoiceLimitType.MONTHLY: self.monthly_duration_ms / 60000
        }.get(limit_type, 0)

        # Create limit reached message for client
        limit_data = {
            "limit_type": limit_type.value,
            "limit_minutes": limit_minutes,
            "used_minutes": usage_minutes,
            "message": self._get_limit_message(limit_type, limit_minutes),
            "voice_disabled": True
        }

        # Broadcast limit reached event
        await self.dispatcher.broadcast(
            self.guid,
            Message(
                MessageHeader(MessageType.VOICE_LIMIT_REACHED),
                data=limit_data
            )
        )

        # Broadcast voice disabled event
        await self.dispatcher.broadcast(
            self.guid,
            Message(
                MessageHeader(MessageType.VOICE_DISABLED),
                data={"reason": f"{limit_type.value}_limit_reached"}
            )
        )

        # Record in database
        asyncio.create_task(self._record_limit_reached(limit_type, limit_minutes, usage_minutes))

        print(f"[VoiceUsage] LIMIT REACHED - User: {self.user_id}, Type: {limit_type.value}, "
              f"Limit: {limit_minutes}min, Usage: {usage_minutes:.2f}min")

    def _get_limit_message(self, limit_type: VoiceLimitType, limit_minutes: float) -> str:
        """Generate a user-friendly limit message."""
        messages = {
            VoiceLimitType.SESSION: f"You've reached your session voice limit of {limit_minutes} minutes. Voice responses are now disabled, but text chat continues to work.",
            VoiceLimitType.DAILY: f"You've reached your daily voice limit of {limit_minutes} minutes. Voice will be available again tomorrow. Text chat continues to work.",
            VoiceLimitType.MONTHLY: f"You've reached your monthly voice limit of {limit_minutes} minutes. Voice will be available next month. Text chat continues to work."
        }
        return messages.get(limit_type, "Voice limit reached. Text chat continues to work.")

    async def _update_database(self, duration_ms: int):
        """Update database with new usage (async background task)."""
        try:
            # Update session
            await self.repository.update_session_usage(
                self.guid,
                duration_ms_increment=duration_ms,
                chunk_count_increment=1
            )

            # Update daily
            await self.repository.update_daily_usage(
                self.user_id,
                duration_ms_increment=duration_ms
            )

            # Update monthly
            await self.repository.update_monthly_usage(
                self.user_id,
                duration_ms_increment=duration_ms
            )

        except Exception as e:
            print(f"[VoiceUsage] Error updating database: {e}")

    async def _record_limit_reached(
        self,
        limit_type: VoiceLimitType,
        limit_minutes: float,
        usage_minutes: float
    ):
        """Record limit reached event in database."""
        try:
            # Record limit event
            await self.repository.record_limit_event(
                self.user_id,
                self.guid,
                limit_type,
                limit_minutes,
                usage_minutes
            )

            # Mark session as limit reached
            await self.repository.mark_session_limit_reached(
                self.guid,
                limit_type
            )

            # Increment daily limit reached count
            await self.repository.increment_daily_limit_reached(self.user_id)

        except Exception as e:
            print(f"[VoiceUsage] Error recording limit: {e}")

    async def end_session(self):
        """End the tracking session and finalize records."""
        if not self.enabled:
            return

        try:
            # Check for abuse patterns at session end
            if self._abuse_detector:
                await self._abuse_detector.check_session_end()

            await self.repository.end_session(self.guid)
            print(f"[VoiceUsage] Session ended - User: {self.user_id}, "
                  f"Total: {self.session_duration_ms/60000:.2f}min")
        except Exception as e:
            print(f"[VoiceUsage] Error ending session: {e}")

    def is_voice_enabled(self) -> bool:
        """Check if voice is currently enabled."""
        return self.enabled and self.voice_enabled

    def get_remaining_ms(self) -> int:
        """Get minimum remaining time across all limits."""
        if not self.enabled:
            return float('inf')

        session_remaining = max(0, self.session_limit_ms - self.session_duration_ms)
        daily_remaining = max(0, self.daily_limit_ms - self.daily_duration_ms)
        monthly_remaining = max(0, self.monthly_limit_ms - self.monthly_duration_ms)

        return min(session_remaining, daily_remaining, monthly_remaining)

    def get_usage_summary(self) -> dict:
        """Get current usage summary."""
        return {
            "user_id": self.user_id,
            "session_id": self.guid,
            "voice_enabled": self.voice_enabled,
            "limit_reached": self.limit_reached.value if self.limit_reached else None,
            "session": {
                "used_ms": self.session_duration_ms,
                "limit_ms": self.session_limit_ms,
                "remaining_ms": max(0, self.session_limit_ms - self.session_duration_ms)
            },
            "daily": {
                "used_ms": self.daily_duration_ms,
                "limit_ms": self.daily_limit_ms,
                "remaining_ms": max(0, self.daily_limit_ms - self.daily_duration_ms)
            },
            "monthly": {
                "used_ms": self.monthly_duration_ms,
                "limit_ms": self.monthly_limit_ms,
                "remaining_ms": max(0, self.monthly_limit_ms - self.monthly_duration_ms)
            }
        }

    def _create_unlimited_summary(self) -> UserVoiceUsageSummary:
        """Create a summary that indicates unlimited usage (when tracking disabled)."""
        return UserVoiceUsageSummary(
            user_id=self.user_id,
            session_duration_ms=0,
            daily_duration_ms=0,
            monthly_duration_ms=0,
            session_limit_ms=float('inf'),
            daily_limit_ms=float('inf'),
            monthly_limit_ms=float('inf'),
            voice_enabled=True,
            limit_reached=None
        )


class VoiceUsageInterceptor:
    """
    Intercepts CALL_WEBSOCKET_PUT events to track audio usage.
    This class subscribes to audio events and tracks usage before forwarding.
    """

    def __init__(
        self,
        guid: str,
        tracker: VoiceUsageTracker,
        dispatcher: Dispatcher
    ):
        """
        Initialize the interceptor.

        Args:
            guid: WebSocket session GUID
            tracker: VoiceUsageTracker instance
            dispatcher: Dispatcher instance
        """
        self.guid = guid
        self.tracker = tracker
        self.dispatcher = dispatcher

    async def run_async(self):
        """
        Run the interceptor, listening for audio tracking events.
        """
        print(f"[VoiceUsage] Interceptor started for session {self.guid[:8]}...")

        try:
            async with await self.dispatcher.subscribe(
                self.guid,
                MessageType.VOICE_AUDIO_TRACKED
            ) as subscriber:
                async for event in subscriber:
                    audio_data = event.message.data.get("audio")
                    if audio_data:
                        # Track the audio chunk
                        allowed = await self.tracker.track_audio_chunk(audio_data)

                        if not allowed:
                            # Voice was disabled, no further action needed
                            # The limit reached event has already been broadcast
                            pass

        except asyncio.CancelledError:
            print(f"[VoiceUsage] Interceptor cancelled for session {self.guid[:8]}...")
        except Exception as e:
            print(f"[VoiceUsage] Interceptor error: {e}")
        finally:
            await self.tracker.end_session()
            print(f"[VoiceUsage] Interceptor stopped for session {self.guid[:8]}...")
