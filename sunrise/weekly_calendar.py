"""Weekly staff timetable backed by the same appointments patients book."""

from datetime import date, timedelta
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

from .services import ClinicError
from .theme import FONT, INK, LINE, MUTED, PALE, TEAL, WHITE, SlimScrollbar, rounded


def monday_for(day):
    return day - timedelta(days=day.weekday())


def time_minutes(value):
    hours, minutes = map(int, value.split(":"))
    return hours * 60 + minutes


def arrange_events(rows):
    """Allocate side-by-side lanes for overlapping bookings on the same day."""
    result, cluster, ends = [], [], []

    def finish():
        result.extend((row, lane, len(ends)) for row, lane in cluster)

    for row in sorted(rows, key=lambda r: (r["start_time"], r["doctor_id"], r["appointment_id"])):
        start = time_minutes(row["start_time"])
        if ends and start >= max(ends):
            finish()
            cluster, ends = [], []
        lane = next((i for i, end in enumerate(ends) if end <= start), len(ends))
        end = start + row["duration_minutes"]
        if lane == len(ends):
            ends.append(end)
        else:
            ends[lane] = end
        cluster.append((row, lane))
    if cluster:
        finish()
    return result


class WeeklyCalendar(ttk.Frame):
    """Seven-day timetable with week navigation, agenda and periodic refresh."""

    def __init__(self, parent, service, guard):
        super().__init__(parent, padding=16)
        self.service, self.guard = service, guard
        self.viewer_role = service.user["role"]
        self.week = monday_for(service.clock().date())
        self.rows = []
        self.timer = None
        self.next_row = None
        self.all_rows = []
        self.show_cancelled = tk.BooleanVar(value=False)
        heading = ttk.Frame(self)
        heading.pack(fill="x")
        ttk.Label(heading, text="Your weekly appointments" if service.user["role"] == "Doctor" else "Clinic weekly appointments", font=(FONT, 16, "bold")).pack(side="left")
        ttk.Button(heading, text="Refresh calendar", command=guard(self.refresh)).pack(side="right")
        nav = ttk.Frame(self)
        nav.pack(fill="x", pady=(14, 10))
        for text, command in [("‹ Previous", lambda: self.shift(-7)), ("This week", self.today), ("Next ›", lambda: self.shift(7))]:
            ttk.Button(nav, text=text, command=guard(command)).pack(side="left", padx=(0, 6))
        self.week_label = ttk.Label(nav, font=(FONT, 10, "bold"))
        self.week_label.pack(side="left", padx=8)
        ttk.Button(nav, text="Next booking", command=guard(self.jump_next)).pack(side="right")
        options = ttk.Frame(self)
        options.pack(fill="x", pady=(0, 10))
        self.doctor_options = {"All doctors": None}
        if service.user["role"] != "Doctor":
            self.doctor_options.update({f"Dr {d['first_name']} {d['last_name']} ({d['doctor_id']})": d["doctor_id"] for d in service.doctors(False)})
            self.doctor_filter = ttk.Combobox(options, values=list(self.doctor_options), state="readonly", width=28)
            self.doctor_filter.set("All doctors")
            self.doctor_filter.pack(side="left", padx=(0, 12))
            self.doctor_filter.bind("<<ComboboxSelected>>", lambda e: guard(self.refresh)())
        else:
            self.doctor_filter = None
            ttk.Label(options, text="Your assigned patients only", foreground=TEAL).pack(side="left")
        ttk.Checkbutton(options, text="Show cancelled", variable=self.show_cancelled, command=guard(self.refresh)).pack(side="right")
        self.status = ttk.Label(self, style="Small.TLabel", wraplength=900)
        self.status.pack(fill="x", pady=(0, 10))
        self.status.bind("<Configure>", lambda e: self.status.configure(wraplength=max(280, e.width)))
        holder = ttk.Frame(self)
        holder.pack(fill="x")
        holder.columnconfigure(0, weight=1)
        holder.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(holder, height=365, bg=WHITE, highlightthickness=0, takefocus=True)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vertical = SlimScrollbar(holder, command=self.canvas.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = SlimScrollbar(holder, orient="horizontal", command=self.canvas.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        def scroll_changed(first, last):
            vertical.set(first, last)
            self.draw_headers()
        self.canvas.configure(yscrollcommand=scroll_changed, xscrollcommand=horizontal.set)
        self.canvas.bind("<Configure>", self.draw)
        self.canvas.bind("<Button-1>", self.open_card)
        self.canvas.bind("<Return>", lambda e: guard(self.agenda)())
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", pady=(10, 0))
        ttk.Label(bottom, text="Click a booking for details · Colours identify doctors", style="Small.TLabel").pack(side="left")
        ttk.Button(bottom, text="Week agenda", command=guard(self.agenda)).pack(side="right")
        self.bind("<Destroy>", self.stop, add="+")
        self.refresh()
        self.schedule_poll()

    def doctor_id(self):
        return self.doctor_options[self.doctor_filter.get()] if self.doctor_filter else None

    def shift(self, days):
        self.week += timedelta(days=days)
        self.refresh()
        self.canvas.yview_moveto(0)

    def today(self):
        self.week = monday_for(self.service.clock().date())
        self.refresh()

    def jump_next(self):
        self.next_row = self.service.next_staff_appointment(self.doctor_id())
        if self.next_row:
            self.week = monday_for(date.fromisoformat(self.next_row["date"]))
            self.refresh()
            minute = time_minutes(self.next_row["start_time"])
            y = 48 + (minute - self.start_minute) * 2.8
            self.canvas.yview_moveto(max(0, (y - 100) / (self.timeline_height + 14)))
        else:
            messagebox.showinfo("Next booking", "No upcoming appointments for this view.", parent=self.winfo_toplevel())

    def refresh(self):
        self.service.touch()
        if self.service.user["role"] != self.viewer_role:
            raise ClinicError("Your role changed. Please sign in again.")
        self.all_rows = self.service.weekly_appointments(self.week.isoformat(), self.doctor_id())
        self.rows = [r for r in self.all_rows if self.show_cancelled.get() or r["status"] != "Cancelled"]
        self.next_row = self.service.next_staff_appointment(self.doctor_id())
        self.week_label.configure(text=f"{self.week:%d %b} – {self.week + timedelta(days=6):%d %b %Y}")
        text = f"{len(self.rows)} appointments this week. "
        if self.next_row:
            row = self.next_row
            text += f"Next: {row['date']} at {row['start_time']} · {row['patient']} · Dr {row['doctor']}."
        else:
            text += "No upcoming bookings."
        self.status.configure(text=text)
        self.draw()

    def schedule_poll(self):
        self.timer = self.after(15000, self.poll)

    def poll(self):
        self.timer = None
        # A background read must not extend an idle authenticated session.
        activity = self.service.last_activity
        user = self.service.user
        try:
            self.refresh()
        except (ClinicError, OSError, sqlite3.Error):
            self.status.configure(text="Calendar refresh paused. Use Refresh calendar or sign in again.")
        finally:
            if self.service.user and user and self.service.user["user_id"] == user["user_id"]:
                self.service.last_activity = activity
        if self.winfo_exists():
            self.schedule_poll()

    def stop(self, event):
        if event.widget is self and self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None

    def draw(self, _event=None):
        canvas = self.canvas
        canvas.delete("all")
        width = max(1030, canvas.winfo_width())
        left, header = 58, 48
        col_width = (width - left) / 7
        start = min([480] + [time_minutes(r["start_time"]) // 60 * 60 for r in self.rows])
        end = max([1020] + [((time_minutes(r["start_time"]) + r["duration_minutes"] + 59) // 60) * 60 for r in self.rows])
        scale = 2.8  # Even a five-minute appointment remains a distinct clickable block.
        height = header + (end - start) * scale
        self.start_minute, self.timeline_height = start, height
        self.header_width, self.header_col_width = width, col_width
        self.event_cards = {}
        for index in range(7):
            day = self.week + timedelta(days=index)
            x = left + index * col_width
            canvas.create_rectangle(x, 0, x + col_width, height, fill=PALE if day == self.service.clock().date() else WHITE, outline=LINE)
            canvas.create_text(x + col_width / 2, 23, text=day.strftime("%a  %d %b"), fill=TEAL if day == self.service.clock().date() else INK, font=(FONT, 10, "bold"))
        for minute in range(start, end + 1, 30):
            y = header + (minute - start) * scale
            canvas.create_line(left, y, width, y, fill=LINE if minute % 60 == 0 else "#F1F5F4")
            if minute % 60 == 0:
                canvas.create_text(left - 6, y + 8, text=f"{minute // 60:02}:{minute % 60:02}", anchor="e", fill=MUTED, font=(FONT, 8))
        colors = ["#D6EFEB", "#DCEAF8", "#E9E2F5", "#F8E7CD"]
        for index in range(7):
            day_rows = [r for r in self.rows if r["date"] == (self.week + timedelta(days=index)).isoformat()]
            for row, lane, lanes in arrange_events(day_rows):
                x = left + index * col_width + lane * col_width / lanes + 3
                y = header + (time_minutes(row["start_time"]) - start) * scale + 1
                w = col_width / lanes - 6
                h = max(12, row["duration_minutes"] * scale - 3)
                tag = f"appointment-{row['appointment_id']}"
                fill = "#ECEFEE" if row["status"] == "Cancelled" else colors[row["doctor_id"] % len(colors)]
                rounded(canvas, x, y, x + w, y + h, radius=min(5, h / 3), fill=fill, outline="", tags=(tag,))
                text = row["start_time"]
                if h >= 30:
                    text += "\n" + row["patient"][:max(3, int(w / 7))]
                if h >= 58:
                    text += "\nDr " + row["doctor"][:max(3, int(w / 7) - 3)]
                if h >= 78:
                    text += "\n" + row["status"]
                canvas.create_text(x + 5, y + 3, text=text, anchor="nw", width=max(1, w - 10), fill=INK, font=(FONT, 8), tags=(tag,))
                self.event_cards[tag] = row
        canvas.configure(scrollregion=(0, 0, width, height + 14))
        self.draw_headers()

    def draw_headers(self):
        if not hasattr(self, "header_width"):
            return
        canvas = self.canvas
        canvas.delete("fixed-header")
        y = canvas.canvasy(0)
        canvas.create_rectangle(0, y, self.header_width, y + 48, fill=WHITE, outline=LINE, tags="fixed-header")
        for index in range(7):
            day = self.week + timedelta(days=index)
            x = 58 + (index + .5) * self.header_col_width
            canvas.create_text(x, y + 24, text=day.strftime("%a  %d %b"), fill=TEAL if day == self.service.clock().date() else INK, font=(FONT, 10, "bold"), tags="fixed-header")

    def open_card(self, event):
        if event.y < 48:
            return
        items = self.canvas.find_overlapping(self.canvas.canvasx(event.x), self.canvas.canvasy(event.y), self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        for item in reversed(items):
            for tag in self.canvas.gettags(item):
                if tag in self.event_cards:
                    return self.guard(lambda: self.details(self.event_cards[tag]))()

    def details(self, row):
        # Query again so an open calendar cannot show another role's stale record.
        fresh = next((r for r in self.service.weekly_appointments(row["date"], self.doctor_id()) if r["appointment_id"] == row["appointment_id"]), None)
        if fresh is None:
            raise ClinicError("This appointment is no longer available in your view.")
        messagebox.showinfo("Appointment details", f"{fresh['patient']}\n{fresh['date']} at {fresh['start_time']} ({fresh['duration_minutes']} minutes)\nDr {fresh['doctor']}\nStatus: {fresh['status']}\nBooking number: {fresh['appointment_id']}\nReason: {fresh['reason'] or 'Not provided'}", parent=self.winfo_toplevel())

    def agenda(self):
        self.refresh()
        window = tk.Toplevel(self.winfo_toplevel())
        window.title("Week agenda")
        window.geometry("850x450")
        window.transient(self.winfo_toplevel())
        tree = ttk.Treeview(window, columns=("date", "time", "patient", "doctor", "status"), show="headings")
        for name in tree["columns"]:
            tree.heading(name, text=name.title())
            tree.column(name, width=145, stretch=True)
        scroll = SlimScrollbar(window, command=tree.yview)
        scroll.pack(side="right", fill="y")
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(fill="both", expand=True, padx=14, pady=14)
        for row in self.rows:
            tree.insert("", "end", iid=str(row["appointment_id"]), values=(row["date"], row["start_time"], row["patient"], "Dr " + row["doctor"], row["status"]))
        def show(_event=None):
            if tree.selection():
                row = next(r for r in self.rows if str(r["appointment_id"]) == tree.selection()[0])
                self.guard(lambda: self.details(row))()
        tree.bind("<Double-1>", show)
        tree.bind("<Return>", show)
        window.grab_set()
