from datetime import datetime
from typing import List, Optional
from lib_database.database import Database
from lib_database.voice_usage_repository import VoiceUsageRepository
from lib_database.voice_usage_models import UserVoiceUsageSummary, VoiceLimitType

class VoiceManagementRepository:
    """
    Repository for administrative management of voice usage.
    """
    def __init__(self, database: Database):
        self.db = database
        self.usage_repo = VoiceUsageRepository(database)

    async def get_all_user_ids(self) -> List[str]:
        """Get all unique user IDs that have voice usage records."""
        # Check daily and monthly collections for all user IDs
        daily_users = await self.db.get_collection("voice_usage_daily").distinct("user_id")
        monthly_users = await self.db.get_collection("voice_usage_monthly").distinct("user_id")
        
        # Combine and remove duplicates
        return list(set(daily_users + monthly_users))

    async def get_user_usage(self, user_id: str) -> UserVoiceUsageSummary:
        """Get usage summary for a specific user (session is omitted as this is an admin view)."""
        # We'll use a dummy session_id since we just want the daily/monthly totals
        # The internal get_user_usage_summary handles session_id if provided
        return await self.usage_repo.get_user_usage_summary(user_id, session_id="admin_query")

    async def get_all_summaries(self) -> List[UserVoiceUsageSummary]:
        """Get usage summaries for all users."""
        user_ids = await self.get_all_user_ids()
        summaries = []
        for uid in user_ids:
            summary = await self.get_user_usage(uid)
            summaries.append(summary)
        return summaries

    async def reset_user_usage(self, user_id: str) -> bool:
        """Reset current daily and monthly usage for a user to zero."""
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        year_month = datetime.utcnow().strftime("%Y-%m")

        # Reset daily
        await self.db.get_collection("voice_usage_daily").update_one(
            {"user_id": user_id, "date": date_str},
            {"$set": {
                "duration_ms": 0,
                "chunk_count": 0,
                "updated_at": datetime.utcnow().isoformat()
            }}
        )

        # Reset monthly
        await self.db.get_collection("voice_usage_monthly").update_one(
            {"user_id": user_id, "year_month": year_month},
            {"$set": {
                "duration_ms": 0,
                "updated_at": datetime.utcnow().isoformat()
            }}
        )

        # Note: We don't reset active sessions here to avoid complicating the real-time tracker,
        # but the user will immediately have new quota for the next audio chunk/session.
        
        print(f"[VoiceManagement] Reset usage for user: {user_id}")
        return True
