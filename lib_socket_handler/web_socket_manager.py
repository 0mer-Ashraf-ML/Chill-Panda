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
    ):
        self.guid = guid
        self.modelInstance = modelInstance
        self.dispatcher = dispatcher
        self.ws = ws
        self.source = source
        self.logger = logger

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
            # check for voice limit events
            asyncio.create_task(self.websocket_put_voice_limit_event()),
            # check for voice abuse events
            asyncio.create_task(self.websocket_put_voice_abuse_event()),
            # check for voice usage updates
            asyncio.create_task(self.websocket_put_voice_usage_update()),
        ]
        await asyncio.gather(*tasks)

    async def websocket_put_voice_limit_event(self):
        """Send voice limit reached notification to client."""
        async with await self.dispatcher.subscribe(
            self.guid, MessageType.VOICE_LIMIT_REACHED
        ) as subscriber:
            async for event in subscriber:
                usage_data = event.message.data
                limit_data = {
                    "type": "voice_limit_reached",
                    "is_voice_disabled": True,
                    "limit_type": usage_data.get("limit_type"),  # session/daily/monthly
                    "upgrade_required": True,
                    "voice_usage": usage_data
                }
                await self.send(limit_data)

    async def websocket_put_voice_abuse_event(self):
        """Send abuse detection notification to client."""
        async with await self.dispatcher.subscribe(
            self.guid, MessageType.VOICE_ABUSE_DETECTED
        ) as subscriber:
            async for event in subscriber:
                abuse_data = event.message.data
                await self.send({
                    "type": "voice_abuse_detected",
                    "abuse_type": abuse_data.get("abuse_type"),
                    "message": abuse_data.get("message")
                })

    async def websocket_put_voice_usage_update(self):
        """Periodically send voice usage stats to client."""
        async with await self.dispatcher.subscribe(
            self.guid, MessageType.VOICE_USAGE_UPDATE
        ) as subscriber:
            async for event in subscriber:
                await self.send({
                    "type": "voice_usage_update",
                    "voice_usage": event.message.data
                })

    async def dispose(self):
        # Cancel all running tasks
        for task in asyncio.all_tasks():
            if task is not asyncio.current_task():
                task.cancel()
        await self.__close()
        




