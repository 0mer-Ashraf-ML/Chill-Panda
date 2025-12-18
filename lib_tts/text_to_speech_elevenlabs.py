import asyncio
import base64
import json
import re
import websockets
from functools import partial
from lib_infrastructure.dispatcher import (
    Dispatcher, Message,
    MessageHeader, MessageType,
)

class TextToSpeechElevenLabs:
    def __init__(self, guid, dispatcher: Dispatcher, api_key, voice_id="21m00Tcm4TlvDq8ikWAM", model_id="eleven_flash_v2_5"):
        self.guid = guid 
        self.dispatcher = dispatcher
        self.api_key = api_key
        self.voice_id = voice_id
        self.model_id = model_id
        self.send_buffer_event = True
        
        # WebSocket connection
        self.websocket = None
        output_format = "pcm_16000"
        self.uri = f"wss://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream-input?model_id={self.model_id}&output_format={output_format}"
        
        # Connection state
        self.is_connected = False
        self.is_processing = False
        self.connection_attempts = 0
        self.max_connection_attempts = 3
        
        # Smart buffering options
        self.use_smart_buffering = True
        self.word_buffer = ""
        self.buffer_timer = None
        self.min_buffer_size = 3  # Minimum words before sending
        self.max_buffer_time = 1.5  # Maximum time to wait before sending
        
        # Voice settings
        self.voice_settings = {
            "stability": 0.4, 
            "similarity_boost": 0.9, 
            "use_speaker_boost": True
        }
        
        # Generation config optimized for real-time
        self.generation_config = {
            "chunk_length_schedule": [50, 80, 120, 160]  # Aggressive chunking for low latency
        }

    async def connect_websocket(self):
        """Establish WebSocket connection and initialize"""
        if self.is_connected:
            return True
            
        try:
            print(f"🔗 Connecting to ElevenLabs WebSocket for voice: {self.voice_id}")
            self.websocket = await websockets.connect(
                self.uri,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            self.is_connected = True
            self.connection_attempts = 0
            
            # Initialize connection with voice settings
            init_message = {
                "text": " ",  # Initial empty text
                "voice_settings": self.voice_settings,
                "generation_config": self.generation_config,
                "xi_api_key": self.api_key,
            }
            
            await self.websocket.send(json.dumps(init_message))
            print(f"✅ ElevenLabs WebSocket connected and initialized")
            
            # Start listening for audio chunks
            asyncio.create_task(self._listen_for_audio())
            
            return True
            
        except Exception as e:
            print(f"❌ ElevenLabs WebSocket connection failed: {e}")
            self.is_connected = False
            self.connection_attempts += 1
            
            # Try to reconnect if under max attempts
            if self.connection_attempts < self.max_connection_attempts:
                print(f"🔄 Retrying connection in 2 seconds... (attempt {self.connection_attempts + 1}/{self.max_connection_attempts})")
                await asyncio.sleep(2)
                return await self.connect_websocket()
            
            return False

    async def _listen_for_audio(self):
        """Listen for incoming audio chunks from WebSocket"""
        try:
            while self.is_connected and self.websocket:
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=30.0)
                    data = json.loads(message)
                    
                    if data.get("audio"):
                        # Audio data is already base64 encoded
                        audio_data = data["audio"]
                        data_object = {"is_text": False, "audio": audio_data}
                        
                        await self.dispatcher.broadcast(
                            self.guid,
                            Message(
                                MessageHeader(MessageType.CALL_WEBSOCKET_PUT),
                                data=data_object,
                            ),
                        )
                        print(f"🎵 ElevenLabs audio chunk received and broadcasted")
                        
                    elif data.get('isFinal'):
                        print("🏁 ElevenLabs audio generation complete")
                        break
                        
                    elif data.get('error'):
                        print(f"❌ ElevenLabs WebSocket error: {data['error']}")
                        break
                        
                except asyncio.TimeoutError:
                    print("⏰ WebSocket timeout - sending ping")
                    try:
                        await self.websocket.ping()
                    except:
                        break
                        
                except websockets.exceptions.ConnectionClosed:
                    print("🔌 ElevenLabs WebSocket connection closed")
                    break
                    
                except json.JSONDecodeError as e:
                    print(f"❌ JSON decode error: {e}")
                    continue
                    
                except Exception as e:
                    print(f"❌ Error receiving audio: {e}")
                    continue
                    
        except Exception as e:
            print(f"❌ Audio listener critical error: {e}")
        finally:
            self.is_connected = False
            print("🔌 Audio listener stopped")

    async def send_text(self, text: str, flush: bool = False, force: bool = False):
        """Send text to ElevenLabs WebSocket for real-time generation"""
        if not text.strip() and not flush:
            return
            
        # Ensure connection
        if not self.is_connected:
            success = await self.connect_websocket()
            if not success:
                print("❌ Cannot send text - WebSocket connection failed")
                return
                
        try:
            message = {"text": text.strip()}
            if flush:
                message["flush"] = True
                
            await self.websocket.send(json.dumps(message))
            
            if flush:
                print(f"🔚 Sent to ElevenLabs with flush: '{text}'")
            else:
                print(f"📤 Sent to ElevenLabs: '{text}' ({len(text)} chars)")
            
        except websockets.exceptions.ConnectionClosed:
            print("❌ WebSocket closed while sending - attempting reconnect")
            self.is_connected = False
            if await self.connect_websocket():
                await self.send_text(text, flush, force)
                
        except Exception as e:
            print(f"❌ Error sending text: {e}")
            self.is_connected = False

    async def add_word_to_buffer(self, word: str):
        """Smart buffering for optimal real-time performance"""
        if not self.use_smart_buffering:
            # Direct streaming mode
            await self.send_text(word)
            return
            
        if self.is_processing:
            return
            
        self.word_buffer += word
        word_count = len(self.word_buffer.split())
        
        should_send = False
        reason = ""
        
        # Smart sending logic
        if self._is_sentence_end(self.word_buffer):
            if not self._is_too_short(self.word_buffer):
                should_send = True
                reason = "sentence_end"
            else:
                # If it's just punctuation, wait for more or let timer handle it
                await self._schedule_buffer_flush()
                return
        
        elif self._is_pause_point(self.word_buffer) and word_count >= 4:
            should_send = True
            reason = "pause_point"
        
        elif word_count >= self.min_buffer_size:
            should_send = True
            reason = "buffer_size"
        
        if should_send:
            await self._flush_buffer(reason)
        else:
            await self._schedule_buffer_flush()

    async def _flush_buffer(self, reason: str = ""):
        """Flush buffer to WebSocket"""
        if self.is_processing or not self.word_buffer.strip():
            return
            
        # Don't send very short fragments alone unless forced
        if self._is_too_short(self.word_buffer) and reason != "forced":
            print(f"⏭️ Skipping short fragment: '{self.word_buffer.strip()}'")
            return
            
        self.is_processing = True
        
        try:
            buffer_content = self.word_buffer.strip()
            print(f"🎵 Flushing buffer ({reason}): '{buffer_content}'")
            
            # Clear buffer BEFORE sending
            self.word_buffer = ""
            
            # Cancel any pending timer
            if self.buffer_timer:
                self.buffer_timer.cancel()
                self.buffer_timer = None
            
            # Send to WebSocket
            await self.send_text(buffer_content)
            
        finally:
            self.is_processing = False

    async def _schedule_buffer_flush(self):
        """Schedule a buffer flush after a delay"""
        if self.buffer_timer:
            self.buffer_timer.cancel()
        
        async def delayed_flush():
            await asyncio.sleep(self.max_buffer_time)
            if not self.is_processing and self.word_buffer.strip():
                print(f"⏰ Timer flush")
                await self._flush_buffer("timer")
        
        self.buffer_timer = asyncio.create_task(delayed_flush())

    def _is_sentence_end(self, text: str) -> bool:
        """Check if text ends with sentence-ending punctuation"""
        return bool(re.search(r'[.!?]\s*$', text.strip()))

    def _is_pause_point(self, text: str) -> bool:
        """Check if text ends with a natural pause point"""
        return bool(re.search(r'[.!?,;:]\s*$', text.strip()))
    
    def _is_too_short(self, text: str) -> bool:
        """Check if text is too short to send alone"""
        return len(text.strip().split()) < 2

    async def flush_and_end(self):
        """Send final flush and end signal"""
        if self.word_buffer.strip():
            await self._flush_buffer("forced")
            
        # Send empty text to signal end
        if self.is_connected and self.websocket:
            try:
                await self.websocket.send(json.dumps({"text": ""}))
                print("🔚 Sent end signal to ElevenLabs")
            except Exception as e:
                print(f"❌ Error sending end signal: {e}")

    async def close_connection(self):
        """Close WebSocket connection gracefully"""
        if self.websocket:
            try:
                await self.flush_and_end()
                await asyncio.sleep(0.5)  # Give time for final audio
                await self.websocket.close()
                print("🔌 ElevenLabs WebSocket closed gracefully")
            except Exception as e:
                print(f"❌ Error closing WebSocket: {e}")
        
        self.is_connected = False
        if self.buffer_timer:
            self.buffer_timer.cancel()
            self.buffer_timer = None

    async def handle_llm_generated_text(self):
        """Handle streaming text from LLM - main event handler"""
        async with await self.dispatcher.subscribe(self.guid, MessageType.LLM_GENERATED_TEXT) as llm_generated_text:
            async for event in llm_generated_text:
                words = event.message.data.get("words")
                is_audio_required = event.message.data.get("is_audio_required")
                
                if is_audio_required and words:
                    if self.use_smart_buffering:
                        await self.add_word_to_buffer(words)
                    else:
                        await self.send_text(words)
                    
                    # Send clear buffer event on first text
                    if self.send_buffer_event:
                        await self.dispatcher.broadcast(
                            self.guid,
                            Message(
                                MessageHeader(MessageType.CLEAR_EXISTING_BUFFER),
                                data={},
                            )
                        )
                        self.send_buffer_event = False

    async def handle_tts_flush(self):
        """Handle TTS flush events"""
        async with await self.dispatcher.subscribe(self.guid, MessageType.TTS_FLUSH) as flush_event:
            async for event in flush_event:
                print("🔄 TTS Flush event received")
                
                # Force flush any remaining buffer
                if self.word_buffer.strip():
                    await self._flush_buffer("forced")
                
                await self.flush_and_end()
                self.send_buffer_event = True

    async def handle_clear_buffer(self):
        """Handle clear buffer events for interruptions"""
        async with await self.dispatcher.subscribe(self.guid, MessageType.CLEAR_EXISTING_BUFFER) as clear_event:
            async for event in clear_event:
                print("🧹 Clear buffer event received")
                
                # Clear any pending buffer
                self.word_buffer = ""
                if self.buffer_timer:
                    self.buffer_timer.cancel()
                    self.buffer_timer = None
                
                # Send flush to stop current generation
                if self.is_connected:
                    await self.send_text("", flush=True)

    def set_voice_settings(self, stability=None, similarity_boost=None, use_speaker_boost=None):
        """Update voice settings"""
        if stability is not None:
            self.voice_settings["stability"] = stability
        if similarity_boost is not None:
            self.voice_settings["similarity_boost"] = similarity_boost
        if use_speaker_boost is not None:
            self.voice_settings["use_speaker_boost"] = use_speaker_boost
        
        print(f"🎛️ Voice settings updated: {self.voice_settings}")

    def set_buffering_mode(self, smart_buffering=True, min_buffer_size=3, max_buffer_time=1.5):
        """Configure buffering behavior"""
        self.use_smart_buffering = smart_buffering
        self.min_buffer_size = min_buffer_size
        self.max_buffer_time = max_buffer_time
        
        mode = "smart" if smart_buffering else "direct"
        print(f"📝 Buffering mode set to: {mode} (min_words: {min_buffer_size}, max_time: {max_buffer_time}s)")

    def set_chunk_schedule(self, chunk_schedule):
        """Update chunk length schedule for generation"""
        self.generation_config["chunk_length_schedule"] = chunk_schedule
        print(f"📊 Chunk schedule updated: {chunk_schedule}")

    async def run_async(self):
        """Main async runner - handles all events"""
        print(f"🚀 Starting ElevenLabs WebSocket TTS service for voice: {self.voice_id}")
        
        # Connect initially
        success = await self.connect_websocket()
        if not success:
            print("❌ Failed to establish initial connection")
            return
        
        try:
            # Run all event handlers concurrently
            await asyncio.gather(
                self.handle_llm_generated_text(),
                self.handle_tts_flush(),
                self.handle_clear_buffer()
            )
        except asyncio.CancelledError:
            print("🛑 ElevenLabs TTS service cancelled")
        except Exception as e:
            print(f"❌ ElevenLabs TTS service error: {e}")
        finally:
            await self.close_connection()
            print("🏁 ElevenLabs WebSocket TTS service stopped")


# Simplified version without smart buffering for maximum real-time performance
class TextToSpeechElevenLabsSimple(TextToSpeechElevenLabs):
    def __init__(self, guid, dispatcher: Dispatcher, api_key, voice_id="21m00Tcm4TlvDq8ikWAM", model_id="eleven_flash_v2_5"):
        super().__init__(guid, dispatcher, api_key, voice_id, model_id)
        
        # Disable smart buffering for maximum real-time performance
        self.use_smart_buffering = False
        
        # Ultra-aggressive chunking for lowest latency
        self.generation_config = {
            "chunk_length_schedule": [20, 40, 60, 80]
        }
        
        print("⚡ ElevenLabs Direct Mode: Maximum real-time performance")

    async def handle_llm_generated_text(self):
        """Direct streaming without any buffering"""
        async with await self.dispatcher.subscribe(self.guid, MessageType.LLM_GENERATED_TEXT) as llm_generated_text:
            async for event in llm_generated_text:
                words = event.message.data.get("words")
                is_audio_required = event.message.data.get("is_audio_required")
                
                if is_audio_required and words:
                    # Send directly without any buffering
                    await self.send_text(words)
                    
                    if self.send_buffer_event:
                        await self.dispatcher.broadcast(
                            self.guid,
                            Message(
                                MessageHeader(MessageType.CLEAR_EXISTING_BUFFER),
                                data={},
                            )
                        )
                        self.send_buffer_event = False