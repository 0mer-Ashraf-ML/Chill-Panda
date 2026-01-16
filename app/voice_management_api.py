from fastapi import APIRouter, HTTPException, Depends
from typing import List
from .management_schemas import UserVoiceUsageSummaryResult, VoiceUsagePeriodDetails, ResetQuotaResponse
from lib_database.database import Database
from lib_database.voice_management_repository import VoiceManagementRepository
from datetime import datetime

management_router = APIRouter(prefix="/api/v1/voice/management", tags=["Voice Management"])

# We'll use a singleton pattern for the management repository
# Or we can initialize it in main.py. For now, we'll create a helper.
_database = Database()
_repo = VoiceManagementRepository(_database)

async def get_repo():
    if not _database.client:
        await _database.connect()
    return _repo

def format_summary(s) -> UserVoiceUsageSummaryResult:
    return UserVoiceUsageSummaryResult(
        user_id=s.user_id,
        voice_enabled=s.voice_enabled,
        limit_reached=s.limit_reached,
        session=VoiceUsagePeriodDetails(
            used_ms=s.session_duration_ms,
            limit_ms=s.session_limit_ms,
            remaining_ms=s.session_remaining_ms,
            used_minutes=round(s.session_duration_ms / 60000, 2),
            limit_minutes=round(s.session_limit_ms / 60000, 2)
        ),
        daily=VoiceUsagePeriodDetails(
            used_ms=s.daily_duration_ms,
            limit_ms=s.daily_limit_ms,
            remaining_ms=s.daily_remaining_ms,
            used_minutes=round(s.daily_duration_ms / 60000, 2),
            limit_minutes=round(s.daily_limit_ms / 60000, 2)
        ),
        monthly=VoiceUsagePeriodDetails(
            used_ms=s.monthly_duration_ms,
            limit_ms=s.monthly_limit_ms,
            remaining_ms=s.monthly_remaining_ms,
            used_minutes=round(s.monthly_duration_ms / 60000, 2),
            limit_minutes=round(s.monthly_limit_ms / 60000, 2)
        )
    )

@management_router.get("/all", response_model=List[UserVoiceUsageSummaryResult])
async def get_all_usage(repo: VoiceManagementRepository = Depends(get_repo)):
    """List voice usage summaries for all users."""
    summaries = await repo.get_all_summaries()
    return [format_summary(s) for s in summaries]

@management_router.get("/{user_id}", response_model=UserVoiceUsageSummaryResult)
async def get_user_usage(user_id: str, repo: VoiceManagementRepository = Depends(get_repo)):
    """Get detailed voice usage for a specific user."""
    summary = await repo.get_user_usage(user_id)
    return format_summary(summary)

@management_router.post("/{user_id}/reset", response_model=ResetQuotaResponse)
async def reset_user_quota(user_id: str, repo: VoiceManagementRepository = Depends(get_repo)):
    """Reset the voice usage quota for a specific user to zero."""
    success = await repo.reset_user_usage(user_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to reset user quota")
    
    return ResetQuotaResponse(
        success=True,
        message=f"Voice usage quota for user {user_id} has been reset successfully.",
        user_id=user_id,
        date_reset=datetime.utcnow()
    )
