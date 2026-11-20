"""Patient ownership, self-service, migration and shared booking regression tests."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import sqlite3
import tempfile
import time
import unittest
from sunrise.database import Database, SCHEMA
from sunrise.demo import initialise_demo, DEMO_PASSWORD
from sunrise.services import ClinicService, ClinicError, AccessDenied

NOW = datetime(2030, 1, 7, 8, 0)
DAY = "2030-01-07"


def profile(number="OTHER000002"):
    return dict(
        first_name="Lerato",
        last_name="Nkosi",
        id_type="Passport",
        id_number=number,
        date_of_birth="1996-04-18",
        gender="Female",
        phone="0100000004",
        email="lerato@example.com",
        address="Example address",
        next_of_kin_name="Example Relative",
        next_of_kin_phone="0100000005",
    )


class PatientPortalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name) / "base.sqlite"
        initialise_demo(cls.base, clock=lambda: NOW)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "clinic.sqlite"
        import shutil

        shutil.copy2(self.base, self.path)
        self.s = ClinicService(self.path, clock=lambda: NOW)

    def tearDown(self):
        self.tempdir.cleanup()

    def signup_other(self):
        self.s.logout()
        return self.s.register_patient_account("lerato", DEMO_PASSWORD, profile())

    def count(self, table):
        with self.s.db.connect() as con:
            return con.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]

    def test_P01_new_patient_signup_hashes_password_and_persists(self):
        pid = self.signup_other()
        self.s.login("LERATO", DEMO_PASSWORD)
        self.assertEqual(self.s.my_profile()["patient_id"], pid)
        with self.s.db.connect() as con:
            encoded = con.execute(
                "SELECT password_hash FROM User WHERE username='lerato'"
            ).fetchone()[0]
        self.assertNotIn(DEMO_PASSWORD, encoded)
        other = ClinicService(self.path)
        self.assertEqual(other.login("lerato", DEMO_PASSWORD)["role"], "Patient")

    def test_P02_validation_and_duplicate_identity_rollback_whole_signup(self):
        before = self.count("User")
        with self.assertRaises(ClinicError):
            self.s.register_patient_account("bad", DEMO_PASSWORD, {})
        data = profile("DEMO000001")
        with self.assertRaises(ClinicError):
            self.s.register_patient_account("claim", DEMO_PASSWORD, data)
        self.assertEqual(self.count("User"), before)
        self.assertEqual(self.count("PatientPortal"), 1)

    def test_P03_private_lists_and_staff_services_are_denied(self):
        self.signup_other()
        self.s.login("lerato", DEMO_PASSWORD)
        self.assertEqual(self.s.my_appointments(), [])
        for action in [
            lambda: self.s.patient(1),
            self.s.patients,
            lambda: self.s.history(1),
            lambda: self.s.appointments(DAY),
            self.s.users,
            self.s.audit_log,
            lambda: self.s.summary(DAY, DAY),
            lambda: self.s.record_visit(1, {"complaint": "no"}),
            self.s.doctors,
        ]:
            with self.subTest(action=action):
                with self.assertRaises(AccessDenied):
                    action()
        self.assertEqual(
            set(self.s.portal_doctors()[0]), {"doctor_id", "first_name", "last_name"}
        )

    def test_P04_patient_booking_appears_in_reception_list(self):
        pid = self.signup_other()
        self.s.login("lerato", DEMO_PASSWORD)
        slots = self.s.my_free_slots(1, DAY)
        self.assertNotIn("09:00", slots)
        aid = self.s.book_for_me(1, DAY, "10:00", "Routine visit")
        self.s.login("reception", DEMO_PASSWORD)
        row = next(r for r in self.s.appointments(DAY) if r["appointment_id"] == aid)
        self.assertEqual(row["patient_id"], pid)
        self.assertEqual(row["status"], "Booked")

    def test_P05_reschedule_cancel_and_slot_release(self):
        self.s.login("patient", DEMO_PASSWORD)
        self.s.book_for_me(1, DAY, "10:00", "Routine", 1)
        self.assertEqual(self.s.my_appointments()[0]["start_time"], "10:00")
        self.s.cancel_my_appointment(1)
        self.assertEqual(self.s.my_appointments()[0]["status"], "Cancelled")
        self.assertIn("10:00", self.s.my_free_slots(1, DAY))

    def test_P06_cross_patient_ids_cannot_book_reschedule_cancel_or_exclude(self):
        self.signup_other()
        self.s.login("lerato", DEMO_PASSWORD)
        for action in [
            lambda: self.s.book(1, 1, DAY, "11:00"),
            lambda: self.s.book_for_me(1, DAY, "11:00", "", 1),
            lambda: self.s.cancel_my_appointment(1),
            lambda: self.s.my_free_slots(1, DAY, 1),
        ]:
            with self.subTest(action=action):
                with self.assertRaises(ClinicError):
                    action()
        self.s.login("reception", DEMO_PASSWORD)
        self.assertEqual(self.s.appointment(1)["start_time"], "09:00")

    def test_P07_identity_edits_and_privilege_change_are_blocked(self):
        self.s.login("patient", DEMO_PASSWORD)
        with self.assertRaises(ClinicError):
            self.s.update_my_contact({"patient_id": 2, "first_name": "Changed"})
        self.s.login("admin", DEMO_PASSWORD)
        uid = next(r["user_id"] for r in self.s.users() if r["username"] == "patient")
        with self.assertRaises(ClinicError):
            self.s.change_user(uid, role="Admin")
        self.s.change_user(uid, active=0)
        with self.assertRaises(AccessDenied):
            self.s.login("patient", DEMO_PASSWORD)

    def test_P08_contact_and_insurance_persist_only_for_owner(self):
        self.signup_other()
        self.s.login("lerato", DEMO_PASSWORD)
        self.s.update_my_contact(
            {"phone": "0100000008", "address": "Updated own address"}
        )
        self.s.update_my_insurance(
            dict(
                insurance_provider="Example Health",
                insurance_plan="Demo plan",
                membership_number="1234564821",
                member_type="Principal member",
            )
        )
        other = ClinicService(self.path)
        other.login("lerato", DEMO_PASSWORD)
        self.assertEqual(other.my_profile()["phone"], "0100000008")
        self.assertEqual(other.my_insurance()["membership_number"], "1234564821")
        other.login("patient", DEMO_PASSWORD)
        self.assertEqual(other.my_insurance()["membership_number"], "")
        self.assertEqual(other.my_profile()["phone"], "0100000002")

    def test_P09_invitation_is_hashed_one_use_and_links_existing_record(self):
        self.s.login("reception", DEMO_PASSWORD)
        pid = self.s.save_patient(profile())
        token = self.s.issue_patient_invitation(pid)
        with self.s.db.connect() as con:
            stored = con.execute("SELECT token_hash FROM PatientInvitation").fetchone()[
                0
            ]
        self.assertEqual(stored, hashlib.sha256(token.encode()).hexdigest())
        self.assertNotEqual(token, stored)
        self.s.logout()
        self.s.register_patient_account("invited", DEMO_PASSWORD, invitation=token)
        with self.assertRaises(ClinicError):
            self.s.register_patient_account("replay", DEMO_PASSWORD, invitation=token)
        self.s.login("invited", DEMO_PASSWORD)
        self.assertEqual(self.s.my_profile()["patient_id"], pid)

    def test_P10_expired_and_replaced_invites_are_rejected(self):
        self.s.login("reception", DEMO_PASSWORD)
        pid = self.s.save_patient(profile())
        old = self.s.issue_patient_invitation(pid)
        new = self.s.issue_patient_invitation(pid)
        self.s.logout()
        with self.assertRaises(ClinicError):
            self.s.register_patient_account("expired", DEMO_PASSWORD, invitation=old)
        self.s.clock = lambda: NOW + timedelta(hours=25)
        with self.assertRaises(ClinicError):
            self.s.register_patient_account("expired", DEMO_PASSWORD, invitation=new)
        self.assertEqual(self.count("PatientPortal"), 1)

    def test_P11_patient_cannot_issue_invitation_and_linked_record_rejected(self):
        self.s.login("patient", DEMO_PASSWORD)
        with self.assertRaises(AccessDenied):
            self.s.issue_patient_invitation(1)
        self.s.login("reception", DEMO_PASSWORD)
        with self.assertRaises(ClinicError):
            self.s.issue_patient_invitation(1)

    def test_P12_visit_summary_has_own_public_fields_only(self):
        self.s.login("reception", DEMO_PASSWORD)
        self.s.set_status(1, "Checked-in")
        self.s.login("doctor", DEMO_PASSWORD)
        self.s.record_visit(
            1,
            {
                "complaint": "Fictional complaint",
                "notes": "Internal clinic note",
                "diagnosis": "Example diagnosis",
                "treatment": "Example treatment",
                "follow_up_date": "2030-01-08",
            },
        )
        self.s.login("patient", DEMO_PASSWORD)
        row = self.s.my_visit_summaries()[0]
        self.assertEqual(row["diagnosis"], "Example diagnosis")
        self.assertNotIn("notes", row)
        self.signup_other()
        self.s.login("lerato", DEMO_PASSWORD)
        self.assertEqual(self.s.my_visit_summaries(), [])

    def test_P13_lockout_session_timeout_and_account_recovery(self):
        for _ in range(5):
            with self.assertRaises(AccessDenied):
                self.s.login("patient", "wrong")
        with self.assertRaises(AccessDenied):
            self.s.login("patient", DEMO_PASSWORD)
        self.s.login("admin", DEMO_PASSWORD)
        uid = next(r["user_id"] for r in self.s.users() if r["username"] == "patient")
        self.s.change_user(uid, unlock=True)
        self.s.login("patient", DEMO_PASSWORD)
        self.s.last_activity = time.monotonic() - 901
        with self.assertRaises(AccessDenied):
            self.s.my_profile()
        self.assertIsNone(self.s.user)

    def test_P14_past_and_checked_in_mutations_denied(self):
        self.s.login("reception", DEMO_PASSWORD)
        self.s.set_status(1, "Checked-in")
        self.s.login("patient", DEMO_PASSWORD)
        with self.assertRaises(ClinicError):
            self.s.cancel_my_appointment(1)
        with self.assertRaises(ClinicError):
            self.s.book_for_me(1, DAY, "10:00", "", 1)
        self.s.login("reception", DEMO_PASSWORD)
        aid = self.s.book(1, 1, DAY, "10:00")
        self.s.clock = lambda: datetime(2030, 1, 7, 11, 0)
        self.s.login("patient", DEMO_PASSWORD)
        with self.assertRaises(ClinicError):
            self.s.cancel_my_appointment(aid)
        with self.assertRaises(ClinicError):
            self.s.book_for_me(1, "2030-01-08", "10:00", "", aid)

    def test_P15_patient_and_reception_compete_for_same_slot(self):
        self.signup_other()

        def attempt(username):
            s = ClinicService(self.path, clock=lambda: NOW)
            s.login(username, DEMO_PASSWORD)
            try:
                return (
                    s.book_for_me(1, DAY, "11:00")
                    if username == "lerato"
                    else s.book(1, 1, DAY, "11:00")
                )
            except ClinicError:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ["lerato", "reception"]))
        self.assertEqual(sum(r is not None for r in results), 1)

    def test_P16_migrate_v1_preserves_records_hashes_and_foreign_keys(self):
        legacy = Path(self.tempdir.name) / "legacy.sqlite"
        old_schema = (
            SCHEMA.split("CREATE TABLE IF NOT EXISTS PatientPortal")[0].replace(
                ",'Patient'", ""
            )
            + "PRAGMA user_version=1;"
        )
        con = sqlite3.connect(legacy)
        con.executescript(old_schema)
        con.execute("ATTACH DATABASE ? AS old", (str(self.path),))
        for table in [
            "User",
            "Patient",
            "Doctor",
            "DoctorSchedule",
            "DoctorUnavailability",
            "Appointment",
            "Visit",
            "AuditLog",
        ]:
            # The fixture has a v2 demo patient user; copy only the original staff users.
            where = " WHERE role<>'Patient'" if table == "User" else ""
            con.execute(f"INSERT INTO {table} SELECT * FROM old.{table}" + where)
        old_hash = con.execute(
            "SELECT password_hash FROM User WHERE username='admin'"
        ).fetchone()[0]
        con.commit()
        con.close()
        upgraded = ClinicService(legacy, clock=lambda: NOW)
        snapshot = legacy.with_name("legacy.before-v2.sqlite")
        with sqlite3.connect(snapshot) as old:
            self.assertEqual(old.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertEqual(
                old.execute("SELECT COUNT(*) FROM Appointment").fetchone()[0], 1
            )
        upgraded.login("reception", DEMO_PASSWORD)
        self.assertEqual(len(upgraded.appointments(DAY)), 1)
        with upgraded.db.connect() as con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 2)
            self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(
                con.execute(
                    "SELECT password_hash FROM User WHERE username='admin'"
                ).fetchone()[0],
                old_hash,
            )
        token = upgraded.issue_patient_invitation(1)
        upgraded.logout()
        upgraded.register_patient_account("migrated", DEMO_PASSWORD, invitation=token)
        upgraded.login("migrated", DEMO_PASSWORD)
        self.assertEqual(upgraded.my_appointments()[0]["appointment_id"], 1)
        Database(legacy)  # A second open is idempotent.

    def test_P17_no_patient_signup_before_clinic_setup(self):
        fresh = ClinicService(
            Path(self.tempdir.name) / "fresh.sqlite", clock=lambda: NOW
        )
        with self.assertRaises(ClinicError):
            fresh.register_patient_account("firstpatient", DEMO_PASSWORD, profile())
        self.assertTrue(fresh.needs_setup())

    def test_P18_insurance_validation_and_self_paying_clear_previous_values(self):
        self.s.login("patient", DEMO_PASSWORD)
        with self.assertRaises(ClinicError):
            self.s.update_my_insurance({"insurance_provider": "Example"})
        self.s.update_my_insurance(
            {
                "insurance_provider": "Example",
                "membership_number": "123456",
                "member_type": "Principal member",
            }
        )
        self.s.update_my_insurance({"member_type": "Self-paying"})
        self.assertEqual(self.s.my_insurance()["membership_number"], "")
