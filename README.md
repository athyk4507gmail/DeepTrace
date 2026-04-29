# 🤖 DeepTrace — Autonomous Deep Research Agent

**A multi-step AI research agent with query decomposition, confidence reasoning, and self-reflection capabilities.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-2.0.0-green)](https://github.com/athyk4507gmail/DeepTrace)

---

## � Features

- **Multi-step Research**: Decomposes complex queries into actionable sub-questions
- **Confidence Scoring**: Rates findings with confidence levels (HIGH/MED/LOW)
- **Source Aggregation**: Gathers and synthesizes information from multiple sources
- **Memory System**: Persistent session storage with Supabase backend
- **Self-Reflection**: AI agent evaluates and improves its own research process
- **Web Scraping**: Firecrawl integration for comprehensive source gathering
- **Interactive UI**: Real-time chat interface for research queries

---

## 📌 Table of Contents

- [Quick Start](#-quick-start)
- [Architecture](#-architecture)
- [API Endpoints](#-api-endpoints)
- [Configuration](#-configuration)
- [Project Structure](#-project-structure)
- [Usage Examples](#-usage-examples)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 Motivation

Traditional research tools often provide surface-level answers without deeper analysis or confidence assessment. DeepTrace addresses this by implementing a comprehensive research agent that:

- **Decomposes complex queries** into manageable sub-questions
- **Gathers diverse sources** through web scraping and search
- **Synthesizes information** with confidence scoring
- **Maintains context** through persistent memory
- **Self-reflects** on research quality and completeness

DeepTrace provides a production-ready research assistant that can handle complex, multi-faceted queries with transparency about confidence levels and source quality.

---

## ⚡ Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/athyk4507gmail/DeepTrace.git
cd DeepTrace
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

### 2. Run the Server

```bash
python server/app.py
# or
uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
```

Open → http://127.0.0.1:8000

### 3. Use the Client

```python
from client import DeepTraceClient

client = DeepTraceClient("http://127.0.0.1:8000")
result = client.research("What are the latest developments in quantum computing?")
print(result)
```

---

## 🏗️ Architecture

DeepTrace consists of several key components:

- **FastAPI Server** (`server/app.py`): Main API endpoints and web interface
- **Research Engine** (`research/`): Query decomposition, synthesis, and confidence scoring
- **Memory System** (`memory/`): Supabase-backed session persistence
- **Web Scraping** (`mcp/`): Firecrawl integration for source gathering
- **Interactive UI** (`server/chat_ui.html`): Real-time research interface

### Research Pipeline

1. **Query Decomposition**: Break complex queries into sub-questions
2. **Source Gathering**: Search and scrape relevant web sources
3. **Information Synthesis**: Combine and analyze findings
4. **Confidence Scoring**: Rate each finding with confidence levels
5. **Self-Reflection**: Evaluate research completeness and quality
6. **Report Generation**: Create structured research reports with citations

---

## 🔌 API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Interactive research chat interface |
| `POST` | `/research` | Submit research query and get results |
| `GET` | `/sessions` | List all research sessions |
| `GET` | `/sessions/{session_id}` | Get session history |
| `DELETE` | `/sessions/{session_id}` | Clear specific session |
| `DELETE` | `/sessions` | Clear all sessions |
| `GET` | `/health` | Health check endpoint |

### Research Request Example

```json
{
  "query": "What are the latest developments in quantum computing?",
  "max_sources": 5,
  "use_memory": true,
  "session_id": "optional-session-id",
  "depth": "standard"
}
```

### Research Response Example

```json
{
  "query": "What are the latest developments in quantum computing?",
  "findings": [
    {
      "finding": "Google achieved quantum supremacy with 53-qubit processor",
      "confidence": "HIGH",
      "score": 9,
      "source_count": 3,
      "sources": [...]
    }
  ],
  "report": "Comprehensive research report with citations...",
  "session_id": "session-uuid",
  "confidence_breakdown": {...},
  "followup_questions": [...]
}
```

---
## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default |
|---|---|---|
| `FIRECRAWL_API_KEY` | Firecrawl API key for web scraping | Required |
| `SUPABASE_URL` | Supabase database URL | Required |
| `SUPABASE_KEY` | Supabase service key | Required |
| `LLM_API_KEY` | LLM provider API key | Required |
| `LLM_BASE_URL` | LLM provider base URL | Optional |
| `MODEL_NAME` | LLM model name | Optional |

### Depth Configuration

| Depth | Sources | Decomposition | Use Case |
|---|---|---|---|
| `quick` | 3 | No | Fast, surface-level research |
| `standard` | 5 | No | Balanced research |
| `deep` | 10 | Yes | Comprehensive, multi-step research |

---

## � Project Structure

```
DeepTrace/
├── server/
│   ├── app.py                   # FastAPI application and web interface
│   ├── chat_ui.html             # Interactive research chat UI
│   └── llm.py                   # LLM client integration
├── research/
│   ├── aggregator.py            # Source aggregation and filtering
│   ├── synthesizer.py           # Query decomposition and synthesis
│   └── citation_builder.py     # Citation formatting and validation
├── memory/
│   └── supabase_client.py       # Session persistence and storage
├── mcp/
│   └── firecrawl_client.py      # Web scraping and search integration
├── models.py                    # Pydantic data models
├── client.py                    # Python client library
├── inference.py                 # Research evaluation runner
├── requirements.txt             # Python dependencies
├── pyproject.toml              # Project configuration
└── README.md                   # This file
```

---

## 💡 Usage Examples

### Basic Research Query

```python
import httpx

# Research query via API
response = httpx.post("http://localhost:8000/research", json={
    "query": "What are the environmental impacts of renewable energy?",
    "max_sources": 5,
    "depth": "standard"
})
result = response.json()
print(result["report"])
```

### Advanced Research with Memory

```python
# Research with session memory
response = httpx.post("http://localhost:8000/research", json={
    "query": "Compare solar vs wind energy efficiency",
    "max_sources": 10,
    "depth": "deep",
    "use_memory": True,
    "session_id": "my-research-session"
})
```

### Command Line Usage

```bash
# Run research from command line
python client.py "What are the latest AI developments?"

# List all sessions
python client.py --list-sessions

# Clear session memory
python client.py --clear-session session-id
```

---

## � Deployment

### Docker Deployment

```bash
# Build Docker image
docker build -t deeptrace .

# Run with environment variables
docker run -p 8000:8000 \
  -e FIRECRAWL_API_KEY=your_key \
  -e SUPABASE_URL=your_url \
  -e SUPABASE_KEY=your_key \
  -e LLM_API_KEY=your_llm_key \
  deeptrace
```

### Production Considerations

- **Rate Limiting**: Implement rate limiting for API endpoints
- **Caching**: Cache research results to improve performance
- **Monitoring**: Add logging and monitoring for research quality
- **Security**: Secure API keys and implement authentication

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

### Areas for Contribution

- **Research Algorithms**: Improve query decomposition and synthesis
- **Source Quality**: Better source filtering and validation
- **UI/UX**: Enhance the web interface
- **Performance**: Optimize research pipeline speed
- **Integrations**: Add new data sources and APIs

---

## 📄 License

This project is licensed under the **MIT License** — see the [`LICENSE`](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Firecrawl** for web scraping capabilities
- **Supabase** for database and storage
- **FastAPI** for the web framework
- **OpenAI** for LLM integration

---

<div align="center">

Made with ❤️ by [DeepTrace Team](https://github.com/athyk4507gmail/DeepTrace)

</div>
