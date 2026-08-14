"""Compatibility facade for accident presentation builders."""

from .modern import generate_presentation
from .traditional import generate_traditional_presentation

__all__ = ["generate_presentation", "generate_traditional_presentation"]
