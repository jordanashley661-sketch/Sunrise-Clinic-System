# Mac GUI test runner update 17 November 2026

The supplied Mac crash report records Python 3.15.2, Tcl 9.0.4 and Tk 9.0.5, with SIGTRAP in Tk_MacOSXGetTkWindow while processing an idle event. The previous runner created and immediately destroyed a Tk probe window, then created more Tk roots in the same process. This lifecycle is consistent with an upstream Mac Tk issue. It is the working diagnosis, not proof of the exact failing Python line.

The runner now creates no controller Tk root and runs each unchanged G01-G40 case in its own Python process. The test fixture creates one root in that process. The controller checks the process exit as well as the result file. A native crash, incomplete/invalid result, skipped case or timeout cannot be reported as PASS. It displays progress, flushes logs and saves incremental JSON with RUNNING until the suite completes.

Validation: all 40 real Tk GUI cases passed on Linux in separate processes. Eight runner evidence checks passed, including a simulated SIGTRAP exit after an otherwise passing result. The 73 service/database cases are unchanged; their earlier passing evidence is retained. This is not a completed native Mac GUI run. Retry on the Mac and retain its real output before recording a Mac pass.

## Replace just the runner

Close the crash popup. Download run_gui_tests.py, put it in your current SunriseClinic project folder beside main.py, and replace the existing file of the same name. Keep it named run_gui_tests.py. In the VS Code terminal run:

    python3 run_gui_tests.py

Allow the run to finish. You should see [1/40] through [40/40] with PASS, FAIL or ERROR, followed by a summary. The new run may take a few minutes because each case starts fresh. Test windows opening and closing are expected. If a case errors, open evidence/gui-test-run.txt to see its details. Current run totals, machine platform and any issues are in evidence/gui-test-results.json. These tests use temporary fictional databases and do not alter your clinic/demo data.

Source context:
https://github.com/python/cpython/issues/149853
https://docs.python.org/3/library/tkinter.html#threading-model
