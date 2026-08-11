#!/usr/bin/env python3
"""Compatibility CLI for the one-click Pivot Cache extractor."""

import json
import sys
from pathlib import Path

from core.excel.pivot_cache_reader import read_pivot_cache_source


def main(source: str, output: str) -> None:
    data = read_pivot_cache_source(source).to_dict()
    Path(output).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("用法：extract_pivot_cache.py 來源.xlsm 暫存.json")
    try:
        main(sys.argv[1], sys.argv[2])
    except (ValueError, OSError) as error:
        raise SystemExit(str(error)) from error
