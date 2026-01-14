from lib_infrastructure.dispatcher import (
    Dispatcher,
    Message,
    MessageHeader,
    MessageType,
)

import json
from fastapi import WebSocket
from fastapi.websockets import WebSocketState
import asyncio , os
from lib_infrastructure.disposable import Disposable
from api_request_schemas import SourceEnum
from lib_llm.helpers.llm import LLM


class WebsocketManager(Disposable):
    def __init__(
        self,
        guid,
        modelInstance : LLM,
        dispatcher: Dispatcher,
        ws: WebSocket,
        source : SourceEnum,
        logger=None,
        voice_tracker=None,  # VoiceUsageTracker instance for limit notifications
    ):
        self.guid = guid
        self.modelInstance = modelInstance
        self.dispatcher = dispatcher
        self.ws = ws
        self.source = source
        self.logger = logger
        self.voice_tracker = voice_tracker

    async def open(self):
        await self.ws.accept()
        self.state = WebSocketState.CONNECTED

    async def stream_text(self):
        async for message in self.ws.iter_text():
            #print("GR: TwilioWebSocket received message")
            yield message

    async def send(self, message):
        if self.is_closed():
            # print("GR: TwilioWebSocket Cannot send message on closed websocket" , flush=True)
            return
        
        # send json data object to twillio websocket 
        # await self.ws.send_bytes(message)
        if isinstance(message , dict) : 
            await self.ws.send_json(message)


    async def __close(self):
        try:
            await self.ws.close()
        except:  # noqa
            pass

    def is_closed(self):
        return (
            self.ws.application_state == WebSocketState.DISCONNECTED
            or self.ws.client_state == WebSocketState.DISCONNECTED
        )

    async def close_connection(self):
        async with await self.dispatcher.subscribe(
            self.guid, MessageType.CALL_CLOSE_CONNECTION
        ) as subscriber:
            async for event in subscriber:
                await self.__close()
                break




    def save_conversation_to_json(self, uuid , messages, file_path="conversations.json"):
        """
        Saves a list of message dicts to a JSON file under the 'conversations' key.
        If the file exists, it appends to it; otherwise, it creates a new file.

        :param messages: List of messages (dicts with 'role' and 'content')
        :param file_path: Path to the JSON file
        """
        conversation_entry = {
            "id": uuid,  # unique conversation ID
            "messages": messages
        }

        # Load existing data or start a new structure
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
        else:
            data = {"conversations": []}

        # Append the new conversation
        data["conversations"].append(conversation_entry)

        # Save the updated structure back to file
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)

        print(f"Conversation saved to {file_path} under ID {conversation_entry['id']}")


    async def check_connection(self):
        while True:
            if (
                self.ws.application_state == WebSocketState.DISCONNECTED
                or self.ws.client_state == WebSocketState.DISCONNECTED
            ):
                print("ServerSocker : " ,  self.ws.application_state , "ClientSocket : " , self.ws.client_state )
                await self.dispatcher.broadcast(
                    self.guid,
                    Message(MessageHeader(MessageType.CALL_ENDED), "Closed"),
                )
                # self.save_conversation_to_json(self.guid , self.modelInstance.messages)

                break  # Exit the loop if the WebSocket is disconnected
            await asyncio.sleep(1)


    async def websocket_get(self):
        try : 
            if self.source == SourceEnum.device :
                reeciever = self.ws.iter_text
            elif self.source == SourceEnum.phone :
                reeciever = self.ws.iter_bytes
            else :
                raise RuntimeError("Invalid source type")
            
            async for message in reeciever():
                await self.dispatcher.broadcast(
                    self.guid,
                    Message(
                        MessageHeader(MessageType.CALL_WEBSOCKET_GET), message
                    ),
                )


        except RuntimeError : 
            pass


    async def websocket_put(self):
        async with await self.dispatcher.subscribe(
            self.guid, MessageType.CALL_WEBSOCKET_PUT
        ) as subscriber:
            async for event in subscriber:
                stream_data = event.message.data
                await self.send( stream_data )


    async def websocket_put_user_transcription(self):
        async with await self.dispatcher.subscribe(
            self.guid, MessageType.FINAL_TRANSCRIPTION_CREATED
        ) as subscriber:
            async for event in subscriber:
                stream_data = event.message.data
                user_msg = stream_data.content
                user_msg_data = { "is_text" : True , "is_clear_event" : False ,  "is_transcription" : True , "is_end" : True  , "msg" : user_msg }
                await self.send( user_msg_data )

    async def websocket_put_llm_responce(self):
        async with await self.dispatcher.subscribe(
            self.guid, MessageType.LLM_GENERATED_TEXT
            # self.guid, MessageType.CURRENT_STREAMING_MSG
        ) as subscriber:
            async for event in subscriber:
                stream_data = event.message.data
                llm_msg = stream_data.get('words')
                llm_msg_data = { "is_text" : True , "is_clear_event" : False ,  "is_transcription" : False , "is_end" : False  , "msg" : llm_msg }
                await self.send( llm_msg_data )


    async def websocket_put_llm_structured_data(self):
        async with await self.dispatcher.subscribe(
            self.guid, MessageType.STRUCTURED_DATA
        ) as subscriber:
            async for event in subscriber:
                stream_data = event.message.data
                llm_msg = stream_data
                llm_msg_data = { "api_data" : llm_msg.get("api_data") , "type" : llm_msg.get("type") , "is_text" : False , "is_clear_event" : False ,  "is_transcription" : False , "is_end" : False,  "msg" : None }
                await self.send( llm_msg_data )



    async def websocket_put_llm_new_responce(self):
        async with await self.dispatcher.subscribe(
            self.guid, MessageType.TTS_FLUSH
        ) as subscriber:
            async for event in subscriber:
                stream_data = event.message.data
                llm_msg = stream_data
                llm_msg_data = { "is_text" : True , "is_clear_event" : False , "is_transcription" : False , "is_end" : True,  "msg" : None }
                await self.send( llm_msg_data )


    async def websocket_put_clear_event(self):
        async with await self.dispatcher.subscribe(
            self.guid, MessageType.CLEAR_EXISTING_BUFFER
        ) as subscriber:
            async for event in subscriber:
                llm_msg_data = { "is_text" : False , "is_clear_event" : True , "is_transcription" : False , "is_end" : False,  "msg" : None }
                await self.send( llm_msg_data )


    async def websocket_put_dormant_event(self):
        async with await self.dispatcher.subscribe(
            self.guid, MessageType.IS_DORMANT
        ) as subscriber:
            async for event in subscriber:
                stream_data = event.message.data
                llm_msg = stream_data
                llm_msg_data = { "is_text" : True , "is_clear_event" : False , "is_transcription" : False , "is_end" : True,  "is_dormant" : True ,  "msg" : None }
                await self.send( llm_msg_data )


    async def websocket_put_crisis_event(self):
        async with await self.dispatcher.subscribe(
            self.guid, MessageType.CRISIS_DETECTED
        ) as subscriber:
            async for event in subscriber:
                is_critical = event.message.data.get("is_critical", False)
                crisis_data = { "is_critical": is_critical }
                await self.send( crisis_data )

    async def websocket_put_voice_limit_reached(self):
        """Handle voice limit reached notifications"""
        async with await self.dispatcher.subscribe(
            self.guid, MessageType.VOICE_LIMIT_REACHED
        ) as subscriber:
            async for event in subscriber:
                limit_data = event.message.data
                voice_limit_msg = {
                    "type": "voice_limit_reached",
                    "limit_type": limit_data.get("limit_type"),
                    "limit_minutes": limit_data.get("limit_minutes"),
                    "used_minutes": limit_data.get("used_minutes"),
                    "message": limit_data.get("message"),
                    "voice_disabled": True,
                    "is_text": False,
                    "is_clear_event": False
                }
                await self.send( voice_limit_msg )

    async def websocket_put_voice_disabled(self):
        """Handle voice disabled notifications"""
        async with await self.dispatcher.subscribe(
            self.guid, MessageType.VOICE_DISABLED
        ) as subscriber:
            async for event in subscriber:
                disabled_data = event.message.data
                voice_disabled_msg = {
                    "type": "voice_disabled",
                    "reason": disabled_data.get("reason"),
                    "voice_disabled": True,
                    "is_text": False,
                    "is_clear_event": False
                }
                await self.send( voice_disabled_msg )

    async def websocket_put_voice_warning(self):
        """Handle voice usage warning notifications"""
        async with await self.dispatcher.subscribe(
            self.guid, MessageType.VOICE_USAGE_WARNING
        ) as subscriber:
            async for event in subscriber:
                warning_data = event.message.data
                voice_warning_msg = {
                    "type": "voice_usage_warning",
                    "limit_type": warning_data.get("limit_type"),
                    "limit_minutes": warning_data.get("limit_minutes"),
                    "used_minutes": warning_data.get("used_minutes"),
                    "remaining_minutes": warning_data.get("remaining_minutes"),
                    "message": warning_data.get("message"),
                    "is_text": False,
                    "is_clear_event": False
                }
                await self.send( voice_warning_msg )



    async def run_async(self):
        await self.open()
        # async background tasks for handeling websocket conenctions
        tasks = [
            # check for recieving events
            asyncio.create_task(self.websocket_get()),
            # check for sending events
            asyncio.create_task(self.websocket_put()),
            # check for sending events for user messages being captured
            asyncio.create_task(self.websocket_put_user_transcription()),
            # check for sending llm finish event
            asyncio.create_task(self.websocket_put_llm_new_responce()),
            # check for sending events for LLM responces being captured
            asyncio.create_task(self.websocket_put_llm_responce()),
            # check for sending events for LLM structured data being captured
            asyncio.create_task(self.websocket_put_llm_structured_data()),
            # check for sending dormant event in LLM
            asyncio.create_task(self.websocket_put_dormant_event()),
            # check for sending crisis event
            asyncio.create_task(self.websocket_put_crisis_event()),
            # check web socket clear buffer event
            asyncio.create_task(self.websocket_put_clear_event()),
            # check for close connection events
            asyncio.create_task(self.close_connection()),
            # check for socket connection state
            asyncio.create_task(self.check_connection()),
            # Voice usage limit notifications
            asyncio.create_task(self.websocket_put_voice_limit_reached()),
            asyncio.create_task(self.websocket_put_voice_disabled()),
            asyncio.create_task(self.websocket_put_voice_warning()),
        ]
        await asyncio.gather(*tasks)

    async def dispose(self):
        # Cancel all running tasks
        for task in asyncio.all_tasks():
            if task is not asyncio.current_task():
                task.cancel()
        await self.__close()
        




