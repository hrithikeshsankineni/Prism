import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

function SourceChip({ url }) {
  let domain;
  try {
    domain = new URL(url).hostname.replace("www.", "");
  } catch {
    domain = url;
  }
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-block px-2 py-0.5 text-[10px] bg-gray-800 hover:bg-gray-700 text-cyan-400 rounded-full border border-gray-700 transition-colors"
    >
      {domain}
    </a>
  );
}

function ConfidenceBar({ value }) {
  const pct = Math.round(value * 100);
  const color =
    pct > 75 ? "bg-emerald-400" : pct > 50 ? "bg-yellow-400" : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6 }}
          className={`h-full rounded-full ${color}`}
        />
      </div>
      <span className="text-[10px] text-gray-400">{pct}%</span>
    </div>
  );
}

function Section({ section }) {
  const [open, setOpen] = useState(true);

  return (
    <div className="border-b border-gray-800 pb-3 mb-3 last:border-0">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full text-left"
      >
        <h3 className="text-sm font-semibold text-gray-200">
          {section.title}
        </h3>
        <div className="flex items-center gap-2">
          <ConfidenceBar value={section.confidence} />
          <span className="text-gray-500 text-xs">{open ? "\u25B2" : "\u25BC"}</span>
        </div>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <p className="text-sm text-gray-300 mt-2 leading-relaxed whitespace-pre-wrap">
              {section.content}
            </p>
            {section.source_urls?.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {section.source_urls.map((url, i) => (
                  <SourceChip key={i} url={url} />
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function FinalBrief({ brief }) {
  if (!brief) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gray-900/50 rounded-xl border border-gray-800 p-5"
    >
      <h2 className="text-lg font-bold text-gray-100 mb-1">
        Intelligence Brief
      </h2>
      <p className="text-xs text-gray-500 mb-4">
        Query: {brief.query}
      </p>

      {/* Executive Summary */}
      <div className="bg-gray-800/50 rounded-lg p-4 mb-4">
        <h3 className="text-xs font-semibold text-cyan-400 uppercase tracking-wider mb-2">
          Executive Summary
        </h3>
        <p className="text-sm text-gray-200 leading-relaxed">
          {brief.executive_summary}
        </p>
      </div>

      {/* Sections */}
      <div className="mb-4">
        {brief.sections?.map((section, i) => (
          <Section key={i} section={section} />
        ))}
      </div>

      {/* Challenged Claims */}
      {brief.challenged_claims?.length > 0 && (
        <div className="bg-amber-950/30 border border-amber-500/20 rounded-lg p-4 mb-4">
          <h3 className="text-xs font-semibold text-amber-400 uppercase tracking-wider mb-3">
            Challenged Claims
          </h3>
          {brief.challenged_claims.map((claim, i) => (
            <div key={i} className="mb-3 last:mb-0">
              <div className="flex items-start gap-2">
                <span
                  className={`px-1.5 py-0.5 text-[10px] rounded font-medium ${
                    claim.severity === "high"
                      ? "bg-red-500/20 text-red-400"
                      : claim.severity === "medium"
                      ? "bg-amber-500/20 text-amber-400"
                      : "bg-gray-500/20 text-gray-400"
                  }`}
                >
                  {claim.severity}
                </span>
                <div>
                  <p className="text-sm text-gray-200">{claim.claim}</p>
                  <p className="text-xs text-gray-400 mt-1">
                    {claim.challenge_reason}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Contradictions */}
      {brief.contradictions?.length > 0 && (
        <div className="bg-red-950/20 border border-red-500/20 rounded-lg p-4 mb-4">
          <h3 className="text-xs font-semibold text-red-400 uppercase tracking-wider mb-3">
            Detected Contradictions
          </h3>
          {brief.contradictions.map((c, i) => (
            <div key={i} className="mb-3 last:mb-0 text-sm">
              <p className="text-gray-300">
                <span className="text-red-400">A:</span> {c.claim_a}
              </p>
              <p className="text-gray-300 mt-1">
                <span className="text-red-400">B:</span> {c.claim_b}
              </p>
              {c.resolution && (
                <p className="text-xs text-gray-500 mt-1 italic">
                  Resolution: {c.resolution}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Overall Stats */}
      <div className="flex items-center gap-6 text-xs text-gray-500 pt-2 border-t border-gray-800">
        <span>
          Confidence: <ConfidenceBar value={brief.overall_confidence || 0} />
        </span>
        <span>Sources: {brief.all_sources?.length || 0}</span>
        <span>
          Agents: {brief.agent_count || 0} ({brief.agent_failures || 0} failed)
        </span>
      </div>
    </motion.div>
  );
}
