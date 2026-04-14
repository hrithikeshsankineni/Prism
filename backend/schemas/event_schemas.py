from enum import Enum
from time import time
from typing import Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    PIPELINE_STARTED = "PIPELINE_STARTED"
    AGENT_STARTED = "AGENT_STARTED"
    AGENT_SEARCHING = "AGENT_SEARCHING"
    AGENT_THOUGHT = "AGENT_THOUGHT"
    AGENT_FOUND = "AGENT_FOUND"
    AGENT_REQUERYING = "AGENT_REQUERYING"          # dynamic follow-up search
    AGENT_CONFLICT_DETECTED = "AGENT_CONFLICT_DETECTED"
    AGENT_COMPLETE = "AGENT_COMPLETE"
    AGENT_FAILED = "AGENT_FAILED"
    RAG_CONTEXT_USED = "RAG_CONTEXT_USED"          # planner used memory
    SYNTHESIS_STARTED = "SYNTHESIS_STARTED"
    SYNTHESIS_COMPLETE = "SYNTHESIS_COMPLETE"
    CRITIC_STARTED = "CRITIC_STARTED"
    CRITIC_COMPLETE = "CRITIC_COMPLETE"
    EVAL_COMPLETE = "EVAL_COMPLETE"
    PIPELINE_METRICS = "PIPELINE_METRICS"          # latency + token telemetry
    PIPELINE_COMPLETE = "PIPELINE_COMPLETE"
    PIPELINE_ERROR = "PIPELINE_ERROR"


class WSEvent(BaseModel):
    event_type: EventType
    agent_id: Optional[str] = None
    agent_type: Optional[str] = None
    data: dict = Field(default_factory=dict)
    sequence: int = 0
    timestamp: float = Field(default_factory=time)
    session_id: str = ""
