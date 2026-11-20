"""SQLite connection factory and version 2 schema and transactional version 1 upgrade."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS User (
 user_id INTEGER PRIMARY KEY, username TEXT NOT NULL COLLATE NOCASE UNIQUE,
 password_hash TEXT NOT NULL, full_name TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('Receptionist','Doctor','Nurse','Admin','Patient')),
 is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
 failed_attempts INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS Patient (
 patient_id INTEGER PRIMARY KEY, first_name TEXT NOT NULL, last_name TEXT NOT NULL,
 id_type TEXT NOT NULL CHECK(id_type IN ('SA ID','Passport')), id_number TEXT NOT NULL UNIQUE,
 date_of_birth TEXT NOT NULL, gender TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL,
 email TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '',
 next_of_kin_name TEXT NOT NULL, next_of_kin_phone TEXT NOT NULL,
 created_by INTEGER NOT NULL REFERENCES User(user_id), updated_by INTEGER NOT NULL REFERENCES User(user_id),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS Doctor (
 doctor_id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE REFERENCES User(user_id),
 first_name TEXT NOT NULL, last_name TEXT NOT NULL, phone TEXT NOT NULL,
 is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1))
);
CREATE TABLE IF NOT EXISTS DoctorSchedule (
 schedule_id INTEGER PRIMARY KEY, doctor_id INTEGER NOT NULL REFERENCES Doctor(doctor_id),
 day_of_week INTEGER NOT NULL CHECK(day_of_week BETWEEN 0 AND 6),
 start_time TEXT NOT NULL, end_time TEXT NOT NULL,
 slot_minutes INTEGER NOT NULL CHECK(slot_minutes BETWEEN 5 AND 120),
 UNIQUE(doctor_id,day_of_week), CHECK(end_time > start_time)
);
CREATE TABLE IF NOT EXISTS DoctorUnavailability (
 unavailability_id INTEGER PRIMARY KEY, doctor_id INTEGER NOT NULL REFERENCES Doctor(doctor_id),
 date TEXT NOT NULL, reason TEXT NOT NULL, UNIQUE(doctor_id,date)
);
CREATE TABLE IF NOT EXISTS Appointment (
 appointment_id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL REFERENCES Patient(patient_id),
 doctor_id INTEGER NOT NULL REFERENCES Doctor(doctor_id), date TEXT NOT NULL,
 start_time TEXT NOT NULL, duration_minutes INTEGER NOT NULL,
 reason TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'Booked'
 CHECK(status IN ('Booked','Checked-in','Completed','Cancelled','No-show')),
 created_by INTEGER NOT NULL REFERENCES User(user_id), updated_by INTEGER NOT NULL REFERENCES User(user_id),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_doctor_slot ON Appointment(doctor_id,date,start_time)
 WHERE status <> 'Cancelled';
CREATE INDEX IF NOT EXISTS ix_appointment_date ON Appointment(date,doctor_id,start_time);
CREATE INDEX IF NOT EXISTS ix_patient_slot ON Appointment(patient_id,date,start_time);
CREATE INDEX IF NOT EXISTS ix_patient_name ON Patient(last_name COLLATE NOCASE,first_name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_patient_phone ON Patient(phone);
CREATE TABLE IF NOT EXISTS Visit (
 visit_id INTEGER PRIMARY KEY, appointment_id INTEGER NOT NULL UNIQUE REFERENCES Appointment(appointment_id),
 patient_id INTEGER NOT NULL REFERENCES Patient(patient_id), clinician_id INTEGER NOT NULL REFERENCES User(user_id),
 visit_date TEXT NOT NULL, complaint TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
 diagnosis TEXT NOT NULL DEFAULT '', treatment TEXT NOT NULL DEFAULT '', follow_up_date TEXT,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_visit_history ON Visit(patient_id,visit_date DESC,visit_id DESC);
CREATE TABLE IF NOT EXISTS AuditLog (
 audit_id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES User(user_id), action TEXT NOT NULL,
 entity TEXT NOT NULL, entity_id INTEGER, timestamp TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS PatientPortal (
 user_id INTEGER PRIMARY KEY REFERENCES User(user_id),
 patient_id INTEGER NOT NULL UNIQUE REFERENCES Patient(patient_id),
 insurance_provider TEXT NOT NULL DEFAULT '', insurance_plan TEXT NOT NULL DEFAULT '',
 membership_number TEXT NOT NULL DEFAULT '', member_type TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS PatientInvitation (
 token_hash TEXT PRIMARY KEY, patient_id INTEGER NOT NULL REFERENCES Patient(patient_id),
 created_by INTEGER NOT NULL REFERENCES User(user_id), expires_at TEXT NOT NULL,
 used_at TEXT
);
PRAGMA user_version=2;
"""


class Database:
    """Open a fresh local connection for each unit of work."""

    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            version = con.execute("PRAGMA user_version").fetchone()[0]
            if version > 2:
                raise ValueError(
                    "Database version is newer than this app. Do not downgrade it."
                )
            if version == 1:
                snapshot = self.path.with_name(
                    self.path.stem + ".before-v2" + self.path.suffix
                )
                if not snapshot.exists():
                    destination = sqlite3.connect(str(snapshot))
                    try:
                        con.backup(destination)
                        if (
                            destination.execute("PRAGMA integrity_check").fetchone()[0]
                            != "ok"
                        ):
                            raise ValueError(
                                "Pre-upgrade backup failed its integrity check."
                            )
                    finally:
                        destination.close()
                # Keep references to User intact: create/copy/drop/rename within one
                # transaction. FK checks are restored and validated before commit.
                con.execute("PRAGMA foreign_keys=OFF")
                try:
                    con.execute("BEGIN IMMEDIATE")
                    user_sql = SCHEMA.split("CREATE TABLE IF NOT EXISTS Patient (")[0]
                    user_sql = user_sql.replace(
                        "CREATE TABLE IF NOT EXISTS User", "CREATE TABLE User_v2"
                    )
                    con.execute(user_sql)
                    con.execute("INSERT INTO User_v2 SELECT * FROM User")
                    con.execute("DROP TABLE User")
                    con.execute("ALTER TABLE User_v2 RENAME TO User")
                    if con.execute("PRAGMA foreign_key_check").fetchone():
                        raise ValueError(
                            "Database upgrade failed its relationship check."
                        )
                    con.execute("PRAGMA user_version=2")
                    con.commit()
                except Exception:
                    con.rollback()
                    raise
                finally:
                    con.execute("PRAGMA foreign_keys=ON")
            con.executescript(SCHEMA)

    @contextmanager
    def connect(self, write=False):
        con = sqlite3.connect(str(self.path), timeout=5)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=5000")
        try:
            if write:
                con.execute("BEGIN IMMEDIATE")
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
