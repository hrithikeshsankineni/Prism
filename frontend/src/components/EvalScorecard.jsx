import { motion } from "framer-motion";

const DIMENSIONS = [
  { key: "factual_consistency", label: "Factual Consistency" },
  { key: "source_coverage", label: "Source Coverage" },
  { key: "confidence_calibration", label: "Confidence Calibration" },
  { key: "completeness", label: "Completeness" },
];

function ScoreBar({ label, score, justification, delay = 0 }) {
  const pct = Math.round((score || 0) * 100);
  const color =
    pct > 75
      ? "from-emerald-500 to-emerald-400"
      : pct > 50
      ? "from-yellow-500 to-yellow-400"
      : "from-red-500 to-red-400";

  return (
    <div className="mb-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-gray-400">{label}</span>
        <span className="text-xs font-mono text-gray-300">{pct}%</span>
      </div>
      <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, delay }}
          className={`h-full rounded-full bg-gradient-to-r ${color}`}
        />
      </div>
      {justification && (
        <p className="text-[10px] text-gray-500 mt-1">{justification}</p>
      )}
    </div>
  );
}

export default function EvalScorecard({ scorecard }) {
  if (!scorecard) return null;

  const overall = scorecard.overall_score || 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gray-900/50 rounded-xl border border-gray-800 p-4"
    >
      <h2 className="text-sm font-bold text-gray-100 mb-3">
        Quality Scorecard
      </h2>

      {DIMENSIONS.map((dim, i) => {
        const data = scorecard[dim.key];
        return (
          <ScoreBar
            key={dim.key}
            label={dim.label}
            score={typeof data === "object" ? data?.score : data}
            justification={typeof data === "object" ? data?.justification : null}
            delay={i * 0.1}
          />
        );
      })}

      <div className="pt-3 mt-3 border-t border-gray-800">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-semibold text-gray-300">Overall</span>
          <span className="text-sm font-mono font-bold text-gray-100">
            {Math.round(overall * 100)}%
          </span>
        </div>
        <div className="w-full h-3 bg-gray-800 rounded-full overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${Math.round(overall * 100)}%` }}
            transition={{ duration: 1, delay: 0.4 }}
            className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-cyan-400"
          />
        </div>
      </div>

      {scorecard.summary && (
        <p className="text-xs text-gray-400 mt-3 italic">{scorecard.summary}</p>
      )}
    </motion.div>
  );
}
