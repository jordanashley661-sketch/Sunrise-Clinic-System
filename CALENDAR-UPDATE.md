# Calendar and scrolling update — 20 November 2026

This package is based on the patient-portal prototype, including patient ownership checks, staff workflows and the shared appointment database.

## What changed
- Patient booking and rescheduling now show an inline month calendar and clickable time buttons.
- Availability loads automatically. Past dates and dates with no free slots are disabled.
- You must explicitly select a time. Changing doctor or date clears that selection.
- The service rechecks availability when confirming; a rejected booking refreshes the picker.
- Native scrollbars throughout the app were replaced by slim, arrow-free draggable thumbs that disappear visually when scrolling is unnecessary. Mouse-wheel scrolling follows the pointer over forms.
- The staff booking form retains its existing controls.

## Open and try
Extract the complete ZIP first. Run `python3 main.py --demo --demo-date 2030-01-07` from this folder, or use run-assessment-demo.command on Mac. Choose Patient portal and use the demo credentials in PATIENT-PORTAL.md. Open My appointments > Book an appointment, select 7 January and 10:00, then confirm. Do not copy a database over your existing data.

## Verification
The standard-library service and calendar-state tests pass (see evidence/test-results.json). Python sources compile. Updated real-Tk workflows are provided in tests/test_ui.py, including calendar selection, unavailable dates, booking, rescheduling and clearing a selected time. They could not be executed here because no graphical display is available. On your computer run `python3 run_gui_tests.py` to verify the visible interface. Existing GUI evidence, screenshots and source-code.pdf are earlier snapshots, not evidence of this UI update.
