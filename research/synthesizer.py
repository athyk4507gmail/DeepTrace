import re
import json
from typing import List, Optional
from models import ScrapedSource, ResearchReport, Citation, FindingConfidence
from server.llm import call_gemini_json, call_gemini
import uuid


def safe_json_parse(text: str) -> dict:
    text = text.strip()
    # Strip markdown fences
    text = re.sub(r'^```json\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^```\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'```$', '', text, flags=re.MULTILINE)
    text = text.strip()
    # Fix trailing commas
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)
    # Fix single quotes
    text = text.replace("'", '"')
    try:
        return json.loads(text)
    except:
        return None


async def decompose_query(query: str) -> List[str]:
    """Break a query into 3 sub-questions for multi-step research."""
    prompt = f"""Break this research query into exactly 3 focused sub-questions that would help thoroughly answer the original query.

Original query: {query}

Respond with a JSON array of 3 strings. Example:
["sub-question 1", "sub-question 2", "sub-question 3"]
"""
    try:
        result = await call_gemini_json(prompt, "You are a research query planner.")
        subs = safe_json_parse(result)
        if isinstance(subs, list) and len(subs) >= 3:
            return subs[:3]
    except Exception:
        pass
    return [query]


async def synthesize(
    query: str,
    sources: List[ScrapedSource],
    session_id: str = None,
    previous_context: str = ""
) -> ResearchReport:
    """
    Use LLM to synthesize a structured research report
    from multiple scraped sources.
    """
    sources_text = ""
    for i, source in enumerate(sources):
        sources_text += f"\n[Source {i+1}] {source.title}\nURL: {source.url}\n{source.content[:3000]}\n\n"

    context_block = ""
    if previous_context:
        context_block = f"\nPrevious research context:\n{previous_context}\n"

    system_prompt = """You are a research synthesis engine.
You MUST respond with ONLY a valid JSON object.
No explanation. No markdown. No backticks. No preamble.
No trailing commas. Use double quotes only.
Start your response with { and end with }
If the topic is a simple factual query (person, place, number),
still return the same JSON structure but keep summary concise."""

    prompt = f"""
Research Query: {query}
{context_block}
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
  "conflicts": ["Any conflicts between sources, or empty array if none"],
  "citations": [
    {{"index": 1, "url": "source url", "title": "source title", "snippet": "key quote or fact from this source"}},
    {{"index": 2, "url": "source url", "title": "source title", "snippet": "key quote or fact from this source"}}
  ],
  "confidence_score": 0.85
}}

Include {len(sources)} citations — one per source used.
If sources conflict on any point, add details to the "conflicts" array.
"""
    llm_response = await call_gemini_json(prompt, system_prompt)

    # Attempt 1: parse JSON normally
    parsed = safe_json_parse(llm_response)

    # Attempt 2: if failed, ask LLM to fix its own output
    if parsed is None:
        fix_prompt = f"""The following text is broken JSON. 
Fix it and return ONLY valid JSON, nothing else:

{llm_response[:2000]}"""
        fixed_response = await call_gemini(fix_prompt,
            system_prompt="Return only valid JSON. No markdown.")
        parsed = safe_json_parse(fixed_response)

    # Attempt 3: if still failed, build report from raw text
    if parsed is None:
        parsed = {
            "summary": llm_response[:600],
            "key_findings": [
                line.strip("- •*") for line in
                llm_response.split('\n')
                if line.strip() and len(line.strip()) > 20
            ][:5],
            "confidence_score": 0.6,
            "suggested_followups": [
                f"Tell me more about {query}",
                f"Latest news on {query}",
                f"Key statistics about {query}"
            ],
            "conflicts": []
        }

    citations = []
    for c in parsed.get("citations", []):
        try:
            citations.append(Citation(**c))
        except Exception:
            pass
    
    conflicts = parsed.get("conflicts", [])
    if isinstance(conflicts, str):
        conflicts = [conflicts] if conflicts else []
    if conflicts and len(conflicts) == 1 and not conflicts[0]:
        conflicts = []

    # Fallback: build citations from scraped sources if LLM didn't provide any
    if not citations:
        citations = [
            Citation(index=i+1, url=s.url, title=s.title, snippet=s.content[:150])
            for i, s in enumerate(sources) if hasattr(s, 'url') and s.url
        ]

    report = ResearchReport(
        query=query,
        summary=parsed.get("summary", ""),
        key_findings=parsed.get("key_findings", []),
        citations=citations,
        conflicts=conflicts,
        sources_scraped=len(sources),
        confidence_score=parsed.get("confidence_score", 0.8),
        session_id=session_id or str(uuid.uuid4())
    )
    return report


async def rate_confidence(report: ResearchReport) -> ResearchReport:
    """Rate each finding's confidence and provide overall explanation."""
    findings_text = "\n".join(f"{i+1}. {f}" for i, f in enumerate(report.key_findings))

    prompt = f"""Analyze these research findings for reliability:

{findings_text}

Sources used: {report.sources_scraped}

For each finding, rate confidence 1-10 and classify as HIGH (8-10), MED (5-7), or LOW (1-4).
Count how many distinct sources back each finding based on citation references.

Respond with JSON:
{{
  "findings": [
    {{"finding": "finding text", "score": 8, "confidence": "HIGH", "source_count": 3}},
  ],
  "overall_confidence": 0.85,
  "explanation": "Brief explanation of overall confidence level"
}}
"""
    try:
        result = await call_gemini_json(prompt, "You are a research quality assessor. Respond with ONLY valid JSON.")
        data = safe_json_parse(result)
        
        if data:
            confidences = []
            for item in data.get("findings", []):
                confidences.append(FindingConfidence(
                    finding=item.get("finding", ""),
                    score=item.get("score", 5),
                    confidence=item.get("confidence", "MED"),
                    source_count=item.get("source_count", 1)
                ))
            
            report.finding_confidences = confidences
            report.confidence_score = data.get("overall_confidence", report.confidence_score)
            report.confidence_explanation = data.get("explanation", "")
    except Exception as e:
        print(f"Confidence rating error: {e}")
    
    if not report.finding_confidences:
        report.finding_confidences = [
            FindingConfidence(finding=f, score=5, confidence="MED", source_count=1)
            for f in report.key_findings
        ]
        report.confidence_explanation = report.confidence_explanation or "Confidence could not be fully assessed."
    
    return report


async def generate_followups(query: str, report: ResearchReport) -> List[str]:
    """Generate 3 follow-up research questions."""
    prompt = f"""Given this research query and findings, suggest 3 follow-up research questions the user might want to explore next.

Original query: {query}
Summary: {report.summary}

Respond with a JSON array of exactly 3 strings:
["follow-up question 1", "follow-up question 2", "follow-up question 3"]
"""
    try:
        result = await call_gemini_json(prompt, "You are a research advisor. Respond with ONLY a JSON array.")
        followups = safe_json_parse(result)
        if isinstance(followups, list):
            return followups[:3]
    except Exception as e:
        print(f"Follow-up generation error: {e}")
    return [f"Tell me more about {query}", f"Latest developments in {query}", f"Key statistics about {query}"]


async def self_reflect(query: str, report: ResearchReport) -> dict:
    """
    Self-reflection: ask the LLM if the query is fully answered.
    Returns {"fully_answered": bool, "suggested_search": str or None}
    """
    prompt = f"""Given this research report, evaluate if the original query is fully answered.

Original query: {query}
Summary: {report.summary}
Key findings count: {len(report.key_findings)}

Is the original query fully and comprehensively answered?
If NOT, what single additional search query would most improve the answer?

Respond with JSON:
{{
  "fully_answered": true,
  "reason": "brief explanation",
  "suggested_search": null
}}
"""
    try:
        result = await call_gemini_json(prompt, "You are a research completeness evaluator. Respond with ONLY valid JSON.")
        data = safe_json_parse(result)
        if data:
            return data
    except Exception:
        pass
    return {"fully_answered": True, "reason": "Could not evaluate", "suggested_search": None}
