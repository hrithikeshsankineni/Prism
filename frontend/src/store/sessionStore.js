import { create } from "zustand";

const useSessionStore = create((set, get) => ({
  sessionId: null,
  query: "",
  pipelineStatus: "idle", // idle | running | complete | error
  agents: {}, // keyed by agent_id
  draftBrief: null,
  criticReview: null,
  finalBrief: null,
  evalScorecard: null,
  priorBriefs: [],
  conflicts: [],
  events: [],
  lastSequence: 0,
  error: null,
  ragContext: null,       // { related_queries, brief_ids } when memory is used
  pipelineMetrics: null,  // { total_duration_ms, total_tokens, stages }

  setQuery: (query) => set({ query }),

  startPipeline: (sessionId) =>
    set({
      sessionId,
      pipelineStatus: "running",
      agents: {},
      draftBrief: null,
      criticReview: null,
      finalBrief: null,
      evalScorecard: null,
      conflicts: [],
      events: [],
      lastSequence: 0,
      error: null,
      ragContext: null,
      pipelineMetrics: null,
    }),

  setPriorBriefs: (briefs) => set({ priorBriefs: briefs }),

  handleEvent: (event) => {
    const state = get();
    const newEvents = [...state.events, event];
    const seq = event.sequence || state.lastSequence;
    const base = { events: newEvents, lastSequence: seq };

    switch (event.event_type) {
      case "PIPELINE_STARTED":
        set({ ...base, pipelineStatus: "running" });
        break;

      case "RAG_CONTEXT_USED":
        set({
          ...base,
          ragContext: {
            relatedQueries: event.data?.related_queries || [],
            briefIds: event.data?.brief_ids || [],
          },
        });
        break;

      case "AGENT_STARTED":
        set({
          ...base,
          agents: {
            ...state.agents,
            [event.agent_id]: {
              id: event.agent_id,
              type: event.agent_type,
              status: "searching",
              thoughts: [],
              findings: [],
              confidence: null,
              error: null,
              focusArea: event.data?.focus_area || "",
              requeryCount: 0,
            },
          },
        });
        break;

      case "AGENT_SEARCHING": {
        const agent = state.agents[event.agent_id];
        if (agent) {
          set({
            ...base,
            agents: {
              ...state.agents,
              [event.agent_id]: {
                ...agent,
                status: "searching",
                thoughts: [...agent.thoughts, `Searching: ${event.data?.query || ""}`],
              },
            },
          });
        } else {
          set(base);
        }
        break;
      }

      case "AGENT_REQUERYING": {
        const agent = state.agents[event.agent_id];
        if (agent) {
          set({
            ...base,
            agents: {
              ...state.agents,
              [event.agent_id]: {
                ...agent,
                status: "requerying",
                requeryCount: (agent.requeryCount || 0) + 1,
                thoughts: [
                  ...agent.thoughts,
                  `Gap found — re-querying: ${event.data?.gap_query || ""}`,
                ],
              },
            },
          });
        } else {
          set(base);
        }
        break;
      }

      case "AGENT_THOUGHT": {
        const agent = state.agents[event.agent_id];
        if (agent) {
          set({
            ...base,
            agents: {
              ...state.agents,
              [event.agent_id]: {
                ...agent,
                thoughts: [...agent.thoughts, event.data?.thought || ""],
              },
            },
          });
        } else {
          set(base);
        }
        break;
      }

      case "AGENT_FOUND": {
        const agent = state.agents[event.agent_id];
        if (agent) {
          set({
            ...base,
            agents: {
              ...state.agents,
              [event.agent_id]: {
                ...agent,
                findingsCount: event.data?.findings_count || 0,
              },
            },
          });
        } else {
          set(base);
        }
        break;
      }

      case "AGENT_COMPLETE": {
        const agent = state.agents[event.agent_id];
        if (agent) {
          set({
            ...base,
            agents: {
              ...state.agents,
              [event.agent_id]: {
                ...agent,
                status: "complete",
                confidence: event.data?.confidence,
                findingsCount: event.data?.findings_count || agent.findingsCount,
              },
            },
          });
        } else {
          set(base);
        }
        break;
      }

      case "AGENT_FAILED": {
        const agent = state.agents[event.agent_id];
        if (agent) {
          set({
            ...base,
            agents: {
              ...state.agents,
              [event.agent_id]: {
                ...agent,
                status: "failed",
                error: event.data?.error || "Unknown error",
              },
            },
          });
        } else {
          set(base);
        }
        break;
      }

      case "AGENT_CONFLICT_DETECTED":
        set({ ...base, conflicts: [...state.conflicts, event.data] });
        break;

      case "SYNTHESIS_STARTED":
      case "SYNTHESIS_COMPLETE":
      case "CRITIC_STARTED":
      case "CRITIC_COMPLETE":
        set(base);
        break;

      case "EVAL_COMPLETE":
        set({ ...base, evalScorecard: event.data });
        break;

      case "PIPELINE_METRICS":
        set({ ...base, pipelineMetrics: event.data });
        break;

      case "PIPELINE_COMPLETE":
        set({
          ...base,
          pipelineStatus: "complete",
          finalBrief: event.data?.brief || null,
          evalScorecard: event.data?.scorecard || state.evalScorecard,
        });
        break;

      case "PIPELINE_ERROR":
        set({
          ...base,
          pipelineStatus: "error",
          error: event.data?.error || "Pipeline failed",
        });
        break;

      default:
        set(base);
    }
  },

  reset: () =>
    set({
      sessionId: null,
      query: "",
      pipelineStatus: "idle",
      agents: {},
      draftBrief: null,
      criticReview: null,
      finalBrief: null,
      evalScorecard: null,
      conflicts: [],
      events: [],
      lastSequence: 0,
      error: null,
      ragContext: null,
      pipelineMetrics: null,
    }),
}));

export default useSessionStore;
