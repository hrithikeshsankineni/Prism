import logging
from typing import Callable, Coroutine, List

from backend.config import settings
from backend.core.confidence import boost_for_corroboration
from backend.core.groq_client import groq_client
from backend.schemas.agent_schemas import (
    AgentPlan,
    AgentResult,
    BriefSection,
    Contradiction,
    DraftBrief,
    Source,
)
from backend.schemas.event_schemas import EventType

logger = logging.getLogger(__name__)

CONTRADICTION_PROMPT = """You are a senior analyst cross-checking findings from multiple research agents.

Identify GENUINE contradictions — cases where two agents make DIRECTLY conflicting factual claims
about the same subject. Do not flag mere differences in emphasis or framing.

For each real contradiction, explain which source is more likely correct and why.

Respond in JSON:
{
  "contradictions": [
    {
      "claim_a": "First claim verbatim",
      "claim_b": "Conflicting claim verbatim",
      "agent_a_id": "agent label (e.g. 'Web Research (transformer architecture)')",
      "agent_b_id": "agent label (e.g. 'Domain Specialist (GPU benchmarks)')",
      "resolution": "Which is more credible and why, referring to agents by their label",
      "resolved": true
    }
  ]
}

If no genuine contradictions exist, return: {"contradictions": []}"""

SYNTHESIS_PROMPT = """You are the Synthesis Agent for PRISM.

Merge findings from multiple research agents into a structured intelligence brief.
Think through the evidence before writing.

Rules:
1. Write an executive summary that answers the user's query directly (2–3 sentences).
2. Group findings into 3–5 logical sections; each section must have a clear title.
3. Weight claims by confidence: high-confidence facts (>0.8) lead each section;
   low-confidence claims (<0.5) appear only if corroborated by multiple agents.
4. Cite source URLs for each section.
5. Do NOT invent claims. Only synthesise what the agents found.

Respond in JSON:
{
  "reasoning": "2-3 sentences: what is the overall picture the agents collectively paint?",
  "executive_summary": "Direct 2–3 sentence answer to the query",
  "sections": [
    {
      "title": "Section Name",
      "content": "Synthesised prose — specific, not vague",
      "source_urls": ["url1", "url2"],
      "confidence": 0.85
    }
  ],
  "overall_confidence": 0.78
}"""


class SynthesisAgent:
    """Merges AgentResults into a coherent DraftBrief with cross-agent corroboration."""

    async def synthesize(
        self,
        query: str,
        plan: AgentPlan,
        results: List[AgentResult],
        emit: Callable[..., Coroutine],
    ) -> DraftBrief:
        await emit(EventType.SYNTHESIS_STARTED, {})

        completed = [r for r in results if r.status == "completed"]
        failed_count = len(results) - len(completed)

        all_sources: List[Source] = []
        for r in completed:
            all_sources.extend(r.sources)

        # ----------------------------------------------------------------
        # Build findings text for LLM (include computed confidence scores)
        # ----------------------------------------------------------------
        spec_map = {spec.agent_id: spec for spec in plan.agents}
        agent_labels: dict[str, str] = {}
        for r in completed:
            spec = spec_map.get(r.agent_id)
            focus = spec.focus_area if spec else r.agent_type
            label = f"{r.agent_type.replace('_', ' ').title()} ({focus})"
            agent_labels[r.agent_id] = label

        findings_text = ""
        for r in completed:
            label = agent_labels[r.agent_id]
            findings_text += (
                f"\n--- {label} | confidence: {r.confidence_score:.2f} ---\n"
            )
            for f in r.findings:
                findings_text += (
                    f"  [{f.category}] conf={f.confidence:.2f} | {f.claim}\n"
                    f"  Sources: {', '.join(f.supporting_sources[:3])}\n"
                )

        # ----------------------------------------------------------------
        # Pass 1: detect contradictions across agents
        # ----------------------------------------------------------------
        contradictions: List[Contradiction] = []
        if len(completed) > 1:
            try:
                contra_parsed = await groq_client.complete_json(
                    messages=[
                        {"role": "system", "content": CONTRADICTION_PROMPT},
                        {"role": "user", "content": f"Query: {query}\n\nFindings:\n{findings_text}"},
                    ],
                    model=settings.groq_synthesis_model,
                )
                for c in contra_parsed.get("contradictions", []):
                    contradiction = Contradiction(
                        claim_a=c.get("claim_a", ""),
                        claim_b=c.get("claim_b", ""),
                        agent_a_id=c.get("agent_a_id", ""),
                        agent_b_id=c.get("agent_b_id", ""),
                        resolution=c.get("resolution", ""),
                        resolved=c.get("resolved", False),
                    )
                    contradictions.append(contradiction)
                    await emit(
                        EventType.AGENT_CONFLICT_DETECTED,
                        {
                            "claim_a": contradiction.claim_a,
                            "claim_b": contradiction.claim_b,
                            "agents": [contradiction.agent_a_id, contradiction.agent_b_id],
                        },
                    )
            except Exception as e:
                logger.warning(f"Contradiction detection failed: {e}")

        # ----------------------------------------------------------------
        # Pass 2: cross-agent corroboration — boost section confidence
        # where multiple agents surfaced consistent findings
        # ----------------------------------------------------------------
        corroboration_map = self._build_corroboration_map(completed)

        # ----------------------------------------------------------------
        # Pass 3: full synthesis with chain-of-thought
        # ----------------------------------------------------------------
        contra_text = ""
        if contradictions:
            contra_text = "\n\nKnown contradictions:\n" + "\n".join(
                f"- '{c.claim_a}' vs '{c.claim_b}' → resolution: {c.resolution}"
                for c in contradictions
            )

        corroboration_hint = ""
        if corroboration_map:
            top = sorted(corroboration_map.items(), key=lambda x: -x[1])[:3]
            corroboration_hint = "\n\nHighly corroborated topics (multiple agents agree):\n" + "\n".join(
                f"- '{kw}' mentioned by {n} agents" for kw, n in top
            )

        parsed = await groq_client.complete_json(
            messages=[
                {"role": "system", "content": SYNTHESIS_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Query: {query}\n\n"
                        f"Findings from {len(completed)} agents "
                        f"({failed_count} failed):\n{findings_text}"
                        f"{contra_text}"
                        f"{corroboration_hint}"
                    ),
                },
            ],
            model=settings.groq_synthesis_model,
        )

        sections = []
        for s in parsed.get("sections", []):
            raw_conf = min(max(s.get("confidence", 0.5), 0.0), 1.0)
            # Boost section confidence if multiple agents converge on this topic
            section_title = s.get("title", "").lower()
            agreeing = corroboration_map.get(section_title, 1)
            boosted_conf = boost_for_corroboration(raw_conf, agreeing)
            sections.append(BriefSection(
                title=s.get("title", ""),
                content=s.get("content", ""),
                source_urls=s.get("source_urls", []),
                confidence=boosted_conf,
            ))

        draft = DraftBrief(
            query=query,
            executive_summary=parsed.get("executive_summary", ""),
            sections=sections,
            contradictions=contradictions,
            all_sources=all_sources,
            overall_confidence=min(max(parsed.get("overall_confidence", 0.5), 0.0), 1.0),
            agent_results_used=len(completed),
            agent_results_failed=failed_count,
        )

        await emit(
            EventType.SYNTHESIS_COMPLETE,
            {
                "sections_count": len(sections),
                "contradictions_count": len(contradictions),
            },
        )

        return draft

    @staticmethod
    def _build_corroboration_map(completed: List[AgentResult]) -> dict:
        """
        Count how many agents mention each significant keyword in their findings.
        Used to identify topics that have cross-agent consensus.
        """
        from collections import Counter
        import re

        keyword_agents: dict = {}
        for agent in completed:
            agent_keywords: set = set()
            for finding in agent.findings:
                # Extract meaningful words (>4 chars) from each claim
                words = re.findall(r"\b[a-zA-Z]{5,}\b", finding.claim.lower())
                agent_keywords.update(words)
            for kw in agent_keywords:
                keyword_agents.setdefault(kw, set()).add(agent.agent_id)

        # Only keep keywords mentioned by 2+ agents
        return {
            kw: len(agents)
            for kw, agents in keyword_agents.items()
            if len(agents) >= 2
        }
