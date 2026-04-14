import { motion } from "framer-motion";

const STAGE_LABELS = {
  planner: "Planner",
  research: "Research",
  synthesis: "Synthesis",
  critic: "Critic",
  eval: "Eval",
};

const STAGE_COLORS = {
  planner: "bg-violet-500",
  research: "bg-cyan-500",
  synthesis: "bg-blue-500",
  critic: "bg-amber-500",
  eval: "bg-emerald-500",
};

function formatMs(ms) {
  if (!ms && ms !== 0) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatTokens(n) {
  if (!n && n !== 0) return "—";
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

export default function PipelineMetrics({ metrics }) {
  if (!metrics) return null;

  const stages = metrics.stages || {};
  const stageKeys = Object.keys(stages).filter((k) => STAGE_LABELS[k]);

  // Compute max duration for bar scaling
  const maxDuration = Math.max(...stageKeys.map((k) => stages[k]?.duration_ms || 0), 1);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gray-900/50 rounded-xl border border-gray-800 p-4 mt-4"
    >
      <h2 className="text-sm font-bold text-gray-100 mb-1">Pipeline Telemetry</h2>
      <div className="flex items-center gap-3 mb-4 text-xs text-gray-400">
        <span>
          Total:{" "}
          <span className="text-gray-200 font-mono">
            {formatMs(metrics.total_duration_ms)}
          </span>
        </span>
        <span className="text-gray-700">|</span>
        <span>
          Tokens:{" "}
          <span className="text-gray-200 font-mono">
            {formatTokens(metrics.total_tokens)}
          </span>
        </span>
      </div>

      {/* Stage breakdown */}
      <div className="space-y-2.5">
        {stageKeys.map((key) => {
          const s = stages[key];
          const barPct = Math.round((s.duration_ms / maxDuration) * 100);
          const color = STAGE_COLORS[key] || "bg-gray-500";

          return (
            <div key={key}>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-gray-400">{STAGE_LABELS[key] || key}</span>
                <div className="flex items-center gap-3 text-gray-500 font-mono">
                  <span>{formatTokens(s.total_tokens)} tok</span>
                  <span className="text-gray-300">{formatMs(s.duration_ms)}</span>
                </div>
              </div>
              <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${barPct}%` }}
                  transition={{ duration: 0.6 }}
                  className={`h-full rounded-full ${color}`}
                />
              </div>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}
