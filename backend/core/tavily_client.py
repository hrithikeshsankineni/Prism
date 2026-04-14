import logging
from typing import Any, Dict, List, Optional

from tavily import TavilyClient as _TavilyClient

from backend.config import settings

logger = logging.getLogger(__name__)


class TavilySearchClient:
    """Wrapper around Tavily search with error handling.

    Returns empty results on failure instead of raising exceptions.
    """

    def __init__(self) -> None:
        self._client = _TavilyClient(api_key=settings.tavily_api_key)

    def search(
        self,
        query: str,
        topic: str = "general",
        max_results: int = 5,
        search_depth: str = "basic",
        include_answer: bool = True,
        include_domains: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Execute a Tavily search. Returns raw response dict."""
        try:
            kwargs: Dict[str, Any] = {
                "query": query,
                "topic": topic,
                "max_results": max_results,
                "search_depth": search_depth,
                "include_answer": include_answer,
            }
            if include_domains:
                kwargs["include_domains"] = include_domains

            return self._client.search(**kwargs)

        except Exception as e:
            logger.error(f"Tavily search failed for '{query}': {e}")
            return {"results": [], "answer": None}

    def search_news(
        self,
        query: str,
        max_results: int = 5,
    ) -> Dict[str, Any]:
        """Convenience method for news-focused searches."""
        return self.search(
            query=query,
            topic="news",
            max_results=max_results,
        )


tavily_client = TavilySearchClient()
