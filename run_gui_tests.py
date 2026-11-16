"""Run real Tk widget tests on a desktop; save a separate evidence report."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import platform
import tkinter as tk
import unittest

from tests import test_ui


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--screenshots",
        action="store_true",
        help="Save PNGs; requires Pillow for test evidence only",
    )
    args = parser.parse_args()
    try:
        probe = tk.Tk()
        probe.destroy()
    except tk.TclError as exc:
        print("GUI tests were NOT RUN. A desktop display is required: " + str(exc))
        return 2
    out = Path("evidence")
    out.mkdir(exist_ok=True)
    if args.screenshots:

        test_ui.SCREENSHOTS = out / "screenshots"
        test_ui.SCREENSHOTS.mkdir(exist_ok=True)
    with (out / "gui-test-run.txt").open("w") as stream:
        suite = unittest.defaultTestLoader.loadTestsFromModule(test_ui)
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    payload = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "tk": str(tk.TkVersion),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "fixture_clock": "2030-01-07 08:00 (simulated; not real clinic data)",
        "method": "Real Tk widgets and SQLite; button.invoke; message/file dialogs intercepted",
        "limits": "Linux test display; not Windows/macOS, staff usability or physical mouse/keyboard testing",
        "screenshots": args.screenshots,
        "issues": [
            {"test": t.id(), "detail": detail}
            for t, detail in result.failures + result.errors
        ],
    }
    (out / "gui-test-results.json").write_text(json.dumps(payload, indent=2))
    print((out / "gui-test-run.txt").read_text())
    print(json.dumps(payload, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
