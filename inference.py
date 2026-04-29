"""
DeepTrace — Inference Test Runner

Runs 3 test research queries against the running DeepTrace server
and prints structured JSON logs for each step.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent
load_dotenv(_ROOT / ".env")
load_dotenv()

SERVER_URL = "http://localhost:7860"

TEST_QUERIES = [
    "What are the latest AI safety regulations in EU 2025?",
    "Top open source LLMs in 2025 and their benchmarks",
    "Recent breakthroughs in quantum computing 2025",
]


def log(entry: dict) -> None:
    """Print a structured JSON log line."""
    print(json.dumps(entry, ensure_ascii=False), flush=True)


async def run_single_query(client: httpx.AsyncClient, query: str) -> dict:
    """Run a single research query against the /research endpoint."""
    log({"type": "START", "query": query})

    payload = {
        "query": query,
        "max_sources": 5,
        "use_memory": False,
    }

    try:
        response = await client.post(
            f"{SERVER_URL}/research",
            json=payload,
            timeout=120.0,
        )
        response.raise_for_status()
        report = response.json()

        log({
            "type": "STEP",
            "status": "scraping",
            "sources": report.get("sources_scraped", 0),
        })

        log({
            "type": "END",
            "sources_scraped": report.get("sources_scraped", 0),
            "confidence": report.get("confidence_score", 0.0),
            "findings": len(report.get("key_findings", [])),
            "citations": len(report.get("citations", [])),
        })

        return report

    except httpx.HTTPStatusError as e:
        log({
            "type": "ERROR",
            "query": query,
            "status_code": e.response.status_code,
            "detail": e.response.text,
        })
        return {}
    except Exception as e:
        log({
            "type": "ERROR",
            "query": query,
            "detail": str(e),
        })
        return {}


async def main() -> None:
    """Run all test queries sequentially."""
    results = []

    async with httpx.AsyncClient() as client:
        # Verify server is healthy first
        try:
            health = await client.get(f"{SERVER_URL}/health", timeout=10.0)
            health.raise_for_status()
            log({"type": "HEALTH", "status": health.json()})
        except Exception as e:
            log({"type": "ERROR", "detail": f"Server not reachable: {e}"})
            sys.exit(1)

        # Run each test query
        for query in TEST_QUERIES:
            report = await run_single_query(client, query)
            results.append(report)

    # Save results to file
    output_path = _ROOT / "inference_results.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    log({"type": "COMPLETE", "total_queries": len(TEST_QUERIES), "output": str(output_path)})


if __name__ == "__main__":
    asyncio.run(main())
