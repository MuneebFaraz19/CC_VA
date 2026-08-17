"""Tests for the Vapi webhook endpoint."""
from __future__ import annotations

import json


VALID_TOOL_ARGS = {
    "first_name": "John",
    "last_name": "Doe",
    "date_of_birth": "01/15/1990",
    "sex": "Male",
    "phone_number": "5551234567",
    "address_line_1": "123 Main St",
    "city": "San Francisco",
    "state": "CA",
    "zip_code": "94102",
}


def _make_tool_call(func_name: str, args: dict) -> dict:
    return {
        "message": {
            "type": "tool-call",
            "toolCalls": [
                {
                    "id": "test-tool-call-id",
                    "function": {
                        "name": func_name,
                        "arguments": json.dumps(args),
                    },
                }
            ],
        }
    }


class TestRegisterPatientWebhook:
    def test_register_success(self, client):
        body = _make_tool_call("registerPatient", VALID_TOOL_ARGS)
        resp = client.post("/vapi/webhook", json=body)
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["status"] == "success"
        assert "patient_id" in result

    def test_register_duplicate(self, client):
        # First registration
        client.post("/vapi/webhook", json=_make_tool_call("registerPatient", VALID_TOOL_ARGS))
        # Second with same phone
        resp = client.post("/vapi/webhook", json=_make_tool_call("registerPatient", VALID_TOOL_ARGS))
        result = resp.json()["result"]
        assert result["status"] == "duplicate"
        assert "patient_id" in result

    def test_register_validation_error(self, client):
        args = {**VALID_TOOL_ARGS, "phone_number": "123"}
        resp = client.post("/vapi/webhook", json=_make_tool_call("registerPatient", args))
        result = resp.json()["result"]
        assert result["status"] == "validation_error"

    def test_register_with_optional_fields(self, client):
        args = {
            **VALID_TOOL_ARGS,
            "email": "john@example.com",
            "insurance_provider": "Blue Cross",
            "insurance_member_id": "BC123",
            "emergency_contact_name": "Jane Doe",
            "emergency_contact_phone": "5559876543",
        }
        resp = client.post("/vapi/webhook", json=_make_tool_call("registerPatient", args))
        assert resp.json()["result"]["status"] == "success"

    def test_dob_iso_format(self, client):
        args = {**VALID_TOOL_ARGS, "date_of_birth": "1990-01-15"}
        resp = client.post("/vapi/webhook", json=_make_tool_call("registerPatient", args))
        assert resp.json()["result"]["status"] == "success"


class TestUpdatePatientWebhook:
    def test_update_success(self, client):
        # Create first
        create_resp = client.post("/vapi/webhook", json=_make_tool_call("registerPatient", VALID_TOOL_ARGS))
        patient_id = create_resp.json()["result"]["patient_id"]

        # Update
        update_args = {"patient_id": patient_id, "email": "updated@example.com"}
        resp = client.post("/vapi/webhook", json=_make_tool_call("updatePatient", update_args))
        result = resp.json()["result"]
        assert result["status"] == "success"


class TestCallEvents:
    def test_call_start(self, client):
        body = {
            "message": {"type": "call-start"},
            "call": {"id": "vapi-call-123", "customer": {"number": "+15551234567"}},
        }
        resp = client.post("/vapi/webhook", json=body)
        assert resp.status_code == 200
        assert "call_id" in resp.json()["data"]

    def test_end_of_call_report(self, client):
        body = {
            "message": {"type": "end-of-call-report"},
            "call": {"id": "vapi-call-456"},
            "transcript": "Agent: Hello! Caller: Hi, I'd like to register.",
            "summary": "Patient registration call",
        }
        resp = client.post("/vapi/webhook", json=body)
        assert resp.status_code == 200

    def test_unknown_function(self, client):
        resp = client.post("/vapi/webhook", json=_make_tool_call("unknownFunction", {}))
        assert resp.status_code == 400

    def test_empty_body(self, client):
        resp = client.post("/vapi/webhook", json={})
        assert resp.status_code == 200
