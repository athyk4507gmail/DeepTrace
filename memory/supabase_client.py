import os
import json
import uuid
import time
from typing import Optional, List
from models import ResearchReport, ResearchSession

# Supabase is optional — gracefully disabled if not configured
try:
    from supabase import create_client, Client
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
    if SUPABASE_URL and SUPABASE_KEY:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        SUPABASE_ENABLED = True
    else:
        SUPABASE_ENABLED = False
except ImportError:
    SUPABASE_ENABLED = False

# In-memory fallback when Supabase is not configured
_memory_store = {}

async def save_report(report: ResearchReport) -> str:
    """Save a research report to memory or Supabase"""
    session_id = report.session_id or str(uuid.uuid4())
    report_dict = report.model_dump()
    report_dict["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if SUPABASE_ENABLED:
        try:
            supabase.table("research_reports").insert({
                "session_id": session_id,
                "query": report.query,
                "report": json.dumps(report_dict)
            }).execute()
            return session_id
        except Exception as e:
            print(f"Supabase save error: {e}")

    # Fallback to in-memory
    if session_id not in _memory_store:
        _memory_store[session_id] = []
    _memory_store[session_id].append(report_dict)
    return session_id

async def get_session_history(session_id: str) -> List[dict]:
    """Retrieve past reports for a session"""
    if SUPABASE_ENABLED:
        try:
            result = supabase.table("research_reports") \
                .select("*") \
                .eq("session_id", session_id) \
                .execute()
            return [json.loads(r["report"]) for r in result.data]
        except Exception as e:
            print(f"Supabase fetch error: {e}")

    return _memory_store.get(session_id, [])

async def get_recent_sessions(limit: int = 3) -> List[dict]:
    """Fetch summaries of the most recent research sessions for context."""
    if SUPABASE_ENABLED:
        try:
            result = supabase.table("research_reports") \
                .select("session_id, query, report") \
                .order("created_at", desc=True) \
                .limit(limit) \
                .execute()
            summaries = []
            for r in result.data:
                report_data = json.loads(r["report"])
                summaries.append({
                    "session_id": r["session_id"],
                    "query": r["query"],
                    "summary": report_data.get("summary", ""),
                    "timestamp": report_data.get("timestamp", "")
                })
            return summaries
        except Exception as e:
            print(f"Supabase recent fetch error: {e}")

    # In-memory fallback: flatten all sessions, return latest
    all_reports = []
    for sid, reports in _memory_store.items():
        for r in reports:
            all_reports.append({
                "session_id": sid,
                "query": r.get("query", ""),
                "summary": r.get("summary", ""),
                "timestamp": r.get("timestamp", "")
            })
    all_reports.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return all_reports[:limit]

async def get_all_sessions() -> List[dict]:
    """Get all sessions for the history panel."""
    if SUPABASE_ENABLED:
        try:
            result = supabase.table("research_reports") \
                .select("session_id, query, report") \
                .order("created_at", desc=True) \
                .limit(50) \
                .execute()
            sessions = []
            for r in result.data:
                report_data = json.loads(r["report"])
                sessions.append({
                    "session_id": r["session_id"],
                    "query": r["query"],
                    "summary": report_data.get("summary", ""),
                    "sources_scraped": report_data.get("sources_scraped", 0),
                    "confidence_score": report_data.get("confidence_score", 0),
                    "timestamp": report_data.get("timestamp", "")
                })
            return sessions
        except Exception as e:
            print(f"Supabase all sessions error: {e}")

    # In-memory fallback
    sessions = []
    for sid, reports in _memory_store.items():
        for r in reports:
            sessions.append({
                "session_id": sid,
                "query": r.get("query", ""),
                "summary": r.get("summary", ""),
                "sources_scraped": r.get("sources_scraped", 0),
                "confidence_score": r.get("confidence_score", 0),
                "timestamp": r.get("timestamp", "")
            })
    sessions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return sessions

async def clear_session(session_id: str):
    """Clear session history"""
    if SUPABASE_ENABLED:
        try:
            supabase.table("research_reports") \
                .delete() \
                .eq("session_id", session_id) \
                .execute()
            return
        except Exception as e:
            print(f"Supabase delete error: {e}")

    _memory_store.pop(session_id, None)

async def clear_all_sessions():
    """Clear all session history"""
    if SUPABASE_ENABLED:
        try:
            supabase.table("research_reports").delete().neq("session_id", "").execute()
            return
        except Exception as e:
            print(f"Supabase clear all error: {e}")
    _memory_store.clear()
