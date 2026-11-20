# Functionality verification - 17 November 2026

## Actual outcome

- Service/database suite: **73 tests, 0 failures, 0 errors**.
- Real Tk widget suite: **40 tests, 0 failures, 0 errors**.
- Total: **113 passed automated checks**. Separate native entry-point startup checks are in evidence/startup-checks.json.
- Python 3.12.14; SQLite 3.53.1; Tk 9.0; Linux test environment.
- Black formatting check and Ruff E4/E7/E9/F checks passed. These selected checks are not a complete PEP 8 audit.
- Combined load in one database: **50,200 patients, 200 appointments, 10 doctors**. Patient search 0.010666s; slot lookup 0.000902s. Both below the two-second target in this environment.

## Visual update on 17 November

The supplied mockups were adapted to the existing staff app: teal split login, sidebar, rounded panels, real daily counts, account identity and role-specific quick actions. The staff rules remain; version 2 adds patient ownership checks, invitation linking and local self-service. G29 checks password visibility without changing its value. G30 checks the refreshed dashboard status, navigation and a registration action at a 1000 x 720 window size. The original 28 GUI workflows still pass.

The student reported core Mac workflows on 16 November using the previous appearance. Those outcomes are not presented as native-Mac approval of this redesign. Test the new appearance on the Mac before submitting it. Patient accounts, own bookings, contacts, insurance and visit summaries have now been added as the local extension described in PATIENT-PORTAL.md.

## What changed

1. A booking cannot be saved using a slot loaded for different patient/doctor/date details. Editing those details clears the selection, and save checks the context again.
2. Rescheduling retains the existing administrative reason.
3. Invalid appointment-date refreshes keep the previous list visible rather than blank the screen.
4. CSV exports require a .csv destination and cannot overwrite the live database. Atomic replacement preserves a previous export if file replacement fails.
5. Last-admin protection excludes locked accounts from the recovery-account count.
6. A role change detected by keyboard/mouse activity or a guarded action closes the previous session and sensitive dialogs.
7. Reports now expose the daily-export doctor filter in the interface and label the date inputs.
8. Login and patient search accept Enter as well as the button.
9. Added a visibly labelled, separate frozen-date demonstration, permitting a complete same-day consultation walkthrough without changing the operating-system clock.
10. Reformatted the source for readability, removed unused imports, and refreshed the source-code PDF.

## Patient extension evidence

All 18 P01-P18 service tests and G31-G40 patient screen tests passed. The test runner now includes 73 service cases (T01-T55 plus P01-P18) and 40 GUI cases. Migration preserves version 1 data and writes a pre-upgrade backup; ownership tests reject cross-patient access, and concurrency tests permit only one of two bookings for a shared slot. See PATIENT-PORTAL.md for exact behaviour and limits.

## Core functions and evidence

| Original requirement | Implementation evidence | GUI evidence |
| --- | --- | --- |
| FR1 Login and role access | T01-T05, T26, T55 | G01-G02, G12, G17-G18, G22, G28 |
| FR2 Patient registration | T06-T08 | G03-G04 |
| FR3 Validation and duplicates | T07-T08, T52 | G04 |
| FR4 Patient search | T09-T10, T35, T54 | G03 |
| FR5 View/update demographics | T09 | G03, G19 |
| FR6 Doctor profiles and hours | T11, T32, T53 | G14-G15, G25 |
| FR7 Unavailable dates | T12, T30 | G14, G25 |
| FR8 Book appointment | T13, T48 | G05 |
| FR9 Prevent clashes and invalid slots | T14-T15, T18-T20, T37, T49-T50 | G06-G07 |
| FR10 Reschedule/cancel | T16-T17, T46, T51 | G08-G09 |
| FR11 Track appointment status | T21, T33, T41, T49 | G09-G11, G23 |
| FR12 Basic clinical visit | T21-T24, T48 | G10-G11, G27-G28 |
| FR13 Newest-first history | T24; reception denied T05 | G10, G12 |
| FR14 Daily appointment list | T25, T36, T42, T54 | G05, G13, G26 |
| FR15 Summary report | T25, T41 | G13, G26 |
| FR16 CSV or PDF export | CSV: T25, T39, T42-T44; PDF report export not implemented | G16, G26 |
| FR17 Account administration | T02-T03, T29, T34, T45, T52, T55 | G15, G24 |
| FR18 Manual backup | T27 | G16 |

The supplied summative brief's excellent functionality band is 24-30 marks: all core features working, with correct, efficient and reliable logic. These results support those qualities, but do not guarantee an assessor's mark.

## How the screen checks were performed

Real Tk windows, entries, tables and buttons were created on a Linux Xorg dummy display. Tests entered data and invoked actual Tk buttons, calling the real service and SQLite database. Message boxes and save-file pickers were intercepted to avoid blocking unattended tests; their messages were asserted in tests. They were not tested through a human clicking native dialog buttons. Screenshots show the actual rendered app, not generated design mockups.

All tests use fictional data. Screen tests use a **simulated 2030-01-07 08:00 application clock**. Session-expiry tests advance the stored monotonic inactivity timestamp rather than wait 15 minutes. Audit timestamps still use the real system clock. Test execution timestamps are recorded in the JSON files.

Initial GUI test failures were test-driver mistakes: a label mismatch and an ambiguous duplicate Create user button. Both were corrected by matching the actual label and limiting the lookup to the active dialog. The original GUI log is retained separately.

## Important limits and remaining submission work

- Native Windows and Mac startup, display scaling and packaging have not been verified here. Check the source on your own intended computer.
- No Windows executable is included. The brief requires a compiled version where applicable; Python source is supplied with launchers and optional Windows packaging instructions.
- Real staff task times, complete keyboard-only access, screen readers, physical mouse/keyboard input and 15 minutes of actual elapsed inactivity remain manual checks.
- Automatic daily backup is not implemented; the original manual-backup functional requirement is implemented. SQLite files and exports are not encrypted. This is a local coursework prototype, not a production clinical system.
- The student supplied the GitHub URL in START-HERE.md and reported uploading it. Its current contents and assessor access are not independently verified; update it with this build after local review.
- The accompanying report has been updated with this build and screen evidence. Review it and export the final report to PDF; include source-code.pdf. Native OS and human acceptance checks remain distinct from automated results.
- Complete the personal reflection after reviewing and running the code. Do not invent formative feedback; none was supplied for this build.
- The brief permits AI as a learning aid, with substantive use acknowledged and reviewed by the student. This package records AI assistance. Review and understand the submitted code yourself.

## Reproduce

Run `python3 run_tests.py` for the service suite. On a desktop, run `python3 run_gui_tests.py`. Optional screenshot capture: install Pillow as a development dependency and run `python3 run_gui_tests.py --screenshots`. No third-party packages are required by the normal app. Black and Ruff are optional development tools, not runtime dependencies.

Authoritative evidence: evidence/test-run.txt, evidence/test-results.json, evidence/gui-test-run.txt, evidence/gui-test-results.json, evidence/startup-checks.json and evidence/screenshots/.

## Mac GUI test runner update

A native Tk crash was reported on the Mac. The updated runner removes the create/destroy probe and runs each unchanged GUI test in a separate process, with progress and honest crash/error reporting. All 40 cases and eight runner classification checks passed on Linux. The native Mac retry remains pending. See MAC-GUI-TEST-FIX.md.
