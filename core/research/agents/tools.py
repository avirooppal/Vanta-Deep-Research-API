from typing import Any, Callable, Dict, List, Optional
import inspect

class Tool:
    def __init__(self, name: str, description: str, func: Callable):
        self.name = name
        self.description = description
        self.func = func
        self.signature = inspect.signature(func)

    def execute(self, **kwargs) -> Any:
        return self.func(**kwargs)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a format suitable for LLM consumption (e.g. OpenAI tools format)."""
        parameters = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        for param_name, param in self.signature.parameters.items():
            if param_name == "self":
                continue
            
            param_type = "string" # Default
            if param.annotation == int:
                param_type = "integer"
            elif param.annotation == bool:
                param_type = "boolean"
            elif param.annotation == float:
                param_type = "number"
            elif hasattr(param.annotation, "__origin__") and param.annotation.__origin__ == list:
                param_type = "array"
                
            parameters["properties"][param_name] = {"type": param_type}
            if param.default == inspect.Parameter.empty:
                parameters["required"].append(param_name)
                
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": parameters
            }
        }

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)
        
    def get_all_tools_dict(self) -> List[Dict[str, Any]]:
        return [tool.to_dict() for tool in self._tools.values()]
