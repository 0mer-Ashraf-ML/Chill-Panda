import logging
import time


class CustomFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None, style="%"):
        super().__init__(fmt, datefmt, style)
        self.last_log_time = None

    def formatTime(self, record, datefmt=None):
        # Elapsed time calculation
        current_time = time.perf_counter()
        if self.last_log_time is None:
            elapsed = 0
        else:
            elapsed = current_time - self.last_log_time
        self.last_log_time = current_time
        # Format the elapsed time and datetime
        elapsed_formatted = f"{elapsed:.4f}s"
        datetime_formatted = super().formatTime(record, datefmt)
        return f"{elapsed_formatted}: {datetime_formatted}"

    def format(self, record):
        record.elapsed = self.formatTime(record)
        return super().format(record)
