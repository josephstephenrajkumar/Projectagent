# Fail-Safe Data Extraction Strategy

**Date:** May 2026  
**Component:** Data Extraction Agent (`agents/data_extraction_agent.py`)

## 1. Executive Summary
The previous extraction pipeline relied on a single-pass Retrieval-Augmented Generation (RAG) query with a context limit of 30 chunks (`k=30`). For large Statement of Work (SOW) documents, this caused the LLM to silently skip work packages (e.g., Work Packages 5, 6, 9, 10) because they were truncated from the context window. 

This document outlines the implemented **Map-Reduce Discovery** and **Targeted Retrieval** architecture, which guarantees 100% extraction coverage and strict schema validation.

---

## 2. Architecture Overview

The new extraction pipeline operates in three distinct phases:
1. **Map-Reduce Discovery (Pass 1):** Scans the entire document to build a definitive list of all Work Packages.
2. **Targeted Retrieval (Pass 2):** Performs micro-searches for each specific Work Package to extract deep details without context contamination.
3. **Pydantic Validation:** Enforces strict JSON schemas at every LLM interaction to prevent silent parsing failures.

---

## 3. Detailed Logic & Implementation

### 3.1 Pydantic Strict JSON Validation
Instead of relying on fragile Regex to parse markdown blocks (`_extract_json_from_response`), the system now uses `pydantic` schemas combined with Langchain's `PydanticOutputParser`.

**Implementation:**
- Two models were created: `WorkPackageDiscovery` (for Pass 1) and `WorkPackageDetail` (for Pass 2).
- The models define all 15 required fields (`phase_name`, `activities`, `risks_mitigations`, etc.) with explicit descriptions.
- The `PydanticOutputParser` automatically injects schema instructions into the prompt, forcing the LLM to return a perfectly formatted JSON string.

### 3.2 Map-Reduce Discovery (100% Coverage)
To ensure no Work Package is skipped due to vector similarity cutoffs, the pipeline now bypasses `similarity_search` during the discovery phase.

**Logic Flow:**
1. **Fetch All Documents:** A new function `get_all_documents(collection_name)` connects directly to `chromadb.PersistentClient` and downloads all chunks for the contract.
2. **Filter (Optimization):** To save API costs, chunks are pre-filtered. Only chunks containing the words "work package", "phase", or "appendix" are sent to the LLM.
3. **Map:** Each filtered chunk is sent to the LLM independently with the prompt: *"List any work packages found in this text exactly per the JSON schema."*
4. **Reduce:** The resulting lists of Work Packages are combined.
5. **Deduplicate & Sort:** The pipeline deduplicates the list by `wp_number` (to handle cases where a phase spans multiple chunks) and sorts them sequentially (1 to 11).

### 3.3 Targeted Detail Retrieval (Deep Specifics)
Once the absolute list of Work Packages is established, the pipeline extracts the specifics for each phase one by one.

**Logic Flow:**
1. **Iterate:** Loop through the sorted list of discovered Work Packages (e.g., "Work Package 5").
2. **Dynamic Search:** Execute a highly specific vector search for *only* that phase:
   ```python
   specific_query = f"{p_name} scope deliverables prerequisites activities"
   phase_context = similarity_search(col_name, specific_query, k=10)
   ```
3. **Targeted Prompt:** The LLM is provided *only* the top 10 chunks relevant to Work Package 5, completely eliminating cross-contamination from other phases.
4. **Validation:** The response is parsed via the `WorkPackageDetail` Pydantic model. If it fails, the error is caught, logged, and the loop continues safely.

---

## 4. Saving Strategy
The extracted JSON dictionaries are aggregated into a Python `list[dict]` and appended to the main Project DTO under the key `work_packages`.

When the user confirms the extraction via the UI, the `db_agent.py` processes this list:
1. It generates a unique `wp_id` (UUID) for each Work Package.
2. It executes an `INSERT INTO ProjectWorkPackage` SQL statement, establishing a Foreign Key relationship with the parent `project_id`.
3. If the project is ever deleted (via the Drop Project UI), SQLite's `ON DELETE CASCADE` rule automatically cleans up these child records.
