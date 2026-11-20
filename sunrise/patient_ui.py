"""Patient-only Tk views backed by service-layer ownership checks."""

from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
from .booking_picker import BookingPicker
from .services import ClinicError, PATIENT_FIELDS
from .theme import BG, PALE, TEAL, MUTED, LINE, FONT, Panel, label, SlimScrollbar


class PatientPortalUI:
    """Patient workspace sharing the staff app's theme and session guards."""

    def patient_signup_form(self):
        window, frame = self.dialog("Create your patient account")
        book = ttk.Notebook(frame)
        book.pack(fill="both", expand=True)
        account = ttk.Frame(book, padding=14)
        personal = ttk.Frame(book, padding=14)
        book.add(account, text="1  Your account")
        book.add(personal, text="2  New patient details")
        inputs = self.fields(
            account, ["username", "password", "confirm_password", "invitation"]
        )
        ttk.Label(
            account,
            text="Use a passphrase of 15–128 characters.\n\nNew patient? Leave the invitation blank and complete the second tab.\n\nAlready registered at this clinic? Ask reception to verify your identity\nand issue an invitation. Paste it here; you do not need the second tab.\nAn ID number alone cannot be used to claim an existing record.",
            style="Small.TLabel",
            wraplength=640,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=18)
        details = self.fields(
            personal,
            PATIENT_FIELDS,
            {"id_type": "Passport"},
            {
                "id_type": ["Passport", "SA ID"],
                "gender": ["", "Female", "Male", "Other", "Prefer not to say"],
            },
        )
        ttk.Label(
            personal,
            text="Email is required for self-registration. Use fictional details for this coursework demo.",
            style="Small.TLabel",
            wraplength=650,
        ).grid(row=12, column=0, columnspan=2, sticky="w", pady=8)
        bar = ttk.Frame(frame)
        bar.pack(fill="x", pady=(12, 0))

        def save():
            data = self.values(inputs)
            if data["password"] != data["confirm_password"]:
                raise ClinicError("The passwords do not match.")
            pid = self.service.register_patient_account(
                data["username"],
                data["password"],
                self.values(details),
                data["invitation"],
            )
            messagebox.showinfo(
                "Account created",
                f"Your patient number is {pid}. You can now book appointments.",
                parent=window,
            )
            self.service.login(data["username"], data["password"])
            window.destroy()
            self.shell()

        self.button(bar, "Create patient account", save)
        self.button(bar, "Close", window.destroy)

    def patient_invitation_dialog(self, patient_id):
        if not messagebox.askyesno(
            "Verify patient identity",
            "Have you verified this patient's identity?\nThe invitation gives access to this patient's existing records. Give it only to the verified patient.",
            parent=self.root,
        ):
            return
        token = self.service.issue_patient_invitation(patient_id)
        window, frame = self.dialog("Patient portal invitation")
        ttk.Label(
            frame,
            text="Give this one-use code to the verified patient.\nIt expires after 24 application-clock hours.\nA new invitation invalidates the previous unused code.",
            wraplength=650,
        ).pack(anchor="w", pady=(0, 18))
        code = ttk.Entry(frame, width=55)
        code.insert(0, token)
        code.configure(state="readonly")
        code.pack(fill="x")
        bar = ttk.Frame(frame)
        bar.pack(fill="x", pady=12)

        def copy():
            self.root.clipboard_clear()
            self.root.clipboard_append(token)
            messagebox.showinfo(
                "Copied",
                "Invitation copied. Give it to the verified patient.",
                parent=window,
            )

        self.button(bar, "Copy invitation", copy)
        self.button(bar, "Close invitation", window.destroy)

    def _patient_canvas(self, key):
        for child in self.content.winfo_children():
            child.destroy()
        self.set_navigation(key)
        canvas = tk.Canvas(self.content, bg=BG, highlightthickness=0)
        scroll = SlimScrollbar(self.content, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        body = tk.Frame(canvas, bg=BG)
        handle = canvas.create_window(0, 0, anchor="nw", window=body)
        body.bind(
            "<Configure>",
            lambda event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>", lambda event: canvas.itemconfigure(handle, width=event.width)
        )
        return body

    def patient_home(self):
        profile = self.service.my_profile()
        insurance = self.service.my_insurance()
        rows = self.service.my_appointments()
        upcoming = sorted(
            [
                a
                for a in rows
                if a["status"] in ("Booked", "Checked-in")
                and datetime.fromisoformat(a["date"] + "T" + a["start_time"])
                >= self.service.clock()
            ],
            key=lambda a: (a["date"], a["start_time"]),
        )
        body = self._patient_canvas("My overview")
        banner = Panel(body, fill=PALE, padding=22)
        banner.pack(fill="x", pady=(0, 18))
        label(banner.body, "YOUR HEALTH. YOUR SPACE.", 8, color=TEAL, bold=True).pack(
            anchor="w", pady=(0, 8)
        )
        label(
            banner.body, f'Welcome back, {profile["first_name"]}.', 24, bold=True
        ).pack(anchor="w")
        label(
            banner.body,
            "Manage your appointments, personal details and medical insurance in one place.",
            10,
            color=MUTED,
            wraplength=650,
        ).pack(anchor="w", pady=(8, 0))
        columns = tk.Frame(body, bg=BG)
        columns.pack(fill="x")
        columns.columnconfigure(0, weight=53, uniform="patient")
        columns.columnconfigure(1, weight=47, uniform="patient")
        left = tk.Frame(columns, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        right = tk.Frame(columns, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        card = Panel(left, padding=20)
        card.pack(fill="x", pady=(0, 16))
        label(card.body, "Upcoming appointment", 12, bold=True).pack(
            anchor="w", pady=(0, 16)
        )
        if upcoming:
            visit = upcoming[0]
            label(
                card.body, visit["date"] + "  ·  " + visit["start_time"], 18, bold=True
            ).pack(anchor="w", pady=(10, 6))
            label(card.body, "Dr " + visit["doctor"], 12, color=TEAL).pack(anchor="w")
            label(card.body, "Status: " + visit["status"], 10, color=MUTED).pack(
                anchor="w", pady=(8, 20)
            )
            text = "Manage my appointments"
            command = self.patient_appointments_screen
        else:
            empty = tk.Frame(card.body, bg="#F6FAF8")
            empty.pack(fill="x", pady=(0, 14))
            label(empty, "+", 28, color=TEAL).pack(anchor="center", pady=(18, 5))
            label(empty, "No upcoming appointments", 12, bold=True).pack(
                anchor="center"
            )
            label(
                empty,
                "When your next visit is booked,\nyou will find the details here.",
                10,
                color=MUTED,
                justify="center",
            ).pack(anchor="center", pady=(9, 24))
            text = "Book an appointment"

            def command():
                self.patient_booking_form(None, self.patient_home)

        ttk.Button(
            card.body, text=text, style="Primary.TButton", command=self.guarded(command)
        ).pack(anchor="center", pady=(4, 6))
        help_card = Panel(left, padding=20)
        help_card.pack(fill="x", pady=(0, 16))
        label(help_card.body, "Need help with your next visit?", 10, bold=True).pack(
            anchor="w"
        )
        label(
            help_card.body,
            "Contact clinic reception for identity corrections,\naccount recovery or changes to a checked-in visit.",
            9,
            color=MUTED,
            wraplength=380,
        ).pack(anchor="w", pady=(9, 0))
        personal = Panel(right, padding=20)
        personal.pack(fill="x", pady=(0, 16))
        label(personal.body, "Personal details", 12, bold=True).pack(anchor="w")
        label(
            personal.body,
            profile["first_name"] + " " + profile["last_name"],
            13,
            bold=True,
        ).pack(anchor="w", pady=(15, 5))
        label(
            personal.body,
            f'Patient number · PT-{profile["patient_id"]:05d}',
            9,
            color=MUTED,
        ).pack(anchor="w")
        tk.Frame(personal.body, bg=LINE, height=1).pack(fill="x", pady=14)
        for heading, value in [
            ("Date of birth", profile["date_of_birth"]),
            ("Phone number", profile["phone"]),
            ("Email address", profile["email"] or "Not provided"),
            ("Address", profile["address"] or "Not provided"),
        ]:
            label(personal.body, heading, 8, color=MUTED).pack(anchor="w")
            label(personal.body, value, 10, wraplength=330).pack(
                anchor="w", pady=(3, 9)
            )
        ttk.Button(
            personal.body,
            text="Edit my details",
            style="Link.TButton",
            command=self.guarded(self.patient_details_screen),
        ).pack(anchor="w")
        aid = Panel(right, padding=20)
        aid.pack(fill="x", pady=(0, 16))
        label(aid.body, "Medical insurance", 12, bold=True).pack(
            anchor="w", pady=(0, 12)
        )
        provider = insurance["insurance_provider"] or (
            "Self-paying"
            if insurance["member_type"] == "Self-paying"
            else "Not provided"
        )
        label(aid.body, provider, 11, color=TEAL, bold=True, wraplength=330).pack(
            anchor="w"
        )
        if insurance["membership_number"]:
            number = insurance["membership_number"]
            label(
                aid.body,
                "Membership: " + ("*" * max(4, len(number) - 4)) + number[-4:],
                9,
                color=MUTED,
            ).pack(anchor="w", pady=(8, 0))
        ttk.Button(
            aid.body,
            text="Update medical insurance",
            style="Link.TButton",
            command=self.guarded(self.patient_insurance_screen),
        ).pack(anchor="w", pady=(10, 0))
        label(
            body,
            "Your private patient workspace  ·  Offline coursework prototype",
            8,
            color=MUTED,
        ).pack(anchor="w", pady=(6, 10))

    def patient_appointments_screen(self):
        frame = self.page(
            "My appointments",
            "Only your appointments are listed. Book a free slot, or reschedule/cancel a future Booked appointment.",
        )
        bar = ttk.Frame(frame)
        bar.pack(fill="x")
        rows = self.service.my_appointments()
        tree = self.tree(
            frame,
            ("appointment_id", "date", "start_time", "doctor", "status", "reason"),
            rows,
        )

        def selected_row():
            aid = int(self.selected(tree)["appointment_id"])
            return next(a for a in rows if a["appointment_id"] == aid)

        def reschedule():
            row = selected_row()
            if (
                row["status"] != "Booked"
                or datetime.fromisoformat(row["date"] + "T" + row["start_time"])
                <= self.service.clock()
            ):
                raise ClinicError(
                    "Only a future Booked appointment can be rescheduled here. Contact reception."
                )
            self.patient_booking_form(row, self.patient_appointments_screen)

        def cancel():
            row = selected_row()
            if messagebox.askyesno(
                "Cancel appointment",
                "Cancel this appointment? The slot will be released.",
                parent=self.root,
            ):
                self.service.cancel_my_appointment(row["appointment_id"])
                self.patient_appointments_screen()

        self.button(
            bar,
            "Book an appointment",
            lambda: self.patient_booking_form(None, self.patient_appointments_screen),
        )
        self.button(bar, "Reschedule my appointment", reschedule)
        self.button(bar, "Cancel my appointment", cancel)
        self.button(bar, "Refresh", self.patient_appointments_screen)

    def patient_booking_form(self, old, refresh):
        choices = {
            f'Dr {d["first_name"]} {d["last_name"]} ({d["doctor_id"]})': d["doctor_id"]
            for d in self.service.portal_doctors()
        }
        if not choices:
            raise ClinicError("No doctors are available yet. Contact reception.")
        window, frame = self.dialog(
            "Reschedule my appointment" if old else "Book my appointment"
        )
        window.geometry("850x760")
        window.minsize(800, 720)
        inputs = self.fields(
            frame, ["doctor", "reason"],
            {"reason": old["reason"] if old else ""},
            {"doctor": list(choices)},
        )
        if old:
            inputs["doctor"].set(next(
                (k for k, v in choices.items() if v == old["doctor_id"]),
                list(choices)[0],
            ))
        picker = None
        loaded_doctor = None

        def selected():
            if picker is not None:
                save_button.configure(state="normal" if picker.selected_time else "disabled")

        def available(day):
            return self.service.my_free_slots(
                choices[inputs["doctor"].get()], day,
                old["appointment_id"] if old else None,
            )

        def save():
            if not picker.selected_time or loaded_doctor != inputs["doctor"].get():
                raise ClinicError("Choose a date and an available time first.")
            day = picker.day.isoformat()
            try:
                aid = self.service.book_for_me(
                    choices[inputs["doctor"].get()], day, picker.selected_time,
                    inputs["reason"].get(), old["appointment_id"] if old else None,
                )
            except ClinicError:
                picker.refresh()
                raise
            messagebox.showinfo(
                "Appointment confirmed",
                f"Appointment {aid}: {day} at {picker.selected_time}.", parent=window,
            )
            window.destroy()
            refresh()

        bar = ttk.Frame(frame)
        bar.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(22, 6))
        save_button = self.button(bar, "Confirm my booking", save)
        save_button.configure(style="Primary.TButton", state="disabled")
        self.button(bar, "Close", window.destroy)
        picker = BookingPicker(
            frame,
            old["date"] if old else self.service.clock().date().isoformat(),
            self.service.clock().date(), available, selected, guard=self.guarded,
        )
        picker.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(22, 0))
        # Exposed for widget-level tests and assistive integrations.
        window.booking_picker = picker
        loaded_doctor = inputs["doctor"].get()

        def doctor_changed(_event=None):
            nonlocal loaded_doctor
            loaded_doctor = inputs["doctor"].get()
            picker.refresh()

        inputs["doctor"].bind("<<ComboboxSelected>>", lambda e: self.guarded(doctor_changed)())
        ttk.Label(
            frame,
            text="Choose a highlighted date, then a time. Availability is checked again when you confirm.\nUse a short administrative reason; keep medical notes for your consultation.",
            style="Small.TLabel", wraplength=720,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=12)

    def patient_details_screen(self):
        profile = self.service.my_profile()
        frame = self.page(
            "Personal details",
            "Keep your contact details current. Reception handles changes to your name, identity number and date of birth.",
        )
        text = f'{profile["first_name"]} {profile["last_name"]}  ·  PT-{profile["patient_id"]:05d}\nDate of birth: {profile["date_of_birth"]}  ·  Gender: {profile["gender"] or "Not provided"}'
        text += f'\n{profile["id_type"]}: {profile["id_number"]}'
        ttk.Label(frame, text=text, style="Title.TLabel", wraplength=650).pack(
            anchor="w", pady=(0, 20)
        )
        form = ttk.Frame(frame)
        form.pack(fill="x")
        inputs = self.fields(
            form,
            ["phone", "email", "address", "next_of_kin_name", "next_of_kin_phone"],
            profile,
        )

        def save():
            self.service.update_my_contact(self.values(inputs))
            messagebox.showinfo(
                "Saved",
                "Your personal contact details have been updated.",
                parent=self.root,
            )

        bar = ttk.Frame(frame)
        bar.pack(fill="x", pady=12)
        self.button(bar, "Save my details", save)

    def patient_insurance_screen(self):
        frame = self.page(
            "Medical insurance",
            "Optional patient-supplied information. These details do not verify cover or process a medical-aid claim.",
        )
        form = ttk.Frame(frame)
        form.pack(fill="x")
        inputs = self.fields(
            form,
            [
                "insurance_provider",
                "insurance_plan",
                "membership_number",
                "member_type",
            ],
            self.service.my_insurance(),
            {"member_type": ["", "Principal member", "Dependant", "Self-paying"]},
        )

        def save():
            self.service.update_my_insurance(self.values(inputs))
            messagebox.showinfo(
                "Saved",
                "Your medical insurance details have been updated.",
                parent=self.root,
            )
            self.patient_insurance_screen()

        bar = ttk.Frame(frame)
        bar.pack(fill="x", pady=12)
        self.button(bar, "Save medical insurance", save)

    def patient_visits_screen(self):
        frame = self.page(
            "Visit summaries",
            "Your recorded diagnoses, treatment and follow-up dates. Ask reception to book a follow-up; the date alone does not create an appointment.",
        )
        text = tk.Text(
            frame, wrap="word", font=(FONT, 11), borderwidth=0, padx=14, pady=14
        )
        scroll = SlimScrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        rows = self.service.my_visit_summaries()
        for row in rows:
            text.insert(
                "end",
                f'{row["visit_date"]} · {row["clinician"]}\nDiagnosis: {row["diagnosis"] or "Not recorded"}\nTreatment: {row["treatment"] or "Not recorded"}\nFollow-up date: {row["follow_up_date"] or "None recorded"}\n\n',
            )
        if not rows:
            text.insert("end", "No completed visit summaries are available yet.")
        text.configure(state="disabled")
