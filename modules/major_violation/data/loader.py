"""Read and normalize multiple major-violation workbooks."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from core.excel import read_excel_source

from .schema import ViolationDataset, ViolationSourceInfo
from .transformer import (
    VIOLATION_PREFERRED_HEADERS,
    merge_violation_datasets,
    transform_violation_source,
)


def load_violation_workbooks(paths: Iterable[str | Path]) -> ViolationDataset:
    """Load every workbook independently and retain per-file failures."""
    datasets: list[ViolationDataset] = []
    failed_sources: list[ViolationSourceInfo] = []
    for index, source_path in enumerate(paths, start=1):
        path = Path(source_path)
        source_id = f"source-{index}"
        try:
            source = read_excel_source(
                path,
                preferred_headers=VIOLATION_PREFERRED_HEADERS,
                count_field="件數",
            )
            datasets.append(transform_violation_source(
                source.to_dict(),
                source_name=path.name,
                source_id=source_id,
            ))
        except (OSError, ValueError) as error:
            failed_sources.append(ViolationSourceInfo(
                source_id=source_id,
                file_name=path.name,
                sheet_name=None,
                source_type="unknown",
                row_mode="unknown",
                status="failed",
                raw_row_count=0,
                warnings=(str(error),),
            ))
    return merge_violation_datasets(datasets, extra_sources=failed_sources)
