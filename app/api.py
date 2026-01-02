from fastapi import APIRouter, HTTPException, Path, Query
from .schemas import (
    ChatRequest, ChatResponse, ConversationHistory, SessionInfo,
    DeleteResponse, ErrorResponse
)
from .chat import generate_ai_reply
from .mongodb_manager import mongodb_manager
from typing import List

router = APIRouter(prefix="/api/v1")


@router.post(
    "/chat",
    response_model=ChatResponse,
    tags=["Chat"],
    summary="Send a message to Chill Panda",
    description="""
Send a message to the Chill Panda AI and receive a mindful response.

The AI uses RAG (Retrieval Augmented Generation) to pull relevant wisdom from 
The Chill Panda book when applicable. Conversation history is automatically 
saved to MongoDB for session continuity.

**Features:**
- Contextual responses based on conversation history
- RAG-powered wisdom from The Chill Panda book
- Multi-language support (en, french, zh-HK, zh-TW)
- Automatic session and message persistence
    """,
    responses={
        200: {
            "description": "Successful response with AI reply",
            "model": ChatResponse
        },
        401: {
            "description": "Invalid or missing API key",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid API Key"}
                }
            }
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to generate response"}
                }
            }
        }
    }
)
async def chat(req: ChatRequest):
    """
    Send a chat message and receive an AI-powered response from Chill Panda.
    
    - **session_id**: UUID that groups messages together
    - **user_id**: Your unique user identifier
    - **input_text**: Your message to Chill Panda
    - **language**: Response language preference
    """
    # Get conversation history
    history = mongodb_manager.get_conversation_history(req.session_id, limit=10)
    
    # Generate AI reply with context
    ai_reply = generate_ai_reply(
        user_message=req.input_text,
        language=req.language,
        conversation_history=history
    )
    
    # Save user message
    user_msg_id = mongodb_manager.save_message(
        session_id=req.session_id,
        user_id=req.user_id,
        role="user",
        content=req.input_text,
        metadata={"language": req.language}
    )
    
    # Save AI reply
    ai_msg_id = mongodb_manager.save_message(
        session_id=req.session_id,
        user_id=req.user_id,
        role="assistant",
        content=ai_reply,
        metadata={"language": req.language}
    )
    
    return ChatResponse(
        reply=ai_reply,
        session_id=req.session_id,
        message_id=ai_msg_id
    )


@router.get(
    "/conversation/{session_id}",
    response_model=ConversationHistory,
    tags=["Sessions"],
    summary="Get conversation history",
    description="""
Retrieve the conversation history for a specific session.

Returns up to 50 messages in chronological order, including both user 
messages and AI responses with timestamps.
    """,
    responses={
        200: {
            "description": "Conversation history retrieved successfully",
            "model": ConversationHistory
        },
        401: {
            "description": "Invalid or missing API key",
            "model": ErrorResponse
        },
        404: {
            "description": "Session not found",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {"detail": "Session not found"}
                }
            }
        }
    }
)
async def get_conversation(
    session_id: str = Path(
        ...,
        description="The unique session identifier (UUID format)",
        examples=["123e4567-e89b-12d3-a456-426614174000"]
    )
):
    """
    Retrieve all messages from a conversation session.
    """
    messages = mongodb_manager.get_conversation_history(session_id, limit=50)
    
    return ConversationHistory(
        session_id=session_id,
        messages=messages,
        total_messages=len(messages)
    )


@router.get(
    "/sessions/{user_id}",
    response_model=List[SessionInfo],
    tags=["Sessions"],
    summary="Get user's sessions",
    description="""
Retrieve all chat sessions for a specific user.

Returns session metadata including creation time, last activity, 
and message count. Sessions are ordered by most recent activity.
    """,
    responses={
        200: {
            "description": "List of user sessions",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "session_id": "123e4567-e89b-12d3-a456-426614174000",
                            "user_id": "user_abc123",
                            "created_at": "2024-01-15T10:30:00Z",
                            "last_activity": "2024-01-15T11:45:00Z",
                            "message_count": 24
                        }
                    ]
                }
            }
        },
        401: {
            "description": "Invalid or missing API key",
            "model": ErrorResponse
        }
    }
)
async def get_user_sessions(
    user_id: str = Path(
        ...,
        description="The unique user identifier",
        examples=["user_abc123"]
    )
):
    """
    Get all chat sessions belonging to a user.
    """
    sessions = mongodb_manager.get_user_sessions(user_id)
    # Add user_id to each session to match SessionInfo schema
    for session in sessions:
        session["user_id"] = user_id
    return sessions


@router.delete(
    "/session/{session_id}",
    response_model=DeleteResponse,
    tags=["Sessions"],
    summary="Delete a session",
    description="""
Permanently delete a chat session and all its messages.

**⚠️ Warning:** This action cannot be undone. All messages in the session 
will be permanently deleted from the database.
    """,
    responses={
        200: {
            "description": "Session deleted successfully",
            "model": DeleteResponse,
            "content": {
                "application/json": {
                    "example": {"message": "Session deleted successfully"}
                }
            }
        },
        401: {
            "description": "Invalid or missing API key",
            "model": ErrorResponse
        },
        500: {
            "description": "Failed to delete session",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to delete session"}
                }
            }
        }
    }
)
async def delete_session(
    session_id: str = Path(
        ...,
        description="The session ID to delete",
        examples=["123e4567-e89b-12d3-a456-426614174000"]
    )
):
    """
    Delete a session and all its associated messages.
    """
    success = mongodb_manager.delete_session(session_id)
    if success:
        return DeleteResponse(message="Session deleted successfully")
    else:
        raise HTTPException(status_code=500, detail="Failed to delete session")