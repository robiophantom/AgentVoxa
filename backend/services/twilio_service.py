"""Twilio call handling helpers.

Builds TwiML responses for inbound calls, transfer, and hangup flows.
"""
from __future__ import annotations

from xml.etree.ElementTree import Element, SubElement, tostring

from core.config import get_settings

settings = get_settings()


def _to_xml(response: Element) -> str:
    return tostring(response, encoding="unicode")


def build_answer_twiml(websocket_url: str) -> str:
    """Return TwiML that greets and connects a call to Twilio Media Streams."""
    response = Element("Response")

    say = SubElement(response, "Say")
    say.text = (
        "Hello! You have reached AgentVoxa, your AI receptionist. "
        "Please hold while I connect you."
    )

    connect = SubElement(response, "Connect")
    stream = SubElement(connect, "Stream")
    stream.set("url", websocket_url)

    return _to_xml(response)


def build_transfer_twiml(to_number: str) -> str:
    """Return TwiML to transfer the call to human staff."""
    response = Element("Response")

    say = SubElement(response, "Say")
    say.text = "Please hold while I transfer you to a human staff member."

    dial = SubElement(response, "Dial")
    if settings.twilio_phone_number:
        dial.set("callerId", settings.twilio_phone_number)
    number = SubElement(dial, "Number")
    number.text = to_number

    return _to_xml(response)


def build_hangup_twiml(message: str = "Thank you for calling. Goodbye!") -> str:
    """Return TwiML to say a closing message and hang up."""
    response = Element("Response")
    say = SubElement(response, "Say")
    say.text = message
    SubElement(response, "Hangup")
    return _to_xml(response)
