"""
Voice Usage Abuse Detection Module

Detects suspicious patterns in voice usage that may indicate abuse:
- Excessive continuous voice use
- Rapid reconnections to bypass limits
- Abnormally long sessions without breaks
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from lib_database.database import Database
from lib_database.voice_usage_repository import VoiceUsageRepository
from lib_database.voice_usage_models import AbuseEventType
from app.config import (
    VOICE_ABUSE_DETECTION_ENABLED,
    VOICE_ABUSE_CONTINUOUS_THRESHOLD_MINUTES,
    VOICE_ABUSE_RECONNECT_THRESHOLD,
    VOICE_ABUSE_RECONNECT_WINDOW_SECONDS
)


class VoiceAbuseDetector:
    """
    Detects and logs suspicious voice usage patterns.

    Abuse patterns detected:
    1. Excessive continuous use: Using voice for extended periods without breaks
    2. Rapid reconnection: Multiple reconnections in short window (limit bypass attempt)
    3. Long sessions without breaks: Sessions exceeding normal duration
    """

    def __init__(
        self,
        user_id: str,
        session_id: str,
        database: Database
    ):
        """
        Initialize the abuse detector.

        Args:
            user_id: User identifier
            session_id: Current session GUID
            database: Database instance
        """
        self.user_id = user_id
        self.session_id = session_id
        self.database = database
        self.repository = VoiceUsageRepository(database)

        # Thresholds
        self.continuous_threshold_ms = VOICE_ABUSE_CONTINUOUS_THRESHOLD_MINUTES * 60 * 1000
        self.reconnect_threshold = VOICE_ABUSE_RECONNECT_THRESHOLD
        self.reconnect_window = VOICE_ABUSE_RECONNECT_WINDOW_SECONDS

        # Tracking state
        self.session_start = datetime.utcnow()
        self.continuous_use_start: Optional[datetime] = None
        self.last_activity: Optional[datetime] = None
        self.total_continuous_ms = 0

        # Enabled flag
        self.enabled = VOICE_ABUSE_DETECTION_ENABLED

    async def check_on_connection(self) -> bool:
        """
        Check for abuse patterns when a new connection is established.

        Returns:
            True if no abuse detected, False if suspicious pattern found
        """
        if not self.enabled:
            return True

        try:
            # Check for rapid reconnection pattern
            recent_sessions = await self.repository.get_recent_session_count(
                self.user_id,
                self.reconnect_window
            )

            if recent_sessions >= self.reconnect_threshold:
                await self._record_abuse_event(
                    AbuseEventType.RAPID_RECONNECTION,
                    {
                        "session_count": recent_sessions,
                        "window_seconds": self.reconnect_window,
                        "threshold": self.reconnect_threshold,
                        "message": f"User started {recent_sessions} sessions in {self.reconnect_window}s window"
                    }
                )
                print(f"[AbuseDetector] RAPID_RECONNECTION detected for user {self.user_id[:8]}...")
                return False

            return True

        except Exception as e:
            print(f"[AbuseDetector] Error checking connection: {e}")
            return True  # Allow on error

    async def track_activity(self, duration_ms: int):
        """
        Track voice activity and check for continuous use patterns.

        Args:
            duration_ms: Duration of audio activity in milliseconds
        """
        if not self.enabled:
            return

        now = datetime.utcnow()

        # Check if this is continuous activity (within 5 seconds of last activity)
        if self.last_activity and (now - self.last_activity).total_seconds() < 5:
            # Continuous use - add to continuous counter
            self.total_continuous_ms += duration_ms

            # Check if continuous use exceeds threshold
            if self.total_continuous_ms >= self.continuous_threshold_ms:
                await self._record_abuse_event(
                    AbuseEventType.EXCESSIVE_CONTINUOUS_USE,
                    {
                        "continuous_duration_ms": self.total_continuous_ms,
                        "threshold_ms": self.continuous_threshold_ms,
                        "session_duration_seconds": (now - self.session_start).total_seconds(),
                        "message": f"Continuous voice use for {self.total_continuous_ms/60000:.1f} minutes"
                    }
                )
                print(f"[AbuseDetector] EXCESSIVE_CONTINUOUS_USE detected for user {self.user_id[:8]}...")
                # Reset to avoid repeated alerts
                self.total_continuous_ms = 0
        else:
            # Break in activity - reset continuous counter
            self.total_continuous_ms = duration_ms
            self.continuous_use_start = now

        self.last_activity = now

    async def check_session_end(self):
        """
        Check for abuse patterns when session ends.
        """
        if not self.enabled:
            return

        now = datetime.utcnow()
        session_duration = (now - self.session_start).total_seconds()

        # Check for abnormally long session (e.g., > 2 hours without breaks)
        long_session_threshold_hours = 2
        if session_duration > long_session_threshold_hours * 3600:
            # Get session details
            session = await self.repository.get_session(self.session_id)
            if session:
                # Calculate average activity rate
                if session.chunk_count > 0:
                    avg_activity_rate = session.duration_ms / session_duration / 1000  # ms per second

                    # If activity rate is high (>50% of time in voice), flag it
                    if avg_activity_rate > 0.5:
                        await self._record_abuse_event(
                            AbuseEventType.LONG_SESSION_NO_BREAKS,
                            {
                                "session_duration_seconds": session_duration,
                                "voice_duration_ms": session.duration_ms,
                                "activity_rate": avg_activity_rate,
                                "chunk_count": session.chunk_count,
                                "message": f"Session lasted {session_duration/3600:.1f} hours with {avg_activity_rate*100:.0f}% voice activity"
                            }
                        )
                        print(f"[AbuseDetector] LONG_SESSION_NO_BREAKS detected for user {self.user_id[:8]}...")

    async def _record_abuse_event(
        self,
        event_type: AbuseEventType,
        details: dict
    ):
        """
        Record an abuse event to the database.

        Args:
            event_type: Type of abuse detected
            details: Details about the event
        """
        try:
            await self.repository.record_abuse_event(
                user_id=self.user_id,
                session_id=self.session_id,
                event_type=event_type,
                details=details
            )
        except Exception as e:
            print(f"[AbuseDetector] Error recording event: {e}")


class AbuseDetectorIntegration:
    """
    Integration helper to add abuse detection to voice usage tracking.
    """

    def __init__(
        self,
        user_id: str,
        session_id: str,
        database: Database
    ):
        """
        Initialize the integration.

        Args:
            user_id: User identifier
            session_id: Current session GUID
            database: Database instance
        """
        self.detector = VoiceAbuseDetector(user_id, session_id, database)

    async def on_session_start(self):
        """Called when a new session starts."""
        return await self.detector.check_on_connection()

    async def on_audio_tracked(self, duration_ms: int):
        """Called when audio is tracked."""
        await self.detector.track_activity(duration_ms)

    async def on_session_end(self):
        """Called when session ends."""
        await self.detector.check_session_end()
