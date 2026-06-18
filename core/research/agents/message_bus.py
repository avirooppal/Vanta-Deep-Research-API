import asyncio
from typing import Dict, List, Callable, Awaitable

class MessageBus:
    """
    A simple in-memory message bus for cross-agent communication.
    In a distributed environment, this would be backed by Redis Pub/Sub or Kafka.
    """
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[dict], Awaitable[None]]]] = {}

    def subscribe(self, topic: str, callback: Callable[[dict], Awaitable[None]]):
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(callback)

    async def publish(self, topic: str, payload: dict):
        if topic in self._subscribers:
            tasks = []
            for callback in self._subscribers[topic]:
                tasks.append(callback(payload))
            if tasks:
                await asyncio.gather(*tasks)

# Global singleton for local execution
global_bus = MessageBus()
