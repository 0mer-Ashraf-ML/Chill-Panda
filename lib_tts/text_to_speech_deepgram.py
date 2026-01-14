import asyncio
import base64
from functools import partial
from lib_infrastructure.dispatcher import (
    Dispatcher, Message,
    MessageHeader, MessageType,
)
from deepgram import (
    DeepgramClient,
    SpeakWSOptions,
    SpeakWebSocketEvents,
)


class TextToSpeechDeepgram:
    """
    FIXED v3:
    - Proper interruption handling (listens to user speech, not clear events)
    - Better state management
    - Smart buffering for better audio quality
    - Voice usage tracking integration
    """

    def __init__(self, guid, dispatcher: Dispatcher, api_key, voice_tracker=None) -> None:
        self.guid = guid
        self.dispatcher = dispatcher
        self.api_key = api_key
        self.voice_tracker = voice_tracker  # Voice usage tracker
        
        # Deepgram client
        from deepgram import DeepgramClientOptions
        self.deepgram_config = DeepgramClientOptions(options={"keepalive": "true"})
        self.deepgram = DeepgramClient(api_key=self.api_key, config=self.deepgram_config)
        self.dg_connection = None
        
        # Connection state
        self.is_connected = False
        self.connection_lock = asyncio.Lock()
        
        # Smart buffering
        self.use_smart_buffering = True
        self.word_buffer = ""
        self.buffer_timer = None
        self.buffer_lock = asyncio.Lock()
        self.min_buffer_size = 5
        self.max_buffer_time = 1.0
        self.is_flushing = False
        
        # Interruption tracking
        self.is_interrupted = False
        
        # TTS options
        self.options = SpeakWSOptions(
            model="aura-asteria-en",
            encoding="linear16",
            sample_rate=16000,
        )

    async def connect(self):
        """Initialize Deepgram TTS connection"""
        async with self.connection_lock:
            if self.is_connected:
                return True
                
            try:
                print("🔗 Connecting to Deepgram TTS...")
                
                # Create new connection
                self.dg_connection = self.deepgram.speak.websocket.v("1")
                
                # Register audio callback
                self.dg_connection.on(
                    SpeakWebSocketEvents.AudioData,
                    self._on_audio_data
                )
                
                # Register other event handlers
                self.dg_connection.on(
                    SpeakWebSocketEvents.Open,
                    self._on_open
                )
                
                self.dg_connection.on(
                    SpeakWebSocketEvents.Close,
                    self._on_close
                )
                
                self.dg_connection.on(
                    SpeakWebSocketEvents.Error,
                    self._on_error
                )
                
                # Start connection
                success = self.dg_connection.start(self.options)
                
                if success:
                    self.is_connected = True
                    print("✅ Deepgram TTS connected")
                    return True
                else:
                    print("❌ Deepgram TTS connection failed")
                    return False
                    
            except Exception as e:
                print(f"❌ Deepgram TTS connection error: {e}")
                self.is_connected = False
                return False

    def _on_audio_data(self, *args, **kwargs):
        """Callback for audio data from Deepgram"""
        # Handle different callback signatures
        data = None
        if args:
            # First positional arg might be self or data
            for arg in args:
                if isinstance(arg, bytes):
                    data = arg
                    break

        if data is None and 'data' in kwargs:
            data = kwargs['data']

        if data is None:
            # Try to find data in args
            for arg in args:
                if hasattr(arg, 'data'):
                    data = arg.data
                    break

        if data is None:
            print("⚠️ No audio data found in callback")
            return

        # Check if interrupted
        if self.is_interrupted:
            print("🚫 Skipping audio - user interrupted")
            return

        # Check if voice is disabled (limit reached)
        if self.voice_tracker and not self.voice_tracker.is_voice_enabled():
            print("🚫 Voice disabled - skipping audio")
            self.is_interrupted = True
            return

        # Encode and broadcast
        base64_audio = base64.b64encode(data).decode("utf-8")

        # Track audio usage (async, in background)
        if self.voice_tracker:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    future = asyncio.create_task(
                        self.voice_tracker.track_audio_chunk(base64_audio)
                    )
                    # Note: We can't await here since this is a sync callback
                    # The tracking will happen asynchronously
            except Exception as e:
                print(f"⚠️ Error tracking audio: {e}")

        data_object = {"is_text": False, "audio": base64_audio}

        # Use asyncio to broadcast (callback is sync)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(
                    self.dispatcher.broadcast(
                        self.guid,
                        Message(
                            MessageHeader(MessageType.CALL_WEBSOCKET_PUT),
                            data=data_object,
                        ),
                    )
                )
            else:
                asyncio.run(
                    self.dispatcher.broadcast(
                        self.guid,
                        Message(
                            MessageHeader(MessageType.CALL_WEBSOCKET_PUT),
                            data=data_object,
                        ),
                    )
                )
            print(f"🎵 Deepgram audio chunk: {len(data)} bytes")
        except Exception as e:
            print(f"❌ Error broadcasting audio: {e}")

    def _on_open(self, *args, **kwargs):
        """Callback for connection open"""
        print("🔗 Deepgram TTS connection opened")
        self.is_connected = True

    def _on_close(self, *args, **kwargs):
        """Callback for connection close"""
        print("🔌 Deepgram TTS connection closed")
        self.is_connected = False

    def _on_error(self, *args, **kwargs):
        """Callback for errors"""
        error = kwargs.get('error', args[0] if args else 'Unknown error')
        print(f"❌ Deepgram TTS error: {error}")

    async def ensure_connection(self):
        """Ensure connection is ready"""
        if not self.is_connected:
            return await self.connect()
        return True

    async def send_text(self, text: str):
        """Send text to Deepgram for TTS"""
        if not text.strip():
            return

        if self.is_interrupted:
            print(f"🚫 Skipping send - interrupted")
            return

        # Check if voice is still enabled (not at limit)
        if self.voice_tracker and not self.voice_tracker.is_voice_enabled():
            print(f"🚫 Voice disabled - skipping TTS")
            return

        if not await self.ensure_connection():
            print("❌ Cannot send - connection failed")
            return
            
        try:
            clean_text = text.replace('*', '').strip()
            self.dg_connection.send_text(clean_text)
            print(f"📤 Sent to Deepgram: '{clean_text[:30]}...' ({len(clean_text)} chars)")
        except Exception as e:
            print(f"❌ Error sending to Deepgram: {e}")
            self.is_connected = False

    async def add_word_to_buffer(self, word: str):
        """Smart buffering for better audio quality"""
        if self.is_interrupted:
            return
            
        if not self.use_smart_buffering:
            await self.send_text(word)
            return

        async with self.buffer_lock:
            self.word_buffer += word
            word_count = len(self.word_buffer.split())

            should_send = False
            reason = ""

            if self._is_sentence_end(self.word_buffer):
                if len(self.word_buffer.strip()) >= 10:
                    should_send = True
                    reason = "sentence_end"

            elif word_count >= self.min_buffer_size:
                should_send = True
                reason = "buffer_size"

            if should_send and not self.is_flushing:
                await self._flush_buffer_internal(reason)
            elif not should_send:
                self._schedule_buffer_flush()

    async def _flush_buffer_internal(self, reason: str = ""):
        """Internal flush - assumes lock is held"""
        if self.is_flushing or not self.word_buffer.strip():
            return
            
        if self.is_interrupted:
            self.word_buffer = ""
            return

        self.is_flushing = True

        try:
            buffer_content = self.word_buffer.strip()
            self.word_buffer = ""

            if self.buffer_timer:
                self.buffer_timer.cancel()
                self.buffer_timer = None

            print(f"🎵 Flushing ({reason}): '{buffer_content[:40]}...'")
            await self.send_text(buffer_content)

        finally:
            self.is_flushing = False

    async def _flush_buffer(self, reason: str = ""):
        """Flush buffer with lock"""
        async with self.buffer_lock:
            await self._flush_buffer_internal(reason)

    def _schedule_buffer_flush(self):
        """Schedule buffer flush after delay"""
        if self.buffer_timer:
            self.buffer_timer.cancel()

        async def delayed_flush():
            await asyncio.sleep(self.max_buffer_time)
            if self.word_buffer.strip() and not self.is_interrupted and not self.is_flushing:
                await self._flush_buffer("timer")

        self.buffer_timer = asyncio.create_task(delayed_flush())

    def _is_sentence_end(self, text: str) -> bool:
        import re
        return bool(re.search(r'[.!?]\s*$', text.strip()))

    async def flush_and_end(self):
        """Flush remaining buffer and signal end"""
        async with self.buffer_lock:
            if self.word_buffer.strip() and not self.is_interrupted:
                await self._flush_buffer_internal("final")
        
        # Flush Deepgram's internal buffer
        if self.is_connected and self.dg_connection:
            try:
                self.dg_connection.flush()
                print("🔚 Sent flush to Deepgram")
                await asyncio.sleep(0.3)  # Give time for audio
            except Exception as e:
                print(f"❌ Error flushing Deepgram: {e}")

    async def close_connection(self):
        """Close connection gracefully"""
        if self.dg_connection:
            try:
                self.dg_connection.finish()
                print("🔌 Deepgram TTS connection closed")
            except Exception as e:
                print(f"❌ Error closing Deepgram: {e}")
        
        self.is_connected = False
        if self.buffer_timer:
            self.buffer_timer.cancel()
            self.buffer_timer = None

    async def handle_llm_generated_text(self):
        """Handle streaming text from LLM"""
        async with await self.dispatcher.subscribe(self.guid, MessageType.LLM_GENERATED_TEXT) as llm_generated_text:
            async for event in llm_generated_text:
                words = event.message.data.get("words")
                is_audio_required = event.message.data.get("is_audio_required")

                if is_audio_required and words:
                    # Reset interrupted flag
                    self.is_interrupted = False
                    
                    if self.use_smart_buffering:
                        await self.add_word_to_buffer(words)
                    else:
                        await self.send_text(words)

    async def handle_tts_flush(self):
        """Handle TTS flush events"""
        async with await self.dispatcher.subscribe(self.guid, MessageType.TTS_FLUSH) as flush_event:
            async for event in flush_event:
                print("🔄 TTS Flush event received")
                await self.flush_and_end()

    async def handle_user_interruption(self):
        """Handle user interruption - listens for user speech"""
        async with await self.dispatcher.subscribe(self.guid, MessageType.FINAL_TRANSCRIPTION_CREATED) as user_speech:
            async for event in user_speech:
                print("🛑 USER SPOKE - Interrupting Deepgram TTS")
                
                self.is_interrupted = True
                
                async with self.buffer_lock:
                    self.word_buffer = ""
                
                if self.buffer_timer:
                    self.buffer_timer.cancel()
                    self.buffer_timer = None
                
                # Flush to stop current generation
                if self.is_connected and self.dg_connection:
                    try:
                        self.dg_connection.flush()
                        print("🛑 Flushed Deepgram to interrupt")
                    except Exception as e:
                        print(f"❌ Error interrupting Deepgram: {e}")
                
                # Send clear to client
                await self.dispatcher.broadcast(
                    self.guid,
                    Message(
                        MessageHeader(MessageType.CLEAR_EXISTING_BUFFER),
                        data={"source": "tts_interrupt"},
                    )
                )

    async def run_async(self):
        """Main async runner"""
        print(f"🚀 Starting Deepgram TTS service")
        
        # Initial connection
        await self.connect()
        
        try:
            await asyncio.gather(
                self.handle_llm_generated_text(),
                self.handle_tts_flush(),
                self.handle_user_interruption(),
            )
        except asyncio.CancelledError:
            print("🛑 Deepgram TTS cancelled")
        except Exception as e:
            print(f"❌ Deepgram TTS error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.close_connection()
            print("🏁 Deepgram TTS stopped")