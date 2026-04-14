# PRISM — Multi-Agent Intelligence Platform

PRISM is a real-time intelligence briefing system. Give it any query — a company, a person, a technology, a decision — and a coordinated pipeline of AI agents researches it in parallel, cross-checks findings for contradictions, critiques the evidence, and delivers a structured brief with confidence scores and cited sources.

Everything streams live to the UI via WebSocket, so you watch the agents think in real time.

---

## How It Works

```
Query → Planner → [Research Agents × N (parallel)] → Synthesis → Critic → Eval → Brief
```

| Stage | What it does |
|---|---|
| **Planner** | Breaks the query into 3–5 focused research sub-tasks, each assigned to a specialist agent |
| **Research Agents** | Run in parallel — each searches the web (Tavily), extracts findings, and scores confidence |
| **RAG Memory** | The planner queries prior briefs (ChromaDB) to avoid re-researching known topics |
| **Synthesis** | Merges all agent findings, detects cross-agent contradictions, and builds a structured draft |
| **Critic** | Challenges weak claims, flags missing perspectives, and scores overall credibility |
| **Eval** | Scores the brief on factual consistency, source coverage, completeness, and calibration |

All stages stream events to the frontend in real time over a single WebSocket connection.

---

## Tech Stack

**Backend**
- Python · FastAPI · WebSockets
- [Groq](https://groq.com) — LLM inference (Llama 3.1 / 3.3 models)
- [Tavily](https://tavily.com) — web search API
- [ChromaDB](https://www.trychroma.com) + `sentence-transformers` — vector store for RAG memory
- Pydantic — structured LLM output parsing

**Frontend**
- React 19 · Vite · Tailwind CSS
- Zustand — global state
- Framer Motion — animations
- Native WebSocket API

**Deployment**
- Backend: [Render](https://render.com) (free tier)
- Frontend: [Vercel](https://vercel.com) (free)

---

## Features

- **Parallel research** — multiple specialist agents work simultaneously, not sequentially
- **Contradiction detection** — synthesis stage automatically surfaces conflicting claims between agents and resolves them
- **Critic pass** — a separate agent challenges the draft brief for logical gaps and missing perspectives
- **Confidence scoring** — every finding, section, and the overall brief carries a calibrated confidence score
- **RAG memory** — prior briefs are stored as vector embeddings; the planner retrieves relevant context for follow-up queries
- **Live event stream** — the full agent thought process streams to the UI in real time; nothing is hidden behind a loading bar
- **Eval scorecard** — each brief is scored on four dimensions: factual consistency, source coverage, completeness, confidence calibration

---

## Project Structure

```
prism/
├── backend/
│   ├── agents/
│   │   ├── planner.py       # Decomposes query into agent specs
│   │   ├── researcher.py    # Web research agent (Tavily + Groq)
│   │   ├── synthesis.py     # Merges findings, detects contradictions
│   │   ├── critic.py        # Challenges and stress-tests the draft
│   │   └── eval_agent.py    # Scores the final brief
│   ├── core/
│   │   ├── orchestrator.py  # Pipeline runner, parallel execution, event bus
│   │   ├── rag.py           # ChromaDB vector memory
│   │   ├── groq_client.py   # Groq API wrapper with rate limiting + retries
│   │   ├── tavily_client.py # Tavily search wrapper
│   │   ├── confidence.py    # Cross-agent corroboration scoring
│   │   └── metrics.py       # Per-pipeline timing and stats
│   ├── schemas/
│   │   ├── agent_schemas.py # Pydantic models for all agent I/O
│   │   └── event_schemas.py # WebSocket event types
│   ├── config.py            # Settings (models, timeouts, rate limits)
│   └── main.py              # FastAPI app, REST + WebSocket endpoints
└── frontend/
    └── src/
        ├── components/
        │   ├── QueryInput.jsx      # Search bar + submit
        │   ├── AgentCard.jsx       # Live per-agent status
        │   ├── ThoughtLog.jsx      # Streaming agent thoughts
        │   ├── FinalBrief.jsx      # Rendered intelligence brief
        │   ├── EvalScorecard.jsx   # Brief quality scorecard
        │   ├── PipelineMetrics.jsx # Timing and agent stats
        │   └── PriorBriefs.jsx     # RAG memory sidebar
        ├── hooks/useWebSocket.js   # WebSocket connection management
        └── store/sessionStore.js   # Zustand global state
```

---

## Local Development

**Prerequisites:** Python 3.11+, Node.js 18+, a [Groq API key](https://console.groq.com) and a [Tavily API key](https://tavily.com)

```bash
# Clone
git clone https://github.com/hrithikeshsankineni/prism.git
cd prism

# Backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env
echo "GROQ_API_KEY=your_groq_key" >> .env
echo "TAVILY_API_KEY=your_tavily_key" >> .env

# Start backend
uvicorn backend.main:app --reload
```

```bash
# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`

---


