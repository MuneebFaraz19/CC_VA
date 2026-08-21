"""System prompt for the voice AI patient registration agent.

This prompt is sent to the LLM (via Vapi) and drives the entire conversation.
It instructs the agent to collect required demographics conversationally,
offer optional fields, confirm before saving, and handle corrections.
"""

SYSTEM_PROMPT = """\
You are a friendly patient registration assistant for a healthcare clinic. \
You are on a phone call. Your goal is to register the caller as a new patient \
by collecting their information naturally and efficiently.

The current date is August 21, 2026. When the caller gives a date without a \
year (e.g. "August 26th"), assume the year 2026. If that date has already \
passed, use 2027. Always use future dates for appointments.

## What to collect (in this order)
1. First and last name — ask together: "What's your first and last name?"
2. Date of birth — "And your date of birth?"
3. Sex — "And what's your Gender? Male, Female, Other, or you can decline."
4. Phone number — "What's the best phone number to reach you?"
5. Address — ask as one question: "What's your street address, city, state, and zip code?"

That's it for required fields. Keep moving — do NOT ask the caller to confirm \
each individual field. Trust what you heard.

## After collecting all five items
Offer optional info in ONE question: "I can also note your email, insurance, \
or emergency contact if you'd like. Anything to add?" If they say no, move on.

## Final confirmation (ONLY once)
Give a quick summary: "Great, so that's [name], born [DOB], [sex], phone [number], \
at [address]. I'll get you registered now." Then immediately call registerPatient.
Do NOT ask "is that correct?" — just register. If they correct something, \
fix it and proceed.

## Rules
- Be very brief. One short sentence at a time. This is a phone call, not a form.
- Never repeat a question you already got an answer to.
- Never spell a name back to the caller. Just use it.
- If the caller gives multiple pieces of info at once, accept all of it and \
continue with whatever's still missing.
- If the caller interrupts or corrects you, stop immediately and acknowledge \
the correction in 3-5 words, then continue.
- If registerPatient returns a duplicate, tell the caller and ask if they'd \
like to update instead.
- After successful registration: "You're all set! You're registered as a \
patient. Would you like to schedule a first appointment?" \
If yes, ask for a preferred date and time and call scheduleAppointment. \
You MUST pass the exact patient_id UUID returned by registerPatient — \
do NOT make up a patient_id. For the date, always use YYYY-MM-DD format \
with the full year (2026 or later). \
If no, say "No problem. Have a great day!" and end the call.
"""


# Vapi tool definition for registerPatient
REGISTER_PATIENT_TOOL = {
    "type": "function",
    "function": {
        "name": "registerPatient",
        "description": (
            "Register a new patient with their demographic information. "
            "Call this after you have collected all required fields and given "
            "a brief summary to the caller."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "first_name": {"type": "string", "description": "Patient's first name"},
                "last_name": {"type": "string", "description": "Patient's last name"},
                "date_of_birth": {
                    "type": "string",
                    "description": "Date of birth in MM/DD/YYYY format",
                },
                "sex": {
                    "type": "string",
                    "enum": ["Male", "Female", "Other", "Decline to Answer"],
                    "description": "Biological sex or decline to answer",
                },
                "phone_number": {
                    "type": "string",
                    "description": "10-digit US phone number (digits only or formatted)",
                },
                "email": {"type": "string", "description": "Email address (optional)"},
                "address_line_1": {"type": "string", "description": "Street address"},
                "address_line_2": {
                    "type": "string",
                    "description": "Apartment/suite/unit (optional)",
                },
                "city": {"type": "string", "description": "City"},
                "state": {
                    "type": "string",
                    "description": "2-letter US state abbreviation",
                },
                "zip_code": {"type": "string", "description": "5-digit or ZIP+4 ZIP code"},
                "insurance_provider": {
                    "type": "string",
                    "description": "Insurance company name (optional)",
                },
                "insurance_member_id": {
                    "type": "string",
                    "description": "Insurance member/subscriber ID (optional)",
                },
                "preferred_language": {
                    "type": "string",
                    "description": "Preferred language, default English",
                },
                "emergency_contact_name": {
                    "type": "string",
                    "description": "Emergency contact full name (optional)",
                },
                "emergency_contact_phone": {
                    "type": "string",
                    "description": "Emergency contact 10-digit phone (optional)",
                },
            },
            "required": [
                "first_name", "last_name", "date_of_birth", "sex",
                "phone_number", "address_line_1", "city", "state", "zip_code",
            ],
        },
    },
}


# Vapi tool for updating an existing patient
UPDATE_PATIENT_TOOL = {
    "type": "function",
    "function": {
        "name": "updatePatient",
        "description": "Update an existing patient's information. Only call when a duplicate was detected.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "The existing patient's UUID"},
                "first_name": {"type": "string"},
                "last_name": {"type": "string"},
                "date_of_birth": {"type": "string", "description": "MM/DD/YYYY"},
                "sex": {"type": "string", "enum": ["Male", "Female", "Other", "Decline to Answer"]},
                "phone_number": {"type": "string"},
                "email": {"type": "string"},
                "address_line_1": {"type": "string"},
                "address_line_2": {"type": "string"},
                "city": {"type": "string"},
                "state": {"type": "string"},
                "zip_code": {"type": "string"},
                "insurance_provider": {"type": "string"},
                "insurance_member_id": {"type": "string"},
                "preferred_language": {"type": "string"},
                "emergency_contact_name": {"type": "string"},
                "emergency_contact_phone": {"type": "string"},
            },
            "required": ["patient_id"],
        },
    },
}


# Vapi tool for scheduling an appointment (bonus)
SCHEDULE_APPOINTMENT_TOOL = {
    "type": "function",
    "function": {
        "name": "scheduleAppointment",
        "description": (
            "Schedule a first appointment for the patient after registration. "
            "The patient_id MUST be the exact UUID returned by registerPatient."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "The patient's UUID"},
                "date": {"type": "string", "description": "Appointment date (YYYY-MM-DD)"},
                "time": {"type": "string", "description": "Appointment time (HH:MM, 24-hour)"},
                "provider_name": {"type": "string", "description": "Provider name, default Dr. Smith"},
            },
            "required": ["patient_id", "date", "time"],
        },
    },
}


ALL_TOOLS = [REGISTER_PATIENT_TOOL, UPDATE_PATIENT_TOOL, SCHEDULE_APPOINTMENT_TOOL]
