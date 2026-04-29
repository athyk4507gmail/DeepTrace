from pydantic import BaseModel
from typing import Optional, List

class ResearchQuery(BaseModel):
    query: str
    max_sources: int = 5
    use_memory: bool = False
    session_id: Optional[str] = None

class ScrapedSource(BaseModel):
    url: str
    title: str
    content: str
    relevance_score: float

class Citation(BaseModel):
    index: int
    url: str
    title: str
    snippet: str

class ResearchReport(BaseModel):
    query: str
    summary: str
    key_findings: List[str]
    citations: List[Citation]
    sources_scraped: int
    confidence_score: float
    session_id: Optional[str] = None

class AgentStep(BaseModel):
    step: int
    action: str
    target: str
    result: str
    sources_found: int

class ResearchSession(BaseModel):
    session_id: str
    history: List[ResearchQuery] = []
    reports: List[ResearchReport] = []
