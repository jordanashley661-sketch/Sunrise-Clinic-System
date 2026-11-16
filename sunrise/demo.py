"""Create fictional data only when explicitly requested with --demo."""

from datetime import date, timedelta
from .services import ClinicService

DEMO_PASSWORD = "SunriseDemo!2026"


def initialise_demo(path, clock=None):
    service = ClinicService(path, clock=clock)
    if not service.needs_setup():
        return
    service.bootstrap_admin("admin", "Demo Administrator", DEMO_PASSWORD)
    service.login("admin", DEMO_PASSWORD)
    service.create_user("reception", "Demo Receptionist", "Receptionist", DEMO_PASSWORD)
    doctor_user = service.create_user(
        "doctor", "Dr Demo Mokoena", "Doctor", DEMO_PASSWORD
    )
    service.create_user("nurse", "Demo Nurse Dlamini", "Nurse", DEMO_PASSWORD)
    did = service.save_doctor(
        {
            "first_name": "Demo",
            "last_name": "Mokoena",
            "phone": "0100000001",
            "user_id": doctor_user,
        }
    )
    for day in range(5):
        service.save_schedule(did, day, "08:00", "16:00", 15)
    service.login("reception", DEMO_PASSWORD)
    pid = service.save_patient(
        {
            "first_name": "Fictional",
            "last_name": "Patient",
            "id_type": "Passport",
            "id_number": "DEMO000001",
            "date_of_birth": "1990-01-01",
            "phone": "0100000002",
            "next_of_kin_name": "Fictional Relative",
            "next_of_kin_phone": "0100000003",
        }
    )
    tomorrow = service.clock().date() if clock else date.today() + timedelta(days=1)
    while tomorrow.weekday() > 4:
        tomorrow += timedelta(days=1)
    service.book(pid, did, tomorrow.isoformat(), "09:00", "Demonstration booking")
    service.logout()
