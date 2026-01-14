from fastapi import APIRouter, Depends, HTTPException, Path, Query, UploadFile, File, Form
from .schemas import (
    ChatRequest, ChatResponse, ConversationHistory, SessionInfo,
    DeleteResponse, ErrorResponse
)
from .chat import generate_ai_reply, generate_streaming_ai_reply
from .mongodb_manager import mongodb_manager
from fastapi.responses import StreamingResponse
import json
import asyncio
from .vision_service import analyze_image_with_gpt4_vision
from .biometric_service import detect_stress
from datetime import datetime
from typing import List, Optional
from .config import (
    VOICE_USAGE_ENABLED,
    VOICE_LIMIT_SESSION_MINUTES,
    VOICE_LIMIT_DAILY_MINUTES,
    VOICE_LIMIT_MONTHLY_MINUTES
)

router = APIRouter(prefix="/api/v1")

# ==============================
# EXISTING CHATBOT APIS (UNCHANGED)
# ==============================

@router.post("/chat/simple", response_model=ChatResponse, tags=["Chat"])
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


@router.post("/chat", tags=["Chat"])
async def chat_stream(req: ChatRequest):
    async def event_generator():
        history = mongodb_manager.get_conversation_history(req.session_id, limit=10)

        # Save user message
        mongodb_manager.save_message(
            session_id=req.session_id,
            user_id=req.user_id,
            role="user",
            content=req.input_text,
            metadata={"language": req.language}
        )

        full_reply = ""
        # The generator from chat.py is synchronous, so we might want to wrap it or just use it
        # Since it's yields from OpenAI which is synchronous in this client
        # For better async performance, we could use asnyc client, but we'll stick to current pattern
        
        for chunk in generate_streaming_ai_reply(
            user_message=req.input_text,
            language=req.language,
            conversation_history=history
        ):
            full_reply += chunk
            yield f"data: {json.dumps({'reply': chunk,'session_id': req.session_id,'is_end': False})}\n\n"
            await asyncio.sleep(0) # Yield control

        # Save assistant message once complete
        ai_msg_id = mongodb_manager.save_message(
            session_id=req.session_id,
            user_id=req.user_id,
            role="assistant",
            content=full_reply,
            metadata={"language": req.language}
        )
        
        # Send final metadata
        yield f"data: {json.dumps({'message_id': ai_msg_id, 'session_id': req.session_id, 'is_end': True})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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


# ==============================
# VOICE USAGE APIs
# ==============================

@router.get("/voice-usage/{user_id}", tags=["Voice Usage"])
async def get_voice_usage(user_id: str):
    """
    Get current voice usage statistics for a user.

    Returns usage for current session (if any), today, and current month,
    along with remaining quota and limits.
    """
    if not VOICE_USAGE_ENABLED:
        return {
            "enabled": False,
            "message": "Voice usage tracking is disabled"
        }

    try:
        # Get daily usage
        today = datetime.utcnow().strftime("%Y-%m-%d")
        daily_doc = mongodb_manager.db["voice_usage_daily"].find_one({
            "user_id": user_id,
            "date": today
        })

        # Get monthly usage
        year_month = datetime.utcnow().strftime("%Y-%m")
        monthly_doc = mongodb_manager.db["voice_usage_monthly"].find_one({
            "user_id": user_id,
            "year_month": year_month
        })

        # Calculate limits in milliseconds
        session_limit_ms = VOICE_LIMIT_SESSION_MINUTES * 60 * 1000
        daily_limit_ms = VOICE_LIMIT_DAILY_MINUTES * 60 * 1000
        monthly_limit_ms = VOICE_LIMIT_MONTHLY_MINUTES * 60 * 1000

        # Get usage values
        daily_used_ms = daily_doc.get("duration_ms", 0) if daily_doc else 0
        monthly_used_ms = monthly_doc.get("duration_ms", 0) if monthly_doc else 0

        # Calculate remaining
        daily_remaining_ms = max(0, daily_limit_ms - daily_used_ms)
        monthly_remaining_ms = max(0, monthly_limit_ms - monthly_used_ms)

        return {
            "enabled": True,
            "user_id": user_id,
            "limits": {
                "session_minutes": VOICE_LIMIT_SESSION_MINUTES,
                "daily_minutes": VOICE_LIMIT_DAILY_MINUTES,
                "monthly_minutes": VOICE_LIMIT_MONTHLY_MINUTES
            },
            "daily": {
                "date": today,
                "used_ms": daily_used_ms,
                "used_minutes": round(daily_used_ms / 60000, 2),
                "remaining_ms": daily_remaining_ms,
                "remaining_minutes": round(daily_remaining_ms / 60000, 2),
                "limit_reached": daily_used_ms >= daily_limit_ms
            },
            "monthly": {
                "year_month": year_month,
                "used_ms": monthly_used_ms,
                "used_minutes": round(monthly_used_ms / 60000, 2),
                "remaining_ms": monthly_remaining_ms,
                "remaining_minutes": round(monthly_remaining_ms / 60000, 2),
                "limit_reached": monthly_used_ms >= monthly_limit_ms
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching voice usage: {str(e)}")


@router.get("/voice-usage/{user_id}/history", tags=["Voice Usage"])
async def get_voice_usage_history(
    user_id: str,
    days: int = Query(default=7, ge=1, le=30, description="Number of days of history to return")
):
    """
    Get voice usage history for a user.

    Returns daily usage for the specified number of past days.
    """
    if not VOICE_USAGE_ENABLED:
        return {
            "enabled": False,
            "message": "Voice usage tracking is disabled"
        }

    try:
        from datetime import timedelta

        # Get usage for past N days
        history = []
        for i in range(days):
            date = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
            daily_doc = mongodb_manager.db["voice_usage_daily"].find_one({
                "user_id": user_id,
                "date": date
            })

            if daily_doc:
                history.append({
                    "date": date,
                    "duration_ms": daily_doc.get("duration_ms", 0),
                    "duration_minutes": round(daily_doc.get("duration_ms", 0) / 60000, 2),
                    "session_count": daily_doc.get("session_count", 0),
                    "limit_reached_count": daily_doc.get("limit_reached_count", 0)
                })
            else:
                history.append({
                    "date": date,
                    "duration_ms": 0,
                    "duration_minutes": 0,
                    "session_count": 0,
                    "limit_reached_count": 0
                })

        return {
            "enabled": True,
            "user_id": user_id,
            "days": days,
            "history": history
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching voice usage history: {str(e)}")
