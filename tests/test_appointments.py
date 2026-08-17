"""Tests for appointment scheduling (bonus feature)."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta


VALID_PATIENT = {
    "first_name": "John",
    "last_name": "Doe",
    "date_of_birth": "1990-01-15",
    "sex": "Male",
    "phone_number": "5551234567",
    "address_line_1": "123 Main St",
    "city": "San Francisco",
    "state": "CA",
    "zip_code": "94102",
}


class TestAppointments:
    def test_create_appointment(self, client):
        create = client.post("/patients", json=VALID_PATIENT)
        pid = create.json()["data"]["patient_id"]
        future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        resp = client.post(f"/patients/{pid}/appointment", json={"scheduled_date": future})
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["patient_id"] == pid
        assert data["provider_name"] == "Dr. Smith"

    def test_get_appointment(self, client):
        create = client.post("/patients", json=VALID_PATIENT)
        pid = create.json()["data"]["patient_id"]
        future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        client.post(f"/patients/{pid}/appointment", json={"scheduled_date": future})
        resp = client.get(f"/patients/{pid}/appointment")
        assert resp.status_code == 200

    def test_appointment_not_found(self, client):
        create = client.post("/patients", json=VALID_PATIENT)
        pid = create.json()["data"]["patient_id"]
        resp = client.get(f"/patients/{pid}/appointment")
        assert resp.status_code == 404

    def test_past_date_rejected(self, client):
        create = client.post("/patients", json=VALID_PATIENT)
        pid = create.json()["data"]["patient_id"]
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        resp = client.post(f"/patients/{pid}/appointment", json={"scheduled_date": past})
        assert resp.status_code == 422

    def test_appointment_for_nonexistent_patient(self, client):
        future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        resp = client.post("/patients/nonexistent/appointment", json={"scheduled_date": future})
        assert resp.status_code == 404
