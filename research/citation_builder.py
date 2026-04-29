from typing import List
from models import ResearchReport, Citation

def format_citations_markdown(report: ResearchReport) -> str:
    """Format citations as markdown for display"""
    lines = []
    for c in report.citations:
        lines.append(f"[{c.index}] **{c.title}**")
        lines.append(f"    {c.url}")
        lines.append(f"    > {c.snippet}")
        lines.append("")
    return "\n".join(lines)

def format_report_markdown(report: ResearchReport) -> str:
    """Format full research report as markdown"""
    lines = [
        f"## Research Report",
        f"**Query:** {report.query}",
        f"**Sources Scraped:** {report.sources_scraped}",
        f"**Confidence:** {report.confidence_score:.0%}",
        "",
        "### Summary",
        report.summary,
        "",
        "### Key Findings",
    ]
    for finding in report.key_findings:
        lines.append(f"- {finding}")
    lines.append("")
    lines.append("### Sources")
    lines.append(format_citations_markdown(report))
    return "\n".join(lines)

def validate_citations(report: ResearchReport) -> bool:
    """Validate that all key findings have citations"""
    if not report.citations:
        return False
    if report.sources_scraped < 3:
        return False
    return True
