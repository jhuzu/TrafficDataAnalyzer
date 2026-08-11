"""Data contracts and normalization for major-violation workbooks."""

from .loader import load_violation_workbooks
from .exporter import STANDARDIZED_HEADERS, build_standardized_export
from .schema import ViolationDataset, ViolationRecord, ViolationSourceInfo
from .transformer import (
    VIOLATION_PREFERRED_HEADERS,
    merge_violation_datasets,
    transform_violation_source,
)

__all__ = [
    "VIOLATION_PREFERRED_HEADERS",
    "STANDARDIZED_HEADERS",
    "ViolationDataset",
    "ViolationRecord",
    "ViolationSourceInfo",
    "load_violation_workbooks",
    "build_standardized_export",
    "merge_violation_datasets",
    "transform_violation_source",
]
