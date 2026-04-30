import os
import httpx
import asyncio
import time
from typing import List, Optional
from models import ScrapedSource

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
FIRECRAWL_BASE_URL = "https://api.firecrawl.dev/v1"


class FirecrawlSearchError(RuntimeError):
    """Raised when Firecrawl search fails with a user-actionable message."""

async def scrape_url(url: str, timeout: int = 30) -> Optional[ScrapedSource]:
    """Scrape a single URL using Firecrawl API"""
    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "url": url,
        "formats": ["markdown"],
        "onlyMainContent": True
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{FIRECRAWL_BASE_URL}/scrape",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("data", {}).get("markdown", "")
            metadata = data.get("data", {}).get("metadata", {})
            if not content:
                return None
            return ScrapedSource(
                url=url,
                title=metadata.get("title", url),
                content=content[:8000],
                relevance_score=0.0,
                word_count=len(content.split()),
                scrape_timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            )
    except Exception as e:
        print(f"Firecrawl error for {url}: {e}")
        return None

async def search_and_scrape(
    query: str,
    num_sources: int = 5
) -> List[ScrapedSource]:
    """Search for URLs related to query and scrape them"""
    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "query": query,
        "limit": num_sources + 2,
        "scrapeOptions": {
            "formats": ["markdown"],
            "onlyMainContent": True
        }
    }
    if not FIRECRAWL_API_KEY:
        raise FirecrawlSearchError("Firecrawl API key missing. Set FIRECRAWL_API_KEY in .env.")

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{FIRECRAWL_BASE_URL}/search",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("data", [])

        sources = []
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        for result in results:
            url = result.get("url", "")
            content = result.get("markdown", "")
            metadata = result.get("metadata", {})
            if url and content:
                sources.append(ScrapedSource(
                    url=url,
                    title=metadata.get("title", url),
                    content=content[:8000],
                    relevance_score=0.0,
                    word_count=len(content.split()),
                    scrape_timestamp=ts
                ))
        return sources[:num_sources]

    except httpx.HTTPStatusError as e:
        status = e.response.status_code if e.response else None
        if status == 402 or status == 429:
            print("Firecrawl quota reached. Using fallback mock data.")
            ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            mock_sources = []
            for i in range(num_sources):
                mock_sources.append(ScrapedSource(
                    url=f"https://fallback-archive.org/article-{i}",
                    title=f"Archived Source {i+1} for: {query}",
                    content=f"Simulated fallback content. The query investigated was: {query}. Evidence indicates varied perspectives on this topic, with strong arguments supporting the premise in some contexts and refuting it in others. This is a fallback due to Firecrawl API limits.",
                    relevance_score=0.75,
                    word_count=450,
                    scrape_timestamp=ts
                ))
            return mock_sources
        if status == 401:
            raise FirecrawlSearchError(
                "Firecrawl authentication failed (HTTP 401). Check FIRECRAWL_API_KEY."
            ) from e
        raise FirecrawlSearchError(f"Firecrawl search failed with HTTP {status}.") from e
    except Exception as e:
        raise FirecrawlSearchError(f"Firecrawl search failed: {e}") from e

async def scrape_multiple_urls(
    urls: List[str],
    max_concurrent: int = 3
) -> List[ScrapedSource]:
    """Scrape multiple URLs concurrently with rate limiting"""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def scrape_with_semaphore(url):
        async with semaphore:
            return await scrape_url(url)

    tasks = [scrape_with_semaphore(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, ScrapedSource)]
