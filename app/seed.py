"""Seed script — creates 2 demo patient records."""
from __future__ import annotations

import logging
from datetime import date

from app.database import init_db, SessionLocal
from app.schemas import PatientCreate
from app.services import PatientService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SEED_PATIENTS = [
    PatientCreate(
        first_name="Jane",
        last_name="Doe",
        date_of_birth=date(1985, 3, 15),
        sex="Female",
        phone_number="5551234567",
        email="jane.doe@example.com",
        address_line_1="123 Main Street",
        address_line_2="Apt 4B",
        city="San Francisco",
        state="CA",
        zip_code="94102",
        insurance_provider="Blue Cross Blue Shield",
        insurance_member_id="BCBS123456789",
        preferred_language="English",
        emergency_contact_name="John Doe",
        emergency_contact_phone="5559876543",
    ),
    PatientCreate(
        first_name="Michael",
        last_name="Smith",
        date_of_birth=date(1990, 7, 22),
        sex="Male",
        phone_number="5559876543",
        email=None,
        address_line_1="456 Oak Avenue",
        address_line_2=None,
        city="New York",
        state="NY",
        zip_code="10001",
        insurance_provider=None,
        insurance_member_id=None,
        preferred_language="English",
        emergency_contact_name=None,
        emergency_contact_phone=None,
    ),
]


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        svc = PatientService(db)
        existing = svc.list_patients()
        if existing:
            logger.info("Database already has %d patients, skipping seed.", len(existing))
            return
        for patient_data in SEED_PATIENTS:
            patient = svc.create_patient(patient_data)
            logger.info("Seeded: %s %s (%s)", patient.first_name, patient.last_name, patient.patient_id)
        logger.info("Seed complete — %d patients created.", len(SEED_PATIENTS))
    finally:
        db.close()


if __name__ == "__main__":
    seed()
