#!/bin/bash
# OpenClaw Startup Script

# 1. Load Environment Variables
if [ -f .env ]; then
  source .env
else
  echo "❌ .env file missing."
  exit 1
fi

if [ -z "$GROQ_API_KEY" ] || [ "$GROQ_API_KEY" == "your-groq-api-key" ] || [ "$GROQ_API_KEY" == "" ]; then
  echo "❌ GROQ_API_KEY is not set in .env — please add it and re-run."
  exit 1
fi

# 2. Check dependencies
echo "�� Checking Python dependencies..."
pip install -q -r requirements.txt
echo "📦 Checking Node.js dependencies..."
cd runtime && npm install --silent && cd ..

# 3. Create necessary directories
echo "📁 Ensuring required directories exist..."
mkdir -p data/chroma_db data/docs/projects ./logs

# 4. Initialize SQLite DB
echo "🗄️  Initializing SQLite database..."
python3 tools/init_sqlite_db.py

# 5. Start Servers
echo "🚀 Starting OpenClaw Orchestrator (Backend) and UI (Frontend)..."

# Use concurrently to run both and stream logs
if ! command -v concurrently &> /dev/null
then
    echo "⚙️ Installing concurrently..."
    npm install -g concurrently
fi

concurrently \
    --names "ORCH,UI  " \
    --prefix-colors "blue,green" \
    --kill-others \
    "python3 -m uvicorn orchestrator.main:server --host 0.0.0.0 --port 8000" \
    "cd ui && npx serve -p 3000"
