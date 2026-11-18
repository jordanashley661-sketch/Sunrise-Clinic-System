# Factual update for the final technical report

Use this information to update the earlier report. It does not replace your own reflection or manual acceptance checks.

## Implementation and testing update

The prototype was revised and tested again on 17 November 2026. The updated service/database suite passed all 55 tests. A separate suite passed 30 real Tk widget tests, giving 85 passing automated checks in total. The screen tests covered login, patient registration and edits, appointments, conflict handling, check-in, visits, history, doctor schedules, user management, reports, export and backup. They also checked session expiry and closure of a sensitive dialog after a role change.

The tests ran on Linux using Python 3.12.14, SQLite 3.53.1 and Tk 9.0. The graphical tests used an Xorg test display. They filled real widgets and invoked real buttons. Message boxes and file pickers were intercepted for unattended testing. These are automated screen checks, not manual staff acceptance tests. The student reported core Mac workflows on 16 November before the visual update. Native Mac review of the redesigned screens and Windows checks remain outstanding.

The combined load test used 50,200 fictional patients, 200 appointments and 10 doctors in the same database. Patient search took 0.009643 seconds and slot lookup took 0.000737 seconds. Both met the two-second target in the recorded test environment. These figures do not establish performance on the intended clinic computer.

Black formatting and selected Ruff correctness/style checks passed. A full PEP 8 assessment was not performed. The new source-code.pdf lists the updated source, and VERIFICATION.md maps the original functional requirements to test evidence.

## Screenshots and suggested captions

The PNGs in evidence/screenshots/ are actual renders of the app with fictional data and a simulated 2030-01-07 application clock. State that context in the report.

- 01-login.png: Staff login in the automated Linux test environment; G01.
- 03-registration.png: Fictional patient registration form; G03.
- 04-patient-directory.png: Directory after registering and editing a fictional patient; G03.
- 05-booking.png: Free-slot selection before saving a fictional booking; G05.
- 06-appointments.png: Daily appointment list after the booking; G05.
- 07-clinical-visit.png: Assigned doctor entering fictional visit details; G10.
- 08-history.png: Saved clinical history after completion; G10.
- 09-doctors-and-schedules.png: Administrator doctor list; G13.
- 09-users.png: Administrator user list; G13.
- 09-reports.png: Appointment summary; G13.
- 09-audit-and-backup.png: Administrative action audit and backup screen; G13.

No screenshot of a native error message is claimed because message dialogs were intercepted. Conflict rejection is verified by G07 and its assertions. Automated test logs are provided separately.

## Acknowledgement update

ChatGPT assisted with revising the prototype, preparing tests, capturing automated test screenshots, formatting the source and generating the source-code listing and verification notes. Add your own truthful description of how you reviewed, ran and adapted this work. Do not state that you completed local manual checks until you have done so.

## Submission correction

The supplied brief explicitly requires an assessor-accessible GitHub repository and a final technical report in PDF. These are not optional. The student supplied https://github.com/jordanashley661-sketch/Sunrise-Clinic-System and reported uploading it; confirm its current contents and assessor access. No live demonstration is required by the brief. A compiled version is requested where applicable; native Windows packaging remains unverified.

## Teal interface update

The 17 November build uses the supplied visual direction for the existing staff system. The login, sidebar and dashboard were redesigned; forms retain their original operations. G29 checks the password visibility toggle and G30 checks dashboard refresh, navigation and a 1000 x 720 window. There are 55 service/database cases and 30 real Tk cases, all passing. Source PDF, manifest and screenshots match this build. No patient self-service or medical insurance feature is claimed.
