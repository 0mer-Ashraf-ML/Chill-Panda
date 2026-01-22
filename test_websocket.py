# """
# WebSocket Test Script for Chill Panda
# Tests the /ws/{source} endpoint with device source

# Run with: python test_websocket.py

# Example message format:
# { "transcibed_text" :  "Hey Whatsapp !" }
# """

# import asyncio
# import json
# import uuid
# import websockets
# import base64
# import os
# from datetime import datetime
# from typing import Optional
# from api_request_schemas import RoleEnum

# # Configuration
# HOST = "chat.thechillpanda.com"
# # PORT = 8000
# PORT = ""
# SOURCE = "device"  # or "phone"
# LANGUAGE = "en"    # "en", "zh-HK", "zh-TW"
# ROLE = RoleEnum.loyal_best_friend
# AUDIO_OUTPUT_DIR = "test_socket_audio"
# user_id = "new_test_user1"

# class WebSocketTester:
#     def __init__(
#         self,
#         host: str = HOST,
#         port: int = PORT,
#         source: str = SOURCE,
#         language: str = LANGUAGE,
#         role: RoleEnum = ROLE,
#         user_id: Optional[str] = user_id,
#         session_id: Optional[str] = None
#     ):
#         self.host = host
#         self.port = port
#         self.source = source
#         self.language = language
#         self.role = role
#         self.user_id = user_id
#         self.session_id = session_id or str(uuid.uuid4())
#         self.ws: Optional[websockets.WebSocketClientProtocol] = None
#         self.audio_chunk_count = 0
#         self.audio_output_dir = AUDIO_OUTPUT_DIR
#         self._ensure_audio_dir()
    
#     def _ensure_audio_dir(self):
#         """Create audio output directory if it doesn't exist."""
#         if not os.path.exists(self.audio_output_dir):
#             os.makedirs(self.audio_output_dir)
#             print(f"[INFO] Created audio output directory: {self.audio_output_dir}")
    
#     def _save_audio(self, audio_base64: str) -> str:
#         """Save audio chunk to file and return the filepath."""
#         self.audio_chunk_count += 1
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         filename = f"audio_{timestamp}_{self.audio_chunk_count:03d}.pcm"
#         filepath = os.path.join(self.audio_output_dir, filename)
        
#         # Decode base64 and save as raw PCM
#         audio_bytes = base64.b64decode(audio_base64)
#         with open(filepath, "wb") as f:
#             f.write(audio_bytes)
        
#         return filepath
        
#     @property
#     def ws_url(self) -> str:
#         url = f"ws://{self.host}:{self.port}/ws/{self.source}?language={self.language}&session_id={self.session_id}&user_id={self.user_id}"
#         if self.role:
#             url += f"&role={self.role.value}"
#         return url
    
#     async def connect(self) -> bool:
#         """Connect to the WebSocket server."""
#         try:
#             print(f"[CONNECTING] {self.ws_url}")
#             self.ws = await websockets.connect(self.ws_url)
#             print(f"[CONNECTED] Session ID: {self.session_id}")
#             return True
#         except Exception as e:
#             print(f"[ERROR] Failed to connect: {e}")
#             return False
    
#     async def disconnect(self):
#         """Disconnect from the WebSocket server."""
#         if self.ws:
#             await self.ws.close()
#             print("[DISCONNECTED]")
    
#     async def send_text_message(self, text: str):
#         """Send a transcribed text message to the server."""
#         if not self.ws:
#             print("[ERROR] Not connected")
#             return
        
#         message = {"transcibed_text": text}
#         await self.ws.send(json.dumps(message))
#         print(f"[SENT] {message}")
    
#     async def send_raw_message(self, data: dict):
#         """Send a raw JSON message to the server."""
#         if not self.ws:
#             print("[ERROR] Not connected")
#             return
        
#         await self.ws.send(json.dumps(data))
#         print(f"[SENT] {data}")
    
#     async def receive_messages(self, timeout: float = 10.0):
#         """Receive and print messages from the server."""
#         if not self.ws:
#             print("[ERROR] Not connected")
#             return
        
#         print(f"[LISTENING] Waiting for messages (timeout: {timeout}s)...")
#         try:
#             while True:
#                 try:
#                     message = await asyncio.wait_for(self.ws.recv(), timeout=timeout)
                    
#                     # Try to parse as JSON
#                     try:
#                         data = json.loads(message)
#                         self._process_response(data)
#                     except json.JSONDecodeError:
#                         print(f"[RAW] {message[:200]}...")  # Truncate long messages
                        
#                 except asyncio.TimeoutError:
#                     print(f"[TIMEOUT] No message received for {timeout} seconds")
#                     break
                    
#         except websockets.exceptions.ConnectionClosed as e:
#             print(f"[CLOSED] Connection closed: {e}")
    
#     def _process_response(self, data: dict):
#         """Process and display WebSocket response."""
#         if data.get("is_text"):
#             if data.get("is_transcription"):
#                 print(f"[TRANSCRIPTION] {data.get('msg', '')}")
#             else:
#                 is_end = data.get("is_end", False)
#                 prefix = "[LLM_END]" if is_end else "[LLM]"
#                 print(f"{prefix} {data.get('msg', '')}")
#         else:
#             if data.get("is_clear_event"):
#                 print("[CLEAR_AUDIO] Audio buffer cleared")
#             elif data.get("audio"):
#                 audio_base64 = data.get("audio", "")
#                 audio_len = len(audio_base64)
                
#                 # Save the audio to file
#                 try:
#                     filepath = self._save_audio(audio_base64)
#                     print(f"[AUDIO] Saved audio chunk to: {filepath} ({audio_len} bytes base64)")
#                 except Exception as e:
#                     print(f"[ERROR] Failed to save audio: {e}")
#             else:
#                 print(f"[DATA] {data}")


# async def test_connection():
#     """Test basic WebSocket connection."""
#     print("\n" + "="*60)
#     print("TEST: Basic WebSocket Connection")
#     print("="*60)
    
#     tester = WebSocketTester()
#     connected = await tester.connect()
    
#     if connected:
#         print("[PASS] WebSocket connection successful!")
#         await tester.disconnect()
#         return True
#     else:
#         print("[FAIL] Could not connect to WebSocket")
#         return False


# async def test_text_message():
#     """Test sending a text message and receiving response."""
#     print("\n" + "="*60)
#     print("TEST: Send Text Message")
#     print("="*60)
    
#     tester = WebSocketTester()
#     connected = await tester.connect()
    
#     if not connected:
#         print("[FAIL] Could not connect")
#         return False
    
#     try:
#         # Send the example message
#         await tester.send_text_message("Hey Whatsapp!")
        
#         # Wait for responses
#         await tester.receive_messages(timeout=15.0)
        
#         print("[PASS] Message exchange completed!")
#         return True
        
#     except Exception as e:
#         print(f"[FAIL] Error during test: {e}")
#         return False
#     finally:
#         await tester.disconnect()


# async def test_interactive():
#     """Interactive mode to send messages and receive responses."""
#     print("\n" + "="*60)
#     print("INTERACTIVE MODE")
#     print("Type messages to send, 'quit' to exit")
#     print("="*60)
    
#     tester = WebSocketTester()
#     connected = await tester.connect()
    
#     if not connected:
#         print("[FAIL] Could not connect")
#         return
    
#     async def receive_loop():
#         """Background task to receive messages."""
#         try:
#             while True:
#                 try:
#                     message = await asyncio.wait_for(tester.ws.recv(), timeout=1.0)
#                     try:
#                         data = json.loads(message)
#                         tester._process_response(data)
#                     except json.JSONDecodeError:
#                         print(f"[RAW] {message[:200]}")
#                 except asyncio.TimeoutError:
#                     continue
#         except websockets.exceptions.ConnectionClosed:
#             print("[CLOSED] Connection closed")
#         except asyncio.CancelledError:
#             pass
    
#     # Start receiving in background
#     receive_task = asyncio.create_task(receive_loop())
    
#     try:
#         while True:
#             # Get user input
#             user_input = await asyncio.get_event_loop().run_in_executor(
#                 None, input, "\n> Enter message (or 'quit'): "
#             )
            
#             if user_input.lower() == 'quit':
#                 break
            
#             if user_input.strip():
#                 await tester.send_text_message(user_input)
#                 # Wait a bit for responses
#                 await asyncio.sleep(3)
#     finally:
#         receive_task.cancel()
#         await tester.disconnect()


# async def run_all_tests():
#     """Run all automated tests."""
#     print("\n" + "="*60)
#     print("CHILL PANDA WEBSOCKET TEST SUITE")
#     print(f"Server: ws://{HOST}:{PORT}")
#     print("="*60)
    
#     results = []
    
#     # Test 1: Connection
#     results.append(("Connection Test", await test_connection()))
    
#     # Test 2: Text Message
#     results.append(("Text Message Test", await test_text_message()))
    
#     # Summary
#     print("\n" + "="*60)
#     print("TEST RESULTS SUMMARY")
#     print("="*60)
    
#     passed = 0
#     failed = 0
#     for name, result in results:
#         status = "PASS ✓" if result else "FAIL ✗"
#         print(f"  {name}: {status}")
#         if result:
#             passed += 1
#         else:
#             failed += 1
    
#     print(f"\nTotal: {passed} passed, {failed} failed")
#     return failed == 0


# if __name__ == "__main__":
#     import sys
    
#     if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
#         # Run interactive mode
#         asyncio.run(test_interactive())
#     else:
#         # Run automated tests
#         success = asyncio.run(run_all_tests())
#         sys.exit(0 if success else 1)


"""
Simplified WebSocket Audio Test for Chill Panda
Sends audio file to /ws/phone and receives audio responses
"""

import asyncio
import json
import uuid
import websockets
import base64
import wave
from pathlib import Path

# Configuration
HOST = "chat.thechillpanda.com"
USER_ID = "test_user_123"
LANGUAGE = "en"
ROLE = "loyal_best_friend"

# Paths
AUDIO_INPUT = "test_audio.wav"  # Your test audio file (WAV format)
AUDIO_OUTPUT_DIR = "received_audio"


class AudioWebSocketTester:
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.user_id = USER_ID
        self.ws = None
        self.received_audio_chunks = []
        
        # Create output directory
        Path(AUDIO_OUTPUT_DIR).mkdir(exist_ok=True)
    
    @property
    def ws_url(self):
        return (f"wss://{HOST}/ws/phone?"
                f"language={LANGUAGE}&"
                f"role={ROLE}&"
                f"session_id={self.session_id}&"
                f"user_id={self.user_id}")
    
    async def connect(self):
        """Connect to WebSocket"""
        print(f"📡 Connecting to: {self.ws_url}")
        self.ws = await websockets.connect(self.ws_url)
        print(f"✅ Connected! Session: {self.session_id}")
    
    async def send_audio_file(self, audio_path: str):
        """Read WAV file and send as PCM chunks"""
        print(f"\n🎤 Reading audio file: {audio_path}")
        
        with wave.open(audio_path, 'rb') as wav_file:
            # Verify format
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            framerate = wav_file.getframerate()
            
            print(f"   Format: {channels} channel(s), {sample_width*8}-bit, {framerate}Hz")
            
            if channels != 1 or sample_width != 2 or framerate != 16000:
                print("⚠️  WARNING: Expected 16kHz, mono, 16-bit PCM")
            
            # Read and send in chunks (500ms = 16000 samples/s * 0.5s * 2 bytes/sample)
            chunk_size = 16000  # bytes per chunk (500ms at 16kHz, 16-bit)
            chunk_num = 0
            
            while True:
                pcm_data = wav_file.readframes(chunk_size // 2)  # frames, not bytes
                if not pcm_data:
                    break
                
                chunk_num += 1
                await self.ws.send(pcm_data)
                print(f"   📤 Sent chunk #{chunk_num} ({len(pcm_data)} bytes)")
                
                # Simulate real-time streaming
                await asyncio.sleep(0.5)
            
            print(f"✅ Sent {chunk_num} audio chunks\n")
    
    async def receive_responses(self, duration: float = 30.0):
        """Listen for text and audio responses"""
        print(f"👂 Listening for responses (timeout: {duration}s)...\n")
        
        try:
            end_time = asyncio.get_event_loop().time() + duration
            
            while asyncio.get_event_loop().time() < end_time:
                try:
                    message = await asyncio.wait_for(
                        self.ws.recv(), 
                        timeout=1.0
                    )
                    
                    data = json.loads(message)
                    self._process_response(data)
                    
                except asyncio.TimeoutError:
                    continue
                    
        except websockets.exceptions.ConnectionClosed:
            print("🔌 Connection closed by server")
    
    def _process_response(self, data: dict):
        """Process incoming WebSocket messages"""
        
        # Voice limit notifications
        if data.get("type") == "voice_limit_reached":
            print(f"🚫 VOICE LIMIT: {data.get('message')}")
            return
        
        if data.get("type") == "voice_usage_warning":
            print(f"⚠️  WARNING: {data.get('message')}")
            return
        
        # Text responses
        if data.get("is_text"):
            if data.get("is_transcription"):
                msg = data.get("msg", "")
                print(f"📝 [YOUR TRANSCRIPTION]: {msg}")
            
            elif data.get("is_end"):
                print(f"🏁 [LLM COMPLETE]\n")
            
            else:
                msg = data.get("msg", "")
                if msg:
                    print(f"💬 [LLM]: {msg}", end="", flush=True)
        
        # Audio responses
        elif data.get("audio"):
            audio_base64 = data.get("audio")
            self.received_audio_chunks.append(audio_base64)
            print(f"🔊 [AUDIO CHUNK] Received #{len(self.received_audio_chunks)}")
        
        # Clear events
        elif data.get("is_clear_event"):
            print("🧹 [CLEAR] Audio buffer cleared")
    
    async def save_received_audio(self):
        """Combine and save all received audio chunks"""
        if not self.received_audio_chunks:
            print("\n⚠️  No audio received")
            return
        
        print(f"\n💾 Saving {len(self.received_audio_chunks)} audio chunks...")
        
        # Decode all chunks
        all_audio_data = b""
        for chunk_base64 in self.received_audio_chunks:
            all_audio_data += base64.b64decode(chunk_base64)
        
        # Save as raw PCM
        pcm_path = f"{AUDIO_OUTPUT_DIR}/response_{self.session_id[:8]}.pcm"
        with open(pcm_path, "wb") as f:
            f.write(all_audio_data)
        
        print(f"✅ Saved PCM: {pcm_path} ({len(all_audio_data)} bytes)")
        
        # Also save as WAV for easy playback
        wav_path = f"{AUDIO_OUTPUT_DIR}/response_{self.session_id[:8]}.wav"
        with wave.open(wav_path, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(16000)  # 16kHz
            wav_file.writeframes(all_audio_data)
        
        print(f"✅ Saved WAV: {wav_path}")
        print(f"🎧 Play with: ffplay {wav_path}\n")
    
    async def disconnect(self):
        """Close connection"""
        if self.ws:
            await self.ws.close()
            print("👋 Disconnected")


async def main():
    """Main test flow"""
    print("\n" + "="*60)
    print("🐼 CHILL PANDA - AUDIO WEBSOCKET TEST")
    print("="*60 + "\n")
    
    # Check if test audio exists
    if not Path(AUDIO_INPUT).exists():
        print(f"❌ Audio file not found: {AUDIO_INPUT}")
        print("\n💡 TIP: Create a test audio file:")
        print(f"   ffmpeg -f lavfi -i 'sine=frequency=1000:duration=3' -ar 16000 -ac 1 -sample_fmt s16 {AUDIO_INPUT}")
        return
    
    tester = AudioWebSocketTester()
    
    try:
        # 1. Connect
        await tester.connect()
        
        # 2. Send audio file
        await tester.send_audio_file(AUDIO_INPUT)
        
        # 3. Receive responses
        await tester.receive_responses(duration=30.0)
        
        # 4. Save received audio
        await tester.save_received_audio()
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await tester.disconnect()
    
    print("\n" + "="*60)
    print("✅ Test Complete")
    print("="*60 + "\n")


if __name__ == "__main__":
    # Run the test
    asyncio.run(main())