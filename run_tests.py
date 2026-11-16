"""Run real tests and save an evidence log and machine-readable results."""

from pathlib import Path
import json
from datetime import datetime
import platform
import sqlite3
import sys
import time
import unittest
from tests import test_clinic


class EvidenceResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.records.append({"test": test.id(), "result": "PASS"})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.records.append(
            {"test": test.id(), "result": "FAIL", "detail": str(err[1])}
        )

    def addError(self, test, err):
        super().addError(test, err)
        self.records.append(
            {"test": test.id(), "result": "ERROR", "detail": str(err[1])}
        )


def main():
    out = Path("evidence")
    out.mkdir(exist_ok=True)
    start = time.perf_counter()
    with (out / "test-run.txt").open("w") as handle:
        suite = unittest.defaultTestLoader.loadTestsFromModule(test_clinic)
        result = unittest.TextTestRunner(
            stream=handle, verbosity=2, resultclass=EvidenceResult
        ).run(suite)
    payload = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "duration_seconds": time.perf_counter() - start,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "sqlite": sqlite3.sqlite_version,
        "gui_tests_run": False,
        "windows_tests_run": False,
        "results": result.records,
        "metrics": test_clinic.METRICS,
    }
    (out / "test-results.json").write_text(json.dumps(payload, indent=2))
    print((out / "test-run.txt").read_text())
    print(json.dumps({k: v for k, v in payload.items() if k != "results"}, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
