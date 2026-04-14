import asyncio
import logging
from collections import deque
from typing import Any, Callable, Coroutine, Dict, List, Optional

from backend.agents.critic import CriticAgent
from backend.agents.eval_agent import EvalAgent
from backend.agents.planner import PlannerAgent
from backend.agents.researcher import ResearchAgent
from backend.agents.synthesis import SynthesisAgent
from backend.config import settings
from backend.core.metrics import PipelineMetrics, set_metrics
from backend.core.rag import rag_memory
from backend.schemas.agent_schemas import AgentResult, AgentSpec, FinalBrief
from backend.schemas.event_schemas import EventType, WSEvent

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """
    Drives the full PRISM pipeline with parallel execution and event streaming.

    Stage order:
        Plan → [Research × N (parallel)] → Synthesise → Critique → Evaluate → Store → Emit
    """

    def __init__(self) -> None:
        self._planner = PlannerAgent()
        self._researcher = ResearchAgent()
        self._synthesis = SynthesisAgent()
        self._critic = CriticAgent()
        self._eval = EvalAgent()

        # Per-session state
        self._event_buffers: Dict[str, deque] = {}
        self._sequence_counters: Dict[str, int] = {}

    def _get_emit(
        self,
        session_id: str,
        ws_send: Callable[[dict], Coroutine],
    ) -> Callable[..., Coroutine]:
        """Create an event emitter bound to a session."""

        async def emit(
            event_type: EventType,
            data: Dict[str, Any],
            agent_id: Optional[str] = None,
            agent_type: Optional[str] = None,
        ) -> None:
            seq = self._sequence_counters.get(session_id, 0) + 1
            self._sequence_counters[session_id] = seq

            event = WSEvent(
                event_type=event_type,
                agent_id=agent_id,
                agent_type=agent_type,
                data=data,
                sequence=seq,
                session_id=session_id,
            )

            if session_id not in self._event_buffers:
                self._event_buffers[session_id] = deque(maxlen=200)
            self._event_buffers[session_id].append(event)

            try:
                await ws_send(event.model_dump())
            except Exception as e:
                logger.warning(f"Failed to send event: {e}")

        return emit

    async def run_pipeline(
        self,
        query: str,
        session_id: str,
        ws_send: Callable[[dict], Coroutine],
    ) -> FinalBrief:
        """Execute the full PRISM pipeline."""
        emit = self._get_emit(session_id, ws_send)

        # Initialise per-session metrics and bind to this async task tree
        metrics = PipelineMetrics(session_id=session_id)
        set_metrics(metrics)

        await emit(EventType.PIPELINE_STARTED, {"query": query, "session_id": session_id})

        try:
            # 1. Plan
            metrics.stage_start("planner")
            plan = await self._planner.plan(query, emit)
            metrics.stage_end("planner")

            # 2. Research agents — staggered parallel launch
            metrics.stage_start("research")
            tasks = [
                asyncio.create_task(self._run_research_agent(spec, i, emit))
                for i, spec in enumerate(plan.agents)
            ]
            results: List[Any] = await asyncio.gather(*tasks, return_exceptions=True)
            metrics.stage_end("research")

            agent_results: List[AgentResult] = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    spec = plan.agents[i]
                    agent_results.append(AgentResult(
                        agent_id=spec.agent_id,
                        agent_type=spec.agent_type,
                        status="failed",
                        error_message=str(result),
                        thoughts=[f"Exception: {result}"],
                    ))
                else:
                    agent_results.append(result)

            completed = [r for r in agent_results if r.status == "completed"]
            if not completed:
                await emit(EventType.PIPELINE_ERROR, {"error": "All research agents failed"})
                raise RuntimeError("All research agents failed")

            # 3. Synthesis
            metrics.stage_start("synthesis")
            draft = await self._synthesis.synthesize(query, plan, agent_results, emit)
            metrics.stage_end("synthesis")

            # 4. Critic
            metrics.stage_start("critic")
            review = await self._critic.critique(draft, agent_results, emit)
            metrics.stage_end("critic")

            # 5. Build FinalBrief
            final_brief = FinalBrief(
                query=query,
                executive_summary=draft.executive_summary,
                sections=draft.sections,
                challenged_claims=review.challenged_claims,
                contradictions=draft.contradictions,
                missing_perspectives=review.missing_perspectives,
                all_sources=draft.all_sources,
                overall_confidence=draft.overall_confidence,
                credibility_score=review.credibility_score,
                agent_count=len(plan.agents),
                agent_failures=len(agent_results) - len(completed),
            )

            # 6. Eval
            metrics.stage_start("eval")
            scorecard = await self._eval.evaluate(final_brief, agent_results, emit)
            metrics.stage_end("eval")
            final_brief.scorecard = scorecard

            # 7. Store in RAG memory
            await rag_memory.store_brief(final_brief)

            # 8. Emit pipeline metrics before complete
            await emit(
                EventType.PIPELINE_METRICS,
                metrics.to_dict(),
            )

            # 9. Pipeline complete
            await emit(
                EventType.PIPELINE_COMPLETE,
                {
                    "brief": final_brief.model_dump(),
                    "scorecard": scorecard.model_dump(),
                },
            )

            return final_brief

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            await emit(EventType.PIPELINE_ERROR, {"error": str(e)})
            raise

    async def _run_research_agent(
        self,
        spec: AgentSpec,
        index: int,
        emit: Callable[..., Coroutine],
    ) -> AgentResult:
        """Run one research agent with staggered start and timeout."""
        if index > 0:
            await asyncio.sleep(settings.agent_stagger_seconds * index)

        try:
            return await asyncio.wait_for(
                self._researcher.research(
                    agent_id=spec.agent_id,
                    agent_type=spec.agent_type,
                    search_queries=spec.search_queries,
                    focus_area=spec.focus_area,
                    emit=emit,
                ),
                timeout=settings.agent_timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Agent {spec.agent_id} timed out")
            await emit(
                EventType.AGENT_FAILED,
                {"error": f"Timeout after {settings.agent_timeout_seconds}s"},
                agent_id=spec.agent_id,
                agent_type=spec.agent_type,
            )
            return AgentResult(
                agent_id=spec.agent_id,
                agent_type=spec.agent_type,
                status="timeout",
                error_message=f"Timeout after {settings.agent_timeout_seconds}s",
                thoughts=["Agent timed out"],
            )

    def get_replay_events(self, session_id: str, after_sequence: int) -> List[dict]:
        """Return buffered events after a given sequence for reconnection replay."""
        buffer = self._event_buffers.get(session_id, deque())
        return [e.model_dump() for e in buffer if e.sequence > after_sequence]

    def cleanup_session(self, session_id: str) -> None:
        self._event_buffers.pop(session_id, None)
        self._sequence_counters.pop(session_id, None)
