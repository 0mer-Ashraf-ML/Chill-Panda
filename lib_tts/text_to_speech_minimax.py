import asyncio
import base64
import json
import websockets
from lib_infrastructure.dispatcher import (
    Dispatcher,
    Message,
    MessageHeader,
    MessageType,
)
from lib_infrastructure.helpers.realtime_observability import SessionObserver


class TextToSpeechMinimax:
    """Realtime TTS client with interruption handling and graceful degradation."""

    def __init__(
        self,
        guid,
        dispatcher: Dispatcher,
        api_key,
        voice_id="English_expressive_narrator",
        model="speech-2.6-hd",
        voice_tracker=None,
        observer: SessionObserver | None = None,
    ):
        self.guid = guid
        self.dispatcher = dispatcher
        self.api_key = api_key
        self.voice_tracker = voice_tracker
        self.observer = observer

        if voice_id == "zh-HK":
            voice_id = "cantonese_audio_ad39f71a-efe2-4881-858e-09b1c1b39ce4"
        elif voice_id == "zh-TW":
            voice_id = "hunyin_6"
        else:
            voice_id = "English_expressive_narrator"

        self.voice_id = voice_id
        self.model = model
        self.uri = "wss://api.minimax.io/ws/v1/t2a_v2"

        self.websocket = None
        self.is_connected = False
        self.is_task_started = False
        self.task_started_event = None
        self.connection_lock = asyncio.Lock()
        self.interrupt_lock = asyncio.Lock()

        self.audio_listener_task = None
        self.buffer_timer = None
        self.buffer_lock = asyncio.Lock()

        self.use_smart_buffering = True
        self.word_buffer = ""
        self.min_buffer_size = 8
        self.max_buffer_time = 2.5
        self.is_flushing = False
        self.is_interrupted = False
        self._suppress_audio_complete = False

        self.audio_settings = {
            "sample_rate": 16000,
            "bitrate": 128000,
            "format": "pcm",
            "channel": 1,
        }
        self.voice_settings = {
            "voice_id": self.voice_id,
            "speed": 1.0,
            "vol": 1,
            "pitch": 0,
            "english_normalization": False,
        }

    async def connect_websocket(self):
        async with self.connection_lock:
            if self.is_connected:
                return True

            if self.websocket:
                try:
                    await self.websocket.close()
                except Exception:
                    pass
                self.websocket = None

            try:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                self.websocket = await websockets.connect(
                    self.uri,
                    additional_headers=headers,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10,
                )

                response = json.loads(await asyncio.wait_for(self.websocket.recv(), timeout=10.0))
                if response.get("event") != "connected_success":
                    return False

                self.is_connected = True
                self.is_task_started = False
                self.task_started_event = asyncio.Event()
                if self.observer:
                    self.observer.log("tts", "connected")

                if self.audio_listener_task is None or self.audio_listener_task.done():
                    self.audio_listener_task = asyncio.create_task(self._listen_for_audio())
                return True
            except Exception as e:
                self.is_connected = False
                if self.observer:
                    self.observer.log("tts", "connect_error", error=str(e))
                return False

    async def ensure_connection(self):
        if self.is_connected:
            return True
        if await self.connect_websocket():
            return True
        await asyncio.sleep(0.5)
        return await self.connect_websocket()

    async def _start_task(self):
        if self.is_task_started:
            return True
        if not self.websocket:
            return False

        try:
            self.task_started_event = self.task_started_event or asyncio.Event()
            self.task_started_event.clear()
            await asyncio.wait_for(
                self.websocket.send(
                    json.dumps(
                        {
                            "event": "task_start",
                            "model": self.model,
                            "voice_setting": self.voice_settings,
                            "audio_setting": self.audio_settings,
                        }
                    )
                ),
                timeout=5.0,
            )
            await asyncio.wait_for(self.task_started_event.wait(), timeout=10.0)
            return True
        except Exception as e:
            if self.observer:
                self.observer.log("tts", "task_start_error", error=str(e))
            return False

    async def _listen_for_audio(self):
        while True:
            try:
                if not self.is_connected or not self.websocket:
                    await asyncio.sleep(0.1)
                    continue

                message = await asyncio.wait_for(self.websocket.recv(), timeout=30.0)
                response = json.loads(message)
                event_type = response.get("event")

                if event_type == "task_started":
                    self.is_task_started = True
                    self._suppress_audio_complete = False
                    if self.task_started_event:
                        self.task_started_event.set()
                    continue

                if event_type == "task_failed":
                    self.is_task_started = False
                    if self.observer:
                        self.observer.log("tts", "task_failed", payload=str(response)[:200])
                    continue

                if self.is_interrupted:
                    continue

                audio_hex = response.get("data", {}).get("audio")
                if audio_hex:
                    audio_bytes = bytes.fromhex(audio_hex)
                    base64_audio = base64.b64encode(audio_bytes).decode("utf-8")

                    if self.voice_tracker:
                        allowed = await self.voice_tracker.track_audio_chunk(base64_audio)
                        if not allowed:
                            await self._interrupt_generation()
                            continue

                    await self.dispatcher.broadcast(
                        self.guid,
                        Message(
                            MessageHeader(MessageType.CALL_WEBSOCKET_PUT),
                            data={"is_text": False, "audio": base64_audio},
                        ),
                    )
                    if self.observer:
                        self.observer.mark("first_audio_out")
                        self.observer.log(
                            "tts",
                            "audio_chunk_out",
                            latency_first_audio_ms=self.observer.latency_ms(
                                "first_llm_token_out", "first_audio_out"
                            ),
                        )

                if response.get("is_final"):
                    self.is_task_started = False
                    if self.task_started_event:
                        self.task_started_event.clear()
                    if not self.is_interrupted and not self._suppress_audio_complete:
                        await self.dispatcher.broadcast(
                            self.guid,
                            Message(
                                MessageHeader(MessageType.CALL_WEBSOCKET_PUT),
                                data={"audio_is_end": True},
                            ),
                        )
            except asyncio.TimeoutError:
                if self.websocket and self.is_connected:
                    try:
                        await self.websocket.ping()
                    except Exception:
                        self.is_connected = False
                continue
            except websockets.exceptions.ConnectionClosed:
                self.is_connected = False
                self.is_task_started = False
                if self.observer:
                    self.observer.log("tts", "connection_closed")
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                if self.observer:
                    self.observer.log("tts", "listener_error", error=str(e))
                await asyncio.sleep(0.3)

    async def send_text(self, text: str):
        if not text.strip() or self.is_interrupted:
            return

        if self.voice_tracker and not self.voice_tracker.is_voice_enabled():
            return

        if not await self.ensure_connection():
            raise RuntimeError("tts_connection_failed")

        if not await self._start_task():
            raise RuntimeError("tts_task_start_failed")

        clean_text = text.replace("*", "").strip()
        await asyncio.wait_for(
            self.websocket.send(json.dumps({"event": "task_continue", "text": clean_text})),
            timeout=5.0,
        )
        if self.observer:
            self.observer.log("tts", "text_sent", chars=len(clean_text))

    async def add_word_to_buffer(self, word: str):
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
            if self._is_sentence_end(self.word_buffer) and len(self.word_buffer.strip()) >= 10:
                should_send = True
                reason = "sentence_end"
            elif word_count >= self.min_buffer_size:
                should_send = True
                reason = "buffer_size"

            if should_send and not self.is_flushing:
                await self._flush_buffer_internal(reason)
            else:
                self._schedule_buffer_flush()

    async def _flush_buffer_internal(self, reason: str = ""):
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
            await self.send_text(buffer_content)
            if self.observer:
                self.observer.log("tts", "buffer_flushed", reason=reason)
        finally:
            self.is_flushing = False

    async def _flush_buffer(self, reason: str = ""):
        async with self.buffer_lock:
            await self._flush_buffer_internal(reason)

    def _schedule_buffer_flush(self):
        if self.buffer_timer:
            self.buffer_timer.cancel()

        async def delayed_flush():
            await asyncio.sleep(self.max_buffer_time)
            if self.word_buffer.strip() and not self.is_interrupted and not self.is_flushing:
                await self._flush_buffer("timer")

        self.buffer_timer = asyncio.create_task(delayed_flush())

    def _is_sentence_end(self, text: str) -> bool:
        import re

        return bool(re.search(r"[.!?]\s*$", text.strip()))

    async def flush_and_end(self):
        async with self.buffer_lock:
            if self.word_buffer.strip() and not self.is_interrupted:
                await self._flush_buffer_internal("final")

        if self.is_connected and self.websocket and self.is_task_started:
            try:
                await asyncio.wait_for(
                    self.websocket.send(json.dumps({"event": "task_finish"})), timeout=3.0
                )
                self.is_task_started = False
                if self.task_started_event:
                    self.task_started_event.clear()
            except Exception as e:
                if self.observer:
                    self.observer.log("tts", "task_finish_error", error=str(e))

    async def _interrupt_generation(self):
        async with self.interrupt_lock:
            self.is_interrupted = True
            self._suppress_audio_complete = True
            async with self.buffer_lock:
                self.word_buffer = ""

            if self.buffer_timer:
                self.buffer_timer.cancel()
                self.buffer_timer = None

            if self.is_connected and self.websocket and self.is_task_started:
                try:
                    await asyncio.wait_for(
                        self.websocket.send(json.dumps({"event": "task_finish"})), timeout=3.0
                    )
                    self.is_task_started = False
                    if self.task_started_event:
                        self.task_started_event.clear()
                except Exception as e:
                    if self.observer:
                        self.observer.log("tts", "interrupt_error", error=str(e))

            await self.dispatcher.broadcast(
                self.guid,
                Message(
                    MessageHeader(MessageType.CLEAR_EXISTING_BUFFER),
                    data={"source": "tts_interrupt"},
                ),
            )

    async def close_connection(self):
        if self.audio_listener_task:
            self.audio_listener_task.cancel()
            try:
                await self.audio_listener_task
            except asyncio.CancelledError:
                pass

        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass

        self.is_connected = False
        self.is_task_started = False
        if self.buffer_timer:
            self.buffer_timer.cancel()
            self.buffer_timer = None

    async def handle_llm_generated_text(self):
        async with await self.dispatcher.subscribe(self.guid, MessageType.LLM_GENERATED_TEXT) as subscriber:
            async for event in subscriber:
                words = event.message.data.get("words")
                if not words:
                    continue
                if not event.message.data.get("is_audio_required"):
                    continue

                self.is_interrupted = False
                if self.use_smart_buffering:
                    await self.add_word_to_buffer(words)
                else:
                    await self.send_text(words)

    async def handle_tts_flush(self):
        async with await self.dispatcher.subscribe(self.guid, MessageType.TTS_FLUSH) as subscriber:
            async for _event in subscriber:
                await self.flush_and_end()

    async def handle_user_interruption(self):
        async with await self.dispatcher.subscribe(self.guid, MessageType.FINAL_TRANSCRIPTION_CREATED) as subscriber:
            async for _event in subscriber:
                await self._interrupt_generation()

    async def run_async(self):
        await self.connect_websocket()

        try:
            await asyncio.gather(
                self.handle_llm_generated_text(),
                self.handle_tts_flush(),
                self.handle_user_interruption(),
            )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            if self.observer:
                self.observer.log("tts", "fatal_error", error=str(e))
            raise
        finally:
            await self.close_connection()
