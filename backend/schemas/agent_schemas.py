from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


# --- Planner output ---


class AgentSpec(BaseModel):
    agent_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_type: str = Field(
        description="One of: web_research, news_sentiment, financial_market, domain_specific, academic"
    )
    focus_area: str = Field(description="What this agent should investigate")
    search_queries: List[str] = Field(
        description="1-3 specific search queries for Tavily"
    )
    priority: int = Field(default=3, ge=1, le=5, description="1=low, 5=critical")


class AgentPlan(BaseModel):
    query: str
    analysis: str = Field(description="Planner's analysis of query domain and intent")
    agents: List[AgentSpec] = Field(min_length=3, max_length=5)
    rag_context_used: bool = False
    rag_brief_ids: List[str] = Field(default_factory=list)


# --- Research agent output ---


class Source(BaseModel):
    url: str
    title: str
    domain: str = ""
    relevance_score: float = Field(default=0.0, ge=0, le=1)


class Finding(BaseModel):
    claim: str
    supporting_sources: List[str] = Field(
        default_factory=list, description="URLs that support this claim"
    )
    confidence: float = Field(ge=0, le=1)
    category: str = Field(
        default="fact",
        description="One of: fact, statistic, opinion, prediction",
    )


class AgentResult(BaseModel):
    agent_id: str
    agent_type: str
    status: str = Field(
        default="completed", description="completed | failed | timeout"
    )
    findings: List[Finding] = Field(default_factory=list)
    sources: List[Source] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0, le=1)
    thoughts: List[str] = Field(default_factory=list)
    search_queries_used: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    execution_time_seconds: float = 0.0
    requery_count: int = 0          # number of dynamic follow-up searches run


# --- Synthesis output ---


class BriefSection(BaseModel):
    title: str
    content: str
    source_urls: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)


class Contradiction(BaseModel):
    claim_a: str
    claim_b: str
    agent_a_id: str
    agent_b_id: str
    resolution: str = ""
    resolved: bool = False


class DraftBrief(BaseModel):
    query: str
    executive_summary: str
    sections: List[BriefSection] = Field(default_factory=list)
    contradictions: List[Contradiction] = Field(default_factory=list)
    all_sources: List[Source] = Field(default_factory=list)
    overall_confidence: float = Field(default=0.0, ge=0, le=1)
    agent_results_used: int = 0
    agent_results_failed: int = 0


# --- Critic output ---


class ChallengedClaim(BaseModel):
    claim: str
    section_title: str
    challenge_reason: str
    severity: str = Field(
        default="medium", description="low | medium | high"
    )
    suggestion: str = ""


class CriticReview(BaseModel):
    challenged_claims: List[ChallengedClaim] = Field(default_factory=list)
    missing_perspectives: List[str] = Field(default_factory=list)
    logical_gaps: List[str] = Field(default_factory=list)
    overall_assessment: str = ""
    credibility_score: float = Field(default=0.0, ge=0, le=1)


# --- Eval output ---


class ScoreDimension(BaseModel):
    score: float = Field(ge=0, le=1)
    justification: str = ""


class EvalScorecard(BaseModel):
    factual_consistency: ScoreDimension
    source_coverage: ScoreDimension
    confidence_calibration: ScoreDimension
    completeness: ScoreDimension
    overall_score: float = Field(ge=0, le=1)
    summary: str = ""


# --- Final brief ---


class FinalBrief(BaseModel):
    brief_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    query: str
    executive_summary: str
    sections: List[BriefSection] = Field(default_factory=list)
    challenged_claims: List[ChallengedClaim] = Field(default_factory=list)
    contradictions: List[Contradiction] = Field(default_factory=list)
    missing_perspectives: List[str] = Field(default_factory=list)
    all_sources: List[Source] = Field(default_factory=list)
    overall_confidence: float = Field(default=0.0, ge=0, le=1)
    credibility_score: float = Field(default=0.0, ge=0, le=1)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    agent_count: int = 0
    agent_failures: int = 0
    scorecard: Optional[EvalScorecard] = None
