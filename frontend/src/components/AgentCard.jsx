import { motion } from "framer-motion";
import ThoughtLog from "./ThoughtLog";

const STATUS_CONFIG = {
  searching: {
    color: "text-cyan-400",
    bg: "bg-cyan-500/10 border-cyan-500/30",
    dot: "bg-cyan-400",
    label: "Searching",
    pulse: true,
  },
  requerying: {
    color: "text-violet-400",
    bg: "bg-violet-500/10 border-violet-500/30",
    dot: "bg-violet-400",
    label: "Re-querying",
    pulse: true,
  },
  complete: {
    color: "text-emerald-400",
    bg: "bg-emerald-500/10 border-emerald-500/30",
    dot: "bg-emerald-400",
    label: "Complete",
    pulse: false,
  },
  failed: {
    color: "text-red-400",
    bg: "bg-red-500/10 border-red-500/30",
    dot: "bg-red-400",
    label: "Failed",
    pulse: false,
  },
};

const TYPE_ICONS = {
  web_research: "\u{1F310}",
  news_sentiment: "\u{1F4F0}",
  financial_market: "\u{1F4C8}",
  domain_specific: "\u{1F3AF}",
  academic: "\u{1F393}",
};

export default function AgentCard({ agent }) {
  const config = STATUS_CONFIG[agent.status] || STATUS_CONFIG.searching;
  const icon = TYPE_ICONS[agent.type] || "\u{1F50D}";

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`rounded-xl border p-4 ${config.bg}`}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-lg">{icon}</span>
          <span className="text-sm font-semibold text-gray-200 capitalize">
            {agent.type?.replace(/_/g, " ")}
          </span>
          {/* Re-query badge */}
          {agent.requeryCount > 0 && (
            <motion.span
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              className="px-1.5 py-0.5 text-[9px] font-semibold bg-violet-500/20 text-violet-300 rounded border border-violet-500/30 uppercase tracking-wide"
            >
              +{agent.requeryCount} requery
            </motion.span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${config.dot} ${
              config.pulse ? "animate-pulse" : ""
            }`}
          />
          <span className={`text-xs font-medium ${config.color}`}>
            {config.label}
          </span>
        </div>
      </div>

      {agent.focusArea && (
        <p className="text-xs text-gray-400 mb-2 line-clamp-2">
          {agent.focusArea}
        </p>
      )}

      <div className="flex items-center gap-4 text-xs text-gray-400">
        {agent.findingsCount != null && (
          <span>
            <span className="text-gray-300 font-medium">{agent.findingsCount}</span> findings
          </span>
        )}
        {agent.confidence != null && (
          <div className="flex items-center gap-1.5">
            <span>confidence</span>
            <div className="w-16 h-1.5 bg-gray-800 rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${agent.confidence * 100}%` }}
                transition={{ duration: 0.5 }}
                className={`h-full rounded-full ${
                  agent.confidence > 0.75
                    ? "bg-emerald-400"
                    : agent.confidence > 0.5
                    ? "bg-yellow-400"
                    : "bg-red-400"
                }`}
              />
            </div>
            <span className="text-gray-300 font-medium">
              {(agent.confidence * 100).toFixed(0)}%
            </span>
          </div>
        )}
      </div>

      {agent.error && (
        <p className="text-xs text-red-400 mt-2">{agent.error}</p>
      )}

      <ThoughtLog thoughts={agent.thoughts} />
    </motion.div>
  );
}
