from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime


class PlaygroundParams(BaseModel):
    """Optional parameters for prompt experimentation playground mode."""

    temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0-2). Higher = more creative."
    )

    max_tokens: Optional[int] = Field(
        default=None,
        ge=1,
        le=128000,
        description="Maximum tokens in the response."
    )

    presence_penalty: Optional[float] = Field(
        default=None,
        ge=-2.0,
        le=2.0,
        description="Presence penalty (-2 to 2). Higher = less repetition."
    )

    frequency_penalty: Optional[float] = Field(
        default=None,
        ge=-2.0,
        le=2.0,
        description="Frequency penalty (-2 to 2). Higher = more variety."
    )

    reasoning_effort: Optional[Literal[
        "none", "minimal", "low", "medium", "high", "xhigh"
    ]] = Field(
        default=None,
        description="Reasoning effort level for GPT-5 family models."
    )


class ChatRequest(BaseModel):
    """Request model for sending a chat message to Chill Panda."""

    session_id: str = Field(
        ...,
        description="Unique session identifier (UUID format)",
        examples=["123e4567-e89b-12d3-a456-426614174000"]
    )

    user_id: str = Field(
        ...,
        description="Unique user identifier",
        examples=["user_abc123"]
    )

    input_text: str = Field(
        ...,
        description="The message text from the user",
        examples=["I'm feeling anxious today. Can you help me calm down?"]
    )

    language: str = Field(
        default="en",
        description=(
            "Language for the AI response. Supported values:\n"
            "- `en` — English (default)\n"
            "- `zh-HK` — Cantonese (Traditional Chinese, Hong Kong)\n"
            "- `zh-TW` — Mandarin (Traditional Chinese, Taiwan)"
        ),
        examples=["en", "zh-HK", "zh-TW"]
    )

    role: Literal[
        "best_friend",
        "caring_parent",
        "coach"
    ] = Field(
        default="best_friend",
        description="Emotional role used by Chill Panda to respond",
        examples=["best_friend"]
    )

    # --- Playground Mode Fields (Optional) ---
    custom_system_prompt: Optional[str] = Field(
        default=None,
        description="Custom system prompt to override the default. If None, uses the standard Chill Panda prompt."
    )

    model: Optional[str] = Field(
        default=None,
        description="Model ID to use (e.g., 'gpt-4.1-nano', 'gpt-4o'). If None, uses the default."
    )

    playground_params: Optional[PlaygroundParams] = Field(
        default=None,
        description="Custom model parameters for experimentation."
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "session_id": "123e4567-e89b-12d3-a456-426614174000",
                    "user_id": "user_abc123",
                    "input_text": "I'm feeling anxious today. Can you help me calm down?",
                    "language": "en",
                    "role": "best_friend"
                }
            ]
        }
    }



class ChatResponse(BaseModel):
    """Response model containing the AI's reply."""
    reply: str = Field(
        ...,
        description="The AI-generated response from Chill Panda",
        examples=["Hello friend! I sense you're feeling a bit anxious. Let's take a moment to breathe together..."]
    )
    session_id: str = Field(
        ...,
        description="The session ID this message belongs to",
        examples=["123e4567-e89b-12d3-a456-426614174000"]
    )
    message_id: Optional[str] = Field(
        default=None,
        description="MongoDB ObjectId of the saved message",
        examples=["65a1b2c3d4e5f6g7h8i9j0k1"]
    )
    used_rag: bool = Field(
        default=False,
        description="Whether RAG (Retrieval Augmented Generation) was used for the response"
    )
    is_critical: bool = Field(
        default=False,
        description="Whether the latest user message was classified as crisis/self-harm risk"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "reply": "Hello friend! I sense you're feeling a bit anxious. Let's practice the Turtle Breath together. Breathe in slowly for 4 counts, hold for 4, and exhale for 6. Remember, you are the Sky - thoughts are just passing clouds. 🐼",
                    "session_id": "123e4567-e89b-12d3-a456-426614174000",
                    "message_id": "65a1b2c3d4e5f6g7h8i9j0k1",
                    "used_rag": True,
                    "is_critical": False
                }
            ]
        }
    }


class Message(BaseModel):
    """A single message in the conversation history."""
    role: str = Field(
        ...,
        description="The role of the message sender (user or assistant)",
        examples=["user", "assistant"]
    )
    content: str = Field(
        ...,
        description="The text content of the message",
        examples=["How can I deal with stress better?"]
    )
    timestamp: datetime = Field(
        ...,
        description="When the message was created (UTC)"
    )


class SessionInfo(BaseModel):
    """Information about a user session."""
    session_id: str = Field(
        ...,
        description="Unique session identifier",
        examples=["123e4567-e89b-12d3-a456-426614174000"]
    )
    user_id: str = Field(
        ...,
        description="User who owns this session",
        examples=["user_abc123"]
    )
    created_at: datetime = Field(
        ...,
        description="When the session was created (UTC)"
    )
    last_activity: datetime = Field(
        ...,
        description="Last activity timestamp (UTC)"
    )
    message_count: int = Field(
        ...,
        description="Total number of messages in this session",
        examples=[42]
    )
    title: Optional[str] = Field(
        default=None,
        description="Session title derived from the last user message (up to 100 chars)",
        examples=["I've been feeling really anxious lately..."]
    )


class ConversationHistory(BaseModel):
    """Conversation history for a session."""
    session_id: str = Field(
        ...,
        description="The session ID for this conversation",
        examples=["123e4567-e89b-12d3-a456-426614174000"]
    )
    messages: List[Message] = Field(
        ...,
        description="List of messages in chronological order"
    )
    total_messages: int = Field(
        ...,
        description="Total number of messages retrieved",
        examples=[10]
    )


class DeleteResponse(BaseModel):
    """Response model for delete operations."""
    message: str = Field(
        ...,
        description="Status message",
        examples=["Session deleted successfully"]
    )


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str = Field(
        ...,
        description="Overall health status",
        examples=["healthy", "unhealthy"]
    )
    database: str = Field(
        ...,
        description="Database connection status",
        examples=["connected", "disconnected"]
    )
    service: str = Field(
        ...,
        description="Service name",
        examples=["Chill Panda API"]
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if unhealthy",
        examples=["Connection timeout"]
    )


class ErrorResponse(BaseModel):
    """Standard error response model."""
    detail: str = Field(
        ...,
        description="Error message describing what went wrong",
        examples=["Invalid API Key", "Session not found"]
    )
