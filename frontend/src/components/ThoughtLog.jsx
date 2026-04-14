import { motion, AnimatePresence } from "framer-motion";

export default function ThoughtLog({ thoughts = [] }) {
  if (thoughts.length === 0) return null;

  return (
    <div className="mt-2 max-h-32 overflow-y-auto space-y-1 scrollbar-thin">
      <AnimatePresence>
        {thoughts.map((thought, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.2 }}
            className="text-xs font-mono text-emerald-400/80 leading-relaxed"
          >
            <span className="text-emerald-600 mr-1">&gt;</span>
            {thought}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
