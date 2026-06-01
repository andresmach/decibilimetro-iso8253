"""
database.py — Persistencia SQLite: sesiones, mediciones y calibraciones
"""
import sqlite3, json, logging
from datetime import datetime
from pathlib import Path

log = logging.getLogger("database")
DB_PATH = Path(__file__).parent / "decibilimetro.db"

ISO_LIMITS = {125:35, 250:25, 500:21, 1000:26, 2000:34, 4000:37, 8000:43}

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at    TEXT DEFAULT (datetime('now','localtime')),
            finished_at   TEXT,
            institucion   TEXT,
            direccion     TEXT,
            sala          TEXT,
            fonoaudiologo TEXT,
            mat_fono      TEXT,
            bioingeniero  TEXT,
            mat_bio       TEXT,
            equipo_sn     TEXT,
            pistonofono   TEXT,
            temperatura   TEXT,
            humedad       TEXT,
            observaciones TEXT,
            veredicto     TEXT DEFAULT 'PENDIENTE'
        );
        CREATE TABLE IF NOT EXISTS measurements (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER REFERENCES sessions(id),
            ts_ms      INTEGER,
            db_125     REAL, db_250  REAL, db_500  REAL,
            db_1000    REAL, db_2000 REAL, db_4000 REAL, db_8000 REAL,
            apta       INTEGER
        );
        CREATE TABLE IF NOT EXISTS calibrations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER REFERENCES sessions(id),
            ts         TEXT DEFAULT (datetime('now','localtime')),
            ref_db     REAL, measured_db REAL, factor REAL
        );
        """)
    log.info(f"Base de datos lista: {DB_PATH}")

def create_session() -> int:
    with get_conn() as conn:
        cur = conn.execute("INSERT INTO sessions DEFAULT VALUES")
        return cur.lastrowid

def update_session(session_id: int, data: dict):
    allowed = {"institucion","direccion","sala","fonoaudiologo","mat_fono",
               "bioingeniero","mat_bio","equipo_sn","pistonofono",
               "temperatura","humedad","observaciones"}
    filtered = {k:v for k,v in data.items() if k in allowed}
    if not filtered: return
    cols  = ", ".join(f"{k}=?" for k in filtered)
    vals  = list(filtered.values()) + [session_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE sessions SET {cols} WHERE id=?", vals)

def insert_measurement(session_id: int, msg: dict):
    spl = msg.get("spl", {})
    apta = 1 if msg.get("apta") else 0
    with get_conn() as conn:
        conn.execute("""INSERT INTO measurements
            (session_id,ts_ms,db_125,db_250,db_500,db_1000,db_2000,db_4000,db_8000,apta)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (session_id, msg.get("ts",0),
             spl.get("125",0), spl.get("250",0), spl.get("500",0),
             spl.get("1000",0), spl.get("2000",0), spl.get("4000",0),
             spl.get("8000",0), apta))

def get_session_averages(session_id: int) -> dict:
    """Retorna el promedio de cada banda para la sesión."""
    with get_conn() as conn:
        row = conn.execute("""
            SELECT AVG(db_125) AS db125, AVG(db_250) AS db250,
                   AVG(db_500) AS db500, AVG(db_1000) AS db1000,
                   AVG(db_2000) AS db2000, AVG(db_4000) AS db4000,
                   AVG(db_8000) AS db8000, COUNT(*) AS n
            FROM measurements WHERE session_id=?""", [session_id]).fetchone()
    if not row or row["n"] == 0:
        return {}
    return {
        125:  row["db125"]  or 0,
        250:  row["db250"]  or 0,
        500:  row["db500"]  or 0,
        1000: row["db1000"] or 0,
        2000: row["db2000"] or 0,
        4000: row["db4000"] or 0,
        8000: row["db8000"] or 0,
    }

def get_session(session_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id=?", [session_id]).fetchone()
    return dict(row) if row else {}

def finalize_session(session_id: int, apta: bool):
    with get_conn() as conn:
        conn.execute("""UPDATE sessions SET finished_at=datetime('now','localtime'),
                        veredicto=? WHERE id=?""",
                     ["APTA" if apta else "NO_APTA", session_id])

def list_sessions(limit=20) -> list:
    with get_conn() as conn:
        rows = conn.execute("""SELECT id, started_at, institucion, sala, veredicto
                               FROM sessions ORDER BY id DESC LIMIT ?""", [limit]).fetchall()
    return [dict(r) for r in rows]
