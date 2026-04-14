import { useState } from "react";
import { motion } from "framer-motion";
import useSessionStore from "../store/sessionStore";
import useWebSocket from "../hooks/useWebSocket";

export default function QueryInput() {
  const [input, setInput] = useState("");
  const pipelineStatus = useSessionStore((s) => s.pipelineStatus);
  const startPipeline = useSessionStore((s) => s.startPipeline);
  const setQuery = useSessionStore((s) => s.setQuery);
  const { connect } = useWebSocket();

  const isRunning = pipelineStatus === "running";

  const handleSubmit = async (e) => {
    e.preventDefault();
    const query = input.trim();
    if (!query || isRunning) return;

    // Create session via REST, then connect WS
    try {
      const apiBase = import.meta.env.VITE_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiBase}/brief`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      const data = await res.json();
      const sessionId = data.session_id;

      setQuery(query);
      startPipeline(sessionId);
      connect(sessionId, query);
    } catch (err) {
      console.error("Failed to start brief:", err);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Enter any query: company, person, topic, decision..."
        disabled={isRunning}
        className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 text-gray-100 placeholder-gray-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-colors disabled:opacity-50"
      />
      <motion.button
        type="submit"
        disabled={isRunning || !input.trim()}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        className="w-full px-6 py-3 bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors"
      >
        {isRunning ? (
          <span className="flex items-center gap-2">
            <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Running
          </span>
        ) : (
          "Analyze"
        )}
      </motion.button>
    </form>
  );
}
