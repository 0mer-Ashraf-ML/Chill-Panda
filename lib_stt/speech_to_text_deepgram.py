import json
import asyncio
from functools import partial
from lib_llm.helpers.llm import LLM
from deepgram import ( DeepgramClient, LiveTranscriptionEvents, LiveOptions, DeepgramClientOptions )
from lib_infrastructure.dispatcher import ( Dispatcher, Message, MessageHeader, MessageType )


class SpeechToTextDeepgram : 
    def __init__(self  , guid , dispatcher: Dispatcher , socket_conext , api_key, language="en" ) -> None:
        self.guid = guid
        self.dispatcher = dispatcher
        self.api_key = api_key
        self.socket_context = socket_conext
        self.language = language
        self.deepgram_config = DeepgramClientOptions( options={"keepalive": "true"} )
        self.deepgram = DeepgramClient(api_key= self.api_key , config=self.deepgram_config )
        self.dg_connection = self.deepgram.listen.live.v("1")
        self.deepgram_options = LiveOptions(
            smart_format = True,
            model = "nova-2-general",
            punctuate=True,
            # language="en-US",
            language=self.language,
            channels=1,
            interim_results=True,
            utterance_end_ms=1000,
            vad_events=True,

        )    



    async def handle_transcibed_text(self, text):
        try:
            if text is None:
                return
            sentence = json.loads(text)
            sentence = sentence.get("transcibed_text" , None)
            if sentence is not None:
                await self.dispatcher.broadcast(
                    self.guid,
                    Message(
                        MessageHeader(MessageType.FINAL_TRANSCRIPTION_CREATED),
                        data=LLM.LLMMessage(role=LLM.Role.USER, content=sentence)
                    ),
                )

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            return



    def transcribe(self, encoded_audio):
        try:
            audio = encoded_audio
            self.dg_connection.send(audio)
        except Exception as e: pass


    async def run_async(self) : 
        # Callback for onMessage deepgram event
        def on_message_deepgram(self , result, **kwargs):
            object_instance = kwargs.get("object_instance")
            if result is None:
                return
            sentence = result.channel.alternatives[0].transcript
            if len(sentence) == 0:
                return
            
            if result.speech_final or result.is_final : 
                # print(f"User : {sentence}")

                asyncio.run(
                    object_instance.dispatcher.broadcast(
                        object_instance.guid,
                        Message(
                            MessageHeader(MessageType.FINAL_TRANSCRIPTION_CREATED),
                            data=LLM.LLMMessage(role=LLM.Role.USER, content=sentence)
                        ),
                    )
                )            

        # Callback for onError deepgram event
        def on_error_deepgram(self, error , **kwargs):
            object_instance = kwargs.get("object_instance")
            # print(f"In deepgram_on_error() > {object_instance}")

            if error is None:
                return True
            # print(f"Error In deepgram : {error}" )
            raise error
        
        # Event listner for Transcript
        self.dg_connection.on(
            LiveTranscriptionEvents.Transcript, partial( on_message_deepgram, object_instance=self )
        )
        # Event listner for Error
        self.dg_connection.on(
            LiveTranscriptionEvents.Error, partial( on_error_deepgram , object_instance=self )
        )

        self.dg_connection.start(self.deepgram_options)

        try:
            async with await self.dispatcher.subscribe(
                self.guid, MessageType.CALL_WEBSOCKET_GET
            ) as websocket_get : 
                async for event in websocket_get:
                    audio_chunk = event.message.data
                    if isinstance(audio_chunk, bytes):
                        self.transcribe(audio_chunk)
                    elif isinstance(audio_chunk, str):
                        await self.handle_transcibed_text(audio_chunk)



        except asyncio.CancelledError: print("Error")        
        except Exception as e : self.dispose( "exception_block" )
        finally: self.dispose( "finally_block" )

    def dispose(self , func_name):
        try : self.dg_connection.finish()
        except Exception as error: print( f"Error_Message > {error}" )



