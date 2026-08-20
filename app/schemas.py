"""Pydantic schemas with validation for the patient data model."""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Optional, Any
from enum import Enum

from pydantic import BaseModel, Field, field_validator, ConfigDict, EmailStr

# ── Constants ─────────────────────────────────────────
VALID_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC",
}
VALID_SEX = {"Male", "Female", "Other", "Decline to Answer"}

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z\-']{0,49}$")
# 10-digit US phone; we normalise to digits-only before validating
PHONE_DIGITS_RE = re.compile(r"^\d{10}$")
ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")


def _normalise_phone(raw: str | None) -> str | None:
    """Strip everything except digits from a US phone number."""
    if raw is None:
        return None
    digits = re.sub(r"\D", "", raw)
    # Drop leading country code 1
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


class SexEnum(str, Enum):
    male = "Male"
    female = "Female"
    other = "Other"
    decline = "Decline to Answer"


# Allow full state names → abbreviation mapping
STATE_NAME_TO_ABBR = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
}

# Allow flexible sex input
SEX_ALIASES = {
    "m": "Male", "male": "Male", "man": "Male",
    "f": "Female", "female": "Female", "woman": "Female",
    "o": "Other", "other": "Other",
    "d": "Decline to Answer", "decline": "Decline to Answer",
    "decline to answer": "Decline to Answer", "prefer not to say": "Decline to Answer",
    "n/a": "Decline to Answer", "na": "Decline to Answer",
}


# ── Patient schemas ──────────────────────────────────
class PatientBase(BaseModel):
    # extra=ignore so LLM passing unexpected fields doesn't cause a validation error
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    date_of_birth: date
    sex: str
    phone_number: str
    email: Optional[EmailStr] = None
    address_line_1: str = Field(..., min_length=1, max_length=255)
    address_line_2: Optional[str] = Field(None, max_length=255)
    city: str = Field(..., min_length=1, max_length=100)
    state: str
    zip_code: str
    insurance_provider: Optional[str] = Field(None, max_length=255)
    insurance_member_id: Optional[str] = Field(None, max_length=100)
    preferred_language: Optional[str] = Field("English", max_length=50)
    emergency_contact_name: Optional[str] = Field(None, max_length=255)
    emergency_contact_phone: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not NAME_RE.match(v):
            raise ValueError("Must be 1–50 alphabetic characters (hyphens/apostrophes allowed)")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: date) -> date:
        if v >= date.today():
            raise ValueError("Date of birth must be in the past")
        # Reasonable upper bound
        if v.year < 1900:
            raise ValueError("Date of birth seems too far in the past")
        return v

    @field_validator("sex")
    @classmethod
    def validate_sex(cls, v: str) -> str:
        v_lower = v.strip().lower()
        if v in VALID_SEX:
            return v
        if v_lower in SEX_ALIASES:
            return SEX_ALIASES[v_lower]
        raise ValueError(f"Sex must be one of: {', '.join(sorted(VALID_SEX))}")

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        norm = _normalise_phone(v)
        if not norm or not PHONE_DIGITS_RE.match(norm):
            raise ValueError("Phone number must be a valid 10-digit US number")
        return norm

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        v_stripped = v.strip()
        v_upper = v_stripped.upper()
        # Already a valid 2-letter abbreviation
        if v_upper in VALID_STATES:
            return v_upper
        # Try full state name
        v_lower = v_stripped.lower()
        if v_lower in STATE_NAME_TO_ABBR:
            return STATE_NAME_TO_ABBR[v_lower]
        raise ValueError("State must be a valid US state (abbreviation or full name)")

    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, v: str) -> str:
        # Extract just the first 5 digits if LLM sent something extra
        digits = re.sub(r"\D", "", v)
        if len(digits) >= 5:
            return digits[:5]
        if not ZIP_RE.match(v):
            raise ValueError("ZIP code must be 5-digit or ZIP+4 format (e.g. 12345 or 12345-6789)")
        return v

    @field_validator("emergency_contact_phone")
    @classmethod
    def validate_emergency_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        norm = _normalise_phone(v)
        if not norm or not PHONE_DIGITS_RE.match(norm):
            raise ValueError("Emergency contact phone must be a valid 10-digit US number")
        return norm


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    """Partial update — all fields optional."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    date_of_birth: Optional[date] = None
    sex: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    address_line_1: Optional[str] = Field(None, min_length=1, max_length=255)
    address_line_2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, min_length=1, max_length=100)
    state: Optional[str] = None
    zip_code: Optional[str] = None
    insurance_provider: Optional[str] = Field(None, max_length=255)
    insurance_member_id: Optional[str] = Field(None, max_length=100)
    preferred_language: Optional[str] = Field(None, max_length=50)
    emergency_contact_name: Optional[str] = Field(None, max_length=255)
    emergency_contact_phone: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if not NAME_RE.match(v):
            raise ValueError("Must be 1–50 alphabetic characters (hyphens/apostrophes allowed)")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: Optional[date]) -> Optional[date]:
        if v is None:
            return None
        if v >= date.today():
            raise ValueError("Date of birth must be in the past")
        if v.year < 1900:
            raise ValueError("Date of birth seems too far in the past")
        return v

    @field_validator("sex")
    @classmethod
    def validate_sex(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v_lower = v.strip().lower()
        if v in VALID_SEX:
            return v
        if v_lower in SEX_ALIASES:
            return SEX_ALIASES[v_lower]
        raise ValueError(f"Sex must be one of: {', '.join(sorted(VALID_SEX))}")

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        norm = _normalise_phone(v)
        if not norm or not PHONE_DIGITS_RE.match(norm):
            raise ValueError("Phone number must be a valid 10-digit US number")
        return norm

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v_stripped = v.strip()
        v_upper = v_stripped.upper()
        if v_upper in VALID_STATES:
            return v_upper
        v_lower = v_stripped.lower()
        if v_lower in STATE_NAME_TO_ABBR:
            return STATE_NAME_TO_ABBR[v_lower]
        raise ValueError("State must be a valid US state (abbreviation or full name)")

    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        digits = re.sub(r"\D", "", v)
        if len(digits) >= 5:
            return digits[:5]
        if not ZIP_RE.match(v):
            raise ValueError("ZIP code must be 5-digit or ZIP+4 format")
        return v

    @field_validator("emergency_contact_phone")
    @classmethod
    def validate_emergency_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        norm = _normalise_phone(v)
        if not norm or not PHONE_DIGITS_RE.match(norm):
            raise ValueError("Emergency contact phone must be a valid 10-digit US number")
        return norm


class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: str
    first_name: str
    last_name: str
    date_of_birth: date
    sex: str
    phone_number: str
    email: Optional[str] = None
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str
    state: str
    zip_code: str
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


# ── Call log schemas ─────────────────────────────────
class CallLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    call_id: str
    patient_id: Optional[str] = None
    vapi_call_id: Optional[str] = None
    caller_phone: Optional[str] = None
    status: str
    transcript: Optional[str] = None
    summary: Optional[str] = None
    collected_data: Optional[Any] = None
    started_at: datetime
    ended_at: Optional[datetime] = None


# ── Appointment schemas ──────────────────────────────
class AppointmentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    scheduled_date: datetime
    provider_name: str = Field("Dr. Smith", max_length=255)
    department: str = Field("General Medicine", max_length=100)
    notes: Optional[str] = None

    @field_validator("scheduled_date")
    @classmethod
    def validate_future(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v <= datetime.now(timezone.utc):
            raise ValueError("Appointment must be in the future")
        return v


class AppointmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    appointment_id: str
    patient_id: str
    scheduled_date: datetime
    provider_name: str
    department: str
    notes: Optional[str] = None
    created_at: datetime


# ── API envelope ─────────────────────────────────────
class Envelope(BaseModel):
    data: Optional[Any] = None
    error: Optional[str] = None
