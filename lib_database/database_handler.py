import asyncio
from lib_infrastructure.dispatcher import Dispatcher, MessageType
from lib_database.conversation_repository import ConversationRepository
from lib_llm.helpers.llm import LLM  # For Role enum

class DatabaseHandler:
    def __init__(
        self,
        guid: str,
        dispatcher: Dispatcher,
        repository: ConversationRepository,
        conversation_id: str
    ):
        self.guid = guid
        self.dispatcher = dispatcher
        self.repository = repository
        self.conversation_id = conversation_id
        
    async def run_async(self):
        """Start listening for events to save to database."""
        await asyncio.gather(
            self.handle_user_messages(),
            self.handle_assistant_messages()
        )
        
    async def handle_user_messages(self):
        """Listen for final transcriptions (User messages)."""
        async with await self.dispatcher.subscribe(
            self.guid, MessageType.FINAL_TRANSCRIPTION_CREATED
        ) as subscriber:
            async for event in subscriber:
                data = event.message.data
                # Data is an LLMMessage object
                if hasattr(data, 'role') and data.role == LLM.Role.USER:
                    content = data.content
                    if content:
                        await self.repository.add_user_message(
                            self.conversation_id,
                            content
                        )
                        # print(f"💾 Saved User message: {content[:30]}...")

    async def handle_assistant_messages(self):
        """Listen for TTS flush events (Assistant messages)."""
        async with await self.dispatcher.subscribe(
            self.guid, MessageType.TTS_FLUSH
        ) as subscriber:
            async for event in subscriber:
                # TTS_FLUSH data is the string content
                content = event.message.data
                if content:
                    await self.repository.add_assistant_message(
                        self.conversation_id,
                        content
                    )
                    # print(f"💾 Saved Assistant message: {content[:30]}...")
