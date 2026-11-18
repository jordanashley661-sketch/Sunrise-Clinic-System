# Sunrise Community Clinic

Offline appointment and patient records coursework prototype for Ashley Jordan Ferreira, student 261231.

**Use fictional data only. This is not a production medical record system.** Application role checks do not protect a database file from someone who has operating-system access. Databases, backups and CSV exports are not encrypted by this prototype.

## Updated assessment build - 17 November 2026

Start with **START-HERE.md**. This build includes 55 service/database checks and 30 real Tk widget checks, saved results and screenshots. See **VERIFICATION.md** for the actual results and limits.

For a repeatable assessment walkthrough, use `run-assessment-demo.bat` (Windows), `run-assessment-demo.command` (Mac), or:

```sh
python3 main.py --demo --demo-date 2030-01-07
```

This visibly labelled demonstration uses a **simulated 7 January 2030, 08:00 application clock** and a separate `demo-2030-01-07.sqlite` file. It lets reception check in the seeded 09:00 appointment and a doctor record its visit in the same session. It does not change your computer clock. The normal app never accepts `--demo-date`. Use fictional data only. Later re-runs keep saved changes; to repeat from the beginning, use a new `--data-dir` folder rather than overwrite a database.

## Teal interface update

The 17 November build adapts the supplied Sunrise mockups to the existing staff system. It adds a split login, sidebar navigation, mint welcome banner, live appointment counts and role-specific quick actions. `sunrise/theme.py` holds the teal palette, Arial typography, rounded cards and vector clinic illustration. No new runtime dependency is required. The reference patient dashboard is a visual guide; patient self-service and medical-insurance storage are outside this staff prototype.

Extract the new project as a complete folder. Its database schema and normal data directory are unchanged, so the same demonstration data remains available. Do not delete the existing database to change the appearance. Check the redesigned screens on your Mac before replacing the submitted GitHub files.

## Start on Windows

1. Install Python 3.12 or later from python.org with **Tcl/Tk and IDLE** and the Python launcher enabled. No third-party runtime packages are required.
2. Extract this entire ZIP to a writable folder. Keep `main.py` and the `sunrise` folder together.
3. Double-click **run-demo.bat**. If the launcher cannot be found, open Command Prompt in this folder and run `python main.py --demo`.
4. Log in with `admin`, `reception`, `doctor` or `nurse`. The demonstration passphrase for all four is **SunriseDemo!2026**.
5. To create a separate empty database, close the app and double-click **run.bat**. The first screen creates your own administrator. Choose your own passphrase of 15–128 characters.

Check Tk if necessary: `py -3 -m tkinter`. A small Tk test window should open. All menu buttons need a normal desktop display.

## Start on macOS or Linux

Install a Python build with Tk support, extract the ZIP, open Terminal in this folder and run:

```sh
python3 main.py --demo
```

On Linux, Tk may require a distribution package such as `python3-tk`. On macOS, the python.org installer normally includes Tk. Service tests and real Tk widget tests have passed on Linux, including a virtual Xorg display. The student reported the core workflow working on a Mac on 16 November, before this visual update. The redesigned screens have been checked on Linux; native Mac appearance and Windows behaviour still need checking.

## First demonstration

1. **Admin:** open Users and see the fictional accounts. Open Doctors and schedules; select Demo Mokoena to inspect weekday hours. Add another Doctor user and link it to a doctor profile if required.
2. **Reception:** open Patients. Register a fictional patient using Passport (for example `DEMO000002`), or SA ID with exactly 13 digits. Enter a birth date, a 10-digit phone, next-of-kin name and phone. Save and note the patient number.
3. **Reception:** open Appointments. Select a current/future weekday. Choose Book, enter the patient number, doctor and date, then Load free slots and Save booking. Attempt to book the same doctor and slot again: it must be rejected.
4. **Reception:** on the appointment date, select the appointment and Check in. You cannot check in a different day's appointment.
5. **Doctor:** log in to the account linked to that doctor. Open the same date in Appointments, select the checked-in patient and Record visit. Enter a complaint and clinical information, then save. The appointment becomes Completed.
6. **Nurse/Doctor:** open Patients and View clinical history. Reception must not have this action and cannot read history through the service either.
7. **Admin:** open Reports, choose dates and export CSV. Open Audit and backup and create a new backup file.

The demonstration database initially contains one booking on the next weekday. Create another booking today within the remaining working hours to demonstrate same-day check-in. If today's schedule has no hours, use the administrator to add hours for that weekday. If the working day has ended, demonstrate booking for a future day and complete the clinical workflow on that day. Do not change your computer's clock to make a screenshot.

## Data files and backups

- Windows default: `%LOCALAPPDATA%\SunriseClinic\clinic.sqlite`
- macOS/Linux default: `~/.sunrise_clinic/clinic.sqlite`
- Demonstration file: `demo.sqlite` in the same directory, always separate from `clinic.sqlite`.
- Optional location: `python main.py --demo --data-dir ./demo-data`
- An administrator can create a verified SQLite backup from the interface. Backups are manual; automatic daily scheduling is not implemented.
- To restore: log everyone out, close every app instance, preserve the current database as a fallback, copy the backup into the appropriate data directory and rename it to `clinic.sqlite` (or `demo.sqlite` for a demonstration). Reopen and verify users, appointments and records. Never restore while the app is open.
- Backups contain personal and clinical information. Use restricted encrypted storage, such as an approved encrypted drive. Do not put patient databases in GitHub.

## Roles

| Role | Main actions |
| --- | --- |
| Receptionist | Register/search/update patient demographics; book/reschedule/check in/cancel/no-show appointments; view daily lists |
| Doctor | Search patient demographics, review clinical history, record checked-in visits assigned to their linked doctor profile |
| Nurse | Search patient demographics, review history and record checked-in visits |
| Admin | Manage users and doctor profiles, set schedules/leave, view reports, export CSV, inspect action audit, back up |

Only doctors and nurses can read clinical notes. Clinical notes should never be typed into administrative booking reasons. The current prototype is designed for one clinic and local storage, not a network share or multi-site deployment.

## Testing and evidence

Run from this folder:

```sh
python run_tests.py
```

This uses standard-library `unittest`, fresh temporary databases, fictional data and a fixed application clock for repeatable booking tests. It writes:

- `evidence/test-run.txt`: complete latest test output;
- `evidence/test-results.json`: individual results, environment and measured timings;
- `evidence/initial-test-run.txt`: first run, including the corrected boundary-test expectation.

No patient database is included in this ZIP. The tests generate and delete their own fixtures. The two load tests create 50,001 synthetic patient rows and 200 same-day appointments for 10 doctors.

The service checks cover application rules, SQLite integration, CSV export, backup restoration and combined load. Screen checks are separate:

```sh
python3 run_gui_tests.py
```

A graphical desktop is required; this runner exits with status 2 if no display is available rather than claiming a pass. Optional PNG capture uses Pillow as a test-only dependency: `python3 -m pip install Pillow`, then `python3 run_gui_tests.py --screenshots`. The normal app requires no third-party packages.

The screen tests invoke real Tk buttons and fill real forms. Message boxes and file pickers are intercepted for unattended execution. All records are fictional and the test clock is fixed at 2030-01-07 08:00. These checks do not prove two-minute staff task times, full mouse/keyboard accessibility, Windows/Mac compatibility, full security or real clinic effectiveness. Complete `MANUAL_CHECKS.md` and add your own screenshots before claiming those checks passed.

## Optional Windows executable

Build on Windows, after running the source and tests successfully there:

```bat
py -3 -m pip install pyinstaller
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name SunriseClinic main.py
```

The result should be `dist\SunriseClinic.exe`. Test that file on a separate Windows PC, including first setup, writing to the data folder, restart persistence, CSV export and restore. The supplied package does not contain a verified Windows executable. PyInstaller is only a build dependency and is not needed to run the Python source.

## Project structure

- `main.py`: application entry point and data-directory selection.
- `sunrise/ui.py`: Tkinter/ttk forms and role-dependent screens.
- `sunrise/services.py`: validation, session checks, booking, visits, reporting and backup rules.
- `sunrise/database.py`: schema and transaction/connection factory.
- `sunrise/security.py`: salted PBKDF2-SHA256 storage and verification.
- `sunrise/demo.py`: opt-in fictional demonstration data.
- `tests/test_clinic.py`: automated service/database tests.
- `run_tests.py`: evidence-producing runner.
- `MANUAL_CHECKS.md`: outstanding local verification checklist.
- `tests/test_ui.py` and `run_gui_tests.py`: real-widget screen checks.
- `VERIFICATION.md`: new evidence, changes and rubric mapping.
- `START-HERE.md`: short start and walkthrough instructions.
- `source-code.pdf`: readable listing of the delivered Python source.

## Scope and known limitations

There is no patient portal, website, SMS/email integration, billing, medical-aid processing, diagnosis automation or cloud sync. CSV is implemented; built-in PDF reports are not. Use a suitable viewer to print CSV files. Follow-up dates are stored and shown in history, but reception must create the actual follow-up booking. There is no automatic follow-up appointment.

ID validation checks format only; it does not verify an SA ID checksum, citizenship, date match or a government identity record. Phone validation currently accepts South African local numbers only. Patient search matches prefixes and returns the first 100 results. The SQLite file is not encrypted; action logs are not tamper-proof. Recovery is a documented offline restore procedure rather than an in-app restore wizard. GUI expiry and sensitive-modal closure are exercised by the screen tests with an advanced inactivity timestamp. A real 15-minute elapsed-time check remains manual.

## Academic use and acknowledgement

ChatGPT assisted with the source, tests, technical diagrams and report draft. Read, run and understand the code; adapt it to your institution's rules and your own work. Add actual lecturer feedback if subsequently received. Replace the marked personal-reflection and submission fields truthfully. Do not claim to have independently written all generated code or completed tests that remain pending.
