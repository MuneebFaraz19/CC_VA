"""Tests for patient CRUD API endpoints."""
from __future__ import annotations

import pytest

# Valid patient payload used across tests
VALID_PATIENT = {
    "first_name": "John",
    "last_name": "Doe",
    "date_of_birth": "1990-01-15",
    "sex": "Male",
    "phone_number": "5551234567",
    "email": "john.doe@example.com",
    "address_line_1": "123 Main St",
    "address_line_2": "Apt 2",
    "city": "San Francisco",
    "state": "CA",
    "zip_code": "94102",
    "insurance_provider": "Blue Cross",
    "insurance_member_id": "BC123",
    "preferred_language": "English",
    "emergency_contact_name": "Jane Doe",
    "emergency_contact_phone": "5559876543",
}


class TestCreatePatient:
    def test_create_valid_patient(self, client):
        resp = client.post("/patients", json=VALID_PATIENT)
        assert resp.status_code == 201
        body = resp.json()
        assert body["error"] is None
        data = body["data"]
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"
        assert data["patient_id"] is not None
        assert data["phone_number"] == "5551234567"
        assert data["deleted_at"] is None

    def test_create_minimal_required_only(self, client):
        minimal = {
            "first_name": "Jane",
            "last_name": "Smith",
            "date_of_birth": "1985-06-20",
            "sex": "Female",
            "phone_number": "5551112222",
            "address_line_1": "456 Oak Ave",
            "city": "New York",
            "state": "NY",
            "zip_code": "10001",
        }
        resp = client.post("/patients", json=minimal)
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["email"] is None
        assert data["preferred_language"] == "English"

    def test_create_normalises_phone(self, client):
        payload = {**VALID_PATIENT, "phone_number": "(555) 123-4567"}
        resp = client.post("/patients", json=payload)
        assert resp.status_code == 201
        assert resp.json()["data"]["phone_number"] == "5551234567"

    def test_create_normalises_phone_with_country_code(self, client):
        payload = {**VALID_PATIENT, "phone_number": "1-555-123-4567"}
        resp = client.post("/patients", json=payload)
        assert resp.status_code == 201
        assert resp.json()["data"]["phone_number"] == "5551234567"

    def test_create_normalises_state_uppercase(self, client):
        payload = {**VALID_PATIENT, "state": "ca"}
        resp = client.post("/patients", json=payload)
        assert resp.status_code == 201
        assert resp.json()["data"]["state"] == "CA"

    def test_create_with_zip_plus_4(self, client):
        payload = {**VALID_PATIENT, "zip_code": "94102-1234"}
        resp = client.post("/patients", json=payload)
        assert resp.status_code == 201

    def test_create_with_hyphenated_name(self, client):
        payload = {**VALID_PATIENT, "first_name": "Mary-Jane", "last_name": "O'Brien"}
        resp = client.post("/patients", json=payload)
        assert resp.status_code == 201
        assert resp.json()["data"]["first_name"] == "Mary-Jane"

    def test_reject_invalid_email(self, client):
        payload = {**VALID_PATIENT, "email": "not-an-email"}
        resp = client.post("/patients", json=payload)
        assert resp.status_code == 422

    def test_reject_future_dob(self, client):
        payload = {**VALID_PATIENT, "date_of_birth": "2099-01-01"}
        resp = client.post("/patients", json=payload)
        assert resp.status_code == 422

    def test_reject_short_phone(self, client):
        payload = {**VALID_PATIENT, "phone_number": "1234567"}
        resp = client.post("/patients", json=payload)
        assert resp.status_code == 422

    def test_reject_invalid_state(self, client):
        payload = {**VALID_PATIENT, "state": "XX"}
        resp = client.post("/patients", json=payload)
        assert resp.status_code == 422

    def test_reject_invalid_zip(self, client):
        payload = {**VALID_PATIENT, "zip_code": "1234"}
        resp = client.post("/patients", json=payload)
        assert resp.status_code == 422

    def test_reject_invalid_sex(self, client):
        payload = {**VALID_PATIENT, "sex": "Unknown"}
        resp = client.post("/patients", json=payload)
        assert resp.status_code == 422

    def test_reject_missing_required_field(self, client):
        payload = {**VALID_PATIENT}
        del payload["first_name"]
        resp = client.post("/patients", json=payload)
        assert resp.status_code == 422

    def test_reject_numeric_name(self, client):
        payload = {**VALID_PATIENT, "first_name": "John123"}
        resp = client.post("/patients", json=payload)
        assert resp.status_code == 422


class TestGetPatient:
    def test_get_existing(self, client):
        create = client.post("/patients", json=VALID_PATIENT)
        pid = create.json()["data"]["patient_id"]
        resp = client.get(f"/patients/{pid}")
        assert resp.status_code == 200
        assert resp.json()["data"]["patient_id"] == pid

    def test_get_not_found(self, client):
        resp = client.get("/patients/nonexistent-uuid")
        assert resp.status_code == 404
        assert resp.json()["error"] == "Patient not found"

    def test_get_deleted_returns_404(self, client):
        create = client.post("/patients", json=VALID_PATIENT)
        pid = create.json()["data"]["patient_id"]
        client.delete(f"/patients/{pid}")
        resp = client.get(f"/patients/{pid}")
        assert resp.status_code == 404


class TestListPatients:
    def test_list_empty(self, client):
        resp = client.get("/patients")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_list_with_patients(self, client):
        client.post("/patients", json=VALID_PATIENT)
        client.post("/patients", json={**VALID_PATIENT, "first_name": "Jane", "phone_number": "5559998888"})
        resp = client.get("/patients")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 2

    def test_filter_by_last_name(self, client):
        client.post("/patients", json=VALID_PATIENT)
        client.post("/patients", json={**VALID_PATIENT, "last_name": "Smith", "phone_number": "5559998888"})
        resp = client.get("/patients?last_name=Doe")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["last_name"] == "Doe"

    def test_filter_by_phone(self, client):
        client.post("/patients", json=VALID_PATIENT)
        resp = client.get("/patients?phone_number=5551234567")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1


class TestUpdatePatient:
    def test_partial_update(self, client):
        create = client.post("/patients", json=VALID_PATIENT)
        pid = create.json()["data"]["patient_id"]
        resp = client.put(f"/patients/{pid}", json={"email": "new.email@example.com"})
        assert resp.status_code == 200
        assert resp.json()["data"]["email"] == "new.email@example.com"
        # Other fields unchanged
        assert resp.json()["data"]["first_name"] == "John"

    def test_update_not_found(self, client):
        resp = client.put("/patients/nonexistent", json={"first_name": "Test"})
        assert resp.status_code == 404

    def test_update_validation_error(self, client):
        create = client.post("/patients", json=VALID_PATIENT)
        pid = create.json()["data"]["patient_id"]
        resp = client.put(f"/patients/{pid}", json={"phone_number": "123"})
        assert resp.status_code == 422


class TestDeletePatient:
    def test_soft_delete(self, client):
        create = client.post("/patients", json=VALID_PATIENT)
        pid = create.json()["data"]["patient_id"]
        resp = client.delete(f"/patients/{pid}")
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted_at"] is not None

    def test_delete_not_found(self, client):
        resp = client.delete("/patients/nonexistent")
        assert resp.status_code == 404

    def test_deleted_not_in_list(self, client):
        create = client.post("/patients", json=VALID_PATIENT)
        pid = create.json()["data"]["patient_id"]
        client.delete(f"/patients/{pid}")
        resp = client.get("/patients")
        assert len(resp.json()["data"]) == 0


class TestAPIEnvelope:
    def test_success_envelope(self, client):
        resp = client.get("/patients")
        body = resp.json()
        assert "data" in body
        assert "error" in body
        assert body["error"] is None

    def test_error_envelope(self, client):
        resp = client.get("/patients/nonexistent")
        body = resp.json()
        assert body["data"] is None
        assert body["error"] is not None


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
