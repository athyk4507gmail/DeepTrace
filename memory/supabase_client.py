import os
import json
import uuid
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
