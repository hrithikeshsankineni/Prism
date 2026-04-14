import json
import logging
import uuid
from typing import Callable, Coroutine, List

from backend.config import settings
from backend.core.groq_client import groq_client
from backend.core.rag import rag_memory
from backend.schemas.agent_schemas import AgentPlan, AgentSpec
from backend.schemas.event_schemas import EventType

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """You are the Planner Agent for PRISM, a multi-agent intelligence platform.

Your job is to decompose a research query into a set of specialised sub-agents, each
covering a DISTINCT angle. Poor planning (redundant agents, obvious queries) wastes
rate-limit budget and produces repetitive briefs.

Available agent types:
- web_research      : broad web search, good for general facts and recent developments
- news_sentiment    : recent news and market/public sentiment
- financial_market  : company financials, market data (reuters, bloomberg, yahoo finance)
- domain_specific   : deep-dive into a domain (technology, healthcare, policy, etc.)
- academic          : peer-reviewed research, arxiv, scientific consensus

Planning rules:
1. Spawn 3–5 agents. More agents = more rate-limit pressure; fewer = coverage gaps.
2. Each agent gets 1–3 SPECIFIC search queries — never the raw user query repeated verbatim.
3. Agents must cover NON-OVERLAPPING aspects. If two agents would run similar searches, merge them.
4. Use prior research context (when available) to focus on GAPS, not already-covered ground.
5. Assign priority 1–5 (5=critical) based on how central this angle is to the query.

Think through the decomposition before writing JSON.

Response format (JSON only):
{
  "reasoning": "Brief decomposition rationale — why these agents, why these queries",
  "agents": [
    {
      "agent_type": "web_research",
      "focus_area": "Precise description of what this agent investigates",
      "search_queries": ["specific query 1", "specific query 2"],
      "priority": 4
    }
  ]
}"""


class PlannerAgent:
    """Analyses the query, retrieves RAG context, and dispatches research agents."""

    async def plan(
        self,
        query: str,
        emit: Callable[..., Coroutine],
    ) -> AgentPlan:
        # Retrieve related prior briefs from vector memory
        rag_context = await rag_memory.query_related(query, n_results=3)
        rag_used = len(rag_context) > 0
        rag_brief_ids: List[str] = []

        context_str = ""
        if rag_context:
            summaries = []
            for item in rag_context:
                meta = item.get("metadata", {})
                brief_id = meta.get("brief_id", "")
                if brief_id and brief_id not in rag_brief_ids:
                    rag_brief_ids.append(brief_id)
                summaries.append(
                    f"- Prior research on '{meta.get('query', 'N/A')}': "
                    f"{item['content'][:200]}"
                )
            context_str = (
                "\n\nRelevant prior research from PRISM memory:\n"
                + "\n".join(summaries)
                + "\n\nFocus new agents on GAPS not already covered above."
            )

            # Surface RAG usage as a visible event so the UI can show it
            await emit(
                EventType.RAG_CONTEXT_USED,
                {
                    "context_used": True,
                    "related_queries": [
                        item.get("metadata", {}).get("query", "")
                        for item in rag_context
                    ],
                    "brief_ids": rag_brief_ids,
                },
            )

        messages = [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Query: {query}{context_str}"},
        ]

        parsed = await groq_client.complete_json(
            messages=messages,
            model=settings.groq_planner_model,
        )

        agents = []
        for spec in parsed.get("agents", [])[:5]:
            agents.append(AgentSpec(
                agent_id=uuid.uuid4().hex[:12],
                agent_type=spec.get("agent_type", "web_research"),
                focus_area=spec.get("focus_area", ""),
                search_queries=spec.get("search_queries", [query]),
                priority=min(max(spec.get("priority", 3), 1), 5),
            ))

        # Ensure minimum 3 agents
        while len(agents) < 3:
            agents.append(AgentSpec(
                agent_id=uuid.uuid4().hex[:12],
                agent_type="web_research",
                focus_area=f"General research on: {query}",
                search_queries=[query],
                priority=2,
            ))

        return AgentPlan(
            query=query,
            analysis=parsed.get("reasoning", parsed.get("analysis", "")),
            agents=agents,
            rag_context_used=rag_used,
            rag_brief_ids=rag_brief_ids,
        )
