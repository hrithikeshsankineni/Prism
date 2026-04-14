import json
import logging
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.core.orchestrator import PipelineOrchestrator
from backend.core.rag import rag_memory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

app = FastAPI(title="PRISM Intelligence Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = PipelineOrchestrator()

# In-memory map of session_id -> query for the POST+WS flow
_pending_sessions: dict = {}


# --- REST endpoints ---


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/brief")
async def create_brief(body: dict):
    """Start a new brief session. Returns session_id to connect via WebSocket."""
    query = body.get("query", "").strip()
    if not query:
        return {"error": "query is required"}, 400

    session_id = uuid.uuid4().hex
    _pending_sessions[session_id] = query
    return {"session_id": session_id, "status": "started"}


@app.get("/briefs")
async def list_briefs():
    """Return summaries of prior briefs from RAG memory."""
    briefs = await rag_memory.list_briefs(limit=20)
    return {"briefs": briefs}


@app.get("/briefs/{brief_id}")
async def get_brief(brief_id: str):
    """Return all chunks for a specific brief."""
    chunks = await rag_memory.get_brief_chunks(brief_id)
    if not chunks:
        return {"error": "Brief not found"}, 404
    return {"brief_id": brief_id, "chunks": chunks}


# --- WebSocket endpoint ---


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()

    try:
        # Wait for the first message which contains the query
        # or use the pending session query from POST /brief
        first_msg = await websocket.receive_text()
        data = json.loads(first_msg)

        # Support replay on reconnect
        replay_after = data.get("replay_after")
        if replay_after is not None:
            events = orchestrator.get_replay_events(session_id, replay_after)
            for event in events:
                await websocket.send_json(event)
            # If this was just a reconnect for replay, keep listening
            if "query" not in data:
                # Keep connection alive for future events
                while True:
                    await websocket.receive_text()
                return

        query = data.get("query") or _pending_sessions.pop(session_id, None)
        if not query:
            await websocket.send_json({"error": "No query provided"})
            await websocket.close()
            return

        # Run the pipeline, streaming events via websocket.send_json
        await orchestrator.run_pipeline(
            query=query,
            session_id=session_id,
            ws_send=websocket.send_json,
        )

    except WebSocketDisconnect:
        logging.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logging.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass
    finally:
        # Don't cleanup immediately — allow reconnection
        pass
