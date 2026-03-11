/**
 * OpenClaw Runtime – HTTP Gateway
 *
 * Architecture:
 *   Chat UI  →  (POST /chat)  →  Gateway  →  FastAPI Orchestrator
 *
 * Also serves the Chat UI static files from ../ui/
 */

import express from "express";
import cors from "cors";
import { createServer } from "http";
import path from "path";
import { fileURLToPath } from "url";
import { config } from "dotenv";
import fetch from "node-fetch";

config({ path: path.join(path.dirname(fileURLToPath(import.meta.url)), "../../.env") });

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const GATEWAY_PORT = process.env.GATEWAY_PORT || 3000;
const ORCHESTRATOR_HOST = process.env.ORCHESTRATOR_HOST || "localhost";
const ORCHESTRATOR_PORT = process.env.ORCHESTRATOR_PORT || 8000;
const ORCHESTRATOR_URL = `http://${ORCHESTRATOR_HOST}:${ORCHESTRATOR_PORT}`;

const app = express();
app.use(cors());
app.use(express.json());

// ── Serve Chat UI ─────────────────────────────────────────────────────────────
app.use(express.static(path.join(__dirname, "../../ui")));

// ── Health check ──────────────────────────────────────────────────────────────
app.get("/health", (req, res) => {
    res.json({ status: "ok", service: "openclaw-gateway", version: "2.0.0" });
});

// ── POST /chat  →  Python FastAPI Orchestrator ────────────────────────────────
app.post("/chat", async (req, res) => {
    const { query } = req.body;

    if (!query || !query.trim()) {
        return res.status(400).json({ error: "Query cannot be empty." });
    }

    console.log(`[Gateway] → Orchestrator: "${query}"`);

    try {
        const upstream = await fetch(`${ORCHESTRATOR_URL}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query }),
        });

        if (!upstream.ok) {
            const err = await upstream.text();
            console.error("[Gateway] Orchestrator error:", err);
            return res.status(upstream.status).json({ error: err });
        }

        const data = await upstream.json();
        console.log(`[Gateway] ← Agent: ${data.agent}`);
        return res.json(data);

    } catch (err) {
        console.error("[Gateway] Connection error:", err.message);
        return res.status(503).json({
            error: `Cannot reach orchestrator at ${ORCHESTRATOR_URL}. Is it running?`,
        });
    }
});

// ── POST /ingest  →  trigger re-ingestion ────────────────────────────────────
app.post("/ingest", async (req, res) => {
    try {
        const upstream = await fetch(`${ORCHESTRATOR_URL}/ingest`, { method: "POST" });
        const data = await upstream.json();
        return res.json(data);
    } catch (err) {
        return res.status(503).json({ error: "Cannot reach orchestrator." });
    }
});

// ── Start ─────────────────────────────────────────────────────────────────────
const server = createServer(app);
server.listen(GATEWAY_PORT, () => {
    console.log(`\n╔══════════════════════════════════════════════════╗`);
    console.log(`║  OpenClaw Runtime  ·  Gateway v2.0               ║`);
    console.log(`╠══════════════════════════════════════════════════╣`);
    console.log(`║  Chat UI   →  http://localhost:${GATEWAY_PORT}              ║`);
    console.log(`║  Proxy     →  ${ORCHESTRATOR_URL}           ║`);
    console.log(`╚══════════════════════════════════════════════════╝\n`);
});
