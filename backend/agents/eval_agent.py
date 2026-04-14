import logging
from typing import Callable, Coroutine, List

from backend.config import settings
from backend.core.groq_client import groq_client
from backend.schemas.agent_schemas import (
    AgentResult,
    EvalScorecard,
    FinalBrief,
    ScoreDimension,
)
from backend.schemas.event_schemas import EventType

logger = logging.getLogger(__name__)

EVAL_PROMPT = """You are the Eval Agent for PRISM. Score the final intelligence brief on quality dimensions.

For each dimension, give a score from 0.0 to 1.0 and a brief justification:

1. factual_consistency: Are claims consistent with each other and with the sources cited?
2. source_coverage: How well do the sources cover the topic? Are there enough diverse sources?
3. confidence_calibration: Are confidence scores appropriate for the evidence strength?
4. completeness: Does the brief cover the topic thoroughly? Are there obvious gaps?

Also provide an overall_score (weighted average) and a 1-2 sentence summary.

Respond in JSON:
{
  "factual_consistency": {"score": 0.85, "justification": "..."},
  "source_coverage": {"score": 0.72, "justification": "..."},
  "confidence_calibration": {"score": 0.80, "justification": "..."},
  "completeness": {"score": 0.68, "justification": "..."},
  "overall_score": 0.76,
  "summary": "One or two sentence assessment"
}"""


class EvalAgent:
    """Auto-scores the final brief on quality dimensions."""

    async def evaluate(
        self,
        brief: FinalBrief,
        agent_results: List[AgentResult],
        emit: Callable[..., Coroutine],
    ) -> EvalScorecard:
        # Format brief for evaluation
        brief_text = f"Query: {brief.query}\n"
        brief_text += f"Executive Summary: {brief.executive_summary}\n\n"
        for section in brief.sections:
            brief_text += f"## {section.title} (conf: {section.confidence})\n"
            brief_text += f"{section.content}\n\n"

        if brief.challenged_claims:
            brief_text += "## Challenged Claims\n"
            for cc in brief.challenged_claims:
                brief_text += f"- {cc.claim} ({cc.severity}): {cc.challenge_reason}\n"

        brief_text += f"\nSources: {len(brief.all_sources)}"
        brief_text += f"\nAgents used: {brief.agent_count}, failures: {brief.agent_failures}"

        messages = [
            {"role": "system", "content": EVAL_PROMPT},
            {"role": "user", "content": brief_text},
        ]

        parsed = await groq_client.complete_json(
            messages=messages,
            model=settings.groq_eval_model,
        )

        def _parse_dim(key: str) -> ScoreDimension:
            dim = parsed.get(key, {})
            if isinstance(dim, dict):
                return ScoreDimension(
                    score=min(max(dim.get("score", 0.5), 0.0), 1.0),
                    justification=dim.get("justification", ""),
                )
            return ScoreDimension(score=0.5, justification="Could not evaluate")

        scorecard = EvalScorecard(
            factual_consistency=_parse_dim("factual_consistency"),
            source_coverage=_parse_dim("source_coverage"),
            confidence_calibration=_parse_dim("confidence_calibration"),
            completeness=_parse_dim("completeness"),
            overall_score=min(max(parsed.get("overall_score", 0.5), 0.0), 1.0),
            summary=parsed.get("summary", ""),
        )

        await emit(
            EventType.EVAL_COMPLETE,
            {
                "factual_consistency": scorecard.factual_consistency.score,
                "source_coverage": scorecard.source_coverage.score,
                "confidence_calibration": scorecard.confidence_calibration.score,
                "completeness": scorecard.completeness.score,
                "overall_score": scorecard.overall_score,
            },
        )

        return scorecard
