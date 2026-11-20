# Start here

## 1. Open the app

Extract the entire ZIP first. Install Python 3.12 or later with Tk support if it is not already installed.

- **Windows:** double-click `run-assessment-demo.bat`.
- **Mac:** double-click `run-assessment-demo.command`. If permissions prevent this, open Terminal in the extracted folder and run the command below.
- **Terminal:** `python3 main.py --demo --demo-date 2030-01-07` (Windows can use `py -3` instead of `python3`).

If Tk is missing, `python3 -m tkinter` will fail to open its test window. Use a Python installer that includes Tk. The launchers have not been run on Windows or Mac in this environment.

## 2. Log in

Passphrase for all fictional demo accounts: **SunriseDemo!2026**

| Username | Purpose |
| --- | --- |
| admin | Users, doctors, schedules, reports and backup |
| reception | Patients, booking and check-in |
| doctor | Assigned consultations and history |
| nurse | Consultations and history |
| patient | Own bookings, personal details, medical insurance and visit summaries; choose Patient portal |

## 3. Try the complete workflow

1. Log in as `reception`, then open Appointments. The date is **2030-01-07**, the clearly labelled simulated demonstration day.
2. Select the fictional 09:00 booking and choose **Check in**.
3. Log out. Log in as `doctor`, open Appointments and select that booking.
4. Choose **Record visit**, enter a fictional complaint and save. It becomes Completed.
5. Select the patient and choose **Patient history** to see the saved visit.
6. Log in as `admin`. Open Reports to export a CSV, then Audit and backup to create a backup with a new filename.

You can also register a new fictional patient as reception, note the patient number, then choose Book, enter that number, load free slots and save. Changing the patient, doctor or date requires reloading slots.

The simulated date is only for repeatable demonstration. To use an empty database with the real clock, run `python3 main.py` and create your first administrator.

## 4. Evidence and submission

- `evidence/test-results.json`: 73 service/database checks (55 original staff cases plus 18 patient-portal cases).
- `evidence/gui-test-results.json`: 40 Tk screen checks.
- `evidence/screenshots/`: actual rendered test screens, not design mockups.
- `source-code.pdf`: complete updated source listing.
- `VERIFICATION.md`: what was checked and what remains.

The student supplied https://github.com/jordanashley661-sketch/Sunrise-Clinic-System and reported uploading the project. Replace its files with this redesigned build after checking it on your Mac. Confirm assessor access and keep local databases out of GitHub. The accompanying report now records 113 automated checks and the new screen evidence. Review the report, personal details and reflection before exporting it to PDF.

## Mac GUI test runner update

A native Tk crash was reported on the Mac. The updated runner removes the create/destroy probe and runs each unchanged GUI test in a separate process, with progress and honest crash/error reporting. All 40 cases and eight runner classification checks passed on Linux. The native Mac retry remains pending. See MAC-GUI-TEST-FIX.md.
