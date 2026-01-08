import asyncio
import base64
import json
import re
import websockets
from lib_infrastructure.dispatcher import (
    Dispatcher, Message,
    MessageHeader, MessageType,
)

class TextToSpeechElevenLabs:
    """
    FIXED v3: 
    - Keep audio listener running (don't break on isFinal)
    - Ensure connection is ready before sending
    - Wait for all audio before ending
    """
    def __init__(self, guid, dispatcher: Dispatcher, api_key, voice_id="21m00Tcm4TlvDq8ikWAM", model_id="eleven_flash_v2_5"):
        self.guid = guid 
        self.dispatcher = dispatcher
        self.api_key = api_key
        self.voice_id = voice_id
        self.model_id = model_id
        
        # WebSocket connection
        self.websocket = None
        output_format = "pcm_16000"
        self.uri = f"wss://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream-input?model_id={self.model_id}&output_format={output_format}"
        
        # Connection state
        self.is_connected = False
        self.is_initialized = False  # Track if init message sent
        self.connection_lock = asyncio.Lock()  # Prevent race conditions
        self.connection_attempts = 0
        self.max_connection_attempts = 3
        
        # Smart buffering options
        self.use_smart_buffering = True
        self.word_buffer = ""
        self.buffer_timer = None
        self.buffer_lock = asyncio.Lock()
        self.min_buffer_size = 5  # Increased for better audio quality
        self.max_buffer_time = 1.0
        self.is_flushing = False
        
        # Voice settings
        self.voice_settings = {
            "stability": 0.5, 
            "similarity_boost": 0.8, 
            "use_speaker_boost": True
        }
        
        # Generation config
        self.generation_config = {
            "chunk_length_schedule": [120, 160, 200, 260]  # Larger chunks for better quality
        }
        
        # Interruption tracking
        self.is_interrupted = False
        
        # Audio listener task
        self.audio_listener_task = None

    async def connect_websocket(self):
        """Establish WebSocket connection and initialize"""
        async with self.connection_lock:
            if self.is_connected and self.is_initialized:
                return True
            
            # Close existing connection if any
            if self.websocket:
                try:
                    await self.websocket.close()
                except:
                    pass
                self.websocket = None
                self.is_connected = False
                self.is_initialized = False
                
            try:
                print(f"🔗 Connecting to ElevenLabs WebSocket...")
                self.websocket = await websockets.connect(
                    self.uri,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10
                )
                self.is_connected = True
                self.connection_attempts = 0
                
                # Initialize connection
                init_message = {
                    "text": " ",
                    "voice_settings": self.voice_settings,
                    "generation_config": self.generation_config,
                    "xi_api_key": self.api_key,
                }
                
                await self.websocket.send(json.dumps(init_message))
                self.is_initialized = True
                print(f"✅ ElevenLabs WebSocket connected and initialized")
                
                # Start audio listener if not running
                if self.audio_listener_task is None or self.audio_listener_task.done():
                    self.audio_listener_task = asyncio.create_task(self._listen_for_audio())
                
                return True
                
            except Exception as e:
                print(f"❌ ElevenLabs WebSocket connection failed: {e}")
                self.is_connected = False
                self.is_initialized = False
                self.connection_attempts += 1
                
                if self.connection_attempts < self.max_connection_attempts:
                    print(f"🔄 Retrying connection in 1 second...")
                    await asyncio.sleep(1)
                    # Release lock before recursive call
                    return False
                
                return False

    async def ensure_connection(self):
        """Ensure connection is ready, reconnect if needed"""
        if not self.is_connected or not self.is_initialized:
            success = await self.connect_websocket()
            if not success:
                # Try one more time
                await asyncio.sleep(0.5)
                success = await self.connect_websocket()
            return success
        return True

    async def _listen_for_audio(self):
        """Listen for incoming audio chunks - runs continuously"""
        print("🎧 Audio listener started")
        
        while True:  # Keep running, don't break on isFinal
            try:
                if not self.is_connected or not self.websocket:
                    await asyncio.sleep(0.1)
                    continue
                    
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=30.0)
                    data = json.loads(message)
                    
                    # Check if we've been interrupted
                    if self.is_interrupted:
                        print(f"🚫 Skipping audio - user interrupted")
                        continue
                    
                    if data.get("audio"):
                        audio_data = data["audio"]
                        data_object = {"is_text": False, "audio": audio_data}
                        
                        await self.dispatcher.broadcast(
                            self.guid,
                            Message(
                                MessageHeader(MessageType.CALL_WEBSOCKET_PUT),
                                data=data_object,
                            ),
                        )
                        print(f"🎵 Audio chunk broadcasted")
                        
                    elif data.get('isFinal'):
                        print("🏁 ElevenLabs audio generation complete for this segment")
                        # DON'T break - keep listening for more audio
                        continue
                        
                    elif data.get('error'):
                        print(f"⚠️ ElevenLabs error: {data['error']}")
                        # Connection may be stale, mark for reconnection
                        self.is_connected = False
                        self.is_initialized = False
                        continue
                        
                except asyncio.TimeoutError:
                    # Send ping to keep alive
                    if self.websocket and self.is_connected:
                        try:
                            await self.websocket.ping()
                        except:
                            self.is_connected = False
                            self.is_initialized = False
                    continue
                    
                except websockets.exceptions.ConnectionClosed:
                    print("🔌 ElevenLabs WebSocket connection closed")
                    self.is_connected = False
                    self.is_initialized = False
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
                
        print("🔌 Audio listener stopped")

    async def send_text(self, text: str, flush: bool = False):
        """Send text to ElevenLabs WebSocket"""
        if not text.strip() and not flush:
            return
        
        if self.is_interrupted and not flush:
            print(f"🚫 Skipping send_text - user interrupted")
            return
        
        # Ensure connection before sending
        if not await self.ensure_connection():
            print("❌ Cannot send text - WebSocket connection failed")
            return
                
        try:
            message = {"text": text.strip()}
            if flush:
                message["flush"] = True
                
            await self.websocket.send(json.dumps(message))
            print(f"📤 Sent: '{text.strip()[:30]}...' ({len(text.strip())} chars)")
            
        except websockets.exceptions.ConnectionClosed:
            print("❌ WebSocket closed while sending - will reconnect")
            self.is_connected = False
            self.is_initialized = False
            
        except Exception as e:
            print(f"❌ Error sending text: {e}")
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
                if len(self.word_buffer.strip()) >= 10:  # At least 10 chars for sentence
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
        """Schedule a buffer flush after a delay"""
        if self.buffer_timer:
            self.buffer_timer.cancel()
        
        async def delayed_flush():
            await asyncio.sleep(self.max_buffer_time)
            if self.word_buffer.strip() and not self.is_interrupted and not self.is_flushing:
                await self._flush_buffer("timer")
        
        self.buffer_timer = asyncio.create_task(delayed_flush())

    def _is_sentence_end(self, text: str) -> bool:
        return bool(re.search(r'[.!?]\s*$', text.strip()))

    async def flush_and_end(self):
        """Send final flush and end signal"""
        async with self.buffer_lock:
            if self.word_buffer.strip() and not self.is_interrupted:
                await self._flush_buffer_internal("final")
        
        # Send generation end signal
        if self.is_connected and self.websocket:
            try:
                # Send empty string with flush to signal end of this generation
                await self.websocket.send(json.dumps({"text": "", "flush": True}))
                print("🔚 Sent end signal to ElevenLabs")
                # Give time for audio to be generated and sent
                await asyncio.sleep(0.3)
            except Exception as e:
                print(f"❌ Error sending end signal: {e}")

    async def close_connection(self):
        """Close WebSocket connection gracefully"""
        # Cancel audio listener
        if self.audio_listener_task:
            self.audio_listener_task.cancel()
            try:
                await self.audio_listener_task
            except asyncio.CancelledError:
                pass
        
        if self.websocket:
            try:
                await self.websocket.close()
                print("🔌 ElevenLabs WebSocket closed gracefully")
            except Exception as e:
                print(f"❌ Error closing WebSocket: {e}")
        
        self.is_connected = False
        self.is_initialized = False
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
                    # Reset interrupted flag - we're now processing a response
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
        """Handle user interruption - listens for FINAL_TRANSCRIPTION_CREATED"""
        async with await self.dispatcher.subscribe(self.guid, MessageType.FINAL_TRANSCRIPTION_CREATED) as user_speech:
            async for event in user_speech:
                print("🛑 USER SPOKE - Interrupting TTS")
                
                # Set interrupted flag
                self.is_interrupted = True
                
                # Clear buffer
                async with self.buffer_lock:
                    self.word_buffer = ""
                
                if self.buffer_timer:
                    self.buffer_timer.cancel()
                    self.buffer_timer = None
                
                # Send flush to stop current generation
                if self.is_connected and self.websocket:
                    try:
                        await self.websocket.send(json.dumps({"text": "", "flush": True}))
                        print("🛑 Sent flush to interrupt ElevenLabs")
                    except Exception as e:
                        print(f"❌ Error interrupting: {e}")
                
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
        print(f"🚀 Starting ElevenLabs TTS service for voice: {self.voice_id}")
        
        # Initial connection
        await self.connect_websocket()
        
        try:
            await asyncio.gather(
                self.handle_llm_generated_text(),
                self.handle_tts_flush(),
                self.handle_user_interruption(),
            )
        except asyncio.CancelledError:
            print("🛑 ElevenLabs TTS service cancelled")
        except Exception as e:
            print(f"❌ ElevenLabs TTS service error: {e}")
        finally:
            await self.close_connection()
            print("🏁 ElevenLabs TTS service stopped")