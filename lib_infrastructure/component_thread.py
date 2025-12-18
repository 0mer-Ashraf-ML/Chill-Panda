import asyncio
import threading
from abc import ABC, abstractmethod
from lib_infrastructure.dispatcher import Dispatcher


class ComponentThread(threading.Thread, ABC):
    def __init__(self, dispatcher: Dispatcher):
        super().__init__()
        self.dispatcher = dispatcher
        self.isDaemon = True

    @abstractmethod
    def run(self):
        pass


class ComponentThreadAsync(ComponentThread, ABC):
    def __init__(self, dispatcher: Dispatcher):
        super().__init__(dispatcher=dispatcher)
        self.loop = asyncio.new_event_loop()

    def run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.run_async())

    @abstractmethod
    async def run_async(self):
        pass
