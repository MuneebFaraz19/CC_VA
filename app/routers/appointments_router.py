"""REST API router for listing all appointments."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AppointmentResponse, Envelope
from app.services import AppointmentService, PatientService

router = APIRouter(prefix="/appointments", tags=["appointments"])


def _ok(data, status_code: int = 200) -> Response:
    return Response(
        content=Envelope(data=data, error=None).model_dump_json(),
        media_type="application/json",
        status_code=status_code,
    )


@router.get("", summary="List all appointments")
def list_appointments(db: Session = Depends(get_db)):
    svc = AppointmentService(db)
    appts = svc.list_appointments()

    # Enrich with patient names
    patient_svc = PatientService(db)
    result = []
    for a in appts:
        item = AppointmentResponse.model_validate(a).model_dump(mode="json")
        patient = patient_svc.get_patient(a.patient_id)
        item["patient_name"] = (
            f"{patient.first_name} {patient.last_name}" if patient else "Unknown"
        )
        item["patient_phone"] = patient.phone_number if patient else None
        result.append(item)
    return _ok(result)
