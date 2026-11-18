from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv


class TavilySearchProvider:
    """Optional live web search provider used to ground current assessments."""

    def __init__(self) -> None:
        load_dotenv()
        self.api_key = os.getenv("TAVILY_API_KEY") or os.getenv("TVILI_API")
        self._client: Any = None

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _get_client(self) -> Any:
        if self._client is None:
            if not self.api_key:
                raise RuntimeError("Tavily API key is not configured")
            from tavily import TavilyClient

            self._client = TavilyClient(api_key=self.api_key)
        return self._client

    def search(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        """Return normalized live citations; failures are isolated from assessments."""
        if not query or not self.enabled:
            return []

        try:
            response = self._get_client().search(
                query,
                search_depth="advanced",
                topic="news",
                max_results=limit,
                include_answer=False,
                include_raw_content=False,
            )
        except Exception:
            return []

        results = response.get("results", []) if isinstance(response, dict) else []
        citations: list[dict[str, Any]] = []
        for result in results[:limit]:
            if not isinstance(result, dict) or not result.get("url"):
                continue
            citations.append(
                {
                    "title": result.get("title") or result.get("url"),
                    "source": result.get("url"),
                    "url": result.get("url"),
                    "text": result.get("content", ""),
                    "snippet": result.get("content", "")[:500],
                    "score": result.get("score"),
                    "provider": "tavily",
                }
            )
        return citations
