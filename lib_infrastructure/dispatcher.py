import asyncio
import enum
import time
from broadcaster import Broadcast


class MessageType(enum.Enum):
    CALL_STARTED = 0
    CALL_ENDED = 1
    TRANSCRIPTION_CREATED = 2
    RAW_AUDIO_RECEIVED = 3
    RAW_AUDIO_GENERATED = 4
    PARTIAL_TRANSCRIPTION_BEING_GENERATED = 5
    CALL_WEBSOCKET_GET = 6
    CALL_WEBSOCKET_PUT = 7
    CALL_CLOSE_CONNECTION = 8
    LLM_GENERATED_TEXT = 9
    LLM_GENERATED_FULL_TEXT = 10
    FUNCTION = 11
    BACKGROUND_SOUND = 12
    CLEAR_EXISTING_BUFFER = 13
    MARK_EVENT_MESSAGE = 14
    CALLER_ID_CAPTURED = 15
    CALLER_INFO_RECIEVED = 16
    FINAL_TRANSCRIPTION_CREATED = 17
    CURRENT_STREAMING_MSG = 18
    TTS_FLUSH = 19
    STRUCTURED_DATA = 20
    IS_DORMANT = 21
    SPEECH_DETECTED = 22
    SPEECH_ENDED = 23
    CRISIS_DETECTED = 24
    # Voice Usage Limit Events
    VOICE_LIMIT_REACHED = 25      # Sent when a voice limit is reached
    VOICE_DISABLED = 26           # Sent when voice is disabled for the session
    VOICE_USAGE_WARNING = 27      # Sent when approaching a limit (e.g., 80% used)
    VOICE_AUDIO_TRACKED = 28      # Internal event for audio chunk tracking


class MessageHeader:
    def __init__(self, message_type: MessageType):
        self.message_type = message_type
        self.created = time.perf_counter()

    def elapsed(self):
        return time.perf_counter() - self.created


class Message:
    def __init__(self, message_header: MessageHeader, data):
        self.message_header = message_header
        self.data = data


class Dispatcher:
    ALL_GUIDS = {}
    LOGGED_CHANNELS = [ "FINAL_TRANSCRIPTION_CREATED" , "LLM_GENERATED_TEXT" , "CALL_WEBSOCKET_PUT" ]

    def __init__(self):
        self._broadcast = Broadcast("memory://")

    async def subscribe(self, guid, message_type: MessageType):
        channel_name = message_type.name + "_" + guid

        # if(message_type.name in Dispatcher.LOGGED_CHANNELS ) : 
        #     print( "SUBSCRIBED > " , channel_name )


        return self._broadcast.subscribe(channel=channel_name)

    async def broadcast(self, guid, message: Message) -> None:
        channel_name = message.message_header.message_type.name + "_" + guid        

        # if(message.message_header.message_type.name in Dispatcher.LOGGED_CHANNELS ) : 
        #     print( "BROADCASTED > " , channel_name )        

        await self._broadcast.publish(channel=channel_name, message=message)



    async def get(self, subscriber) -> Message:
        async for event in subscriber:
            yield event

    async def get_nowait(self, subscriber) -> Message:
        try:
            return await asyncio.wait_for(subscriber.get(), timeout=0.0001)
        except asyncio.TimeoutError:
            return None





    async def connect(self):
        await self._broadcast.connect()

    async def disconnect(self):
        await self._broadcast.disconnect()
