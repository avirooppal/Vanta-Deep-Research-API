from typing import List, Optional
from core.llm.client import LLMClient
from core.llm.types import Message as LLMMessage
from core.research.agents.tools import ToolRegistry
from core.research.agents.message_bus import MessageBus, global_bus
from core.research.memory import MemoryStore

class BaseAgent:
    def __init__(
        self, 
        name: str, 
        llm: LLMClient, 
        memory: Optional[MemoryStore] = None,
        bus: MessageBus = global_bus
    ):
        self.name = name
        self.llm = llm
        self.memory = memory
        self.bus = bus
        self.tool_registry = ToolRegistry()
        self.history: List[LLMMessage] = []

    def register_tool(self, tool):
        self.tool_registry.register(tool)

    async def _complete(self, messages, complexity: str = "high", timeout: int | None = None) -> "LLMResponse":
        """Wrapper that always injects agent_name for gateway routing."""
        return await self.llm.complete(
            messages, complexity=complexity, timeout=timeout, agent_name=self.name
        )

    async def run(self, initial_prompt: str, max_steps: int = 5) -> str:
        """
        Standard agent loop:
        1. Think/Observe (via LLM)
        2. Act (via Tools)
        3. Repeat until max_steps or final answer.
        """
        self.history.append(LLMMessage(role="user", content=initial_prompt))
        
        for step in range(max_steps):
            response = await self._complete(self.history)
            self.history.append(LLMMessage(role="assistant", content=response.content))
            return response.content
            
        return "Max steps reached without a final answer."
        
    async def publish(self, topic: str, payload: dict):
        payload["sender"] = self.name
        await self.bus.publish(topic, payload)

