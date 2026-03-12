/**
 * OpenClaw Runtime – ChromaDB Connector
 *
 * Connectors abstract data-source configuration so Skills and the Gateway
 * never hard-code paths or connection strings.
 *
 * This connector provides the ChromaDB path and embedding model name used
 * by the Python tools layer, read from environment variables.
 */

import { config } from "dotenv";
config();

import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, '../../');
const resolvePath = (envVal) => path.isAbsolute(envVal) ? envVal : path.join(PROJECT_ROOT, envVal);

export const chromaConnector = {
    name: "ChromaConnector",
    description: "Configuration connector for the local ChromaDB vector store.",

    /** Absolute or relative path used by the Python persistence client. */
    get dbPath() {
        return resolvePath(process.env.CHROMA_DB_PATH || "./data/chroma_db");
    },

    /** HuggingFace sentence-transformer model used for embeddings. */
    get embeddingModel() {
        return process.env.EMBEDDING_MODEL || "all-mpnet-base-v2";
    },

    /** Directory containing source documents to be ingested. */
    get sourceDataDir() {
        return resolvePath(process.env.SOURCE_DATA_DIR || "./data/docs");
    },

    /** Serialise connector config for logging / debugging. */
    info() {
        return {
            dbPath: this.dbPath,
            embeddingModel: this.embeddingModel,
            sourceDataDir: this.sourceDataDir,
        };
    },
};
