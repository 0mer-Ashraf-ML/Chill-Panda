from typing import Dict
from lib_infrastructure.helpers.custom_formatter import CustomFormatter
from lib_infrastructure.dispatcher import Dispatcher, MessageType
import logging , asyncio


class GlobalLoggerAsync:  # Changed to an Async version
    def __init__(
        self,
        guid,
        dispatcher: Dispatcher,
        pubsub_events: Dict[MessageType, bool],
        ignore_msg_events : Dict[MessageType , bool]
    ):
        self.guid = guid
        self.dispatcher = dispatcher
        self.pubsub_events = pubsub_events
        self.ignore_msg_events = ignore_msg_events
        self.loggers = {}

        format_string = (
            "%(levelname)s:\t%(elapsed)s\t%(event_name)s: %(message)s"
        )
        format_string_ignore_msg = (
            "%(levelname)s:\t%(elapsed)s\t%(event_name)s:"
        )


        for key in self.pubsub_events.keys():
            self.loggers[key] = logging.getLogger(key.name)
            self.loggers[key].setLevel(logging.INFO)

            handler = logging.StreamHandler()
            
            if self.ignore_msg_events.get( key , None ) != None : 

                handler.setFormatter(CustomFormatter(format_string_ignore_msg))
            else :  
                handler.setFormatter(CustomFormatter(format_string))

            self.loggers[key].addHandler(handler)
            self.loggers[key].propagate = False

    async def run_async(self):
        tasks = []
        for key in self.pubsub_events.keys():
            if self.pubsub_events[key]:
                #print(f"Creating logger for {key.name}")
                task = asyncio.create_task(self.log_messages(key))
                tasks.append(task)

        await asyncio.gather(*tasks)

    async def log_messages(self, message_type: MessageType):
        async with await self.dispatcher.subscribe(
            self.guid, message_type
        ) as subscriber:
            async for event in subscriber:
                # #print(
                #     "LOGGING",
                #     event.message.message_header.message_type,
                #     event.message.data,
                # )

                self.loggers[message_type].log(
                    logging.INFO,
                    event.message.data,
                    extra={"event_name": message_type.name},
                )


class DefaultLogger:
    def __init__(self, level=logging.DEBUG):
        self.level = level
        self.logger = logging.getLogger("default")
        self.logger.setLevel(self.level)
        self.logger.addHandler(logging.StreamHandler())
        # format to include the class name
        self.logger.handlers[0].setFormatter(
            logging.Formatter(
                "%(levelname)s:%(name)s: %(asctime)s - %(message)s"
            )
        )

    def log(self, level, message):
        self.logger.log(level, message)
