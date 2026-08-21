"""Service layer — business logic for patients, calls, and appointments."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Patient, CallLog, Appointment
from app.schemas import PatientCreate, PatientUpdate, AppointmentCreate

logger = logging.getLogger(__name__)


# ── Patients ─────────────────────────────────────────
class PatientService:
    def __init__(self, db: Session):
        self.db = db

    def list_patients(
        self,
        last_name: Optional[str] = None,
        date_of_birth: Optional[str] = None,
        phone_number: Optional[str] = None,
        include_deleted: bool = False,
    ) -> list[Patient]:
        stmt = select(Patient)
        if not include_deleted:
            stmt = stmt.where(Patient.deleted_at.is_(None))
        if last_name:
            stmt = stmt.where(Patient.last_name.ilike(f"%{last_name}%"))
        if date_of_birth:
            stmt = stmt.where(Patient.date_of_birth == date_of_birth)
        if phone_number:
            # Normalise the search term the same way we store it
            import re
            digits = re.sub(r"\D", "", phone_number)
            if len(digits) == 11 and digits.startswith("1"):
                digits = digits[1:]
            stmt = stmt.where(Patient.phone_number == digits)
        stmt = stmt.order_by(Patient.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def get_patient(self, patient_id: str) -> Optional[Patient]:
        return self.db.get(Patient, patient_id)

    def get_by_phone(self, phone_number: str) -> Optional[Patient]:
        """Find a non-deleted patient by phone number (for duplicate detection)."""
        import re
        digits = re.sub(r"\D", "", phone_number)
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        stmt = select(Patient).where(
            Patient.phone_number == digits,
            Patient.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalars().first()

    def create_patient(self, data: PatientCreate) -> Patient:
        patient = Patient(**data.model_dump())
        self.db.add(patient)
        self.db.commit()
        self.db.refresh(patient)
        logger.info("Created patient %s: %s %s", patient.patient_id, patient.first_name, patient.last_name)
        return patient

    def update_patient(self, patient_id: str, data: PatientUpdate) -> Optional[Patient]:
        patient = self.db.get(Patient, patient_id)
        if not patient or patient.deleted_at is not None:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(patient, key, value)
        patient.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(patient)
        logger.info("Updated patient %s", patient_id)
        return patient

    def soft_delete(self, patient_id: str) -> Optional[Patient]:
        patient = self.db.get(Patient, patient_id)
        if not patient or patient.deleted_at is not None:
            return None
        patient.deleted_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(patient)
        logger.info("Soft-deleted patient %s", patient_id)
        return patient


# ── Call logs ────────────────────────────────────────
class CallService:
    def __init__(self, db: Session):
        self.db = db

    def create_call(
        self,
        vapi_call_id: Optional[str] = None,
        caller_phone: Optional[str] = None,
    ) -> CallLog:
        call = CallLog(vapi_call_id=vapi_call_id, caller_phone=caller_phone)
        self.db.add(call)
        self.db.commit()
        self.db.refresh(call)
        return call

    def get_call(self, call_id: str) -> Optional[CallLog]:
        return self.db.get(CallLog, call_id)

    def update_call(
        self,
        call_id: str,
        patient_id: Optional[str] = None,
        status: Optional[str] = None,
        transcript: Optional[str] = None,
        summary: Optional[str] = None,
        collected_data: Optional[dict] = None,
    ) -> Optional[CallLog]:
        call = self.db.get(CallLog, call_id)
        if not call:
            return None
        if patient_id is not None:
            call.patient_id = patient_id
        if status is not None:
            call.status = status
        if transcript is not None:
            call.transcript = transcript
        if summary is not None:
            call.summary = summary
        if collected_data is not None:
            call.collected_data = collected_data
        if status in ("completed", "failed"):
            call.ended_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(call)
        return call

    def list_calls(self, limit: int = 50) -> list[CallLog]:
        stmt = select(CallLog).order_by(CallLog.started_at.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())


# ── Appointments ─────────────────────────────────────
class AppointmentService:
    def __init__(self, db: Session):
        self.db = db

    def get_for_patient(self, patient_id: str) -> Optional[Appointment]:
        stmt = select(Appointment).where(Appointment.patient_id == patient_id)
        return self.db.execute(stmt).scalars().first()

    def list_appointments(self) -> list[Appointment]:
        """List all appointments, most recent first."""
        stmt = select(Appointment).order_by(Appointment.scheduled_date.desc())
        return list(self.db.execute(stmt).scalars().all())

    def create(self, patient_id: str, data: AppointmentCreate) -> Appointment:
        existing = self.get_for_patient(patient_id)
        if existing:
            # Update existing appointment
            existing.scheduled_date = data.scheduled_date
            existing.provider_name = data.provider_name
            existing.department = data.department
            existing.notes = data.notes
            self.db.commit()
            self.db.refresh(existing)
            return existing
        appt = Appointment(patient_id=patient_id, **data.model_dump())
        self.db.add(appt)
        self.db.commit()
        self.db.refresh(appt)
        logger.info("Created appointment for patient %s", patient_id)
        return appt
