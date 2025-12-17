# external imports
import os , uuid , asyncio
from dotenv import load_dotenv
from api_request_schemas import (SourceEnum , LanguageEnum)
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


# app initalization & setup
app = FastAPI(lifespan=lifespan)
app.mount("/public", StaticFiles(directory="public"), name="static")
templates = Jinja2Templates(directory="templates")
dispatcher = Dispatcher()


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
    language: LanguageEnum | None = None 
):
    guid = str(uuid.uuid4())

    print(f"WebSocket connection established via => {source.value} with UID => {guid} & language => {language.value}")

    prompt_generator = PromptGenerator(language)
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
    speech_to_text = SpeechToTextDeepgram( guid , dispatcher ,  websocket , DEEPGRAM_API_KEY )
    large_language_model = LargeLanguageModel( guid , modelInstance , dispatcher, source.value )
    # text_to_speeech = TextToSpeechElevenLabs( guid  , dispatcher , ELEVENLABS_API_KEY )
    text_to_speeech = TextToSpeechMinimax( guid  , dispatcher , MINIMAX_API_KEY )

    try:

        tasks = [
            asyncio.create_task(global_logger.run_async()),
            asyncio.create_task(speech_to_text.run_async()),
            asyncio.create_task(large_language_model.run_async()),
            asyncio.create_task(text_to_speeech.run_async()),            
            asyncio.create_task(websocket_manager.run_async()),
        ]

        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        await websocket_manager.dispose()
    except Exception as e:
        await websocket_manager.dispose()
        raise e
    finally:
        await dispatcher.broadcast(
            guid , Message(MessageHeader(MessageType.CALL_ENDED), "Call ended") 
            )




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
    print(f"Server Up At : http://localhost:{PORT}/")
