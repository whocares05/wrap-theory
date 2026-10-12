import re

from app.core.errors import bad_request


def normalize_pakistani_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if digits.startswith("0092"):
        normalized = f"+{digits[2:]}"
    elif digits.startswith("92"):
        normalized = f"+{digits}"
    elif digits.startswith("0"):
        normalized = f"+92{digits[1:]}"
    else:
        normalized = f"+92{digits}"
    if not re.fullmatch(r"\+923\d{9}", normalized):
        raise bad_request("Enter a valid Pakistani mobile number")
    return normalized
