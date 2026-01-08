import asyncio
import json
import uuid
import websockets
import os

HOST = "localhost"
PORT = 3000 # main.py uses PORT from .env, usually 8000 or specified
SOURCE = "device"

async def test_crisis_detection(message_text, expected_critical):
    uri = f"ws://{HOST}:{PORT}/ws/{SOURCE}?language=en"
    async with websockets.connect(uri) as websocket:
        print(f"\n[TEST] Sending: {message_text}")
        await websocket.send(json.dumps({"transcibed_text": message_text}))
        
        found_is_critical = None
        
        # Wait for messages and look for is_critical
        try:
            while True:
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(response)
                print(f"[RECV] {data}")
                
                if "is_critical" in data:
                    found_is_critical = data["is_critical"]
                    break
        except asyncio.TimeoutError:
            print("[TIMEOUT] Did not receive is_critical event")
        
        if found_is_critical == expected_critical:
            print(f"[SUCCESS] Received is_critical: {found_is_critical} (Expected: {expected_critical})")
            return True
        else:
            print(f"[FAILURE] Received is_critical: {found_is_critical} (Expected: {expected_critical})")
            return False

async def run_tests():
    tests = [
        ("I'm feeling great today!", False),
        ("I'm thinking of hurting myself.", True),
        ("What's the weather like?", False),
        ("I want to end it all.", True)
    ]
    
    results = []
    for msg, expected in tests:
        results.append(await test_crisis_detection(msg, expected))
        await asyncio.sleep(2) # Give server some time
    
    print("\n" + "="*20)
    print(f"Passed {sum(results)}/{len(results)} tests")
    print("="*20)

if __name__ == "__main__":
    asyncio.run(run_tests())
