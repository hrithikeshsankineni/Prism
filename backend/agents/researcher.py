import logging
import time
from typing import Any, Callable, Coroutine, Dict, List
from urllib.parse import urlparse

from backend.config import settings
from backend.core.confidence import (
    compute_agent_confidence,
    compute_claim_confidence,
)
from backend.core.groq_client import groq_client
from backend.core.tavily_client import tavily_client
from backend.schemas.agent_schemas import AgentResult, Finding, Source
from backend.schemas.event_schemas import EventType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Search strategy per agent type
# ---------------------------------------------------------------------------
SEARCH_STRATEGIES: Dict[str, Dict[str, Any]] = {
    "web_research": {"topic": "general", "search_depth": "advanced"},
    "news_sentiment": {"topic": "news"},
    "financial_market": {
        "topic": "general",
        "include_domains": [
            "reuters.com", "bloomberg.com", "finance.yahoo.com", "ft.com", "cnbc.com",
        ],
    },
    "domain_specific": {"topic": "general", "search_depth": "advanced"},
    "academic": {
        "topic": "general",
        "include_domains": [
            "arxiv.org", "scholar.google.com", "nature.com", "sciencedirect.com",
        ],
    },
}

# ---------------------------------------------------------------------------
# Extraction prompt — chain-of-thought before structured output
# Few-shot example teaches the model what granularity we want.
# ---------------------------------------------------------------------------
EXTRACTION_PROMPT = """You are a senior research analyst extracting structured findings from web search results.

INSTRUCTIONS:
1. Think step-by-step about what the sources collectively say before writing JSON.
2. Extract only claims that are directly supported by the provided sources.
3. Do not extrapolate or infer beyond what is written.
4. Distinguish between facts/statistics (verifiable) vs opinions/predictions (subjective).

EXAMPLE (abbreviated):
Topic: "OpenAI revenue 2024"
Findings:
[
  {"claim": "OpenAI reported $3.4B in annualised revenue as of late 2024",
   "supporting_sources": ["https://ft.com/openai-revenue"],
   "category": "statistic"},
  {"claim": "Analysts predict OpenAI could reach $10B revenue by 2025",
   "supporting_sources": ["https://bloomberg.com/openai-forecast"],
   "category": "prediction"}
]

OUTPUT FORMAT (JSON only, no markdown):
{
  "reasoning": "2-3 sentences: what do these sources collectively establish?",
  "findings": [
    {
      "claim": "specific, concrete claim — not vague",
      "supporting_sources": ["url1", "url2"],
      "category": "fact | statistic | opinion | prediction"
    }
  ]
}"""

# ---------------------------------------------------------------------------
# Gap analysis prompt — decides whether a follow-up search is needed
# ---------------------------------------------------------------------------
GAP_ANALYSIS_PROMPT = """You are a research analyst reviewing initial findings.

Given the topic and what was found so far, identify the single most important
unanswered question that would materially improve the brief.

Respond in JSON:
{
  "needs_followup": true/false,
  "gap_query": "one specific search query to fill the gap (empty string if no followup needed)",
  "gap_reason": "why this gap matters"
}

Rules:
- Only set needs_followup=true if there is a genuine, important gap.
- The gap_query must be specific and different from the original queries.
- If the findings are already comprehensive, set needs_followup=false."""


class ResearchAgent:
    """
    Research agent that:
    1. Executes parallel Tavily searches per assigned query
    2. Runs a gap analysis and conditionally fires a follow-up search
    3. Extracts findings with chain-of-thought reasoning
    4. Scores confidence from evidence signals, not LLM self-report
    """

    async def research(
        self,
        agent_id: str,
        agent_type: str,
        search_queries: List[str],
        focus_area: str,
        emit: Callable[..., Coroutine],
    ) -> AgentResult:
        start = time.time()
        thoughts: List[str] = []
        all_tavily_results: List[Dict[str, Any]] = []
        requery_count = 0

        try:
            await emit(
                EventType.AGENT_STARTED,
                {"focus_area": focus_area},
                agent_id=agent_id,
                agent_type=agent_type,
            )

            strategy = SEARCH_STRATEGIES.get(agent_type, {})

            # ----------------------------------------------------------------
            # Phase 1: execute assigned search queries
            # ----------------------------------------------------------------
            for query in search_queries:
                await emit(
                    EventType.AGENT_SEARCHING,
                    {"query": query},
                    agent_id=agent_id,
                    agent_type=agent_type,
                )
                thoughts.append(f"Searching: {query}")
                await emit(
                    EventType.AGENT_THOUGHT,
                    {"thought": f"Searching: {query}"},
                    agent_id=agent_id,
                    agent_type=agent_type,
                )

                result = tavily_client.search(
                    query=query,
                    max_results=settings.tavily_max_results,
                    **strategy,
                )
                results_list = result.get("results", [])
                all_tavily_results.extend(results_list)
                thoughts.append(f"Found {len(results_list)} results for '{query}'")
                await emit(
                    EventType.AGENT_THOUGHT,
                    {"thought": f"Found {len(results_list)} results"},
                    agent_id=agent_id,
                    agent_type=agent_type,
                )

            # ----------------------------------------------------------------
            # Phase 2: gap analysis — let the agent decide to re-query
            # ----------------------------------------------------------------
            if all_tavily_results:
                gap_result = await self._gap_analysis(
                    focus_area=focus_area,
                    initial_results=all_tavily_results,
                    original_queries=search_queries,
                )
                if gap_result.get("needs_followup") and gap_result.get("gap_query"):
                    gap_query = gap_result["gap_query"]
                    gap_reason = gap_result.get("gap_reason", "")

                    thoughts.append(f"Gap identified: {gap_reason}")
                    await emit(
                        EventType.AGENT_REQUERYING,
                        {"gap_query": gap_query, "gap_reason": gap_reason},
                        agent_id=agent_id,
                        agent_type=agent_type,
                    )
                    await emit(
                        EventType.AGENT_THOUGHT,
                        {"thought": f"Re-querying to fill gap: {gap_query}"},
                        agent_id=agent_id,
                        agent_type=agent_type,
                    )

                    followup = tavily_client.search(
                        query=gap_query,
                        max_results=settings.tavily_max_results,
                        **strategy,
                    )
                    followup_results = followup.get("results", [])
                    all_tavily_results.extend(followup_results)
                    requery_count = 1
                    thoughts.append(
                        f"Follow-up search returned {len(followup_results)} additional results"
                    )

            # ----------------------------------------------------------------
            # Deduplicate by URL
            # ----------------------------------------------------------------
            seen_urls: set = set()
            unique_results = []
            for r in all_tavily_results:
                url = r.get("url", "")
                if url not in seen_urls:
                    seen_urls.add(url)
                    unique_results.append(r)

            if not unique_results:
                return AgentResult(
                    agent_id=agent_id,
                    agent_type=agent_type,
                    status="completed",
                    findings=[],
                    sources=[],
                    confidence_score=0.0,
                    thoughts=thoughts + ["No search results found"],
                    search_queries_used=search_queries,
                    execution_time_seconds=time.time() - start,
                    requery_count=requery_count,
                )

            # ----------------------------------------------------------------
            # Build source list
            # ----------------------------------------------------------------
            sources = [
                Source(
                    url=r.get("url", ""),
                    title=r.get("title", ""),
                    domain=urlparse(r.get("url", "")).netloc if r.get("url") else "",
                    relevance_score=r.get("score", 0.0),
                )
                for r in unique_results
            ]

            # ----------------------------------------------------------------
            # Phase 3: LLM extraction with chain-of-thought
            # ----------------------------------------------------------------
            search_context = "\n\n".join(
                f"Source: {r.get('title', 'N/A')} ({r.get('url', '')})\n"
                f"Content: {r.get('content', '')[:700]}"
                for r in unique_results[:6]
            )

            messages = [
                {"role": "system", "content": EXTRACTION_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Topic: {focus_area}\n"
                        f"Agent type: {agent_type}\n\n"
                        f"Search results:\n{search_context}"
                    ),
                },
            ]

            parsed = await groq_client.complete_json(
                messages=messages,
                model=settings.groq_research_model,
                max_tokens=1024,
            )

            # Log the CoT reasoning as a thought
            reasoning = parsed.get("reasoning", "")
            if reasoning:
                thoughts.append(f"Reasoning: {reasoning}")
                await emit(
                    EventType.AGENT_THOUGHT,
                    {"thought": reasoning},
                    agent_id=agent_id,
                    agent_type=agent_type,
                )

            # ----------------------------------------------------------------
            # Phase 4: compute evidence-grounded confidence (not LLM self-report)
            # ----------------------------------------------------------------
            findings: List[Finding] = []
            for f in parsed.get("findings", []):
                grounded_conf = compute_claim_confidence(
                    category=f.get("category", "fact"),
                    supporting_source_urls=f.get("supporting_sources", []),
                    fallback_sources=sources,
                )
                findings.append(Finding(
                    claim=f.get("claim", ""),
                    supporting_sources=f.get("supporting_sources", []),
                    confidence=grounded_conf,
                    category=f.get("category", "fact"),
                ))

            # Agent-level confidence aggregated from claim signals
            confidence = compute_agent_confidence(findings, sources)

            await emit(
                EventType.AGENT_FOUND,
                {"findings_count": len(findings), "sources_count": len(sources)},
                agent_id=agent_id,
                agent_type=agent_type,
            )
            await emit(
                EventType.AGENT_COMPLETE,
                {"confidence": confidence, "findings_count": len(findings)},
                agent_id=agent_id,
                agent_type=agent_type,
            )

            return AgentResult(
                agent_id=agent_id,
                agent_type=agent_type,
                status="completed",
                findings=findings,
                sources=sources,
                confidence_score=confidence,
                thoughts=thoughts,
                search_queries_used=search_queries,
                execution_time_seconds=time.time() - start,
                requery_count=requery_count,
            )

        except Exception as e:
            logger.error(f"Research agent {agent_id} failed: {e}", exc_info=True)
            await emit(
                EventType.AGENT_FAILED,
                {"error": str(e)},
                agent_id=agent_id,
                agent_type=agent_type,
            )
            return AgentResult(
                agent_id=agent_id,
                agent_type=agent_type,
                status="failed",
                thoughts=thoughts + [f"Error: {e}"],
                search_queries_used=search_queries,
                error_message=str(e),
                execution_time_seconds=time.time() - start,
                requery_count=requery_count,
            )

    async def _gap_analysis(
        self,
        focus_area: str,
        initial_results: List[Dict[str, Any]],
        original_queries: List[str],
    ) -> Dict[str, Any]:
        """Ask the LLM whether there is a critical gap in the initial results."""
        summary = "\n".join(
            f"- {r.get('title', 'N/A')}: {r.get('content', '')[:120]}"
            for r in initial_results[:3]
        )
        messages = [
            {"role": "system", "content": GAP_ANALYSIS_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Research topic: {focus_area}\n"
                    f"Original queries: {original_queries}\n\n"
                    f"Initial findings summary:\n{summary}"
                ),
            },
        ]
        try:
            return await groq_client.complete_json(
                messages=messages,
                model=settings.groq_research_model,
                max_tokens=256,
            )
        except Exception as e:
            logger.warning(f"Gap analysis failed: {e}")
            return {"needs_followup": False, "gap_query": "", "gap_reason": ""}
