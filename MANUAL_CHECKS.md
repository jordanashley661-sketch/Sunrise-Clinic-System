# Local verification and final submission checks

These **local human acceptance checks are not yet performed**. Separate automated Linux screen tests have now passed; see VERIFICATION.md and evidence/gui-test-results.json. They do not replace the local checks below. Record your real date, machine, tester and outcome; do not mark them passed without running them.

## Environment

- Operating system and version:
- RAM:
- Python version (`python --version`):
- Tk version (`python -m tkinter`):
- Date and tester:

## Manual acceptance tests

| ID | Action | Expected outcome | Actual result / evidence |
| --- | --- | --- | --- |
| M01 | Extract all files and run `run-demo.bat` on Windows | Login window opens; no import error | Not run |
| M02 | Run normal app on a fresh data directory | First administrator setup appears; no default admin | Not run |
| M03 | Log in as each demo role | Menu and permitted tasks match the role | Not run |
| M04 | Register a fictional patient with a stopwatch | Clear validation; aim for under two minutes after familiarisation | Not run |
| M05 | Search and edit that patient | Saved demographics persist after closing and reopening | Not run |
| M06 | Book a future slot, then try the same slot again | First saves; clash rejected with clear message | Not run |
| M07 | Reschedule and cancel from the UI | List updates; cancelled slot becomes available | Not run |
| M08 | Check in a patient today and record a visit as the assigned doctor | Visit saved; appointment Completed; history readable to clinical staff | Not run |
| M09 | Log in as receptionist and try to view clinical history | No clinical-history control; no notes disclosed | Not run |
| M10 | Leave UI idle for more than 15 minutes | User returns to login | Not run |
| M11 | Create a summary and daily CSV; open in spreadsheet viewer | Correct columns and figures; protect exported information | Not run |
| M12 | Create backup, close app, restore to a separate test directory | Restored users, patient, visit and appointment are present | Not run |
| M13 | Disconnect internet and repeat login, search and booking | No network connection is required | Not run |
| M14 | Test at 1366×768 and Windows display scaling 100% and 125% | Buttons visible, forms usable, no overlapping text | Not run |
| M15 | Package on Windows and run executable on another PC | EXE starts and all required workflows function | Not run |
| M16 | Time patient registration and appointment booking after training | Each task under two minutes; record actual times | Not run |

## Screenshots to add to the report

Use fictional names only. Capture the actual application, not a mockup.

1. First setup or staff login.
2. Reception patient directory and registration form.
3. Booking form with free slots and the double-booking rejection message.
4. Daily list with a checked-in or completed appointment.
5. Clinical visit form and history while logged in as Doctor or Nurse.
6. Doctor weekly schedule editor.
7. User management and role assignment.
8. Report summary and successful backup confirmation.
9. Local automated test results.

Use captions stating screen, action, user role and evidence/test ID. Add dates and refer to screenshots in the relevant report sections.

## Personal and submission checks

- Confirm the home/cell number copied from the foundational report; it appears to have nine digits.
- Enter the actual submission date; the draft was prepared 15 November 2026.
- Replace the personal reflection prompts with your own learning and difficulties.
- Review every paragraph and understand the main service functions. The brief does not require a live demonstration, but the assessor can ask you to explain the work.
- Add lecturer feedback only if received; none was supplied for this build.
- Update Windows/GUI results and requirement statuses only after running them.
- Create the required assessor-accessible GitHub repository, excluding databases and exports; add the real URL to the report. A private repository requires assessor access.
- Re-run `python run_tests.py` after any code change; update report totals and timings to match.
- Keep the complete source folder and test evidence with the submission.
