"""Application rules. The UI calls this layer rather than executing SQL."""

from datetime import date, datetime, timedelta
from pathlib import Path
import csv
import os
import tempfile
import re
import sqlite3
import time
import hashlib
import secrets

from .database import Database
from .security import hash_password, verify_password

ROLES = ("Receptionist", "Doctor", "Nurse", "Admin")
PATIENT_FIELDS = (
    "first_name",
    "last_name",
    "id_type",
    "id_number",
    "date_of_birth",
    "gender",
    "phone",
    "email",
    "address",
    "next_of_kin_name",
    "next_of_kin_phone",
)


class ClinicError(ValueError):
    """A validation error suitable for displaying to a user."""


class AccessDenied(ClinicError):
    """A session or role does not permit the requested action."""


def stamp():
    return datetime.now().isoformat(timespec="seconds")


def parse_date(value):
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError()
        return parsed
    except (ValueError, TypeError):
        raise ClinicError("Enter a valid date in YYYY-MM-DD format.") from None


def minutes(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{2}:\d{2}", value):
        raise ClinicError("Enter a valid time in HH:MM format.")
    hour, minute = map(int, value.split(":"))
    if hour > 23 or minute > 59:
        raise ClinicError("Enter a valid time in HH:MM format.")
    return hour * 60 + minute


def phone_ok(value):
    return bool(re.fullmatch(r"0[0-9]{9}", value))


class ClinicService:
    """One authenticated session, with server-side-equivalent role checks."""

    IDLE_SECONDS = 900

    def __init__(self, database_path, clock=None):
        self.db = Database(database_path)
        self.user = None
        self.last_activity = 0.0
        self.clock = clock or datetime.now

    def _audit(self, con, action, entity, entity_id, actor=None):
        actor = (
            actor
            if actor is not None
            else (self.user["user_id"] if self.user else None)
        )
        con.execute(
            "INSERT INTO AuditLog(user_id,action,entity,entity_id,timestamp) VALUES(?,?,?,?,?)",
            (actor, action, entity, entity_id, stamp()),
        )

    def _require(self, *roles):
        if not self.user:
            raise AccessDenied("Please log in first.")
        if time.monotonic() - self.last_activity >= self.IDLE_SECONDS:
            self.logout()
            raise AccessDenied(
                "Your session expired after 15 minutes without activity."
            )
        with self.db.connect() as con:
            row = con.execute(
                "SELECT * FROM User WHERE user_id=?", (self.user["user_id"],)
            ).fetchone()
        if not row or not row["is_active"] or row["failed_attempts"] >= 5:
            self.logout()
            raise AccessDenied(
                "Your account is inactive or locked. Contact the administrator."
            )
        self.user = dict(row)
        if roles and self.user["role"] not in roles:
            raise AccessDenied("Your role is not allowed to perform this action.")
        self.last_activity = time.monotonic()
        return self.user

    def touch(self):
        """Record actual keyboard/mouse activity, without extending an expired session."""
        self._require()

    def needs_setup(self):
        with self.db.connect() as con:
            return con.execute("SELECT COUNT(*) FROM User").fetchone()[0] == 0

    def bootstrap_admin(self, username, full_name, password):
        if not username.strip() or not full_name.strip():
            raise ClinicError("Username and full name are required.")
        encoded = hash_password(password)
        with self.db.connect(write=True) as con:
            if con.execute("SELECT COUNT(*) FROM User").fetchone()[0]:
                raise AccessDenied("Initial setup is already complete.")
            cur = con.execute(
                "INSERT INTO User(username,password_hash,full_name,role,created_at) VALUES(?,?,?,?,?)",
                (username.strip(), encoded, full_name.strip(), "Admin", stamp()),
            )
            self._audit(con, "initial_setup", "User", cur.lastrowid, cur.lastrowid)
        return cur.lastrowid

    def login(self, username, password):
        self.user = None
        error = None
        with self.db.connect(write=True) as con:
            row = con.execute(
                "SELECT * FROM User WHERE username=?", (username.strip(),)
            ).fetchone()
            if not row or not row["is_active"]:
                error = "Invalid username or password."
            elif row["failed_attempts"] >= 5:
                error = "Account locked. Contact the administrator."
            elif not verify_password(password, row["password_hash"]):
                con.execute(
                    "UPDATE User SET failed_attempts=failed_attempts+1 WHERE user_id=?",
                    (row["user_id"],),
                )
                self._audit(con, "login_failed", "User", row["user_id"], row["user_id"])
                error = "Invalid username or password."
            else:
                con.execute(
                    "UPDATE User SET failed_attempts=0 WHERE user_id=?",
                    (row["user_id"],),
                )
                self._audit(
                    con, "login_success", "User", row["user_id"], row["user_id"]
                )
                self.user = dict(row)
                self.user["failed_attempts"] = 0
        if error:
            raise AccessDenied(error)
        self.last_activity = time.monotonic()
        return {
            key: self.user[key] for key in ("user_id", "username", "full_name", "role")
        }

    def logout(self):
        self.user = None
        self.last_activity = 0.0

    def users(self):
        self._require("Admin")
        with self.db.connect() as con:
            return [
                dict(r)
                for r in con.execute(
                    "SELECT user_id,username,full_name,role,is_active,failed_attempts FROM User ORDER BY username"
                )
            ]

    def create_user(self, username, full_name, role, password):
        self._require("Admin")
        if role not in ROLES or not username.strip() or not full_name.strip():
            raise ClinicError("Username, full name and a valid role are required.")
        encoded = hash_password(password)
        try:
            with self.db.connect(write=True) as con:
                cur = con.execute(
                    "INSERT INTO User(username,password_hash,full_name,role,created_at) VALUES(?,?,?,?,?)",
                    (username.strip(), encoded, full_name.strip(), role, stamp()),
                )
                self._audit(con, "create", "User", cur.lastrowid)
                return cur.lastrowid
        except sqlite3.IntegrityError:
            raise ClinicError("That username is already in use.") from None

    def change_user(self, user_id, role=None, active=None, password=None, unlock=False):
        self._require("Admin")
        encoded = hash_password(password) if password is not None else None
        with self.db.connect(write=True) as con:
            row = con.execute(
                "SELECT * FROM User WHERE user_id=?", (user_id,)
            ).fetchone()
            if not row:
                raise ClinicError("Select an existing user.")
            new_role = role if role is not None else row["role"]
            new_active = int(active) if active is not None else row["is_active"]
            if row["role"] == "Patient":
                if new_role != "Patient":
                    raise ClinicError(
                        "Patient accounts cannot be converted into staff accounts."
                    )
            elif new_role not in ROLES:
                raise ClinicError("Select a valid role.")
            if (
                row["role"] == "Admin"
                and row["is_active"]
                and (new_role != "Admin" or not new_active)
            ):
                remaining = con.execute(
                    "SELECT COUNT(*) FROM User WHERE role='Admin' AND is_active=1 AND failed_attempts<5 AND user_id<>?",
                    (user_id,),
                ).fetchone()[0]
                if not remaining:
                    raise ClinicError(
                        "Keep at least one active, unlocked administrator."
                    )
            if (
                new_role != "Doctor"
                and con.execute(
                    "SELECT 1 FROM Doctor WHERE user_id=?", (user_id,)
                ).fetchone()
            ):
                raise ClinicError(
                    "Unlink this user from their doctor profile before changing role."
                )
            con.execute(
                "UPDATE User SET role=?,is_active=?,password_hash=?,failed_attempts=? WHERE user_id=?",
                (
                    new_role,
                    new_active,
                    encoded or row["password_hash"],
                    0 if unlock or encoded else row["failed_attempts"],
                    user_id,
                ),
            )
            self._audit(con, "account_change", "User", user_id)

    def _patient_values(self, data):
        values = {k: str(data.get(k, "")).strip() for k in PATIENT_FIELDS}
        for key in (
            "first_name",
            "last_name",
            "id_number",
            "date_of_birth",
            "phone",
            "next_of_kin_name",
            "next_of_kin_phone",
        ):
            if not values[key]:
                raise ClinicError(f'{key.replace("_", " ").capitalize()} is required.')
        if values["id_type"] not in ("SA ID", "Passport"):
            raise ClinicError("Choose SA ID or Passport.")
        if values["id_type"] == "SA ID" and not re.fullmatch(
            r"[0-9]{13}", values["id_number"]
        ):
            raise ClinicError("SA ID number must contain exactly 13 digits.")
        if values["id_type"] == "Passport" and not re.fullmatch(
            r"[A-Za-z0-9]{5,20}", values["id_number"]
        ):
            raise ClinicError("Passport must contain 5 to 20 letters or digits.")
        values["id_number"] = values["id_number"].upper()
        if parse_date(values["date_of_birth"]) > self.clock().date():
            raise ClinicError("Date of birth cannot be in the future.")
        if not phone_ok(values["phone"]) or not phone_ok(values["next_of_kin_phone"]):
            raise ClinicError("Phone numbers must be 10 digits, starting with 0.")
        if values["email"] and not re.fullmatch(
            r"[^\s@]+@[^\s@]+\.[^\s@]+", values["email"]
        ):
            raise ClinicError("Enter a valid email address or leave it blank.")
        if any(len(v) > 1000 for v in values.values()):
            raise ClinicError("A patient field is too long (maximum 1000 characters).")
        return values

    def save_patient(self, data, patient_id=None):
        self._require("Receptionist")
        values = self._patient_values(data)
        try:
            with self.db.connect(write=True) as con:
                if patient_id is None:
                    fields = list(PATIENT_FIELDS) + [
                        "created_by",
                        "updated_by",
                        "created_at",
                        "updated_at",
                    ]
                    vals = (
                        list(values.values())
                        + [self.user["user_id"]] * 2
                        + [stamp()] * 2
                    )
                    cur = con.execute(
                        f'INSERT INTO Patient({",".join(fields)}) VALUES({",".join("?" for _ in fields)})',
                        vals,
                    )
                    patient_id = cur.lastrowid
                    action = "create"
                else:
                    if not con.execute(
                        "SELECT 1 FROM Patient WHERE patient_id=?", (patient_id,)
                    ).fetchone():
                        raise ClinicError("Patient record was not found.")
                    vals = list(values.values()) + [
                        self.user["user_id"],
                        stamp(),
                        patient_id,
                    ]
                    con.execute(
                        "UPDATE Patient SET "
                        + ",".join(f"{f}=?" for f in PATIENT_FIELDS)
                        + ",updated_by=?,updated_at=? WHERE patient_id=?",
                        vals,
                    )
                    action = "update"
                self._audit(con, action, "Patient", patient_id)
                return patient_id
        except sqlite3.IntegrityError:
            with self.db.connect() as con:
                existing = con.execute(
                    "SELECT patient_id FROM Patient WHERE id_number=?",
                    (values["id_number"],),
                ).fetchone()
            detail = f" Existing patient number: {existing[0]}." if existing else ""
            raise ClinicError(
                "Patient already registered or input conflicts with a database rule."
                + detail
            ) from None

    def patients(self, query=""):
        self._require("Receptionist", "Doctor", "Nurse")
        query = query.strip()
        # Escape LIKE metacharacters; use placeholders for user-supplied values.
        pattern = (
            query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        )
        with self.db.connect() as con:
            return [
                dict(r)
                for r in con.execute(
                    """SELECT patient_id,first_name,last_name,id_number,phone,date_of_birth
              FROM Patient WHERE first_name LIKE ? ESCAPE '\\' OR last_name LIKE ? ESCAPE '\\'
              OR id_number LIKE ? ESCAPE '\\' OR phone LIKE ? ESCAPE '\\'
              ORDER BY last_name,first_name LIMIT 100""",
                    (pattern,) * 4,
                )
            ]

    def patient(self, patient_id):
        self._require("Receptionist", "Doctor", "Nurse")
        with self.db.connect() as con:
            row = con.execute(
                "SELECT * FROM Patient WHERE patient_id=?", (patient_id,)
            ).fetchone()
        if not row:
            raise ClinicError("Patient record was not found.")
        return dict(row)

    def doctors(self, active_only=True):
        self._require(*ROLES)
        with self.db.connect() as con:
            sql = "SELECT doctor_id,user_id,first_name,last_name,phone,is_active FROM Doctor"
            if active_only:
                sql += " WHERE is_active=1"
            return [
                dict(r) for r in con.execute(sql + " ORDER BY last_name,first_name")
            ]

    def save_doctor(self, data, doctor_id=None):
        self._require("Admin")
        first, last, phone = [
            str(data.get(k, "")).strip() for k in ("first_name", "last_name", "phone")
        ]
        uid = data.get("user_id") or None
        active = int(bool(data.get("is_active", True)))
        if not first or not last or not phone_ok(phone):
            raise ClinicError(
                "Doctor name, surname and valid 10-digit phone are required."
            )
        try:
            with self.db.connect(write=True) as con:
                if (
                    uid
                    and not con.execute(
                        "SELECT 1 FROM User WHERE user_id=? AND role='Doctor' AND is_active=1",
                        (uid,),
                    ).fetchone()
                ):
                    raise ClinicError("Linked user must be an active Doctor account.")
                if doctor_id is None:
                    cur = con.execute(
                        "INSERT INTO Doctor(user_id,first_name,last_name,phone,is_active) VALUES(?,?,?,?,?)",
                        (uid, first, last, phone, active),
                    )
                    doctor_id = cur.lastrowid
                else:
                    if not con.execute(
                        "SELECT 1 FROM Doctor WHERE doctor_id=?", (doctor_id,)
                    ).fetchone():
                        raise ClinicError("Doctor not found.")
                    con.execute(
                        "UPDATE Doctor SET user_id=?,first_name=?,last_name=?,phone=?,is_active=? WHERE doctor_id=?",
                        (uid, first, last, phone, active, doctor_id),
                    )
                self._audit(con, "save", "Doctor", doctor_id)
                return doctor_id
        except sqlite3.IntegrityError:
            raise ClinicError("This user is already linked to a doctor.") from None

    def schedule(self, doctor_id):
        self._require(*ROLES)
        with self.db.connect() as con:
            return [
                dict(r)
                for r in con.execute(
                    "SELECT * FROM DoctorSchedule WHERE doctor_id=? ORDER BY day_of_week",
                    (doctor_id,),
                )
            ]

    def save_schedule(
        self, doctor_id, day_of_week, start_time, end_time, slot_minutes=15
    ):
        self._require("Admin")
        start, end = minutes(start_time), minutes(end_time)
        try:
            day, duration = int(day_of_week), int(slot_minutes)
        except (ValueError, TypeError):
            raise ClinicError(
                "Weekday and slot duration must be whole numbers."
            ) from None
        if not 0 <= day <= 6 or not 5 <= duration <= 120 or end <= start:
            raise ClinicError(
                "Use weekday 0–6, duration 5–120 minutes, and end time after start time."
            )
        with self.db.connect(write=True) as con:
            if not con.execute(
                "SELECT 1 FROM Doctor WHERE doctor_id=?", (doctor_id,)
            ).fetchone():
                raise ClinicError("Doctor not found.")
            con.execute(
                """INSERT INTO DoctorSchedule(doctor_id,day_of_week,start_time,end_time,slot_minutes) VALUES(?,?,?,?,?)
             ON CONFLICT(doctor_id,day_of_week) DO UPDATE SET start_time=excluded.start_time,end_time=excluded.end_time,slot_minutes=excluded.slot_minutes""",
                (doctor_id, day, start_time, end_time, duration),
            )
            self._audit(con, "schedule", "Doctor", doctor_id)

    def unavailability(self, doctor_id):
        self._require("Admin")
        with self.db.connect() as con:
            return [
                dict(r)
                for r in con.execute(
                    "SELECT * FROM DoctorUnavailability WHERE doctor_id=? ORDER BY date",
                    (doctor_id,),
                )
            ]

    def set_unavailable(self, doctor_id, day, reason):
        self._require("Admin")
        parse_date(day)
        if not reason.strip():
            raise ClinicError("An unavailability reason is required.")
        with self.db.connect(write=True) as con:
            if not con.execute(
                "SELECT 1 FROM Doctor WHERE doctor_id=?", (doctor_id,)
            ).fetchone():
                raise ClinicError("Doctor not found.")
            if con.execute(
                "SELECT 1 FROM Appointment WHERE doctor_id=? AND date=? AND status IN ('Booked','Checked-in')",
                (doctor_id, day),
            ).fetchone():
                raise ClinicError(
                    "Reschedule or cancel existing appointments before marking this day unavailable."
                )
            con.execute(
                """INSERT INTO DoctorUnavailability(doctor_id,date,reason) VALUES(?,?,?)
             ON CONFLICT(doctor_id,date) DO UPDATE SET reason=excluded.reason""",
                (doctor_id, day, reason.strip()),
            )
            self._audit(con, "unavailable", "Doctor", doctor_id)

    def remove_unavailable(self, doctor_id, day):
        self._require("Admin")
        with self.db.connect(write=True) as con:
            con.execute(
                "DELETE FROM DoctorUnavailability WHERE doctor_id=? AND date=?",
                (doctor_id, day),
            )
            self._audit(con, "available", "Doctor", doctor_id)

    def _free_slots(self, con, doctor_id, day, exclude=None, patient_id=None):
        target = parse_date(day)
        if target < self.clock().date():
            return [], None
        if not con.execute(
            "SELECT 1 FROM Doctor WHERE doctor_id=? AND is_active=1", (doctor_id,)
        ).fetchone():
            return [], None
        if con.execute(
            "SELECT 1 FROM DoctorUnavailability WHERE doctor_id=? AND date=?",
            (doctor_id, day),
        ).fetchone():
            return [], None
        schedule = con.execute(
            "SELECT * FROM DoctorSchedule WHERE doctor_id=? AND day_of_week=?",
            (doctor_id, target.weekday()),
        ).fetchone()
        if not schedule:
            return [], None
        rows = con.execute(
            "SELECT * FROM Appointment WHERE date=? AND status<>'Cancelled' AND (doctor_id=? OR patient_id=?)",
            (day, doctor_id, patient_id),
        ).fetchall()
        busy = [
            (minutes(r["start_time"]), minutes(r["start_time"]) + r["duration_minutes"])
            for r in rows
            if r["appointment_id"] != exclude
        ]
        duration = schedule["slot_minutes"]
        slots = []
        for start in range(
            minutes(schedule["start_time"]),
            minutes(schedule["end_time"]) - duration + 1,
            duration,
        ):
            value = f"{start//60:02}:{start%60:02}"
            if datetime.fromisoformat(day + "T" + value) <= self.clock():
                continue
            if not any(start < end and start + duration > begin for begin, end in busy):
                slots.append(value)
        return slots, duration

    def free_slots(self, doctor_id, day, exclude=None, patient_id=None):
        self._require("Receptionist", "Admin")
        with self.db.connect() as con:
            return self._free_slots(con, doctor_id, day, exclude, patient_id)[0]

    def book(
        self, patient_id, doctor_id, day, start_time, reason="", appointment_id=None
    ):
        self._require("Receptionist", "Patient")
        if self.user["role"] == "Patient" and patient_id != self._my_patient_id():
            raise AccessDenied("You can book only for your own patient profile.")
        if len(reason) > 500:
            raise ClinicError("Booking reason must be 500 characters or fewer.")
        parse_date(day)
        minutes(start_time)
        try:
            with self.db.connect(write=True) as con:
                if not con.execute(
                    "SELECT 1 FROM Patient WHERE patient_id=?", (patient_id,)
                ).fetchone():
                    raise ClinicError("Select a registered patient.")
                if appointment_id:
                    old = con.execute(
                        "SELECT * FROM Appointment WHERE appointment_id=?",
                        (appointment_id,),
                    ).fetchone()
                    if not old or old["status"] != "Booked":
                        raise ClinicError(
                            "Only Booked appointments can be rescheduled."
                        )
                    if old["patient_id"] != patient_id:
                        raise ClinicError("Rescheduling cannot change the patient.")
                    if (
                        self.user["role"] == "Patient"
                        and datetime.fromisoformat(
                            old["date"] + "T" + old["start_time"]
                        )
                        <= self.clock()
                    ):
                        raise ClinicError(
                            "Past appointments cannot be rescheduled through the patient portal."
                        )
                slots, duration = self._free_slots(
                    con, doctor_id, day, appointment_id, patient_id
                )
                if start_time not in slots:
                    raise ClinicError(
                        "Slot unavailable, in the past or conflicting. Refresh the free slots."
                    )
                actor = self.user["user_id"]
                now = stamp()
                if appointment_id:
                    con.execute(
                        "UPDATE Appointment SET doctor_id=?,date=?,start_time=?,duration_minutes=?,reason=?,updated_by=?,updated_at=? WHERE appointment_id=?",
                        (
                            doctor_id,
                            day,
                            start_time,
                            duration,
                            reason.strip(),
                            actor,
                            now,
                            appointment_id,
                        ),
                    )
                    action = "reschedule"
                else:
                    cur = con.execute(
                        """INSERT INTO Appointment(patient_id,doctor_id,date,start_time,duration_minutes,reason,created_by,updated_by,created_at,updated_at)
                     VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (
                            patient_id,
                            doctor_id,
                            day,
                            start_time,
                            duration,
                            reason.strip(),
                            actor,
                            actor,
                            now,
                            now,
                        ),
                    )
                    appointment_id = cur.lastrowid
                    action = "book"
                self._audit(con, action, "Appointment", appointment_id)
                return appointment_id
        except sqlite3.IntegrityError:
            raise ClinicError(
                "Appointment conflict. Refresh and select a different slot."
            ) from None

    def appointments(self, day, doctor_id=None):
        self._require(*ROLES)
        parse_date(day)
        sql = """SELECT a.appointment_id,a.patient_id,a.doctor_id,a.date,a.start_time,a.status,
         p.first_name||' '||p.last_name AS patient,d.first_name||' '||d.last_name AS doctor
         FROM Appointment a JOIN Patient p USING(patient_id) JOIN Doctor d USING(doctor_id) WHERE a.date=?"""
        args = [day]
        if doctor_id:
            sql += " AND a.doctor_id=?"
            args.append(doctor_id)
        with self.db.connect() as con:
            return [
                dict(r) for r in con.execute(sql + " ORDER BY doctor,start_time", args)
            ]

    def weekly_appointments(self, day, doctor_id=None):
        """Monday–Sunday administrative schedule from the shared booking table.

        Doctors see only records assigned to their linked doctor profile.
        Admin/reception/nurses can review the clinic-wide schedule.
        """
        self._require(*ROLES)
        target = parse_date(day)
        monday = target - timedelta(days=target.weekday())
        end = monday + timedelta(days=7)
        sql = """SELECT a.appointment_id,a.patient_id,a.doctor_id,a.date,
            a.start_time,a.duration_minutes,a.status,a.reason,
            p.first_name||' '||p.last_name AS patient,
            d.first_name||' '||d.last_name AS doctor
            FROM Appointment a JOIN Patient p USING(patient_id)
            JOIN Doctor d USING(doctor_id) WHERE a.date>=? AND a.date<?"""
        args = [monday.isoformat(), end.isoformat()]
        if self.user["role"] == "Doctor":
            sql += " AND d.user_id=?"
            args.append(self.user["user_id"])
        if doctor_id is not None:
            sql += " AND a.doctor_id=?"
            args.append(doctor_id)
        with self.db.connect() as con:
            return [dict(row) for row in con.execute(
                sql + " ORDER BY a.date,a.start_time,a.doctor_id,a.appointment_id", args
            )]

    def next_staff_appointment(self, doctor_id=None):
        """Find the next upcoming booking, even outside the displayed week."""
        self._require(*ROLES)
        now = self.clock()
        sql = """SELECT a.appointment_id,a.date,a.start_time,
            p.first_name||' '||p.last_name AS patient,
            d.first_name||' '||d.last_name AS doctor
            FROM Appointment a JOIN Patient p USING(patient_id)
            JOIN Doctor d USING(doctor_id)
            WHERE (a.date>? OR (a.date=? AND a.start_time>=?))
            AND a.status IN ('Booked','Checked-in')"""
        args = [now.date().isoformat(), now.date().isoformat(), now.strftime("%H:%M")]
        if self.user["role"] == "Doctor":
            sql += " AND d.user_id=?"
            args.append(self.user["user_id"])
        if doctor_id is not None:
            sql += " AND a.doctor_id=?"
            args.append(doctor_id)
        with self.db.connect() as con:
            row = con.execute(sql + " ORDER BY a.date,a.start_time,a.appointment_id LIMIT 1", args).fetchone()
        return dict(row) if row else None

    def appointment(self, appointment_id):
        """Return administrative details for rescheduling an existing appointment."""
        self._require("Receptionist")
        with self.db.connect() as con:
            row = con.execute(
                "SELECT * FROM Appointment WHERE appointment_id=?", (appointment_id,)
            ).fetchone()
        if row is None:
            raise ClinicError("Appointment not found.")
        return dict(row)

    def set_status(self, appointment_id, status):
        self._require("Receptionist", "Doctor", "Nurse")
        with self.db.connect(write=True) as con:
            row = con.execute(
                "SELECT * FROM Appointment WHERE appointment_id=?", (appointment_id,)
            ).fetchone()
            if not row:
                raise ClinicError("Appointment not found.")
            allowed = {
                "Booked": ("Checked-in", "Cancelled", "No-show"),
                "Checked-in": ("Cancelled",),
            }
            if status not in allowed.get(row["status"], ()):
                raise ClinicError(
                    "Invalid status change. Complete visits through the clinical screen."
                )
            if self.user["role"] != "Receptionist":
                raise AccessDenied(
                    "Reception handles check-in, cancellations and no-shows."
                )
            now = self.clock()
            if status == "Checked-in" and row["date"] != now.date().isoformat():
                raise ClinicError("Check-in is only available on the appointment date.")
            if (
                status == "No-show"
                and datetime.fromisoformat(row["date"] + "T" + row["start_time"]) > now
            ):
                raise ClinicError("Cannot mark a future appointment as No-show.")
            if (
                status == "Cancelled"
                and datetime.fromisoformat(row["date"] + "T" + row["start_time"]) < now
            ):
                raise ClinicError(
                    "Past appointments cannot be cancelled; use No-show where applicable."
                )
            con.execute(
                "UPDATE Appointment SET status=?,updated_by=?,updated_at=? WHERE appointment_id=?",
                (status, self.user["user_id"], stamp(), appointment_id),
            )
            self._audit(con, status, "Appointment", appointment_id)

    def record_visit(self, appointment_id, data):
        self._require("Doctor", "Nurse")
        complaint = str(data.get("complaint", "")).strip()
        follow = str(data.get("follow_up_date", "")).strip() or None
        if not complaint:
            raise ClinicError("Presenting complaint is required.")
        if follow and parse_date(follow) < self.clock().date():
            raise ClinicError("Follow-up date cannot be in the past.")
        with self.db.connect(write=True) as con:
            row = con.execute(
                "SELECT * FROM Appointment WHERE appointment_id=?", (appointment_id,)
            ).fetchone()
            if not row or row["status"] != "Checked-in":
                raise ClinicError(
                    "Select a checked-in appointment without a completed visit."
                )
            if self.user["role"] == "Doctor":
                doctor = con.execute(
                    "SELECT user_id FROM Doctor WHERE doctor_id=?", (row["doctor_id"],)
                ).fetchone()
                if doctor["user_id"] != self.user["user_id"]:
                    raise AccessDenied(
                        "Doctors may record visits only for their own appointments."
                    )
            cur = con.execute(
                """INSERT INTO Visit(appointment_id,patient_id,clinician_id,visit_date,complaint,notes,diagnosis,treatment,follow_up_date,created_at)
             VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    appointment_id,
                    row["patient_id"],
                    self.user["user_id"],
                    self.clock().date().isoformat(),
                    complaint,
                    str(data.get("notes", "")).strip(),
                    str(data.get("diagnosis", "")).strip(),
                    str(data.get("treatment", "")).strip(),
                    follow,
                    stamp(),
                ),
            )
            con.execute(
                "UPDATE Appointment SET status='Completed',updated_by=?,updated_at=? WHERE appointment_id=?",
                (self.user["user_id"], stamp(), appointment_id),
            )
            self._audit(con, "record", "Visit", cur.lastrowid)
            return cur.lastrowid

    def history(self, patient_id):
        self._require("Doctor", "Nurse")
        with self.db.connect() as con:
            return [
                dict(r)
                for r in con.execute(
                    """SELECT v.*,u.full_name AS clinician FROM Visit v JOIN User u ON u.user_id=v.clinician_id
             WHERE patient_id=? ORDER BY visit_date DESC,visit_id DESC""",
                    (patient_id,),
                )
            ]

    def summary(self, first_day, last_day):
        self._require("Admin")
        if parse_date(first_day) > parse_date(last_day):
            raise ClinicError("Start date must be before or equal to end date.")
        with self.db.connect() as con:
            return [
                dict(r)
                for r in con.execute(
                    """SELECT d.doctor_id,d.first_name||' '||d.last_name AS doctor,
             COUNT(a.appointment_id) AS appointments,
             SUM(CASE WHEN a.status='Completed' THEN 1 ELSE 0 END) AS completed_visits,
             SUM(CASE WHEN a.status='No-show' THEN 1 ELSE 0 END) AS no_shows,
             SUM(CASE WHEN a.status='Cancelled' THEN 1 ELSE 0 END) AS cancelled
             FROM Doctor d LEFT JOIN Appointment a ON a.doctor_id=d.doctor_id AND a.date BETWEEN ? AND ?
             GROUP BY d.doctor_id ORDER BY d.last_name""",
                    (first_day, last_day),
                )
            ]

    def export_csv(self, path, kind, first_day, last_day=None, doctor_id=None):
        self._require("Admin")
        if kind == "daily":
            rows = [
                r
                for r in self.appointments(first_day, doctor_id)
                if r["status"] != "Cancelled"
            ]
            fields = (
                "appointment_id",
                "date",
                "start_time",
                "doctor",
                "patient",
                "status",
            )
        elif kind == "summary":
            rows = self.summary(first_day, last_day or first_day)
            fields = (
                "doctor",
                "appointments",
                "completed_visits",
                "no_shows",
                "cancelled",
            )
        else:
            raise ClinicError("Choose daily or summary report.")

        def safe_cell(value):
            # Prevent spreadsheet formula execution when the CSV is opened in Excel.
            text = str(value)
            return (
                "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text
            )

        target = Path(path).expanduser().resolve()
        if target == self.db.path or target.suffix.lower() != ".csv":
            raise ClinicError("Choose a .csv filename, not a database or backup file.")
        # Replace a completed CSV atomically; an interrupted write keeps the old file.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                newline="",
                encoding="utf-8-sig",
                dir=target.parent,
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                writer = csv.writer(handle)
                writer.writerow(fields)
                for row in rows:
                    writer.writerow([safe_cell(row[f]) for f in fields])
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        with self.db.connect(write=True) as con:
            self._audit(con, "export_" + kind, "Report", None)
        return len(rows)

    def backup(self, path):
        self._require("Admin")
        target = Path(path).expanduser().resolve()
        if target == self.db.path:
            raise ClinicError("Choose a different file for the backup.")
        if target.exists():
            raise ClinicError(
                "Choose a new backup filename to avoid overwriting an existing backup."
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.db.connect() as con:
                dest = sqlite3.connect(str(target))
                try:
                    con.backup(dest)
                    if dest.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise ClinicError("Backup integrity check failed.")
                finally:
                    dest.close()
        except Exception:
            target.unlink(missing_ok=True)
            raise
        with self.db.connect(write=True) as con:
            self._audit(con, "backup", "Database", None)
        return str(target)

    def audit_log(self):
        self._require("Admin")
        with self.db.connect() as con:
            return [
                dict(r)
                for r in con.execute(
                    """SELECT l.audit_id,l.timestamp,u.username,l.action,l.entity,l.entity_id
             FROM AuditLog l LEFT JOIN User u USING(user_id) ORDER BY audit_id DESC LIMIT 300"""
                )
            ]

    def _my_patient_id(self):
        """Resolve ownership from the authenticated user, never from a UI field."""
        self._require("Patient")
        with self.db.connect() as con:
            row = con.execute(
                "SELECT patient_id FROM PatientPortal WHERE user_id=?",
                (self.user["user_id"],),
            ).fetchone()
        if not row:
            raise AccessDenied("Your patient profile is not linked. Contact reception.")
        return row[0]

    def issue_patient_invitation(self, patient_id):
        """Reception checks identity in person before handing over this one-use code."""
        self._require("Receptionist")
        token = secrets.token_urlsafe(24)
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.db.connect(write=True) as con:
            if not con.execute(
                "SELECT 1 FROM Patient WHERE patient_id=?", (patient_id,)
            ).fetchone():
                raise ClinicError("Select an existing patient.")
            if con.execute(
                "SELECT 1 FROM PatientPortal WHERE patient_id=?", (patient_id,)
            ).fetchone():
                raise ClinicError(
                    "This patient already has a portal account. Contact the administrator for account recovery."
                )
            con.execute(
                "DELETE FROM PatientInvitation WHERE patient_id=? AND used_at IS NULL",
                (patient_id,),
            )
            con.execute(
                "INSERT INTO PatientInvitation VALUES(?,?,?,?,NULL)",
                (
                    digest,
                    patient_id,
                    self.user["user_id"],
                    (self.clock() + timedelta(hours=24)).isoformat(timespec="seconds"),
                ),
            )
            self._audit(con, "portal_invitation", "Patient", patient_id)
        return token

    def register_patient_account(self, username, password, data=None, invitation=""):
        """Atomically sign up a new patient or redeem a clinic-issued invitation.

        Existing clinical records can only be linked by a one-use invitation;
        knowing a patient's ID or date of birth is never sufficient.
        """
        if self.user:
            raise AccessDenied("Log out before creating a patient account.")
        if self.needs_setup():
            raise ClinicError("Clinic setup is not complete. Contact reception.")
        username = username.strip()
        if not re.fullmatch(r"[A-Za-z0-9._@+\-]{3,80}", username):
            raise ClinicError("Use a username of 3–80 letters, numbers or . _ @ + -.")
        encoded = hash_password(password)
        token = invitation.strip()
        values = None if token else self._patient_values(data or {})
        if values and not values["email"]:
            raise ClinicError("An email address is required for your patient account.")
        try:
            with self.db.connect(write=True) as con:
                if token:
                    digest = hashlib.sha256(token.encode()).hexdigest()
                    invite = con.execute(
                        "SELECT * FROM PatientInvitation WHERE token_hash=? AND used_at IS NULL",
                        (digest,),
                    ).fetchone()
                    if (
                        not invite
                        or datetime.fromisoformat(invite["expires_at"]) <= self.clock()
                    ):
                        raise ClinicError(
                            "Invitation is invalid, expired or already used. Ask reception for a new code."
                        )
                    pid = invite["patient_id"]
                    profile = con.execute(
                        "SELECT first_name,last_name FROM Patient WHERE patient_id=?",
                        (pid,),
                    ).fetchone()
                    full_name = profile["first_name"] + " " + profile["last_name"]
                else:
                    full_name = values["first_name"] + " " + values["last_name"]
                cur = con.execute(
                    "INSERT INTO User(username,password_hash,full_name,role,created_at) VALUES(?,?,?,'Patient',?)",
                    (username, encoded, full_name, stamp()),
                )
                uid = cur.lastrowid
                if not token:
                    fields = list(PATIENT_FIELDS) + [
                        "created_by",
                        "updated_by",
                        "created_at",
                        "updated_at",
                    ]
                    cur = con.execute(
                        f'INSERT INTO Patient({",".join(fields)}) VALUES({",".join("?" for _ in fields)})',
                        list(values.values()) + [uid, uid, stamp(), stamp()],
                    )
                    pid = cur.lastrowid
                con.execute(
                    "INSERT INTO PatientPortal(user_id,patient_id) VALUES(?,?)",
                    (uid, pid),
                )
                if token:
                    con.execute(
                        "UPDATE PatientInvitation SET used_at=? WHERE token_hash=?",
                        (stamp(), digest),
                    )
                self._audit(con, "patient_signup", "Patient", pid, uid)
                return pid
        except sqlite3.IntegrityError:
            raise ClinicError(
                "Registration could not be completed. Use a different username, or ask reception for an invitation if you are already registered."
            ) from None

    def my_profile(self):
        pid = self._my_patient_id()
        fields = ["patient_id"] + list(PATIENT_FIELDS)
        with self.db.connect() as con:
            return dict(
                con.execute(
                    "SELECT " + ",".join(fields) + " FROM Patient WHERE patient_id=?",
                    (pid,),
                ).fetchone()
            )

    def update_my_contact(self, data):
        pid = self._my_patient_id()
        allowed = ("phone", "email", "address", "next_of_kin_name", "next_of_kin_phone")
        if set(data) - set(allowed):
            raise ClinicError(
                "Only contact and next-of-kin details can be changed here. Ask reception to correct identity details."
            )
        profile = self.my_profile()
        profile.update(data)
        values = self._patient_values(profile)
        with self.db.connect(write=True) as con:
            con.execute(
                "UPDATE Patient SET "
                + ",".join(f"{k}=?" for k in allowed)
                + ",updated_by=?,updated_at=? WHERE patient_id=?",
                [values[k] for k in allowed] + [self.user["user_id"], stamp(), pid],
            )
            self._audit(con, "patient_contact_update", "Patient", pid)

    def my_insurance(self):
        self._my_patient_id()
        with self.db.connect() as con:
            return dict(
                con.execute(
                    "SELECT insurance_provider,insurance_plan,membership_number,member_type FROM PatientPortal WHERE user_id=?",
                    (self.user["user_id"],),
                ).fetchone()
            )

    def update_my_insurance(self, data):
        pid = self._my_patient_id()
        fields = (
            "insurance_provider",
            "insurance_plan",
            "membership_number",
            "member_type",
        )
        if set(data) - set(fields):
            raise ClinicError("Unexpected insurance field.")
        values = {k: str(data.get(k, "")).strip() for k in fields}
        if any(len(v) > 200 for v in values.values()):
            raise ClinicError("Insurance fields must be 200 characters or fewer.")
        if values["member_type"] not in (
            "",
            "Principal member",
            "Dependant",
            "Self-paying",
        ):
            raise ClinicError("Choose a listed member type.")
        if (
            values["member_type"] != "Self-paying"
            and any(values.values())
            and not all(
                values[k]
                for k in ("insurance_provider", "membership_number", "member_type")
            )
        ):
            raise ClinicError(
                "Enter a provider, membership number and member type, or choose Self-paying."
            )
        if values["member_type"] == "Self-paying":
            values.update(
                insurance_provider="", insurance_plan="", membership_number=""
            )
        with self.db.connect(write=True) as con:
            con.execute(
                "UPDATE PatientPortal SET "
                + ",".join(f"{k}=?" for k in fields)
                + " WHERE user_id=?",
                list(values.values()) + [self.user["user_id"]],
            )
            self._audit(con, "patient_insurance_update", "Patient", pid)

    def portal_doctors(self):
        self._my_patient_id()
        with self.db.connect() as con:
            return [
                dict(r)
                for r in con.execute(
                    "SELECT doctor_id,first_name,last_name FROM Doctor WHERE is_active=1 ORDER BY last_name,first_name"
                )
            ]

    def my_appointments(self):
        pid = self._my_patient_id()
        with self.db.connect() as con:
            return [
                dict(r)
                for r in con.execute(
                    """SELECT a.appointment_id,a.doctor_id,a.date,a.start_time,a.status,a.reason,
                d.first_name||' '||d.last_name AS doctor FROM Appointment a JOIN Doctor d USING(doctor_id)
                WHERE a.patient_id=? ORDER BY a.date DESC,a.start_time DESC""",
                    (pid,),
                )
            ]

    def my_free_slots(self, doctor_id, day, appointment_id=None):
        pid = self._my_patient_id()
        with self.db.connect() as con:
            if appointment_id:
                old = con.execute(
                    "SELECT 1 FROM Appointment WHERE appointment_id=? AND patient_id=? AND status='Booked'",
                    (appointment_id, pid),
                ).fetchone()
                if not old:
                    raise AccessDenied("Appointment is unavailable for your account.")
            return self._free_slots(con, doctor_id, day, appointment_id, pid)[0]

    def book_for_me(self, doctor_id, day, start_time, reason="", appointment_id=None):
        pid = self._my_patient_id()
        return self.book(pid, doctor_id, day, start_time, reason, appointment_id)

    def cancel_my_appointment(self, appointment_id):
        pid = self._my_patient_id()
        with self.db.connect(write=True) as con:
            row = con.execute(
                "SELECT * FROM Appointment WHERE appointment_id=? AND patient_id=?",
                (appointment_id, pid),
            ).fetchone()
            if not row:
                raise AccessDenied("Appointment is unavailable for your account.")
            if (
                row["status"] != "Booked"
                or datetime.fromisoformat(row["date"] + "T" + row["start_time"])
                <= self.clock()
            ):
                raise ClinicError(
                    "Only a future Booked appointment can be cancelled here. Contact reception for other changes."
                )
            con.execute(
                "UPDATE Appointment SET status='Cancelled',updated_by=?,updated_at=? WHERE appointment_id=?",
                (self.user["user_id"], stamp(), appointment_id),
            )
            self._audit(con, "patient_cancel", "Appointment", appointment_id)

    def my_visit_summaries(self):
        pid = self._my_patient_id()
        with self.db.connect() as con:
            return [
                dict(r)
                for r in con.execute(
                    """SELECT v.visit_date,u.full_name AS clinician,v.diagnosis,v.treatment,v.follow_up_date
                FROM Visit v JOIN User u ON u.user_id=v.clinician_id WHERE v.patient_id=?
                ORDER BY v.visit_date DESC,v.visit_id DESC""",
                    (pid,),
                )
            ]
