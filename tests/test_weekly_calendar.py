"""Shared booking visibility, doctor scoping and weekly layout regressions."""

from datetime import date, datetime
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock

from sunrise.demo import initialise_demo, DEMO_PASSWORD
from sunrise.services import ClinicService, AccessDenied
from sunrise.weekly_calendar import WeeklyCalendar, arrange_events, monday_for

NOW = datetime(2030, 1, 7, 8)


class SharedCalendarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_dir = tempfile.TemporaryDirectory()
        cls.base = Path(cls.base_dir.name) / "base.sqlite"
        initialise_demo(cls.base, clock=lambda: NOW)

    @classmethod
    def tearDownClass(cls):
        cls.base_dir.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "shared.sqlite"
        shutil.copy2(self.base, self.path)
        self.patient = ClinicService(self.path, clock=lambda: NOW)
        self.patient.login("patient", DEMO_PASSWORD)

    def tearDown(self):
        self.tmp.cleanup()

    def staff(self, name):
        session = ClinicService(self.path, clock=lambda: NOW)
        session.login(name, DEMO_PASSWORD)
        return session

    def test_patient_booking_visible_to_admin_doctor_and_reception(self):
        # Three independent sessions/connections, not an in-memory UI list.
        staff = [self.staff(name) for name in ("admin", "doctor", "reception")]
        aid = self.patient.book_for_me(1, "2030-01-08", "10:00", "Routine")
        for session in staff:
            row = next(r for r in session.weekly_appointments("2030-01-07") if r["appointment_id"] == aid)
            self.assertEqual(row["date"], "2030-01-08")
            self.assertEqual(row["start_time"], "10:00")
            self.assertEqual(row["patient"], "Fictional Patient")
            self.assertEqual(row["duration_minutes"], 15)

    def test_week_boundaries_include_sunday_and_exclude_next_monday(self):
        admin = self.staff("admin")
        admin.save_schedule(1, 6, "08:00", "16:00", 15)
        sunday = self.patient.book_for_me(1, "2030-01-13", "10:00")
        monday = self.patient.book_for_me(1, "2030-01-14", "10:00")
        ids = {r["appointment_id"] for r in admin.weekly_appointments("2030-01-09")}
        self.assertIn(sunday, ids)
        self.assertNotIn(monday, ids)

    def test_other_doctors_cannot_see_foreign_bookings(self):
        admin = self.staff("admin")
        uid = admin.create_user("otherdoctor", "Dr Other", "Doctor", DEMO_PASSWORD)
        did = admin.save_doctor(dict(first_name="Other", last_name="Doctor", phone="0100000008", user_id=uid))
        admin.save_schedule(did, 1, "08:00", "16:00", 15)
        aid = self.patient.book_for_me(did, "2030-01-08", "10:00")
        assigned = self.staff("otherdoctor")
        other = self.staff("doctor")
        self.assertIn(aid, {r["appointment_id"] for r in assigned.weekly_appointments("2030-01-08")})
        self.assertNotIn(aid, {r["appointment_id"] for r in other.weekly_appointments("2030-01-08")})
        self.assertEqual(other.weekly_appointments("2030-01-08", did), [])
        self.assertIsNone(assigned.next_staff_appointment(1))
        self.assertIn(aid, {r["appointment_id"] for r in admin.weekly_appointments("2030-01-08")})

    def test_next_booking_finds_future_week_and_cancellation_removes_it(self):
        self.patient.cancel_my_appointment(1)
        aid = self.patient.book_for_me(1, "2030-01-21", "10:00")
        for name in ("admin", "doctor"):
            session = self.staff(name)
            self.assertTrue(all(r["status"] == "Cancelled" for r in session.weekly_appointments("2030-01-07")))
            self.assertEqual(session.next_staff_appointment()["appointment_id"], aid)
        self.patient.cancel_my_appointment(aid)
        self.assertIsNone(self.staff("admin").next_staff_appointment())

    def test_reschedule_updates_shared_week_and_does_not_duplicate(self):
        admin = self.staff("admin")
        aid = self.patient.book_for_me(1, "2030-01-08", "10:00", appointment_id=1)
        self.assertEqual(aid, 1)
        rows = admin.weekly_appointments("2030-01-07")
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["date"], rows[0]["start_time"]), ("2030-01-08", "10:00"))
        self.patient.cancel_my_appointment(aid)
        self.assertEqual(admin.weekly_appointments("2030-01-07")[0]["status"], "Cancelled")

    def test_patient_cannot_read_staff_calendar(self):
        with self.assertRaises(AccessDenied):
            self.patient.weekly_appointments("2030-01-07")
        with self.assertRaises(AccessDenied):
            self.patient.next_staff_appointment()

    def test_background_refresh_does_not_extend_session(self):
        session = self.staff("admin")
        widget = WeeklyCalendar.__new__(WeeklyCalendar)
        widget.service = session
        widget.status = Mock()
        widget.winfo_exists = Mock(return_value=False)
        widget.refresh = lambda: session.weekly_appointments("2030-01-07")
        activity = session.last_activity
        widget.poll()
        self.assertEqual(session.last_activity, activity)


class CalendarLayoutTests(unittest.TestCase):
    def row(self, aid, time, duration=30):
        return dict(appointment_id=aid, doctor_id=aid, start_time=time, duration_minutes=duration)

    def test_week_monday_across_year_boundary(self):
        self.assertEqual(monday_for(date(2030, 1, 1)), date(2029, 12, 31))

    def test_overlapping_doctors_have_separate_lanes(self):
        result = arrange_events([self.row(1, "09:00"), self.row(2, "09:00"), self.row(3, "09:15")])
        self.assertEqual({lane for _, lane, _ in result}, {0, 1, 2})
        self.assertTrue(all(total == 3 for _, _, total in result))

    def test_adjacent_appointments_reuse_full_width(self):
        result = arrange_events([self.row(1, "09:00"), self.row(2, "09:30")])
        self.assertEqual([(lane, total) for _, lane, total in result], [(0, 1), (0, 1)])

    def test_partial_overlap_reuses_lanes_without_hiding_events(self):
        result = arrange_events([self.row(1, "09:00", 60), self.row(2, "09:00", 15), self.row(3, "09:15", 15)])
        self.assertEqual([(lane, total) for _, lane, total in result], [(0, 2), (1, 2), (1, 2)])


if __name__ == "__main__":
    unittest.main()
