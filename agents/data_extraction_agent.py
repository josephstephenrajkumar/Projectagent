"""
Agent Mesh – Data Extraction Agent (Enhanced)
Extracts structured project data by:
  1. Parsing the estimation-milestone Excel directly (dates, costs, resources)
  2. Using LLM to extract SOW data from contract collection (parties, pricing, work packages)
  3. Merging both into a combined JSON DTO for the Project table

SOW prompts adapted from azureai_search_sow_crawler_agent_b_(_backup_).py
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orchestrator.llm_factory import get_llm
from tools.retrieval import similarity_search
from tools.excel_parser import parse_estimation_excel
from langchain_core.messages import SystemMessage, HumanMessage

llm = get_llm()

# ── SOW Extraction prompt (adapted from the backup agent's prompt_str + sample_output_structure)
SOW_EXTRACTION_PROMPT = """You are an AI assistant that helps extract structured contract information.
Given the contract document context below, extract the following and return as a single JSON object.
Use null for any field you cannot find.

Required JSON fields:
{{
  "customer": "string – customer / client company name",
  "end_customer": "string – end customer if different from customer, else same",
  "PMName": "string – Project Manager name",
  "DMName": "string – Delivery Manager name",
  "country": "string – country of delivery",
  "startdateContract": "string – contract start date (YYYY-MM-DD)",
  "endDateContract": "string – contract end date (YYYY-MM-DD)",
  "exchangerate": "string – exchange rate if mentioned",
  "MBRReporting_currency": "string – reporting currency (e.g. SGD, USD)",
  "Proj_Stage": "string – project stage (e.g. Execution, Initiation)",
  "Contr_Type": "string – contract type (e.g. Fixed Price, T&M)",
  "Rev_Type": "string – revenue type",
  "Baseline_Rev": "number – baseline/total revenue amount",
  "Prod_Grp": "string – product group",
  "Portfolio": "string – portfolio",
  "Region": "string – region (e.g. SEAK, EMEA)",
  "Project_Owner": "string – project owner",
  "sow_data": {{
    "parties": {{
      "provider": "string",
      "customer": "string",
      "end_customer": "string"
    }},
    "pricing_summary": {{
      "work_packages": [
        {{
          "phase": "string – phase/milestone name",
          "percentage": "string – payment percentage",
          "amount": "string – payment amount",
          "indicative_date": "string – derived date",
          "documented_date": "string – original T0+weeks notation"
        }}
      ],
      "subtotal": "string – total contract value",
      "currency": "string"
    }},
    "tentative_engagement_schedule": {{
      "start_date": "string",
      "end_date": "string"
    }},
    "billing_address": "string",
    "billing_contact": "string",
    "delivery_location": "string",
    "delivery_timezone": "string"
  }}
}}

--- Contract Document Context ---
{contract_context}

Return ONLY the JSON object. No markdown fences, no explanation, no extra text."""


# ── Work Package scope extraction prompts ─────────────────────────────────────
WP_DISCOVERY_PROMPT = """You are an expert contract analyst. From the SOW/contract context below,
identify every distinct work package or phase listing (e.g. "Work Package #1", "Work Package #2", etc.).
You must be EXHAUSTIVE. Appendix A often contains the full list from #1 to #11.
Scan the entire context carefully and list EVERY single unique work package number you find.

CRITICAL INSTRUCTION: Identify phases by their "Work Package #X" label. If multiple sections describe the same Work Package #, list it exactly once with its most complete name. Do not miss any numbers in the sequence (check for 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11).

Return ONLY a JSON array of objects:
[
  {{
    "phase_name": "string – e.g. Work Package #1 - Project kick-off",
    "phase_order": 1,
    "wp_number": 1
  }}
]

--- Contract Document Context ---
{contract_context}

Return ONLY the JSON array. No markdown fences, no explanation."""

WP_DETAIL_PROMPT = """You are an expert contract analyst. Based on the following SOW context,
extract the detailed scope for specifically this ONE phase: "{phase_name}"

Return a single JSON object with these fields, keeping them extremely concise (1 sentence or 2 bullet points max):
{{
  "phase_name": "{phase_name}",
  "phase_order": {phase_order},
  "prerequisites": "string",
  "activities": "string",
  "customer_responsibilities": "string",
  "out_of_scope": "string",
  "risks_mitigations": "string",
  "deliverables": "string",
  "acceptance_criteria": "string",
  "overview": "string",
  "engagement_summary": "string",
  "scope": "string",
  "tech_landscape": "string",
  "key_deliverables": "string",
  "missing_items": "string",
  "next_steps": "string",
  "quick_summary": "string"
}}

--- Contract Document Context ---
{contract_context}

Return ONLY the JSON object. No markdown fences, no explanation."""

def _extract_json_from_response(text: str) -> dict:
    """Robustly extract a JSON object from an LLM response."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_nl = cleaned.index("\n") if "\n" in cleaned else 3
        cleaned = cleaned[first_nl:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    obj_start = cleaned.find("{")
    arr_start = cleaned.find("[")

    if arr_start >= 0 and (obj_start < 0 or arr_start < obj_start):
        end = cleaned.rfind("]")
        if end > arr_start:
            cleaned = cleaned[arr_start : end + 1]
    elif obj_start >= 0:
        end = cleaned.rfind("}")
        if end > obj_start:
            cleaned = cleaned[obj_start : end + 1]

    return json.loads(cleaned)


def update_status(project_code: str, msg: str):
    import os
    safe_code = project_code.replace(" ", "_").replace("-", "_").lower()
    status_file = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "docs", "projects")), safe_code, "status.txt")
    try:
        os.makedirs(os.path.dirname(status_file), exist_ok=True)
        with open(status_file, "w") as f:
            f.write(msg)
    except:
        pass

def data_extraction_agent_node(state: dict) -> dict:
    """
    Extract structured project data from:
      1. Excel file (direct parsing for dates, costs, resources, milestones)
      2. ChromaDB contract collection (LLM-based SOW extraction)
      2b. Work package scope extraction (LLM-based Two-Pass)
    Merges all into a combined extracted_data dict.
    """
    collection_names = state.get("collection_names", [])
    uploaded_files = state.get("uploaded_files", [])
    project_code = state.get("project_code", "")
    project_name = state.get("project_name", "")
    opportunity_id = state.get("opportunity_id", "")
    debug = state.get("debug_log", "")

    update_status(project_code, "Parsing uploaded Excel files...")

    excel_data = None
    xlsx_file = None
    for f in uploaded_files:
        if f.lower().endswith((".xlsx", ".xls")):
            xlsx_file = f
            break

    if xlsx_file and os.path.exists(xlsx_file):
        try:
            excel_data = parse_estimation_excel(xlsx_file)
            debug += f"\n✅ Excel parsed: {len(excel_data.get('resources', []))} resources, cost={excel_data.get('total_cost')}"
        except Exception as exc:
            debug += f"\n⚠️ Excel parsing failed: {exc}"
    else:
        debug += "\n⚠️ No estimation Excel file found in uploaded files."

    sow_extracted = {}
    contract_context = ""

    if collection_names:
        search_query = (
            f"project {project_name} {project_code} contract details "
            "pricing milestones deliverables timeline parties scope "
            "billing address delivery location payment schedule"
        )
        for col_name in collection_names:
            col_lower = col_name.lower()
            if "contract" in col_lower:
                try:
                    context = similarity_search(col_name, search_query, k=10)
                    contract_context += context + "\n"
                except Exception as exc:
                    debug += f"\n⚠️ Error querying {col_name}: {exc}"

        if contract_context.strip():
            prompt = SOW_EXTRACTION_PROMPT.format(
                contract_context=contract_context,
            )
            try:
                response = llm.invoke(
                    [SystemMessage(content=prompt), HumanMessage(content=search_query)]
                )
                sow_extracted = _extract_json_from_response(response.content)
                debug += "\n✅ SOW data extracted via LLM."
            except json.JSONDecodeError as exc:
                debug += f"\n⚠️ SOW JSON parse error: {exc}"
            except Exception as exc:
                debug += f"\n⚠️ SOW LLM extraction error: {exc}"
        else:
            debug += "\n⚠️ No contract context retrieved from collections."
    else:
        debug += "\n⚠️ No collections available for SOW extraction."

    # ── Step 2b: Work Package scope extraction (TWO-PASS) ────────────────────
    work_packages = []
    wp_context = ""
    wp_search_query = f"project {project_code} {project_name} appendix A work packages phases scope deliverables list of all work packages phase 1 phase 2"

    update_status(project_code, "Running Discovery Pass: Scanning for Work Packages...")

    if collection_names:
        for col_name in collection_names:
            if "contract" in col_name.lower():
                try:
                    context = similarity_search(col_name, wp_search_query, k=30)
                    wp_context += context + "\n"
                except Exception as exc:
                    debug += f"\n⚠️ Error querying {col_name} for WPs: {exc}"
                    
    if wp_context.strip():
        # PASS 1: Discovery
        discovery_prompt = WP_DISCOVERY_PROMPT.format(contract_context=wp_context)
        discovered_phases = []
        try:
            discovery_res = llm.invoke(
                [SystemMessage(content=discovery_prompt), HumanMessage(content="list the work packages")]
            )
            discovered_phases = _extract_json_from_response(discovery_res.content)
            if isinstance(discovered_phases, dict) and "work_packages" in discovered_phases:
                discovered_phases = discovered_phases["work_packages"]
            
            if not isinstance(discovered_phases, list):
                discovered_phases = []
            
            # Post-discovery deduplication by wp_number to ensure 1:1 mapping for Pass 2
            seen_wp_nums = set()
            unique_phases = []
            for p in discovered_phases:
                wnum = p.get("wp_number")
                if wnum and wnum not in seen_wp_nums:
                    seen_wp_nums.add(wnum)
                    unique_phases.append(p)
                elif not wnum: # fallback if LLM missed the field
                    unique_phases.append(p)
            
            discovered_phases = unique_phases
            debug += f"\n✅ Pass 1: Discovered {len(discovered_phases)} unique phases."
        except Exception as exc:
            debug += f"\n⚠️ Work package PASS 1 error: {exc}"

        # PASS 2: Detail Extraction per phase
        total_phases = len(discovered_phases)
        for i, phase in enumerate(discovered_phases):
            p_name = phase.get("phase_name")
            p_order = phase.get("phase_order", 0)
            if not p_name:
                continue

            update_status(project_code, f"Extracting deep specifics for Phase {i+1} of {total_phases}: {p_name}...")

            detail_prompt = WP_DETAIL_PROMPT.format(
                contract_context=wp_context,
                phase_name=p_name,
                phase_order=p_order
            )
            try:
                detail_res = llm.invoke(
                    [SystemMessage(content=detail_prompt), HumanMessage(content=f"extract details for {p_name}")]
                )
                phase_details = _extract_json_from_response(detail_res.content)
                if isinstance(phase_details, dict):
                    work_packages.append(phase_details)
            except Exception as exc:
                debug += f"\\n⚠️ Detail extraction failed for {p_name}: {exc}"
                
        if work_packages:
            debug += f"\\n✅ Pass 2: Extracted detailed data for {len(work_packages)} phases."

    update_status(project_code, "Merging all final datasets into Project DTO...")

    # ── Step 3: Merge all data sources ───────────────────────────────────────
    # Start with LLM-extracted SOW fields (flat fields for the Project table)
    extracted = {
        "ProjectNumber": project_code,
        "OpportunityID": opportunity_id,
        "customer": sow_extracted.get("customer"),
        "end_customer": sow_extracted.get("end_customer"),
        "PMName": sow_extracted.get("PMName"),
        "DMName": sow_extracted.get("DMName"),
        "country": sow_extracted.get("country"),
        "startdateContract": sow_extracted.get("startdateContract"),
        "endDateContract": sow_extracted.get("endDateContract"),
        "exchangerate": sow_extracted.get("exchangerate"),
        "MBRReporting_currency": sow_extracted.get("MBRReporting_currency"),
        "Proj_Stage": sow_extracted.get("Proj_Stage"),
        "Contr_Type": sow_extracted.get("Contr_Type"),
        "Rev_Type": sow_extracted.get("Rev_Type"),
        "Baseline_Rev": sow_extracted.get("Baseline_Rev"),
        "Prod_Grp": sow_extracted.get("Prod_Grp"),
        "Portfolio": sow_extracted.get("Portfolio"),
        "Region": sow_extracted.get("Region"),
        "Project_Owner": sow_extracted.get("Project_Owner"),
    }

    # Override/add with Excel-parsed data (more reliable for dates/costs)
    if excel_data:
        extracted["startdateBaseline"] = excel_data.get("startdateBaseline")
        extracted["endDateBaseline"] = excel_data.get("endDateBaseline")
        extracted["Baseline_Cost"] = excel_data.get("total_cost")
        extracted["total_project_cost"] = excel_data.get("total_cost")

        # Travel & Other costs from nested structures
        travel_data = excel_data.get("travel_expenses", {})
        other_data = excel_data.get("other_costs", {})
        extracted["travel_cost"] = travel_data.get("total", 0.0) if isinstance(travel_data, dict) else 0.0
        extracted["other_cost"] = other_data.get("total", 0.0) if isinstance(other_data, dict) else 0.0

        # JSON-serializable nested structures
        extracted["resources_json"] = json.dumps(excel_data.get("resources", []), default=str)
        extracted["invoice_json"] = json.dumps(
            excel_data.get("invoicing", []),
            default=str,
        )
        extracted["revenue_json"] = json.dumps(excel_data.get("revenue", []), default=str)
        extracted["total_hours_json"] = json.dumps({
            "planned_months": excel_data.get("planned_months", []),
            "total_hours": excel_data.get("total_hours", 0),
            "total_fees": excel_data.get("total_fees", 0),
            "hours_per_month": excel_data.get("total_hours_per_month", {}),
            "invoicing": excel_data.get("invoicing", []),
            "travel_expenses": travel_data,
            "other_costs": other_data,
        }, default=str)

    # Add SOW JSON (full nested structure from LLM)
    sow_nested = sow_extracted.get("sow_data")
    if sow_nested:
        extracted["sow_json"] = json.dumps(sow_nested, default=str)

    # Add work packages
    if work_packages:
        extracted["work_packages"] = work_packages

    debug += "\\n✅ Data Extraction Agent: merged Excel + SOW + Work Packages into project DTO."

    print(f"\\n--- DATA EXTRACTION DEBUG LOG ---\\n{debug}\\n----------------------------------\\n")

    return {
        "extracted_data": extracted,
        "debug_log": debug,
    }

