import sqlite3
import json
import os

DB_PATH = 'data/openclaw.db'

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Project (
            project_id TEXT PRIMARY KEY,
            sow_json TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def test_ingestion():
    project_id = '9162d923-a2a6-42b9-a636-82eb0c1e1e31'
    sample_data = {
        "pricing_summary": {"total": 1000, "currency": "USD"},
        "milestones": ["Discovery", "Development", "UAT"]
    }
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO Project (project_id, sow_json, status) VALUES (?, ?, ?)',
                   (project_id, json.dumps(sample_data), 'active'))
    conn.commit()
    
    # Verification query similar to what was in bash history
    cursor.execute('SELECT sow_json FROM Project WHERE project_id = ?', (project_id,))
    row = cursor.fetchone()
    if row:
        data = json.loads(row[0])
        print(f"Verified ingestion for {project_id}")
        print(f"Data keys: {list(data.keys())}")
        print(f"Pricing summary type: {type(data.get('pricing_summary'))}")
    
    conn.close()

if __name__ == "__main__":
    init_db()
    test_ingestion()
