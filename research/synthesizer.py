import json
from typing import List
from models import ScrapedSource, ResearchReport, Citation
from server.llm import call_gemini_json
import uuid

async def synthesize(
    query: str,
    sources: List[ScrapedSource],
    session_id: str = None
) -> ResearchReport:
    """
    Use Gemini to synthesize a structured research report
    from multiple scraped sources.
    """
    sources_text = ""
    for i, source in enumerate(sources):
        sources_text += f"\n[Source {i+1}] {source.title}\nURL: {source.url}\n{source.content[:3000]}\n\n"

    system_prompt = """You are DeepTrace, an expert research synthesizer.
Your job is to synthesize information from multiple web sources into a
structured, accurate research report. Always cite sources by their index number.
Never hallucinate. If sources conflict, note the conflict."""

    prompt = f"""
Research Query: {query}

Sources:
{sources_text}

Produce a structured research report as JSON with exactly this format:
{{
  "summary": "2-3 sentence executive summary of findings",
  "key_findings": [
    "Finding 1 with source citation [1]",
    "Finding 2 with source citation [2]",
    "Finding 3 with source citation [3]"
  ],
  "citations": [
    {{"index": 1, "url": "source url", "title": "source title", "snippet": "key quote or fact from this source"}},
    {{"index": 2, "url": "source url", "title": "source title", "snippet": "key quote or fact from this source"}}
  ],
  "confidence_score": 0.85
}}

Include {len(sources)} citations — one per source used.
"""
    result = await call_gemini_json(prompt, system_prompt)
    data = json.loads(result)

    citations = [Citation(**c) for c in data.get("citations", [])]

    return ResearchReport(
        query=query,
        summary=data.get("summary", ""),
        key_findings=data.get("key_findings", []),
        citations=citations,
        sources_scraped=len(sources),
        confidence_score=data.get("confidence_score", 0.8),
        session_id=session_id or str(uuid.uuid4())
    )
