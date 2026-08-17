"""Router for call logs (transcript viewing)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import CallLogResponse, Envelope
from app.services import CallService

router = APIRouter(prefix="/calls", tags=["calls"])


@router.get("", summary="List recent calls")
def list_calls(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    svc = CallService(db)
    calls = svc.list_calls(limit)
    data = [CallLogResponse.model_validate(c).model_dump(mode="json") for c in calls]
    return Response(
        content=Envelope(data=data, error=None).model_dump_json(),
        media_type="application/json",
        status_code=200,
    )


@router.get("/{call_id}", summary="Get a single call log")
def get_call(call_id: str, db: Session = Depends(get_db)):
    svc = CallService(db)
    call = svc.get_call(call_id)
    if not call:
        return Response(
            content=Envelope(data=None, error="Call not found").model_dump_json(),
            media_type="application/json",
            status_code=404,
        )
    return Response(
        content=Envelope(data=CallLogResponse.model_validate(call).model_dump(mode="json"), error=None).model_dump_json(),
        media_type="application/json",
        status_code=200,
    )
