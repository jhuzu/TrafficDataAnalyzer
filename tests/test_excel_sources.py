import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from core.excel.source_detector import read_excel_source


PREFERRED = {
    "事故類別", "發生月", "發生時間", "路段", "交叉路名", "肇事原因",
    "年齡", "當事者區分", "件數",
}


def column_name(index):
    output = ""
    value = index + 1
    while value:
        value, remainder = divmod(value - 1, 26)
        output = chr(65 + remainder) + output
    return output


def worksheet_xml(rows):
    row_nodes = []
    for row_number, row in enumerate(rows, start=1):
        cells = []
        for column, value in enumerate(row):
            if value is None:
                continue
            ref = f"{column_name(column)}{row_number}"
            if isinstance(value, (int, float)):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                cells.append(
                    f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
                )
        row_nodes.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(row_nodes)}</sheetData></worksheet>'
    )


def pivot_xml(fields, rows):
    shared = []
    indexes = []
    for column, _ in enumerate(fields):
        values = []
        mapping = {}
        for row in rows:
            value = row[column]
            if isinstance(value, str) and value not in mapping:
                mapping[value] = len(values)
                values.append(value)
        shared.append(values)
        indexes.append(mapping)
    field_nodes = []
    for name, values in zip(fields, shared):
        items = "".join(f'<s v="{escape(value)}"/>' for value in values)
        field_nodes.append(
            f'<cacheField name="{escape(name)}"><sharedItems>{items}</sharedItems></cacheField>'
        )
    definition = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<pivotCacheDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<cacheFields count="{len(fields)}">{"".join(field_nodes)}</cacheFields>'
        '</pivotCacheDefinition>'
    )
    records = []
    for row in rows:
        cells = []
        for column, value in enumerate(row):
            if value is None:
                cells.append('<m/>')
            elif isinstance(value, str):
                cells.append(f'<x v="{indexes[column][value]}"/>')
            else:
                cells.append(f'<n v="{value}"/>')
        records.append(f'<r>{"".join(cells)}</r>')
    record_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<pivotCacheRecords xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'{"".join(records)}</pivotCacheRecords>'
    )
    return definition, record_xml


def make_workbook(path, sheets, pivot=None):
    sheet_nodes = []
    rel_nodes = []
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, (name, rows) in enumerate(sheets, start=1):
            sheet_nodes.append(
                f'<sheet name="{escape(name)}" sheetId="{index}" '
                f'r:id="rId{index}"/>'
            )
            rel_nodes.append(
                f'<Relationship Id="rId{index}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                f'Target="worksheets/sheet{index}.xml"/>'
            )
            archive.writestr(f"xl/worksheets/sheet{index}.xml", worksheet_xml(rows))
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets>{"".join(sheet_nodes)}</sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'{"".join(rel_nodes)}</Relationships>',
        )
        if pivot:
            definition, records = pivot_xml(*pivot)
            archive.writestr("xl/pivotCache/pivotCacheDefinition1.xml", definition)
            archive.writestr("xl/pivotCache/pivotCacheRecords1.xml", records)


class ExcelSourceTests(unittest.TestCase):
    def test_regular_worksheet_adds_count_for_raw_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "raw.xlsx"
            make_workbook(source, [("事故原始資料", [
                ["交通事故明細"],
                ["事故類別", "發生月", "路段", "年齡"],
                ["A2", 1, "文化路", 25],
                ["A2", 2, "民生路", None],
            ])])
            data = read_excel_source(source, PREFERRED)
        self.assertEqual(data.source_type, "worksheet")
        self.assertEqual(data.sheet_name, "事故原始資料")
        self.assertEqual(data.row_mode, "raw")
        self.assertEqual(data.headers[-1], "件數")
        self.assertEqual([row[-1] for row in data.rows], [1, 1])

    def test_worksheet_preserves_aggregated_count(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "aggregate.xlsx"
            make_workbook(source, [("統計", [
                ["事故類別", "發生月", "件數"],
                ["A2", 1, 12],
                ["A1", 2, 2],
            ])])
            data = read_excel_source(source, PREFERRED)
        self.assertEqual(data.row_mode, "aggregated")
        self.assertEqual(sum(row[-1] for row in data.rows), 14)

    def test_richer_pivot_cache_beats_displayed_pivot_summary(self):
        pivot_fields = ["事故類別", "發生月", "路段", "交叉路名", "肇事原因", "年齡", "當事者區分", "件數"]
        pivot_rows = [["A2", 1, "文化路", "民生路", "未依規定讓車", 25, "C03-普通重型機車", 3]]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "pivot.xlsm"
            make_workbook(source, [("分析表", [
                ["事故類別", "件數"],
                ["A2", 3],
            ])], pivot=(pivot_fields, pivot_rows))
            data = read_excel_source(source, PREFERRED)
        self.assertEqual(data.source_type, "pivot-cache")
        self.assertEqual(data.headers, pivot_fields)
        self.assertEqual(data.rows[0][-1], 3)

    def test_legacy_xls_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "legacy.xls"
            source.write_bytes(b"not an OOXML file")
            with self.assertRaisesRegex(ValueError, "另存為 .xlsx 或 .xlsm"):
                read_excel_source(source, PREFERRED)


if __name__ == "__main__":
    unittest.main()
