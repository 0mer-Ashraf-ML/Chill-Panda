import asyncio , os , base64
from functools import partial
from lib_infrastructure.dispatcher import (
    Dispatcher,Message,
    MessageHeader,MessageType,
)
from deepgram import (
    DeepgramClient,
    SpeakOptions,
    SpeakWSOptions,
    SpeakWebSocketEvents,
)

class TextToSpeechDeepgram : 
    def __init__(self, guid ,  dispatcher: Dispatcher , api_key) -> None:
        self.guid = guid 
        self.dispatcher = dispatcher
        self.api_key = api_key
        self.send_buffer_event = True

        DEEPGRAM_API_KEY = self.api_key
        self.deepgram = DeepgramClient(DEEPGRAM_API_KEY)
        self.dg_connection = self.deepgram.speak.websocket.v("1")




    async def convert_via_deepgram(self, words:str):
        words = words.replace('*','')
        self.dg_connection.send_text(words)


    async def handle_llm_generated_text(self):
        async with await self.dispatcher.subscribe(self.guid, MessageType.LLM_GENERATED_TEXT) as llm_generated_text:
            async for event in llm_generated_text:
                words  = event.message.data.get("words")
                is_audio_required = event.message.data.get("is_audio_required")
                if is_audio_required : 
                    asyncio.create_task(self.convert_via_deepgram(words))

                    if self.send_buffer_event : 
                        # Send Clear Buffer Event
                        await self.dispatcher.broadcast(
                            self.guid,
                            Message(
                                MessageHeader(MessageType.CLEAR_EXISTING_BUFFER),
                                data = {},
                            )
                        )
                        # switch the toggle
                        self.send_buffer_event = False




    async def handle_tts_flush(self):
        async with await self.dispatcher.subscribe(self.guid, MessageType.TTS_FLUSH) as flush_event:
            async for event in flush_event:
                fluhs_event = event.message.data
                self.dg_connection.flush()
                # switch the toggle to be re-used again
                self.send_buffer_event = True

    async def run_async(self):
        def on_binary_data(self, data, **kwargs):
            object_instance = kwargs.get("object_instance")
            base64_audio = base64.b64encode(data).decode("utf-8")
            data_object = { "is_text" : False , "audio" : base64_audio }


            asyncio.run(
                object_instance.dispatcher.broadcast(
                    object_instance.guid,
                    Message(
                        MessageHeader(MessageType.CALL_WEBSOCKET_PUT),
                        data= data_object ,
                    ),
                )
            )            



        self.dg_connection.on(SpeakWebSocketEvents.AudioData, partial( on_binary_data , object_instance=self ))

        self.options: SpeakWSOptions = SpeakWSOptions(
            model = "aura-asteria-en",
            encoding="linear16",
            sample_rate=16000,
        )

        success = self.dg_connection.start(self.options)
        if not success : 
            print(f"DeepGram TTS not connected")

        await asyncio.gather(
            self.handle_llm_generated_text(),
            self.handle_tts_flush()
        )