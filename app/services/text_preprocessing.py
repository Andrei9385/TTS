from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.auto_accent import AutoAccentAdapter, NoOpAutoAccentAdapter

_WHITESPACE_RE = re.compile(r"\s+")
_DUP_PUNCT_RE = re.compile(r"([!?.,:;])\1{1,}")
_PUNCT_SPACING_RE = re.compile(r"\s+([!?.,:;])")
_PLUS_GAP_RE = re.compile(r"\+\s+")

_ALLOWED_TEXT_RE = re.compile(r"^[а-яёА-ЯЁ0-9\s+.,:;!?()\[\]""'«»—\-…]*$")
_HAS_RUSSIAN_LETTER_RE = re.compile(r"[а-яёА-ЯЁ]")


@dataclass
class TextValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class PreprocessResult:
    original_text: str
    cleaned_text: str
    stressed_text: str
    final_text: str
    auto_accent_applied: bool
    adapter_name: str
    validation: TextValidationResult


def normalize_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def normalize_punctuation_conservative(text: str) -> str:
    cleaned = text.replace("…", "...")
    cleaned = cleaned.replace("“", '"').replace("”", '"').replace("’", "'")
    cleaned = _DUP_PUNCT_RE.sub(r"\1", cleaned)
    cleaned = _PUNCT_SPACING_RE.sub(r"\1", cleaned)
    cleaned = cleaned.replace(" ,", ",").replace(" .", ".")
    return cleaned


def preserve_stress_markers(text: str) -> str:
    # Keep '+' exactly as stress marker and only remove surrounding accidental gaps.
    return _PLUS_GAP_RE.sub("+", text)


def validate_russian_text_input(text: str) -> TextValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not text.strip():
        errors.append("Text cannot be empty.")

    if not _HAS_RUSSIAN_LETTER_RE.search(text):
        warnings.append("Text does not contain Russian letters.")

    if not _ALLOWED_TEXT_RE.fullmatch(text):
        errors.append(
            "Text contains unsupported characters. Allowed: Russian letters, digits, spaces, '+', and basic punctuation."
        )

    if "++" in text:
        warnings.append("Found consecutive '+' markers. Please verify stress placement.")

    return TextValidationResult(is_valid=not errors, errors=errors, warnings=warnings)


def preprocess_text(
    text: str,
    auto_accent_adapter: AutoAccentAdapter | None = None,
    enable_auto_accent: bool = False,
) -> PreprocessResult:
    adapter = auto_accent_adapter or NoOpAutoAccentAdapter()

    cleaned = normalize_whitespace(text)
    cleaned = normalize_punctuation_conservative(cleaned)
    stressed = preserve_stress_markers(cleaned)

    validation = validate_russian_text_input(stressed)

    if enable_auto_accent and validation.is_valid:
        final_text = adapter.apply(stressed)
        applied = True
    else:
        final_text = stressed
        applied = False

    return PreprocessResult(
        original_text=text,
        cleaned_text=cleaned,
        stressed_text=stressed,
        final_text=final_text,
        auto_accent_applied=applied,
        adapter_name=adapter.name,
        validation=validation,
    )
