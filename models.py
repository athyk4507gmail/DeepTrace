from pydantic import BaseModel
from typing import Optional, List

class ResearchQuery(BaseModel):
    query: str
    max_sources: int = 5
    use_memory: bool = True
    session_id: Optional[str] = None
    depth: str = "standard"  # quick | standard | deep

class ScrapedSource(BaseModel):
    url: str
    title: str
    content: str
    relevance_score: float
    word_count: int = 0
    scrape_timestamp: Optional[str] = None

class Citation(BaseModel):
    index: int
    url: str
    title: str
    snippet: str

class FindingConfidence(BaseModel):
    finding: str
    confidence: str  # HIGH / MED / LOW
    score: int  # 1-10
    source_count: int

class ResearchReport(BaseModel):
    query: str
    summary: str
    key_findings: List[str]
    finding_confidences: List[FindingConfidence] = []
    citations: List[Citation] = []
    sources_scraped: int
    confidence_score: float
    confidence_explanation: str = ""
    conflicts: List[str] = []
    suggested_followups: List[str] = []
    refined_findings: List[str] = []
    session_id: Optional[str] = None
    sub_questions: List[str] = []
    depth: str = "standard"

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
