"""Sunrise visual theme and small vector components, using only Tk/ttk."""

import tkinter as tk
from tkinter import ttk

TEAL = "#087F82"
INK = "#193E43"
MUTED = "#6B8083"
BG = "#F3F7F7"
PALE = "#E5F3EF"
LINE = "#DFE8E7"
WHITE = "#FFFFFF"
GOLD = "#EAC681"
FONT = "Arial"


def configure_theme(root):
    """Apply the same palette on Mac, Windows and Linux through built-in clam."""
    root.configure(background=BG)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", font=(FONT, 11), background=WHITE, foreground=INK)
    style.configure("TFrame", background=WHITE)
    style.configure("Workspace.TFrame", background=BG)
    style.configure("TLabel", background=WHITE, foreground=INK)
    style.configure("Title.TLabel", font=(FONT, 21, "bold"), foreground=INK)
    style.configure("PageTitle.TLabel", font=(FONT, 23, "bold"), background=BG)
    style.configure(
        "PageSmall.TLabel", font=(FONT, 10), foreground=MUTED, background=BG
    )
    style.configure("Small.TLabel", font=(FONT, 9), foreground=MUTED)
    style.configure(
        "TButton",
        padding=(14, 9),
        borderwidth=1,
        relief="flat",
        background=WHITE,
        foreground=TEAL,
        bordercolor=LINE,
        focuscolor=TEAL,
        font=(FONT, 10, "bold"),
    )
    style.map(
        "TButton",
        background=[("disabled", "#F0F3F2"), ("pressed", "#D7ECE7"), ("active", PALE)],
        foreground=[("disabled", "#9BA9A8")],
        bordercolor=[("focus", TEAL)],
    )
    style.configure(
        "Primary.TButton",
        background=TEAL,
        foreground=WHITE,
        borderwidth=0,
        padding=(18, 12),
        font=(FONT, 10, "bold"),
        focuscolor=INK,
    )
    style.map(
        "Primary.TButton",
        background=[
            ("disabled", "#A7C8C4"),
            ("pressed", "#056164"),
            ("active", "#096D70"),
        ],
        foreground=[("disabled", WHITE), ("active", WHITE)],
    )
    style.configure(
        "Nav.TButton",
        anchor="w",
        background=WHITE,
        foreground=MUTED,
        borderwidth=0,
        padding=(16, 13),
        font=(FONT, 10),
    )
    style.map("Nav.TButton", background=[("active", "#F1F7F5"), ("pressed", PALE)])
    style.configure(
        "Selected.Nav.TButton",
        background=PALE,
        foreground=TEAL,
        font=(FONT, 10, "bold"),
    )
    style.map(
        "Selected.Nav.TButton",
        background=[("active", "#DCEFE9"), ("pressed", "#D1E8E2")],
    )
    style.configure(
        "Link.TButton",
        padding=(7, 6),
        borderwidth=0,
        background=WHITE,
        foreground=TEAL,
        font=(FONT, 9, "bold"),
    )
    style.map("Link.TButton", background=[("active", PALE), ("pressed", "#D1E8E2")])
    style.configure(
        "TEntry",
        padding=(9, 6),
        fieldbackground=WHITE,
        bordercolor=LINE,
        lightcolor=LINE,
        darkcolor=LINE,
        insertcolor=TEAL,
    )
    style.map("TEntry", bordercolor=[("focus", TEAL)], lightcolor=[("focus", TEAL)])
    style.configure("Login.TEntry", padding=(12, 11), borderwidth=0, relief="flat")
    style.configure(
        "TCombobox",
        padding=(8, 6),
        fieldbackground=WHITE,
        background=WHITE,
        bordercolor=LINE,
        arrowcolor=TEAL,
        arrowsize=13,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", WHITE)],
        foreground=[("readonly", INK)],
        selectbackground=[("readonly", PALE)],
        selectforeground=[("readonly", INK)],
    )
    style.configure(
        "Treeview",
        background=WHITE,
        fieldbackground=WHITE,
        foreground=INK,
        bordercolor=LINE,
        borderwidth=0,
        rowheight=38,
        font=(FONT, 10),
    )
    style.configure(
        "Treeview.Heading",
        font=(FONT, 9, "bold"),
        background="#EDF5F2",
        foreground=INK,
        padding=(10, 11),
        relief="flat",
        borderwidth=0,
    )
    style.map(
        "Treeview", background=[("selected", "#DDEFE9")], foreground=[("selected", INK)]
    )
    style.map("Treeview.Heading", background=[("active", "#E3EEEB")])
    style.configure(
        "Vertical.TScrollbar",
        background="#D8E5E1",
        troughcolor=WHITE,
        borderwidth=0,
        arrowsize=12,
    )
    style.configure(
        "Horizontal.TScrollbar",
        background="#D8E5E1",
        troughcolor=WHITE,
        borderwidth=0,
        arrowsize=12,
    )
    style.configure("TNotebook", background=WHITE, borderwidth=0)
    style.configure("TNotebook.Tab", padding=(16, 10), background="#F0F5F3")
    style.map(
        "TNotebook.Tab",
        background=[("selected", PALE)],
        foreground=[("selected", TEAL)],
    )
    root.option_add("*Text.background", WHITE)
    root.option_add("*Text.foreground", INK)
    root.option_add("*Text.insertBackground", TEAL)
    root.option_add("*Listbox.background", WHITE)
    root.option_add("*Listbox.foreground", INK)
    return style


def label(parent, text, size=11, color=INK, bold=False, **kwargs):
    """Text on the containing surface, without an unrelated label background."""
    bg = (
        parent.cget("background")
        if isinstance(parent, (tk.Frame, tk.Canvas))
        else WHITE
    )
    kwargs.setdefault("justify", "left")
    kwargs.setdefault("anchor", "w")
    return tk.Label(
        parent,
        text=text,
        font=(FONT, size, "bold" if bold else "normal"),
        fg=color,
        bg=bg,
        **kwargs,
    )


def rounded(canvas, x1, y1, x2, y2, radius=14, **kwargs):
    points = [
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)


class Panel(tk.Canvas):
    """Resizable rounded surface containing ordinary accessible Tk widgets."""

    def __init__(self, parent, fill=WHITE, padding=20, stretch=False, **kwargs):
        super().__init__(
            parent, background=BG, highlightthickness=0, height=100, **kwargs
        )
        self.fill, self.padding, self.stretch = fill, padding, stretch
        self.body = tk.Frame(self, background=fill)
        self._window = self.create_window(
            padding, padding, anchor="nw", window=self.body
        )
        self.bind("<Configure>", self._resize)
        self.body.bind("<Configure>", self._body_resize)

    def _body_resize(self, _event=None):
        if not self.stretch:
            desired = self.body.winfo_reqheight() + self.padding * 2
            if abs(self.winfo_reqheight() - desired) > 1:
                self.configure(height=desired)

    def _resize(self, event):
        w, h = event.width, event.height
        self.delete("surface")
        rounded(
            self,
            1,
            1,
            max(2, w - 1),
            max(2, h - 1),
            18,
            fill=self.fill,
            outline=LINE,
            tags="surface",
        )
        self.tag_lower("surface")
        self.itemconfigure(self._window, width=max(1, w - self.padding * 2))
        if self.stretch:
            self.itemconfigure(self._window, height=max(1, h - self.padding * 2))


def brand(parent, background=WHITE):
    row = tk.Frame(parent, bg=background)
    icon = tk.Canvas(row, width=40, height=40, bg=background, highlightthickness=0)
    icon.pack(side="left", padx=(0, 10))
    rounded(icon, 0, 0, 40, 40, 12, fill=TEAL, outline="")
    icon.create_line(20, 11, 20, 29, fill=WHITE, width=2)
    icon.create_line(11, 20, 29, 20, fill=WHITE, width=2)
    words = tk.Frame(row, bg=background)
    words.pack(side="left")
    label(words, "sunrise.", 22, bold=True).pack(anchor="w")
    label(words, "COMMUNITY CLINIC", 7, color=MUTED).pack(anchor="w")
    return row


def draw_login_art(canvas):
    """Draw the reference-inspired clinic illustration as resolution-free vectors."""
    canvas.delete("all")
    w, h = canvas.winfo_width(), canvas.winfo_height()
    if w < 20:
        return
    bg = "#ECF6F3"
    canvas.configure(background=bg)
    x = 44
    rounded(canvas, x, 36, x + 40, 76, 12, fill=TEAL, outline="")
    canvas.create_text(x + 20, 55, text="+", font=(FONT, 26), fill=WHITE)
    canvas.create_text(
        x + 52, 49, text="sunrise.", font=(FONT, 23, "bold"), anchor="w", fill=INK
    )
    canvas.create_text(
        x + 53, 73, text="COMMUNITY CLINIC", font=(FONT, 8), anchor="w", fill=MUTED
    )
    hero = max(145, int(h * 0.27))
    canvas.create_text(
        x,
        hero,
        text="CONNECTED CARE. SIMPLIFIED.",
        font=(FONT, 8, "bold"),
        anchor="w",
        fill=TEAL,
    )
    canvas.create_text(
        x,
        hero + 33,
        text="A good day of care",
        font=(FONT, 32, "bold"),
        anchor="nw",
        fill=INK,
    )
    canvas.create_text(
        x,
        hero + 81,
        text="starts here.",
        font=(FONT, 32, "bold"),
        anchor="nw",
        fill=TEAL,
    )
    canvas.create_text(
        x,
        hero + 151,
        text="One familiar workspace for patient details, appointments\nand better organised care.",
        font=(FONT, 11),
        anchor="nw",
        fill=MUTED,
        width=w - 80,
    )
    center = min(w * 0.43, 255)
    cy = min(hero + 330, h - 158)
    scale = min(1.0, (w - 95) / 440)

    def box(a, b, c, d, **kw):
        return canvas.create_rectangle(
            center + a * scale, cy + b * scale, center + c * scale, cy + d * scale, **kw
        )

    canvas.create_oval(
        center - 135 * scale,
        cy - 125 * scale,
        center + 135 * scale,
        cy + 145 * scale,
        outline="#D4E7DF",
        width=1,
    )
    canvas.create_oval(
        center - 110 * scale,
        cy - 101 * scale,
        center + 110 * scale,
        cy + 124 * scale,
        fill="#E2F0E9",
        outline="",
    )
    rounded(
        canvas,
        center - 115 * scale,
        cy - 55 * scale,
        center + 115 * scale,
        cy + 112 * scale,
        10,
        fill=WHITE,
        outline="#D6E6DF",
    )
    rounded(
        canvas,
        center - 115 * scale,
        cy - 55 * scale,
        center + 115 * scale,
        cy - 17 * scale,
        10,
        fill=TEAL,
        outline="",
    )
    canvas.create_text(
        center,
        cy - 37 * scale,
        text="SUNRISE COMMUNITY CLINIC",
        fill=WHITE,
        font=(FONT, 7, "bold"),
    )
    rounded(
        canvas,
        center - 21 * scale,
        cy - 75 * scale,
        center + 21 * scale,
        cy - 33 * scale,
        11,
        fill=WHITE,
        outline="",
    )
    canvas.create_text(center, cy - 55 * scale, text="+", fill=TEAL, font=(FONT, 23))
    box(-18, 45, 18, 112, fill="#DDEFE8", outline="#E7F3EE")
    box(11, 71, 13, 82, fill="#78A99D", outline="")
    box(-82, 20, -47, 56, fill="#E6F4EE", outline="#F2F7F5")
    box(48, 20, 83, 56, fill="#E6F4EE", outline="#F2F7F5")
    for wx in [-65, 65]:
        canvas.create_line(
            center + wx * scale,
            cy + 21 * scale,
            center + wx * scale,
            cy + 55 * scale,
            fill=WHITE,
            width=2,
        )
    for tx, ty in [(-145, 70), (147, 61)]:
        box(tx - 2, ty, tx + 2, 112, fill="#85B4A1", outline="")
        canvas.create_oval(
            center + (tx - 16) * scale,
            cy + (ty - 28) * scale,
            center + (tx + 16) * scale,
            cy + (ty + 12) * scale,
            fill="#C7DFC6",
            outline="",
        )
    canvas.create_line(
        center - 165 * scale,
        cy + 113 * scale,
        center + 165 * scale,
        cy + 113 * scale,
        fill="#B8D4C8",
    )
    canvas.create_oval(
        center + 142 * scale,
        cy - 83 * scale,
        center + 163 * scale,
        cy - 62 * scale,
        fill=GOLD,
        outline="",
    )
    rounded(
        canvas,
        center - 176 * scale,
        cy + 1 * scale,
        center - 18 * scale,
        cy + 47 * scale,
        9,
        fill=WHITE,
        outline="#E1EAE4",
    )
    canvas.create_text(
        center - 161 * scale,
        cy + 16 * scale,
        text="Every visit matters.",
        anchor="w",
        fill=INK,
        font=(FONT, 9, "bold"),
    )
    canvas.create_text(
        center - 161 * scale,
        cy + 32 * scale,
        text="Simple tools. More time for people.",
        anchor="w",
        fill=MUTED,
        font=(FONT, 7),
    )
    canvas.create_oval(x, h - 35, x + 5, h - 30, fill="#3A9F86", outline="")
    canvas.create_text(
        x + 12,
        h - 32,
        text="Designed for your clinic. Available offline.",
        anchor="w",
        fill=MUTED,
        font=(FONT, 8),
    )
