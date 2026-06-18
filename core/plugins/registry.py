import os
import importlib
import inspect
from typing import Dict, Type
from core.plugins.base import BaseSearchPlugin, BaseExtractorPlugin

class PluginRegistry:
    def __init__(self):
        self.search_plugins: Dict[str, Type[BaseSearchPlugin]] = {}
        self.extractor_plugins: Dict[str, Type[BaseExtractorPlugin]] = {}

    def discover_plugins(self, plugin_dir: str = "plugins"):
        """
        Scan a directory for Python files and load plugin classes.
        Assumes the directory is a package (i.e. has __init__.py) or in PYTHONPATH.
        """
        if not os.path.exists(plugin_dir):
            return

        for filename in os.listdir(plugin_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name = filename[:-3]
                try:
                    module = importlib.import_module(f"{plugin_dir}.{module_name}")
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, BaseSearchPlugin) and obj is not BaseSearchPlugin:
                            instance = obj()
                            self.search_plugins[instance.name] = obj
                        elif issubclass(obj, BaseExtractorPlugin) and obj is not BaseExtractorPlugin:
                            instance = obj()
                            self.extractor_plugins[instance.name] = obj
                except Exception as e:
                    print(f"Error loading plugin {module_name}: {e}")

global_registry = PluginRegistry()
