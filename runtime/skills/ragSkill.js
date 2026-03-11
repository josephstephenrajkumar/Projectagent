/**
 * OpenClaw Runtime – RAG Skill
 *
 * Skills are callable wrappers that invoke Python Tools/APIs via the
 * FastAPI orchestrator. This skill exposes RAG query functionality
 * so other Node.js modules can call it without knowing the HTTP details.
 *
 *   Usage:
 *     import { ragSkill } from "./ragSkill.js";
 *     const result = await ragSkill.query("What is the Boston plan?");
 */

import fetch from "node-fetch";
import { config } from "dotenv";
config();

const ORCHESTRATOR_URL = `http://${process.env.ORCHESTRATOR_HOST || "localhost"}:${process.env.ORCHESTRATOR_PORT || 8000
    }`;

export const ragSkill = {
    name: "RAGSkill",
    description: "Query the multi-agent RAG system via the LangGraph orchestrator.",

    /**
     * Send a natural-language query through the full agent pipeline.
     * @param {string} query
     * @returns {Promise<{response: string, debug_log: string, agent: string}>}
     */
    async query(query) {
        const res = await fetch(`${ORCHESTRATOR_URL}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query }),
        });
        if (!res.ok) {
            throw new Error(`Orchestrator responded ${res.status}: ${await res.text()}`);
        }
        return res.json();
    },

    /**
     * Trigger document re-ingestion.
     */
    async ingest() {
        const res = await fetch(`${ORCHESTRATOR_URL}/ingest`, { method: "POST" });
        return res.json();
    },
};
