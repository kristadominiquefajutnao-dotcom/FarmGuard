import hashlib
import hmac
import secrets
import sqlite3
from pathlib import Path
from uuid import uuid4

DB_PATH = Path(__file__).parent / "farmguard.db"
_HASH_ITERATIONS = 310_000


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _make_id(prefix):
    return f"{prefix}-" + uuid4().hex[:8].upper()


def _hash_secret(secret, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", str(secret).encode("utf-8"), bytes.fromhex(salt), _HASH_ITERATIONS
    ).hex()
    return salt, digest


def _verify_secret(secret, salt, saved_hash):
    _, candidate = _hash_secret(secret, salt)
    return hmac.compare_digest(candidate, saved_hash)


def _ensure_column(conn, table, column, definition):
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    """Create tables and safely migrate the original single-farm database."""
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS owners (
                owner_id TEXT PRIMARY KEY,
                full_name TEXT NOT NULL,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS farms (
                farm_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL UNIQUE,
                farm_name TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(owner_id) REFERENCES owners(owner_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workers (
                worker_id TEXT PRIMARY KEY,
                farm_id TEXT NOT NULL,
                worker_code TEXT NOT NULL,
                full_name TEXT NOT NULL,
                pin_salt TEXT NOT NULL,
                pin_hash TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(farm_id, worker_code),
                FOREIGN KEY(farm_id) REFERENCES farms(farm_id)
            )
        """)
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

        # Add new fields without deleting existing crop and observation records.
        _ensure_column(conn, "crops", "farm_id", "TEXT")
        _ensure_column(conn, "observations", "created_by_worker_id", "TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_crops_farm_id ON crops(farm_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workers_farm_id ON workers(farm_id)")


def create_owner(full_name, farm_name, username, password):
    """Register a farm owner and create their farm. Returns owner_id and farm_id."""
    full_name = str(full_name).strip()
    farm_name = str(farm_name).strip()
    username = str(username).strip()
    if not full_name or not farm_name or not username:
        raise ValueError("Full name, farm name, and username are required.")
    if len(str(password)) < 8:
        raise ValueError("Password must be at least 8 characters long.")

    owner_id, farm_id = _make_id("OWN"), _make_id("FARM")
    salt, password_hash = _hash_secret(password)
    with connect() as conn:
        try:
            conn.execute(
                "INSERT INTO owners(owner_id, full_name, username, password_salt, password_hash) VALUES(?,?,?,?,?)",
                (owner_id, full_name, username, salt, password_hash),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("That username is already registered.") from exc
        conn.execute(
            "INSERT INTO farms(farm_id, owner_id, farm_name) VALUES(?,?,?)",
            (farm_id, owner_id, farm_name),
        )
        # Attach legacy records to the first farm registered after migration.
        conn.execute("UPDATE crops SET farm_id=? WHERE farm_id IS NULL", (farm_id,))
    return {"owner_id": owner_id, "farm_id": farm_id}


def authenticate_owner(username, password):
    """Return owner/farm session details, or None if credentials are invalid."""
    with connect() as conn:
        row = conn.execute("""
            SELECT o.owner_id, o.full_name, o.username, o.password_salt, o.password_hash,
                   f.farm_id, f.farm_name
            FROM owners o JOIN farms f ON f.owner_id=o.owner_id
            WHERE o.username=? COLLATE NOCASE
        """, (str(username).strip(),)).fetchone()
    if row is None or not _verify_secret(password, row["password_salt"], row["password_hash"]):
        return None
    return {key: row[key] for key in ("owner_id", "full_name", "username", "farm_id", "farm_name")}


def get_farm_by_owner(owner_id):
    with connect() as conn:
        row = conn.execute(
            "SELECT farm_id, owner_id, farm_name, created_at FROM farms WHERE owner_id=?",
            (owner_id,),
        ).fetchone()
    return dict(row) if row else None


def add_worker(farm_id, full_name, pin):
    """Add a worker and return their worker_code (share it with the worker)."""
    full_name, pin = str(full_name).strip(), str(pin).strip()
    if not full_name:
        raise ValueError("Worker name is required.")
    if not pin.isdigit() or not 4 <= len(pin) <= 6:
        raise ValueError("Worker PIN must be 4 to 6 digits.")

    worker_id, worker_code = _make_id("WRK"), secrets.token_hex(3).upper()
    salt, pin_hash = _hash_secret(pin)
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM farms WHERE farm_id=?", (farm_id,)).fetchone():
            raise ValueError("Farm account was not found.")
        conn.execute("""
            INSERT INTO workers(worker_id, farm_id, worker_code, full_name, pin_salt, pin_hash)
            VALUES(?,?,?,?,?,?)
        """, (worker_id, farm_id, worker_code, full_name, salt, pin_hash))
    return {"worker_id": worker_id, "worker_code": worker_code, "full_name": full_name}


def authenticate_worker(farm_id, worker_code, pin):
    """Authenticate a worker using farm ID, worker code, and individual PIN."""
    with connect() as conn:
        row = conn.execute("""
            SELECT worker_id, farm_id, worker_code, full_name, pin_salt, pin_hash
            FROM workers WHERE farm_id=? AND worker_code=? AND is_active=1
        """, (farm_id, str(worker_code).strip().upper())).fetchone()
    if row is None or not _verify_secret(pin, row["pin_salt"], row["pin_hash"]):
        return None
    return {key: row[key] for key in ("worker_id", "farm_id", "worker_code", "full_name")}


def get_workers(farm_id, include_inactive=False):
    query = "SELECT worker_id, farm_id, worker_code, full_name, is_active, created_at FROM workers WHERE farm_id=?"
    params = [farm_id]
    if not include_inactive:
        query += " AND is_active=1"
    query += " ORDER BY full_name"
    with connect() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def set_worker_active(farm_id, worker_id, is_active):
    """Deactivate/reactivate a worker without deleting their report history."""
    with connect() as conn:
        conn.execute(
            "UPDATE workers SET is_active=? WHERE farm_id=? AND worker_id=?",
            (1 if is_active else 0, farm_id, worker_id),
        )


def add_observation(
    crop_type, crop_name, location, section, obs_date, symptoms, severity,
    affected_area, notes, farm_id=None, worker_id=None
):
    """Save a crop report. Pass farm_id and worker_id for authenticated worker reports."""
    with connect() as conn:
        if farm_id is None:
            existing = conn.execute("""
                SELECT crop_id FROM crops
                WHERE crop_type=? AND crop_name=? AND location=? AND section IS ? AND farm_id IS NULL
            """, (crop_type, crop_name, location, section)).fetchone()
        else:
            existing = conn.execute("""
                SELECT crop_id FROM crops
                WHERE crop_type=? AND crop_name=? AND location=? AND section IS ? AND farm_id=?
            """, (crop_type, crop_name, location, section, farm_id)).fetchone()

        crop_id = existing["crop_id"] if existing else _make_id("CR")
        if existing is None:
            conn.execute("""
                INSERT INTO crops(crop_id, crop_type, crop_name, location, section, farm_id)
                VALUES(?,?,?,?,?,?)
            """, (crop_id, crop_type, crop_name, location, section, farm_id))

        observation_id = _make_id("OBS")
        conn.execute("""
            INSERT INTO observations(
                observation_id, crop_id, observation_date, symptoms, severity,
                affected_area, notes, created_by_worker_id
            ) VALUES(?,?,?,?,?,?,?,?)
        """, (observation_id, crop_id, obs_date, symptoms, severity, affected_area, notes, worker_id))
    return observation_id


def get_observations(farm_id=None):
    """Get reports; always pass the logged-in user's farm_id in the new app."""
    with connect() as conn:
        query = """
            SELECT o.*, c.crop_type, c.crop_name, c.location, c.section,
                   w.full_name AS reported_by, w.worker_code AS reporter_code
            FROM observations o
            JOIN crops c ON o.crop_id=c.crop_id
            LEFT JOIN workers w ON o.created_by_worker_id=w.worker_id
        """
        params = []
        if farm_id is not None:
            query += " WHERE c.farm_id=?"
            params.append(farm_id)
        query += " ORDER BY o.observation_date DESC"
        rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["recurrence_count"] = conn.execute("""
                SELECT COUNT(*) - 1 FROM observations
                WHERE crop_id=? AND lower(trim(symptoms))=lower(trim(?))
            """, (item["crop_id"], item["symptoms"])).fetchone()[0]
            results.append(item)
        return results


def get_crops(farm_id=None):
    with connect() as conn:
        if farm_id is None:
            rows = conn.execute("SELECT * FROM crops ORDER BY crop_name").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM crops WHERE farm_id=? ORDER BY crop_name", (farm_id,)
            ).fetchall()
    return [dict(row) for row in rows]


def update_status(observation_id, status, farm_id=None):
    with connect() as conn:
        if farm_id is None:
            conn.execute(
                "UPDATE observations SET status=? WHERE observation_id=?",
                (status, observation_id),
            )
        else:
            conn.execute("""
                UPDATE observations SET status=?
                WHERE observation_id=?
                  AND crop_id IN (SELECT crop_id FROM crops WHERE farm_id=?)
            """, (status, observation_id, farm_id))


def delete_observation(observation_id, farm_id=None):
    with connect() as conn:
        if farm_id is None:
            conn.execute("DELETE FROM observations WHERE observation_id=?", (observation_id,))
            conn.execute("""
                DELETE FROM crops
                WHERE crop_id NOT IN (SELECT DISTINCT crop_id FROM observations)
            """)
        else:
            conn.execute("""
                DELETE FROM observations
                WHERE observation_id=?
                  AND crop_id IN (SELECT crop_id FROM crops WHERE farm_id=?)
            """, (observation_id, farm_id))
            conn.execute("""
                DELETE FROM crops
                WHERE farm_id=?
                  AND crop_id NOT IN (SELECT DISTINCT crop_id FROM observations)
            """, (farm_id,))


def add_sample_data(farm_id=None):
    if get_observations(farm_id):
        return
    samples = [
        ("Rice", "NSIC Rc 222", "Field A", "Plot 1", "2026-11-01", "Yellowing leaves", "Moderate", 25, "Sample demonstration record"),
        ("Mango", "Carabao Mango", "Orchard North", "Tree 05", "2026-11-02", "Leaf spots", "High", 40, "Sample demonstration record"),
        ("Banana", "Lakatan", "Field B", "Row 2", "2026-11-03", "Wilting leaves", "Critical", 60, "Sample demonstration record"),
    ]
    for sample in samples:
        add_observation(*sample, farm_id=farm_id)
