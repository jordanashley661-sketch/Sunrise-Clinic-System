"""Deterministic service and SQLite integration tests using fictional fixtures."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import csv
import sqlite3
import tempfile
import time
import unittest

from sunrise.services import AccessDenied, ClinicError, ClinicService
from sunrise.security import hash_password, verify_password

PASSWORD = "SunriseTest!2026"
NOW = datetime(2030, 1, 7, 8, 0)
DAY = "2030-01-07"
METRICS = {}


def patient_data(number="TEST0001"):
    return dict(
        first_name="Test",
        last_name="Patient",
        id_type="Passport",
        id_number=number,
        date_of_birth="1990-01-01",
        phone="0100000001",
        email="",
        address="Fictional address",
        next_of_kin_name="Test Relative",
        next_of_kin_phone="0100000002",
    )


class ClinicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_dir = tempfile.TemporaryDirectory()
        cls.base = Path(cls.base_dir.name) / "base.sqlite"
        s = ClinicService(cls.base, clock=lambda: NOW)
        s.bootstrap_admin("admin", "Test Admin", PASSWORD)
        s.login("admin", PASSWORD)
        cls.reception = s.create_user(
            "reception", "Test Reception", "Receptionist", PASSWORD
        )
        cls.doctor_user = s.create_user("doctor", "Test Doctor", "Doctor", PASSWORD)
        cls.nurse = s.create_user("nurse", "Test Nurse", "Nurse", PASSWORD)
        cls.did = s.save_doctor(
            dict(
                first_name="Test",
                last_name="Doctor",
                phone="0100000003",
                user_id=cls.doctor_user,
            )
        )
        for day in range(7):
            s.save_schedule(cls.did, day, "08:00", "16:00", 15)
        s.login("reception", PASSWORD)
        cls.pid = s.save_patient(patient_data())

    @classmethod
    def tearDownClass(cls):
        cls.base_dir.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "clinic.sqlite"
        source = sqlite3.connect(self.base)
        dest = sqlite3.connect(self.path)
        source.backup(dest)
        source.close()
        dest.close()
        self.s = ClinicService(self.path, clock=lambda: NOW)
        self.s.login("reception", PASSWORD)

    def tearDown(self):
        self.tmp.cleanup()

    def admin(self):
        self.s.login("admin", PASSWORD)

    def doctor(self):
        self.s.login("doctor", PASSWORD)

    def book(self, start="09:00"):
        return self.s.book(self.pid, self.did, DAY, start)

    def test_T01_password_salt_and_verification(self):
        a, b = hash_password(PASSWORD), hash_password(PASSWORD)
        self.assertNotEqual(a, b)
        self.assertNotIn(PASSWORD, a)
        self.assertTrue(verify_password(PASSWORD, a))
        self.assertFalse(verify_password("wrong", a))

    def test_T02_failed_login_lockout_and_admin_unlock(self):
        for _ in range(5):
            with self.assertRaises(AccessDenied):
                self.s.login("reception", "wrong")
        with self.assertRaisesRegex(AccessDenied, "locked"):
            self.s.login("reception", PASSWORD)
        self.admin()
        self.s.change_user(self.reception, unlock=True)
        self.assertEqual(self.s.login("reception", PASSWORD)["role"], "Receptionist")

    def test_T03_deactivation_invalidates_existing_session(self):
        other = ClinicService(self.path, clock=lambda: NOW)
        other.login("reception", PASSWORD)
        self.admin()
        self.s.change_user(self.reception, active=False)
        with self.assertRaises(AccessDenied):
            other.patients()

    def test_T04_session_timeout(self):
        self.s.last_activity = time.monotonic() - 901
        with self.assertRaisesRegex(AccessDenied, "expired"):
            self.s.patients()
        self.assertIsNone(self.s.user)

    def test_T05_reception_denied_clinical_history_and_visit_write(self):
        with self.assertRaises(AccessDenied):
            self.s.history(self.pid)
        with self.assertRaises(AccessDenied):
            self.s.record_visit(1, {"complaint": "Example"})

    def test_T06_register_valid_sa_id_format(self):
        d = patient_data("9001015009087")
        d["id_type"] = "SA ID"
        pid = self.s.save_patient(d)
        self.assertEqual(self.s.patient(pid)["id_number"], d["id_number"])

    def test_T07_invalid_patient_inputs_do_not_save(self):
        for field, value in [
            ("first_name", ""),
            ("id_number", "ABC"),
            ("phone", "123"),
            ("date_of_birth", "2031-01-01"),
            ("next_of_kin_phone", "x"),
        ]:
            d = patient_data("9001015009087")
            d["id_type"] = "SA ID"
            d[field] = value
            with self.assertRaises(ClinicError):
                self.s.save_patient(d)
        self.assertEqual(len(self.s.patients()), 1)

    def test_T08_duplicate_id_returns_existing_number(self):
        with self.assertRaisesRegex(ClinicError, "Existing patient number"):
            self.s.save_patient(patient_data())
        self.assertEqual(len(self.s.patients()), 1)

    def test_T09_search_and_update(self):
        for query in ["Test", "Patient", "TEST0001", "0100000001"]:
            self.assertEqual(len(self.s.patients(query)), 1)
        d = patient_data()
        d["address"] = "Updated fictional address"
        self.s.save_patient(d, self.pid)
        self.assertEqual(self.s.patient(self.pid)["address"], d["address"])

    def test_T10_sql_injection_is_data(self):
        self.assertEqual(self.s.patients("' OR 1=1 --"), [])
        self.assertEqual(len(self.s.patients()), 1)

    def test_T11_admin_doctor_schedule(self):
        self.admin()
        self.s.save_schedule(self.did, 0, "10:00", "12:00", 30)
        slots = self.s.free_slots(self.did, DAY)
        self.assertEqual(slots, ["10:00", "10:30", "11:00", "11:30"])
        with self.assertRaises(ClinicError):
            self.s.save_schedule(self.did, 0, "16:00", "08:00")

    def test_T12_unavailable_day(self):
        self.admin()
        self.s.set_unavailable(self.did, DAY, "Fictional leave")
        self.assertEqual(self.s.free_slots(self.did, DAY), [])
        self.s.remove_unavailable(self.did, DAY)
        self.assertIn("09:00", self.s.free_slots(self.did, DAY))

    def test_T13_valid_booking_persists(self):
        aid = self.book()
        rows = self.s.appointments(DAY)
        self.assertEqual(rows[0]["appointment_id"], aid)
        self.assertEqual(rows[0]["status"], "Booked")

    def test_T14_duplicate_doctor_slot_blocked(self):
        self.book()
        pid = self.s.save_patient(patient_data("TEST0002"))
        with self.assertRaises(ClinicError):
            self.s.book(pid, self.did, DAY, "09:00")
        self.assertEqual(len(self.s.appointments(DAY)), 1)

    def test_T15_past_outside_hours_and_off_grid_blocked(self):
        for day, slot in [
            ("2030-01-06", "09:00"),
            (DAY, "07:00"),
            (DAY, "16:00"),
            (DAY, "09:07"),
            (DAY, "07:45"),
        ]:
            with self.assertRaises(ClinicError):
                self.s.book(self.pid, self.did, day, slot)
        self.assertEqual(self.s.appointments(DAY), [])

    def test_T16_cancellation_releases_slot(self):
        aid = self.book()
        self.s.set_status(aid, "Cancelled")
        self.book()
        self.assertEqual(len(self.s.appointments(DAY)), 2)

    def test_T17_reschedule_preserves_original_on_conflict(self):
        a = self.book("09:00")
        self.book("10:00")
        with self.assertRaises(ClinicError):
            self.s.book(self.pid, self.did, DAY, "10:00", appointment_id=a)
        self.assertEqual(
            [r["start_time"] for r in self.s.appointments(DAY)], ["09:00", "10:00"]
        )
        self.s.book(self.pid, self.did, DAY, "11:00", appointment_id=a)
        self.assertIn("11:00", [r["start_time"] for r in self.s.appointments(DAY)])

    def test_T18_patient_cannot_overlap_across_doctors(self):
        self.book()
        self.admin()
        did = self.s.save_doctor(
            dict(first_name="Other", last_name="Doctor", phone="0100000004")
        )
        self.s.save_schedule(did, 0, "08:00", "16:00", 15)
        self.s.login("reception", PASSWORD)
        with self.assertRaises(ClinicError):
            self.s.book(self.pid, did, DAY, "09:00")

    def test_T19_concurrent_booking_only_one_succeeds(self):
        services = [ClinicService(self.path, clock=lambda: NOW) for _ in range(2)]
        for s in services:
            s.login("reception", PASSWORD)

        def attempt(s):
            try:
                s.book(self.pid, self.did, DAY, "09:00")
                return "booked"
            except ClinicError:
                return "rejected"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, services))
        self.assertEqual(sorted(results), ["booked", "rejected"])
        self.assertEqual(len(self.s.appointments(DAY)), 1)

    def test_T20_database_unique_constraint(self):
        self.book()
        with self.assertRaises(sqlite3.IntegrityError):
            with self.s.db.connect(write=True) as con:
                con.execute(
                    """INSERT INTO Appointment(patient_id,doctor_id,date,start_time,duration_minutes,created_by,updated_by,created_at,updated_at)
                 SELECT patient_id,doctor_id,date,start_time,duration_minutes,created_by,updated_by,created_at,updated_at FROM Appointment"""
                )

    def test_T21_record_visit_completes_appointment(self):
        aid = self.book()
        self.s.set_status(aid, "Checked-in")
        self.doctor()
        self.s.record_visit(
            aid,
            dict(
                complaint="Fictional complaint",
                notes="Fictional note",
                diagnosis="Demo",
                treatment="Demo",
                follow_up_date="2030-01-08",
            ),
        )
        self.assertEqual(self.s.appointments(DAY)[0]["status"], "Completed")
        history = self.s.history(self.pid)
        self.assertEqual(history[0]["notes"], "Fictional note")
        with self.assertRaises(ClinicError):
            self.s.record_visit(aid, {"complaint": "Duplicate"})

    def test_T22_invalid_visit_does_not_complete_appointment(self):
        aid = self.book()
        self.s.set_status(aid, "Checked-in")
        self.doctor()
        with self.assertRaises(ClinicError):
            self.s.record_visit(aid, {"complaint": ""})
        self.assertEqual(self.s.appointments(DAY)[0]["status"], "Checked-in")
        self.assertEqual(self.s.history(self.pid), [])

    def test_T23_doctor_assignment_enforced(self):
        aid = self.book()
        self.s.set_status(aid, "Checked-in")
        self.admin()
        self.s.create_user("otherdoc", "Other Doctor", "Doctor", PASSWORD)
        self.s.login("otherdoc", PASSWORD)
        with self.assertRaises(AccessDenied):
            self.s.record_visit(aid, {"complaint": "Example"})

    def test_T24_nurse_visit_and_history_order(self):
        a = self.book("09:00")
        b = self.book("10:00")
        self.s.set_status(a, "Checked-in")
        self.s.set_status(b, "Checked-in")
        self.s.login("nurse", PASSWORD)
        self.s.record_visit(a, {"complaint": "First"})
        self.s.record_visit(b, {"complaint": "Second"})
        self.assertEqual(
            [v["complaint"] for v in self.s.history(self.pid)], ["Second", "First"]
        )

    def test_T25_summary_counts_and_daily_export(self):
        a = self.book("09:00")
        b = self.book("10:00")
        self.s.set_status(a, "Checked-in")
        self.s.set_status(b, "Cancelled")
        self.doctor()
        self.s.record_visit(a, {"complaint": "Fictional"})
        self.admin()
        row = self.s.summary(DAY, DAY)[0]
        self.assertEqual(
            (row["appointments"], row["completed_visits"], row["cancelled"]), (2, 1, 1)
        )
        path = Path(self.tmp.name) / "daily.csv"
        self.assertEqual(self.s.export_csv(path, "daily", DAY), 1)
        with path.open(encoding="utf-8-sig") as f:
            self.assertEqual(len(list(csv.DictReader(f))), 1)

    def test_T26_report_permissions(self):
        with self.assertRaises(AccessDenied):
            self.s.summary(DAY, DAY)
        with self.assertRaises(AccessDenied):
            self.s.export_csv(Path(self.tmp.name) / "out.csv", "daily", DAY)

    def test_T27_backup_restore_and_integrity(self):
        self.book()
        self.admin()
        path = Path(self.tmp.name) / "backup.sqlite"
        self.s.backup(path)
        restored = ClinicService(path, clock=lambda: NOW)
        restored.login("reception", PASSWORD)
        self.assertEqual(len(restored.appointments(DAY)), 1)
        with restored.db.connect() as con:
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        with self.assertRaises(ClinicError):
            self.s.backup(self.path)

    def test_T28_audit_records_changes_without_notes(self):
        self.book()
        self.admin()
        entries = self.s.audit_log()
        self.assertTrue(
            any(r["action"] == "book" and r["entity"] == "Appointment" for r in entries)
        )
        self.assertNotIn("notes", entries[0])

    def test_T29_last_active_admin_protected(self):
        self.admin()
        with self.assertRaises(ClinicError):
            self.s.change_user(self.s.user["user_id"], active=False)

    def test_T30_unavailability_rejects_existing_bookings(self):
        self.book()
        self.admin()
        with self.assertRaises(ClinicError):
            self.s.set_unavailable(self.did, DAY, "Leave")

    def test_T31_transaction_rolls_back_partial_write(self):
        with self.assertRaises(RuntimeError):
            with self.s.db.connect(write=True) as con:
                con.execute(
                    "UPDATE Patient SET last_name='SHOULD_ROLL_BACK' WHERE patient_id=?",
                    (self.pid,),
                )
                raise RuntimeError("Simulated interruption")
        self.assertEqual(self.s.patient(self.pid)["last_name"], "Patient")

    def test_T32_inactive_doctor_not_bookable(self):
        self.admin()
        self.s.save_doctor(
            dict(
                first_name="Test",
                last_name="Doctor",
                phone="0100000003",
                user_id=self.doctor_user,
                is_active=False,
            ),
            self.did,
        )
        self.s.login("reception", PASSWORD)
        with self.assertRaises(ClinicError):
            self.book()

    def test_T33_invalid_status_and_future_no_show(self):
        aid = self.book()
        with self.assertRaises(ClinicError):
            self.s.set_status(aid, "Completed")
        with self.assertRaises(ClinicError):
            self.s.set_status(aid, "No-show")

    def test_T34_users_management_and_reset(self):
        self.admin()
        uid = self.s.create_user("extra", "Extra Reception", "Receptionist", PASSWORD)
        self.s.change_user(
            uid, role="Nurse", password="NewPassphrase!2030", unlock=True
        )
        self.assertEqual(self.s.login("extra", "NewPassphrase!2030")["role"], "Nurse")

    def test_T35_fifty_thousand_patient_search(self):
        rows = []
        for i in range(50_000):
            rows.append(
                (
                    f"Person{i:05}",
                    f"Fixture{i:05}",
                    "Passport",
                    f"LOAD{i:08}",
                    "1990-01-01",
                    "0100000001",
                    "Relative",
                    "0100000002",
                    self.reception,
                    self.reception,
                    "2030-01-01",
                    "2030-01-01",
                )
            )
        with self.s.db.connect(write=True) as con:
            con.executemany(
                """INSERT INTO Patient(first_name,last_name,id_type,id_number,date_of_birth,phone,next_of_kin_name,next_of_kin_phone,created_by,updated_by,created_at,updated_at)
             VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
        durations = []
        for _ in range(5):
            start = time.perf_counter()
            result = self.s.patients("LOAD00049999")
            durations.append(time.perf_counter() - start)
            self.assertEqual(len(result), 1)
        METRICS["patient_rows"] = 50_001
        METRICS["patient_search_seconds"] = durations
        METRICS["patient_search_worst_seconds"] = max(durations)
        self.assertLess(max(durations), 2.0)

    def test_T36_ten_doctors_two_hundred_appointments(self):
        self.admin()
        ids = [self.did]
        for i in range(9):
            did = self.s.save_doctor(
                dict(first_name=f"Demo{i}", last_name="LoadDoctor", phone="0100000004")
            )
            self.s.save_schedule(did, 0, "08:00", "16:00", 15)
            ids.append(did)
        self.s.login("reception", PASSWORD)
        # Separate fictional patients avoid intentionally blocked cross-doctor overlaps.
        pids = [self.pid] + [
            self.s.save_patient(patient_data(f"LOADP{i:06}")) for i in range(19)
        ]
        for j, pid in enumerate(pids):
            start = 8 * 60 + 15 * (j + 1)
            self.s.book(pid, ids[0], DAY, f"{start//60:02}:{start%60:02}")
        # Separate patients for other doctors avoid simultaneous patient appointments.
        for k, did in enumerate(ids[1:], 1):
            for j in range(20):
                pid = self.s.save_patient(patient_data(f"D{k}P{j:04}"))
                start = 8 * 60 + 15 * (j + 1)
                self.s.book(pid, did, DAY, f"{start//60:02}:{start%60:02}")
        start = time.perf_counter()
        rows = self.s.appointments(DAY)
        elapsed = time.perf_counter() - start
        METRICS["load_doctors"] = 10
        METRICS["load_appointments"] = len(rows)
        METRICS["daily_lookup_seconds"] = elapsed
        start = time.perf_counter()
        self.s.free_slots(ids[0], DAY)
        slot_elapsed = time.perf_counter() - start
        METRICS["slot_lookup_seconds"] = slot_elapsed
        self.assertLess(slot_elapsed, 2)
        self.assertEqual(len(rows), 200)
        self.assertLess(elapsed, 2)

    def test_T37_overlap_with_changed_slot_duration(self):
        self.book("09:15")
        self.admin()
        self.s.save_schedule(self.did, 0, "08:00", "16:00", 20)
        self.s.login("reception", PASSWORD)
        with self.assertRaises(ClinicError):
            self.s.book(self.pid, self.did, DAY, "09:00")

    def test_T38_foreign_keys_enabled(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with self.s.db.connect(write=True) as con:
                con.execute(
                    "INSERT INTO DoctorSchedule(doctor_id,day_of_week,start_time,end_time,slot_minutes) VALUES(999,0,'08:00','09:00',15)"
                )

    def test_T39_csv_formula_injection_escaped(self):
        d = patient_data()
        d["first_name"] = "=1+1"
        self.s.save_patient(d, self.pid)
        self.book()
        self.admin()
        p = Path(self.tmp.name) / "export.csv"
        self.s.export_csv(p, "daily", DAY)
        with p.open(encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        self.assertTrue(rows[0]["patient"].startswith("'="))

    def test_T40_second_bootstrap_denied(self):
        with self.assertRaises(AccessDenied):
            self.s.bootstrap_admin("other", "Other", PASSWORD)

    def test_T41_elapsed_no_show_is_counted(self):
        aid = self.book()
        self.s.clock = lambda: datetime(2030, 1, 7, 10, 0)
        self.s.set_status(aid, "No-show")
        self.admin()
        self.assertEqual(self.s.summary(DAY, DAY)[0]["no_shows"], 1)

    def test_T42_daily_doctor_filter_and_export(self):
        self.book()
        self.admin()
        other = self.s.save_doctor(
            dict(first_name="Other", last_name="Doctor", phone="0100000004")
        )
        self.s.save_schedule(other, 0, "08:00", "16:00", 15)
        self.s.login("reception", PASSWORD)
        pid = self.s.save_patient(patient_data("FILTER0001"))
        self.s.book(pid, other, DAY, "10:00")
        self.assertEqual(len(self.s.appointments(DAY, self.did)), 1)
        self.admin()
        target = Path(self.tmp.name) / "filtered.csv"
        self.assertEqual(self.s.export_csv(target, "daily", DAY, doctor_id=other), 1)
        with target.open(encoding="utf-8-sig") as f:
            row = list(csv.DictReader(f))[0]
        self.assertEqual(row["doctor"], "Other Doctor")

    def test_T43_csv_cannot_overwrite_database(self):
        self.book()
        self.admin()
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ClinicError, ".csv"):
            self.s.export_csv(self.path, "daily", DAY)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(len(self.s.appointments(DAY)), 1)

    def test_T44_csv_failed_replacement_preserves_previous_export(self):
        from unittest.mock import patch

        self.admin()
        target = Path(self.tmp.name) / "previous.csv"
        target.write_text("original report")
        with patch(
            "sunrise.services.os.replace", side_effect=OSError("simulated disk failure")
        ):
            with self.assertRaises(OSError):
                self.s.export_csv(target, "daily", DAY)
        self.assertEqual(target.read_text(), "original report")
        self.assertEqual(list(target.parent.glob("*.tmp")), [])

    def test_T45_locked_admin_is_not_a_recovery_account(self):
        self.admin()
        self.s.create_user("otheradmin", "Other admin", "Admin", PASSWORD)
        for _ in range(5):
            with self.assertRaises(AccessDenied):
                self.s.login("otheradmin", "wrong")
        self.admin()
        with self.assertRaisesRegex(ClinicError, "unlocked"):
            self.s.change_user(self.s.user["user_id"], active=False)

    def test_T46_reschedule_details_preserve_reason(self):
        aid = self.s.book(self.pid, self.did, DAY, "09:00", "Administrative example")
        self.assertEqual(self.s.appointment(aid)["reason"], "Administrative example")
        self.doctor()
        with self.assertRaises(AccessDenied):
            self.s.appointment(aid)

    def test_T47_demo_clock_never_applies_to_normal_mode(self):
        from main import arguments
        from contextlib import redirect_stderr
        import io

        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            arguments(["--demo-date", DAY])
        args = arguments(["--demo", "--demo-date", DAY])
        self.assertEqual(args.demo_date.isoformat(), DAY)

    def test_T48_demo_seed_supports_same_day_consultation(self):
        from sunrise.demo import initialise_demo, DEMO_PASSWORD

        path = Path(self.tmp.name) / "demo.sqlite"
        initialise_demo(path, clock=lambda: NOW)
        s = ClinicService(path, clock=lambda: NOW)
        s.login("reception", DEMO_PASSWORD)
        aid = s.appointments(DAY)[0]["appointment_id"]
        s.set_status(aid, "Checked-in")
        s.login("doctor", DEMO_PASSWORD)
        s.record_visit(aid, {"complaint": "Fictional demo"})
        self.assertEqual(s.appointments(DAY)[0]["status"], "Completed")
        initialise_demo(path, clock=lambda: NOW)
        self.assertEqual(len(s.appointments(DAY)), 1)

    def test_T49_future_checkin_does_not_change_booking(self):
        aid = self.s.book(self.pid, self.did, "2030-01-08", "09:00")
        with self.assertRaises(ClinicError):
            self.s.set_status(aid, "Checked-in")
        self.assertEqual(self.s.appointment(aid)["status"], "Booked")

    def test_T50_invalid_dates_and_empty_slots_leave_no_bookings(self):
        for day, slot in [("2030-02-30", "09:00"), (DAY, ""), (DAY, "25:00")]:
            with self.assertRaises(ClinicError):
                self.s.book(self.pid, self.did, day, slot)
        self.assertEqual(self.s.appointments(DAY), [])

    def test_T51_completed_visit_cannot_be_rescheduled(self):
        aid = self.book()
        self.s.set_status(aid, "Checked-in")
        self.doctor()
        self.s.record_visit(aid, {"complaint": "Example"})
        self.s.login("reception", PASSWORD)
        with self.assertRaises(ClinicError):
            self.s.book(self.pid, self.did, DAY, "10:00", appointment_id=aid)
        self.assertEqual(self.s.appointment(aid)["start_time"], "09:00")

    def test_T52_duplicate_usernames_are_case_insensitive(self):
        self.admin()
        with self.assertRaises(ClinicError):
            self.s.create_user("RECEPTION", "Duplicate", "Nurse", PASSWORD)

    def test_T53_no_schedule_produces_no_slots(self):
        self.admin()
        did = self.s.save_doctor(
            dict(first_name="New", last_name="Doctor", phone="0100000004")
        )
        self.assertEqual(self.s.free_slots(did, DAY), [])

    def test_T54_combined_fifty_thousand_patients_and_appointment_load(self):
        self.test_T35_fifty_thousand_patient_search()
        self.test_T36_ten_doctors_two_hundred_appointments()
        start = time.perf_counter()
        found = self.s.patients("LOAD00049999")
        search = time.perf_counter() - start
        start = time.perf_counter()
        slots = self.s.free_slots(self.did, DAY)
        lookup = time.perf_counter() - start
        with self.s.db.connect() as con:
            count = con.execute("SELECT COUNT(*) FROM Patient").fetchone()[0]
        self.assertEqual(len(found), 1)
        self.assertTrue(slots)
        self.assertGreaterEqual(count, 50_000)
        self.assertEqual(len(self.s.appointments(DAY)), 200)
        self.assertLess(search, 2)
        self.assertLess(lookup, 2)
        METRICS["combined_load"] = {
            "patients": count,
            "appointments": 200,
            "doctors": 10,
            "patient_search_seconds": search,
            "slot_lookup_seconds": lookup,
        }

    def test_T55_user_role_change_is_enforced_in_open_session(self):
        other = ClinicService(self.path, clock=lambda: NOW)
        other.login("nurse", PASSWORD)
        self.admin()
        self.s.change_user(self.nurse, role="Receptionist")
        with self.assertRaises(AccessDenied):
            other.history(self.pid)
        self.assertEqual(other.user["role"], "Receptionist")


if __name__ == "__main__":
    unittest.main(verbosity=2)
