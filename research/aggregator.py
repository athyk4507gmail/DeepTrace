import json
from typing import List
from models import ScrapedSource
from server.llm import call_gemini_json

async def score_relevance(
    sources: List[ScrapedSource],
    query: str
) -> List[ScrapedSource]:
    """Use Gemini to score how relevant each source is to the query"""
    system = "You are a research relevance scorer."
    prompt = f"""
Query: {query}

Rate each source's relevance to the query from 0.0 to 1.0.
Sources:
{json.dumps([{"url": s.url, "title": s.title, "snippet": s.content[:500]} for s in sources], indent=2)}

Respond with JSON array: [{{"url": "...", "score": 0.0}}]
"""
    try:
        result = await call_gemini_json(prompt, system)
        scores = json.loads(result)
        score_map = {item["url"]: item["score"] for item in scores}
        for source in sources:
            source.relevance_score = score_map.get(source.url, 0.5)
        return sorted(sources, key=lambda s: s.relevance_score, reverse=True)
    except Exception:
        return sources

async def aggregate_sources(
    sources: List[ScrapedSource],
    query: str,
    min_sources: int = 3
) -> List[ScrapedSource]:
    """
    Aggregate and filter sources.
    Enforces minimum source count constraint.
    """
    if not sources:
        raise ValueError("No sources scraped. Cannot proceed.")

    scored = await score_relevance(sources, query)
    filtered = [s for s in scored if s.relevance_score >= 0.3]

    # Enforce minimum — fall back to top scored if filter is too aggressive
    if len(filtered) < min_sources:
        filtered = scored[:min_sources]

    return filtered
