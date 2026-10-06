"""Format email messages without sending them."""
from typing import TypedDict


class EmailMessage(TypedDict):
    to: str
    subject: str
    text: str

def format_subject(name: str) -> str:
    return f"Hello {name}"

def create_email(to: str, subject: str, text: str) -> EmailMessage:
    return {"to": to, "subject": subject, "text": text}
