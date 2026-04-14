import { AnimatePresence, motion } from "framer-motion";
import useSessionStore from "./store/sessionStore";
import QueryInput from "./components/QueryInput";
import AgentCard from "./components/AgentCard";
import FinalBrief from "./components/FinalBrief";
import EvalScorecard from "./components/EvalScorecard";
import PipelineMetrics from "./components/PipelineMetrics";
import PriorBriefs from "./components/PriorBriefs";

function PipelineStatus() {
  const status = useSessionStore((s) => s.pipelineStatus);
  const error = useSessionStore((s) => s.error);
  const conflicts = useSessionStore((s) => s.conflicts);

  if (status === "idle") return null;

  return (
    <div className="flex items-center gap-3 mb-4">
      {status === "running" && (
        <div className="flex items-center gap-2 text-sm text-cyan-400">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          Pipeline running...
        </div>
      )}
      {status === "complete" && (
        <div className="text-sm text-emerald-400">Pipeline complete</div>
      )}
      {status === "error" && (
        <div className="text-sm text-red-400">Error: {error}</div>
      )}
      {conflicts.length > 0 && (
        <motion.span
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          className="px-2 py-0.5 text-xs bg-red-500/20 text-red-400 rounded-full border border-red-500/30 animate-pulse"
        >
          {conflicts.length} conflict{conflicts.length > 1 ? "s" : ""} detected
        </motion.span>
      )}
    </div>
  );
}

function RAGIndicator() {
  const ragContext = useSessionStore((s) => s.ragContext);
  if (!ragContext) return null;

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      className="bg-violet-950/40 border border-violet-500/20 rounded-lg px-3 py-2"
    >
      <div className="flex items-center gap-1.5 mb-1">
        <span className="w-1.5 h-1.5 rounded-full bg-violet-400" />
        <span className="text-[10px] font-semibold text-violet-300 uppercase tracking-wider">
          Memory active
        </span>
      </div>
      {ragContext.relatedQueries?.length > 0 && (
        <p className="text-[10px] text-gray-400 leading-relaxed">
          Building on prior research:{" "}
          {ragContext.relatedQueries.slice(0, 2).map((q, i) => (
            <span key={i} className="text-violet-300 italic">
              "{q}"{i < Math.min(ragContext.relatedQueries.length, 2) - 1 ? ", " : ""}
            </span>
          ))}
        </p>
      )}
    </motion.div>
  );
}

export default function App() {
  const agents = useSessionStore((s) => s.agents);
  const finalBrief = useSessionStore((s) => s.finalBrief);
  const evalScorecard = useSessionStore((s) => s.evalScorecard);
  const pipelineMetrics = useSessionStore((s) => s.pipelineMetrics);
  const pipelineStatus = useSessionStore((s) => s.pipelineStatus);

  const agentList = Object.values(agents);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-violet-500 flex items-center justify-center">
            <span className="text-white font-bold text-sm">P</span>
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight">PRISM</h1>
            <p className="text-[10px] text-gray-500 uppercase tracking-widest">
              Multi-Agent Intelligence Platform
            </p>
          </div>
        </div>
      </header>

      <div className="flex h-[calc(100vh-73px)]">
        {/* Left Panel */}
        <aside className="w-72 border-r border-gray-800 p-4 flex flex-col gap-4 overflow-y-auto">
          <QueryInput />
          <AnimatePresence>
            <RAGIndicator />
          </AnimatePresence>
          <div className="flex-1 overflow-y-auto">
            <PriorBriefs />
          </div>
        </aside>

        {/* Main Area */}
        <main className="flex-1 overflow-y-auto p-6">
          <PipelineStatus />

          {/* Agent Cards Grid */}
          {agentList.length > 0 && (
            <div className="mb-6">
              <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                Research Agents
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                <AnimatePresence>
                  {agentList.map((agent) => (
                    <AgentCard key={agent.id} agent={agent} />
                  ))}
                </AnimatePresence>
              </div>
            </div>
          )}

          {/* Final Brief */}
          <AnimatePresence>
            {finalBrief && <FinalBrief brief={finalBrief} />}
          </AnimatePresence>

          {/* Empty state */}
          {pipelineStatus === "idle" && (
            <div className="flex items-center justify-center h-96 text-gray-700">
              <div className="text-center">
                <div className="text-5xl mb-4 opacity-30">&#x25C8;</div>
                <p className="text-lg font-medium">Ready for analysis</p>
                <p className="text-sm mt-1">
                  Enter a query to begin intelligence gathering
                </p>
              </div>
            </div>
          )}
        </main>

        {/* Right Panel — Scorecard + Pipeline Telemetry */}
        <aside className="w-72 border-l border-gray-800 p-4 overflow-y-auto">
          <AnimatePresence>
            {evalScorecard && <EvalScorecard scorecard={evalScorecard} />}
          </AnimatePresence>

          <AnimatePresence>
            {pipelineMetrics && <PipelineMetrics metrics={pipelineMetrics} />}
          </AnimatePresence>

          {!evalScorecard && !pipelineMetrics && pipelineStatus !== "idle" && (
            <div className="text-xs text-gray-600 text-center py-8 italic">
              Quality scorecard and telemetry will appear after analysis completes
            </div>
          )}
          {pipelineStatus === "idle" && (
            <div className="text-xs text-gray-600 text-center py-8 italic">
              Quality metrics
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
