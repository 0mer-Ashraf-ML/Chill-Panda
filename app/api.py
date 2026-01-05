from fastapi import APIRouter, Depends, HTTPException, Path, Query, UploadFile, File, Form
from .schemas import (
    ChatRequest, ChatResponse, ConversationHistory, SessionInfo,
    DeleteResponse, ErrorResponse
)
from .chat import generate_ai_reply
from .mongodb_manager import mongodb_manager
from .vision_service import analyze_image_with_gpt4_vision
from .biometric_service import detect_stress
from datetime import datetime
from typing import List

router = APIRouter(prefix="/api/v1")

# ==============================
# EXISTING CHATBOT APIS (UNCHANGED)
# ==============================

@router.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(req: ChatRequest):
    history = mongodb_manager.get_conversation_history(req.session_id, limit=10)

    ai_reply = generate_ai_reply(
        user_message=req.input_text,
        language=req.language,
        conversation_history=history
    )

    mongodb_manager.save_message(
        session_id=req.session_id,
        user_id=req.user_id,
        role="user",
        content=req.input_text,
        metadata={"language": req.language}
    )

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


@router.get("/conversation/{session_id}", response_model=ConversationHistory, tags=["Sessions"])
async def get_conversation(session_id: str):
    messages = mongodb_manager.get_conversation_history(session_id, limit=50)
    return ConversationHistory(
        session_id=session_id,
        messages=messages,
        total_messages=len(messages)
    )


@router.get("/sessions/{user_id}", response_model=List[SessionInfo], tags=["Sessions"])
async def get_user_sessions(user_id: str):
    return mongodb_manager.get_user_sessions(user_id)


@router.delete("/session/{session_id}", response_model=DeleteResponse, tags=["Sessions"])
async def delete_session(session_id: str):
    success = mongodb_manager.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete session")
    return DeleteResponse(message="Session deleted successfully")


# ==============================
# NEW PHASE 2 APIs (APPENDED)
# ==============================

@router.post("/vision/analyze", tags=["Vision"])
async def analyze_vision(
    user_id: str = Form(...),
    session_id: str = Form(...),
    image: UploadFile = File(...)
):
    if image.content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(status_code=400, detail="Invalid image format")

    image_bytes = await image.read()
    vision_result = await analyze_image_with_gpt4_vision(image_bytes, user_id)

    record = {
        "session_id": session_id,
        "user_id": user_id,
        "type": "vision",
        "data": vision_result,
        "timestamp": datetime.utcnow()
    }

    mongodb_manager.db["emotion_events"].insert_one(record)

    return {
        "status": "success",
        "source": "vision",
        "data": vision_result
    }


@router.post("/biometric/ingest", tags=["Biometric"])
async def ingest_biometrics(
    user_id: str = Form(...),
    session_id: str = Form(...),
    heart_rate: int = Form(...),
    hrv: float = Form(...)
):
    stressed, recommendations = await detect_stress({
        "user_id": user_id,
        "heart_rate": heart_rate,
        "hrv": hrv
    })

    record = {
        "session_id": session_id,
        "user_id": user_id,
        "type": "biometric",
        "heart_rate": heart_rate,
        "hrv": hrv,
        "stress_event": stressed,
        "recommendations": recommendations,
        "timestamp": datetime.utcnow()
    }

    mongodb_manager.db["biometrics"].insert_one(record)

    return {
        "status": "success",
        "stress_event": stressed,
        "recommendations": recommendations,
        "source": "biometric"
    }
