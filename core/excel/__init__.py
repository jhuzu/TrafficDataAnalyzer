"""Excel data-source readers shared by analysis modules."""

from .models import ExcelDataSource
from .source_detector import read_excel_source

__all__ = ["ExcelDataSource", "read_excel_source"]
