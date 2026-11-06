import sqlite3
from pathlib import Path
from uuid import uuid4

DB_PATH = Path(__file__).parent / "farmguard.db"

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crops (
                crop_id TEXT PRIMARY KEY,
                crop_type TEXT NOT NULL,
                crop_name TEXT NOT NULL,
                location TEXT NOT NULL,
                section TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                observation_id TEXT PRIMARY KEY,
                crop_id TEXT NOT NULL,
                observation_date TEXT NOT NULL,
                symptoms TEXT NOT NULL,
                severity TEXT NOT NULL,
                affected_area REAL NOT NULL,
                notes TEXT,
                status TEXT NOT NULL DEFAULT 'Pending Inspection',
                FOREIGN KEY(crop_id) REFERENCES crops(crop_id)
            )
        """)

def add_observation(crop_type, crop_name, location, section, obs_date, symptoms, severity, affected_area, notes):
    with connect() as conn:
        existing = conn.execute(
            "SELECT crop_id FROM crops WHERE crop_type=? AND crop_name=? AND location=? AND section=?",
            (crop_type, crop_name, location, section)
        ).fetchone()
        crop_id = existing["crop_id"] if existing else "CR-" + uuid4().hex[:8].upper()
        if not existing:
            conn.execute(
                "INSERT INTO crops(crop_id,crop_type,crop_name,location,section) VALUES(?,?,?,?,?)",
                (crop_id, crop_type, crop_name, location, section)
            )
        obs_id = "OBS-" + uuid4().hex[:8].upper()
        conn.execute("""
            INSERT INTO observations(observation_id,crop_id,observation_date,symptoms,severity,affected_area,notes)
            VALUES(?,?,?,?,?,?,?)
        """, (obs_id, crop_id, obs_date, symptoms, severity, affected_area, notes))

def get_observations():
    with connect() as conn:
        rows = conn.execute("""
            SELECT o.*, c.crop_type, c.crop_name, c.location, c.section
            FROM observations o JOIN crops c ON o.crop_id=c.crop_id
            ORDER BY o.observation_date DESC
        """).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["recurrence_count"] = conn.execute("""
                SELECT COUNT(*) FROM observations
                WHERE crop_id=? AND lower(trim(symptoms))=lower(trim(?))
            """, (item["crop_id"], item["symptoms"])).fetchone()[0] - 1
            result.append(item)
        return result

def get_crops():
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM crops ORDER BY crop_name").fetchall()]

def update_status(observation_id, status):
    with connect() as conn:
        conn.execute("UPDATE observations SET status=? WHERE observation_id=?", (status, observation_id))

def delete_observation(observation_id):
    with connect() as conn:
        conn.execute("DELETE FROM observations WHERE observation_id=?", (observation_id,))
        # Remove crop rows that no longer have observations.
        conn.execute("DELETE FROM crops WHERE crop_id NOT IN (SELECT DISTINCT crop_id FROM observations)")

def add_sample_data():
    if get_observations():
        return
    samples = [
        ("Rice", "NSIC Rc 222", "Field A", "Plot 1", "2026-11-01", "Yellowing leaves", "Moderate", 25, "Sample demonstration record"),
        ("Mango", "Carabao Mango", "Orchard North", "Tree 05", "2026-11-02", "Leaf spots", "High", 40, "Sample demonstration record"),
        ("Banana", "Lakatan", "Field B", "Row 2", "2026-11-03", "Wilting leaves", "Critical", 60, "Sample demonstration record"),
    ]
    for sample in samples:
        add_observation(*sample)
