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

    async def run(self, initial_prompt: str, max_steps: int = 5) -> str:
        """
        Standard agent loop:
        1. Think/Observe (via LLM)
        2. Act (via Tools)
        3. Repeat until max_steps or final answer.
        """
        self.history.append(LLMMessage(role="user", content=initial_prompt))
        
        for step in range(max_steps):
            response = await self.llm.complete(self.history)
            self.history.append(LLMMessage(role="assistant", content=response.content))
            
            # Simple heuristic for tool usage vs final answer:
            # If the response contains a tool call format, execute it.
            # For simplicity in this base implementation, we assume if the agent
            # doesn't use a tool, it has provided its final answer.
            # In a full implementation, you'd parse function calls/JSON here.
            
            # For now, we just return the raw text if no standard tool syntax is found.
            # (Subclasses can override this run loop for specialized extraction logic).
            return response.content
            
        return "Max steps reached without a final answer."
        
    async def publish(self, topic: str, payload: dict):
        payload["sender"] = self.name
        await self.bus.publish(topic, payload)
