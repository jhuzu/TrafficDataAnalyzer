"""Presentation data contract for the traffic-accident module."""

from .payload_builder import SCHEMA_VERSION, build_presentation_payload
from .service import AccidentPresentationService, GeneratedPresentation

__all__ = [
    "AccidentPresentationService",
    "GeneratedPresentation",
    "SCHEMA_VERSION",
    "build_presentation_payload",
]
