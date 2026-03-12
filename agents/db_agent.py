"""
Agent Mesh – DB Agent
Validates extracted project data, checks for duplicates by ProjectNumber
and OpportunityID, and inserts into the SQLite Project table.
"""
import sqlite3
import uuid
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _resolve_path(env_val):
    if os.path.isabs(env_val):
        return env_val
    return os.path.abspath(os.path.join(PROJECT_ROOT, env_val))


DB_PATH = _resolve_path(os.getenv("SQLITE_DB_PATH", "./data/openclaw.db"))

# Fields that MUST be present for a valid insert
REQUIRED_FIELDS = ["ProjectNumber", "OpportunityID", "customer"]

# All columns in the Project table (excluding project_id, auto-generated)
PROJECT_COLUMNS = [
    "ProjectNumber", "OpportunityID", "customer", "end_customer",
    "PMName", "DMName", "country",
    "startdateContract", "endDateContract",
    "startdateBaseline", "endDateBaseline",
    "exchangerate", "MBRReporting_currency",
    "Proj_Stage", "Prod_Grp", "Portfolio", "Contr_Type", "Rev_Type",
    "Region", "CMT", "Country_Group",
    "Project_Owner", "Delivery_Manager", "Q2C_Ops",
    "Start_Dt", "End_Date", "ActiveCurrency",
    "Baseline_Rev", "Baseline_Cost",
    "SEGM_percent", "DEGM_percent", "EGM_variance_percent",
    "sow_json", "resources_json", "invoice_json",
    "revenue_json", "total_hours_json",
    "total_project_cost", "travel_cost", "other_cost",
]


def _validate(data: dict) -> list[str]:
    """Return a list of validation error messages, empty if valid."""
    errors = []
    for field in REQUIRED_FIELDS:
        val = data.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            errors.append(f"Missing required field: {field}")
    return errors


def _check_duplicate(conn: sqlite3.Connection, data: dict) -> str | None:
    """Return existing project_id if duplicate found, else None."""
    row = conn.execute(
        "SELECT project_id FROM Project WHERE ProjectNumber = ? OR OpportunityID = ?",
        (data.get("ProjectNumber"), data.get("OpportunityID")),
    ).fetchone()
    return row[0] if row else None


def _insert_project(conn: sqlite3.Connection, data: dict) -> str:
    """Insert a row into the Project table and return the generated project_id."""
    project_id = str(uuid.uuid4())

    cols = ["project_id"]
    vals = [project_id]

    import json

    for col in PROJECT_COLUMNS:
        if col in data and data[col] is not None:
            cols.append(col)
            val = data[col]
            if col.endswith("_json") and isinstance(val, (dict, list)):
                vals.append(json.dumps(val, default=str))
            else:
                vals.append(val)

    placeholders = ", ".join(["?"] * len(cols))
    col_str = ", ".join(cols)

    conn.execute(
        f"INSERT INTO Project ({col_str}) VALUES ({placeholders})",
        vals,
    )
    conn.commit()
    return project_id


def _insert_work_packages(conn: sqlite3.Connection, project_id: str, work_packages: list) -> int:
    """Insert work package rows into ProjectWorkPackage table. Returns count inserted."""
    count = 0
    for wp in work_packages:
        wp_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO ProjectWorkPackage
               (wp_id, project_id, phase_name, phase_order,
                prerequisites, activities, customer_responsibilities,
                out_of_scope, risks_mitigations, deliverables, acceptance_criteria,
                overview, engagement_summary, scope, tech_landscape, 
                key_deliverables, missing_items, next_steps, quick_summary)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                wp_id,
                project_id,
                wp.get("phase_name", "Unknown Phase"),
                wp.get("phase_order", count + 1),
                wp.get("prerequisites", ""),
                wp.get("activities", ""),
                wp.get("customer_responsibilities", ""),
                wp.get("out_of_scope", ""),
                wp.get("risks_mitigations", ""),
                wp.get("deliverables", ""),
                wp.get("acceptance_criteria", ""),
                
                # New Comprehensive Summary Fields
                wp.get("overview", ""),
                wp.get("engagement_summary", ""),
                wp.get("scope", ""),
                wp.get("tech_landscape", ""),
                wp.get("key_deliverables", ""),
                wp.get("missing_items", ""),
                wp.get("next_steps", ""),
                wp.get("quick_summary", "")
            ),
        )
        count += 1
    conn.commit()
    return count


def db_agent_node(state: dict) -> dict:
    """
    Validate and persist extracted project data and work packages to SQLite.

    Expects state keys:
      - extracted_data: dict with project fields + optional work_packages list
      - user_confirmed: bool (must be True to proceed)
    """
    data = state.get("extracted_data")
    confirmed = state.get("user_confirmed", False)
    debug = state.get("debug_log", "")

    if not confirmed:
        return {
            "response": "⚠️ Project data has not been confirmed by the user yet.",
            "debug_log": debug + "\n⚠️ DB Agent: awaiting user confirmation.",
        }

    if not data:
        return {
            "response": "❌ No extracted data to persist.",
            "debug_log": debug + "\n❌ DB Agent: no extracted_data in state.",
        }

    # Extract work packages before validation (not a Project table field)
    work_packages = data.pop("work_packages", [])

    # 1. Validate
    errors = _validate(data)
    if errors:
        error_msg = "Validation errors:\n• " + "\n• ".join(errors)
        return {
            "response": f"❌ {error_msg}",
            "debug_log": debug + f"\n❌ DB Agent: validation failed – {errors}",
        }

    # 2. Duplicate check
    conn = sqlite3.connect(DB_PATH)
    try:
        existing_id = _check_duplicate(conn, data)
        if existing_id:
            return {
                "response": (
                    f"⚠️ Duplicate detected: A project with ProjectNumber "
                    f"'{data.get('ProjectNumber')}' or OpportunityID "
                    f"'{data.get('OpportunityID')}' already exists "
                    f"(project_id: {existing_id}). No new record created."
                ),
                "debug_log": debug + f"\n⚠️ DB Agent: duplicate found – {existing_id}.",
            }

        # 3. Insert Project
        new_id = _insert_project(conn, data)

        # 4. Insert Work Packages
        wp_count = 0
        if work_packages:
            wp_count = _insert_work_packages(conn, new_id, work_packages)

        return {
            "response": (
                f"✅ Project created successfully!\n"
                f"• Project ID: {new_id}\n"
                f"• Project Number: {data.get('ProjectNumber')}\n"
                f"• Opportunity ID: {data.get('OpportunityID')}\n"
                f"• Customer: {data.get('customer')}\n"
                f"• Work Packages: {wp_count} phases saved"
            ),
            "debug_log": debug + f"\n✅ DB Agent: inserted project {new_id} with {wp_count} work packages.",
        }
    except Exception as exc:
        return {
            "response": f"❌ Database error: {exc}",
            "debug_log": debug + f"\n❌ DB Agent: database error – {exc}",
        }
    finally:
        conn.close()

