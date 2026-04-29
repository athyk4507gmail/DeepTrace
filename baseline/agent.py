"""
DeepTrace — Baseline Research Agent

A multi-step agent that runs the full research pipeline:
  search_and_scrape → aggregate_sources → synthesize → validate → submit
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")
load_dotenv()

from models import ResearchQuery, ResearchReport
from mcp.firecrawl_client import search_and_scrape
from research.aggregator import aggregate_sources
from research.synthesizer import synthesize
from research.citation_builder import validate_citations, format_report_markdown


MAX_STEPS = 5

ACTIONS = ["search", "score", "synthesize", "validate", "submit"]


def _log_step(step: int, action: str, result_summary: str) -> None:
    """Log each agent step with timestamp."""
    entry = {
        "step": step,
        "action": action,
        "result": result_summary,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    print(json.dumps(entry, ensure_ascii=False), flush=True)


async def run_baseline(
    query: str,
    max_sources: int = 5,
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Run the full DeepTrace research pipeline as a baseline agent.

    Steps:
        1. search  — call search_and_scrape to fetch live web sources
        2. score   — call aggregate_sources to score and filter by relevance
        3. synthesize — call synthesize to produce a structured report
        4. validate — call validate_citations to check report quality
        5. submit  — return the final ResearchReport

    Returns a dict with the full run metadata and final report.
    """
    session_id = session_id or str(uuid.uuid4())
    step = 0
    raw_sources = []
    scored_sources = []
    report: Optional[ResearchReport] = None
    validated = False
    history = []

    try:
        for action in ACTIONS:
            if step >= MAX_STEPS:
                break
            step += 1

            if action == "search":
                raw_sources = await search_and_scrape(
                    query=query,
                    num_sources=max_sources,
                )
                summary = f"Scraped {len(raw_sources)} raw sources"
                _log_step(step, action, summary)
                history.append({"step": step, "action": action, "result": summary})

                if not raw_sources:
                    _log_step(step, "abort", "No sources found — cannot proceed")
                    return {
                        "query": query,
                        "session_id": session_id,
                        "steps": step,
                        "history": history,
                        "report": None,
                        "error": "No sources scraped",
                    }

            elif action == "score":
                scored_sources = await aggregate_sources(
                    sources=raw_sources,
                    query=query,
                    min_sources=3,
                )
                summary = f"Scored and filtered to {len(scored_sources)} sources"
                _log_step(step, action, summary)
                history.append({"step": step, "action": action, "result": summary})

            elif action == "synthesize":
                report = await synthesize(
                    query=query,
                    sources=scored_sources,
                    session_id=session_id,
                )
                summary = (
                    f"Synthesized report: {len(report.key_findings)} findings, "
                    f"{len(report.citations)} citations, "
                    f"confidence={report.confidence_score:.2f}"
                )
                _log_step(step, action, summary)
                history.append({"step": step, "action": action, "result": summary})

            elif action == "validate":
                if report:
                    validated = validate_citations(report)
                    summary = f"Validation {'PASSED' if validated else 'FAILED'}"
                else:
                    validated = False
                    summary = "No report to validate"
                _log_step(step, action, summary)
                history.append({"step": step, "action": action, "result": summary})

            elif action == "submit":
                if report and validated:
                    summary = f"Submitted report (confidence={report.confidence_score:.2f})"
                    _log_step(step, action, summary)
                    history.append({"step": step, "action": action, "result": summary})
                else:
                    summary = "Cannot submit — validation failed or no report"
                    _log_step(step, action, summary)
                    history.append({"step": step, "action": action, "result": summary})

    except Exception as e:
        _log_step(step, "error", str(e))
        history.append({"step": step, "action": "error", "result": str(e)})
        return {
            "query": query,
            "session_id": session_id,
            "steps": step,
            "history": history,
            "report": None,
            "error": str(e),
        }

    return {
        "query": query,
        "session_id": session_id,
        "steps": step,
        "history": history,
        "report": report.model_dump() if report else None,
        "validated": validated,
        "markdown": format_report_markdown(report) if report else None,
    }


async def main() -> None:
    """CLI entry point — run baseline agent with a sample query."""
    import sys

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Latest AI safety regulations in EU 2025"
    print(f"\n{'='*60}")
    print(f"DeepTrace Baseline Agent")
    print(f"Query: {query}")
    print(f"{'='*60}\n")

    result = await run_baseline(query)

    print(f"\n{'='*60}")
    print(f"RESULT")
    print(f"{'='*60}")
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    asyncio.run(main())