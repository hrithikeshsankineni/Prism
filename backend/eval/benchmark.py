"""
Offline evaluation harness for PRISM.

Runs a curated set of benchmark queries against the live pipeline and uses
an LLM judge to score whether each expected fact appears in the final brief.

This separates evaluation from capability — the pipeline cannot grade its own
homework. Each case has ground-truth claims sourced independently.

Usage:
    python -m backend.eval.benchmark

Output: per-case recall scores + aggregate pass rate.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Benchmark cases
# Each case defines:
#   query        : the input to PRISM
#   expected_facts: a list of claims that should appear in a correct brief.
#                   These are independently verifiable facts, not opinions.
# ---------------------------------------------------------------------------
BENCHMARK_CASES = [
    {
        "id": "nvidia_h100",
        "query": "NVIDIA H100 GPU supply and demand 2024",
        "expected_facts": [
            "H100 is based on the Hopper architecture",
            "NVIDIA dominates the AI accelerator market",
            "H100 GPUs were in high demand from cloud providers",
            "TSMC manufactures NVIDIA GPUs",
        ],
    },
    {
        "id": "openai_gpt4",
        "query": "OpenAI GPT-4 capabilities and limitations",
        "expected_facts": [
            "GPT-4 is a multimodal model",
            "GPT-4 has a knowledge cutoff date",
            "GPT-4 can hallucinate or generate incorrect information",
            "OpenAI released GPT-4 in 2023",
        ],
    },
    {
        "id": "apple_revenue",
        "query": "Apple Inc revenue breakdown by segment 2024",
        "expected_facts": [
            "iPhone is Apple's largest revenue segment",
            "Apple has a Services segment including the App Store",
            "Apple generates revenue from Mac and iPad product lines",
        ],
    },
    {
        "id": "transformer_architecture",
        "query": "transformer neural network architecture attention mechanism",
        "expected_facts": [
            "Transformers use self-attention mechanisms",
            "The original transformer paper is 'Attention Is All You Need'",
            "Transformers replaced recurrent neural networks for many NLP tasks",
            "Multi-head attention allows the model to attend to different positions",
        ],
    },
    {
        "id": "electric_vehicles",
        "query": "electric vehicle market share and adoption 2024",
        "expected_facts": [
            "Tesla is a leading electric vehicle manufacturer",
            "China is the largest EV market by volume",
            "Battery range and charging infrastructure are key adoption barriers",
        ],
    },
]

# ---------------------------------------------------------------------------
# LLM judge prompt
# ---------------------------------------------------------------------------
JUDGE_PROMPT = """You are an objective evaluator. Given a research brief and a list of
expected facts, determine which expected facts are COVERED in the brief.

A fact is "covered" if the brief contains a claim that conveys the same information,
even if worded differently. It is NOT covered if it is missing or contradicted.

Respond in JSON:
{
  "evaluations": [
    {"fact": "the expected fact", "covered": true/false, "explanation": "brief reason"}
  ],
  "recall_score": 0.75
}"""


@dataclass
class CaseResult:
    case_id: str
    query: str
    expected_facts: List[str]
    covered_facts: List[str] = field(default_factory=list)
    missed_facts: List[str] = field(default_factory=list)
    recall_score: float = 0.0
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "query": self.query,
            "recall_score": self.recall_score,
            "covered": self.covered_facts,
            "missed": self.missed_facts,
            "error": self.error,
        }


async def evaluate_case(case: dict) -> CaseResult:
    """Run one benchmark case end-to-end and score it."""
    from backend.core.groq_client import groq_client
    from backend.config import settings

    result = CaseResult(
        case_id=case["id"],
        query=case["query"],
        expected_facts=case["expected_facts"],
    )

    # Run the full pipeline inline
    try:
        import uuid
        from backend.core.orchestrator import PipelineOrchestrator

        session_id = uuid.uuid4().hex
        orch = PipelineOrchestrator()
        events_collected = []

        async def collect(event: dict) -> None:
            events_collected.append(event)

        brief = await orch.run_pipeline(
            query=case["query"],
            session_id=session_id,
            ws_send=collect,
        )

        # Build brief text for the judge
        brief_text = f"Query: {brief.query}\n\n"
        brief_text += f"Executive Summary: {brief.executive_summary}\n\n"
        for section in brief.sections:
            brief_text += f"## {section.title}\n{section.content}\n\n"

        # LLM judge: score coverage
        judge_messages = [
            {"role": "system", "content": JUDGE_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Brief:\n{brief_text}\n\n"
                    f"Expected facts:\n"
                    + "\n".join(f"- {f}" for f in case["expected_facts"])
                ),
            },
        ]
        judge_response = await groq_client.complete_json(
            messages=judge_messages,
            model=settings.groq_eval_model,
        )

        for ev in judge_response.get("evaluations", []):
            if ev.get("covered"):
                result.covered_facts.append(ev["fact"])
            else:
                result.missed_facts.append(ev["fact"])

        result.recall_score = judge_response.get("recall_score", 0.0)

    except Exception as e:
        result.error = str(e)
        logger.error(f"Benchmark case {case['id']} failed: {e}", exc_info=True)

    return result


async def run_benchmark(cases: list = BENCHMARK_CASES) -> None:
    """Run all benchmark cases sequentially (to avoid rate-limit bursts)."""
    logging.basicConfig(level=logging.WARNING)

    print(f"\n{'=' * 60}")
    print(f"  PRISM Benchmark  —  {len(cases)} cases")
    print(f"{'=' * 60}\n")

    results: List[CaseResult] = []
    for case in cases:
        print(f"Running: [{case['id']}] {case['query'][:60]}...")
        result = await evaluate_case(case)
        results.append(result)

        if result.error:
            print(f"  ERROR: {result.error}")
        else:
            print(f"  Recall: {result.recall_score:.0%}  "
                  f"({len(result.covered_facts)}/{len(result.expected_facts)} facts covered)")
            if result.missed_facts:
                for mf in result.missed_facts:
                    print(f"    MISSED: {mf}")
        print()

    # Aggregate
    scored = [r for r in results if not r.error]
    if scored:
        avg_recall = sum(r.recall_score for r in scored) / len(scored)
        pass_rate = sum(1 for r in scored if r.recall_score >= 0.75) / len(scored)
        print(f"{'=' * 60}")
        print(f"  Average recall : {avg_recall:.1%}")
        print(f"  Pass rate (≥75%): {pass_rate:.0%}  ({sum(1 for r in scored if r.recall_score >= 0.75)}/{len(scored)} cases)")
        print(f"{'=' * 60}\n")

    # Dump full results as JSON
    output_path = "benchmark_results.json"
    with open(output_path, "w") as f:
        json.dump([r.to_dict() for r in results], f, indent=2)
    print(f"Full results saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
