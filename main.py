"""Launch the offline desktop application and select its data directory."""

import argparse
from datetime import datetime, time
import os
from pathlib import Path
import sys
import sqlite3
import tkinter as tk
from tkinter import messagebox

from sunrise.services import ClinicService, parse_date
from sunrise.ui import ClinicApp


def arguments(argv=None):
    """Validate demonstration settings before opening or creating any database."""
    parser = argparse.ArgumentParser(
        description="Sunrise Community Clinic coursework prototype"
    )
    parser.add_argument(
        "--demo", action="store_true", help="Use fictional demonstration data"
    )
    parser.add_argument(
        "--demo-date",
        type=parse_date,
        metavar="YYYY-MM-DD",
        help="Demo only: freeze the application clock at 08:00 on this date",
    )
    parser.add_argument(
        "--data-dir", type=Path, help="Override the local data directory"
    )
    args = parser.parse_args(argv)
    if args.demo_date and not args.demo:
        parser.error(
            "--demo-date requires --demo; the normal database always uses the real clock"
        )
    return args


def main():
    args = arguments()
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(
            "A graphical desktop and Tk are required. Run on your own computer.\n"
            + str(exc),
            file=sys.stderr,
        )
        return 1
    root.withdraw()
    try:
        if args.data_dir:
            directory = args.data_dir
        elif sys.platform == "win32":
            directory = (
                Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "SunriseClinic"
            )
        else:
            directory = Path.home() / ".sunrise_clinic"
        directory.mkdir(parents=True, exist_ok=True)
        # Each frozen-date demonstration has a separate file and cannot mix with live data.
        name = (
            f"demo-{args.demo_date.isoformat()}.sqlite"
            if args.demo_date
            else "demo.sqlite"
        )
        path = directory / (name if args.demo else "clinic.sqlite")
        clock = None
        if args.demo_date:
            frozen = datetime.combine(args.demo_date, time(8, 0))

            def clock():
                return frozen

        if args.demo:
            from sunrise.demo import initialise_demo

            initialise_demo(path, clock=clock)
        service = ClinicService(path, clock=clock)
        if args.demo_date:
            service.demo_clock_label = (
                f"SIMULATED CLOCK: {args.demo_date.isoformat()} 08:00"
            )
        ClinicApp(root, service, demo=args.demo)
        root.deiconify()
        root.mainloop()
        return 0
    except (OSError, ValueError, sqlite3.Error) as exc:
        messagebox.showerror(
            "Unable to open Sunrise Clinic",
            "Check that the data folder is writable and the database is valid.\n\n"
            + str(exc),
            parent=root,
        )
        root.destroy()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
