from __future__ import annotations
import json
from typing import Dict, List
from lib_llm.helpers.llm import LLM
from lib_llm.helpers.tools import *
import asyncio
from lib_infrastructure.dispatcher import (Dispatcher, MessageType, Message, MessageHeader)
from lib_llm.helpers.crisis_detector import CrisisDetector


tools = [

]


tool_implementations = {
    "call_api": call_api
}

class LargeLanguageModel:
    def __init__(self, guid, llm: LLM, dispatcher: Dispatcher, source: str = "device"):
        self.guid = guid
        self.llm = llm
        self.dispatcher = dispatcher
        llm.tools = []
        self.source = source
        self.is_audio_required = True
        self.is_generating = False
        self.crisis_detector = CrisisDetector(llm.api_key)


    async def _check_for_crisis(self, text: str):
        is_critical = await self.crisis_detector.detect_crisis(text)
        await self.dispatcher.broadcast(
            self.guid,
            Message(
                MessageHeader(MessageType.CRISIS_DETECTED),
                data={"is_critical": is_critical}
            )
        )

    async def process(self, message: LLM.LLMMessage):
        # ONLY send clear buffer for USER messages (new user input)
        # This tells the TTS to stop any ongoing playback
        # DO NOT send clear buffer for TOOL or SYSTEM messages
        if message.role == LLM.Role.USER:
            self.is_generating = True
            print(f"[LLM] Processing user message: \"{message.content[:50]}{'...' if len(message.content) > 50 else ''}\"")
            # Fire and forget crisis detection to not block the main response
            asyncio.create_task(self._check_for_crisis(message.content))
            
            await self.dispatcher.broadcast(
                self.guid,
                Message(
                    MessageHeader(MessageType.CLEAR_EXISTING_BUFFER),
                    data={"source": "user_input"},  # Tag the source
                )
            )

        llm_words = []
        async for words in self.llm.create_completion(message=message):
            if isinstance(words, Dict):
                # Tool call handling
                print(f"[TOOL_CALL] : {words}")

                func = tool_implementations.get(words.get('name'))
                tool_call_id = words.get('id')
                if func:
                    func_args = words.get('args', {})
                    func_args['lat'] = self.lat
                    func_args['long'] = self.long
                    func_args['source'] = self.source
                    result = func(func_args)
                    if result.get('is_llm_needed'):
                        await self.dispatcher.broadcast(
                            self.guid,
                            Message(
                                MessageHeader(MessageType.FINAL_TRANSCRIPTION_CREATED),
                                data=LLM.LLMMessage(
                                    role=LLM.Role.SYSTEM,
                                    content=json.dumps(result.get("data")),
                                ),
                            ),
                        )
                    else:
                        llm_words = result.get('data')
                        strucutred_data = result.get('api_data', {})
                        api_data_type = result.get('type', None)

                        await self.dispatcher.broadcast(
                            self.guid,
                            Message(
                                MessageHeader(MessageType.STRUCTURED_DATA),
                                data={"id": tool_call_id, "api_data": strucutred_data, "type": api_data_type},
                            ),
                        )

                        self.llm.messages.append({
                            "role": LLM.Role.ASSISTANT.value,
                            "tool_calls": [
                                {"id": tool_call_id, "type": "function",
                                 "function": {"name": words.get('name'), "arguments": json.dumps(func_args)}}
                            ]
                        })

                        message = LLM.LLMMessage(role=LLM.Role.TOOL, content=json.dumps(llm_words),
                                                 tool_call_id=words.get('id'))
                        await self.process(message=message)

            else:
                words = words.lower()
                llm_words.append(words)
                # words = words.replace("{", "").replace("}", "").replace("response", "").replace("is_critical", "").replace("true", "").replace("false", "")
                await self.dispatcher.broadcast(
                    self.guid,
                    Message(
                        MessageHeader(
                            MessageType.LLM_GENERATED_TEXT
                        ),
                        data={"words": words, "is_audio_required": self.is_audio_required},
                    ),
                )

        self.is_generating = False
        words = "".join(llm_words)
        print(f"[LLM] Response complete - Length: {len(words)} chars")
        # words = words.replace("```json", "").replace("```", "")
        # words = json.loads(words)
        # print("------------","LargeLanguageModel",words,"------------")
        await self.dispatcher.broadcast(
            self.guid,
            Message(
                MessageHeader(
                    MessageType.TTS_FLUSH
                ),
                # data=words["response"],
                data=words
            ),
        )

    async def run_async(self):
        async with await self.dispatcher.subscribe(
                self.guid, MessageType.CALL_ENDED
        ) as call_ended_subscriber, await self.dispatcher.subscribe(
            self.guid, MessageType.FINAL_TRANSCRIPTION_CREATED
        ) as transcription_created_subscriber:

            async for event in transcription_created_subscriber:
                self.is_audio_required = True
                await self.process(message=event.message.data)

                call_ended_message = await self.dispatcher.get_nowait(
                    call_ended_subscriber
                )
                if call_ended_message is not None:
                    break