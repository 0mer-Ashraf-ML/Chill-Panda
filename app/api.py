from fastapi import APIRouter, Depends, HTTPException
from .auth import verify_key
from .schemas import ChatRequest, ChatResponse, ConversationHistory, SessionInfo
from .chat import generate_ai_reply
from .mongodb_manager import mongodb_manager
from typing import List

router = APIRouter(prefix="/api/v1")

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, _=Depends(verify_key)):
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

@router.get("/conversation/{session_id}", response_model=ConversationHistory)
async def get_conversation(session_id: str, _=Depends(verify_key)):
    messages = mongodb_manager.get_conversation_history(session_id, limit=50)
    
    return ConversationHistory(
        session_id=session_id,
        messages=messages,
        total_messages=len(messages)
    )

@router.get("/sessions/{user_id}", response_model=List[SessionInfo])
async def get_user_sessions(user_id: str, _=Depends(verify_key)):
    sessions = mongodb_manager.get_user_sessions(user_id)
    return sessions

@router.delete("/session/{session_id}")
async def delete_session(session_id: str, _=Depends(verify_key)):
    success = mongodb_manager.delete_session(session_id)
    if success:
        return {"message": "Session deleted successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete session")