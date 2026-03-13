#!/usr/bin/env python3
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.isabs(os.getenv("SQLITE_DB_PATH", "./data/openclaw.db")) and os.getenv("SQLITE_DB_PATH") or os.path.abspath(os.path.join(PROJECT_ROOT, os.getenv("SQLITE_DB_PATH", "./data/openclaw.db")))

def init_semantic_map():
    print(f"Initializing SemanticMap table in {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS SemanticMap (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword TEXT UNIQUE,
        entity TEXT,
        attribute TEXT,
        filter_logic TEXT,
        description TEXT
    )
    """)
    
    # Seed with some initial high-value patterns
    initial_mappings = [
        ("high priority", "RAIDitems", "Category", "Category LIKE '%High%'", "Filters for high priority risks/issues"),
        ("overdue", "RAIDitems", "DueDate", "DueDate < date('now') AND Status NOT IN ('Closed', 'Resolved')", "Finds items past their due date"),
        ("costs", "Project", "total_project_cost", None, "References total contractual costs"),
        ("milestones", "ProjectWorkPackage", "phase_name", None, "References project phases/milestones"),
        ("customer", "Project", "customer", "customer LIKE '%?%'", "Fuzzy search for customer names"),
        ("owner", "Project", "Project_Owner", None, "References the main project owner")
    ]
    
    for mapping in initial_mappings:
        try:
            cursor.execute("INSERT INTO SemanticMap (keyword, entity, attribute, filter_logic, description) VALUES (?, ?, ?, ?, ?)", mapping)
        except sqlite3.IntegrityError:
            pass # Already exists
            
    conn.commit()
    conn.close()
    print("✅ SemanticMap table initialized and seeded.")

if __name__ == "__main__":
    init_semantic_map()
