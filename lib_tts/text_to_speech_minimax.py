import asyncio
import base64
import json
import ssl
import websockets
from lib_infrastructure.dispatcher import (
    Dispatcher, Message,
    MessageHeader, MessageType,
)


class TextToSpeechMinimax:
    """
    FIXED v3:
    - Keep audio listener running continuously
    - Ensure connection is ready before sending
    - Proper task lifecycle management
    - Voice usage tracking integration
    """

    def __init__(
        self,
        guid,
        dispatcher: Dispatcher,
        api_key,
        voice_id="English_expressive_narrator",
        model="speech-2.6-hd",
        voice_tracker=None  # VoiceUsageTracker instance for usage tracking
    ):
        self.guid = guid
        self.dispatcher = dispatcher
        self.api_key = api_key
        self.voice_tracker = voice_tracker  # Voice usage tracker
        if voice_id is None:
            voice_id = "English_expressive_narrator"
        elif voice_id == "zh-HK":
            # voice_id = "moss_audio_c86cf59f-7c89-4c8b-97a8-2e77807295e9"
            voice_id = "cantonese_audio_ad39f71a-efe2-4881-858e-09b1c1b39ce4"
        elif voice_id == "zh-TW":
            voice_id = "hunyin_6"
        else:
            voice_id = "English_expressive_narrator"
        self.voice_id = voice_id
        self.model = model
        
        # WebSocket connection
        self.websocket = None
        self.uri = "wss://api.minimax.io/ws/v1/t2a_v2"

        # Connection state
        self.is_connected = False
        self.is_task_started = False
        self.task_started_event = None
        self.connection_lock = asyncio.Lock()
        self.connection_attempts = 0
        self.max_connection_attempts = 3

        # Audio settings
        self.audio_settings = {
            "sample_rate": 16000,
            "bitrate": 128000,
            "format": "pcm",
            "channel": 1
        }

        # Voice settings
        self.voice_settings = {
            "voice_id": self.voice_id,
            "speed": 1.0,
            "vol": 1,
            "pitch": 0,
            "english_normalization": False
        }

        # Smart buffering
        self.use_smart_buffering = True
        self.word_buffer = ""
        self.buffer_timer = None
        self.buffer_lock = asyncio.Lock()
        self.min_buffer_size = 8
        self.max_buffer_time = 2.5 # 1.5
        self.is_flushing = False
        
        # Interruption tracking
        self.is_interrupted = False
        
        # Audio listener task
        self.audio_listener_task = None

    async def connect_websocket(self):
        """Establish WebSocket connection to Minimax"""
        async with self.connection_lock:
            if self.is_connected:
                return True

            # Close existing connection if any
            if self.websocket:
                try:
                    await self.websocket.close()
                except:
                    pass
                self.websocket = None
                self.is_connected = False
                self.is_task_started = False

            try:
                print(f"🔗 Connecting to Minimax WebSocket...")

                headers = {"Authorization": f"Bearer {self.api_key}"}

                self.websocket = await websockets.connect(
                    self.uri,
                    additional_headers=headers,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10
                )

                response = json.loads(await self.websocket.recv())
                
                if response.get("event") == "connected_success":
                    self.is_connected = True
                    self.connection_attempts = 0
                    self.task_started_event = asyncio.Event()
                    print(f"✅ Minimax WebSocket connected")

                    # Start audio listener if not running
                    if self.audio_listener_task is None or self.audio_listener_task.done():
                        self.audio_listener_task = asyncio.create_task(self._listen_for_audio())

                    return True
                else:
                    print(f"❌ Minimax connection failed: {response}")
                    return False

            except Exception as e:
                print(f"❌ Minimax WebSocket connection failed: {e}")
                self.is_connected = False
                self.connection_attempts += 1

                if self.connection_attempts < self.max_connection_attempts:
                    print(f"🔄 Retrying connection...")
                    await asyncio.sleep(1)
                    return False

                return False

    async def ensure_connection(self):
        """Ensure connection is ready"""
        if not self.is_connected:
            success = await self.connect_websocket()
            if not success:
                await asyncio.sleep(0.5)
                success = await self.connect_websocket()
            return success
        return True

    async def _start_task(self):
        """Send task_start message and wait for confirmation"""
        if self.is_task_started:
            return True

        try:
            if self.task_started_event:
                self.task_started_event.clear()
            else:
                self.task_started_event = asyncio.Event()
                
            start_msg = {
                "event": "task_start",
                "model": self.model,
                "voice_setting": self.voice_settings,
                "audio_setting": self.audio_settings
            }

            await self.websocket.send(json.dumps(start_msg))
            print(f"📤 Sent task_start")
            
            try:
                await asyncio.wait_for(self.task_started_event.wait(), timeout=10.0)
                print(f"✅ Task started")
                return True
            except asyncio.TimeoutError:
                print(f"❌ Timeout waiting for task_started")
                return False

        except Exception as e:
            print(f"❌ Failed to start task: {e}")
            return False

    async def _listen_for_audio(self):
        """Listen for incoming audio chunks - runs continuously"""
        print("🎧 Minimax audio listener started")
        
        while True:
            try:
                if not self.is_connected or not self.websocket:
                    await asyncio.sleep(0.1)
                    continue
                    
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=30.0)
                    response = json.loads(message)

                    event_type = response.get("event")

                    if event_type == "task_started":
                        print("🎬 Task started event received")
                        self.is_task_started = True
                        if self.task_started_event:
                            self.task_started_event.set()
                        continue

                    if event_type == "task_failed":
                        print(f"❌ Task failed: {response}")
                        self.is_task_started = False
                        continue

                    # Check if interrupted
                    if self.is_interrupted:
                        print(f"🚫 Skipping audio - user interrupted")
                        continue

                    # Handle audio data
                    if "data" in response and "audio" in response["data"]:
                        audio_hex = response["data"]["audio"]
                        if audio_hex:
                            audio_bytes = bytes.fromhex(audio_hex)
                            base64_audio = base64.b64encode(audio_bytes).decode("utf-8")

                            # Check voice usage limits before sending
                            if self.voice_tracker:
                                allowed = await self.voice_tracker.track_audio_chunk(base64_audio)
                                if not allowed:
                                    print(f"🚫 Voice limit reached - stopping audio")
                                    self.is_interrupted = True
                                    continue

                            data_object = {"is_text": False, "audio": base64_audio}

                            await self.dispatcher.broadcast(
                                self.guid,
                                Message(
                                    MessageHeader(MessageType.CALL_WEBSOCKET_PUT),
                                    data=data_object,
                                ),
                            )
                            print(f"🎵 Audio chunk: {len(audio_bytes)} bytes")

                    if response.get("is_final"):
                        print("🏁 Audio generation complete for this segment")
                        self.is_task_started = False
                        if self.task_started_event:
                            self.task_started_event.clear()

                        if not self.is_interrupted:
                            await self.dispatcher.broadcast(
                                self.guid,
                                Message(
                                    MessageHeader(MessageType.TTS_AUDIO_COMPLETE),
                                    data={"audio_complete": True},
                                ),
                            )
                        # DON'T break - keep listening

                except asyncio.TimeoutError:
                    if self.websocket and self.is_connected:
                        try:
                            await self.websocket.ping()
                        except:
                            self.is_connected = False
                    continue

                except websockets.exceptions.ConnectionClosed:
                    print("🔌 Minimax WebSocket connection closed")
                    self.is_connected = False
                    self.is_task_started = False
                    continue

                except json.JSONDecodeError as e:
                    print(f"❌ JSON decode error: {e}")
                    continue

            except asyncio.CancelledError:
                print("🛑 Audio listener cancelled")
                break
            except Exception as e:
                print(f"❌ Audio listener error: {e}")
                await asyncio.sleep(0.5)
                continue
                
        print("🔌 Minimax audio listener stopped")

    async def send_text(self, text: str):
        """Send text to Minimax for TTS"""
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

        if not self.is_task_started:
            success = await self._start_task()
            if not success:
                print("❌ Cannot send - task start failed")
                return

        try:
            clean_text = text.replace('*', '').strip()

            continue_msg = {
                "event": "task_continue",
                "text": clean_text
            }

            await self.websocket.send(json.dumps(continue_msg))
            print(f"📤 Sent: '{clean_text[:30]}...' ({len(clean_text)} chars)")

        except websockets.exceptions.ConnectionClosed:
            print("❌ WebSocket closed - will reconnect")
            self.is_connected = False
            self.is_task_started = False

        except Exception as e:
            print(f"❌ Error sending: {e}")
            self.is_connected = False

    async def add_word_to_buffer(self, word: str):
        """Smart buffering"""
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
        """Schedule buffer flush"""
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
        """Send final flush and end task"""
        async with self.buffer_lock:
            if self.word_buffer.strip() and not self.is_interrupted:
                await self._flush_buffer_internal("final")

        if self.is_connected and self.websocket and self.is_task_started:
            try:
                await self.websocket.send(json.dumps({"event": "task_finish"}))
                print("🔚 Sent task_finish")
                self.is_task_started = False
                if self.task_started_event:
                    self.task_started_event.clear()
                # Give time for audio
                await asyncio.sleep(0.3)
            except Exception as e:
                print(f"❌ Error ending task: {e}")

    async def close_connection(self):
        """Close connection gracefully"""
        if self.audio_listener_task:
            self.audio_listener_task.cancel()
            try:
                await self.audio_listener_task
            except asyncio.CancelledError:
                pass

        if self.websocket:
            try:
                await self.websocket.close()
                print("🔌 Minimax WebSocket closed")
            except Exception as e:
                print(f"❌ Error closing: {e}")

        self.is_connected = False
        self.is_task_started = False
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
        """Handle user interruption"""
        async with await self.dispatcher.subscribe(self.guid, MessageType.FINAL_TRANSCRIPTION_CREATED) as user_speech:
            async for event in user_speech:
                print("🛑 USER SPOKE - Interrupting TTS")
                
                self.is_interrupted = True
                
                async with self.buffer_lock:
                    self.word_buffer = ""
                
                if self.buffer_timer:
                    self.buffer_timer.cancel()
                    self.buffer_timer = None
                
                if self.is_connected and self.is_task_started:
                    try:
                        await self.websocket.send(json.dumps({"event": "task_finish"}))
                        self.is_task_started = False
                        if self.task_started_event:
                            self.task_started_event.clear()
                        print("🛑 Sent task_finish to interrupt")
                    except Exception as e:
                        print(f"❌ Error interrupting: {e}")
                
                await self.dispatcher.broadcast(
                    self.guid,
                    Message(
                        MessageHeader(MessageType.CLEAR_EXISTING_BUFFER),
                        data={"source": "tts_interrupt"},
                    )
                )

    async def run_async(self):
        """Main async runner"""
        print(f"🚀 Starting Minimax TTS for voice: {self.voice_id}")

        await self.connect_websocket()

        try:
            await asyncio.gather(
                self.handle_llm_generated_text(),
                self.handle_tts_flush(),
                self.handle_user_interruption(),
            )
        except asyncio.CancelledError:
            print("🛑 Minimax TTS cancelled")
        except Exception as e:
            print(f"❌ Minimax TTS error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.close_connection()
            print("🏁 Minimax TTS stopped")