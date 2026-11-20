"""Keyboard-accessible calendar and appointment-time buttons using standard Tk."""

import calendar
from datetime import date
import tkinter as tk
from tkinter import ttk

from .theme import WHITE, MUTED, TEAL, PALE, FONT, SlimScrollbar


class BookingPicker(ttk.Frame):
    """Shows service-provided availability; a time always needs an explicit click."""

    def __init__(self, parent, day, today, availability, changed, guard=lambda f: f):
        super().__init__(parent)
        self.guard = guard
        self.today = today
        self.availability = availability
        self.changed = changed
        self.selected_time = ""
        self.day = date.fromisoformat(day)
        self.month = self.day.replace(day=1)
        self.cache = {}
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.calendar_frame = ttk.Frame(self, padding=(0, 0, 22, 0))
        self.calendar_frame.grid(row=0, column=0, sticky="nsew")
        times = ttk.Frame(self)
        times.grid(row=0, column=1, sticky="nsew")
        ttk.Label(times, text="2  Choose a time", font=(FONT, 12, "bold")).pack(anchor="w", pady=(0, 12))
        self.time_caption = ttk.Label(times, style="Small.TLabel", wraplength=300)
        self.time_caption.pack(anchor="w", pady=(0, 12))
        viewport = ttk.Frame(times)
        viewport.pack(fill="both", expand=True)
        self.time_canvas = tk.Canvas(viewport, bg=WHITE, highlightthickness=0, height=252)
        scroll = SlimScrollbar(viewport, orient="vertical", command=self.time_canvas.yview)
        scroll.pack(side="right", fill="y")
        self.time_canvas.pack(side="left", fill="both", expand=True)
        self.time_canvas.configure(yscrollcommand=scroll.set)
        self.time_grid = ttk.Frame(self.time_canvas)
        handle = self.time_canvas.create_window(0, 0, anchor="nw", window=self.time_grid)
        self.time_canvas.bind("<Configure>", lambda e: self.time_canvas.itemconfigure(handle, width=e.width))
        self.time_grid.bind("<Configure>", lambda e: self.time_canvas.configure(scrollregion=self.time_canvas.bbox("all")))
        self.time_grid.columnconfigure((0, 1), weight=1, uniform="time")
        self.summary = ttk.Label(self, text="Choose a date and an available time.", foreground=TEAL, wraplength=670)
        self.summary.grid(row=1, column=0, columnspan=2, sticky="w", pady=(18, 0))
        self.refresh()

    def slots(self, day):
        key = day.isoformat()
        if key not in self.cache:
            self.cache[key] = list(self.availability(key)) if day >= self.today else []
        return self.cache[key]

    def refresh(self):
        self.cache.clear()
        self.selected_time = ""
        self.draw_calendar()
        self.draw_times()
        self.changed()

    def move_month(self, step):
        index = self.month.year * 12 + self.month.month - 1 + step
        if not 12 <= index <= 9999 * 12 - 1:
            return
        self.month = date(index // 12, index % 12 + 1, 1)
        self.draw_calendar()

    def choose_day(self, day):
        self.day = day
        self.month = day.replace(day=1)
        self.selected_time = ""
        self.draw_calendar()
        self.draw_times()
        self.changed()

    def draw_calendar(self):
        for child in self.calendar_frame.winfo_children():
            child.destroy()
        head = ttk.Frame(self.calendar_frame)
        head.pack(fill="x")
        ttk.Label(head, text="1  Choose a date", font=(FONT, 12, "bold")).pack(side="left")
        nav = ttk.Frame(self.calendar_frame)
        nav.pack(fill="x", pady=(12, 8))
        previous = ttk.Button(nav, text="‹", width=3, command=self.guard(lambda: self.move_month(-1)))
        previous.pack(side="left")
        if self.month <= self.today.replace(day=1):
            previous.state(["disabled"])
        ttk.Label(nav, text=self.month.strftime("%B %Y"), anchor="center", font=(FONT, 11, "bold")).pack(side="left", fill="x", expand=True)
        ttk.Button(nav, text="›", width=3, command=self.guard(lambda: self.move_month(1))).pack(side="right")
        grid = ttk.Frame(self.calendar_frame)
        grid.pack(fill="x")
        self.day_buttons = {}
        for col, name in enumerate(("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")):
            grid.columnconfigure(col, weight=1, uniform="day")
            ttk.Label(grid, text=name, anchor="center", foreground=MUTED).grid(row=0, column=col, pady=5)
        for row, week in enumerate(calendar.monthcalendar(self.month.year, self.month.month), 1):
            for col, number in enumerate(week):
                if not number:
                    continue
                day = self.month.replace(day=number)
                available = bool(self.slots(day))
                button = ttk.Button(grid, text=str(number), width=3, style="Selected.Day.TButton" if day == self.day else "Day.TButton", command=self.guard(lambda d=day: self.choose_day(d)))
                button.grid(row=row, column=col, sticky="ew", padx=1, pady=2)
                if not available:
                    button.state(["disabled"])
                self.day_buttons[day.isoformat()] = button
        ttk.Label(self.calendar_frame, text="Teal: selected  ·  Grey: unavailable", style="Small.TLabel").pack(anchor="w", pady=(12, 0))

    def draw_times(self):
        for child in self.time_grid.winfo_children():
            child.destroy()
        self.time_buttons = {}
        self.time_canvas.yview_moveto(0)
        self.time_caption.configure(text=self.day.strftime("%A, %d %B %Y"))
        values = self.slots(self.day)
        if not values:
            ttk.Label(self.time_grid, text="No available times on this date.\nChoose another highlighted date.", wraplength=270, foreground=MUTED).grid(row=0, column=0, columnspan=2, sticky="w", pady=14)
        for index, value in enumerate(values):
            button = ttk.Button(self.time_grid, text=value, command=self.guard(lambda v=value: self.choose_time(v)), style="Time.TButton")
            button.grid(row=index // 2, column=index % 2, sticky="ew", padx=3, pady=4)
            self.time_buttons[value] = button
        self.summary.configure(text="Choose an available time to continue.")

    def choose_time(self, value):
        if value not in self.slots(self.day):
            return
        self.selected_time = value
        for time, button in self.time_buttons.items():
            button.configure(style="Selected.Time.TButton" if time == value else "Time.TButton")
        self.summary.configure(text=self.day.strftime("%A, %d %B %Y") + "  ·  " + value)
        self.changed()
