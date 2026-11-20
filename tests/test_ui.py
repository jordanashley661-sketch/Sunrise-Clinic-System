"""Real Tk widget workflows. Requires a desktop display; no fake widget objects.

Message boxes and file pickers are intercepted to allow unattended tests.
The screens, buttons, forms, service calls and SQLite writes are real.
"""

from datetime import datetime
from pathlib import Path
import shutil
import tempfile
import time
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from sunrise.demo import initialise_demo, DEMO_PASSWORD
from sunrise.services import ClinicService
from sunrise.ui import ClinicApp

DAY = "2030-01-07"
NOW = datetime(2030, 1, 7, 8, 0)
SCREENSHOTS = None


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


class GuiTests(unittest.TestCase):
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
        self.path = Path(self.tmp.name) / "test.sqlite"
        shutil.copy2(self.base, self.path)
        self.s = ClinicService(self.path, clock=lambda: NOW)
        self.s.demo_clock_label = (
            "SIMULATED CLOCK: 2030-01-07 08:00 — automated test fixture"
        )
        self.root = tk.Tk()
        self.initial_scaling = float(self.root.tk.call("tk", "scaling"))
        self.callbacks = []
        self.root.report_callback_exception = lambda *exc: self.callbacks.append(
            str(exc[1])
        )
        self.messages = []
        self.patches = []
        for kind in ("showerror", "showwarning", "showinfo"):
            stub = patch(
                "sunrise.ui.messagebox." + kind,
                side_effect=lambda title, text, _kind=kind, **kw: self.messages.append(
                    (_kind, title, text)
                ),
            )
            stub.start()
            self.patches.append(stub)
        stub = patch("sunrise.ui.messagebox.askyesno", return_value=True)
        stub.start()
        self.patches.append(stub)
        self.app = ClinicApp(self.root, self.s, demo=True)
        self.root.update()

    def tearDown(self):
        for item in self.root.tk.call("after", "info"):
            self.root.after_cancel(item)
        self.root.tk.call("tk", "scaling", self.initial_scaling)
        self.root.destroy()
        for stub in reversed(self.patches):
            stub.stop()
        self.tmp.cleanup()
        self.assertEqual(self.callbacks, [], "Unhandled Tk callback exception")

    def click(self, text, parent=None):
        matches = [
            w
            for w in descendants(parent or self.root)
            if isinstance(w, ttk.Button) and w.cget("text") == text
        ]
        self.assertEqual(len(matches), 1, "Expected one button: " + text)
        matches[0].invoke()
        self.root.update()

    def field(self, label, value=None, parent=None):
        if parent is None:
            dialogs = [
                w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)
            ]
            parent = dialogs[-1] if dialogs else self.root
        for widget in descendants(parent or self.root):
            if getattr(widget, "_field_label", None) == label:
                if value is not None:
                    if isinstance(widget, ttk.Combobox):
                        widget.set(value)
                    elif isinstance(widget, tk.Text):
                        widget.delete("1.0", "end")
                        widget.insert("1.0", value)
                    else:
                        widget.delete(0, "end")
                        widget.insert(0, value)
                return widget
        for w in descendants(parent or self.root):
            if isinstance(w, ttk.Label) and w.cget("text") == label:
                info = w.grid_info()
                for other in w.master.winfo_children():
                    if isinstance(other, (ttk.Entry, ttk.Combobox, tk.Text)):
                        pos = other.grid_info()
                        if pos.get("row") == info.get("row") and pos.get("column") == 1:
                            if value is not None:
                                if isinstance(other, ttk.Combobox):
                                    other.set(value)
                                elif isinstance(other, tk.Text):
                                    other.delete("1.0", "end")
                                    other.insert("1.0", value)
                                else:
                                    other.delete(0, "end")
                                    other.insert(0, value)
                            return other
        self.fail("Field not found: " + label)

    def login(self, username):
        if self.s.user:
            self.click("Log out")
        self.field("Username", username)
        self.field("Passphrase (15–128 characters)", DEMO_PASSWORD)
        self.click("Log in")
        self.assertIsNotNone(self.s.user)

    def dialog(self):
        dialogs = [w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)]
        self.assertEqual(len(dialogs), 1)
        return dialogs[0]

    def select(self, appointment_id=None):
        trees = [w for w in descendants(self.root) if isinstance(w, ttk.Treeview)]
        self.assertEqual(len(trees), 1)
        tree = trees[0]
        for iid in tree.get_children():
            if appointment_id is None or str(tree.item(iid, "values")[0]) == str(
                appointment_id
            ):
                tree.selection_set(iid)
                return
        self.fail("Row not found")

    def screenshot(self, name, widget=None):
        if SCREENSHOTS is None:
            return
        from PIL import ImageGrab
        import os

        widget = widget or self.root
        self.root.update()
        x, y = widget.winfo_rootx(), widget.winfo_rooty()
        ImageGrab.grab(xdisplay=os.environ.get("DISPLAY")).crop(
            (x, y, x + widget.winfo_width(), y + widget.winfo_height())
        ).save(SCREENSHOTS / (name + ".png"))

    def test_G01_login_all_roles_and_navigation(self):
        self.screenshot("01-login")
        for user in ("admin", "reception", "doctor", "nurse"):
            self.login(user)
            self.assertTrue(
                any(
                    isinstance(w, ttk.Button) and w.cget("text") == "Appointments"
                    for w in descendants(self.root)
                )
            )
            self.screenshot("02-" + user + "-home")

    def test_G02_bad_login_stays_on_login(self):
        self.field("Username", "reception")
        self.field("Passphrase (15–128 characters)", "wrong")
        self.click("Log in")
        self.assertIsNone(self.s.user)
        self.assertIn("Invalid username", self.messages[-1][2])

    def test_G03_register_and_edit_patient(self):
        self.login("reception")
        self.click("Patients")
        self.click("Register patient")
        self.field("First name", "Example")
        self.field("Surname", "StudentDemo")
        self.field("ID type", "Passport")
        self.field("ID or passport number", "UI000002")
        self.field("Date of birth (YYYY-MM-DD)", "1995-01-01")
        self.field("Phone (10 digits)", "0100000004")
        self.field("Next of kin name", "Fictional Relative")
        self.field("Next of kin phone", "0100000005")
        self.screenshot("03-registration", self.dialog())
        self.click("Save patient")
        rows = self.s.patients("StudentDemo")
        self.assertEqual(len(rows), 1)
        self.select(rows[0]["patient_id"])
        self.click("View or update")
        self.field("Address (optional)", "Updated fictional address")
        self.click("Save patient")
        self.assertEqual(
            self.s.patient(rows[0]["patient_id"])["address"],
            "Updated fictional address",
        )
        self.screenshot("04-patient-directory")

    def test_G04_validation_keeps_form_and_database_safe(self):
        self.login("reception")
        self.click("Patients")
        self.click("Register patient")
        self.click("Save patient")
        self.assertEqual(len(self.s.patients()), 1)
        self.assertTrue(self.dialog().winfo_exists())
        self.assertIn("required", self.messages[-1][2])

    def test_G05_booking_workflow(self):
        self.login("reception")
        self.click("Appointments")
        self.click("Book")
        self.field("Patient number", "1")
        self.click("Load free slots")
        self.field("Time slot", "10:00")
        self.field("Administrative booking reason", "Fictional check")
        self.screenshot("05-booking", self.dialog())
        self.click("Save booking")
        self.assertEqual(len(self.s.appointments(DAY)), 2)
        self.screenshot("06-appointments")

    def test_G06_stale_slot_requires_reload(self):
        self.login("reception")
        self.click("Appointments")
        self.click("Book")
        self.field("Patient number", "1")
        self.click("Load free slots")
        self.field("Date (YYYY-MM-DD)", "2030-01-08")
        self.click("Save booking")
        self.assertIn("Load free slots again", self.messages[-1][2])
        self.assertEqual(len(self.s.appointments("2030-01-08")), 0)

    def test_G07_concurrent_conflict_rejected_by_save(self):
        self.login("reception")
        self.click("Appointments")
        self.click("Book")
        self.field("Patient number", "1")
        self.click("Load free slots")
        self.field("Time slot", "10:00")
        other = ClinicService(self.path, clock=lambda: NOW)
        other.login("reception", DEMO_PASSWORD)
        other.book(1, 1, DAY, "10:00")
        self.click("Save booking")
        self.assertIn("Slot unavailable", self.messages[-1][2])
        self.assertEqual(len(self.s.appointments(DAY)), 2)

    def test_G08_reschedule_keeps_reason_and_updates_time(self):
        self.login("reception")
        self.click("Appointments")
        self.select()
        self.click("Reschedule")
        self.assertEqual(
            self.field("Administrative booking reason").get(), "Demonstration booking"
        )
        self.click("Load free slots")
        self.field("Time slot", "10:00")
        self.click("Save booking")
        self.assertEqual(self.s.appointments(DAY)[0]["start_time"], "10:00")
        self.assertEqual(self.s.appointment(1)["reason"], "Demonstration booking")

    def test_G09_cancel_releases_slot(self):
        self.login("reception")
        self.click("Appointments")
        self.select()
        self.click("Cancel")
        self.assertEqual(self.s.appointments(DAY)[0]["status"], "Cancelled")
        self.assertIn("09:00", self.s.free_slots(1, DAY))

    def test_G10_checkin_visit_and_history(self):
        self.login("reception")
        self.click("Appointments")
        self.select()
        self.click("Check in")
        self.login("doctor")
        self.click("Appointments")
        self.select()
        self.click("Record visit")
        self.field("Presenting complaint", "Fictional headache for coursework")
        self.field("Clinical notes", "Synthetic demonstration note only")
        self.field("Diagnosis", "Fictional demonstration")
        self.field("Treatment", "Demonstration only")
        self.field("Follow-up date (optional YYYY-MM-DD)", "2030-01-08")
        self.screenshot("07-clinical-visit", self.dialog())
        self.click("Save visit and complete appointment")
        self.assertEqual(self.s.appointments(DAY)[0]["status"], "Completed")
        self.select()
        self.click("Patient history")
        self.screenshot("08-history", self.dialog())
        self.assertEqual(
            self.s.history(1)[0]["notes"], "Synthetic demonstration note only"
        )

    def test_G11_invalid_visit_does_not_complete(self):
        self.login("reception")
        self.s.set_status(1, "Checked-in")
        self.login("doctor")
        self.click("Appointments")
        self.select()
        self.click("Record visit")
        self.click("Save visit and complete appointment")
        self.assertEqual(self.s.appointments(DAY)[0]["status"], "Checked-in")
        self.assertIn("required", self.messages[-1][2])

    def test_G12_reception_has_no_history_or_visit_controls(self):
        self.login("reception")
        self.click("Patients")
        texts = [
            w.cget("text") for w in descendants(self.root) if isinstance(w, ttk.Button)
        ]
        self.assertNotIn("View clinical history", texts)
        self.click("Appointments")
        self.assertFalse(
            any(
                isinstance(w, ttk.Button) and w.cget("text") == "Record visit"
                for w in descendants(self.root)
            )
        )

    def test_G13_admin_screens_render(self):
        self.login("admin")
        for screen in ("Doctors and schedules", "Users", "Reports", "Audit and backup"):
            self.click(screen)
            self.assertTrue(
                any(isinstance(w, ttk.Treeview) for w in descendants(self.root))
            )
            self.screenshot("09-" + screen.lower().replace(" ", "-"))

    def test_G14_schedule_and_leave_forms_save(self):
        self.login("admin")
        self.click("Doctors and schedules")
        self.select()
        self.click("Schedules and leave")
        self.field("Time (HH:MM)", "09:00")
        self.field("End time", "15:00")
        self.field("Slot minutes", "30")
        self.click("Save weekday hours")
        self.assertEqual(self.s.schedule(1)[0]["slot_minutes"], 30)
        notebook = next(
            w for w in descendants(self.dialog()) if isinstance(w, ttk.Notebook)
        )
        notebook.select(1)
        self.root.update()
        self.field("Date (YYYY-MM-DD)", "2030-01-08")
        self.field("Administrative booking reason", "Fictional leave")
        self.click("Mark unavailable")
        self.assertEqual(self.s.unavailability(1)[0]["date"], "2030-01-08")

    def test_G15_create_user_and_doctor(self):
        self.login("admin")
        self.click("Users")
        self.click("Create user")
        self.field("Username", "newdoctor")
        self.field("Full name", "Example Doctor")
        self.field("Role", "Doctor")
        self.field("Passphrase (15–128 characters)", DEMO_PASSWORD)
        self.click("Create user", self.dialog())
        uid = next(u["user_id"] for u in self.s.users() if u["username"] == "newdoctor")
        self.click("Doctors and schedules")
        self.click("Add doctor")
        self.field("First name", "Example")
        self.field("Surname", "Doctor")
        self.field("Phone (10 digits)", "0100000006")
        self.field("Doctor login user number (optional)", str(uid))
        self.click("Save doctor")
        self.assertEqual(len(self.s.doctors()), 2)

    def test_G16_report_export_and_backup_restore(self):
        self.login("admin")
        self.click("Reports")
        csv_path = Path(self.tmp.name) / "daily.csv"
        with patch(
            "sunrise.ui.filedialog.asksaveasfilename", return_value=str(csv_path)
        ):
            self.click("Export daily CSV")
        self.assertIn("Fictional Patient", csv_path.read_text(encoding="utf-8-sig"))
        self.click("Audit and backup")
        backup = Path(self.tmp.name) / "backup.sqlite"
        with patch("sunrise.ui.filedialog.asksaveasfilename", return_value=str(backup)):
            self.click("Create backup")
        restored = ClinicService(backup, clock=lambda: NOW)
        restored.login("reception", DEMO_PASSWORD)
        self.assertEqual(len(restored.appointments(DAY)), 1)

    def test_G17_expiry_closes_sensitive_modal(self):
        self.login("doctor")
        self.click("Patients")
        self.select()
        self.click("View clinical history")
        self.s.last_activity = time.monotonic() - 901
        self.app.check_idle()
        self.root.update()
        self.assertIsNone(self.s.user)
        self.assertFalse(
            any(isinstance(w, tk.Toplevel) for w in self.root.winfo_children())
        )
        self.assertTrue(self.field("Username").winfo_exists())

    def test_G18_role_change_closes_old_clinical_screen(self):
        self.login("nurse")
        self.click("Patients")
        self.select()
        self.click("View clinical history")
        other = ClinicService(self.path)
        other.login("admin", DEMO_PASSWORD)
        other.change_user(self.s.user["user_id"], role="Receptionist")
        self.app.last_touch = 0
        self.app.activity()
        self.root.update()
        self.assertIsNone(self.s.user)
        self.assertFalse(
            any(isinstance(w, tk.Toplevel) for w in self.root.winfo_children())
        )

    def test_G19_restart_persistence(self):
        self.login("reception")
        aid = self.s.book(1, 1, DAY, "10:00")
        self.s.logout()
        restarted = ClinicService(self.path, clock=lambda: NOW)
        restarted.login("reception", DEMO_PASSWORD)
        self.assertIn(aid, [a["appointment_id"] for a in restarted.appointments(DAY)])

    def test_G20_invalid_refresh_keeps_previous_list(self):
        self.login("reception")
        self.click("Appointments")
        entries = [w for w in descendants(self.app.content) if type(w) is ttk.Entry]
        entries[0].delete(0, "end")
        entries[0].insert(0, "invalid")
        self.click("Refresh")
        self.assertIn("valid date", self.messages[-1][2])
        tree = next(w for w in descendants(self.root) if isinstance(w, ttk.Treeview))
        self.assertEqual(len(tree.get_children()), 1)

    def test_G21_form_actions_fit_at_125_percent_scaling(self):
        self.root.tk.call("tk", "scaling", 1.667)
        self.login("reception")
        self.click("Patients")
        self.click("Register patient")
        self.root.update()
        dialog = self.dialog()
        save = next(
            w
            for w in descendants(dialog)
            if isinstance(w, ttk.Button) and w.cget("text") == "Save patient"
        )
        bottom = save.winfo_rooty() - dialog.winfo_rooty() + save.winfo_height()
        self.assertLessEqual(bottom, dialog.winfo_height())
        self.screenshot("10-registration-scaled", dialog)

    def test_G22_first_administrator_setup(self):
        self.s.logout()
        self.s = ClinicService(Path(self.tmp.name) / "empty.sqlite", clock=lambda: NOW)
        self.app.service = self.s
        self.app.login_screen()
        self.root.update()
        self.field("Username", "firstadmin")
        self.field("Full name", "Fictional Administrator")
        self.field("Passphrase (15–128 characters)", DEMO_PASSWORD)
        self.click("Create administrator and log in")
        self.assertEqual(self.s.user["role"], "Admin")
        self.assertFalse(self.s.needs_setup())

    def test_G23_no_show_controls(self):
        self.login("reception")
        self.click("Appointments")
        self.select()
        self.click("No-show")
        self.assertIn("future", self.messages[-1][2])
        self.s.clock = lambda: datetime(2030, 1, 7, 10, 0)
        self.click("No-show")
        self.assertEqual(self.s.appointments(DAY)[0]["status"], "No-show")

    def test_G24_manage_account_and_unlock(self):
        self.login("admin")
        self.click("Users")
        uid = next(u["user_id"] for u in self.s.users() if u["username"] == "reception")
        self.select(uid)
        self.click("Manage selected user")
        self.field("Role", "Nurse")
        self.field("Passphrase (15–128 characters)", "ChangedPassphrase!2030")
        self.click("Save changes and unlock")
        other = ClinicService(self.path)
        self.assertEqual(
            other.login("reception", "ChangedPassphrase!2030")["role"], "Nurse"
        )

    def test_G25_edit_doctor_and_remove_leave(self):
        self.login("admin")
        self.click("Doctors and schedules")
        self.select()
        self.click("Edit doctor")
        self.field("Phone (10 digits)", "0100000009")
        self.click("Save doctor")
        self.assertEqual(self.s.doctors()[0]["phone"], "0100000009")
        self.s.set_unavailable(1, "2030-01-08", "Example leave")
        self.select()
        self.click("Schedules and leave")
        notebook = next(
            w for w in descendants(self.dialog()) if isinstance(w, ttk.Notebook)
        )
        notebook.select(1)
        self.root.update()
        self.field("Date (YYYY-MM-DD)", "2030-01-08")
        self.click("Remove date")
        self.assertEqual(self.s.unavailability(1), [])

    def test_G26_summary_export_and_daily_doctor_filter(self):
        import csv

        self.login("admin")
        self.click("Reports")
        combo = next(
            w for w in descendants(self.app.content) if isinstance(w, ttk.Combobox)
        )
        combo.current(1)
        path = Path(self.tmp.name) / "report.csv"
        with patch("sunrise.ui.filedialog.asksaveasfilename", return_value=str(path)):
            self.click("Export daily CSV")
        with path.open(encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["doctor"], "Demo Mokoena")
        with patch("sunrise.ui.filedialog.asksaveasfilename", return_value=str(path)):
            self.click("Export summary CSV")
        with path.open(encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]["appointments"], "1")

    def test_G27_nurse_can_record_checked_in_visit(self):
        self.login("reception")
        self.s.set_status(1, "Checked-in")
        self.login("nurse")
        self.click("Appointments")
        self.select()
        self.click("Record visit")
        self.field("Presenting complaint", "Fictional nurse consultation")
        self.click("Save visit and complete appointment")
        self.assertEqual(self.s.history(1)[0]["clinician"], "Demo Nurse Dlamini")

    def test_G28_unassigned_doctor_cannot_complete_visit(self):
        self.login("admin")
        self.s.create_user("otherdoc", "Other Doctor", "Doctor", DEMO_PASSWORD)
        self.login("reception")
        self.s.set_status(1, "Checked-in")
        self.login("otherdoc")
        self.click("Appointments")
        self.select()
        self.click("Record visit")
        self.field("Presenting complaint", "Blocked example")
        self.click("Save visit and complete appointment")
        self.assertIn("only for their own", self.messages[-1][2])
        self.assertEqual(self.s.appointments(DAY)[0]["status"], "Checked-in")

    def test_G29_password_visibility_toggle(self):
        entry = self.field("Passphrase (15–128 characters)", "FictionalPassword")
        self.assertNotEqual(str(entry.cget("show")), "")
        self.click("Show")
        self.assertEqual(str(entry.cget("show")), "")
        self.assertEqual(entry.get(), "FictionalPassword")
        self.click("Hide")
        self.assertNotEqual(str(entry.cget("show")), "")
        self.assertEqual(entry.get(), "FictionalPassword")

    def test_G30_overview_status_refresh_and_small_window_navigation(self):
        self.login("reception")
        self.s.set_status(1, "Checked-in")
        self.click("Home")
        labels = [
            w.cget("text")
            for w in descendants(self.app.content)
            if isinstance(w, tk.Label)
        ]
        self.assertIn("Demo Mokoena  ·  Checked-in", labels)
        self.assertIn("Demo Receptionist", labels)
        self.root.geometry("1000x720")
        self.root.update()
        self.click("View appointments")
        self.assertEqual(self.app.breadcrumb.get(), "Staff workspace  /  Appointments")
        self.assertEqual(self.s.appointments(DAY)[0]["status"], "Checked-in")
        self.click("Home")
        self.click("Register a patient")
        self.assertTrue(self.field("First name").winfo_ismapped())
        self.click("Close")
        self.assertEqual(self.s.appointments(DAY)[0]["status"], "Checked-in")

    def patient_login(self):
        if self.s.user:
            self.click("Log out")
        self.click("Patient portal")
        self.field("Username", "patient")
        self.field("Passphrase (15–128 characters)", DEMO_PASSWORD)
        self.click("Log in")
        self.assertEqual(self.s.user["role"], "Patient")

    def staff_login(self, username):
        if self.s.user:
            self.click("Log out")
        self.click("Staff sign in")
        self.login(username)

    def test_G31_patient_sign_in_and_private_navigation(self):
        self.click("Patient portal")
        self.screenshot("11-patient-login")
        self.patient_login()
        self.assertIn("My appointments", self.app.nav_buttons)
        self.assertNotIn("Patients", self.app.nav_buttons)
        self.assertNotIn("Users", self.app.nav_buttons)
        self.screenshot("12-patient-overview")

    def test_G32_patient_books_and_reception_sees_booking(self):
        self.patient_login()
        self.click("My appointments")
        self.click("Book an appointment")
        self.dialog().booking_picker.choose_time("10:00")
        self.field("Administrative booking reason", "Routine appointment")
        self.screenshot("13-patient-booking", self.dialog())
        self.click("Confirm my booking")
        self.assertEqual(len(self.s.my_appointments()), 2)
        self.screenshot("14-patient-appointments")
        self.staff_login("reception")
        self.assertTrue(
            any(a["start_time"] == "10:00" for a in self.s.appointments(DAY))
        )

    def test_G33_patient_reschedules_and_cancels(self):
        self.patient_login()
        self.click("My appointments")
        self.select(1)
        self.click("Reschedule my appointment")
        self.dialog().booking_picker.choose_day(datetime(2030, 1, 8).date())
        self.dialog().booking_picker.choose_time("10:00")
        self.click("Confirm my booking")
        self.assertEqual(self.s.my_appointments()[0]["date"], "2030-01-08")
        self.select(1)
        self.click("Cancel my appointment")
        self.assertEqual(self.s.my_appointments()[0]["status"], "Cancelled")

    def test_G34_patient_edits_contact_and_medical_insurance(self):
        self.patient_login()
        self.click("Personal details")
        identity_text = " ".join(
            w.cget("text")
            for w in descendants(self.app.content)
            if isinstance(w, ttk.Label)
        )
        self.assertIn("DEMO000001", identity_text)
        self.field("Phone (10 digits)", "0100000008")
        self.field("Address (optional)", "Updated patient address")
        self.click("Save my details")
        self.assertEqual(self.s.my_profile()["address"], "Updated patient address")
        self.click("Medical insurance")
        self.field("Medical aid provider", "Example Health")
        self.field("Membership number", "1234564821")
        self.field("Member type", "Principal member")
        self.click("Save medical insurance")
        self.assertEqual(self.s.my_insurance()["membership_number"], "1234564821")
        self.screenshot("15-patient-insurance")
        self.click("My overview")
        labels = [
            w.cget("text")
            for w in descendants(self.app.content)
            if isinstance(w, tk.Label)
        ]
        self.assertTrue(any("4821" in t and "123456" not in t for t in labels))

    def test_G35_new_patient_registration_and_empty_overview(self):
        from tests.test_patient_portal import profile

        self.click("Patient portal")
        self.click("Create a patient account")
        self.field("Username", "lerato")
        self.field("Passphrase (15–128 characters)", DEMO_PASSWORD)
        self.field("Confirm password", DEMO_PASSWORD)
        notebook = next(
            w for w in descendants(self.dialog()) if isinstance(w, ttk.Notebook)
        )
        notebook.select(1)
        self.root.update()
        data = profile()
        for key, field in [
            ("first_name", "First name"),
            ("last_name", "Surname"),
            ("id_number", "ID or passport number"),
            ("date_of_birth", "Date of birth (YYYY-MM-DD)"),
            ("gender", "Gender (optional)"),
            ("phone", "Phone (10 digits)"),
            ("email", "Email (optional)"),
            ("address", "Address (optional)"),
            ("next_of_kin_name", "Next of kin name"),
            ("next_of_kin_phone", "Next of kin phone"),
        ]:
            self.field(field, data[key])
        self.screenshot("16-patient-registration", self.dialog())
        self.click("Create patient account")
        self.assertEqual(self.s.my_profile()["first_name"], "Lerato")
        self.assertEqual(self.s.my_appointments(), [])
        self.click("Medical insurance")
        for field, value in [
            ("Medical aid provider", "Example Health"),
            ("Plan (optional)", "Sample medical aid plan"),
            ("Membership number", "1234564821"),
            ("Member type", "Principal member"),
        ]:
            self.field(field, value)
        self.click("Save medical insurance")
        self.click("My overview")
        self.root.geometry("1363x936")
        self.root.update()
        self.screenshot("17-patient-empty-overview")

    def test_G36_reception_invitation_redeemed_in_patient_signup(self):
        from tests.test_patient_portal import profile

        self.login("reception")
        pid = self.s.save_patient(profile())
        self.click("Patients")
        # Refresh lists after creating this fixture through the real service.
        self.click("Search")
        self.select(pid)
        self.click("View or update")
        self.click("Create portal invitation")
        windows = [w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)]
        invitation_window = next(
            w for w in windows if w.title() == "Patient portal invitation"
        )
        token = next(
            w.get() for w in descendants(invitation_window) if isinstance(w, ttk.Entry)
        )
        self.assertGreater(len(token), 20)
        self.click("Close invitation")
        self.click("Close")
        self.click("Log out")
        self.click("Patient portal")
        self.click("Create a patient account")
        self.field("Username", "invited")
        self.field("Passphrase (15–128 characters)", DEMO_PASSWORD)
        self.field("Confirm password", DEMO_PASSWORD)
        self.field("Clinic invitation code (optional)", token)
        self.click("Create patient account")
        self.assertEqual(self.s.my_profile()["patient_id"], pid)

    def test_G37_own_visit_summary_excludes_internal_notes(self):
        self.login("reception")
        self.s.set_status(1, "Checked-in")
        self.staff_login("doctor")
        self.s.record_visit(
            1,
            {
                "complaint": "Fictional complaint",
                "notes": "Private staff note",
                "diagnosis": "Example diagnosis",
                "treatment": "Example treatment",
            },
        )
        self.patient_login()
        self.click("Visit summaries")
        text = next(
            w for w in descendants(self.app.content) if isinstance(w, tk.Text)
        ).get("1.0", "end")
        self.assertIn("Example diagnosis", text)
        self.assertNotIn("Private staff note", text)
        self.screenshot("18-patient-visit-summaries")

    def test_G38_patient_small_window_and_session_expiry(self):
        self.root.geometry("1000x720")
        self.root.update()
        self.click("Patient portal")
        button = next(
            w
            for w in descendants(self.root)
            if isinstance(w, ttk.Button) and w.cget("text") == "Log in"
        )
        self.assertGreaterEqual(button.winfo_rooty(), self.root.winfo_rooty())
        self.assertLessEqual(
            button.winfo_rooty() + button.winfo_height(),
            self.root.winfo_rooty() + self.root.winfo_height(),
        )
        self.patient_login()
        self.click("Personal details")
        self.assertTrue(self.field("Phone (10 digits)").winfo_ismapped())
        self.s.last_activity = time.monotonic() - 901
        self.click("Save my details")
        self.assertIsNone(self.s.user)
        self.assertFalse(
            hasattr(self.app, "content") and self.app.content.winfo_exists()
        )

    def test_G39_patient_changed_date_clears_loaded_slot(self):
        self.patient_login()
        self.click("My appointments")
        self.click("Book an appointment")
        picker = self.dialog().booking_picker
        self.assertEqual(picker.selected_time, "")
        picker.time_buttons["10:00"].invoke()
        self.assertEqual(picker.selected_time, "10:00")
        picker.day_buttons["2030-01-08"].invoke()
        self.assertEqual(picker.day.isoformat(), "2030-01-08")
        self.assertEqual(picker.selected_time, "")
        confirm = next(w for w in descendants(self.dialog())
                       if isinstance(w, ttk.Button) and w.cget("text") == "Confirm my booking")
        self.assertTrue(confirm.instate(["disabled"]))
        self.assertEqual(len(self.s.my_appointments()), 1)
        self.click("Close")

    def test_G42_calendar_disables_unavailable_days_and_rejects_invalid_time(self):
        self.patient_login()
        self.click("My appointments")
        self.click("Book an appointment")
        picker = self.dialog().booking_picker
        self.assertTrue(picker.day_buttons["2030-01-06"].instate(["disabled"]))
        self.assertNotIn("09:00", picker.time_buttons)  # Existing demo booking.
        picker.choose_time("03:00")
        self.assertEqual(picker.selected_time, "")
        self.assertIn("10:00", picker.time_buttons)
        picker.move_month(1)
        self.assertEqual(picker.month.month, 2)
        picker.move_month(-1)
        self.assertEqual(picker.month.month, 1)
        self.assertEqual(len(self.s.my_appointments()), 1)
        self.click("Close")

    def test_G40_patient_and_staff_login_modes_are_distinct(self):
        self.field("Username", "patient")
        self.field("Passphrase (15–128 characters)", DEMO_PASSWORD)
        self.click("Log in")
        self.assertIsNone(self.s.user)
        self.click("Patient portal")
        self.field("Username", "reception")
        self.field("Passphrase (15–128 characters)", DEMO_PASSWORD)
        self.click("Log in")
        self.assertIsNone(self.s.user)

    def test_G43_patient_future_booking_appears_on_staff_home(self):
        from sunrise.weekly_calendar import WeeklyCalendar
        self.patient_login()
        aid = self.s.book_for_me(1, "2030-01-21", "10:00", "Routine check")
        for username in ("admin", "doctor"):
            self.staff_login(username)
            widget = next(w for w in descendants(self.app.content) if isinstance(w, WeeklyCalendar))
            # The existing demo booking is earlier; jump directly to the target week.
            widget.week = datetime(2030, 1, 21).date()
            widget.refresh()
            self.root.update()
            self.assertIn(aid, {r["appointment_id"] for r in widget.rows})
            self.assertIn("appointment-" + str(aid), widget.event_cards)
