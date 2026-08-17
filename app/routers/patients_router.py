"""REST API router for patient CRUD operations."""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    PatientCreate, PatientUpdate, PatientResponse, Envelope,
    AppointmentCreate, AppointmentResponse,
)
from app.services import PatientService, AppointmentService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/patients", tags=["patients"])


def _ok(data, status_code: int = 200) -> Response:
    return Response(
        content=Envelope(data=data, error=None).model_dump_json(),
        media_type="application/json",
        status_code=status_code,
    )


def _err(error: str, status_code: int) -> Response:
    return Response(
        content=Envelope(data=None, error=error).model_dump_json(),
        media_type="application/json",
        status_code=status_code,
    )


@router.get("", summary="List all patients")
def list_patients(
    last_name: Optional[str] = Query(None, description="Filter by last name (partial match)"),
    date_of_birth: Optional[str] = Query(None, description="Filter by DOB (YYYY-MM-DD)"),
    phone_number: Optional[str] = Query(None, description="Filter by phone number"),
    db: Session = Depends(get_db),
):
    svc = PatientService(db)
    patients = svc.list_patients(
        last_name=last_name,
        date_of_birth=date_of_birth,
        phone_number=phone_number,
    )
    data = [PatientResponse.model_validate(p).model_dump(mode="json") for p in patients]
    return _ok(data)


@router.get("/{patient_id}", summary="Get a single patient")
def get_patient(patient_id: str, db: Session = Depends(get_db)):
    svc = PatientService(db)
    patient = svc.get_patient(patient_id)
    if not patient:
        return _err("Patient not found", 404)
    if patient.deleted_at is not None:
        return _err("Patient not found", 404)
    return _ok(PatientResponse.model_validate(patient).model_dump(mode="json"))


@router.post("", summary="Create a new patient", status_code=201)
def create_patient(payload: PatientCreate, db: Session = Depends(get_db)):
    try:
        svc = PatientService(db)
        patient = svc.create_patient(payload)
        return _ok(PatientResponse.model_validate(patient).model_dump(mode="json"), 201)
    except Exception as exc:
        logger.exception("Failed to create patient")
        return _err(str(exc), 500)


@router.put("/{patient_id}", summary="Update a patient (partial allowed)")
def update_patient(patient_id: str, payload: PatientUpdate, db: Session = Depends(get_db)):
    svc = PatientService(db)
    patient = svc.update_patient(patient_id, payload)
    if not patient:
        return _err("Patient not found", 404)
    return _ok(PatientResponse.model_validate(patient).model_dump(mode="json"))


@router.delete("/{patient_id}", summary="Soft-delete a patient")
def delete_patient(patient_id: str, db: Session = Depends(get_db)):
    svc = PatientService(db)
    patient = svc.soft_delete(patient_id)
    if not patient:
        return _err("Patient not found", 404)
    return _ok({"patient_id": patient_id, "deleted_at": patient.deleted_at.isoformat()})


# ── Appointments (bonus) ─────────────────────────────
@router.get("/{patient_id}/appointment", summary="Get appointment for a patient")
def get_appointment(patient_id: str, db: Session = Depends(get_db)):
    appt_svc = AppointmentService(db)
    appt = appt_svc.get_for_patient(patient_id)
    if not appt:
        return _err("No appointment found for this patient", 404)
    return _ok(AppointmentResponse.model_validate(appt).model_dump(mode="json"))


@router.post("/{patient_id}/appointment", summary="Schedule an appointment", status_code=201)
def create_appointment(patient_id: str, payload: AppointmentCreate, db: Session = Depends(get_db)):
    patient_svc = PatientService(db)
    patient = patient_svc.get_patient(patient_id)
    if not patient or patient.deleted_at is not None:
        return _err("Patient not found", 404)
    appt_svc = AppointmentService(db)
    appt = appt_svc.create(patient_id, payload)
    return _ok(AppointmentResponse.model_validate(appt).model_dump(mode="json"), 201)
