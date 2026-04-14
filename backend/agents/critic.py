import logging
from typing import Callable, Coroutine, List

from backend.config import settings
from backend.core.groq_client import groq_client
from backend.schemas.agent_schemas import (
    AgentResult,
    ChallengedClaim,
    CriticReview,
    DraftBrief,
)
from backend.schemas.event_schemas import EventType

logger = logging.getLogger(__name__)

CRITIC_PROMPT = """You are the Critic Agent for PRISM. Your job is to red-team an intelligence brief.

Review the draft brief against the raw research findings and identify:
1. Claims not directly supported by any source
2. Claims that overstate confidence relative to the evidence
3. Missing perspectives or viewpoints not explored
4. Logical gaps or leaps in reasoning

For each challenged claim, rate severity as "low", "medium", or "high".

Respond in JSON:
{
  "challenged_claims": [
    {
      "claim": "The specific claim being challenged",
      "section_title": "Which section it appears in",
      "challenge_reason": "Why this claim is problematic",
      "severity": "medium",
      "suggestion": "What should be done about it"
    }
  ],
  "missing_perspectives": ["perspective 1", "perspective 2"],
  "logical_gaps": ["gap 1"],
  "overall_assessment": "Narrative summary of the brief's credibility",
  "credibility_score": 0.75
}"""


class CriticAgent:
    """Red-teams the draft brief, flags unsupported or overconfident claims."""

    async def critique(
        self,
        draft: DraftBrief,
        agent_results: List[AgentResult],
        emit: Callable[..., Coroutine],
    ) -> CriticReview:
        await emit(EventType.CRITIC_STARTED, {})

        # Format the draft brief
        brief_text = f"Executive Summary: {draft.executive_summary}\n\n"
        for section in draft.sections:
            brief_text += f"## {section.title} (confidence: {section.confidence})\n"
            brief_text += f"{section.content}\n\n"

        # Format raw findings for comparison
        raw_findings = ""
        for r in agent_results:
            if r.status != "completed":
                continue
            raw_findings += f"\n--- Agent {r.agent_id} ({r.agent_type}) ---\n"
            for f in r.findings:
                raw_findings += f"  - {f.claim} (conf: {f.confidence}, sources: {len(f.supporting_sources)})\n"

        messages = [
            {"role": "system", "content": CRITIC_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Draft Brief:\n{brief_text}\n\n"
                    f"Raw Agent Findings:\n{raw_findings}"
                ),
            },
        ]

        parsed = await groq_client.complete_json(
            messages=messages,
            model=settings.groq_critic_model,
        )

        challenged = []
        for c in parsed.get("challenged_claims", []):
            challenged.append(ChallengedClaim(
                claim=c.get("claim", ""),
                section_title=c.get("section_title", ""),
                challenge_reason=c.get("challenge_reason", ""),
                severity=c.get("severity", "medium"),
                suggestion=c.get("suggestion", ""),
            ))

        review = CriticReview(
            challenged_claims=challenged,
            missing_perspectives=parsed.get("missing_perspectives", []),
            logical_gaps=parsed.get("logical_gaps", []),
            overall_assessment=parsed.get("overall_assessment", ""),
            credibility_score=min(
                max(parsed.get("credibility_score", 0.5), 0.0), 1.0
            ),
        )

        await emit(
            EventType.CRITIC_COMPLETE,
            {
                "challenged_claims_count": len(challenged),
                "credibility_score": review.credibility_score,
            },
        )

        return review
