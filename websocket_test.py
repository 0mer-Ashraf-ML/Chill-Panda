import asyncio
import websockets
import sounddevice as sd
import numpy as np
import uuid
import json

# ================= CONFIG =================
HOST = "localhost:8000"
LANGUAGE = "en"
ROLE = "loyal_best_friend"
USER_ID = "mic_test_user"

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"
FRAME_DURATION = 0.5  # seconds
FRAMES_PER_CHUNK = int(SAMPLE_RATE * FRAME_DURATION)
# =========================================


class MicWebSocketTester:
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.ws = None
        self.running = True

    @property
    def ws_url(self):
        return (
            f"ws://{HOST}/ws/phone?"
            f"language={LANGUAGE}&"
            f"role={ROLE}&"
            f"session_id={self.session_id}&"
            f"user_id={USER_ID}"
        )

    async def connect(self):
        print(f"🎧 Connecting → {self.ws_url}")
        self.ws = await websockets.connect(self.ws_url)
        print(f"✅ Connected (session={self.session_id})")

    async def send_mic_audio(self):
        loop = asyncio.get_running_loop()

        def callback(indata, frames, time, status):
            if status:
                print("⚠️", status)
            pcm_bytes = indata.tobytes()
            asyncio.run_coroutine_threadsafe(
                self.ws.send(pcm_bytes), loop
            )

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=FRAMES_PER_CHUNK,
            callback=callback,
        ):
            print("🎤 Microphone streaming... (Ctrl+C to stop)")
            while self.running:
                await asyncio.sleep(0.1)

    async def receive_responses(self):
        try:
            async for msg in self.ws:
                data = json.loads(msg)

                if data.get("is_text"):
                    if data.get("is_transcription"):
                        print(f"\n📝 YOU: {data['msg']}")
                    elif data.get("is_end"):
                        print("\n🏁 LLM finished\n")
                    else:
                        print(data["msg"], end="", flush=True)

                elif data.get("audio"):
                    print("🔊 [AUDIO CHUNK RECEIVED]")

                elif data.get("is_clear_event"):
                    print("\n🧹 CLEAR EVENT (user interrupted)\n")

        except websockets.exceptions.ConnectionClosed:
            print("🔌 Connection closed")

    async def run(self):
        await self.connect()
        await asyncio.gather(
            self.send_mic_audio(),
            self.receive_responses()
        )


async def main():
    tester = MicWebSocketTester()
    try:
        await tester.run()
    except KeyboardInterrupt:
        print("\n🛑 Stopping microphone")
        tester.running = False
        if tester.ws:
            await tester.ws.close()


if __name__ == "__main__":
    asyncio.run(main())
