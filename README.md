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

## 🧠 Core Features
- **RAG System:** Context-aware responses using wisdom from "The Chill Panda" book.
- **Multi-Service TTS:** Support for Minimax, ElevenLabs, and Deepgram Aura.
- **Session Management:** Persistent chat history stored in MongoDB.
- **Mindful Interventions:** Biometric-aware responses (Chill Labs integration).

---
*Just chill. 🐼*
