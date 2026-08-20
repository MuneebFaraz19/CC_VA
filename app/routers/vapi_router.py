"""Vapi webhook router — receives tool-call events from the voice agent."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.schemas import Envelope, PatientCreate, PatientUpdate
from app.services import PatientService, CallService, AppointmentService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vapi", tags=["vapi"])
_settings = get_settings()


def _ok(data: Any, status_code: int = 200) -> Response:
    return Response(
        content=Envelope(data=data, error=None).model_dump_json(),
        media_type="application/json",
        status_code=status_code,
    )


def _err(error: str, status_code: int = 400) -> Response:
    return Response(
        content=Envelope(data=None, error=error).model_dump_json(),
        media_type="application/json",
        status_code=status_code,
    )


def _parse_dob(raw: str) -> str:
    """Convert MM/DD/YYYY → YYYY-MM-DD for Pydantic date parsing."""
    raw = raw.strip()
    # Already ISO?
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return raw
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw)
    if m:
        mm, dd, yyyy = m.groups()
        return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"
    raise ValueError(f"Invalid date format: {raw}")


def _extract_tool_call(body: dict) -> Optional[dict]:
    """Extract the tool call from a Vapi webhook payload."""
    # Vapi sends tool calls in message.toolCalls
    msg = body.get("message", {})
    tool_calls = msg.get("toolCalls") or msg.get("tool_calls") or []
    if tool_calls:
        return tool_calls[0]
    # Some payloads nest differently
    if "toolCall" in body:
        return body["toolCall"]
    return None


def _extract_call_info(body: dict) -> dict:
    """Extract call-level metadata from the Vapi payload.

    Vapi sends call info in different places depending on event type:
    - body.call.id  (some events)
    - body.message.call.id  (newer format)
    - body.callId  (legacy)
    """
    call = body.get("call", {}) or {}
    msg = body.get("message", {}) or {}
    msg_call = msg.get("call", {}) or {}

    vapi_call_id = (
        call.get("id")
        or msg_call.get("id")
        or body.get("callId")
        or msg.get("callId")
    )
    caller_phone = (
        call.get("customer", {}).get("number")
        or msg_call.get("customer", {}).get("number")
        or body.get("customerNumber")
        or msg.get("customerNumber")
    )
    return {
        "vapi_call_id": vapi_call_id,
        "caller_phone": caller_phone,
    }


@router.post("/webhook", summary="Vapi webhook endpoint")
async def vapi_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receives webhook events from Vapi.

    Key event types from Vapi:
    - assistant.started: Call started (Vapi's newer event name)
    - call-start: Call started (legacy event name)
    - status-update: Mid-call status, may include tool calls
    - speech-update: Speech started/stopped events
    - conversation-update: Conversation messages so far
    - end-of-call-report: Call finished, includes transcript + summary
    - tool_call: The LLM wants to call registerPatient / updatePatient / scheduleAppointment
    """
    try:
        body = await request.json()
    except Exception:
        return _err("Invalid JSON body", 400)

    # Verify webhook HMAC signature if a secret is configured
    if _settings.vapi_webhook_secret:
        signature = request.headers.get("x-vapi-signature", "")
        raw_body = await request.body()
        import hmac
        import hashlib
        expected = hmac.new(
            _settings.vapi_webhook_secret.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            logger.warning("Webhook signature mismatch — rejecting request")
            return _err("Invalid webhook signature", 401)

    logger.info("Vapi webhook received: %s", json.dumps(body, default=str)[:2000])

    msg_type = body.get("message", {}).get("type") or body.get("type", "")

    logger.info("Webhook event type: %s", msg_type)

    # ── Call started (Vapi sends 'assistant.started' or 'call-start') ──
    if msg_type in ("call-start", "assistant.started"):
        info = _extract_call_info(body)
        call_svc = CallService(db)
        # Avoid duplicate if we already have this vapi_call_id
        if info["vapi_call_id"]:
            from sqlalchemy import select
            from app.models import CallLog
            existing = db.execute(
                select(CallLog).where(CallLog.vapi_call_id == info["vapi_call_id"])
            ).scalars().first()
            if existing:
                logger.info("Call already logged: vapi_call_id=%s", info["vapi_call_id"])
                return _ok({"call_id": existing.call_id, "message": "Call already logged"})
        call = call_svc.create_call(
            vapi_call_id=info["vapi_call_id"],
            caller_phone=info["caller_phone"],
        )
        logger.info("Call started: call_id=%s, caller=%s", call.call_id, info["caller_phone"])
        return _ok({"call_id": call.call_id, "message": "Call logged"})

    # ── End-of-call report ───────────────────────────
    if msg_type in ("end-of-call-report", "end-of-call"):
        info = _extract_call_info(body)
        call_svc = CallService(db)
        vapi_id = info["vapi_call_id"]
        msg = body.get("message", {})

        # Try to get transcript/summary from multiple possible locations
        transcript = msg.get("transcript") or body.get("transcript", "")
        summary = msg.get("summary") or body.get("summary", "")

        # Vapi may send artifact with ordered messages instead of a flat transcript
        if not transcript:
            artifact = body.get("artifact") or msg.get("artifact")
            if artifact and isinstance(artifact, dict):
                transcript = artifact.get("transcript", "")
                summary = summary or artifact.get("summary", "")
                # Build transcript from messages array if no flat transcript
                if not transcript:
                    messages = artifact.get("messages", [])
                    parts = []
                    for m in messages:
                        role = m.get("role", "")
                        text = m.get("message") or m.get("content", "")
                        if role == "bot" or role == "assistant":
                            parts.append(f"Agent: {text}")
                        elif role == "user":
                            parts.append(f"Caller: {text}")
                    if parts:
                        transcript = "\n".join(parts)

        logger.info("End-of-call: vapi_call_id=%s, transcript_len=%d", vapi_id, len(transcript or ""))

        # Try to find the call
        from sqlalchemy import select
        from app.models import CallLog
        stmt = select(CallLog).where(CallLog.vapi_call_id == vapi_id)
        existing = db.execute(stmt).scalars().first()
        if existing:
            call_svc.update_call(
                existing.call_id,
                status="completed",
                transcript=transcript,
                summary=summary,
            )
        else:
            call = call_svc.create_call(vapi_call_id=vapi_id, caller_phone=info["caller_phone"])
            call_svc.update_call(call.call_id, status="completed", transcript=transcript, summary=summary)
        logger.info("Call completed: vapi_call_id=%s", vapi_id)
        return _ok({"message": "Call report saved"})

    # ── Tool call ────────────────────────────────────
    tool_call = _extract_tool_call(body)
    if not tool_call:
        # Not a tool call, just acknowledge
        return _ok({"message": "Acknowledged"})

    func_name = tool_call.get("function", {}).get("name", "")
    func_args_raw = tool_call.get("function", {}).get("arguments", "{}")
    try:
        func_args = json.loads(func_args_raw) if isinstance(func_args_raw, str) else func_args_raw
    except json.JSONDecodeError:
        return _err("Invalid tool call arguments", 400)

    tool_call_id = tool_call.get("id", "")
    call_info = _extract_call_info(body)

    # ── registerPatient ──────────────────────────────
    if func_name == "registerPatient":
        return _handle_register(func_args, tool_call_id, db, call_info)

    # ── updatePatient ────────────────────────────────
    if func_name == "updatePatient":
        return _handle_update(func_args, tool_call_id, db)

    # ── scheduleAppointment ──────────────────────────
    if func_name == "scheduleAppointment":
        return _handle_schedule(func_args, tool_call_id, db)

    return _err(f"Unknown function: {func_name}", 400)


def _handle_register(func_args: dict, tool_call_id: str, db: Session, call_info: dict | None = None) -> Response:
    """Process registerPatient tool call."""
    try:
        # Convert DOB format
        if "date_of_birth" in func_args:
            func_args["date_of_birth"] = _parse_dob(func_args["date_of_birth"])

        # Check for duplicate by phone number
        phone = func_args.get("phone_number", "")
        patient_svc = PatientService(db)
        existing = patient_svc.get_by_phone(phone)
        if existing:
            return Response(
                content=json.dumps({
                    "result": {
                        "status": "duplicate",
                        "patient_id": existing.patient_id,
                        "first_name": existing.first_name,
                        "last_name": existing.last_name,
                        "message": f"A patient with this phone number already exists: "
                                   f"{existing.first_name} {existing.last_name}. "
                                   f"Ask the caller if they want to update instead.",
                    },
                    "toolCallId": tool_call_id,
                }),
                media_type="application/json",
                status_code=200,
            )

        # Validate and create
        data = PatientCreate(**func_args)
        patient = patient_svc.create_patient(data)

        # Link this patient to the call log if we have a vapi_call_id
        if call_info and call_info.get("vapi_call_id"):
            vapi_id = call_info["vapi_call_id"]
            from sqlalchemy import select
            from app.models import CallLog
            stmt = select(CallLog).where(CallLog.vapi_call_id == vapi_id)
            existing_call = db.execute(stmt).scalars().first()
            if existing_call:
                call_svc = CallService(db)
                call_svc.update_call(existing_call.call_id, patient_id=patient.patient_id)

        # Log the collected data to stdout (observability requirement)
        logger.info("Patient registered via voice agent: %s", json.dumps({
            "patient_id": patient.patient_id,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "phone_number": patient.phone_number,
        }))

        return Response(
            content=json.dumps({
                "result": {
                    "status": "success",
                    "patient_id": patient.patient_id,
                    "message": f"Patient {patient.first_name} {patient.last_name} "
                               f"registered successfully.",
                },
                "toolCallId": tool_call_id,
            }),
            media_type="application/json",
            status_code=200,
        )
    except ValueError as e:
        logger.warning("Validation error in registerPatient: %s", e)
        return Response(
            content=json.dumps({
                "result": {
                    "status": "validation_error",
                    "message": f"I couldn't save the information because: {e}. "
                               f"Please ask the caller to correct this and try again.",
                },
                "toolCallId": tool_call_id,
            }),
            media_type="application/json",
            status_code=200,
        )
    except Exception as e:
        logger.exception("Error in registerPatient")
        return Response(
            content=json.dumps({
                "result": {
                    "status": "error",
                    "message": "There was a problem saving the patient information. "
                               "Please ask the caller to try again later.",
                },
                "toolCallId": tool_call_id,
            }),
            media_type="application/json",
            status_code=200,
        )


def _handle_update(func_args: dict, tool_call_id: str, db: Session) -> Response:
    """Process updatePatient tool call."""
    try:
        patient_id = func_args.pop("patient_id", None)
        if not patient_id:
            return _err("patient_id is required for updatePatient", 400)

        if "date_of_birth" in func_args and func_args["date_of_birth"]:
            func_args["date_of_birth"] = _parse_dob(func_args["date_of_birth"])

        # Remove empty values
        func_args = {k: v for k, v in func_args.items() if v is not None and v != ""}

        data = PatientUpdate(**func_args)
        patient_svc = PatientService(db)
        patient = patient_svc.update_patient(patient_id, data)
        if not patient:
            return Response(
                content=json.dumps({
                    "result": {"status": "error", "message": "Patient not found."},
                    "toolCallId": tool_call_id,
                }),
                media_type="application/json",
                status_code=200,
            )

        logger.info("Patient updated via voice agent: %s", patient_id)
        return Response(
            content=json.dumps({
                "result": {
                    "status": "success",
                    "patient_id": patient.patient_id,
                    "message": f"Patient information updated successfully.",
                },
                "toolCallId": tool_call_id,
            }),
            media_type="application/json",
            status_code=200,
        )
    except ValueError as e:
        logger.warning("Validation error in updatePatient: %s", e)
        return Response(
            content=json.dumps({
                "result": {
                    "status": "validation_error",
                    "message": f"Validation error: {e}. Please correct and try again.",
                },
                "toolCallId": tool_call_id,
            }),
            media_type="application/json",
            status_code=200,
        )
    except Exception as e:
        logger.exception("Error in updatePatient")
        return Response(
            content=json.dumps({
                "result": {"status": "error", "message": "Update failed. Please try again."},
                "toolCallId": tool_call_id,
            }),
            media_type="application/json",
            status_code=200,
        )


def _handle_schedule(func_args: dict, tool_call_id: str, db: Session) -> Response:
    """Process scheduleAppointment tool call (bonus)."""
    try:
        patient_id = func_args.get("patient_id")
        date_str = func_args.get("date")  # YYYY-MM-DD
        time_str = func_args.get("time")  # HH:MM
        provider = func_args.get("provider_name", "Dr. Smith")

        if not patient_id or not date_str or not time_str:
            return _err("patient_id, date, and time are required", 400)

        dt_str = f"{date_str}T{time_str}:00"
        scheduled = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)

        from app.schemas import AppointmentCreate
        appt_data = AppointmentCreate(scheduled_date=scheduled, provider_name=provider)
        appt_svc = AppointmentService(db)
        appt = appt_svc.create(patient_id, appt_data)

        logger.info("Appointment scheduled for patient %s on %s", patient_id, scheduled)
        return Response(
            content=json.dumps({
                "result": {
                    "status": "success",
                    "appointment_id": appt.appointment_id,
                    "message": f"Appointment scheduled with {appt.provider_name} "
                               f"on {scheduled.strftime('%B %d, %Y at %I:%M %p')}.",
                },
                "toolCallId": tool_call_id,
            }),
            media_type="application/json",
            status_code=200,
        )
    except Exception as e:
        logger.exception("Error in scheduleAppointment")
        return Response(
            content=json.dumps({
                "result": {"status": "error", "message": "Could not schedule appointment."},
                "toolCallId": tool_call_id,
            }),
            media_type="application/json",
            status_code=200,
        )
