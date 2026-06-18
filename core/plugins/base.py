from typing import Any, Dict, List
from abc import ABC, abstractmethod

class BaseSearchPlugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the search plugin (e.g., 'google', 'arxiv')."""
        pass

    @abstractmethod
    async def search(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        """
        Execute a search.
        Returns a list of dictionaries with 'url', 'title', and optional 'snippet'.
        """
        pass

class BaseExtractorPlugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the extractor plugin (e.g., 'pdf', 'youtube')."""
        pass

    @abstractmethod
    async def extract(self, url: str) -> str:
        """
        Extract text content from the given URL.
        """
        pass
