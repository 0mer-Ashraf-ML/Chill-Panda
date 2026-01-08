from pydantic import BaseModel, Field
from enum import Enum


class invoke_llm_schema(BaseModel):
    """Schema for invoking LLM via WebSocket."""
    guid: str = Field(..., description="Unique session identifier (UUID)")
    user_msg: str = Field(..., description="User's message to send to the LLM")


class SourceEnum(str, Enum):
    """
    Connection source for WebSocket streaming.
    
    - **device**: Web browser or desktop application
    - **phone**: Mobile phone application
    """
    device = "device"
    phone = "phone"


class LanguageEnum(str, Enum):
    """
    Supported languages for conversation.
    
    - **en**: English
    - **french**: French
    - **zh-HK**: Traditional Chinese (Hong Kong)
    - **zh-TW**: Traditional Chinese (Taiwan)
    """
    french = "french"
    english = "en"
    zh_hk = "zh-HK"
    zh_tw = "zh-TW"


class RoleEnum(str, Enum):
    """
    Supported roles for the AI persona.
    """
    loyal_best_friend = "loyal_best_friend"
    caring_parent = "caring_parent"
    coach = "coach"
    funny_friend = "funny_friend"