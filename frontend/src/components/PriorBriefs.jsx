import { useEffect, useState } from "react";
import { motion } from "framer-motion";

export default function PriorBriefs() {
  const [briefs, setBriefs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const apiBase = import.meta.env.VITE_API_URL || "http://localhost:8000";
    fetch(`${apiBase}/briefs`)
      .then((r) => r.json())
      .then((data) => {
        setBriefs(data.briefs || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="text-xs text-gray-500 py-4 text-center">
        Loading prior briefs...
      </div>
    );
  }

  if (briefs.length === 0) {
    return (
      <div className="text-xs text-gray-600 py-4 text-center italic">
        No prior briefs yet. Your research history will appear here.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
        Prior Research
      </h3>
      {briefs.map((brief, i) => (
        <motion.div
          key={brief.brief_id || i}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: i * 0.05 }}
          className="p-3 bg-gray-900/50 rounded-lg border border-gray-800 hover:border-gray-700 cursor-pointer transition-colors"
        >
          <p className="text-xs font-medium text-gray-200 line-clamp-1">
            {brief.query}
          </p>
          <p className="text-[10px] text-gray-500 mt-1 line-clamp-2">
            {brief.executive_summary}
          </p>
          <p className="text-[10px] text-gray-600 mt-1">
            {brief.created_at
              ? new Date(brief.created_at).toLocaleDateString()
              : ""}
          </p>
        </motion.div>
      ))}
    </div>
  );
}
