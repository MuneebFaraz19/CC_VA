"""SQLAlchemy ORM models for patients, calls, and appointments."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Date, DateTime, Text, Boolean, ForeignKey, Index
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Patient(Base):
    __tablename__ = "patients"

    patient_id = Column(String(36), primary_key=True, default=_uuid)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    sex = Column(String(20), nullable=False)
    phone_number = Column(String(20), nullable=False)
    email = Column(String(255), nullable=True)
    address_line_1 = Column(String(255), nullable=False)
    address_line_2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=False)
    state = Column(String(2), nullable=False)
    zip_code = Column(String(10), nullable=False)
    insurance_provider = Column(String(255), nullable=True)
    insurance_member_id = Column(String(100), nullable=True)
    preferred_language = Column(String(50), nullable=True, default="English")
    emergency_contact_name = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(20), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    calls = relationship("CallLog", back_populates="patient", cascade="all, delete-orphan")
    appointment = relationship("Appointment", back_populates="patient", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_patients_phone", "phone_number"),
        Index("ix_patients_last_name", "last_name"),
        Index("ix_patients_dob", "date_of_birth"),
    )


class CallLog(Base):
    """Stores a transcript / summary of each voice call, linked to a patient."""
    __tablename__ = "call_logs"

    call_id = Column(String(36), primary_key=True, default=_uuid)
    patient_id = Column(String(36), ForeignKey("patients.patient_id"), nullable=True)
    vapi_call_id = Column(String(255), nullable=True, index=True)
    caller_phone = Column(String(20), nullable=True)
    status = Column(String(20), nullable=False, default="in_progress")  # in_progress, completed, failed
    transcript = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    collected_data = Column(JSON, nullable=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    patient = relationship("Patient", back_populates="calls")


class Appointment(Base):
    """Mock appointment linked to a patient (bonus feature)."""
    __tablename__ = "appointments"

    appointment_id = Column(String(36), primary_key=True, default=_uuid)
    patient_id = Column(String(36), ForeignKey("patients.patient_id"), nullable=False, unique=True)
    scheduled_date = Column(DateTime(timezone=True), nullable=False)
    provider_name = Column(String(255), nullable=False, default="Dr. Smith")
    department = Column(String(100), nullable=False, default="General Medicine")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    patient = relationship("Patient", back_populates="appointment")
