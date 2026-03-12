"""
Migration Script
Safely updates the `ProjectWorkPackage` SQLite table by adding 8 new text columns
for comprehensive project summaries generated during data extraction:
overview, engagement_summary, scope, tech_landscape, key_deliverables, missing_items, next_steps, quick_summary
"""

import sqlite3
import os
import shutil
from datetime import datetime

def migrate_wp():
    # 1. Paths
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    db_path = os.getenv("SQLITE_DB_PATH", "./data/openclaw.db")
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(os.path.join(project_root, db_path))
        
    print(f"Target Database: {db_path}")

    # 2. Backup
    backup_path = f"{db_path}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
    shutil.copy2(db_path, backup_path)
    print(f"Backup created at: {backup_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 3. Rename existing
        print("Renaming existing ProjectWorkPackage table to ProjectWorkPackage_old...")
        cursor.execute("DROP TABLE IF EXISTS ProjectWorkPackage_old")
        cursor.execute("ALTER TABLE ProjectWorkPackage RENAME TO ProjectWorkPackage_old")

        # 4. Create new schema with the 8 new text fields
        print("Creating new ProjectWorkPackage table schema...")
        cursor.execute("""
        CREATE TABLE ProjectWorkPackage (
            wp_id TEXT PRIMARY KEY,
            project_id TEXT,
            phase_name TEXT,
            phase_order INTEGER,
            prerequisites TEXT,
            activities TEXT,
            customer_responsibilities TEXT,
            out_of_scope TEXT,
            risks_mitigations TEXT,
            deliverables TEXT,
            acceptance_criteria TEXT,
            
            -- NEW FIELDS FOR COMPREHENSIVE SUMMARIES --
            overview TEXT,
            engagement_summary TEXT,
            scope TEXT,
            tech_landscape TEXT,
            key_deliverables TEXT,
            missing_items TEXT,
            next_steps TEXT,
            quick_summary TEXT,
            
            FOREIGN KEY(project_id) REFERENCES Project(project_id) ON DELETE CASCADE
        )
        """)

        # 5. Copy Old Data
        print("Restoring old data into new table...")
        cursor.execute("""
            INSERT INTO ProjectWorkPackage (
                wp_id, project_id, phase_name, phase_order,
                prerequisites, activities, customer_responsibilities,
                out_of_scope, risks_mitigations, deliverables, acceptance_criteria
            )
            SELECT 
                wp_id, project_id, phase_name, phase_order,
                prerequisites, activities, customer_responsibilities,
                out_of_scope, risks_mitigations, deliverables, acceptance_criteria
            FROM ProjectWorkPackage_old
        """)

        # 6. Cleanup
        print("Dropping old table...")
        cursor.execute("DROP TABLE ProjectWorkPackage_old")

        conn.commit()
        print("✅ Migration completed successfully!")

    except Exception as e:
        print(f"\n❌ Migration Failed: {e}")
        print("Rolling back changes...")
        conn.rollback()
        
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_wp()
