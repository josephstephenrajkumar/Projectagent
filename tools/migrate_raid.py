import sqlite3
import os

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "openclaw.db"))

def migrate():
    print(f"Migrating RAIDitems table in {DB_PATH} ...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Rename existing to backup
    try:
        cursor.execute("DROP TABLE IF EXISTS RAIDitems_backup")
        cursor.execute("CREATE TABLE RAIDitems_backup AS SELECT * FROM RAIDitems")
        cursor.execute("DROP TABLE RAIDitems")
        print("Backed up old RAIDitems to RAIDitems_backup")
    except sqlite3.OperationalError as e:
        print(f"Skipping backup: {e}")

    # 2. Create new table
    cursor.execute("""
    CREATE TABLE RAIDitems (
        raidID TEXT PRIMARY KEY,
        project_id TEXT,
        LastupdateDate DATETIME,
        Type VARCHAR(50),
        Category VARCHAR(50),
        owner VARCHAR(100),
        Description TEXT,
        MitigatingAction TEXT,
        DueDate DATETIME,
        ROAM VARCHAR(50),
        StartDate DATETIME,
        EndDate DATETIME,
        Status VARCHAR(25),
        Statusdate DATETIME,
        Status_summary TEXT,
        FOREIGN KEY(project_id) REFERENCES Project(project_id)
    );
    """)
    print("Created new RAIDitems schema.")

    # 3. Try to copy data back (mapping columns that match)
    try:
        cursor.execute("""
        INSERT INTO RAIDitems (raidID, project_id, LastupdateDate, Type, Category, ROAM, Description, StartDate, EndDate, Status)
        SELECT raidID, project_id, LastupdateDate, Type, Category, ROAM, Description, StartDate, EndDate, Status
        FROM RAIDitems_backup
        """)
        print("Restored existing data into new schema.")
    except Exception as e:
        print(f"Warning: Failed to restore data: {e}")

    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
