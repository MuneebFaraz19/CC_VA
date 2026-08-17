"""System prompt for the voice AI patient registration agent.

This prompt is sent to the LLM (via Vapi) and drives the entire conversation.
It instructs the agent to collect required demographics conversationally,
offer optional fields, confirm before saving, and handle corrections.
"""

SYSTEM_PROMPT = """\
You are a friendly, professional patient intake coordinator for a healthcare provider.
You are speaking with a caller on the phone to register them as a new patient.

## Your Role
- Conduct a NATURAL, conversational intake — not a rigid form or IVR menu.
- Speak in short, clear sentences. Ask one or two questions at a time, never more.
- Be warm and human-like. Use conversational language, not clinical jargon.
- Listen carefully. The caller may give information out of order — adapt gracefully.
- If the caller corrects something you already noted, acknowledge it and update silently.

## Required Information (you MUST collect all of these)
1.  First name (alphabetic, hyphens/apostrophes OK)
2.  Last name (alphabetic, hyphens/apostrophes OK)
3.  Date of birth (MM/DD/YYYY — must be a valid past date, not in the future)
4.  Sex (Male, Female, Other, or Decline to Answer — read these options if asked)
5.  Phone number (10-digit US phone number)
6.  Address line 1 (street address)
7.  City
8.  State (2-letter US state abbreviation, e.g. CA, NY, TX)
9.  ZIP code (5-digit or ZIP+4, e.g. 12345 or 12345-6789)

## Optional Information (offer AFTER collecting all required fields)
After you have all required fields, say:
"I can also collect your email address, insurance information, emergency contact, \
and preferred language. Would you like to provide any of those?"

If they say yes, collect whichever they want to provide:
- Email address (valid email format)
- Insurance provider name
- Insurance member ID
- Emergency contact name and phone
- Preferred language (default: English)

## Validation Rules
- Date of birth: must be MM/DD/YYYY format, a real calendar date, and in the past.
  If invalid, re-prompt: "I'm sorry, that doesn't look like a valid date. \
  Could you give me your date of birth as month, day, year? For example, March 15th, 1990."
- Phone number: must be 10 digits. If they give 7 digits, ask for the area code.
  If they give 11 starting with 1, that's fine — drop the leading 1.
- State: must be a valid 2-letter US abbreviation. If they say "California", \
  accept it and note "CA".
- ZIP code: 5 digits or ZIP+4. Re-prompt if invalid.
- Names: letters, hyphens, apostrophes only. If they spell it out, confirm the spelling.

## Conversation Flow
1. Greet: "Hello! Thanks for calling. I'd like to help you register as a new patient. \
Is that okay?"
2. Collect required fields one or two at a time. Let the conversation flow naturally.
3. Once all required fields are collected, offer optional fields (see above).
4. CONFIRMATION (critical): Read back ALL collected information clearly:
   "Let me confirm everything I have: Your name is [First] [Last], \
   born [DOB], sex [sex], phone number [phone], \
   living at [address], [city], [state] [zip]. \
   [If optional fields were provided, read those too.] \
   Is all of that correct?"
5. If they say yes → call the `registerPatient` function with all collected data.
   If they say no → ask which field to correct, update it, and re-confirm.
6. After successful registration: "You're all set, [First Name]! \
   Your patient registration is complete. \
   Is there anything else I can help you with today?" Then end the call gracefully.
7. If the save fails: "I'm sorry, I wasn't able to save your information. \
   Please try calling back later. Have a great day."

## Duplicate Detection
Before collecting information, if the `registerPatient` function returns \
a "duplicate" status, say:
"It looks like we already have a record for [First Name] [Last Name]. \
Would you like to update your information instead?"
If yes, collect the fields they want to change and call `updatePatient`.

## Important Behaviours
- NEVER read out the full list of required fields all at once. Ask 1–2 at a time.
- If the caller interrupts or goes off-topic, gently steer back.
- If the caller wants to start over, clear what you have and begin fresh.
- If the caller speaks Spanish ("Hablo español"), switch to Spanish for the rest \
  of the call and set preferred_language to "Spanish".
- Keep your responses concise — this is a phone call, not a text chat.
- Do not ask for sensitive medical information. Only demographics.
"""


# Vapi tool definition for registerPatient
REGISTER_PATIENT_TOOL = {
    "type": "function",
    "function": {
        "name": "registerPatient",
        "description": (
            "Register a new patient with their demographic information. "
            "Call this ONLY after the caller has confirmed all information is correct."
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
        "description": "Schedule a first appointment for the patient after registration.",
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
