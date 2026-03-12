#!/usr/bin/env bash
# start.sh – Quick launcher for the OpenClaw Multi-Agent System
# Usage: ./start.sh
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║        OpenClaw Multi-Agent System v2            ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Check .env ────────────────────────────────────────────────────────────
if [ ! -f "$ROOT/.env" ]; then
  echo "⚠️  .env not found – copying from .env.example"
  cp "$ROOT/.env.example" "$ROOT/.env"
fi

# ── Check Groq API key ────────────────────────────────────────────────────
GROQ_KEY=$(grep GROQ_API_KEY "$ROOT/.env" | cut -d= -f2 | tr -d '"')
if [ -z "$GROQ_KEY" ]; then
  echo "❌  GROQ_API_KEY is not set in .env — please add it and re-run."
  exit 1
fi
echo "🤖 LLM: Groq → openai/gpt-oss-120b"

# ── Node deps ─────────────────────────────────────────────────────────────
if [ ! -d "$ROOT/runtime/node_modules" ]; then
  echo "📦 Installing Node.js dependencies…"
  cd "$ROOT/runtime" && npm install && cd "$ROOT"
fi

# ── Start FastAPI Orchestrator ────────────────────────────────────────────
echo ""
echo "🐍 Starting Python Orchestrator (FastAPI) on port 8000…"
cd "$ROOT/orchestrator"
python main.py &
PYTHON_PID=$!
echo "   PID: $PYTHON_PID"
sleep 2

# ── Start ACP Agent Server ────────────────────────────────────────────────
echo "🤖 Starting ACP Agent Server on port 8100…"
cd "$ROOT/agents"
python acp_agent_server.py &
ACP_PID=$!
echo "   PID: $ACP_PID"
sleep 2

# ── Start Node.js Gateway ─────────────────────────────────────────────────
echo "⚙️  Starting OpenClaw Gateway (Node.js) on port 3000…"
cd "$ROOT/runtime"
node gateway/server.js &
NODE_PID=$!
echo "   PID: $NODE_PID"
sleep 1

echo ""
echo "✅ System running!"
echo "   Chat UI      → http://localhost:3000"
echo "   API docs     → http://localhost:8000/docs"
echo "   ACP agents   → http://localhost:8100/agents"
echo "   A2A card     → http://localhost:8100/.well-known/agent.json"
echo ""
echo "Press Ctrl+C to stop all services."
echo ""

# ── Wait & cleanup ────────────────────────────────────────────────────────
trap "echo ''; echo 'Shutting down…'; kill $PYTHON_PID $ACP_PID $NODE_PID 2>/dev/null; exit 0" INT TERM
wait $PYTHON_PID $ACP_PID $NODE_PID
