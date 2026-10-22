"""Masking of sensitive values (SSNs, EINs of individuals, account/routing numbers, IP PINs).

Masking is applied in API serializers for every user. Unmasked values are only returned by the explicit reveal
endpoint, which requires clearance and writes a sensitive_access_log row.
"""

import re

SSN_RE = re.compile(r"\b(\d{3})-(\d{2})-(\d{4})\b")
IBAN_RE = re.compile(r"\b([A-Z]{2}\d{2})((?:\s?\d{4}){3,7})\b")
LONG_DIGITS_RE = re.compile(r"(?<![\d.,-])(\d{9,17})(?![\d.,])")
PIN_CONTEXT_RE = re.compile(r"(?i)(ip pin|identity protection pin|pin)[:\s]*(\d{5,6})")

SENSITIVE_VALUE_TYPES = {"ssn", "account_number"}
SENSITIVE_FIELDS = {"ssn", "ip_pin", "account", "routing", "account_number", "pin"}


def mask_ssn(value: str | None) -> str | None:
    if not value:
        return value
    digits = re.sub(r"\D", "", value)
    return f"***-**-{digits[-4:]}" if len(digits) >= 4 else "***"


def mask_account(value: str | None) -> str | None:
    if not value:
        return value
    compact = re.sub(r"\s", "", value)
    return "•" * max(len(compact) - 4, 3) + compact[-4:]


def mask_pin(value: str | None) -> str | None:
    return None if value is None else "•" * len(value)


def mask_value(value_type: str, value):
    if value is None or not isinstance(value, str):
        return value
    if value_type == "ssn":
        return mask_ssn(value)
    if value_type == "account_number":
        return mask_account(value)
    return value


def mask_text(text: str | None) -> str | None:
    """Mask SSNs, IBAN-style and long account numbers, and PINs inside free text (printed page content)."""
    if not text:
        return text
    out = SSN_RE.sub(lambda m: f"***-**-{m.group(3)}", text)
    out = IBAN_RE.sub(lambda m: mask_account(m.group(0)), out)
    out = PIN_CONTEXT_RE.sub(lambda m: f"{m.group(1)} {'•' * len(m.group(2))}", out)
    out = LONG_DIGITS_RE.sub(lambda m: mask_account(m.group(1)), out)
    return out


def is_sensitive_field(field: str, value_type: str | None = None) -> bool:
    return (value_type in SENSITIVE_VALUE_TYPES) or field.lower() in SENSITIVE_FIELDS or "ip_pin" in field.lower()


SENSITIVE_KEY_RE = re.compile(r"(?i)(ssn|ip_pin|routing|account_number|^account$|^pin$)")


def mask_deep(value):
    """Mask free text and sensitive-named keys anywhere inside a JSON-like structure."""
    if isinstance(value, str):
        return mask_text(value)
    if isinstance(value, list):
        return [mask_deep(v) for v in value]
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if isinstance(v, str) and SENSITIVE_KEY_RE.search(str(k)):
                out[k] = mask_pin(v) if "pin" in str(k).lower() else mask_ssn(v) if "ssn" in str(k).lower() \
                    else mask_account(v)
            else:
                out[k] = mask_deep(v)
        return out
    return value
