from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class ChatRequest(BaseModel):
    session_id: str
    user_id: str
    input_text: str
    language: str = "en"

class ChatResponse(BaseModel):
    reply: str
    session_id: str
    message_id: Optional[str] = None
    used_rag: bool = False

class Message(BaseModel):
    role: str
    content: str
    timestamp: datetime

class SessionInfo(BaseModel):
    session_id: str
    user_id: str
    created_at: datetime
    last_activity: datetime
    message_count: int

class ConversationHistory(BaseModel):
    session_id: str
    messages: List[Message]
    total_messages: int