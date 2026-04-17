import json
import time


class SessionObserver:
    """Small structured logger + latency tracker for realtime sessions."""

    def __init__(self, session_id: str, user_id: str, source: str):
        self.session_id = session_id
        self.user_id = user_id
        self.source = source
        self._marks = {}
        self._started = time.perf_counter()

    def log(self, component: str, event: str, **fields):
        payload = {
            "ts": time.time(),
            "session_id": self.session_id,
            "user_id": self.user_id,
            "source": self.source,
            "component": component,
            "event": event,
            "uptime_ms": int((time.perf_counter() - self._started) * 1000),
            **fields,
        }
        print(json.dumps(payload, ensure_ascii=True))

    def mark(self, name: str):
        if name not in self._marks:
            self._marks[name] = time.perf_counter()

    def latency_ms(self, start_mark: str, end_mark: str) -> int | None:
        start = self._marks.get(start_mark)
        end = self._marks.get(end_mark)
        if start is None or end is None:
            return None
        return int((end - start) * 1000)

