from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class VoiceUsagePeriodDetails(BaseModel):
    """Detailed information about a specific usage period (session, daily, monthly)."""
    used_ms: int = Field(..., description="Used duration in milliseconds")
    limit_ms: int = Field(..., description="Limit duration in milliseconds")
    remaining_ms: int = Field(..., description="Remaining duration in milliseconds")
    used_minutes: float = Field(..., description="Used duration in minutes")
    limit_minutes: float = Field(..., description="Limit duration in minutes")

class UserVoiceUsageSummaryResult(BaseModel):
    """Result model for a user's voice usage summary."""
    user_id: str = Field(..., description="User identifier")
    voice_enabled: bool = Field(..., description="Whether voice is currently enabled for the user")
    limit_reached: Optional[str] = Field(None, description="Type of limit reached, if any")
    session: VoiceUsagePeriodDetails
    daily: VoiceUsagePeriodDetails
    monthly: VoiceUsagePeriodDetails

class ResetQuotaResponse(BaseModel):
    """Response model for quota reset operation."""
    success: bool = Field(..., description="Whether the reset was successful")
    message: str = Field(..., description="Status message")
    user_id: str = Field(..., description="The user whose quota was reset")
    date_reset: datetime = Field(..., description="Timestamp of the reset")
