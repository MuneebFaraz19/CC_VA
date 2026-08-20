"""Script to create a Vapi assistant and provision a phone number.

Usage:
    python -m app.setup_vapi

This will:
1. Create a Vapi assistant with the system prompt and tool definitions.
2. Buy a US phone number.
3. Link the assistant to the phone number.
4. Print the IDs to add to your .env file.

Requires VAPI_API_KEY in your environment.
"""
from __future__ import annotations

import json
import sys
import logging

import httpx

from app.config import get_settings
from app.voice_prompt import SYSTEM_PROMPT, ALL_TOOLS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

VAPI_BASE = "https://api.vapi.ai"


def create_assistant(api_key: str, webhook_url: str) -> dict:
    """Create a Vapi assistant configured for patient registration."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Configure the assistant with Groq as the LLM model provider.
    # NOTE: Vapi's current API uses `model` (not `llm`) and `server: {url}`
    # (not `serverUrl`/`modelUrl`) for webhook configuration.
    payload = {
        "name": "Patient Registration Agent",
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "en-US",
            "endpointing": 200,          # ms — detect end-of-speech faster for quicker barge-in
            "profanityFilter": False,
        },
        "model": {
            "provider": "groq",
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                }
            ],
            "tools": ALL_TOOLS,
            "temperature": 0.4,
            "maxTokens": 200,            # shorter responses = faster generation, less audio to interrupt through
        },
        "voice": {
            "provider": "11labs",
            "voiceId": "21m00Tcm4TlvDq8ikWAM",  # Rachel (ElevenLabs)
            "stability": 0.4,
            "similarityBoost": 0.6,
            "speed": 1.1,               # slightly faster speech delivery
        },
        "firstMessage": (
            "Hi, thanks for calling! I can help you register as a new patient. "
            "What's your first and last name?"
        ),
        "recordingEnabled": True,
        "silenceTimeoutSeconds": 30,   # keep generous — users may pause to find info
        "maxDurationSeconds": 300,
        "responseDelaySeconds": 0,
        "server": {
            "url": webhook_url,  # Vapi sends tool-call + call events here
        },
    }

    logger.info("Creating Vapi assistant...")
    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{VAPI_BASE}/assistant", headers=headers, json=payload)
        resp.raise_for_status()
        assistant = resp.json()
    logger.info("Assistant created: id=%s", assistant.get("id"))
    return assistant


def update_assistant(api_key: str, assistant_id: str, webhook_url: str) -> dict:
    """Update an existing Vapi assistant with the current prompt and config."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    payload = {
        "name": "Patient Registration Agent",
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "en-US",
            "endpointing": 200,          # ms — detect end-of-speech faster for quicker barge-in
            "profanityFilter": False,
        },
        "model": {
            "provider": "groq",
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                }
            ],
            "tools": ALL_TOOLS,
            "temperature": 0.4,
            "maxTokens": 200,            # shorter responses = faster generation, less audio to interrupt through
        },
        "voice": {
            "provider": "11labs",
            "voiceId": "21m00Tcm4TlvDq8ikWAM",
            "stability": 0.4,
            "similarityBoost": 0.6,
            "speed": 1.1,               # slightly faster speech delivery
        },
        "firstMessage": (
            "Hi, thanks for calling! I can help you register as a new patient. "
            "What's your first and last name?"
        ),
        "recordingEnabled": True,
        "silenceTimeoutSeconds": 30,   # keep generous — users may pause to find info
        "maxDurationSeconds": 300,
        "responseDelaySeconds": 0,
        "server": {
            "url": webhook_url,
        },
    }

    logger.info("Updating Vapi assistant %s...", assistant_id)
    with httpx.Client(timeout=30) as client:
        resp = client.patch(f"{VAPI_BASE}/assistant/{assistant_id}", headers=headers, json=payload)
        resp.raise_for_status()
        assistant = resp.json()
    logger.info("Assistant updated: id=%s", assistant.get("id"))
    return assistant


def buy_phone_number(api_key: str, assistant_id: str) -> dict:
    """Buy a US phone number and link it to the assistant."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    payload = {
        "provider": "vapi",
        "assistantId": assistant_id,
        "numberDesiredAreaCode": "415",  # San Francisco area code
        "name": "Patient Registration Line",
    }

    logger.info("Provisioning US phone number...")
    with httpx.Client(timeout=30) as client:
        # Try to create a phone number
        resp = client.post(f"{VAPI_BASE}/phone-number", headers=headers, json=payload)
        if resp.status_code == 422:
            # Vapi might need Twilio credentials — try the "buy" endpoint
            logger.warning("Direct provisioning failed, trying alternative...")
            resp = client.post(f"{VAPI_BASE}/phone-number/buy", headers=headers, json=payload)
        resp.raise_for_status()
        number = resp.json()
    logger.info("Phone number provisioned: %s", number.get("number"))
    return number


def main() -> None:
    settings = get_settings()

    if not settings.vapi_api_key or settings.vapi_api_key == "your_vapi_api_key_here":
        logger.error("VAPI_API_KEY is not set. Please set it in your .env file.")
        sys.exit(1)

    webhook_url = f"{settings.public_base_url}/vapi/webhook"
    logger.info("Webhook URL: %s", webhook_url)

    # If VAPI_ASSISTANT_ID is set, update the existing assistant instead of creating a new one
    if settings.vapi_assistant_id:
        logger.info("VAPI_ASSISTANT_ID is set — updating existing assistant...")
        try:
            assistant = update_assistant(settings.vapi_api_key, settings.vapi_assistant_id, webhook_url)
            print(f"\n✅ Assistant updated: {assistant['id']}")
            print("   The phone number linked to this assistant now uses the updated prompt.")
        except httpx.HTTPStatusError as e:
            logger.error("Vapi API error: %s - %s", e.response.status_code, e.response.text)
            sys.exit(1)
        except Exception as e:
            logger.error("Unexpected error: %s", e)
            sys.exit(1)
        return

    try:
        assistant = create_assistant(settings.vapi_api_key, webhook_url)
        assistant_id = assistant["id"]
        print(f"\n✅ Assistant created: {assistant_id}")
        print(f"   Add to .env: VAPI_ASSISTANT_ID={assistant_id}")

        try:
            number = buy_phone_number(settings.vapi_api_key, assistant_id)
            number_id = number.get("id", "")
            phone = number.get("number", "N/A")
            print(f"\n✅ Phone number provisioned: {phone}")
            print(f"   Add to .env: VAPI_PHONE_NUMBER_ID={number_id}")
            print(f"\n📞 Call this number to test: {phone}")
        except Exception as e:
            logger.error("Could not provision phone number: %s", e)
            print("\n⚠️  Could not provision a phone number automatically.")
            print("   You may need to:")
            print("   1. Add a Twilio account in the Vapi dashboard, OR")
            print("   2. Import an existing Twilio number, OR")
            print("   3. Buy a number directly in the Vapi dashboard.")
            print(f"\n   Then link it to assistant: {assistant_id}")

    except httpx.HTTPStatusError as e:
        logger.error("Vapi API error: %s - %s", e.response.status_code, e.response.text)
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
