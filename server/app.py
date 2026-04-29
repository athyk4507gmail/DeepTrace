import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env BEFORE any module imports that read env vars
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()

import uuid
import json
import time
import asyncio
from fastapi import FastAPI, HTTPException, Query as QueryParam
from fastapi.responses import HTMLResponse, StreamingResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from models import ResearchQuery, ResearchReport
from mcp.firecrawl_client import search_and_scrape, FirecrawlSearchError
from research.aggregator import aggregate_sources
from research.synthesizer import (
    synthesize, decompose_query, rate_confidence,
    generate_followups, self_reflect
)
from research.citation_builder import format_report_markdown, validate_citations
from memory.supabase_client import (
    save_report, get_session_history, clear_session,
    get_recent_sessions, get_all_sessions, clear_all_sessions
)

app = FastAPI(
    title="DeepTrace — Autonomous Deep Research Agent",
    description="Multi-step AI research agent with query decomposition, confidence reasoning, and self-reflection",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Depth configuration
DEPTH_CONFIG = {
    "quick":    {"sources": 3,  "decompose": False},
    "standard": {"sources": 5,  "decompose": False},
    "deep":     {"sources": 10, "decompose": True},
}

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("server/chat_ui.html") as f:
        return f.read()

@app.get("/health")
async def health():
    return {"status": "ok", "agent": "DeepTrace", "version": "2.0.0"}

@app.post("/research", response_model=ResearchReport)
async def run_research(query: ResearchQuery):
    """Main endpoint — full research pipeline."""
    try:
        cfg = DEPTH_CONFIG.get(query.depth, DEPTH_CONFIG["standard"])
        raw_sources = await search_and_scrape(query=query.query, num_sources=cfg["sources"])
        if not raw_sources:
            raise HTTPException(status_code=502, detail="No sources could be scraped.")

        sources = await aggregate_sources(sources=raw_sources, query=query.query, min_sources=3)
        session_id = query.session_id or str(uuid.uuid4())
        report = await synthesize(query=query.query, sources=sources, session_id=session_id)

        if not validate_citations(report):
            raise HTTPException(status_code=500, detail="Report validation failed.")

        await save_report(report)
        return report

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/research/stream")
async def stream_research(
    query: str,
    max_sources: int = 5,
    depth: str = "standard"
):
    """Streaming endpoint with full pipeline: decompose → search → aggregate → synthesize → confidence → followups → reflect"""
    async def event_stream():
        step = 0
        ts = lambda: time.strftime("%H:%M:%S", time.gmtime())
        cfg = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["standard"])
        num_sources = cfg["sources"]
        do_decompose = cfg["decompose"]

        def emit(status, message, **extra):
            nonlocal step
            step += 1
            payload = {"status": status, "step": step, "timestamp": ts(), "message": message}
            payload.update(extra)
            return f"data: {json.dumps(payload)}\n\n"

        try:
            # Step: Fetch previous context
            yield emit("context", "Loading previous research context...")
            recent = await get_recent_sessions(limit=3)
            context_text = ""
            if recent:
                context_parts = [f"- Query: {s['query']} | Summary: {s['summary'][:200]}" for s in recent]
                context_text = "Previous research sessions:\n" + "\n".join(context_parts)

            all_sources = []

            # Step: Query decomposition (deep mode)
            sub_questions = [query]
            if do_decompose:
                yield emit("decompose", "Decomposing query into sub-questions...")
                sub_questions = await decompose_query(query)
                yield emit("decompose_done", f"Generated {len(sub_questions)} sub-questions",
                          sub_questions=sub_questions)

            # Step: Search for each sub-question
            for i, sq in enumerate(sub_questions):
                per_q = max(3, num_sources // len(sub_questions))
                yield emit("searching", f"Searching: {sq[:80]}...")
                try:
                    results = await search_and_scrape(query=sq, num_sources=per_q)
                except FirecrawlSearchError as e:
                    yield emit("error", str(e))
                    return
                all_sources.extend(results)
                # Emit sources for real-time right panel updates
                source_data = [{"url": s.url, "title": s.title, "word_count": s.word_count,
                               "relevance_score": s.relevance_score,
                               "scrape_timestamp": s.scrape_timestamp,
                               "preview": s.content[:300]} for s in results]
                yield emit("sources_found", f"Found {len(results)} sources for sub-query {i+1}",
                          sources=source_data)

            if not all_sources:
                yield emit("error", "No sources found. Try a different query.")
                return

            # Step: Aggregate and score
            yield emit("scoring", f"Scoring relevance across {len(all_sources)} sources...")
            sources = await aggregate_sources(all_sources, query, min_sources=3)
            scored_data = [{"url": s.url, "title": s.title, "relevance_score": s.relevance_score,
                           "word_count": s.word_count} for s in sources]
            yield emit("scored", f"Filtered to {len(sources)} high-relevance sources",
                      scored_sources=scored_data)

            # Step: Synthesize
            yield emit("synthesizing", f"Synthesizing report from {len(sources)} sources...")
            session_id = str(uuid.uuid4())
            report = await synthesize(
                query=query, sources=sources,
                session_id=session_id, previous_context=context_text
            )
            report.sub_questions = sub_questions
            report.depth = depth

            # Step: Confidence reasoning
            yield emit("confidence", "Evaluating finding confidence levels...")
            report = await rate_confidence(report)

            # Step: Validate
            yield emit("validating", "Validating citations and report quality...")
            valid = validate_citations(report)

            # Step: Follow-up suggestions
            yield emit("followups", "Generating follow-up research questions...")
            followups = await generate_followups(query, report)
            report.suggested_followups = followups

            # Step: Self-reflection
            yield emit("reflecting", "Self-evaluating report completeness...")
            reflection = await self_reflect(query, report)

            if not reflection.get("fully_answered", True) and reflection.get("suggested_search"):
                yield emit("refining", f"Running refinement search: {reflection['suggested_search'][:60]}...")
                extra_sources = await search_and_scrape(
                    query=reflection["suggested_search"], num_sources=3
                )
                if extra_sources:
                    extra_scored = await aggregate_sources(extra_sources, query, min_sources=1)
                    # Quick re-synthesis for additional findings
                    extra_text = "\n".join(f"- {s.title}: {s.content[:500]}" for s in extra_scored)
                    from server.llm import call_gemini_json
                    refine_result = await call_gemini_json(
                        f"Extract 1-2 NEW findings from these additional sources that weren't in the original report:\n{extra_text}\n\nOriginal findings: {', '.join(report.key_findings[:3])}\n\nRespond with JSON array: [\"new finding 1\", \"new finding 2\"]",
                        "You are a research supplement agent."
                    )
                    try:
                        new_findings = json.loads(refine_result)
                        if isinstance(new_findings, list):
                            report.refined_findings = new_findings[:2]
                    except Exception:
                        pass
                yield emit("refined", f"Added {len(report.refined_findings)} refined findings",
                          reflection=reflection)
            else:
                yield emit("complete", "Query fully answered — no refinement needed",
                          reflection=reflection)

            # Step: Save to memory
            yield emit("saving", "Saving report to session memory...")
            await save_report(report)

            # Final: send complete report
            yield f"data: {json.dumps({'status': 'done', 'step': step + 1, 'timestamp': ts(), 'report': report.model_dump()})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'step': step + 1, 'timestamp': ts(), 'message': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/research/export")
async def export_research(session_id: str, format: str = "markdown"):
    """Export last report for a session in various formats."""
    history = await get_session_history(session_id)
    if not history:
        raise HTTPException(status_code=404, detail="No reports found for this session.")
    
    last_report_data = history[-1]
    # Reconstruct report object
    from models import Citation
    citations = [Citation(**c) for c in last_report_data.get("citations", [])]
    report = ResearchReport(
        query=last_report_data.get("query", ""),
        summary=last_report_data.get("summary", ""),
        key_findings=last_report_data.get("key_findings", []),
        citations=citations,
        sources_scraped=last_report_data.get("sources_scraped", 0),
        confidence_score=last_report_data.get("confidence_score", 0),
        session_id=session_id
    )
    
    md = format_report_markdown(report)
    
    if format == "markdown":
        return PlainTextResponse(md, media_type="text/markdown",
                                headers={"Content-Disposition": f"attachment; filename=deeptrace-report-{session_id[:8]}.md"})
    elif format == "pdf":
        # Convert markdown to PDF
        try:
            import weasyprint
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 40px; }}
                    h1 {{ color: #333; border-bottom: 2px solid #00ff88; padding-bottom: 10px; }}
                    h2 {{ color: #555; margin-top: 30px; }}
                    .finding {{ background: #f5f5f5; padding: 15px; margin: 10px 0; border-left: 4px solid #00ff88; }}
                    .citation {{ font-size: 0.9em; color: #666; }}
                </style>
            </head>
            <body>
                {md.replace('\n', '<br>')}
            </body>
            </html>
            """
            pdf = weasyprint.HTML(string=html_content).write_pdf()
            return Response(
                content=pdf,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=deeptrace-report-{session_id[:8]}.pdf"}
            )
        except ImportError:
            # Fallback if weasyprint not available
            return PlainTextResponse(md, media_type="text/markdown",
                                    headers={"Content-Disposition": f"attachment; filename=deeptrace-report-{session_id[:8]}.md"})
    elif format == "ppt":
        # Create PPT-like content (simplified HTML that can be opened as PPT)
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>DeepTrace Report - {report.query[:50]}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
                .slide {{ page-break-after: always; min-height: 90vh; border: 1px solid #ddd; padding: 40px; margin-bottom: 20px; }}
                .title {{ font-size: 24px; font-weight: bold; color: #00ff88; margin-bottom: 20px; }}
                .content {{ font-size: 18px; line-height: 1.6; }}
                .finding {{ background: #f9f9f9; padding: 20px; margin: 15px 0; border-left: 4px solid #00ff88; }}
            </style>
        </head>
        <body>
            <div class="slide">
                <div class="title">DeepTrace Research Report</div>
                <div class="content">
                    <h2>Query: {report.query}</h2>
                    <p><strong>Confidence Score:</strong> {report.confidence_score}/10</p>
                    <p><strong>Sources Analyzed:</strong> {report.sources_scraped}</p>
                </div>
            </div>
            <div class="slide">
                <div class="title">Key Findings</div>
                <div class="content">
        """
        
        for i, finding in enumerate(report.key_findings, 1):
            html_content += f'<div class="finding"><strong>{i}.</strong> {finding}</div>'
        
        html_content += """
                </div>
            </div>
            <div class="slide">
                <div class="title">Summary</div>
                <div class="content">""" + report.summary + """</div>
            </div>
        </body>
        </html>
        """
        return Response(
            content=html_content.encode('utf-8'),
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename=deeptrace-report-{session_id[:8]}.ppt.html"}
        )
    
    return PlainTextResponse(md)

@app.get("/research/share/{session_id}")
async def share_research(session_id: str):
    """Generate shareable link for a research session."""
    # Create a shareable URL that points to a public view of the research
    share_url = f"{os.getenv('BASE_URL', 'http://localhost:8000')}/shared/{session_id}"
    return {"share_url": share_url, "session_id": session_id}

@app.get("/shared/{session_id}")
async def view_shared_research(session_id: str):
    """Public view of a shared research session."""
    history = await get_session_history(session_id)
    if not history:
        raise HTTPException(status_code=404, detail="Research session not found.")
    
    last_report_data = history[-1]
    # Reconstruct report object
    from models import Citation
    citations = [Citation(**c) for c in last_report_data.get("citations", [])]
    report = ResearchReport(
        query=last_report_data.get("query", ""),
        summary=last_report_data.get("summary", ""),
        key_findings=last_report_data.get("key_findings", []),
        citations=citations,
        sources_scraped=last_report_data.get("sources_scraped", 0),
        confidence_score=last_report_data.get("confidence_score", 0),
        session_id=session_id
    )
    
    # Generate HTML for shared view
    md = format_report_markdown(report)
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>DeepTrace Research - {report.query[:50]}</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 40px; max-width: 800px; }}
            h1 {{ color: #333; border-bottom: 2px solid #00ff88; padding-bottom: 10px; }}
            h2 {{ color: #555; margin-top: 30px; }}
            .finding {{ background: #f5f5f5; padding: 15px; margin: 10px 0; border-left: 4px solid #00ff88; }}
            .citation {{ font-size: 0.9em; color: #666; }}
            .header {{ background: #00ff88; color: #000; padding: 20px; margin: -40px -40px 20px -40px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🤖 DeepTrace Research Report</h1>
            <p><strong>Query:</strong> {report.query}</p>
            <p><strong>Confidence Score:</strong> {report.confidence_score}/10</p>
            <p><strong>Sources Analyzed:</strong> {report.sources_scraped}</p>
        </div>
        {md.replace('\n', '<br>')}
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/sessions")
async def list_sessions():
    """Get all research sessions for the history panel."""
    sessions = await get_all_sessions()
    return {"sessions": sessions}

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

@app.delete("/sessions/all")
async def delete_all_sessions():
    """Clear all research sessions"""
    await clear_all_sessions()
    return {"message": "All sessions cleared"}

@app.get("/tasks")
async def list_tasks():
    """OpenEnv-compatible tasks endpoint"""
    return {
        "agent": "DeepTrace",
        "version": "2.0.0",
        "tasks": ["deep_research"],
        "actions": ["decompose", "search_and_scrape", "aggregate", "synthesize",
                    "rate_confidence", "generate_followups", "self_reflect", "cite"]
    }