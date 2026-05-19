#!/bin/bash

# OpenClaw Multi-Agent Startup Script
echo "Starting OpenClaw Multi-Agent Environment..."

# Ensure environment variables
if [ -f .env ]; then
    export $(cat .env | xargs)
fi

# Initialize database if needed
python3 tools/test_financial_ingestion.py

echo "Environment ready."
