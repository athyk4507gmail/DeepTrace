import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env BEFORE any module imports that read env vars
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()

import uuid
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from models import ResearchQuery, ResearchReport
from mcp.firecrawl_client import search_and_scrape
from research.aggregator import aggregate_sources
from research.synthesizer import synthesize
from research.citation_builder import format_report_markdown, validate_citations
from memory.supabase_client import save_report, get_session_history, clear_session
import json

app = FastAPI(
    title="DeepTrace — Autonomous Deep Research Agent",
    description="Multi-step AI research agent using Firecrawl MCP and Gemini",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("server/chat_ui.html") as f:
        return f.read()

@app.get("/health")
async def health():
    return {"status": "ok", "agent": "DeepTrace", "version": "1.0.0"}

@app.post("/research", response_model=ResearchReport)
async def run_research(query: ResearchQuery):
    """
    Main endpoint — takes a natural language query,
    scrapes 3-5 live sources, synthesizes, returns cited report.
    """
    try:
        # Step 1: Scrape live sources via Firecrawl MCP
        raw_sources = await search_and_scrape(
            query=query.query,
            num_sources=query.max_sources
        )
        if not raw_sources:
            raise HTTPException(
                status_code=502,
                detail="No sources could be scraped. Try a different query."
            )

        # Step 2: Aggregate and score sources
        sources = await aggregate_sources(
            sources=raw_sources,
            query=query.query,
            min_sources=3
        )

        # Step 3: Synthesize report using Gemini
        session_id = query.session_id or str(uuid.uuid4())
        report = await synthesize(
            query=query.query,
            sources=sources,
            session_id=session_id
        )

        # Step 4: Validate citations
        if not validate_citations(report):
            raise HTTPException(
                status_code=500,
                detail="Report validation failed — insufficient sources."
            )

        # Step 5: Save to memory if enabled
        if query.use_memory:
            await save_report(report)

        return report

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/research/stream")
async def stream_research(query: str, max_sources: int = 5):
    """
    Streaming endpoint — sends progress updates as SSE
    while research is happening.
    """
    async def event_stream():
        try:
            yield f"data: {json.dumps({'status': 'searching', 'message': 'Searching live web sources...'})}\n\n"
            raw_sources = await search_and_scrape(query=query, num_sources=max_sources)

            yield f"data: {json.dumps({'status': 'scraping', 'message': f'Scraped {len(raw_sources)} sources. Scoring relevance...'})}\n\n"
            sources = await aggregate_sources(raw_sources, query, min_sources=3)

            yield f"data: {json.dumps({'status': 'synthesizing', 'message': f'Synthesizing across {len(sources)} sources with Gemini...'})}\n\n"
            report = await synthesize(query=query, sources=sources)

            yield f"data: {json.dumps({'status': 'done', 'report': report.model_dump()})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get research history for a session"""
    history = await get_session_history(session_id)
    return {"session_id": session_id, "history": history}

@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Clear a research session"""
    await clear_session(session_id)
    return {"message": f"Session {session_id} cleared"}

@app.get("/tasks")
async def list_tasks():
    """OpenEnv-compatible tasks endpoint"""
    return {
        "agent": "DeepTrace",
        "tasks": ["deep_research"],
        "actions": ["search_and_scrape", "aggregate", "synthesize", "cite"]
    }