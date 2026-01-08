# Chill Panda Backend API 🐼

Welcome to the Chill Panda backend! This repository powers a mindful AI companion focused on mental wellness, featuring real-time voice and text interactions.

## 🚀 Getting Started

### Prerequisites
- Python 3.11
- MongoDB
- API Keys: OpenAI, Deepgram, Minimax (optional)

### Installation
1. Clone the repository.
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment:
   Create a `.env` file based on `.env.example`.

5. Run the server:
   ```bash
   python main.py
   ```
   The API will be available at `http://localhost:3000`.

---

## 🎙️ Speech-to-Text (STT)

We use **Deepgram Nova-2** for high-accuracy, low-latency live transcription.

- **Model:** `nova-2-general`
- **Mechanism:** 
    - The backend subscribes to the WebSocket stream.
    - Raw audio chunks are forwarded to Deepgram's streaming API.
    - Transcripts are broadcasted to the system via the internal dispatcher (`FINAL_TRANSCRIPTION_CREATED`).
- **Features:** Smart formatting, punctuation, and Voice Activity Detection (VAD).

---

## 🔌 WebSocket Architecture

The primary real-time interface is via the `/ws/{source}` endpoint.

### Endpoints
- `ws://localhost:3000/ws/device`: Optimized for web clients (sends/receives JSON).
- `ws://localhost:3000/ws/phone`: Optimized for mobile clients (handles raw byte streaming).

### Connection Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `source` | Path | Yes | `device` or `phone`. |
| `language` | Query | No | Language code (e.g., `en`, `zh-HK`). Defaults to `en`. |
| `session_id`| Query | No | UUID for session continuity. |

### Quick Start Examples

**JavaScript (Browser):**
```javascript
const sessionId = crypto.randomUUID();
const ws = new WebSocket(`ws://localhost:3000/ws/device?language=en&session_id=${sessionId}`);

ws.onopen = () => console.log("Connected to Chill Panda!");
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.is_text) {
    console.log("AI says:", data.msg);
  } else {
    // Handle Base64 audio
    playAudio(data.audio);
  }
};
ws.onerror = (error) => console.error("WebSocket error:", error);
ws.onclose = (event) => console.log(`Connection closed: ${event.code}`);
```

**Python:**
```python
import asyncio
import websockets
import uuid

async def connect():
    session_id = str(uuid.uuid4())
    uri = f"ws://localhost:3000/ws/device?language=en&session_id={session_id}"
    
    async with websockets.connect(uri) as ws:
        print("Connected to Chill Panda!")
        async for message in ws:
            print(f"Received: {message}")

asyncio.run(connect())
```

### Data Protocol (Web/Device)
Clients should send and receive JSON objects.
- **Inbound (User Speech):** Raw bytes or JSON containing audio/text.
- **Outbound (AI Response):**
  ```json
  {
    "is_text": true,
    "msg": "Hello friend...",
    "is_transcription": false,
    "is_end": false
  }
  ```
- **Outbound (Audio):**
  ```json
  {
    "is_text": false,
    "audio": "BASE64_ENCODED_PCM_DATA"
  }
  ```

### Error Handling & Reconnection

| Close Code | Meaning | Recommended Action |
|------------|---------|-------------------|
| `1000` | Normal closure | No action needed |
| `1001` | Going away | Reconnect with same session_id |
| `1006` | Abnormal closure | Reconnect with exponential backoff |
| `1011` | Server error | Wait and retry |

**Reconnection Strategy:**
```javascript
let reconnectAttempts = 0;
const maxReconnectDelay = 30000;

function reconnect() {
  const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), maxReconnectDelay);
  setTimeout(() => {
    reconnectAttempts++;
    connect(); // Your connection function
  }, delay);
}
```

### Keepalive (Ping/Pong)
The server sends periodic WebSocket ping frames to maintain connection health. Clients should:
- Respond to ping frames automatically (most WebSocket libraries handle this).
- Consider the connection dead if no ping is received within **60 seconds**.
- Send application-level heartbeats if needed for NAT traversal.

---

## 🔊 Audio Specification

To ensure high-quality, real-time responses, we adhere to the following audio standards:

### Input (STT)
- **Preferred Sample Rate:** 16,000 Hz (16kHz).
- **Encoding:** Linear PCM (16-bit).
- **Channels:** 1 (Mono).

### Output (TTS - Minimax/Deepgram)
- **Sample Rate:** 16,000 Hz (16kHz).
- **Encoding:** 16-bit Signed Integer (PCM).
- **Bitrate:** 128 kbps.
- **Format delivered to client:** Base64 encoded PCM buffer (for web) or raw bytes (for phone).

---

## 📄 API Documentation

Full REST API documentation is available via Swagger at:
[http://localhost:3000/docs](http://localhost:3000/docs)

---

## ⚙️ Environment Variables

Create a `.env` file in the project root with the following variables:

### Required
| Variable | Description |
|----------|-------------|
| `PORT` | Server port (e.g., `3000`) |
| `OPENAI_API_KEY` | OpenAI API key for LLM and embeddings |
| `DEEPGRAM_API_KEY` | Deepgram API key for STT |
| `MONGODB_URI` | MongoDB connection string |
| `PINECONE_API_KEY` | Pinecone API key for RAG |

### Optional
| Variable | Default | Description |
|----------|---------|-------------|
| `MINIMAX_API_KEY` | - | Minimax API key for TTS |
| `ELEVENLABS_API_KEY` | - | ElevenLabs API key for TTS |
| `API_BASE_URL` | - | Base URL for external API calls |
| `MONGODB_DATABASE` | `chillpanda_db` | MongoDB database name |
| `MONGODB_CHATS_COLLECTION` | `chat_history` | Collection for chat history |
| `MONGODB_SESSIONS_COLLECTION` | `user_sessions` | Collection for sessions |
| `PINECONE_INDEX_NAME` | `chill-panda-index` | Pinecone index name |
| `PINECONE_ENVIRONMENT` | - | Pinecone environment |
| `EMBEDDING_MODEL` | `text-embedding-ada-002` | OpenAI embedding model |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI chat model |
| `RAG_SIMILARITY_THRESHOLD` | `0.7` | Similarity threshold for RAG |
| `MAX_HISTORY_MESSAGES` | `50` | Max messages in history |
| `CORS_ORIGINS` | `http://localhost:8501` | Allowed CORS origins (comma-separated) |
| `ENV` | `development` | Environment mode |
| `DEBUG` | `true` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## 🧠 Core Features
- **RAG System:** Context-aware responses using wisdom from "The Chill Panda" book.
- **Multi-Service TTS:** Support for Minimax, ElevenLabs, and Deepgram Aura.
- **Session Management:** Persistent chat history stored in MongoDB.
- **Mindful Interventions:** Biometric-aware responses (Chill Labs integration).

---
*Just chill. 🐼*
