# external imports
import os , uuid , asyncio
from dotenv import load_dotenv
from api_request_schemas import (SourceEnum , LanguageEnum, RoleEnum)
from fastapi import FastAPI, WebSocket , Request
from fastapi.websockets import WebSocketDisconnect
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
from contextlib import asynccontextmanager
from app.api import router
from app.mongodb_manager import mongodb_manager

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
    
    yield
    
    # Shutdown
    print("Disconnecting from memory://")
    await dispatcher.disconnect()
    print("Disconnected from memory://")


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

## WebSocket Connections
Connect to `/ws/{source}` for real-time voice/text interaction:
- **source**: `device` or `phone`
- **language**: `en`, `french`, `zh-HK`, `zh-TW` (optional query param)
- **role**: `loyal_best_friend`, `caring_parent`, `coach`, `funny_friend` (optional query param)
- **session_id**: UUID for session continuity (optional query param)

Example: `ws://localhost:8000/ws/device?language=en&role=coach&session_id=123e4567-e89b-12d3-a456-426614174000`
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
app.mount("/public", StaticFiles(directory="public"), name="static")
templates = Jinja2Templates(directory="templates")
dispatcher = Dispatcher()

app.include_router(router)

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
    session_id: str | None = None  # Optional UUID from frontend
):
    # Use provided session_id if valid, otherwise generate new UUID
    if session_id and len(session_id) == 36:  # Basic UUID format validation
        guid = session_id
    else:
        guid = str(uuid.uuid4())

    print(f"WebSocket connection established via => {source.value} with UID => {guid} & language => {language.value if language else 'en'} & role => {role.value if role else 'None'}")

    prompt_generator = PromptGenerator(language, role)
    # print("\nPrompt Being Used:")
    # print("\n**START**")
    # print(str(prompt_generator))
    # print("\n**END**")
    modelInstance = LLM(guid , prompt_generator, OPENAI_API_KEY)
    # You can now use the 'language' variable in your logic as needed

    global_logger = GlobalLoggerAsync(
        guid,
        dispatcher,
        pubsub_events={
            MessageType.CALL_WEBSOCKET_PUT: True,
            MessageType.LLM_GENERATED_TEXT: True,
            MessageType.TRANSCRIPTION_CREATED: True,
            MessageType.FINAL_TRANSCRIPTION_CREATED : True,
            MessageType.LLM_GENERATED_FULL_TEXT : True,
            MessageType.CALL_WEBSOCKET_GET : False

        },
        # events whose output needs to be ignored, we just need to capture the time they are fired
        ignore_msg_events = {  
            MessageType.CALL_WEBSOCKET_PUT: True,
            MessageType.CALL_WEBSOCKET_GET : True
        }

    )


    websocket_manager = WebsocketManager( guid, modelInstance , dispatcher, websocket , source )
    speech_to_text = SpeechToTextDeepgram( guid , dispatcher ,  websocket , DEEPGRAM_API_KEY, language=language.value )
    large_language_model = LargeLanguageModel( guid , modelInstance , dispatcher, source.value )
    # text_to_speeech = TextToSpeechElevenLabs( guid  , dispatcher , ELEVENLABS_API_KEY, voice_id="OjkyUe8dIihIFvOisuvM" )
    # text_to_speeech = TextToSpeechDeepgram( guid  , dispatcher , DEEPGRAM_API_KEY )
    text_to_speeech = TextToSpeechMinimax( guid  , dispatcher , MINIMAX_API_KEY , voice_id=language.value )

    try:

        tasks = [
            asyncio.create_task(global_logger.run_async()),
            asyncio.create_task(speech_to_text.run_async()),
            asyncio.create_task(large_language_model.run_async()),
            asyncio.create_task(text_to_speeech.run_async()),            
            asyncio.create_task(websocket_manager.run_async()),
        ]

        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        for task in pending:
            task.cancel()
        
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        for task in done:
            task.result()
    except asyncio.CancelledError:
        await websocket_manager.dispose()
    except Exception as e:
        await websocket_manager.dispose()
        # raise e
    finally:
        await dispatcher.broadcast(
            guid , Message(MessageHeader(MessageType.CALL_ENDED), "Call ended") 
            )


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
