import asyncio
import json
import wave
from dotenv import load_dotenv
import os
import websockets

load_dotenv()

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY").strip()
TEXT = "你好，我好唔開心。"  # "hi i am sad" in Cantonese (zh-HK)
OUTPUT_FILE = "zh-hk.wav"


async def main():
    audio_chunks = []

    ws = await websockets.connect(
        "wss://api.minimax.io/ws/v1/t2a_v2",
        additional_headers={"Authorization": f"Bearer {MINIMAX_API_KEY}"},
    )

    await ws.recv()  # connected_success

    await ws.send(json.dumps({
        "event": "task_start",
        "model": "speech-2.6-hd",
        "voice_setting": {"voice_id": "Cantonese_ProfessionalHost\uff08M)", "speed": 1.0, "vol": 1, "pitch": 0},
        "audio_setting": {"sample_rate": 16000, "bitrate": 128000, "format": "pcm", "channel": 1},
    }))

    await ws.recv()  # task_started

    await ws.send(json.dumps({"event": "task_continue", "text": TEXT}))
    await ws.send(json.dumps({"event": "task_finish"}))

    while True:
        msg = json.loads(await ws.recv())
        if msg.get("event") == "task_failed":
            print(f"❌ Task failed: {msg}")
            break
        if "data" in msg and "audio" in msg["data"]:
            audio_chunks.append(bytes.fromhex(msg["data"]["audio"]))
            print(f"Got chunk #{len(audio_chunks)}")
        if msg.get("is_final"):
            break

    await ws.close()

    if audio_chunks:
        with wave.open(OUTPUT_FILE, "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(16000)
            f.writeframes(b"".join(audio_chunks))
        print(f"✅ Saved to {OUTPUT_FILE}")
    else:
        print("No audio received.")


asyncio.run(main())
