# external imports
import os , uuid , asyncio , logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
from dotenv import load_dotenv
from api_request_schemas import (SourceEnum , LanguageEnum, RoleEnum, GenderEnum)
from fastapi import FastAPI, WebSocket , Request, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
# internal imports
from lib_socket_handler.web_socket_manager import WebsocketManager
from lib_stt.speech_to_text_deepgram import SpeechToTextDeepgram
from lib_llm.helpers.llm import LLM
from lib_llm.helpers.prompt_generator import PromptGenerator
from lib_llm.large_language_model import LargeLanguageModel
from lib_tts.text_to_speech_deepgram import TextToSpeechDeepgram
from lib_tts.text_to_speech_elevenlabs import TextToSpeechElevenLabs
from lib_tts.text_to_speech_minimax import TextToSpeechMinimax
from lib_infrastructure.dispatcher import ( Dispatcher , Message , MessageHeader , MessageType )
from lib_infrastructure.helpers.global_event_logger import GlobalLoggerAsync
from lib_infrastructure.helpers.realtime_observability import SessionObserver
from contextlib import asynccontextmanager
from app.api import router
from app.mongodb_manager import mongodb_manager
from app.voice_management_api import management_router
# Voice usage tracking imports
from lib_database.database import Database
from lib_voice_usage.voice_usage_tracker import VoiceUsageTracker, VoiceUsageInterceptor
from lib_database.voice_usage_repository import create_voice_usage_indexes
from app.config import VOICE_USAGE_ENABLED, CORS_ORIGINS

# loading .env configs
load_dotenv()
PORT = int(os.getenv("PORT"))
OUTPUT_MP3_FILES = "output.mp3"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Conneting to memory://")
    await dispatcher.connect()
    print("Connected to memory://")

    # Initialize voice usage database connection
    if VOICE_USAGE_ENABLED:
        print("Connecting to MongoDB for voice usage tracking...")
        await voice_usage_database.connect()
        await create_voice_usage_indexes(voice_usage_database)
        print("Voice usage database connected")

    yield

    # Shutdown
    print("Disconnecting from memory://")
    await dispatcher.disconnect()
    print("Disconnected from memory://")

    # Disconnect voice usage database
    if VOICE_USAGE_ENABLED:
        await voice_usage_database.disconnect()


# OpenAPI Tags metadata for grouping endpoints
tags_metadata = [
    {
        "name": "Chat",
        "description": "AI-powered chat operations with Chill Panda. Send messages and receive mindful responses.",
    },
    {
        "name": "Sessions",
        "description": "Manage user sessions and conversation history.",
    },
    {
        "name": "Health",
        "description": "System health and status endpoints.",
    },
    {
        "name": "WebSocket",
        "description": "Real-time WebSocket connections for voice and text streaming.",
    },
]

# app initalization & setup
app = FastAPI(
    title="Chill Panda API",
    description="""
🐼 **Chill Panda Backend API**

A mindful AI companion for mental wellness, featuring:
- **RAG-powered chat** with wisdom from The Chill Panda book
- **Real-time voice/text streaming** via WebSocket
- **Session management** for conversation history
- **MongoDB integration** for persistent storage

## Authentication
Most endpoints require an API key passed in the `X-API-Key` header.

## Language Support
All chat and voice endpoints support the following languages via the `language` parameter:
| Code | Language |
|------|----------|
| `en` | English (default) |
| `zh-HK` | Cantonese (Traditional Chinese, Hong Kong) |
| `zh-TW` | Mandarin (Traditional Chinese, Taiwan) |

For **Chat API** (`/api/v1/chat`, `/api/v1/chat/simple`): pass `language` in the JSON request body.

For **WebSocket**: pass `language` as a query parameter.

## WebSocket Connections
Connect to `/ws/{source}` for real-time voice/text interaction:
- **source**: `device` or `phone`
- **user_id**: Required user identifier for voice usage tracking
- **language**: `en`, `zh-HK`, `zh-TW` (optional query param)
- **role**: `loyal_best_friend`, `caring_parent`, `coach`, `funny_friend` (optional query param)
- **session_id**: UUID for session continuity (optional query param)

Example: `ws://localhost:8000/ws/device?user_id=user123&language=zh-HK&role=coach&session_id=123e4567-e89b-12d3-a456-426614174000`

## Voice Usage Limits
Voice (TTS) usage is tracked per user with the following limits:
- **Session**: 10 minutes per WebSocket session
- **Daily**: 50 minutes per day
- **Monthly**: 200 minutes per month
When a limit is reached, voice responses are disabled but text chat continues.
    """,
    version="1.0.0",
    contact={
        "name": "Chill Panda Support",
        "email": "support@chillpanda.com",
    },
    license_info={
        "name": "Proprietary",
    },
    openapi_tags=tags_metadata,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/public", StaticFiles(directory="public"), name="static")
templates = Jinja2Templates(directory="templates")
dispatcher = Dispatcher()

# Voice usage database connection (async motor client)
voice_usage_database = Database()

app.include_router(router)
app.include_router(management_router)

# managing dispatcher connect event on app startup


# UI to onboard new customers and view logs + customers info
@app.get("/")
async def get(request: Request):
    return templates.TemplateResponse("index.html" ,  {"request": request})



@app.websocket("/invoke_llm")
async def chat_invoke(websocket: WebSocket):
    guid = str(uuid.uuid4())
    prompt_generator = PromptGenerator()
    modelInstance = LLM(guid , prompt_generator, OPENAI_API_KEY)

    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            if data : 
                user_msg=LLM.LLMMessage(role=LLM.Role.USER, content=data['user_msg'])
                llm_resp = modelInstance.interaction_langchain_synchronous( user_msg )
                print(llm_resp)
                await websocket.send_json(llm_resp)



    except Exception as e:
        print(f"Client disconnected >>> {e}")
        



@app.websocket("/ws/{source}")
async def websocket_endpoint(
    websocket: WebSocket,
    source: SourceEnum,
    language: LanguageEnum | None = None,
    role: RoleEnum | None = None,
    gender: GenderEnum | None = None,
    session_id: str | None = None,
    user_id: str = Query(..., description="Required user identifier for usage tracking")
):
    # Validate user_id
    if not user_id or not user_id.strip():
        await websocket.close(code=4001, reason="user_id is required")
        return

    user_id = user_id.strip()
    if session_id and len(session_id) == 36:
        guid = session_id
    else:
        guid = str(uuid.uuid4())

    language_value = language.value if language else "en"
    role_value = role.value if role else "none"
    observer = SessionObserver(guid, user_id, source.value)
    observer.log(
        "session",
        "started",
        language=language_value,
        role=role_value,
    )

    prompt_generator = PromptGenerator(language or LanguageEnum.english, role)
    modelInstance = LLM(guid, prompt_generator, OPENAI_API_KEY)

    voice_tracker = None
    voice_interceptor = None
    if VOICE_USAGE_ENABLED:
        try:
            voice_tracker = VoiceUsageTracker(
                guid=guid,
                user_id=user_id,
                dispatcher=dispatcher,
                database=voice_usage_database
            )
            usage_summary = await voice_tracker.initialize()
            if not usage_summary.voice_enabled:
                observer.log(
                    "voice_usage",
                    "limit_already_reached",
                    limit=str(usage_summary.limit_reached),
                )
            voice_interceptor = VoiceUsageInterceptor(
                guid=guid,
                tracker=voice_tracker,
                dispatcher=dispatcher
            )
        except Exception as e:
            observer.log("voice_usage", "init_error", error=str(e))

    websocket_manager = WebsocketManager(
        guid,
        modelInstance,
        dispatcher,
        websocket,
        source,
        voice_tracker=voice_tracker,
        observer=observer,
    )
    def create_stt_component():
        return SpeechToTextDeepgram(
            guid,
            dispatcher,
            websocket,
            DEEPGRAM_API_KEY,
            language=language_value,
            source=source.value,
            observer=observer,
        )
    speech_to_text = create_stt_component()
    large_language_model = LargeLanguageModel(
        guid,
        modelInstance,
        dispatcher,
        source.value,
        observer=observer,
        user_id=user_id,
        mongodb_manager=mongodb_manager,
        language=language_value,
        role_value=role_value,
    )

    gender_value = gender.value if gender else "female"

    _VOICE_MAP = {
        ("en",    "male"):   ("elevenlabs", "nPczCjzI2devNBz1zQrb"),
        ("en",    "female"): ("elevenlabs", "hGQkZQUA5RiOXIw7P9iO"),
        ("zh-TW", "male"):   ("minimax",    "Chinese (Mandarin)_Gentle_Youth"),
        ("zh-TW", "female"): ("minimax",    "Chinese (Mandarin)_Gentle_Senior"),
        ("zh-HK", "male"):   ("minimax",    "Cantonese_ProfessionalHost\uff08M)"),
        ("zh-HK", "female"): ("minimax",    "Cantonese_GentleLady"),
    }
    _provider, _voice_id = _VOICE_MAP.get(
        (language_value, gender_value),
        ("minimax", "English_expressive_narrator"),
    )

    def create_tts_component():
        if _provider == "elevenlabs":
            return TextToSpeechElevenLabs(
                guid,
                dispatcher,
                ELEVENLABS_API_KEY,
                voice_id=_voice_id,
                voice_tracker=voice_tracker,
            )
        return TextToSpeechMinimax(
            guid,
            dispatcher,
            MINIMAX_API_KEY,
            voice_id=_voice_id,
            voice_tracker=voice_tracker,
            observer=observer,
        )

    text_to_speech = create_tts_component()

    tasks: dict[str, asyncio.Task] = {}
    error_occurred = None
    tts_retries_remaining = 1
    stt_retries_remaining = 1

    try:
        tasks["STT"] = asyncio.create_task(speech_to_text.run_async(), name="STT")
        tasks["LLM"] = asyncio.create_task(large_language_model.run_async(), name="LLM")
        tasks["TTS"] = asyncio.create_task(text_to_speech.run_async(), name="TTS")
        tasks["WebSocket"] = asyncio.create_task(websocket_manager.run_async(), name="WebSocket")
        if voice_interceptor:
            tasks["VoiceInterceptor"] = asyncio.create_task(voice_interceptor.run_async(), name="VoiceInterceptor")

        shutdown = False
        while tasks and not shutdown:
            done, _ = await asyncio.wait(tasks.values(), return_when=asyncio.FIRST_COMPLETED)
            for done_task in done:
                task_name = next((name for name, task in tasks.items() if task is done_task), "unknown")
                tasks.pop(task_name, None)

                try:
                    done_task.result()
                    observer.log("session", "task_completed", task=task_name)
                    if task_name in {"STT", "LLM", "WebSocket"}:
                        shutdown = True
                        break
                except asyncio.CancelledError:
                    observer.log("session", "task_cancelled", task=task_name)
                except Exception as e:
                    observer.log("session", "task_failed", task=task_name, error=str(e))
                    if task_name == "STT":
                        if stt_retries_remaining > 0:
                            stt_retries_remaining -= 1
                            observer.log("session", "stt_retrying", retries_left=stt_retries_remaining)
                            speech_to_text = create_stt_component()
                            tasks["STT"] = asyncio.create_task(speech_to_text.run_async(), name="STT")
                            continue
                        await dispatcher.broadcast(
                            guid,
                            Message(
                                MessageHeader(MessageType.CALL_WEBSOCKET_PUT),
                                data={
                                    "is_text": True,
                                    "is_transcription": False,
                                    "is_end": True,
                                    "msg": "Voice transcription is temporarily unavailable. You can keep chatting by text.",
                                },
                            ),
                        )
                        error_occurred = e
                        shutdown = True
                        break

                    if task_name == "TTS":
                        if tts_retries_remaining > 0:
                            tts_retries_remaining -= 1
                            observer.log("session", "tts_retrying", retries_left=tts_retries_remaining)
                            text_to_speech = create_tts_component()
                            tasks["TTS"] = asyncio.create_task(text_to_speech.run_async(), name="TTS")
                            continue
                        await dispatcher.broadcast(
                            guid,
                            Message(
                                MessageHeader(MessageType.VOICE_DISABLED),
                                data={"reason": "tts_unavailable"},
                            ),
                        )
                        observer.log("session", "tts_degraded_to_text_only")
                        continue

                    error_occurred = e
                    shutdown = True
                    break

    except Exception as e:
        error_occurred = e
        observer.log("session", "unexpected_error", error=str(e))
    finally:
        try:
            await dispatcher.broadcast(
                guid,
                Message(MessageHeader(MessageType.CALL_ENDED), "Call ended"),
            )
        except Exception as e:
            observer.log("session", "call_ended_broadcast_failed", error=str(e))

        for pending_task in tasks.values():
            pending_task.cancel()
        if tasks:
            await asyncio.gather(*tasks.values(), return_exceptions=True)

        try:
            await websocket_manager.dispose()
        except Exception as e:
            observer.log("session", "websocket_dispose_error", error=str(e))

        if voice_tracker:
            try:
                await voice_tracker.end_session()
            except Exception as e:
                observer.log("voice_usage", "end_session_error", error=str(e))

        if error_occurred:
            observer.log("session", "ended_with_error", error=str(error_occurred))
        else:
            observer.log("session", "ended")
            
@app.get(
    '/api/info',
    tags=["Health"],
    summary="Get API information",
    description="Returns basic information about the Chill Panda API including version and available features.",
    response_description="API status and feature list",
    responses={
        200: {
            "description": "API information",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Chill Panda Backend Running",
                        "version": "1.0.0",
                        "features": ["RAG", "MongoDB", "Pinecone", "Chat History"]
                    }
                }
            }
        }
    }
)
def api_info():
    """
    Get basic API information and status.
    
    Returns the API version and list of available features.
    """
    return {
        'message': 'Chill Panda Backend Running',
        'version': '1.0.0',
        'features': ['RAG', 'MongoDB', 'Pinecone', 'Chat History']
    }


@app.get(
    '/health',
    tags=["Health"],
    summary="Health check",
    description="""
Check the health status of the Chill Panda API and its dependencies.

This endpoint verifies:
- API server is running
- MongoDB database is connected and responsive
    """,
    response_description="Health status of the API and its dependencies",
    responses={
        200: {
            "description": "Service health status",
            "content": {
                "application/json": {
                    "examples": {
                        "healthy": {
                            "summary": "Healthy response",
                            "value": {
                                "status": "healthy",
                                "database": "connected",
                                "service": "Chill Panda API"
                            }
                        },
                        "unhealthy": {
                            "summary": "Unhealthy response",
                            "value": {
                                "status": "unhealthy",
                                "database": "disconnected",
                                "error": "Connection timeout"
                            }
                        }
                    }
                }
            }
        }
    }
)
def health_check():
    """
    Check API and database health.
    
    Returns:
    - **status**: 'healthy' or 'unhealthy'
    - **database**: 'connected' or 'disconnected'
    - **error**: Error message if unhealthy (optional)
    """
    try:
        # Check MongoDB connection
        mongodb_manager._ensure_connection()
        mongodb_manager.client.admin.command('ping')
        return {
            'status': 'healthy',
            'database': 'connected',
            'service': 'Chill Panda API'
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'database': 'disconnected',
            'error': str(e)
        }

@app.on_event("shutdown")
def shutdown_event():
    """Cleanup on shutdown"""
    mongodb_manager.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
    print(f"Server Up At : http://localhost:{PORT}/")
