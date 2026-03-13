#!/bin/bash
# OpenClaw Shutdown Script

echo "🛑 Stopping OpenClaw services..."

# Find and kill the uvicorn backend orchestrator
ORCH_PIDS=$(lsof -t -i:8000 2>/dev/null)
if [ ! -z "$ORCH_PIDS" ]; then
    echo "Killing Orchestrator on port 8000 (PIDs: $ORCH_PIDS)..."
    kill -15 $ORCH_PIDS 2>/dev/null
    sleep 2
    kill -9 $ORCH_PIDS 2>/dev/null
else
    echo "Orchestrator not running on port 8000."
fi

# Find and kill the serve frontend UI
UI_PIDS=$(lsof -t -i:3000 2>/dev/null)
if [ ! -z "$UI_PIDS" ]; then
    echo "Killing UI on port 3000 (PIDs: $UI_PIDS)..."
    kill -15 $UI_PIDS 2>/dev/null
    sleep 2
    kill -9 $UI_PIDS 2>/dev/null
else
    echo "UI not running on port 3000."
fi

echo "✅ All OpenClaw services have been stopped."
