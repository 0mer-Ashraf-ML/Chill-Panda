import asyncio
import base64
import json
import os
import ssl
import websockets
from datetime import datetime
from lib_infrastructure.dispatcher import (
    Dispatcher, Message,
    MessageHeader, MessageType,
)


class TextToSpeechMinimax:
    """
    Text-to-Speech implementation using Minimax API.
    Follows the same pattern as TextToSpeechElevenLabs for consistency.
    """

    def __init__(
        self,
        guid,
        dispatcher: Dispatcher,
        api_key,
        voice_id="English_expressive_narrator",
        model="speech-2.6-turbo" # "speech-2.6-hd"
    ):
        self.guid = guid
        self.dispatcher = dispatcher
        self.api_key = api_key
        self.voice_id = voice_id
        self.model = model
        self.send_buffer_event = True
 
        # WebSocket connection
        self.websocket = None
        self.uri = "wss://api.minimax.io/ws/v1/t2a_v2"

        # Connection state
        self.is_connected = False
        self.is_task_started = False
        self.task_started_event = None  # Event to wait for task_started
        self.connection_attempts = 0
        self.max_connection_attempts = 3

        # Audio settings - using PCM format for compatibility with other TTS providers
        self.audio_settings = {
            "sample_rate": 16000,  # Match other providers
            "bitrate": 128000,
            "format": "pcm",  # Use PCM instead of MP3 for compatibility
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

        # Smart buffering (optimized for Minimax's ~1.6s TTFB latency)
        # Send larger chunks less frequently to reduce roundtrip overhead
        self.use_smart_buffering = True
        self.word_buffer = ""
        self.buffer_timer = None
        self.min_buffer_size = 10  # Increased from 3 to reduce API calls
        self.max_buffer_time = 2.5  # Increased from 1.5s to accumulate more text
        self.is_processing = False

        # Audio file saving for debugging (DISABLED for real-time performance)
        # self.save_audio = True
        # self.audio_save_dir = "audio_output"
        # self.collected_audio = b""
        self.save_audio = False  # Disabled for real-time performance
        
        # Create audio output directory if saving is enabled
        # if self.save_audio and not os.path.exists(self.audio_save_dir):
        #     os.makedirs(self.audio_save_dir)

    async def connect_websocket(self):
        """Establish WebSocket connection to Minimax"""
        if self.is_connected:
            return True

        try:
            print(f"🔗 Connecting to Minimax WebSocket for voice: {self.voice_id}")

            headers = {"Authorization": f"Bearer {self.api_key}"}

            # SSL context for secure connection
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            self.websocket = await websockets.connect(
                self.uri,
                additional_headers=headers,
                # ssl=ssl_context,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )

            # Wait for connection acknowledgment
            response = json.loads(await self.websocket.recv())
            print(f"📥 Minimax connection response: {response}")
            
            if response.get("event") == "connected_success":
                self.is_connected = True
                self.connection_attempts = 0
                self.task_started_event = asyncio.Event()
                print(f"✅ Minimax WebSocket connected successfully")

                # Start listening for audio chunks
                asyncio.create_task(self._listen_for_audio())

                return True
            else:
                print(f"❌ Minimax connection failed: {response}")
                return False

        except Exception as e:
            print(f"❌ Minimax WebSocket connection failed: {e}")
            self.is_connected = False
            self.connection_attempts += 1

            if self.connection_attempts < self.max_connection_attempts:
                print(f"🔄 Retrying connection in 2 seconds... (attempt {self.connection_attempts + 1}/{self.max_connection_attempts})")
                await asyncio.sleep(2)
                return await self.connect_websocket()

            return False

    async def _start_task(self):
        """Send task_start message and wait for task_started confirmation"""
        if self.is_task_started:
            return True

        try:
            start_msg = {
                "event": "task_start",
                "model": self.model,
                "voice_setting": self.voice_settings,
                "audio_setting": self.audio_settings
            }

            print(f"📤 Sending task_start: {json.dumps(start_msg, indent=2)}")
            await self.websocket.send(json.dumps(start_msg))
            
            # Wait for task_started event (with timeout)
            try:
                await asyncio.wait_for(self.task_started_event.wait(), timeout=10.0)
                print(f"✅ Task started confirmed")
                return True
            except asyncio.TimeoutError:
                print(f"❌ Timeout waiting for task_started event")
                return False

        except Exception as e:
            print(f"❌ Failed to start Minimax task: {e}")
            return False

    async def _listen_for_audio(self):
        """Listen for incoming audio chunks from WebSocket"""
        try:
            while self.is_connected and self.websocket:
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=30.0)
                    response = json.loads(message)

                    event_type = response.get("event")
                    print(f"📥 Minimax event: {event_type or 'audio_data'}")

                    if event_type == "task_started":
                        print("🎬 Minimax task_started event received")
                        self.is_task_started = True
                        if self.task_started_event:
                            self.task_started_event.set()
                        continue

                    if event_type == "task_failed":
                        print(f"❌ Minimax task failed: {response}")
                        break

                    # Handle audio data
                    if "data" in response and "audio" in response["data"]:
                        audio_hex = response["data"]["audio"]
                        if audio_hex:
                            # Convert hex to bytes
                            audio_bytes = bytes.fromhex(audio_hex)
                            
                            # Collect audio for saving (DISABLED for real-time performance)
                            # if self.save_audio:
                            #     self.collected_audio += audio_bytes
                            
                            # Convert to base64 for broadcasting
                            base64_audio = base64.b64encode(audio_bytes).decode("utf-8")

                            data_object = {"is_text": False, "audio": base64_audio}

                            await self.dispatcher.broadcast(
                                self.guid,
                                Message(
                                    MessageHeader(MessageType.CALL_WEBSOCKET_PUT),
                                    data=data_object,
                                ),
                            )
                            print(f"🎵 Minimax audio chunk: {len(audio_bytes)} bytes broadcasted")

                    # Check for final message
                    if response.get("is_final"):
                        print("🏁 Minimax audio generation complete")
                        
                        # Save the collected audio to file (DISABLED for real-time performance)
                        # if self.save_audio and self.collected_audio:
                        #     await self._save_audio_file()
                        
                        self.is_task_started = False
                        if self.task_started_event:
                            self.task_started_event.clear()
                        # Don't break - keep listening for next task

                except asyncio.TimeoutError:
                    print("⏰ Minimax WebSocket timeout - sending ping")
                    try:
                        await self.websocket.ping()
                    except:
                        break

                except websockets.exceptions.ConnectionClosed:
                    print("🔌 Minimax WebSocket connection closed")
                    break

                except json.JSONDecodeError as e:
                    print(f"❌ JSON decode error: {e}")
                    continue

                except Exception as e:
                    print(f"❌ Error receiving audio: {e}")
                    import traceback
                    traceback.print_exc()
                    continue

        except Exception as e:
            print(f"❌ Audio listener critical error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.is_connected = False
            self.is_task_started = False
            print("🔌 Minimax audio listener stopped")

    # DISABLED for real-time performance
    # async def _save_audio_file(self):
    #     """Save collected audio to file for debugging"""
    #     if not self.collected_audio:
    #         return
    #         
    #     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    #     # Use .pcm extension since we're requesting PCM format
    #     filename = os.path.join(self.audio_save_dir, f"minimax_audio_{timestamp}.pcm")
    #     
    #     try:
    #         with open(filename, "wb") as f:
    #             f.write(self.collected_audio)
    #         print(f"💾 Audio saved to: {filename} ({len(self.collected_audio)} bytes)")
    #         
    #         # Reset collected audio for next session
    #         self.collected_audio = b""
    #     except Exception as e:
    #         print(f"❌ Failed to save audio: {e}")

    async def send_text(self, text: str):
        """Send text to Minimax for TTS conversion"""
        if not text.strip():
            return

        # Ensure connection
        if not self.is_connected:
            success = await self.connect_websocket()
            if not success:
                print("❌ Cannot send text - WebSocket connection failed")
                return

        # Ensure task is started (and wait for confirmation)
        if not self.is_task_started:
            success = await self._start_task()
            if not success:
                print("❌ Cannot send text - Task start failed")
                return

        try:
            # Clean text (remove markdown asterisks etc.)
            clean_text = text.replace('*', '').strip()

            continue_msg = {
                "event": "task_continue",
                "text": clean_text
            }

            await self.websocket.send(json.dumps(continue_msg))
            print(f"📤 Sent to Minimax: '{clean_text}' ({len(clean_text)} chars)")

        except websockets.exceptions.ConnectionClosed:
            print("❌ WebSocket closed while sending - attempting reconnect")
            self.is_connected = False
            self.is_task_started = False
            if await self.connect_websocket():
                await self.send_text(text)

        except Exception as e:
            print(f"❌ Error sending text: {e}")
            self.is_connected = False

    async def add_word_to_buffer(self, word: str):
        """Smart buffering for optimal real-time performance"""
        if not self.use_smart_buffering:
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

        if self._is_too_short(self.word_buffer) and reason != "forced":
            print(f"⏭️ Skipping short fragment: '{self.word_buffer.strip()}'")
            return

        self.is_processing = True

        try:
            buffer_content = self.word_buffer.strip()
            print(f"🎵 Flushing buffer ({reason}): '{buffer_content}'")

            self.word_buffer = ""

            if self.buffer_timer:
                self.buffer_timer.cancel()
                self.buffer_timer = None

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
        import re
        return bool(re.search(r'[.!?]\s*$', text.strip()))

    def _is_pause_point(self, text: str) -> bool:
        """Check if text ends with a natural pause point"""
        import re
        return bool(re.search(r'[.!?,;:]\s*$', text.strip()))

    def _is_too_short(self, text: str) -> bool:
        """Check if text is too short to send alone"""
        return len(text.strip().split()) < 2

    async def flush_and_end(self):
        """Send final flush and end signal"""
        if self.word_buffer.strip():
            await self._flush_buffer("forced")

        # Send task_finish to Minimax
        if self.is_connected and self.websocket and self.is_task_started:
            try:
                await self.websocket.send(json.dumps({"event": "task_finish"}))
                print("🔚 Sent task_finish to Minimax")
                self.is_task_started = False
            except Exception as e:
                print(f"❌ Error sending task_finish: {e}")

    async def close_connection(self):
        """Close WebSocket connection gracefully"""
        # Save any remaining audio (DISABLED for real-time performance)
        # if self.save_audio and self.collected_audio:
        #     await self._save_audio_file()
            
        if self.websocket:
            try:
                await self.flush_and_end()
                await asyncio.sleep(0.5)
                await self.websocket.close()
                print("🔌 Minimax WebSocket closed gracefully")
            except Exception as e:
                print(f"❌ Error closing WebSocket: {e}")

        self.is_connected = False
        self.is_task_started = False
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
                
                if self.is_connected:
                    await self.send_text("", flush=True)

    def set_voice_settings(self, speed=None, vol=None, pitch=None):
        """Update voice settings"""
        if speed is not None:
            self.voice_settings["speed"] = speed
        if vol is not None:
            self.voice_settings["vol"] = vol
        if pitch is not None:
            self.voice_settings["pitch"] = pitch

        print(f"🎛️ Voice settings updated: {self.voice_settings}")

    def set_buffering_mode(self, smart_buffering=True, min_buffer_size=3, max_buffer_time=1.5):
        """Configure buffering behavior"""
        self.use_smart_buffering = smart_buffering
        self.min_buffer_size = min_buffer_size
        self.max_buffer_time = max_buffer_time

        mode = "smart" if smart_buffering else "direct"
        print(f"📝 Buffering mode set to: {mode} (min_words: {min_buffer_size}, max_time: {max_buffer_time}s)")

    async def run_async(self):
        """Main async runner - handles all events"""
        print(f"🚀 Starting Minimax WebSocket TTS service for voice: {self.voice_id}")
        print(f"📊 Audio settings: {self.audio_settings}")

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
            print("🛑 Minimax TTS service cancelled")
        except Exception as e:
            print(f"❌ Minimax TTS service error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.close_connection()
            print("🏁 Minimax WebSocket TTS service stopped")


# Simplified version without smart buffering for maximum real-time performance
class TextToSpeechMinimaxSimple(TextToSpeechMinimax):
    def __init__(
        self,
        guid,
        dispatcher: Dispatcher,
        api_key,
        voice_id="English_expressive_narrator",
        model="speech-2.6-hd"
    ):
        super().__init__(guid, dispatcher, api_key, voice_id, model)

        # Disable smart buffering for maximum real-time performance
        self.use_smart_buffering = False

        print("⚡ Minimax Direct Mode: Maximum real-time performance")

    async def handle_llm_generated_text(self):
        """Direct streaming without any buffering"""
        async with await self.dispatcher.subscribe(self.guid, MessageType.LLM_GENERATED_TEXT) as llm_generated_text:
            async for event in llm_generated_text:
                words = event.message.data.get("words")
                is_audio_required = event.message.data.get("is_audio_required")

                if is_audio_required and words:
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
