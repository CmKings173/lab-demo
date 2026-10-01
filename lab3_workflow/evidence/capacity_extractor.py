"""Narrow, deterministic extraction of maximum product capacities."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

_FIELDS = {"max_ram_gb", "max_gpu_slots", "max_storage_gb"}
_NUMBER = r"(?<![\w.+-])(?P<number>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
_UNIT = r"(?:tb|gb)(?![\w/])"
_AMOUNT = rf"{_NUMBER}\s*(?P<unit>{_UNIT})"
_COUNT = _NUMBER


def extract_capacity_value(text: str, field_name: str) -> int | None:
    """Return one explicit supported maximum/capacity value, or fail closed.

    RAM and storage accept GB/TB only (1 TB = 1024 GB). GPU slots accept an
    explicit maximum count or a direct ``N GPU slots`` declaration. Multiple
    different candidate values, unsupported units, malformed numbers, and
    non-integral conversions are rejected. This is a rule parser, not a truth
    or confidence assessment.
    """

    if field_name not in _FIELDS or not isinstance(text, str) or not text.strip():
        return None

    normalized = _normalize(text)
    if field_name == "max_gpu_slots":
        candidates = _extract_gpu_counts(normalized)
    else:
        subject = (
            r"(?:ram|memory)"
            if field_name == "max_ram_gb"
            else r"(?:storage(?:\s+capacity)?|luu\s+tru|o\s+cung)"
        )
        candidates = _extract_capacity_amounts(normalized, subject)

    unique = set(candidates)
    return next(iter(unique)) if len(unique) == 1 else None


def _normalize(text: str) -> str:
    folded = text.casefold().replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", folded)
    unaccented = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", unaccented)


def _extract_capacity_amounts(text: str, subject: str) -> list[int]:
    maximum = r"(?:maximum|max|toi\s+da)"
    patterns = (
        rf"{maximum}\s+(?:supported\s+)?{subject}\b\s*(?:capacity\s*)?"
        rf"(?:up\s+to\s*)?[:=]?\s*{_AMOUNT}",
        rf"{subject}\b\s*(?:capacity\s*)?(?:{maximum}|up\s+to)\s*[:=]?\s*{_AMOUNT}",
        rf"(?:supports?\s+)?up\s+to\s+{_AMOUNT}\s+{subject}\b",
    )
    values: list[int] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            if _has_installed_configuration_context(text, match.start(), match.end()):
                return []
            if _has_alternative_value(text, match.end(), require_unit=True):
                return []
            amount = _decimal(match.group("number"))
            if amount is None:
                continue
            multiplier = Decimal(1024) if match.group("unit") == "tb" else Decimal(1)
            gigabytes = amount * multiplier
            if gigabytes >= 0 and gigabytes == gigabytes.to_integral_value():
                values.append(int(gigabytes))
    return values


def _extract_gpu_counts(text: str) -> list[int]:
    subject = r"(?:gpu(?:s)?|graphics\s+cards?)"
    maximum = r"(?:maximum|max|toi\s+da)"
    patterns = (
        rf"{maximum}\s+(?:supported\s+)?{subject}(?:\s+slots?)?\b\s*[:=]?\s*{_COUNT}",
        rf"{subject}\s+{maximum}\s*[:=]?\s*{_COUNT}",
        rf"(?:supports?\s+)?up\s+to\s+{_COUNT}\s+{subject}\b",
        rf"{_COUNT}\s+{subject}\s+slots?\b",
    )
    values: list[int] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            if _has_installed_configuration_context(text, match.start(), match.end()):
                return []
            if _has_alternative_value(text, match.end(), require_unit=False):
                return []
            count = _decimal(match.group("number"))
            if count is not None and count >= 0 and count == count.to_integral_value():
                values.append(int(count))
    return values


def _has_installed_configuration_context(text: str, start: int, end: int) -> bool:
    separators = ".!?;"
    last_separator = max(
        (text.rfind(separator, 0, start) for separator in separators), default=-1
    )
    clause_start = last_separator + 1
    clause_ends = [text.find(separator, end) for separator in separators]
    clause_end = min((position for position in clause_ends if position >= 0), default=len(text))
    clause = text[clause_start:clause_end]
    return re.search(
        r"\b(?:installed|configured|equipped|current(?:ly)?\s+(?:configuration|system|setup|installation))\b",
        clause,
    ) is not None


def _has_alternative_value(text: str, end: int, *, require_unit: bool) -> bool:
    tail = re.split(r"[.!?;\n]", text[end:], maxsplit=1)[0]
    qualifier = r"(?:(?:up\s+to|maximum|max)\s+)?"
    unit = rf"\s*{_UNIT}" if require_unit else r"\b"
    return re.match(
        rf"\s*(?:or|and|/)\s*{qualifier}{_NUMBER}{unit}",
        tail,
    ) is not None


def _decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value.replace(",", ""))
    except InvalidOperation:
        return None
