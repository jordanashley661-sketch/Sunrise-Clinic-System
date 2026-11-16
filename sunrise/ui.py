"""Tkinter/ttk desktop interface. All business operations use ClinicService."""

import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from .services import AccessDenied, ClinicError, PATIENT_FIELDS, ROLES

LABELS = {
    "first_name": "First name",
    "last_name": "Surname",
    "id_type": "ID type",
    "id_number": "ID or passport number",
    "date_of_birth": "Date of birth (YYYY-MM-DD)",
    "gender": "Gender (optional)",
    "phone": "Phone (10 digits)",
    "email": "Email (optional)",
    "address": "Address (optional)",
    "next_of_kin_name": "Next of kin name",
    "next_of_kin_phone": "Next of kin phone",
    "user_id": "Doctor login user number (optional)",
    "full_name": "Full name",
    "username": "Username",
    "password": "Passphrase (15–128 characters)",
    "patient_id": "Patient number",
    "doctor": "Doctor",
    "is_active": "Active (1 yes / 0 no)",
    "role": "Role",
    "day": "Date (YYYY-MM-DD)",
    "start_time": "Time (HH:MM)",
    "reason": "Administrative booking reason",
    "complaint": "Presenting complaint",
    "notes": "Clinical notes",
    "diagnosis": "Diagnosis",
    "treatment": "Treatment",
    "follow_up_date": "Follow-up date (optional YYYY-MM-DD)",
}


class ClinicApp:
    """Task-focused, role-dependent screens for a single local workstation."""

    def __init__(self, root, service, demo=False):
        self.root, self.service, self.demo = root, service, demo
        root.title("Sunrise Community Clinic — coursework prototype")
        root.geometry("1160x780")
        root.minsize(980, 680)
        self.session_role = None
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", font=("Arial", 11))
        style.configure("TButton", padding=(10, 7))
        style.configure("Treeview", rowheight=29)
        style.configure("Treeview.Heading", font=("Arial", 10, "bold"))
        style.configure("Title.TLabel", font=("Arial", 21, "bold"))
        style.configure("Small.TLabel", font=("Arial", 10), foreground="#52636e")
        self.last_touch = 0
        root.bind_all("<KeyPress>", self.activity, add="+")
        root.bind_all("<ButtonPress>", self.activity, add="+")
        root.after(10_000, self.check_idle)
        self.login_screen()

    def guarded(self, callback):
        def run():
            try:
                if self.service.user:
                    self.service.touch()
                    if (
                        self.session_role
                        and self.session_role != self.service.user["role"]
                    ):
                        self.service.logout()
                        self.login_screen()
                        raise AccessDenied("Your role changed. Please log in again.")
                return callback()
            except AccessDenied as exc:
                messagebox.showwarning("Access", str(exc), parent=self.root)
                if not self.service.user:
                    self.login_screen()
            except (ClinicError, ValueError, OSError) as exc:
                messagebox.showerror("Please check", str(exc), parent=self.root)
            except sqlite3.Error:
                messagebox.showerror(
                    "Database problem",
                    "The operation could not be saved. Check disk space and try again. No partial save was kept.",
                    parent=self.root,
                )

        return run

    def activity(self, _event=None):
        import time

        if self.service.user and time.monotonic() - self.last_touch > 2:
            self.last_touch = time.monotonic()
            try:
                self.service.touch()
                if self.session_role and self.service.user["role"] != self.session_role:
                    self.service.logout()
                    self.login_screen()
            except AccessDenied:
                self.login_screen()

    def check_idle(self):
        import time

        if (
            self.service.user
            and time.monotonic() - self.service.last_activity
            >= self.service.IDLE_SECONDS
        ):
            self.service.logout()
            self.login_screen()
            messagebox.showinfo(
                "Session ended",
                "You were logged out after 15 minutes without activity.",
            )
        self.root.after(10_000, self.check_idle)

    def clear(self):
        for child in self.root.winfo_children():
            child.destroy()

    def button(self, parent, text, callback):
        b = ttk.Button(parent, text=text, command=self.guarded(callback))
        b.pack(side="left", padx=(0, 8), pady=6)
        return b

    def login_screen(self):
        self.clear()
        outer = ttk.Frame(self.root, padding=40)
        outer.pack(expand=True)
        ttk.Label(outer, text="Sunrise Community Clinic", style="Title.TLabel").pack(
            anchor="w", pady=12
        )
        ttk.Label(
            outer,
            text="Offline appointment and patient records prototype",
            style="Small.TLabel",
        ).pack(anchor="w", pady=4)
        if self.demo:
            ttk.Label(
                outer,
                text="DEMONSTRATION DATABASE — synthetic data only",
                foreground="#9c4d00",
            ).pack(anchor="w", pady=6)
        self.session_role = None
        setup = self.service.needs_setup()
        ttk.Label(
            outer, text="Create the first administrator" if setup else "Staff login"
        ).pack(anchor="w", pady=10)
        frame = ttk.Frame(outer)
        frame.pack(fill="x")
        fields = (
            ["username", "full_name", "password"] if setup else ["username", "password"]
        )
        inputs = self.fields(frame, fields)

        def submit():
            data = self.values(inputs)
            if setup:
                self.service.bootstrap_admin(
                    data["username"], data["full_name"], data["password"]
                )
            self.service.login(data["username"], data["password"])
            self.shell()

        bar = ttk.Frame(outer)
        bar.pack(fill="x")
        login_button = self.button(
            bar, "Create administrator and log in" if setup else "Log in", submit
        )
        for entry in inputs.values():
            entry.bind("<Return>", lambda event: login_button.invoke())
        if self.demo:
            ttk.Label(
                outer,
                text="Users: admin / reception / doctor / nurse\nDemo passphrase for all: SunriseDemo!2026",
                style="Small.TLabel",
            ).pack(anchor="w", pady=10)
        ttk.Label(
            outer,
            text="Data file: " + str(self.service.db.path),
            style="Small.TLabel",
            wraplength=650,
        ).pack(anchor="w", pady=12)
        inputs["username"].focus_set()

    def fields(self, parent, names, defaults=None, choices=None, multiline=()):
        defaults, choices = defaults or {}, choices or {}
        fields = {}
        for row, name in enumerate(names):
            ttk.Label(
                parent, text=LABELS.get(name, name.replace("_", " ").capitalize())
            ).grid(row=row, column=0, sticky="nw", padx=(0, 12), pady=5)
            if name in multiline:
                entry = tk.Text(
                    parent, width=60, height=3, font=("Arial", 11), wrap="word"
                )
                entry.insert("1.0", str(defaults.get(name, "") or ""))
            elif name in choices:
                entry = ttk.Combobox(
                    parent, values=choices[name], state="readonly", width=43
                )
                entry.set(
                    str(
                        defaults.get(name, choices[name][0] if choices[name] else "")
                        or ""
                    )
                )
            else:
                entry = ttk.Entry(
                    parent, width=46, show="*" if name == "password" else ""
                )
                entry.insert(0, str(defaults.get(name, "") or ""))
            entry.grid(row=row, column=1, sticky="ew", pady=5)
            fields[name] = entry
        parent.columnconfigure(1, weight=1)
        return fields

    def values(self, fields):
        return {
            k: (v.get("1.0", "end-1c") if isinstance(v, tk.Text) else v.get())
            for k, v in fields.items()
        }

    def dialog(self, title):
        window = tk.Toplevel(self.root)
        window.title(title)
        window.transient(self.root)
        window.geometry("800x690")
        window.minsize(720, 620)
        frame = ttk.Frame(window, padding=18)
        frame.pack(fill="both", expand=True)
        window.grab_set()
        return window, frame

    def shell(self):
        self.clear()
        top = ttk.Frame(self.root, padding=(18, 12))
        top.pack(fill="x")
        user = self.service.user
        self.session_role = user["role"]
        ttk.Label(top, text="Sunrise Community Clinic", style="Title.TLabel").pack(
            side="left"
        )
        ttk.Label(top, text=f"{user['full_name']}  |  {user['role']}").pack(
            side="right"
        )
        nav = ttk.Frame(self.root, padding=(18, 0))
        nav.pack(fill="x")
        self.button(nav, "Home", self.home)
        if user["role"] in ("Receptionist", "Doctor", "Nurse"):
            self.button(nav, "Patients", self.patients_screen)
        self.button(nav, "Appointments", self.appointments_screen)
        if user["role"] == "Admin":
            self.button(nav, "Doctors and schedules", self.doctors_screen)
            self.button(nav, "Users", self.users_screen)
            self.button(nav, "Reports", self.reports_screen)
            self.button(nav, "Audit and backup", self.audit_screen)
        self.button(
            nav, "Log out", lambda: (self.service.logout(), self.login_screen())
        )
        if self.demo:
            clock_label = getattr(self.service, "demo_clock_label", "Live system clock")
            ttk.Label(
                self.root,
                text="DEMO — fictional data only | " + clock_label,
                foreground="#9c4d00",
                padding=(18, 5),
            ).pack(fill="x")
        self.content = ttk.Frame(self.root, padding=18)
        self.content.pack(fill="both", expand=True)
        self.home()

    def page(self, title, description=""):
        for child in self.content.winfo_children():
            child.destroy()
        ttk.Label(self.content, text=title, style="Title.TLabel").pack(
            anchor="w", pady=(0, 8)
        )
        if description:
            ttk.Label(
                self.content, text=description, wraplength=1050, style="Small.TLabel"
            ).pack(anchor="w", pady=(0, 10))
        frame = ttk.Frame(self.content)
        frame.pack(fill="both", expand=True)
        return frame

    def tree(self, parent, columns, rows):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, pady=8)
        tree = ttk.Treeview(
            frame, columns=columns, show="headings", selectmode="browse"
        )
        for col in columns:
            tree.heading(col, text=col.replace("_", " ").title())
            tree.column(col, width=110, minwidth=55, stretch=True)
        y = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        x = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        for row in rows:
            tree.insert(
                "",
                "end",
                values=[
                    row.get(c, "") if row.get(c) is not None else "" for c in columns
                ],
            )
        return tree

    def selected(self, tree):
        selection = tree.selection()
        if not selection:
            raise ClinicError("Select a row first.")
        return dict(zip(tree["columns"], tree.item(selection[0], "values")))

    def home(self):
        frame = self.page(
            "Welcome",
            "Use the navigation to open the tasks available for your role. Dates use YYYY-MM-DD and times use 24-hour HH:MM.",
        )
        role = self.service.user["role"]
        text = {
            "Receptionist": "Register patients, search or update demographic details, book and reschedule appointments, check patients in and manage cancellations.",
            "Doctor": "Find patients, review visit history and record a consultation for a checked-in appointment assigned to your doctor profile.",
            "Nurse": "Find patients, review visit history and record a consultation for a checked-in appointment.",
            "Admin": "Create staff accounts and doctor profiles, set weekly schedules and unavailable dates, review reports and create database backups.",
        }[role]
        ttk.Label(frame, text=text, wraplength=900).pack(anchor="w", pady=15)
        ttk.Label(
            frame,
            text="This is a coursework prototype. Use fictional patient data only.\nThe database and exports are not encrypted; protect the computer and backup storage.",
            wraplength=900,
            style="Small.TLabel",
        ).pack(anchor="w", pady=15)
        ttk.Label(
            frame,
            text="Build sequence: Admin creates users → Admin adds doctors and schedules → Reception registers patients and books → Reception checks in → Doctor or nurse records visit.",
            wraplength=900,
        ).pack(anchor="w", pady=10)

    def patients_screen(self):
        frame = self.page(
            "Patient directory",
            "Search by the beginning of a first name, surname, ID/passport number or phone. Up to 100 results are shown. Reception cannot access clinical notes.",
        )
        bar = ttk.Frame(frame)
        bar.pack(fill="x")
        query = ttk.Entry(bar, width=35)
        query.pack(side="left", padx=(0, 8))
        holder = ttk.Frame(frame)
        holder.pack(fill="both", expand=True)
        tree = None

        def refresh():
            nonlocal tree
            rows = self.service.patients(query.get())
            for child in holder.winfo_children():
                child.destroy()
            tree = self.tree(
                holder,
                (
                    "patient_id",
                    "first_name",
                    "last_name",
                    "id_number",
                    "phone",
                    "date_of_birth",
                ),
                rows,
            )

        search_button = self.button(bar, "Search", refresh)
        query.bind("<Return>", lambda event: search_button.invoke())
        if self.service.user["role"] == "Receptionist":
            self.button(
                bar, "Register patient", lambda: self.patient_form(None, refresh)
            )
            self.button(
                bar,
                "View or update",
                lambda: self.patient_form(
                    int(self.selected(tree)["patient_id"]), refresh
                ),
            )
        else:
            self.button(
                bar,
                "View clinical history",
                lambda: self.history_dialog(int(self.selected(tree)["patient_id"])),
            )
        refresh()

    def patient_form(self, patient_id, refresh):
        defaults = (
            self.service.patient(patient_id) if patient_id else {"id_type": "SA ID"}
        )
        window, frame = self.dialog("Patient details")
        inputs = self.fields(
            frame,
            PATIENT_FIELDS,
            defaults,
            {
                "id_type": ["SA ID", "Passport"],
                "gender": ["", "Female", "Male", "Other", "Prefer not to say"],
            },
        )
        ttk.Label(
            frame,
            text="Required: names, ID/passport, birth date, phone and next-of-kin details.\nSA ID validation checks the 13-digit format only.",
            style="Small.TLabel",
        ).grid(row=12, column=0, columnspan=2, sticky="w", pady=8)
        bar = ttk.Frame(frame)
        bar.grid(row=13, column=0, columnspan=2, sticky="w")

        def save():
            saved = self.service.save_patient(self.values(inputs), patient_id)
            messagebox.showinfo("Saved", f"Patient number: {saved}", parent=window)
            window.destroy()
            refresh()

        self.button(bar, "Save patient", save)
        self.button(bar, "Close", window.destroy)

    def history_dialog(self, patient_id):
        patient = self.service.patient(patient_id)
        rows = self.service.history(patient_id)
        window, frame = self.dialog("Clinical history")
        ttk.Label(
            frame,
            text=f"{patient['first_name']} {patient['last_name']}  |  Patient {patient_id}",
            style="Title.TLabel",
        ).pack(anchor="w")
        text = tk.Text(frame, wrap="word", font=("Arial", 11))
        text.pack(fill="both", expand=True, pady=10)
        for visit in rows:
            text.insert(
                "end",
                f"{visit['visit_date']} — {visit['clinician']}\nComplaint: {visit['complaint']}\nNotes: {visit['notes']}\nDiagnosis: {visit['diagnosis']}\nTreatment: {visit['treatment']}\nFollow-up: {visit['follow_up_date'] or 'None'}\n\n",
            )
        if not rows:
            text.insert("end", "No visits recorded for this patient.")
        text.configure(state="disabled")

    def appointments_screen(self):
        frame = self.page(
            "Daily appointments",
            "Refresh after a change. The list includes cancelled appointments; exported daily lists exclude them.",
        )
        bar = ttk.Frame(frame)
        bar.pack(fill="x")
        day = ttk.Entry(bar, width=14)
        day.insert(0, self.service.clock().date().isoformat())
        day.pack(side="left", padx=(0, 8))
        doctor_options = {"All doctors": None}
        doctor_options.update(
            {
                f"{d['doctor_id']}: {d['last_name']}": d["doctor_id"]
                for d in self.service.doctors()
            }
        )
        doctor_filter = ttk.Combobox(
            bar, values=list(doctor_options), state="readonly", width=16
        )
        doctor_filter.set("All doctors")
        doctor_filter.pack(side="left", padx=(0, 8))
        holder = ttk.Frame(frame)
        holder.pack(fill="both", expand=True)
        tree = None

        def refresh():
            nonlocal tree
            rows = self.service.appointments(
                day.get(), doctor_options[doctor_filter.get()]
            )
            for child in holder.winfo_children():
                child.destroy()
            tree = self.tree(
                holder,
                (
                    "appointment_id",
                    "start_time",
                    "patient",
                    "doctor",
                    "status",
                    "patient_id",
                    "doctor_id",
                ),
                rows,
            )

        self.button(bar, "Refresh", refresh)
        role = self.service.user["role"]
        bar = ttk.Frame(frame)
        bar.pack(fill="x", before=holder)
        if role == "Receptionist":
            self.button(
                bar, "Book", lambda: self.booking_form(None, day.get(), refresh)
            )
            self.button(
                bar,
                "Reschedule",
                lambda: self.booking_form(self.selected(tree), day.get(), refresh),
            )

            def status(value):
                row = self.selected(tree)
                if messagebox.askyesno(
                    "Confirm", f'Set appointment {row["appointment_id"]} to {value}?'
                ):
                    self.service.set_status(int(row["appointment_id"]), value)
                    refresh()

            self.button(bar, "Check in", lambda: status("Checked-in"))
            self.button(bar, "Cancel", lambda: status("Cancelled"))
            self.button(bar, "No-show", lambda: status("No-show"))
        elif role in ("Doctor", "Nurse"):
            self.button(
                bar,
                "Record visit",
                lambda: self.visit_form(self.selected(tree), refresh),
            )
            self.button(
                bar,
                "Patient history",
                lambda: self.history_dialog(int(self.selected(tree)["patient_id"])),
            )
        refresh()

    def booking_form(self, old, day, refresh):
        window, frame = self.dialog(
            "Reschedule appointment" if old else "Book appointment"
        )
        doctors = self.service.doctors()
        choices = {
            f"{d['doctor_id']}: {d['first_name']} {d['last_name']}": d["doctor_id"]
            for d in doctors
        }
        if not choices:
            window.destroy()
            raise ClinicError("An administrator must add a doctor and schedule first.")
        defaults = {"patient_id": old["patient_id"] if old else "", "day": day}
        if old:
            defaults["reason"] = self.service.appointment(int(old["appointment_id"]))[
                "reason"
            ]
        inputs = self.fields(
            frame,
            ["patient_id", "doctor", "day", "reason"],
            defaults,
            {"doctor": list(choices)},
        )
        if old:
            inputs["patient_id"].configure(state="readonly")
            match = next(
                (
                    label
                    for label, did in choices.items()
                    if str(did) == old["doctor_id"]
                ),
                None,
            )
            if match:
                inputs["doctor"].set(match)
        ttk.Label(frame, text="Time slot").grid(row=4, column=0, sticky="w", pady=6)
        slot = ttk.Combobox(frame, state="readonly", width=25)
        slot.grid(row=4, column=1, sticky="w")
        loaded_context = None

        def context():
            data = self.values(inputs)
            return (data["patient_id"].strip(), data["doctor"], data["day"].strip())

        def invalidate(_event=None):
            nonlocal loaded_context
            loaded_context = None
            slot.set("")
            slot["values"] = ()
            save_button.configure(state="disabled")

        def load_slots():
            nonlocal loaded_context
            data = self.values(inputs)
            try:
                pid = int(data["patient_id"])
            except ValueError:
                raise ClinicError(
                    "Enter the patient number from the patient directory."
                ) from None
            did = choices[data["doctor"]]
            available = self.service.free_slots(
                did, data["day"], int(old["appointment_id"]) if old else None, pid
            )
            slot["values"] = available
            slot.set(available[0] if available else "")
            loaded_context = context()
            save_button.configure(state="normal" if available else "disabled")
            if not available:
                messagebox.showinfo(
                    "No slots",
                    "No available slots. Check the date, doctor schedule and patient bookings.",
                    parent=window,
                )

        def save():
            if loaded_context != context() or not slot.get():
                invalidate()
                raise ClinicError(
                    "Load free slots again after changing the patient, doctor or date."
                )
            data = self.values(inputs)
            aid = self.service.book(
                int(data["patient_id"]),
                choices[data["doctor"]],
                data["day"],
                slot.get(),
                data["reason"],
                int(old["appointment_id"]) if old else None,
            )
            messagebox.showinfo("Booked", f"Appointment number: {aid}", parent=window)
            window.destroy()
            refresh()

        bar = ttk.Frame(frame)
        bar.grid(row=5, column=0, columnspan=2, sticky="w", pady=10)
        self.button(bar, "Load free slots", load_slots)
        save_button = self.button(bar, "Save booking", save)
        save_button.configure(state="disabled")
        for field in ("patient_id", "doctor", "day"):
            inputs[field].bind("<<ComboboxSelected>>", invalidate)
            inputs[field].bind("<KeyRelease>", invalidate)
        ttk.Label(
            frame,
            text="Enter a patient number, doctor and date, then load free slots.\nThe service checks availability again when you save.\nBooking reasons are administrative only; enter clinical details in the visit screen.",
            wraplength=700,
            style="Small.TLabel",
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=10)

    def visit_form(self, row, refresh):
        window, frame = self.dialog("Record clinical visit")
        ttk.Label(
            frame, text=f"Appointment {row['appointment_id']} — {row['patient']}"
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        inner = ttk.Frame(frame)
        inner.grid(row=1, column=0, columnspan=2, sticky="nsew")
        inputs = self.fields(
            inner,
            ["complaint", "notes", "diagnosis", "treatment", "follow_up_date"],
            multiline=("complaint", "notes", "diagnosis", "treatment"),
        )

        def save():
            data = self.values(inputs)
            self.service.record_visit(int(row["appointment_id"]), data)
            window.destroy()
            refresh()
            if data["follow_up_date"]:
                messagebox.showinfo(
                    "Follow-up request",
                    f"Ask reception to book patient {row['patient_id']} on {data['follow_up_date']}. A follow-up date does not create a booking automatically.",
                )

        bar = ttk.Frame(frame)
        bar.grid(row=2, column=0, columnspan=2, sticky="w")
        self.button(bar, "Save visit and complete appointment", save)

    def doctors_screen(self):
        frame = self.page(
            "Doctors and availability",
            "Create a Doctor user first if the doctor will log in. A profile may also exist without a linked login.",
        )
        bar = ttk.Frame(frame)
        bar.pack(fill="x")
        tree = self.tree(
            frame,
            ("doctor_id", "first_name", "last_name", "phone", "user_id", "is_active"),
            self.service.doctors(False),
        )

        def doctor_form(edit=False):
            old = self.selected(tree) if edit else {}
            window, inner = self.dialog("Doctor profile")
            inputs = self.fields(
                inner,
                ["first_name", "last_name", "phone", "user_id", "is_active"],
                old,
                {"is_active": ["1", "0"]},
            )

            def save():
                data = self.values(inputs)
                data["user_id"] = int(data["user_id"]) if data["user_id"] else None
                data["is_active"] = data["is_active"] == "1"
                self.service.save_doctor(data, int(old["doctor_id"]) if edit else None)
                window.destroy()
                self.doctors_screen()

            bar = ttk.Frame(inner)
            bar.grid(row=6, column=0, columnspan=2, sticky="w")
            self.button(bar, "Save doctor", save)

        self.button(bar, "Add doctor", doctor_form)
        self.button(bar, "Edit doctor", lambda: doctor_form(True))
        self.button(
            bar,
            "Schedules and leave",
            lambda: self.schedule_dialog(int(self.selected(tree)["doctor_id"])),
        )

    def schedule_dialog(self, did):
        window, frame = self.dialog("Weekly schedule and unavailable dates")
        notebook = ttk.Notebook(frame)
        notebook.pack(fill="both", expand=True)
        tab = ttk.Frame(notebook, padding=12)
        leave = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Weekly hours")
        notebook.add(leave, text="Unavailable dates")
        inputs = self.fields(
            tab,
            ["day_of_week", "start_time", "end_time", "slot_minutes"],
            {
                "day_of_week": "0",
                "start_time": "08:00",
                "end_time": "16:00",
                "slot_minutes": "15",
            },
            {"day_of_week": [str(i) for i in range(7)]},
        )
        ttk.Label(
            tab,
            text="Weekdays: 0 Monday · 1 Tuesday · 2 Wednesday · 3 Thursday · 4 Friday · 5 Saturday · 6 Sunday",
            wraplength=650,
            style="Small.TLabel",
        ).grid(row=4, column=0, columnspan=2, pady=5)

        def save_schedule():
            d = self.values(inputs)
            self.service.save_schedule(
                did,
                int(d["day_of_week"]),
                d["start_time"],
                d["end_time"],
                int(d["slot_minutes"]),
            )
            window.destroy()
            self.schedule_dialog(did)

        buttons = ttk.Frame(tab)
        buttons.grid(row=5, column=0, columnspan=2, sticky="w")
        self.button(buttons, "Save weekday hours", save_schedule)
        text = "\n".join(
            f"Day {s['day_of_week']}: {s['start_time']}–{s['end_time']}, {s['slot_minutes']} min"
            for s in self.service.schedule(did)
        )
        ttk.Label(tab, text=text or "No weekly schedule yet.").grid(
            row=6, column=0, columnspan=2, sticky="w", pady=15
        )
        fields = self.fields(
            leave, ["day", "reason"], {"day": self.service.clock().date().isoformat()}
        )

        def save_leave():
            d = self.values(fields)
            self.service.set_unavailable(did, d["day"], d["reason"])
            window.destroy()
            self.schedule_dialog(did)

        def remove_leave():
            self.service.remove_unavailable(did, fields["day"].get())
            window.destroy()
            self.schedule_dialog(did)

        bar = ttk.Frame(leave)
        bar.grid(row=3, column=0, columnspan=2, sticky="w")
        self.button(bar, "Mark unavailable", save_leave)
        self.button(bar, "Remove date", remove_leave)
        text = "\n".join(
            f"{r['date']}: {r['reason']}" for r in self.service.unavailability(did)
        )
        ttk.Label(leave, text=text or "No unavailable dates.", wraplength=650).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=12
        )

    def users_screen(self):
        frame = self.page(
            "Staff accounts",
            "Passphrases must contain 15–128 characters. Five failed logins lock the account until an administrator resets or unlocks it.",
        )
        bar = ttk.Frame(frame)
        bar.pack(fill="x")
        tree = self.tree(
            frame,
            (
                "user_id",
                "username",
                "full_name",
                "role",
                "is_active",
                "failed_attempts",
            ),
            self.service.users(),
        )

        def create():
            window, inner = self.dialog("Create user")
            inputs = self.fields(
                inner,
                ["username", "full_name", "role", "password"],
                choices={"role": list(ROLES)},
            )

            def save():
                d = self.values(inputs)
                self.service.create_user(
                    d["username"], d["full_name"], d["role"], d["password"]
                )
                window.destroy()
                self.users_screen()

            b = ttk.Frame(inner)
            b.grid(row=5, column=0, columnspan=2, sticky="w")
            self.button(b, "Create user", save)

        def edit():
            row = self.selected(tree)
            window, inner = self.dialog("Manage user")
            inputs = self.fields(
                inner,
                ["role", "is_active", "password"],
                row,
                {"role": list(ROLES), "is_active": ["1", "0"]},
            )
            ttk.Label(
                inner,
                text="Leave passphrase blank to retain it. Saving also unlocks the account.",
                style="Small.TLabel",
            ).grid(row=4, column=0, columnspan=2, sticky="w")

            def save():
                d = self.values(inputs)
                self.service.change_user(
                    int(row["user_id"]),
                    d["role"],
                    d["is_active"] == "1",
                    d["password"] or None,
                    True,
                )
                window.destroy()
                self.users_screen()

            b = ttk.Frame(inner)
            b.grid(row=5, column=0, columnspan=2, sticky="w")
            self.button(b, "Save changes and unlock", save)

        self.button(bar, "Create user", create)
        self.button(bar, "Manage selected user", edit)

    def reports_screen(self):
        frame = self.page(
            "Appointment reports",
            "Daily appointment CSV exports exclude cancellations. Summary reports include all statuses and count completed visits separately.",
        )
        bar = ttk.Frame(frame)
        bar.pack(fill="x")
        ttk.Label(bar, text="From").pack(side="left")
        first = ttk.Entry(bar, width=14)
        first.insert(0, self.service.clock().date().isoformat())
        first.pack(side="left", padx=4)
        ttk.Label(bar, text="To (summary)").pack(side="left")
        last = ttk.Entry(bar, width=14)
        last.insert(0, self.service.clock().date().isoformat())
        last.pack(side="left", padx=4)
        holder = ttk.Frame(frame)
        holder.pack(fill="both", expand=True)
        doctor_options = {"All doctors": None}
        doctor_options.update(
            {
                f"{d['doctor_id']}: {d['first_name']} {d['last_name']}": d["doctor_id"]
                for d in self.service.doctors(False)
            }
        )
        ttk.Label(bar, text="Daily export doctor").pack(side="left", padx=(10, 4))
        doctor_filter = ttk.Combobox(
            bar, values=list(doctor_options), state="readonly", width=22
        )
        doctor_filter.set("All doctors")
        doctor_filter.pack(side="left")
        actions = ttk.Frame(frame)
        actions.pack(fill="x", before=holder)

        def summary():
            rows = self.service.summary(first.get(), last.get())
            for child in holder.winfo_children():
                child.destroy()
            self.tree(
                holder,
                ("doctor", "appointments", "completed_visits", "no_shows", "cancelled"),
                rows,
            )

        def export(kind):
            path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV", "*.csv")],
                initialfile=f"{kind}-appointments.csv",
            )
            if path:
                n = self.service.export_csv(
                    path,
                    kind,
                    first.get(),
                    last.get(),
                    doctor_options[doctor_filter.get()],
                )
                messagebox.showinfo(
                    "Exported",
                    f"{n} report rows exported. Protect this file as confidential.",
                )

        self.button(actions, "View summary", summary)
        self.button(actions, "Export summary CSV", lambda: export("summary"))
        self.button(actions, "Export daily CSV", lambda: export("daily"))
        summary()

    def audit_screen(self):
        frame = self.page(
            "Audit and database backup",
            "Audit entries contain actions and record numbers, not clinical notes. Backups are unencrypted: use restricted, encrypted storage. Restore only while the application is closed.",
        )
        bar = ttk.Frame(frame)
        bar.pack(fill="x")

        def backup():
            path = filedialog.asksaveasfilename(
                defaultextension=".sqlite",
                initialfile=f"sunrise-backup-{self.service.clock().date().isoformat()}.sqlite",
                filetypes=[("SQLite database", "*.sqlite")],
            )
            if path:
                self.service.backup(path)
                messagebox.showinfo(
                    "Backup created", "Backup completed and database integrity checked."
                )
                self.audit_screen()

        self.button(bar, "Create backup", backup)
        self.tree(
            frame,
            ("audit_id", "timestamp", "username", "action", "entity", "entity_id"),
            self.service.audit_log(),
        )
