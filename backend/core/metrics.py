"""
Pipeline observability: per-stage latency and LLM token usage.

Uses asyncio ContextVar so each concurrent session owns its own accumulator —
no locking, no global state collisions between simultaneous pipeline runs.

Pattern:
    # In orchestrator, at pipeline start:
    metrics = PipelineMetrics(session_id)
    set_metrics(metrics)

    # In any agent or client, no argument passing needed:
    m = get_metrics()
    if m:
        m.record_tokens("research", prompt_tokens, completion_tokens)
"""
from __future__ import annotations

import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Dict, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class StageMetrics:
    stage: str
    duration_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict:
        return {
            "duration_ms": self.duration_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class PipelineMetrics:
    session_id: str
    started_at: float = field(default_factory=time.time)
    stages: Dict[str, StageMetrics] = field(default_factory=dict)
    _stage_starts: Dict[str, float] = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------ timing

    def stage_start(self, stage: str) -> None:
        self._stage_starts[stage] = time.time()
        self.stages.setdefault(stage, StageMetrics(stage=stage))

    def stage_end(self, stage: str) -> None:
        start = self._stage_starts.pop(stage, None)
        if start is not None:
            self.stages.setdefault(stage, StageMetrics(stage=stage))
            self.stages[stage].duration_ms = round((time.time() - start) * 1000)

    # ------------------------------------------------------------------ tokens

    def record_tokens(self, stage: str, prompt: int, completion: int) -> None:
        self.stages.setdefault(stage, StageMetrics(stage=stage))
        self.stages[stage].prompt_tokens += prompt
        self.stages[stage].completion_tokens += completion

    # ---------------------------------------------------------------- summary

    @property
    def total_duration_ms(self) -> float:
        return round((time.time() - self.started_at) * 1000)

    @property
    def total_tokens(self) -> int:
        return sum(s.total_tokens for s in self.stages.values())

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "total_duration_ms": self.total_duration_ms,
            "total_tokens": self.total_tokens,
            "stages": {name: s.to_dict() for name, s in self.stages.items()},
        }


# ---------------------------------------------------------------------------
# ContextVar — one slot per async task tree (i.e. per pipeline run)
# ---------------------------------------------------------------------------

_current_metrics: ContextVar[Optional[PipelineMetrics]] = ContextVar(
    "current_metrics", default=None
)


def get_metrics() -> Optional[PipelineMetrics]:
    return _current_metrics.get()


def set_metrics(m: PipelineMetrics) -> None:
    _current_metrics.set(m)
