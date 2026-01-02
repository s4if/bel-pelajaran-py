import sqlite3
from pathlib import Path

DB_DIR = Path(__file__).parent.parent / "instance"
DB_FILE = DB_DIR / "bel.db"
ASSETS_DIR = Path(__file__).parent.parent / "assets"


def init_db():
    DB_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hari TEXT NOT NULL,
            jam TEXT NOT NULL,
            file TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            edited_at TIMESTAMP
        )
    """)

    cursor.execute("PRAGMA table_info(schedules)")
    columns = [col[1] for col in cursor.fetchall()]

    if "edited_at" not in columns:
        cursor.execute("ALTER TABLE schedules ADD COLUMN edited_at TIMESTAMP")

    conn.commit()
    conn.close()


def save_config(config):
    init_db()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM schedules")

    for hari in ["senin", "selasa", "rabu", "kamis", "jumat", "sabtu"]:
        if hari in config:
            for item in config[hari]:
                cursor.execute(
                    "INSERT INTO schedules (hari, jam, file) VALUES (?, ?, ?)",
                    (hari, item["jam"], item["file"]),
                )

    conn.commit()
    conn.close()


def load_config():
    init_db()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT hari, jam, file FROM schedules ORDER BY hari, jam")
    rows = cursor.fetchall()

    conn.close()

    config = {}
    for hari, jam, file in rows:
        if hari not in config:
            config[hari] = []
        config[hari].append({"jam": jam, "file": file})

    return config


def has_config():
    if not DB_FILE.exists():
        return False

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM schedules")
    count = cursor.fetchone()[0]

    conn.close()

    return count > 0


def get_available_sounds():
    sounds = []
    if ASSETS_DIR.exists():
        for file in sorted(ASSETS_DIR.glob("*.mp3")):
            sounds.append(file.name)
    return sounds


def add_schedule(hari, jam, file):
    init_db()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO schedules (hari, jam, file) VALUES (?, ?, ?)",
        (hari, jam, file),
    )

    conn.commit()
    conn.close()

    return cursor.lastrowid


def update_schedule(id, hari=None, jam=None, file=None):
    init_db()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    updates = []
    values = []

    if hari is not None:
        updates.append("hari = ?")
        values.append(hari)
    if jam is not None:
        updates.append("jam = ?")
        values.append(jam)
    if file is not None:
        updates.append("file = ?")
        values.append(file)

    if updates:
        updates.append("edited_at = CURRENT_TIMESTAMP")
        values.append(id)
        cursor.execute(
            f"UPDATE schedules SET {', '.join(updates)} WHERE id = ?",
            values,
        )

    conn.commit()
    conn.close()


def delete_schedule(id):
    init_db()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM schedules WHERE id = ?", (id,))

    conn.commit()
    conn.close()


def get_schedule_by_id(id):
    init_db()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, hari, jam, file, created_at, edited_at FROM schedules WHERE id = ?",
        (id,),
    )
    row = cursor.fetchone()

    conn.close()

    if row:
        return {
            "id": row[0],
            "hari": row[1],
            "jam": row[2],
            "file": row[3],
            "created_at": row[4],
            "edited_at": row[5],
        }
    return None


def list_schedules():
    init_db()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, hari, jam, file, created_at, edited_at FROM schedules ORDER BY hari, jam"
    )
    rows = cursor.fetchall()

    conn.close()

    schedules = []
    for row in rows:
        schedules.append(
            {
                "id": row[0],
                "hari": row[1],
                "jam": row[2],
                "file": row[3],
                "created_at": row[4],
                "edited_at": row[5],
            }
        )

    return schedules
