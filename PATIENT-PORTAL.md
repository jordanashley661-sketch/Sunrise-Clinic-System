# Patient portal walkthrough

The clinic app now includes patient self-service as a local coursework extension. It is the same offline desktop app and the same database reception uses. It is not an Internet booking website. A patient on a separate device cannot access the clinic database through this build. Do not host or share the SQLite file as a substitute for an authenticated online service.

## Try the existing fictional patient

1. Extract the entire new ZIP and open its SunriseClinic folder in VS Code.
2. Run `python3 main.py --demo --demo-date 2030-01-07`.
3. Choose **Patient portal** at the top of the login form.
4. Username: **patient**. Password: **SunriseDemo!2026**.
5. Choose **My appointments**, then **Book an appointment**. Select a doctor, click a highlighted calendar date, click an available time button, then **Confirm my booking**. Changing the doctor or date clears the previous time selection.
6. Choose **Log out**, then **Staff sign in**. Log in as **reception** with the same demo password. The booking appears under **Appointments** for that date.

The demo patient owns the original fictional patient record, including its saved bookings and visit summaries. Re-running the demo preserves edits. If the original 09:00 booking is already Completed, book a new future slot. Normal mode does not create any demo account.

## Create a new patient account

Choose **Patient portal → Create a patient account**. On the first tab, enter a unique username and matching passphrases of 15–128 characters. Leave the invitation blank. On the second tab, enter fictional personal details, including an email address and next of kin. Save the account. The patient profile and login are created together, or neither is created if validation fails.

## Link someone already registered by reception

Reception verifies the patient's identity first. In **Patients**, select the patient, choose **View or update**, then **Create portal invitation**. Confirm identity verification and give the one-use code only to that patient. The patient chooses **Create a patient account** and enters the code on the first tab with a new username/passphrase. The second tab is unnecessary. Codes expire after 24 application-clock hours; issuing a new code invalidates the previous unused one. Only a hash of the code is stored. An existing patient cannot claim records merely by entering an ID number or date of birth.

The demonstration clock is frozen, so the code expiry clock advances only when the application clock advances. Normal mode uses real time. An administrator can unlock, deactivate or reset a patient account from **Users**; a patient account cannot be converted to a staff role.

## What patients can access

- Their own upcoming and past appointments and status.
- Booking, rescheduling and cancellation of their own future Booked appointments; checked-in/completed/past visits require reception for changes.
- Their own personal details, with editable phone, email, address and next-of-kin contacts. Reception handles identity corrections.
- Their own optional medical-aid provider, plan, membership number and member type. This does not verify cover or submit a claim. The overview masks the membership number.
- Their own saved diagnosis, treatment and follow-up summaries. Staff-only clinical notes are excluded. A follow-up date does not make a booking automatically.

Patient ownership is checked in the service layer from the signed-in user's unique PatientPortal link, even if someone attempts to call a method with a different patient or appointment ID. Patients cannot browse the directory, open staff reports/audits, manage users or write clinical visits.

## Existing database upgrade

Schema version 1 is upgraded to version 2 automatically. Before altering it, the app creates a one-time SQLite backup next to the database with `.before-v2` in its name. User IDs, password hashes, appointments and visits are preserved. The role constraint gains Patient, and PatientPortal and PatientInvitation tables are added. Existing data is not reset. Keep the upgraded app and database together; older builds cannot open version 2. Automatic daily backup is still not implemented.

## Verification and remaining checks

17 November 2026: **73 service/database tests and 40 real Tk screen tests passed (113 total)** on Linux. P01–P18 cover ownership, registration, one-use invitations, migration, shared booking conflicts, contact/insurance data and visit summaries. G31–G40 exercise actual patient forms. Logs are in evidence/. Native Mac review of this extension, Windows packaging, live-network deployment and clinic acceptance remain outstanding. The student's earlier Mac checks apply to the earlier staff build.


## Staff weekly calendar
After booking, log out and choose Staff sign in. Admin and doctor home screens include the weekly timetable. The **Weekly calendar** navigation item also opens it directly. Select Previous/Next to browse weeks, or Next booking to jump to the next upcoming appointment. Each block shows its time and patient; click it for full details. Admin can filter by doctor. Doctors see only their linked doctor profile's appointments. The Week agenda button provides a text/table alternative.

All logins must use the same data file shown at the top of the workspace. Click the filename to see its full path. Demo mode, the assessment demo and normal mode intentionally use different databases. This desktop prototype does not synchronise bookings between separate computers.
